"""Host Poisoning — stops retry loops on unreachable/decommissioned hosts.

After 3 consecutive "instance_not_reachable" failures (SSM delivery failures,
NOT playbook logic failures), marks the host as POISONED:
- Reject all future actions for this host
- Drain queued actions from priority queue
- Send escalation notification
- Auto-unpoison when periodic health probe succeeds (every 30 min)
"""

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_PROBE_INTERVAL_SECONDS = 1800  # 30 minutes


@dataclass
class PoisonedHost:
    """Record of a poisoned host."""

    host: str
    poisoned_at: float
    consecutive_unreachable: int
    last_incident_id: str
    reason: str


@dataclass
class PoisonCheckResult:
    """Result of checking if a host is poisoned."""

    is_poisoned: bool
    reason: str = ""
    poisoned_since: float = 0.0


class HostPoisonManager:
    """Manages poisoned host state to prevent infinite retry loops.

    Thread-safe. Used by ConcurrencyManager to reject actions targeting
    decommissioned or permanently unreachable hosts.
    """

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        probe_interval_seconds: int = DEFAULT_PROBE_INTERVAL_SECONDS,
    ) -> None:
        self._lock = Lock()
        self._threshold = failure_threshold
        self._probe_interval = probe_interval_seconds
        # Poisoned hosts: host → PoisonedHost
        self._poisoned: dict[str, PoisonedHost] = {}
        # Unreachable counter: host → consecutive failures
        self._unreachable_counts: dict[str, int] = {}

    def check(self, host: str) -> PoisonCheckResult:
        """Check if a host is poisoned (should reject all actions).

        Args:
            host: The target hostname.

        Returns:
            PoisonCheckResult indicating if host is blocked.
        """
        with self._lock:
            record = self._poisoned.get(host)
            if record is None:
                return PoisonCheckResult(is_poisoned=False)

            return PoisonCheckResult(
                is_poisoned=True,
                reason=(
                    f"Host '{host}' is POISONED: {record.reason} "
                    f"(since {time.strftime('%H:%M:%S', time.localtime(record.poisoned_at))})"
                ),
                poisoned_since=record.poisoned_at,
            )

    def record_unreachable(self, host: str, incident_id: str) -> bool:
        """Record an unreachable failure for a host.

        Returns True if the host was just poisoned (threshold breached).
        """
        with self._lock:
            if host in self._poisoned:
                return False  # Already poisoned

            count = self._unreachable_counts.get(host, 0) + 1
            self._unreachable_counts[host] = count

            if count >= self._threshold:
                # Poison this host
                self._poisoned[host] = PoisonedHost(
                    host=host,
                    poisoned_at=time.time(),
                    consecutive_unreachable=count,
                    last_incident_id=incident_id,
                    reason=f"{count} consecutive unreachable failures",
                )
                # Clear the counter
                del self._unreachable_counts[host]

                logger.warning(
                    "HOST POISONED: '%s' after %d consecutive unreachable failures "
                    "(last incident: %s). All future actions will be rejected.",
                    host,
                    count,
                    incident_id,
                )
                return True

            return False

    def record_reachable(self, host: str) -> None:
        """Record a successful communication with a host (reset counter).

        Called after successful SSM command delivery or health probe.
        """
        with self._lock:
            self._unreachable_counts.pop(host, None)

    def unpoison(self, host: str) -> bool:
        """Manually unpoison a host (operator action or auto-probe success).

        Returns True if the host was poisoned and is now unpoisoned.
        """
        with self._lock:
            if host in self._poisoned:
                del self._poisoned[host]
                self._unreachable_counts.pop(host, None)
                logger.info("Host '%s' UNPOISONED (removed from block list)", host)
                return True
            return False

    def get_poisoned_hosts(self) -> list[dict]:
        """Get all currently poisoned hosts for status API."""
        with self._lock:
            return [
                {
                    "host": record.host,
                    "poisoned_at": record.poisoned_at,
                    "reason": record.reason,
                    "last_incident_id": record.last_incident_id,
                    "duration_seconds": time.time() - record.poisoned_at,
                }
                for record in self._poisoned.values()
            ]

    @property
    def poisoned_count(self) -> int:
        """Number of currently poisoned hosts."""
        with self._lock:
            return len(self._poisoned)
