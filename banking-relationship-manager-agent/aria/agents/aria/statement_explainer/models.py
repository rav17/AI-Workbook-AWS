from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_DR_CR = {"D", "C"}
_ALLOWED_CATEGORIES = {
    "salary",
    "transfer",
    "standing_order",
    "fee",
    "utilities",
    "groceries",
    "dining",
    "travel",
    "entertainment",
    "uncategorized",
}


class StatementTransaction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    trans_id: str
    value_date: str
    amount: Decimal
    dr_cr_ind: str
    narrative: str
    category: str
    balance_after: Decimal
    currency: str = "INR"

    @field_validator("trans_id")
    @classmethod
    def validate_trans_id(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("trans_id must be a non-empty string")
        return value.strip()

    @field_validator("value_date")
    @classmethod
    def validate_value_date(cls, value: str) -> str:
        from datetime import date

        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:  # pragma: no cover - guard branch
            raise ValueError("value_date must be an ISO date (YYYY-MM-DD)") from exc

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal | str | int | float) -> Decimal:
        try:
            dec = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("amount must be a finite decimal value") from exc
        if not dec.is_finite():
            raise ValueError("amount must be finite")
        if dec < 0:
            raise ValueError("amount must be non-negative")
        return dec

    @field_validator("dr_cr_ind")
    @classmethod
    def validate_dr_cr_ind(cls, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in _ALLOWED_DR_CR:
            raise ValueError("dr_cr_ind must be 'D' or 'C'")
        return normalized

    @field_validator("narrative")
    @classmethod
    def validate_narrative(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("narrative must not be empty")
        return value.strip()

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if not normalized:
            raise ValueError("category must not be empty")
        if normalized not in _ALLOWED_CATEGORIES:
            return "uncategorized"
        return normalized

    @field_validator("balance_after")
    @classmethod
    def validate_balance_after(cls, value: Decimal | str | int | float) -> Decimal:
        try:
            dec = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("balance_after must be a finite decimal value") from exc
        if not dec.is_finite():
            raise ValueError("balance_after must be finite")
        return dec


class StatementAnalysisRequest(BaseModel):
    statement_ref: str | None = None
    question: str
    session_context: str = ""
    filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("statement_ref")
    @classmethod
    def validate_statement_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("statement_ref must be a non-empty opaque reference")
        return value.strip()

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("question must be a non-empty string")
        return value.strip()

    @field_validator("session_context")
    @classmethod
    def validate_session_context(cls, value: str) -> str:
        if value is None:
            return ""
        return str(value)[:400]


class StatementToolResult(BaseModel):
    operation: str
    summary: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    transaction_ids: list[str] = Field(default_factory=list)
    source_rows: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("operation is required")
        return str(value).strip()


class AgentActivityEvent(BaseModel):
    run_id: str
    sequence: int
    event_type: str
    statement_ref: str | None = None
    tool_name: str | None = None
    summary: str = ""
    transaction_ids: list[str] = Field(default_factory=list)
    status: str | None = None
    error_code: str | None = None
    message: str | None = None


class StatementExplainerSession(BaseModel):
    session_id: str
    statement_ref: str | None = None
    conversation_context: str = ""


class StatementAuditRecord(BaseModel):
    run_id: str
    session_id: str
    statement_ref: str | None = None
    sanitized_question: str
    tool_sequence: list[str] = Field(default_factory=list)
    final_status: str
    final_response: str
    cited_transaction_ids: list[str] = Field(default_factory=list)


__all__ = [
    "AgentActivityEvent",
    "StatementAnalysisRequest",
    "StatementAuditRecord",
    "StatementExplainerSession",
    "StatementToolResult",
    "StatementTransaction",
]
