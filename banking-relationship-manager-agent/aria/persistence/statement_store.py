from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from boto3.dynamodb.conditions import Key

from aria.agents.aria.statement_explainer.models import StatementTransaction

_MAX_PAGE_SIZE = 100
_STATEMENT_REF_PATTERN = re.compile(r"[A-Za-z0-9_-]{8,128}\Z")
_TRANSACTION_KEY_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}#[A-Za-z0-9/_-]{1,64}\Z")


class StatementAccessDenied(Exception):
    """Raised when a verified principal has no active statement entitlement."""


def principal_scope_key(tenant_id: str, user_id: str) -> str:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("verified tenant identity is required")
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("verified user identity is required")
    scope = f"{tenant_id.strip()}\0{user_id.strip()}".encode("utf-8")
    return hashlib.sha256(scope).hexdigest()


def _iso_date(value: str, name: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO date") from exc


class StatementReadStore:
    def __init__(self, *, entitlements_table: Any, transactions_table: Any) -> None:
        self._entitlements_table = entitlements_table
        self._transactions_table = transactions_table

    def list_authorized_statements(
        self,
        tenant_id: str,
        user_id: str,
        *,
        limit: int = 25,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 25:
            raise ValueError("limit must be between 1 and 25")
        principal_scope = principal_scope_key(tenant_id, user_id)
        query: dict[str, Any] = {
            "KeyConditionExpression": Key("principal_scope").eq(principal_scope),
            "Limit": limit,
            "ConsistentRead": True,
        }
        if page_token:
            if not _STATEMENT_REF_PATTERN.fullmatch(page_token):
                raise ValueError("page_token is invalid")
            query["ExclusiveStartKey"] = {
                "principal_scope": principal_scope,
                "statement_ref": page_token,
            }

        response = self._entitlements_table.query(**query)
        statements = []
        for item in response.get("Items", []):
            if (
                item.get("principal_scope") != principal_scope
                or item.get("access_status") != "ACTIVE"
                or not _STATEMENT_REF_PATTERN.fullmatch(str(item.get("statement_ref", "")))
            ):
                continue
            statements.append(
                {
                    "statement_ref": item["statement_ref"],
                    "display_label": str(item.get("display_label", "Statement"))[:80],
                    "currency": str(item.get("currency", ""))[:3],
                    "period_start": _iso_date(item.get("period_start"), "period_start"),
                    "period_end": _iso_date(item.get("period_end"), "period_end"),
                    "opening_balance": str(item["opening_balance"])
                    if item.get("opening_balance") is not None
                    else None,
                }
            )

        last_key = response.get("LastEvaluatedKey") or {}
        return {
            "status": "ok",
            "statements": statements,
            "next_page_token": last_key.get("statement_ref"),
        }

    def get_statement_transactions(
        self,
        tenant_id: str,
        user_id: str,
        statement_ref: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        page_size: int = 100,
        page_token: str | None = None,
        trans_id: str | None = None,
    ) -> dict[str, Any]:
        if not _STATEMENT_REF_PATTERN.fullmatch(str(statement_ref)):
            raise ValueError("statement_ref is invalid")
        if isinstance(page_size, bool) or not 1 <= page_size <= _MAX_PAGE_SIZE:
            raise ValueError("page_size must be between 1 and 100")

        principal_scope = principal_scope_key(tenant_id, user_id)
        entitlement = self._entitlements_table.get_item(
            Key={"principal_scope": principal_scope, "statement_ref": statement_ref},
            ConsistentRead=True,
        ).get("Item")
        if (
            not isinstance(entitlement, dict)
            or entitlement.get("principal_scope") != principal_scope
            or entitlement.get("statement_ref") != statement_ref
            or entitlement.get("access_status") != "ACTIVE"
        ):
            raise StatementAccessDenied("statement is unavailable")

        selected_start = _iso_date(
            start_date or entitlement.get("period_start"), "start_date"
        )
        selected_end = _iso_date(end_date or entitlement.get("period_end"), "end_date")
        if selected_start > selected_end:
            raise ValueError("start_date must not be after end_date")

        if trans_id is not None:
            if not re.fullmatch(r"[A-Za-z0-9/_-]{1,64}", trans_id):
                raise ValueError("trans_id is invalid")
            response = self._transactions_table.query(
                IndexName="StatementTransactionIdIndex",
                KeyConditionExpression=Key("statement_transaction_id").eq(
                    f"{statement_ref}#{trans_id}"
                ),
                Limit=2,
            )
        else:
            query: dict[str, Any] = {
                "KeyConditionExpression": Key("statement_ref").eq(statement_ref)
                & Key("transaction_key").between(
                    f"{selected_start}#",
                    f"{selected_end}#\uffff",
                ),
                "Limit": page_size,
                "ConsistentRead": True,
            }
            if page_token:
                if not _TRANSACTION_KEY_PATTERN.fullmatch(page_token):
                    raise ValueError("page_token is invalid")
                token_date = page_token.split("#", maxsplit=1)[0]
                if not selected_start <= token_date <= selected_end:
                    raise ValueError("page_token is outside the selected date range")
                query["ExclusiveStartKey"] = {
                    "statement_ref": statement_ref,
                    "transaction_key": page_token,
                }
            response = self._transactions_table.query(**query)

        if trans_id is None and page_token:
            if not _TRANSACTION_KEY_PATTERN.fullmatch(page_token):
                raise ValueError("page_token is invalid")
            token_date = page_token.split("#", maxsplit=1)[0]
            if not selected_start <= token_date <= selected_end:
                raise ValueError("page_token is outside the selected date range")

        result_items = response.get("Items", [])
        if trans_id is not None and len(result_items) > 1:
            raise ValueError("transaction ID is not unique within the statement")
        rows = []
        for item in result_items:
            if item.get("statement_ref") != statement_ref:
                continue
            transaction = StatementTransaction.model_validate(
                {
                    "trans_id": item.get("trans_id"),
                    "value_date": item.get("value_date"),
                    "amount": item.get("amount"),
                    "dr_cr_ind": item.get("dr_cr_ind"),
                    "narrative": item.get("narrative"),
                    "category": item.get("category"),
                    "balance_after": item.get("balance_after"),
                    "currency": item.get("currency"),
                }
            )
            if not selected_start <= transaction.value_date <= selected_end:
                continue
            expected_key = f"{transaction.value_date}#{transaction.trans_id}"
            if item.get("transaction_key") != expected_key:
                raise ValueError("statement row key does not match source fields")
            rows.append(transaction.model_dump(mode="json"))

        last_key = response.get("LastEvaluatedKey") or {}
        return {
            "status": "ok",
            "statement_ref": statement_ref,
            "currency": entitlement.get("currency"),
            "rows": rows,
            "next_page_token": last_key.get("transaction_key"),
        }