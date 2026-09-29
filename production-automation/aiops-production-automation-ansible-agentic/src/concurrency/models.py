"""Data models for the Concurrent Execution Safety module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.concurrency.enums import (
    CircuitBreakerStateEnum,
    ConflictResolutionStrategy,
    ExecutionDecisionType,
)
from src.models import Severity


@dataclass
class HostLock:
    """A mutual exclusion lock for a specific host."""

    host: str
    incident_id: str
    acquired_at: datetime
    ttl_seconds: int
    action_name: str


@dataclass
class QueueEntry:
    """An entry in the priority queue awaiting execution."""

    incident_id: str
    target_host: str
    action_name: str
    severity: Severity
    enqueued_at: datetime
    correlation_group: str

    def priority_key(self) -> tuple[int, float]:
        """Return sort key: (severity_rank, timestamp).

        Lower severity_rank = higher priority (P1=1, P5=5).
        Earlier timestamp = higher priority within same severity.
        """
        severity_map = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}
        rank = severity_map.get(self.severity.value, 5)
        return (rank, self.enqueued_at.timestamp())


@dataclass
class CircuitBreakerState:
    """Per-host circuit breaker state."""

    host: str
    state: CircuitBreakerStateEnum
    consecutive_failures: int
    last_failure_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    failed_incident_ids: list[str] = field(default_factory=list)
    last_failed_action: Optional[str] = None


@dataclass
class FingerprintRecord:
    """A stored alert fingerprint for deduplication."""

    fingerprint: str
    incident_id: str
    created_at: datetime
    ttl_seconds: int


@dataclass
class ResourceConflict:
    """Details of a detected resource conflict."""

    conflicting_categories: list[str]
    blocking_incident_id: str
    blocking_action_name: str
    resolution_strategy: ConflictResolutionStrategy
    estimated_remaining_seconds: Optional[float] = None


@dataclass
class ExecutionDecision:
    """Result of a request_execution call."""

    decision_type: ExecutionDecisionType
    allowed: bool
    reason: Optional[str] = None
    queue_position: Optional[int] = None
    blocking_incident_id: Optional[str] = None


@dataclass
class StateTransition:
    """Record of a circuit breaker state change."""

    host: str
    previous_state: CircuitBreakerStateEnum
    new_state: CircuitBreakerStateEnum
    trigger: str  # failure, cooldown_elapsed, test_success, test_failure, manual_reset


@dataclass
class PreemptionRecord:
    """Record of a preemption event."""

    preempted_incident_id: str
    preempting_incident_id: str
    preempted_severity: Severity
    preempting_severity: Severity
    target_host: str
    timestamp: datetime
    progress_at_preemption: Optional[str] = None
