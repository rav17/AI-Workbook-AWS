"""Resolved Alert Tracker — prevents unnecessary remediations.

Tracks active incidents and honors Alertmanager "resolved" signals:
1. If incident has a PENDING execution in queue → cancel it
2. If incident has an ACTIVE execution running → let it complete
3. If incident was already executed → log "resolved after remediation"
4. Track auto-resolution rate as a metric

This prevents the system from executing remediations for issues that
have already self-healed (e.g., a brief CPU spike that resolved before
the pipeline could act).
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

# Maximum tracked incidents (prevents unbounded memory growth)
MAX_TRACKED_INCIDENTS = 10000
# TTL for tracked incidents (24 hours)
INCIDENT_TTL_SECONDS = 86400


class IncidentState(Enum):
    """Lifecycle states of a tracked incident."""

    PENDING = "pending"  # Received, in pipeline or queue
    EXECUTING = "executing"  # Currently being remediated
    COMPLETED = "completed"  # Remediation finished (success or failure)
    RESOLVED = "resolved"  # Alertmanager sent resolved signal
    CANCELLED = "cancelled"  # Was pending but resolved before execution


@dataclass
class TrackedIncident:
    """A tracked incident with lifecycle state."""

    incident_id: str
    alert_name: str
    host: str
    state: IncidentState
    created_at: float
    resolved_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class ResolutionDecision:
    """Result of checking a resolved signal against the tracker."""

    should_cancel: bool
    reason: str
    incident_state: Optional[IncidentState] = None


class ResolvedAlertTracker:
    """Tracks incident lifecycle and handles resolved signals.

    Thread-safe. Used by the webhook handler to detect when an alert
    resolves before or during remediation.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._incidents: dict[str, TrackedIncident] = {}
        # Metrics
        self._auto_resolved_before_execution: int = 0
        self._resolved_after_execution: int = 0
        self._resolved_during_execution: int = 0

    @property
    def auto_resolved_count(self) -> int:
        """Alerts that resolved before any remediation action was taken."""
        return self._auto_resolved_before_execution

    @property
    def tracked_count(self) -> int:
        """Total currently tracked incidents."""
        with self._lock:
            return len(self._incidents)

    def register_pending(
        self, incident_id: str, alert_name: str, host: str
    ) -> None:
        """Register a new incident as PENDING (entered pipeline).

        Called when the webhook accepts an alert into the processing pipeline.
        """
        with self._lock:
            self._evict_stale()
            self._incidents[incident_id] = TrackedIncident(
                incident_id=incident_id,
                alert_name=alert_name,
                host=host,
                state=IncidentState.PENDING,
                created_at=time.time(),
            )

    def mark_executing(self, incident_id: str) -> None:
        """Mark an incident as EXECUTING (remediation started).

        Called just before the executor runs the playbook.
        """
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident and incident.state == IncidentState.PENDING:
                incident.state = IncidentState.EXECUTING

    def mark_completed(self, incident_id: str) -> None:
        """Mark an incident as COMPLETED (remediation finished).

        Called after execution regardless of success/failure.
        """
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident:
                incident.state = IncidentState.COMPLETED
                incident.completed_at = time.time()

    def handle_resolved(self, alert_name: str, host: str) -> ResolutionDecision:
        """Handle an incoming "resolved" signal from Alertmanager.

        Checks if there's a matching pending/executing incident and
        determines appropriate action.

        Args:
            alert_name: The alert that resolved.
            host: The host that resolved.

        Returns:
            ResolutionDecision indicating what to do.
        """
        with self._lock:
            # Find matching incident by alert_name + host
            matching = None
            for incident in self._incidents.values():
                if (
                    incident.alert_name == alert_name
                    and incident.host == host
                    and incident.state in (IncidentState.PENDING, IncidentState.EXECUTING)
                ):
                    matching = incident
                    break

            if matching is None:
                # No active incident for this alert — might have already completed
                return ResolutionDecision(
                    should_cancel=False,
                    reason="No active incident found for resolved alert",
                )

            if matching.state == IncidentState.PENDING:
                # Cancel it — hasn't started executing yet
                matching.state = IncidentState.CANCELLED
                matching.resolved_at = time.time()
                self._auto_resolved_before_execution += 1

                logger.info(
                    "Auto-resolved: cancelled pending incident %s "
                    "(%s on %s resolved before execution)",
                    matching.incident_id,
                    alert_name,
                    host,
                )
                return ResolutionDecision(
                    should_cancel=True,
                    reason=(
                        f"Alert '{alert_name}' on '{host}' resolved before "
                        f"execution started — cancelling pending action"
                    ),
                    incident_state=IncidentState.CANCELLED,
                )

            elif matching.state == IncidentState.EXECUTING:
                # Let it complete — don't interrupt mid-execution
                matching.resolved_at = time.time()
                self._resolved_during_execution += 1

                logger.info(
                    "Resolved during execution: incident %s "
                    "(%s on %s) — letting execution complete",
                    matching.incident_id,
                    alert_name,
                    host,
                )
                return ResolutionDecision(
                    should_cancel=False,
                    reason=(
                        f"Alert resolved during active execution — "
                        f"letting remediation complete (fail-safe)"
                    ),
                    incident_state=IncidentState.EXECUTING,
                )

        return ResolutionDecision(
            should_cancel=False,
            reason="Incident in terminal state",
        )

    def is_resolved(self, incident_id: str) -> bool:
        """Check if an incident has been resolved (for approval endpoint).

        If the alert resolved while awaiting approval, the approval
        endpoint should show "already resolved" instead of executing.
        """
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                return False
            return incident.state in (IncidentState.RESOLVED, IncidentState.CANCELLED)

    def get_metrics(self) -> dict:
        """Get resolution metrics for Prometheus/CloudWatch."""
        with self._lock:
            return {
                "auto_resolved_before_execution": self._auto_resolved_before_execution,
                "resolved_during_execution": self._resolved_during_execution,
                "resolved_after_execution": self._resolved_after_execution,
                "tracked_incidents": len(self._incidents),
                "pending": sum(
                    1 for i in self._incidents.values()
                    if i.state == IncidentState.PENDING
                ),
                "executing": sum(
                    1 for i in self._incidents.values()
                    if i.state == IncidentState.EXECUTING
                ),
            }

    def _evict_stale(self) -> None:
        """Remove old incidents to prevent unbounded memory growth.

        Must be called while holding self._lock.
        """
        if len(self._incidents) < MAX_TRACKED_INCIDENTS:
            return

        now = time.time()
        stale_ids = [
            iid for iid, inc in self._incidents.items()
            if (now - inc.created_at) > INCIDENT_TTL_SECONDS
            or inc.state in (IncidentState.COMPLETED, IncidentState.CANCELLED)
        ]

        for iid in stale_ids[:1000]:  # Remove up to 1000 at a time
            del self._incidents[iid]
