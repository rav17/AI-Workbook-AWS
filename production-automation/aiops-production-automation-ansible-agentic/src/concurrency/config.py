"""Configuration for the Concurrent Execution Safety module."""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _parse_int_env(name: str, default: int, min_val: int, max_val: int) -> int:
    """Parse an integer environment variable with range validation.

    Falls back to default if value is invalid or out of range.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid value for %s: '%s', using default %d", name, raw, default
        )
        return default
    if value < min_val or value > max_val:
        logger.warning(
            "Value %d for %s outside range [%d, %d], using default %d",
            value,
            name,
            min_val,
            max_val,
            default,
        )
        return default
    return value


@dataclass
class ConcurrencyConfig:
    """All configurable parameters for the concurrency module."""

    # Host lock settings
    max_lock_duration_seconds: int = 600
    lock_duration_min: int = 60
    lock_duration_max: int = 3600

    # Suppression window
    suppression_window_seconds: int = 300
    suppression_window_min: int = 30
    suppression_window_max: int = 1800

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_failure_threshold_min: int = 2
    circuit_breaker_failure_threshold_max: int = 10
    circuit_breaker_cooldown_seconds: int = 300
    circuit_breaker_cooldown_min: int = 60
    circuit_breaker_cooldown_max: int = 3600

    # Priority queue
    max_queue_depth_per_host: int = 20
    max_queue_depth_min: int = 5
    max_queue_depth_max: int = 100
    max_queue_wait_seconds: int = 600
    max_queue_wait_min: int = 60
    max_queue_wait_max: int = 3600

    # Dependency graph
    dependency_timeout_seconds: int = 600
    dependency_timeout_min: int = 60
    dependency_timeout_max: int = 3600
    max_dependency_nodes: int = 200
    max_dependency_edges: int = 500

    # Resource conflict
    resource_conflict_queue_timeout_seconds: int = 600

    # DynamoDB table name
    lock_table_name: str = "AiopsExecutionLocks"

    # Preemption settings (severity difference must be >= 2)
    preemption_severity_gap: int = 2
    preemption_cancel_timeout_seconds: int = 10

    # Multi-host max
    max_target_hosts: int = 20

    @classmethod
    def from_environment(cls) -> "ConcurrencyConfig":
        """Load configuration from environment variables with validation."""
        config = cls()

        config.max_lock_duration_seconds = _parse_int_env(
            "CONCURRENCY_MAX_LOCK_DURATION",
            config.max_lock_duration_seconds,
            config.lock_duration_min,
            config.lock_duration_max,
        )

        config.suppression_window_seconds = _parse_int_env(
            "CONCURRENCY_SUPPRESSION_WINDOW",
            config.suppression_window_seconds,
            config.suppression_window_min,
            config.suppression_window_max,
        )

        config.circuit_breaker_failure_threshold = _parse_int_env(
            "CONCURRENCY_CB_FAILURE_THRESHOLD",
            config.circuit_breaker_failure_threshold,
            config.circuit_breaker_failure_threshold_min,
            config.circuit_breaker_failure_threshold_max,
        )

        config.circuit_breaker_cooldown_seconds = _parse_int_env(
            "CONCURRENCY_CB_COOLDOWN",
            config.circuit_breaker_cooldown_seconds,
            config.circuit_breaker_cooldown_min,
            config.circuit_breaker_cooldown_max,
        )

        config.max_queue_depth_per_host = _parse_int_env(
            "CONCURRENCY_MAX_QUEUE_DEPTH",
            config.max_queue_depth_per_host,
            config.max_queue_depth_min,
            config.max_queue_depth_max,
        )

        config.max_queue_wait_seconds = _parse_int_env(
            "CONCURRENCY_MAX_QUEUE_WAIT",
            config.max_queue_wait_seconds,
            config.max_queue_wait_min,
            config.max_queue_wait_max,
        )

        config.lock_table_name = os.environ.get(
            "CONCURRENCY_LOCK_TABLE", config.lock_table_name
        )

        return config
