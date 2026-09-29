"""Core domain dataclasses for the Agentic AI system.

Contains RemediationStep, RemediationPlan, CorrelationGroup,
IncidentRecord, HumanResponse, and PrerequisiteResult models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.agentic_ai.models.enums import EscalationStatus, FallbackReason
from src.models import EnrichedAlert


@dataclass
class RemediationStep:
    """A single step in a multi-step remediation plan.

    Attributes:
        step_number: Sequential step number (1-based).
        action: SSM document name or command to execute.
        target_resource: EC2 instance ID or resource ARN.
        parameters: Key-value parameters passed to the SSM document.
        expected_outcome: Description of the expected result.
    """

    step_number: int
    action: str
    target_resource: str
    parameters: dict[str, str] = field(default_factory=dict)
    expected_outcome: str = ""


@dataclass
class RemediationPlan:
    """Structured output from the AI Reasoning Agent.

    Attributes:
        incident_ids: All correlated incident IDs addressed by this plan.
        steps: Ordered remediation steps (max 20).
        confidence_score: AI confidence in the plan (0.0 to 1.0).
        reasoning_explanation: AI reasoning text (max 2048 characters).
        selected_action: Primary remediation action name.
        target_resource: Primary target resource identifier.
        requires_escalation: Whether human escalation is needed.
        fallback_used: Whether rule-based fallback was triggered.
        fallback_reason: Reason for fallback if applicable.
        truncation_flag: Whether the model response was truncated at token limit.
    """

    incident_ids: list[str]
    steps: list[RemediationStep]
    confidence_score: float
    reasoning_explanation: str
    selected_action: str
    target_resource: str
    requires_escalation: bool = False
    fallback_used: bool = False
    fallback_reason: Optional[FallbackReason] = None
    truncation_flag: bool = False

    def __post_init__(self) -> None:
        """Validate field constraints after initialization."""
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {self.confidence_score}"
            )
        if len(self.steps) > 20:
            raise ValueError(
                f"steps must contain at most 20 items, got {len(self.steps)}"
            )
        if len(self.reasoning_explanation) > 2048:
            raise ValueError(
                f"reasoning_explanation must be at most 2048 characters, "
                f"got {len(self.reasoning_explanation)}"
            )


@dataclass
class CorrelationGroup:
    """A group of correlated alerts within a time window.

    Attributes:
        group_id: Unique identifier for this correlation group.
        alerts: List of correlated enriched alerts (max 50).
        common_labels: Shared label values across alerts in the group.
        window_start: Start of the correlation time window.
        window_end: End of the correlation time window.
    """

    group_id: str
    alerts: list[EnrichedAlert]
    common_labels: dict[str, str]
    window_start: datetime
    window_end: datetime

    def __post_init__(self) -> None:
        """Validate field constraints after initialization."""
        if len(self.alerts) > 50:
            raise ValueError(
                f"alerts must contain at most 50 items, got {len(self.alerts)}"
            )


@dataclass
class IncidentRecord:
    """Historical incident record stored in DynamoDB.

    Attributes:
        incident_id: Unique incident identifier (partition key).
        alert_name: Name of the alert that triggered this incident.
        severity: Alert severity level.
        affected_service: Service affected by the incident.
        affected_resource: Target resource identifier.
        remediation_action: Action taken to remediate.
        outcome: Result of remediation (success, failure, timeout).
        execution_duration_seconds: Duration of execution in seconds.
        timestamp_completed: When the remediation completed.
        expiry_timestamp: Unix epoch for DynamoDB TTL auto-expiry.
        model_id: Bedrock model used for reasoning.
        input_token_count: Tokens sent to the model.
        output_token_count: Tokens received from the model.
        reasoning_latency_ms: AI reasoning duration in milliseconds.
        confidence_score: AI confidence score (0.0-1.0).
        reasoning_summary: AI reasoning text (max 2048 chars).
        escalation_status: Escalation lifecycle state.
        escalation_responder: Identity of the human responder.
        escalation_response_timestamp: When the human responded.
        fallback_used: Whether fallback was triggered.
        fallback_reason: Reason for fallback if applicable.
    """

    incident_id: str
    alert_name: str
    severity: str
    affected_service: str
    affected_resource: str
    remediation_action: str
    outcome: str  # success, failure, timeout
    execution_duration_seconds: float
    timestamp_completed: datetime
    expiry_timestamp: int  # Unix epoch for DynamoDB TTL

    # AI-specific fields
    model_id: Optional[str] = None
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None
    reasoning_latency_ms: Optional[float] = None
    confidence_score: Optional[float] = None
    reasoning_summary: str = ""

    # Escalation fields
    escalation_status: Optional[EscalationStatus] = None
    escalation_responder: Optional[str] = None
    escalation_response_timestamp: Optional[datetime] = None

    # Fallback tracking
    fallback_used: bool = False
    fallback_reason: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate field constraints after initialization."""
        if self.confidence_score is not None and not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(
                f"confidence_score must be between 0.0 and 1.0, got {self.confidence_score}"
            )
        if len(self.reasoning_summary) > 2048:
            raise ValueError(
                f"reasoning_summary must be at most 2048 characters, "
                f"got {len(self.reasoning_summary)}"
            )


@dataclass
class HumanResponse:
    """Human response to an escalation.

    Attributes:
        action: One of "approve", "reject_with_alternative", or "reject".
        responder_identity: Identity of the human responder.
        timestamp: When the response was provided.
        alternative_action: Alternative action if rejecting with alternative.
    """

    action: str  # "approve", "reject_with_alternative", "reject"
    responder_identity: str
    timestamp: datetime
    alternative_action: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate action is one of the allowed values."""
        valid_actions = {"approve", "reject_with_alternative", "reject"}
        if self.action not in valid_actions:
            raise ValueError(
                f"action must be one of {valid_actions}, got '{self.action}'"
            )


@dataclass
class PrerequisiteResult:
    """Result of SSM prerequisite checks.

    Attributes:
        is_ready: Whether the instance is ready for SSM execution.
        registration_status: Whether the instance is registered with SSM.
        online_status: Whether the instance is online.
        iam_role_attached: Whether the required IAM role is attached.
        error_message: Description of the specific prerequisite failure.
    """

    is_ready: bool
    registration_status: bool
    online_status: bool
    iam_role_attached: bool
    error_message: str = ""
