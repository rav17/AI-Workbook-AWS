"""Graceful Degradation Manager — adjusts behavior based on dependency health.

When a dependency fails (DynamoDB down, Bedrock unavailable, SES throttled),
the system automatically enters the appropriate degraded mode rather than
producing incomplete results or crashing.

Operating Modes:
- FULL: All dependencies healthy, normal pipeline
- DEGRADED_NO_AI: Bedrock unavailable → rules_only mode
- DEGRADED_NO_ENRICHMENT: Asset inventory/EC2 unavailable → use labels directly
- DEGRADED_NO_NOTIFICATIONS: SES/Slack down → buffer notifications
- DEGRADED_NO_EXECUTION: SSM/Ansible unavailable → queue actions for later

The /health endpoint reports which mode is active.
Auto-recovers to FULL when dependencies heal.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Health probe interval (seconds)
PROBE_INTERVAL_SECONDS = 30
# Consecutive healthy probes before restoring a dependency
RECOVERY_THRESHOLD = 2


class OperatingMode(Enum):
    """System operating modes based on dependency health."""

    FULL = "full"
    DEGRADED_NO_AI = "degraded_no_ai"
    DEGRADED_NO_ENRICHMENT = "degraded_no_enrichment"
    DEGRADED_NO_NOTIFICATIONS = "degraded_no_notifications"
    DEGRADED_NO_EXECUTION = "degraded_no_execution"
    STORM_MODE = "storm_mode"
    FLEET_BREAKER_OPEN = "fleet_breaker_open"
    DRAINING = "draining"


class DependencyStatus(Enum):
    """Health status of a single dependency."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DependencyHealth:
    """Tracks the health state of a single dependency."""

    name: str
    status: DependencyStatus = DependencyStatus.UNKNOWN
    last_check_at: float = 0.0
    last_healthy_at: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    error_message: str = ""


@dataclass
class DegradationState:
    """Complete system degradation state."""

    mode: OperatingMode = OperatingMode.FULL
    dependencies: dict[str, DependencyHealth] = field(default_factory=dict)
    mode_entered_at: float = 0.0
    transitions: list[dict] = field(default_factory=list)


class DegradationManager:
    """Manages system operating mode based on dependency health.

    Probes dependencies periodically and adjusts the operating mode.
    Components check the current mode to adjust their behavior:
    - AI agent checks if mode allows AI invocations
    - Enricher checks if mode allows enrichment lookups
    - Notification dispatcher checks if notifications are available
    - Executor checks if execution is allowed

    Thread-safe: all state access protected by a lock.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._state = DegradationState(
            mode=OperatingMode.FULL,
            mode_entered_at=time.time(),
        )

        # Health probe callbacks: name → callable that returns True if healthy
        self._probes: dict[str, Callable[[], bool]] = {}

        # Initialize known dependencies
        self._known_dependencies = [
            "bedrock",
            "dynamodb",
            "ssm",
            "ses",
            "enrichment",
        ]
        for dep in self._known_dependencies:
            self._state.dependencies[dep] = DependencyHealth(
                name=dep,
                status=DependencyStatus.UNKNOWN,
            )

    @property
    def current_mode(self) -> OperatingMode:
        """Current operating mode."""
        with self._lock:
            return self._state.mode

    @property
    def is_ai_available(self) -> bool:
        """Whether AI reasoning is available in current mode."""
        return self.current_mode not in (
            OperatingMode.DEGRADED_NO_AI,
            OperatingMode.DRAINING,
        )

    @property
    def is_enrichment_available(self) -> bool:
        """Whether enrichment lookups are available."""
        return self.current_mode != OperatingMode.DEGRADED_NO_ENRICHMENT

    @property
    def is_notification_available(self) -> bool:
        """Whether notification channels are available."""
        return self.current_mode != OperatingMode.DEGRADED_NO_NOTIFICATIONS

    @property
    def is_execution_available(self) -> bool:
        """Whether execution (SSM/Ansible) is available."""
        return self.current_mode not in (
            OperatingMode.DEGRADED_NO_EXECUTION,
            OperatingMode.DRAINING,
        )

    def register_probe(self, dependency_name: str, probe_fn: Callable[[], bool]) -> None:
        """Register a health probe function for a dependency.

        Args:
            dependency_name: Name of the dependency (bedrock, dynamodb, etc.)
            probe_fn: Callable that returns True if healthy, False otherwise.
                      Must complete within 5 seconds.
        """
        self._probes[dependency_name] = probe_fn

    def record_dependency_success(self, dependency_name: str) -> None:
        """Record a successful interaction with a dependency.

        Called by components after successful API calls (e.g., Bedrock invocation
        succeeded). This provides real-time health signal without waiting for probes.
        """
        with self._lock:
            dep = self._state.dependencies.get(dependency_name)
            if dep is None:
                dep = DependencyHealth(name=dependency_name)
                self._state.dependencies[dependency_name] = dep

            dep.status = DependencyStatus.HEALTHY
            dep.last_healthy_at = time.time()
            dep.last_check_at = time.time()
            dep.consecutive_failures = 0
            dep.consecutive_successes += 1
            dep.error_message = ""

            # Check if we can recover
            if dep.consecutive_successes >= RECOVERY_THRESHOLD:
                self._recalculate_mode()

    def record_dependency_failure(self, dependency_name: str, error: str = "") -> None:
        """Record a failed interaction with a dependency.

        Called by components after API failures (e.g., Bedrock timeout).
        Immediately transitions to degraded mode if appropriate.
        """
        with self._lock:
            dep = self._state.dependencies.get(dependency_name)
            if dep is None:
                dep = DependencyHealth(name=dependency_name)
                self._state.dependencies[dependency_name] = dep

            dep.status = DependencyStatus.UNHEALTHY
            dep.last_check_at = time.time()
            dep.consecutive_failures += 1
            dep.consecutive_successes = 0
            dep.error_message = error

            # Transition to degraded mode
            self._recalculate_mode()

    def run_probes(self) -> dict[str, str]:
        """Run all registered health probes and update state.

        Returns dict of dependency → status string for /health endpoint.
        """
        results = {}

        for name, probe_fn in self._probes.items():
            try:
                healthy = probe_fn()
                if healthy:
                    self.record_dependency_success(name)
                    results[name] = "healthy"
                else:
                    self.record_dependency_failure(name, "probe returned False")
                    results[name] = "unhealthy"
            except Exception as e:
                self.record_dependency_failure(name, str(e))
                results[name] = f"unhealthy: {e}"

        return results

    def get_status(self) -> dict:
        """Get full degradation status for the /health endpoint."""
        with self._lock:
            return {
                "mode": self._state.mode.value,
                "mode_entered_at": self._state.mode_entered_at,
                "dependencies": {
                    name: {
                        "status": dep.status.value,
                        "consecutive_failures": dep.consecutive_failures,
                        "error": dep.error_message,
                    }
                    for name, dep in self._state.dependencies.items()
                },
                "recent_transitions": self._state.transitions[-5:],
            }

    def force_mode(self, mode: OperatingMode) -> str:
        """Manually force an operating mode (for operators). Returns previous mode."""
        with self._lock:
            previous = self._state.mode
            self._transition_to(mode)
            return previous.value

    def _recalculate_mode(self) -> None:
        """Recalculate the operating mode based on current dependency health.

        Priority order (highest impact first):
        1. Execution unavailable → DEGRADED_NO_EXECUTION
        2. AI unavailable → DEGRADED_NO_AI
        3. Enrichment unavailable → DEGRADED_NO_ENRICHMENT
        4. Notifications unavailable → DEGRADED_NO_NOTIFICATIONS
        5. All healthy → FULL

        Must be called while holding self._lock.
        """
        new_mode = OperatingMode.FULL

        # Check SSM/execution health
        ssm_dep = self._state.dependencies.get("ssm")
        if ssm_dep and ssm_dep.status == DependencyStatus.UNHEALTHY:
            new_mode = OperatingMode.DEGRADED_NO_EXECUTION

        # Check Bedrock/AI health
        elif self._state.dependencies.get("bedrock", DependencyHealth(name="bedrock")).status == DependencyStatus.UNHEALTHY:
            new_mode = OperatingMode.DEGRADED_NO_AI

        # Check enrichment health
        elif self._state.dependencies.get("enrichment", DependencyHealth(name="enrichment")).status == DependencyStatus.UNHEALTHY:
            new_mode = OperatingMode.DEGRADED_NO_ENRICHMENT

        # Check notification health
        elif self._state.dependencies.get("ses", DependencyHealth(name="ses")).status == DependencyStatus.UNHEALTHY:
            new_mode = OperatingMode.DEGRADED_NO_NOTIFICATIONS

        if new_mode != self._state.mode:
            self._transition_to(new_mode)

    def _transition_to(self, new_mode: OperatingMode) -> None:
        """Transition to a new operating mode. Must hold self._lock."""
        previous = self._state.mode
        self._state.mode = new_mode
        self._state.mode_entered_at = time.time()

        transition = {
            "from": previous.value,
            "to": new_mode.value,
            "at": time.time(),
        }
        self._state.transitions.append(transition)

        # Keep only last 20 transitions
        if len(self._state.transitions) > 20:
            self._state.transitions = self._state.transitions[-20:]

        if new_mode == OperatingMode.FULL:
            logger.info(
                "Operating mode RECOVERED: %s → FULL",
                previous.value,
            )
        else:
            logger.warning(
                "Operating mode DEGRADED: %s → %s",
                previous.value,
                new_mode.value,
            )
