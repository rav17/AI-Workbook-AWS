"""Alert Inhibitor — suppresses symptom alerts when root cause is active.

When a database goes down, every dependent service fires alerts (timeout,
connection refused, health check failed). This module detects that pattern
and suppresses the downstream symptoms, processing only the root cause.

Also groups alerts arriving within a 30-second window for the same host,
selecting the highest-severity one as the primary representative.

Configuration loaded from config/inhibition_rules.yml.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.environ.get(
    "INHIBITION_CONFIG_PATH", "config/inhibition_rules.yml"
)
DEFAULT_GROUPING_WINDOW_SECONDS = 30

# Severity ordering (lower number = higher severity)
SEVERITY_RANK = {"critical": 1, "P1": 1, "warning": 2, "P2": 2, "P3": 3, "info": 4, "P4": 4, "P5": 5}


@dataclass
class InhibitionRule:
    """A rule that suppresses target alerts when source is active."""

    source_alert: str
    target_alerts: list[str]
    condition: str = ""  # e.g., "same_host", "same_service_dependency"


@dataclass
class InhibitionDecision:
    """Result of evaluating an alert against the inhibitor."""

    should_process: bool
    suppressed: bool = False
    reason: str = ""
    parent_incident_id: str = ""
    group_primary: bool = False


@dataclass
class ActiveIncident:
    """Tracks an active root-cause incident."""

    incident_id: str
    alert_name: str
    host: str
    service_name: str
    started_at: float
    resolved: bool = False


@dataclass
class AlertGroup:
    """A group of alerts arriving within the grouping window."""

    host: str
    alerts: list[dict] = field(default_factory=list)
    window_start: float = 0.0
    primary_selected: bool = False


class AlertInhibitor:
    """Pre-processing stage between Normalize and Enrich.

    Two functions:
    1. Inhibition: suppress alerts whose root-cause alert is already active
    2. Grouping: batch alerts for the same host within a 30s window

    Thread-safe: all state access protected by locks.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._lock = Lock()

        # Inhibition rules from config
        self._rules: list[InhibitionRule] = []

        # Active incidents tracking: alert_name → ActiveIncident
        self._active_incidents: dict[str, ActiveIncident] = {}

        # Grouping state: host → AlertGroup
        self._groups: dict[str, AlertGroup] = {}

        # Grouping window from config
        self._grouping_window_seconds = DEFAULT_GROUPING_WINDOW_SECONDS

        # Load config
        self._load_config()

    @property
    def rule_count(self) -> int:
        """Number of loaded inhibition rules."""
        return len(self._rules)

    def _load_config(self) -> None:
        """Load inhibition rules from YAML config."""
        if not os.path.isfile(self._config_path):
            logger.info("Inhibition config not found at %s, no rules loaded", self._config_path)
            return

        try:
            with open(self._config_path, "r") as f:
                data = yaml.safe_load(f)

            if not data or not isinstance(data, dict):
                return

            # Load rules
            rules_data = data.get("inhibition_rules", [])
            for rule_data in rules_data:
                if isinstance(rule_data, dict):
                    self._rules.append(InhibitionRule(
                        source_alert=rule_data.get("source_alert", ""),
                        target_alerts=rule_data.get("target_alerts", []),
                        condition=rule_data.get("condition", ""),
                    ))

            # Load grouping config
            grouping = data.get("grouping", {})
            if grouping:
                self._grouping_window_seconds = grouping.get(
                    "window_seconds", DEFAULT_GROUPING_WINDOW_SECONDS
                )

            logger.info(
                "Alert inhibitor loaded: %d rules, grouping_window=%ds",
                len(self._rules),
                self._grouping_window_seconds,
            )

        except Exception as e:
            logger.warning("Failed to load inhibition config: %s", e)

    def register_active_incident(
        self,
        incident_id: str,
        alert_name: str,
        host: str,
        service_name: str,
    ) -> None:
        """Register a new active incident (called when alert starts processing).

        This builds the context needed for inhibition checks.
        """
        with self._lock:
            self._active_incidents[alert_name] = ActiveIncident(
                incident_id=incident_id,
                alert_name=alert_name,
                host=host,
                service_name=service_name,
                started_at=time.time(),
            )

    def mark_resolved(self, alert_name: str) -> None:
        """Mark an active incident as resolved (from Alertmanager resolved signal)."""
        with self._lock:
            incident = self._active_incidents.get(alert_name)
            if incident:
                incident.resolved = True

    def evaluate(
        self,
        alert_name: str,
        host: str,
        severity: str,
        status: str,
        incident_id: str = "",
        service_name: str = "",
    ) -> InhibitionDecision:
        """Evaluate whether an alert should be processed or suppressed.

        Checks:
        1. If status is "resolved" → skip processing (auto-cancellation)
        2. If alert matches a target in inhibition rules AND the source is active → suppress
        3. If within grouping window for same host → only process if highest severity

        Args:
            alert_name: The alertname label.
            host: Target host from alert labels.
            severity: Alert severity.
            status: Alert status ("firing" or "resolved").
            incident_id: Unique incident ID.
            service_name: Service name if available.

        Returns:
            InhibitionDecision with processing recommendation.
        """
        # Check 1: Resolved alerts should not trigger new remediations
        if status == "resolved":
            return InhibitionDecision(
                should_process=False,
                suppressed=True,
                reason=f"Alert '{alert_name}' has status=resolved, skipping pipeline",
            )

        with self._lock:
            # Check 2: Inhibition rules
            for rule in self._rules:
                if alert_name in rule.target_alerts:
                    # Check if the source alert is currently active
                    source_incident = self._active_incidents.get(rule.source_alert)
                    if source_incident and not source_incident.resolved:
                        # Additional condition check
                        if self._condition_matches(rule.condition, host, service_name, source_incident):
                            return InhibitionDecision(
                                should_process=False,
                                suppressed=True,
                                reason=(
                                    f"Inhibited: '{alert_name}' suppressed by active "
                                    f"root cause '{rule.source_alert}' "
                                    f"(incident {source_incident.incident_id})"
                                ),
                                parent_incident_id=source_incident.incident_id,
                            )

            # Check 3: Host-based grouping within time window
            now = time.time()
            group = self._groups.get(host)

            if group is not None:
                window_elapsed = now - group.window_start
                if window_elapsed < self._grouping_window_seconds:
                    # Within grouping window — add to group
                    group.alerts.append({
                        "alert_name": alert_name,
                        "severity": severity,
                        "incident_id": incident_id,
                        "added_at": now,
                    })

                    # Check if this is the highest severity in the group
                    if self._is_highest_severity(severity, group):
                        # This becomes the new primary
                        return InhibitionDecision(
                            should_process=True,
                            group_primary=True,
                            reason=f"Group primary for host '{host}' (highest severity)",
                        )
                    else:
                        return InhibitionDecision(
                            should_process=False,
                            suppressed=True,
                            reason=(
                                f"Grouped: '{alert_name}' on host '{host}' — "
                                f"not highest severity in {self._grouping_window_seconds}s window"
                            ),
                        )
                else:
                    # Window expired — start new group
                    self._groups[host] = AlertGroup(
                        host=host,
                        alerts=[{
                            "alert_name": alert_name,
                            "severity": severity,
                            "incident_id": incident_id,
                            "added_at": now,
                        }],
                        window_start=now,
                    )
            else:
                # First alert for this host — start group
                self._groups[host] = AlertGroup(
                    host=host,
                    alerts=[{
                        "alert_name": alert_name,
                        "severity": severity,
                        "incident_id": incident_id,
                        "added_at": now,
                    }],
                    window_start=now,
                )

        # No inhibition or grouping applies — process normally
        return InhibitionDecision(should_process=True)

    def get_suppressed_count(self) -> int:
        """Total alerts currently suppressed across all groups."""
        with self._lock:
            total = 0
            for group in self._groups.values():
                total += max(0, len(group.alerts) - 1)  # All except primary
            return total

    def cleanup_stale(self, max_age_seconds: int = 600) -> int:
        """Remove stale incidents and expired groups. Returns count removed."""
        now = time.time()
        removed = 0
        with self._lock:
            # Clean stale active incidents
            stale_keys = [
                k for k, v in self._active_incidents.items()
                if (now - v.started_at) > max_age_seconds or v.resolved
            ]
            for k in stale_keys:
                del self._active_incidents[k]
                removed += 1

            # Clean expired groups
            stale_hosts = [
                h for h, g in self._groups.items()
                if (now - g.window_start) > self._grouping_window_seconds * 2
            ]
            for h in stale_hosts:
                del self._groups[h]
                removed += 1

        return removed

    def _condition_matches(
        self,
        condition: str,
        alert_host: str,
        alert_service: str,
        source: ActiveIncident,
    ) -> bool:
        """Check if the inhibition condition is satisfied."""
        if not condition:
            return True  # No condition = always matches

        if condition == "same_host":
            return alert_host == source.host

        if condition in ("same_service_dependency", "same_availability_zone"):
            # For service dependency, the source being active is sufficient
            # (the rule itself defines the dependency relationship)
            return True

        # Unknown condition — match conservatively
        return True

    def _is_highest_severity(self, severity: str, group: AlertGroup) -> bool:
        """Check if severity is the highest (lowest rank number) in the group."""
        my_rank = SEVERITY_RANK.get(severity, 5)
        for alert in group.alerts:
            other_rank = SEVERITY_RANK.get(alert["severity"], 5)
            if other_rank < my_rank:
                return False
        return True
