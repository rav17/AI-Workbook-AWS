"""Data models for SmartBanker. Traces: R1, R12, R13, R28."""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field
import uuid


class Status(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExecutionResult(BaseModel):
    """Structured output contract for all worker agents. Traces: R12, R28, R29, R30, R31, R33, R35, R36."""
    status: Literal["success", "failure"]
    confidence: Literal["high", "medium", "low"]
    recommendation: str
    risk_level: Literal["low", "medium", "high"]
    issues: list[str] = Field(default_factory=list)
    explainability_summary: str = ""
    disclaimer: str = ""
    worker_domain: str = ""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # Phase 2 fields
    recommendation_source: str = ""
    non_fiduciary_disclaimer: str = ""
    scope_limitation: str = ""
    facilitation_summary: str = ""
    priority_level: str = ""
    estimated_processing_time: str = ""
    tracking_reference: str = ""
    commission_disclosure: str = ""
    low_confidence_warning: str = ""


WORKER_DOMAINS = [
    "spending_analysis",
    "savings_advice",
    "investment_advice",
    "loan_advice",
    "financial_query",
    "risk_compliance",
    "service_request",
    "value_assessment",
]


class PlanTask(BaseModel):
    """A single task within a Plan. Traces: R1."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: str
    assigned_worker: str
    execution_order: int = Field(default=0, ge=0)
    required_tools: list[str] = Field(default_factory=list)
    context_hints: str = ""


class Plan(BaseModel):
    """Structured plan produced by the Coordinator. Traces: R1."""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    original_request: str
    tasks: list[PlanTask]
    excluded_strategies: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InteractionRecord(BaseModel):
    """Short-term memory record (DynamoDB). Traces: R9, R26, R28, R29."""
    user_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    input: str
    output: str
    status: Literal["success", "failure"]
    confidence: Literal["high", "medium", "low"]
    intent: str = ""
    worker_domain: str = ""
    strategy_used: str = ""
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # Phase 2 fields
    channel_id: str = ""
    priority_level: str = ""
    service_request_type: str = ""


class FinancialPattern(BaseModel):
    """Long-term semantic memory record. Traces: R10."""
    pattern_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    pattern_type: Literal["behavior", "recommendation", "failure", "preference"]
    content: str
    embedding: Optional[list[float]] = None
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SimilarPattern(BaseModel):
    """Result from semantic similarity search."""
    pattern_id: str = ""
    content: str = ""
    similarity_score: float = 0.0
    metadata: dict = Field(default_factory=dict)


class MemoryContext(BaseModel):
    """Filtered memory context sent to LLM. Traces: R11."""
    failures: list[InteractionRecord] = Field(default_factory=list)
    patterns: list[SimilarPattern] = Field(default_factory=list)
    intent: str = ""
    # Legacy aliases kept for backward compatibility
    @property
    def recent_failures(self) -> list[InteractionRecord]:
        return self.failures

    @property
    def similar_patterns(self) -> list[SimilarPattern]:
        return self.patterns


class PruneEvent(BaseModel):
    """Record of a pruned interaction from short-term memory. Traces: R9.2, R14.1."""
    user_id: str
    pruned_timestamp: str
    reason: str = "exceeded_max_interactions"


class ValidationResult(BaseModel):
    """Result of schema or tool invocation validation."""
    valid: bool
    errors: list[str] = Field(default_factory=list)


class ReflectionDecision(BaseModel):
    """Output of the reflection step. Traces: R13."""
    action: Literal["retry", "finalize"] = "finalize"
    reason: str = ""
    failed_tasks: list[str] = Field(default_factory=list)
    # Legacy aliases for backward compatibility
    @property
    def should_retry(self) -> bool:
        return self.action == "retry"

    @property
    def failed_task_ids(self) -> list[str]:
        return self.failed_tasks


class IntrospectionReport(BaseModel):
    """Result of introspecting an ExecutionResult for schema and quality."""
    schema_valid: bool
    quality_score: str = ""
    issues: list[str] = Field(default_factory=list)


class FinalResponse(BaseModel):
    """Response returned to the user. Traces: R17."""
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    status: Literal["success", "partial_success", "failure"] = "success"
    recommendations: list[ExecutionResult] = Field(default_factory=list)
    retries_used: int = 0
    warnings: list[str] = Field(default_factory=list)


# --- Phase 2 Models (R18–R39) ---


class ProgrammeTier(BaseModel):
    """Configurable banking programme tier. Traces: R18."""
    name: str
    min_balance: float = 0.0
    salary_credit: float = 0.0
    benefits: list[str] = Field(default_factory=list)


class FamilyGroup(BaseModel):
    """Family group linking accounts for shared tier benefits. Traces: R22."""
    primary_holder: str
    linked_members: list[str] = Field(default_factory=list)
    max_group_size: int = 6


class FeeWaiverMatrix(BaseModel):
    """Tier-to-fee-waiver mapping. Traces: R23."""
    tier_waivers: dict[str, list[str]] = Field(default_factory=dict)
    tier_pricing: dict[str, dict[str, str]] = Field(default_factory=dict)


class ServiceRequest(BaseModel):
    """User-initiated service request. Traces: R28."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    request_type: Literal[
        "account_modification",
        "charge_dispute",
        "failed_transaction_inquiry",
        "service_modification",
        "card_issue",
        "document_request",
        "kyc_update",
        "cheque_book_request",
        "other",
    ]
    description: str
    status: Literal["received", "in_progress", "escalated", "resolved", "closed"] = "received"
    priority_level: str = "standard"
    tracking_reference: str = ""
    escalation: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class EscalationResult(BaseModel):
    """Result of escalating a service request. Traces: R28."""
    tracking_reference: str
    estimated_timeline: str
    escalation_reason: str = ""
    escalation_path: str = ""


class ProactiveNotification(BaseModel):
    """Proactive engagement notification. Traces: R37."""
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    opportunity_type: Literal[
        "fee_waiver_expiry",
        "investment_maturity",
        "tier_upgrade_eligibility",
        "promotional_offer",
        "tier_downgrade_risk",
        "savings_opportunity",
    ]
    message: str
    priority: Literal["low", "medium", "high"] = "medium"
    tier_specific: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ValueAssessmentResult(BaseModel):
    """Value assessment of user banking activity vs tier benefits. Traces: R39."""
    user_id: str
    current_tier: str
    activity_summary: dict = Field(default_factory=dict)
    utilized_benefits: list[str] = Field(default_factory=list)
    unused_benefits: list[str] = Field(default_factory=list)
    value_score: float = Field(default=0.0, ge=0.0, le=1.0)
    tier_recommendation: Optional[dict] = None
    self_service_sufficient: bool = False
