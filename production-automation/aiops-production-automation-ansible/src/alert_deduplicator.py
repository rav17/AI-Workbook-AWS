"""Alert deduplication with configurable suppression window.

Suppresses duplicate alerts for the same (hostname, alert_name) pair within
a configurable time window. Higher-severity alerts override active suppression
and reset the window (severity escalation).

Uses time.monotonic() for timing to avoid clock drift issues.
"""

import logging
import time

from src.concurrency_models import SuppressionEntry
from src.models import Severity

logger = logging.getLogger(__name__)

# Severity ordering: P1 is most critical (highest), P3 is least critical (lowest).
# Lower numeric value = higher severity.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.P1: 1,
    Severity.P2: 2,
    Severity.P3: 3,
}


class AlertDeduplicator:
    """Suppresses duplicate alerts within a configurable time window.

    Tracks suppression state independently per unique (hostname, alert_name)
    pair. When an alert is recorded, subsequent alerts for the same pair are
    suppressed until the suppression window expires or a higher-severity alert
    arrives (severity escalation override).
    """

    def __init__(self, suppression_window: float = 300.0) -> None:
        """Initialize the deduplicator.

        Args:
            suppression_window: Duration in seconds during which duplicate
                alerts are suppressed. Defaults to 300 seconds (5 minutes).
        """
        self._suppression_window = suppression_window
        self._entries: dict[tuple[str, str], SuppressionEntry] = {}

    @property
    def suppression_window(self) -> float:
        """The configured suppression window duration in seconds."""
        return self._suppression_window

    def should_suppress(
        self, hostname: str, alert_name: str, severity: Severity
    ) -> bool:
        """Check whether this alert should be suppressed.

        Returns True if a matching (hostname, alert_name) entry exists,
        the suppression window has not expired, and the incoming severity
        is not higher than the recorded severity.

        A higher-severity alert (e.g., P1 arriving when P2 is suppressed)
        passes through and is NOT suppressed.

        Args:
            hostname: Target host for the alert.
            alert_name: Name/type of the alert.
            severity: Severity level of the incoming alert.

        Returns:
            True if the alert should be suppressed (skip execution),
            False if it should be allowed through.
        """
        key = (hostname, alert_name)
        entry = self._entries.get(key)

        if entry is None:
            # No prior record — allow through
            return False

        now = time.monotonic()
        elapsed = now - entry.timestamp

        if elapsed >= self._suppression_window:
            # Suppression window expired — allow through
            return False

        # Window is still active — check severity escalation
        if _is_higher_severity(severity, entry.severity):
            # Higher severity overrides suppression — allow through
            return False

        # Same or lower severity within window — suppress
        return True

    def record_execution(
        self, hostname: str, alert_name: str, severity: Severity
    ) -> None:
        """Record that an alert was allowed through, starting the suppression window.

        This should be called after should_suppress() returns False and the
        alert is about to be executed. It creates or resets the suppression
        entry for the (hostname, alert_name) pair.

        Args:
            hostname: Target host for the alert.
            alert_name: Name/type of the alert.
            severity: Severity level of the alert being executed.
        """
        key = (hostname, alert_name)
        self._entries[key] = SuppressionEntry(
            hostname=hostname,
            alert_name=alert_name,
            severity=severity,
            timestamp=time.monotonic(),
        )

    def cleanup_expired(self) -> None:
        """Remove expired suppression entries.

        Should be called periodically (e.g., every 60 seconds) to prevent
        unbounded memory growth from stale entries.
        """
        now = time.monotonic()
        expired_keys = [
            key
            for key, entry in self._entries.items()
            if (now - entry.timestamp) >= self._suppression_window
        ]
        for key in expired_keys:
            del self._entries[key]

        if expired_keys:
            logger.debug(
                "Cleaned up %d expired suppression entries", len(expired_keys)
            )


def _is_higher_severity(incoming: Severity, existing: Severity) -> bool:
    """Check if incoming severity is strictly higher than existing.

    P1 > P2 > P3 (lower rank number = higher severity).

    Args:
        incoming: The severity of the new alert.
        existing: The severity of the currently suppressed alert.

    Returns:
        True if incoming is strictly more severe than existing.
    """
    return _SEVERITY_RANK[incoming] < _SEVERITY_RANK[existing]
