"""Data models, enums, and configuration for the Concurrency Guard layer.

Defines all data structures used by the concurrency safety mechanisms:
host locking, alert deduplication, conflict matrix, priority queuing,
circuit breakers, and blast radius limiting.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

from src.models import Severity

logger = logging.getLogger(__name__)


# --- Enums ---


class GuardRejectionReason(Enum):
    """Reasons the ConcurrencyGuard may reject an execution."""

    SUPPRESSED = "suppressed"
    LOCK_TIMEOUT = "lock_timeout"
    CIRCUIT_OPEN = "circuit_open"
    QUEUE_FULL = "queue_full"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    CONFLICT_TIMEOUT = "conflict_timeout"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# --- Dataclasses ---


@dataclass
class SuppressionEntry:
    """Tracks when an alert was last allowed through for deduplication."""

    hostname: str
    alert_name: str
    severity: Severity
    timestamp: float  # time.monotonic()


@dataclass
class CircuitBreakerState:
    """Per-host circuit breaker state."""

    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    opened_at: float = 0.0


@dataclass(order=True)
class ExecutionSlot:
    """A queued execution request ordered by priority then arrival time."""

    priority: int  # 1=P1, 2=P2, 3=P3 (lower = higher priority)
    arrival_time: float
    playbook_path: str = field(compare=False)
    target_host: str = field(compare=False)
    extra_vars: dict = field(compare=False, default_factory=dict)
    severity: Optional[Severity] = field(compare=False, default=None)
    alert_name: str = field(compare=False, default="")
    incident_id: str = field(compare=False, default="")


@dataclass
class ConflictGroup:
    """A named group of mutually exclusive playbooks."""

    name: str
    playbooks: list[str]


# --- Configuration ---


@dataclass
class ConcurrencyConfig:
    """Configuration for all concurrency safety mechanisms."""

    host_lock_timeout: float = 120.0
    suppression_window: float = 300.0
    conflict_matrix_path: str = "config/conflict_matrix.yml"
    priority_queue_max_depth: int = 20
    circuit_breaker_threshold: int = 3
    circuit_breaker_recovery: float = 600.0
    max_concurrent_hosts: int = 5
    blast_radius_overflow: int = 50

    @classmethod
    def from_yaml(cls, path: str) -> "ConcurrencyConfig":
        """Load configuration from a YAML file with fallback to defaults.

        If the file is missing or contains invalid YAML, returns a
        ConcurrencyConfig with all default values and logs a warning.

        Args:
            path: Path to the concurrency configuration YAML file.

        Returns:
            A ConcurrencyConfig instance populated from the file or defaults.
        """
        try:
            config_path = Path(path)
            if not config_path.exists():
                logger.warning(
                    "Concurrency config file not found at %s, using defaults", path
                )
                return cls()

            with open(config_path, "r") as f:
                raw = yaml.safe_load(f)

            if not raw or not isinstance(raw, dict):
                logger.warning(
                    "Concurrency config file %s is empty or invalid, using defaults",
                    path,
                )
                return cls()

            # Extract the concurrency section
            concurrency = raw.get("concurrency", raw)

            # Parse nested circuit_breaker section
            circuit_breaker = concurrency.get("circuit_breaker", {})
            if not isinstance(circuit_breaker, dict):
                circuit_breaker = {}

            # Parse nested blast_radius section
            blast_radius = concurrency.get("blast_radius", {})
            if not isinstance(blast_radius, dict):
                blast_radius = {}

            return cls(
                host_lock_timeout=float(
                    concurrency.get("host_lock_timeout", cls.host_lock_timeout)
                ),
                suppression_window=float(
                    concurrency.get("suppression_window", cls.suppression_window)
                ),
                conflict_matrix_path=str(
                    concurrency.get("conflict_matrix_path", cls.conflict_matrix_path)
                ),
                priority_queue_max_depth=int(
                    concurrency.get(
                        "priority_queue_max_depth", cls.priority_queue_max_depth
                    )
                ),
                circuit_breaker_threshold=int(
                    circuit_breaker.get(
                        "failure_threshold", cls.circuit_breaker_threshold
                    )
                ),
                circuit_breaker_recovery=float(
                    circuit_breaker.get(
                        "recovery_period", cls.circuit_breaker_recovery
                    )
                ),
                max_concurrent_hosts=int(
                    blast_radius.get(
                        "max_concurrent_hosts", cls.max_concurrent_hosts
                    )
                ),
                blast_radius_overflow=int(
                    blast_radius.get(
                        "overflow_threshold", cls.blast_radius_overflow
                    )
                ),
            )

        except (yaml.YAMLError, TypeError, ValueError) as e:
            logger.warning(
                "Error parsing concurrency config from %s: %s. Using defaults.",
                path,
                e,
            )
            return cls()
