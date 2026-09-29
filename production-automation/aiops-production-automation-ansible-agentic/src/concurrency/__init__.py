"""Concurrent Execution Safety module.

Provides host-level locking, resource conflict detection, alert deduplication,
priority-based queuing, circuit breaker protection, and execution dependency
management to ensure concurrent remediations do not cause cascading failures.
"""

from src.concurrency.enums import (
    CircuitBreakerStateEnum,
    ConflictResolutionStrategy,
    ExecutionDecisionType,
)
from src.concurrency.models import (
    CircuitBreakerState,
    ExecutionDecision,
    FingerprintRecord,
    HostLock,
    PreemptionRecord,
    QueueEntry,
    ResourceConflict,
    StateTransition,
)
from src.concurrency.config import ConcurrencyConfig
from src.concurrency.manager import ConcurrencyManager

__all__ = [
    # Main facade
    "ConcurrencyManager",
    "ConcurrencyConfig",
    # Enums
    "CircuitBreakerStateEnum",
    "ConflictResolutionStrategy",
    "ExecutionDecisionType",
    # Models
    "CircuitBreakerState",
    "ExecutionDecision",
    "FingerprintRecord",
    "HostLock",
    "PreemptionRecord",
    "QueueEntry",
    "ResourceConflict",
    "StateTransition",
]
