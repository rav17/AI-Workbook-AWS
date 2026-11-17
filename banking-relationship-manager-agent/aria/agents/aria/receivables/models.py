from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FrozenDict(dict[str, Any]):
    """JSON-compatible immutable mapping for nested boundary collections."""

    def __init__(self, value: dict[str, Any] | None = None) -> None:
        dict.__init__(self, {key: deep_freeze(item) for key, item in (value or {}).items()})

    def __setitem__(self, key: str, value: Any) -> None:
        raise TypeError("immutable mapping cannot be changed")

    def __delitem__(self, key: str) -> None:
        raise TypeError("immutable mapping cannot be changed")

    def clear(self) -> None:
        raise TypeError("immutable mapping cannot be changed")

    def pop(self, key: str, default: Any = None) -> Any:
        raise TypeError("immutable mapping cannot be changed")

    def popitem(self) -> tuple[str, Any]:
        raise TypeError("immutable mapping cannot be changed")

    def setdefault(self, key: str, default: Any = None) -> Any:
        raise TypeError("immutable mapping cannot be changed")

    def update(self, __m: Any = ..., **kwargs: Any) -> None:
        raise TypeError("immutable mapping cannot be changed")


def deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return FrozenDict(value)
    if isinstance(value, list):
        return tuple(deep_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(deep_freeze(item) for item in value)
    return value


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AuthoritySource(StrEnum):
    TRUSTED_SERVER_PROVIDER = "trusted_server_provider"
    SYNTHETIC_HARNESS = "synthetic_harness"


class Outcome(StrEnum):
    RECOMMEND = "recommend"
    NO_RECOMMENDATION = "no_recommendation"
    ESCALATE = "escalate"
    OUT_OF_SCOPE = "out_of_scope"


class DecisionKind(StrEnum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"
    ESCALATE = "escalate"


class Availability(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    MALFORMED = "malformed"
    CONFLICTING = "conflicting"


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class EvidenceType(StrEnum):
    PAYMENT = "payment"
    VIRTUAL_ACCOUNT = "virtual_account"
    CUSTOMER = "customer"
    INVOICE = "invoice"
    PAYMENT_HISTORY = "payment_history"
    ALLOCATION_LEDGER = "allocation_ledger"
    POLICY = "policy"


class EvidenceClassification(StrEnum):
    AUTHORITATIVE = "authoritative"
    INFERENCE = "inference"


class ExceptionState(StrEnum):
    RECEIVED = "received"
    INVESTIGATING = "investigating"
    AWAITING_ANALYST = "awaiting_analyst"
    APPROVED_AWAITING_CONFIRMATION = "approved_awaiting_confirmation"
    REVISED = "revised"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    TASK_CREATED = "task_created"


class CheckStatus(StrEnum):
    CLEAR = "clear"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class AllocationCheckStatus(StrEnum):
    CLEAR = "clear"
    PRESENT = "present"
    CONFIRMED = "confirmed"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class TrustedContext(FrozenModel):
    tenant_id: str = Field(min_length=1, max_length=80)
    user_id: str = Field(min_length=1, max_length=80)
    session_id: str = Field(min_length=1, max_length=120)
    correlation_id: str = Field(min_length=1, max_length=120)
    analyst_role: str = "receivables_operations_analyst"
    authority_source: AuthoritySource

    @field_validator("analyst_role")
    @classmethod
    def synthetic_role_only(cls, value: str) -> str:
        if value != "receivables_operations_analyst":
            raise ValueError("unsupported synthetic analyst role")
        return value


class ReceivablesException(FrozenModel):
    exception_id: str = Field(pattern=r"^EXC-SYN-[A-Z0-9]{3,8}$")
    payment_id: str = Field(pattern=r"^PAY-SYN-[A-Z0-9]{3,8}$")
    intake_hint: str = Field(max_length=80)
    customer_scope: str = "CORP-SYN-001"
    currency: str = "USD"
    state: ExceptionState = ExceptionState.RECEIVED


class DuplicateCheckResult(FrozenModel):
    status: CheckStatus
    matched_record_ids: tuple[str, ...] = ()


class PriorAllocationResult(FrozenModel):
    status: CheckStatus
    matched_record_ids: tuple[str, ...] = ()


class PaymentData(FrozenModel):
    payment_id: str = Field(pattern=r"^PAY-SYN-[A-Z0-9]{3,8}$")
    amount: str
    currency: str
    value_date: date
    va_id: str | None
    remittance_reference: str = ""
    payer_name: str = ""
    narrative: str = ""
    bank_reference: str = ""

    @field_validator("amount")
    @classmethod
    def payment_amount_finite(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("payment amount must be a decimal string") from exc
        if not amount.is_finite():
            raise ValueError("payment amount must be finite")
        return value


class VirtualAccountData(FrozenModel):
    va_id: str
    status: str
    customer_id: str
    effective_from: date
    effective_to: date


class CustomerData(FrozenModel):
    customer_id: str
    known_payer_names: tuple[str, ...] = ()


class InvoiceData(FrozenModel):
    invoice_id: str
    customer_id: str
    currency: str
    status: str
    outstanding_amount: str
    reference: str = ""
    due_date: date | None = None
    original_amount: str | None = None

    @field_validator("outstanding_amount", "original_amount")
    @classmethod
    def invoice_amount_finite(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                amount = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError("invoice amount must be a decimal string") from exc
            if not amount.is_finite():
                raise ValueError("invoice amount must be finite")
        return value


class AllocationRecord(FrozenModel):
    allocation_id: str
    payment_id: str
    invoice_id: str
    status: str


class SourceRecord(FrozenModel):
    source_type: EvidenceType
    source_record_id: str = Field(min_length=1, max_length=100)
    source_version: str = Field(min_length=1, max_length=160)
    values: dict[str, Any]

    @field_validator("values", mode="after")
    @classmethod
    def freeze_source_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], deep_freeze(value))


class SnapshotEntry(FrozenModel):
    source_type: EvidenceType
    source_record_id: str
    source_version: str
    record_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SnapshotManifest(FrozenModel):
    entries: tuple[SnapshotEntry, ...]
    snapshot_id: str
    snapshot_version: str
    aggregate_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class EvidenceDisclosure(FrozenModel):
    source_type: EvidenceType
    availability: Availability
    freshness: Freshness
    as_of: datetime
    age_seconds: int | None = None
    safe_detail: str | None = None

    @field_validator("as_of")
    @classmethod
    def disclosure_time_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evidence disclosure timestamp must be timezone-aware")
        return value.astimezone(UTC)


class EvidenceCitation(FrozenModel):
    source_type: EvidenceType
    source_record_id: str
    snapshot_id: str
    snapshot_version: str
    record_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    classification: EvidenceClassification
    evidence_kind: str = "source_fact"
    as_of: datetime
    age_seconds: int = Field(ge=0)
    availability: Availability = Availability.AVAILABLE
    freshness: Freshness = Freshness.FRESH

    @field_validator("as_of")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evidence timestamp must be timezone-aware")
        return value.astimezone(UTC)


class CandidateAllocation(FrozenModel):
    invoice_id: str
    eligible: bool
    exclusion_reason: str | None = None
    score: int = Field(ge=0)
    band: str
    expected_amount: Decimal
    variance: Decimal
    within_tolerance: bool
    evidence_ids: tuple[str, ...] = ()


class InvestigationProposal(FrozenModel):
    proposal_id: str
    exception_id: str
    payment_id: str
    version: int = Field(ge=1)
    outcome: Outcome
    classification: str | None
    primary_reason: str
    duplicate_status: CheckStatus = CheckStatus.UNKNOWN
    prior_allocation_status: AllocationCheckStatus = AllocationCheckStatus.UNKNOWN
    secondary_reasons: tuple[str, ...] = ()
    proposed_invoice_id: str | None = None
    payment_amount: Decimal | None = None
    expected_amount: Decimal | None = None
    variance: Decimal | None = None
    currency: str = "USD"
    policy_id: str | None = None
    policy_version: str | None = None
    evidence: tuple[EvidenceCitation, ...] = ()
    evidence_statuses: tuple[EvidenceDisclosure, ...] = ()
    snapshot: SnapshotManifest | None = None
    created_at: datetime
    expires_at: datetime
    draft_operations_note: str
    safe_next_step: str | None = None
    content_hash: str
    candidates: tuple[CandidateAllocation, ...] = ()

    @field_validator("created_at", "expires_at")
    @classmethod
    def proposal_time_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("proposal timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def recommendation_payload_consistent(self) -> InvestigationProposal:
        if self.outcome == Outcome.RECOMMEND:
            if not self.proposed_invoice_id or self.variance is None or not self.evidence:
                raise ValueError("recommendations require an invoice, variance, and evidence")
        elif self.proposed_invoice_id is not None:
            raise ValueError("non-recommendations cannot propose an invoice")
        return self


class DecisionState(FrozenModel):
    tenant_id: str
    session_id: str
    exception_id: str
    current_proposal_version: int = Field(ge=1)
    decision_revision: int = Field(ge=0)
    state: ExceptionState
    confirmation_id: str | None = None


class AnalystDecision(FrozenModel):
    decision_id: str
    proposal_id: str
    proposal_version: int = Field(ge=1)
    decision: DecisionKind
    analyst_id: str
    decision_revision: int = Field(ge=1)
    rationale: str = Field(default="", max_length=500)
    created_at: datetime


class MockCaseTaskPayload(FrozenModel):
    exception_id: str
    proposal_id: str
    proposal_version: int
    payment_id: str
    invoice_id: str
    customer_id: str
    currency: str
    payment_amount: str
    expected_amount: str
    variance: str
    policy_id: str
    policy_version: str
    evidence_ids: tuple[str, ...]
    decision_revision: int
    summary: str = Field(max_length=280)


class ConfirmationBinding(FrozenModel):
    confirmation_id: str
    tenant_id: str
    session_id: str
    exception_id: str
    proposal_id: str
    proposal_version: int
    decision_revision: int
    payload_hash: str
    context_binding: str


class CaseTask(FrozenModel):
    case_task_id: str
    confirmation_id: str
    payload_hash: str
    payload: MockCaseTaskPayload
    tenant_id: str
    session_id: str
    created_at: datetime


class AuditEvent(FrozenModel):
    event_id: str
    correlation_id: str
    sequence: int
    event_type: str
    actor: str
    source_refs: tuple[str, ...] = ()
    policy_version: str | None = None
    reason_codes: tuple[str, ...] = ()
    proposal_version: int | None = None
    proposal_id: str | None = None
    confirmation_id: str | None = None
    case_task_id: str | None = None
    safe_summary: str = Field(max_length=500)
    created_at: datetime


class SourceResult(FrozenModel):
    status: Availability
    records: tuple[SourceRecord, ...] = ()
    as_of: datetime
    detail: str | None = None

    @field_validator("as_of")
    @classmethod
    def result_time_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source timestamp must be timezone-aware")
        return value.astimezone(UTC)


class PolicyRecord(FrozenModel):
    policy_id: str
    version: str
    tenant_id: str
    currency: str
    exception_types: tuple[str, ...]
    effective_from: date
    effective_to: date
    approval_status: str
    approval_record_ref: str
    tolerance_abs: Decimal
    tolerance_pct: Decimal
    weights: dict[str, int]
    bands: dict[str, int]
    competing_margin: int
    duplicate_window_days: int
    proposal_ttl_minutes: int
    confirmation_window_minutes: int
    freshness_max_age_seconds: dict[str, int]

    @field_validator("weights", "bands", "freshness_max_age_seconds", mode="after")
    @classmethod
    def freeze_policy_mappings(cls, value: dict[str, Any]) -> dict[str, Any]:
        return cast(dict[str, Any], deep_freeze(value))

    @model_validator(mode="after")
    def effective_window_valid(self) -> PolicyRecord:
        if self.effective_to < self.effective_from:
            raise ValueError("policy effective window is inverted")
        if self.tolerance_abs < 0 or self.tolerance_pct < 0:
            raise ValueError("policy tolerances cannot be negative")
        return self
