from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from aria.agents.aria.statement_explainer.models import (
    AgentActivityEvent,
    StatementAnalysisRequest,
    StatementTransaction,
)


def _transaction(**overrides: object) -> StatementTransaction:
    values: dict[str, object] = {
        "trans_id": "TX-001",
        "value_date": "2026-01-04",
        "amount": Decimal("125.50"),
        "dr_cr_ind": "D",
        "narrative": "Utility debit",
        "category": "utilities",
        "balance_after": Decimal("1000.00"),
        "currency": "INR",
    }
    values.update(overrides)
    return StatementTransaction.model_validate(values)


def test_statement_transaction_validation_normalizes_safe_source_fields() -> None:
    row = _transaction(trans_id=" TX-001 ", dr_cr_ind="d", category="UNKNOWN")

    assert row.trans_id == "TX-001"
    assert row.dr_cr_ind == "D"
    assert row.category == "uncategorized"
    assert row.amount == Decimal("125.50")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("trans_id", "  "),
        ("value_date", "2026-02-30"),
        ("amount", "NaN"),
        ("amount", "Infinity"),
        ("dr_cr_ind", "X"),
        ("narrative", " "),
        ("balance_after", "-Infinity"),
    ],
)
def test_statement_transaction_rejects_invalid_source_fields(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _transaction(**{field: value})


def test_analysis_request_uses_optional_opaque_reference_and_bounded_context() -> None:
    request = StatementAnalysisRequest(
        question="Summarize my statement",
        statement_ref="stmt-opaque-001",
        session_context="x" * 1000,
    )

    assert request.statement_ref == "stmt-opaque-001"
    assert len(request.session_context) == 400
    assert StatementAnalysisRequest(question="List my assigned statements").statement_ref is None


def test_activity_event_serializes_statement_reference_not_fixture_id() -> None:
    event = AgentActivityEvent(
        run_id="run-1",
        sequence=1,
        event_type="tool.completed",
        statement_ref="stmt-opaque-001",
        tool_name="get_transactions",
        transaction_ids=["TX-001"],
    )

    serialized = event.model_dump(mode="json")
    assert serialized["statement_ref"] == "stmt-opaque-001"
    assert "statement_id" not in serialized
