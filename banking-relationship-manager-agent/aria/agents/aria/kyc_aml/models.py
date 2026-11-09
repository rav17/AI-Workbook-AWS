from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class DocumentReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document_ref: str = Field(min_length=1, max_length=256)
    document_type: str = Field(min_length=1, max_length=64)
    jurisdiction: str = Field(min_length=1, max_length=64)


class ExtractedFieldObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str = Field(min_length=1, max_length=64)
    masked_value: str = Field(min_length=1, max_length=256)
    comparison_token: str | None = Field(default=None, max_length=128)
    confidence: float = Field(ge=0, le=1)
    document_ref: str = Field(min_length=1, max_length=256)


class VerificationObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str = Field(min_length=1, max_length=64)
    source_id: str = Field(min_length=1, max_length=128)
    masked_value: str | None = Field(default=None, max_length=256)
    comparison_token: str | None = Field(default=None, max_length=128)
    status: Literal["verified", "missing", "stale", "unavailable", "invalid"]
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("retrieved_at")
    @classmethod
    def normalize_retrieval_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("source retrieval timestamps must include a timezone")
        return value.astimezone(UTC)


class CompliancePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    jurisdiction: str = Field(min_length=1, max_length=64)
    effective_from: datetime
    effective_to: datetime
    supported_document_types: list[str] = Field(min_length=1)
    required_fields: list[str] = Field(min_length=1)
    required_sources_by_field: dict[str, list[str]]
    minimum_extraction_confidence: float = Field(ge=0, le=1)

    @field_validator("effective_from", "effective_to")
    @classmethod
    def normalize_policy_dates(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("compliance policy dates must include a timezone")
        return value.astimezone(UTC)


class AMLFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_code: str = Field(min_length=1, max_length=64)
    severity: Literal["low", "medium", "high", "unknown"]
    evidence_ref: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=512)


class AMLAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["clear", "findings", "incomplete"]
    findings: list[AMLFinding] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("findings")
    @classmethod
    def require_findings_for_flagged_status(
        cls, value: list[AMLFinding], info: ValidationInfo
    ) -> list[AMLFinding]:
        status = info.data.get("status")
        if status == "findings" and not value:
            raise ValueError("findings status requires at least one finding")
        if status == "clear" and value:
            raise ValueError("clear status cannot contain findings")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def require_evidence_for_clear(cls, value: list[str], info: ValidationInfo) -> list[str]:
        if info.data.get("status") == "clear" and not value:
            raise ValueError("clear AML assessment requires evidence references")
        return value


class FieldVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_name: str
    status: Literal[
        "verified",
        "conflict",
        "missing",
        "low_confidence",
        "stale",
        "source_unavailable",
        "unconfigured",
    ]
    evidence_refs: list[str] = Field(default_factory=list)
    reason_code: str


class ComplianceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_id: str
    correlation_id: str | None = None
    status: Literal["evidence_consistent", "review_required", "unassessed"]
    field_results: list[FieldVerificationResult] = Field(default_factory=list)
    aml_findings: list[AMLFinding] = Field(default_factory=list)
    aml_status: Literal["clear", "findings", "unassessed"] = "unassessed"
    policy_version: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    requires_human_review: bool = True
    recommended_kyc_status: None = None


class ComplianceAuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1, max_length=64)
    correlation_id: str | None = Field(default=None, max_length=128)
    subject_hash: str = Field(min_length=16, max_length=64)
    event_type: Literal[
        "document.extract",
        "source.verify",
        "field.match",
        "field.conflict",
        "risk.assess",
        "aml.assess",
        "compliance.escalate",
        "analyst.decision",
    ]
    source_reference: str | None = Field(default=None, max_length=256)
    policy_version: str | None = Field(default=None, max_length=64)
    reason_code: str = Field(min_length=1, max_length=128)
    safe_summary: str = Field(max_length=512)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("created_at")
    @classmethod
    def normalize_audit_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("audit timestamps must include a timezone")
        return value.astimezone(UTC)
