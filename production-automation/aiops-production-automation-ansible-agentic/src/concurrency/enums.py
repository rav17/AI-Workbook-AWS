"""Enums for the Concurrent Execution Safety module."""

from enum import Enum


class ConflictResolutionStrategy(Enum):
    """Strategy applied when a resource conflict is detected."""

    QUEUE = "QUEUE"
    REJECT = "REJECT"
    PREEMPT = "PREEMPT"


class CircuitBreakerStateEnum(Enum):
    """Circuit breaker state machine states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ExecutionDecisionType(Enum):
    """Decision outcome for a remediation execution request."""

    ALLOWED = "ALLOWED"
    QUEUED = "QUEUED"
    REJECTED = "REJECTED"
    SUPPRESSED = "SUPPRESSED"
