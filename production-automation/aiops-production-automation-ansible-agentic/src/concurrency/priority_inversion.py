"""Priority Inversion Prevention — reduces P1 wait time behind low-priority locks.

When a P1/P2 alert arrives for a host currently locked by a P3/P4/P5 remediation,
the high-priority action must wait. This module detects that situation and:
1. Reduces the remaining timeout for the blocking execution (120s boosted timeout)
2. If blocking doesn't complete within boosted timeout → signal termination
3. Re-queues the terminated lower-priority action for later retry

This is the classic "priority inversion" problem — solved here via priority inheritance
(the blocking task gets a shorter deadline when a higher-priority task is waiting).
"""

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

# Boosted timeout when priority inversion detected
BOOSTED_TIMEOUT_SECONDS = 120
# Minimum severity gap to trigger priority boost (e.g., P1 boosts P3+)
MIN_SEVERITY_GAP = 2

# Severity rank (lower = higher priority)
SEVERITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}


@dataclass
class PriorityPressure:
    """Records that a high-priority action is waiting behind a lock."""

    waiting_incident_id: str
    waiting_severity: str
    blocking_incident_id: str
    blocking_severity: str
    host: str
    pressure_applied_at: float
    boosted_deadline: float  # When the blocking action must finish


@dataclass
class InversionCheckResult:
    """Result of checking for priority inversion."""

    inversion_detected: bool
    should_boost: bool = False
    boosted_deadline: float = 0.0
    reason: str = ""
    blocking_incident_id: str = ""


class PriorityInversionManager:
    """Detects and mitigates priority inversion in the lock system.

    Thread-safe. Used by ConcurrencyManager when a lock acquisition
    fails and the waiting action has higher priority than the holder.
    """

    def __init__(self, boosted_timeout: int = BOOSTED_TIMEOUT_SECONDS) -> None:
        self._lock = Lock()
        self._boosted_timeout = boosted_timeout
        # Active pressure records: host → PriorityPressure
        self._pressure: dict[str, PriorityPressure] = {}

    def check_inversion(
        self,
        waiting_severity: str,
        blocking_severity: str,
        waiting_incident_id: str,
        blocking_incident_id: str,
        host: str,
    ) -> InversionCheckResult:
        """Check if a priority inversion exists and apply pressure if so.

        Args:
            waiting_severity: Severity of the waiting (higher-priority) action.
            blocking_severity: Severity of the lock holder.
            waiting_incident_id: Incident waiting for the lock.
            blocking_incident_id: Incident currently holding the lock.
            host: The contested host.

        Returns:
            InversionCheckResult with boost recommendation.
        """
        waiting_rank = SEVERITY_RANK.get(waiting_severity, 5)
        blocking_rank = SEVERITY_RANK.get(blocking_severity, 5)
        gap = blocking_rank - waiting_rank

        if gap < MIN_SEVERITY_GAP:
            return InversionCheckResult(
                inversion_detected=False,
                reason=f"No inversion: gap={gap} (need >= {MIN_SEVERITY_GAP})",
            )

        # Priority inversion detected — apply pressure
        now = time.time()
        deadline = now + self._boosted_timeout

        with self._lock:
            self._pressure[host] = PriorityPressure(
                waiting_incident_id=waiting_incident_id,
                waiting_severity=waiting_severity,
                blocking_incident_id=blocking_incident_id,
                blocking_severity=blocking_severity,
                host=host,
                pressure_applied_at=now,
                boosted_deadline=deadline,
            )

        logger.warning(
            "PRIORITY INVERSION: %s(%s) waiting behind %s(%s) on host '%s'. "
            "Boosted deadline: %ds from now.",
            waiting_incident_id,
            waiting_severity,
            blocking_incident_id,
            blocking_severity,
            host,
            self._boosted_timeout,
        )

        return InversionCheckResult(
            inversion_detected=True,
            should_boost=True,
            boosted_deadline=deadline,
            reason=(
                f"Priority inversion: {waiting_severity} waiting behind "
                f"{blocking_severity} (gap={gap}). Timeout reduced to {self._boosted_timeout}s."
            ),
            blocking_incident_id=blocking_incident_id,
        )

    def check_deadline_exceeded(self, host: str) -> Optional[PriorityPressure]:
        """Check if a boosted deadline has been exceeded for a host.

        Called periodically to determine if a blocking action should be terminated.

        Returns:
            The PriorityPressure record if deadline exceeded, None otherwise.
        """
        with self._lock:
            pressure = self._pressure.get(host)
            if pressure is None:
                return None

            if time.time() > pressure.boosted_deadline:
                return pressure

            return None

    def clear_pressure(self, host: str) -> None:
        """Clear priority pressure for a host (after lock is released or action terminates).

        Called when the blocking action completes or is terminated.
        """
        with self._lock:
            self._pressure.pop(host, None)

    def get_active_inversions(self) -> list[dict]:
        """Get all active priority inversions for status API."""
        with self._lock:
            now = time.time()
            return [
                {
                    "host": p.host,
                    "waiting": f"{p.waiting_incident_id} ({p.waiting_severity})",
                    "blocking": f"{p.blocking_incident_id} ({p.blocking_severity})",
                    "deadline_in_seconds": max(0, p.boosted_deadline - now),
                    "deadline_exceeded": now > p.boosted_deadline,
                }
                for p in self._pressure.values()
            ]

    @property
    def active_count(self) -> int:
        """Number of active priority inversions."""
        with self._lock:
            return len(self._pressure)
