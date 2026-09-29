"""Data models and enums for the Safe Execution Guardrails module."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class RiskLevel(Enum):
    """Blast radius risk classification levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def elevate(self) -> "RiskLevel":
        """Return the next higher risk level, capped at CRITICAL.

        Returns:
            The next higher RiskLevel, or CRITICAL if already at max.
        """
        order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        current_idx = order.index(self)
        next_idx = min(current_idx + 1, len(order) - 1)
        return order[next_idx]


class GuardrailDecisionType(Enum):
    """Possible outcomes of guardrail evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"


class CheckResultType(Enum):
    """Result type for individual guardrail checks."""

    ALLOW = "allow"
    DENY = "deny"
    DEFER = "defer"


@dataclass
class CheckResult:
    """Result of a single guardrail check.

    Attributes:
        result_type: Whether the check allows, denies, or defers.
        check_name: Name of the guardrail check that produced this result.
        reason: Human-readable explanation of the decision.
        metadata: Additional context about the decision.
    """

    result_type: CheckResultType
    check_name: str
    reason: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class ExecutionMode(Enum):
    """Execution mode based on risk level (graduated execution)."""

    AUTO_EXECUTE = "auto_execute"  # LOW risk: execute immediately
    EXECUTE_WITH_BAKING = "execute_with_baking"  # MEDIUM risk: execute + validate
    APPROVAL_REQUIRED = "approval_required"  # HIGH risk: require human approval
    DRY_RUN_FIRST = "dry_run_first"  # CRITICAL risk: preview before execute


class RemediationOutcome(Enum):
    """Outcome of a remediation after baking period validation."""

    EFFECTIVE = "effective"  # Alarm resolved AND host healthy
    INEFFECTIVE = "ineffective"  # Alarm still in ALARM state after baking
    DEGRADED = "degraded"  # Host health check fails post-execution
    INCONCLUSIVE = "inconclusive"  # Unable to determine
    PENDING = "pending"  # Baking period still in progress
    ABORTED = "aborted"  # Stopped by stop condition during execution


@dataclass
class RemediationAction:
    """A remediation action to be evaluated by the guardrail engine.

    Attributes:
        incident_id: Unique identifier for the incident.
        action_name: Name/type of the remediation action (e.g., playbook name).
        target_host: Hostname or FQDN of the target.
        service_name: Name of the service being remediated.
        environment: Deployment environment (dev, staging, prod).
        risk_level: Classified risk level (may be set by classifier).
        severity: Alert severity that triggered this action.
        playbook_path: Path to the remediation playbook.
        extra_vars: Additional variables for the remediation.
        correlation_group: Correlation group ID for grouped alerts.
        pre_approved: Whether this action was already approved by a human.
        ai_generated: Whether this plan came from AI reasoning agent.
    """

    incident_id: str
    action_name: str
    target_host: str
    service_name: str = ""
    environment: str = "prod"
    risk_level: Optional[RiskLevel] = None
    severity: str = "P2"
    playbook_path: str = ""
    extra_vars: dict[str, str] = field(default_factory=dict)
    correlation_group: str = ""
    pre_approved: bool = False
    ai_generated: bool = False


@dataclass
class GuardrailDecision:
    """Final decision from the guardrail engine evaluation.

    Attributes:
        decision_type: ALLOW, DENY, or DEFER.
        action: The remediation action that was evaluated.
        checks_passed: List of checks that returned ALLOW.
        denying_check: The check that caused DENY/DEFER (if applicable).
        reason: Human-readable explanation of the final decision.
        evaluation_duration_seconds: Time taken for the full evaluation.
        timestamp: When the decision was made.
    """

    decision_type: GuardrailDecisionType
    action: RemediationAction
    checks_passed: list[str] = field(default_factory=list)
    denying_check: Optional[str] = None
    reason: str = ""
    evaluation_duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass
class DeferredAction:
    """An action that has been deferred for later re-evaluation.

    Attributes:
        action: The original remediation action.
        deferred_at: When the action was deferred.
        defer_reason: Why it was deferred.
        max_defer_seconds: Maximum time to hold before expiry.
        re_evaluate_on: Event that should trigger re-evaluation.
    """

    action: RemediationAction
    deferred_at: datetime
    defer_reason: str
    max_defer_seconds: int = 3600
    re_evaluate_on: str = ""  # "slot_release", "window_end"
