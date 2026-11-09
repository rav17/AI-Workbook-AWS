from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from aria.persistence.statement_store import (
    StatementAccessDenied,
    StatementReadStore,
    principal_scope_key,
)


class FakeDynamoTable:
    def __init__(
        self,
        *,
        item: dict[str, Any] | None = None,
        items: list[dict[str, Any]] | None = None,
        last_key: dict[str, Any] | None = None,
    ) -> None:
        self.item = item
        self.items = items or []
        self.last_key = last_key
        self.get_calls: list[dict[str, Any]] = []
        self.query_calls: list[dict[str, Any]] = []

    def get_item(self, **kwargs: Any) -> dict[str, Any]:
        self.get_calls.append(kwargs)
        return {"Item": self.item} if self.item else {}

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.query_calls.append(kwargs)
        response = {"Items": self.items}
        if self.last_key:
            response["LastEvaluatedKey"] = self.last_key
        return response


def _row() -> dict[str, str]:
    return {
        "trans_id": "TX-001",
        "value_date": "2026-01-10",
        "amount": "75.50",
        "dr_cr_ind": "D",
        "narrative": "Statement debit",
        "category": "utilities",
        "balance_after": "9924.50",
        "currency": "INR",
    }


def test_principal_scope_is_stable_and_does_not_store_raw_identity() -> None:
    first = principal_scope_key("tenant-a", "user-a")
    second = principal_scope_key("tenant-a", "user-a")

    assert first == second
    assert len(first) == 64
    assert "tenant-a" not in first
    assert "user-a" not in first
    assert first != principal_scope_key("tenant-b", "user-a")


def test_list_authorized_statements_returns_only_active_safe_metadata() -> None:
    entitlements = FakeDynamoTable(
        items=[
            {
                "principal_scope": principal_scope_key("tenant-a", "user-a"),
                "statement_ref": "stmt-opaque-001",
                "access_status": "ACTIVE",
                "display_label": "Operating account •••• 4281",
                "currency": "INR",
                "period_start": "2026-01-01",
                "period_end": "2026-03-31",
                "opening_balance": "10000.00",
                "account_id": "must-not-be-returned",
            },
            {
                "principal_scope": principal_scope_key("tenant-a", "user-a"),
                "statement_ref": "stmt-revoked",
                "access_status": "REVOKED",
                "display_label": "Revoked account",
            },
        ]
    )
    store = StatementReadStore(entitlements_table=entitlements, transactions_table=FakeDynamoTable())

    result = store.list_authorized_statements("tenant-a", "user-a")

    assert [item["statement_ref"] for item in result["statements"]] == ["stmt-opaque-001"]
    assert result["statements"][0]["display_label"] == "Operating account •••• 4281"
    assert "account_id" not in result["statements"][0]
    assert entitlements.query_calls[0]["KeyConditionExpression"]


def test_statement_read_checks_entitlement_before_querying_rows() -> None:
    entitlements = FakeDynamoTable(item=None)
    transactions = FakeDynamoTable(items=[_row()])
    store = StatementReadStore(entitlements_table=entitlements, transactions_table=transactions)

    with pytest.raises(StatementAccessDenied):
        store.get_statement_transactions(
            "tenant-a",
            "user-a",
            "stmt-opaque-001",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

    assert len(entitlements.get_calls) == 1
    assert transactions.query_calls == []


def test_statement_read_returns_validated_bounded_page_after_entitlement() -> None:
    entitlement = {
        "principal_scope": principal_scope_key("tenant-a", "user-a"),
        "statement_ref": "stmt-opaque-001",
        "access_status": "ACTIVE",
        "currency": "INR",
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
    }
    next_key = {"statement_ref": "stmt-opaque-001", "transaction_key": "2026-01-10#TX-001"}
    entitlements = FakeDynamoTable(item=entitlement)
    transactions = FakeDynamoTable(
        items=[
            {
                **_row(),
                "statement_ref": "stmt-opaque-001",
                "transaction_key": "2026-01-10#TX-001",
            }
        ],
        last_key=next_key,
    )
    store = StatementReadStore(entitlements_table=entitlements, transactions_table=transactions)

    result = store.get_statement_transactions(
        "tenant-a",
        "user-a",
        "stmt-opaque-001",
        start_date="2026-01-01",
        end_date="2026-01-31",
        page_size=1,
    )

    assert result["status"] == "ok"
    assert Decimal(result["rows"][0]["amount"]) == Decimal("75.50")
    assert result["next_page_token"] == "2026-01-10#TX-001"
    assert transactions.query_calls[0]["Limit"] == 1
    assert transactions.query_calls[0]["ConsistentRead"] is True


def test_revoked_entitlement_and_oversized_pages_fail_closed() -> None:
    revoked = {
        "principal_scope": principal_scope_key("tenant-a", "user-a"),
        "statement_ref": "stmt-opaque-001",
        "access_status": "REVOKED",
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
    }
    entitlements = FakeDynamoTable(item=revoked)
    transactions = FakeDynamoTable(items=[_row()])
    store = StatementReadStore(entitlements_table=entitlements, transactions_table=transactions)

    with pytest.raises(StatementAccessDenied):
        store.get_statement_transactions(
            "tenant-a", "user-a", "stmt-opaque-001", page_size=1
        )
    assert transactions.query_calls == []

    active_store = StatementReadStore(
        entitlements_table=FakeDynamoTable(
            item={
                **revoked,
                "access_status": "ACTIVE",
            }
        ),
        transactions_table=FakeDynamoTable(),
    )
    with pytest.raises(ValueError, match="page_size"):
        active_store.get_statement_transactions(
            "tenant-a", "user-a", "stmt-opaque-001", page_size=101
        )


def test_transaction_id_lookup_uses_statement_scoped_index() -> None:
    entitlement = {
        "principal_scope": principal_scope_key("tenant-a", "user-a"),
        "statement_ref": "stmt-opaque-001",
        "access_status": "ACTIVE",
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
    }
    transaction = {
        **_row(),
        "statement_ref": "stmt-opaque-001",
        "transaction_key": "2026-01-10#TX-001",
        "statement_transaction_id": "stmt-opaque-001#TX-001",
    }
    entitlements = FakeDynamoTable(item=entitlement)
    transactions = FakeDynamoTable(items=[transaction])
    store = StatementReadStore(entitlements_table=entitlements, transactions_table=transactions)

    result = store.get_statement_transactions(
        "tenant-a",
        "user-a",
        "stmt-opaque-001",
        trans_id="TX-001",
    )

    assert result["rows"][0]["trans_id"] == "TX-001"
    assert transactions.query_calls[0]["IndexName"] == "StatementTransactionIdIndex"
