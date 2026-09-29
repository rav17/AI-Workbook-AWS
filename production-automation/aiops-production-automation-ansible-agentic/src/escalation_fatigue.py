"""Escalation Fatigue Prevention — auto-approve trusted patterns.

When the same (alert_name, playbook, host) combination has been approved
by an operator 3+ consecutive times with SUCCESS outcomes in the last 7 days,
the system auto-approves subsequent instances.

Trust is immediately revoked on any FAILURE, INEFFECTIVE, or ABORTED outcome.

This prevents "approval fatigue" where operators rubber-stamp approvals
without reading them (which defeats the human-in-the-loop safety purpose).
"""

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TRUST_THRESHOLD = 3  # Consecutive successes to earn trust
DEFAULT_TRUST_WINDOW_DAYS = 7  # Trust expires after this many days of inactivity
TRUST_WINDOW_SECONDS = DEFAULT_TRUST_WINDOW_DAYS * 86400


@dataclass
class TrustRecord:
    """Tracks approval trust for a specific (alert, playbook, host) pattern."""

    alert_name: str
    playbook_path: str
    host: str
    consecutive_approvals: int = 0
    consecutive_successes: int = 0
    last_approved_at: float = 0.0
    last_success_at: float = 0.0
    trusted: bool = False
    trust_revoked_reason: str = ""


@dataclass
class FatigueDecision:
    """Result of checking fatigue prevention for an action."""

    auto_approve: bool
    reason: str
    approval_count: int = 0


class EscalationFatigueManager:
    """Manages operator trust for repeated approval patterns.

    Thread-safe. Used by the Approval Gate to decide whether to skip
    human approval for well-known, consistently-successful patterns.
    """

    def __init__(
        self,
        trust_threshold: int = DEFAULT_TRUST_THRESHOLD,
        trust_window_seconds: float = TRUST_WINDOW_SECONDS,
        enabled: bool = True,
    ) -> None:
        self._lock = Lock()
        self._threshold = trust_threshold
        self._window = trust_window_seconds
        self._enabled = enabled
        # Records: composite_key → TrustRecord
        self._records: dict[str, TrustRecord] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _make_key(self, alert_name: str, playbook_path: str, host: str) -> str:
        return f"{alert_name}##{playbook_path}##{host}"

    def should_auto_approve(
        self, alert_name: str, playbook_path: str, host: str
    ) -> FatigueDecision:
        """Check if this pattern has earned operator trust.

        Args:
            alert_name: The triggering alert.
            playbook_path: The playbook to execute.
            host: The target host.

        Returns:
            FatigueDecision indicating whether to skip approval.
        """
        if not self._enabled:
            return FatigueDecision(
                auto_approve=False,
                reason="Fatigue prevention disabled",
            )

        key = self._make_key(alert_name, playbook_path, host)

        with self._lock:
            record = self._records.get(key)

            if record is None:
                return FatigueDecision(
                    auto_approve=False,
                    reason="No trust history for this pattern",
                )

            # Check if trust has expired
            now = time.time()
            if record.last_success_at > 0 and (now - record.last_success_at) > self._window:
                record.trusted = False
                return FatigueDecision(
                    auto_approve=False,
                    reason=f"Trust expired (last success > {DEFAULT_TRUST_WINDOW_DAYS} days ago)",
                )

            if record.trusted:
                return FatigueDecision(
                    auto_approve=True,
                    reason=(
                        f"Auto-approved: operator trust earned after "
                        f"{record.consecutive_successes} consecutive successes"
                    ),
                    approval_count=record.consecutive_approvals,
                )

            return FatigueDecision(
                auto_approve=False,
                reason=(
                    f"Trust not yet earned ({record.consecutive_successes}/"
                    f"{self._threshold} consecutive successes needed)"
                ),
                approval_count=record.consecutive_approvals,
            )

    def record_approval(self, alert_name: str, playbook_path: str, host: str) -> None:
        """Record that an operator approved this pattern.

        Called when the operator clicks the approval link.
        """
        key = self._make_key(alert_name, playbook_path, host)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                record = TrustRecord(
                    alert_name=alert_name,
                    playbook_path=playbook_path,
                    host=host,
                )
                self._records[key] = record

            record.consecutive_approvals += 1
            record.last_approved_at = time.time()

    def record_success(self, alert_name: str, playbook_path: str, host: str) -> None:
        """Record a successful execution outcome for this pattern.

        If consecutive successes reach the threshold, trust is established.
        """
        key = self._make_key(alert_name, playbook_path, host)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                record = TrustRecord(
                    alert_name=alert_name,
                    playbook_path=playbook_path,
                    host=host,
                )
                self._records[key] = record

            record.consecutive_successes += 1
            record.last_success_at = time.time()

            # Check if trust threshold reached
            if record.consecutive_successes >= self._threshold and not record.trusted:
                record.trusted = True
                record.trust_revoked_reason = ""
                logger.info(
                    "TRUST ESTABLISHED: %s/%s/%s after %d consecutive successes",
                    alert_name,
                    playbook_path,
                    host,
                    record.consecutive_successes,
                )

    def record_failure(
        self, alert_name: str, playbook_path: str, host: str, reason: str = "failure"
    ) -> None:
        """Record a failed/ineffective/aborted outcome — revokes trust immediately.

        Any failure resets the counter and revokes trust, requiring the operator
        to re-approve manually going forward.
        """
        key = self._make_key(alert_name, playbook_path, host)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return

            was_trusted = record.trusted
            record.consecutive_successes = 0
            record.trusted = False
            record.trust_revoked_reason = reason

            if was_trusted:
                logger.warning(
                    "TRUST REVOKED: %s/%s/%s due to %s",
                    alert_name,
                    playbook_path,
                    host,
                    reason,
                )

    def get_trusted_patterns(self) -> list[dict]:
        """Get all currently trusted patterns for status/reporting."""
        with self._lock:
            return [
                {
                    "alert_name": r.alert_name,
                    "playbook_path": r.playbook_path,
                    "host": r.host,
                    "consecutive_successes": r.consecutive_successes,
                    "last_success_at": r.last_success_at,
                }
                for r in self._records.values()
                if r.trusted
            ]

    @property
    def trusted_count(self) -> int:
        """Number of currently trusted patterns."""
        with self._lock:
            return sum(1 for r in self._records.values() if r.trusted)
