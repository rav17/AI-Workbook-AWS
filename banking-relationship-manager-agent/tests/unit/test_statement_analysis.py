from __future__ import annotations

from decimal import Decimal

import pytest

from aria.agents.aria.statement_explainer.models import StatementTransaction
from aria.agents.aria.statement_explainer.tools import (
    categorise_spend,
    compare_category_spend,
    detect_anomalies,
    explain_transaction,
    get_transactions,
    summarise_period,
)


def _transaction(
    trans_id: str,
    value_date: str,
    amount: str,
    direction: str = "D",
    category: str = "utilities",
) -> StatementTransaction:
    return StatementTransaction(
        trans_id=trans_id,
        value_date=value_date,
        amount=Decimal(amount),
        dr_cr_ind=direction,
        narrative=f"Narrative for {trans_id}",
        category=category,
        balance_after=Decimal("1000.00"),
        currency="INR",
    )


@pytest.fixture
def rows() -> list[StatementTransaction]:
    return [
        _transaction("UTL-DEC", "2025-12-10", "80.00"),
        _transaction("UTL-JAN", "2026-01-10", "100.00"),
        _transaction("UTL-FEB", "2026-02-10", "90.00"),
        _transaction("UTL-MAR-1", "2026-03-10", "100.00"),
        _transaction("UTL-MAR-2", "2026-03-20", "50.00"),
        _transaction("SAL-MAR", "2026-03-25", "500.00", "C", "salary"),
    ]


def test_get_transactions_filters_and_bounds_rows(rows) -> None:
    result = get_transactions(
        rows,
        start_date="2026-03-01",
        end_date="2026-03-31",
        dr_cr_ind="D",
        min_amount="100.00",
        max_results=1,
    )

    assert len(result) == 1
    assert result[0]["trans_id"] == "UTL-MAR-1"
    assert result[0]["dr_cr_ind"] == "D"
    assert get_transactions(rows, narrative_keyword="does-not-exist") == []


def test_summarise_period_uses_decimal_rows(rows) -> None:
    result = summarise_period(rows, "2026-03-01", "2026-03-31")

    assert result["transaction_count"] == 3
    assert result["debit_total"] == Decimal("150.00")
    assert result["credit_total"] == Decimal("500.00")
    assert result["net_movement"] == Decimal("350.00")
    assert result["category_totals"] == {"utilities": Decimal("150.00")}


def test_categorise_and_compare_spend_report_periods_and_ids(rows) -> None:
    result = categorise_spend(rows, "2026-03-01", "2026-03-31")
    comparison = compare_category_spend(
        rows,
        "utilities",
        current_start="2026-03-01",
        current_end="2026-03-31",
        prior_start="2026-02-01",
        prior_end="2026-02-28",
    )

    assert result["category_totals"] == {"utilities": Decimal("150.00")}
    assert comparison["current_total"] == Decimal("150.00")
    assert comparison["prior_total"] == Decimal("90.00")
    assert comparison["absolute_change"] == Decimal("60.00")
    assert comparison["current_transaction_ids"] == ["UTL-MAR-1", "UTL-MAR-2"]


def test_anomalies_use_three_complete_preceding_months(rows) -> None:
    result = detect_anomalies(rows, "utilities", "2026-03-01", "2026-03-31")

    assert result["baseline_months"] == ["2025-12", "2026-01", "2026-02"]
    assert result["baseline_monthly_average"] == Decimal("90")
    assert result["current_period_total"] == Decimal("150.00")
    assert result["status"] == "ok"
    assert result["baseline_transaction_ids"] == ["UTL-DEC", "UTL-JAN", "UTL-FEB"]


def test_explain_transaction_requires_unique_matching_row(rows) -> None:
    explained = explain_transaction(rows, "UTL-MAR-1")
    missing = explain_transaction(rows, "UNKNOWN")

    assert explained["status"] == "ok"
    assert Decimal(explained["amount"]) == Decimal("100.00")
    assert missing["status"] == "not_found"


def test_tools_reject_invalid_period_and_result_bounds(rows) -> None:
    try:
        get_transactions(rows, start_date="2026-02-30")
    except ValueError as error:
        assert "ISO date" in str(error)
    else:
        raise AssertionError("invalid dates must fail")

    try:
        get_transactions(rows, max_results=101)
    except ValueError as error:
        assert "max_results" in str(error)
    else:
        raise AssertionError("oversized result limits must fail")
