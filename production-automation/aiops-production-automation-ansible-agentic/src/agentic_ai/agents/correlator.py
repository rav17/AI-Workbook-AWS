"""Alert Correlator — groups related alerts within a configurable time window.

Groups alerts sharing at least one common label (instance, service_name, location).
Enforces max 50 alerts per group.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.agentic_ai.models.domain import CorrelationGroup
from src.models import EnrichedAlert

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 300
MIN_WINDOW_SECONDS = 30
MAX_WINDOW_SECONDS = 900
MAX_ALERTS_PER_GROUP = 50
CORRELATION_LABELS = ("instance", "service_name", "location")


class AlertCorrelator:
    """Groups related alerts within a configurable time window.

    Alerts are correlated if they share at least one common label
    from: instance, service_name, location.
    """

    def __init__(self, window_seconds: Optional[int] = None) -> None:
        """Initialize AlertCorrelator.

        Args:
            window_seconds: Correlation window in seconds (30-900, default 300).
                Also reads CORRELATION_WINDOW_SECONDS env var.
        """
        if window_seconds is not None:
            self._window_seconds = self._validate_window(window_seconds)
        else:
            env_val = os.environ.get("CORRELATION_WINDOW_SECONDS", "")
            self._window_seconds = self._validate_window_str(env_val)

        # Active groups: group_id -> {alerts, common_labels, window_start}
        self._groups: dict[str, dict] = {}
        self._alert_to_group: dict[str, str] = {}  # alert incident_id -> group_id

    @property
    def window_seconds(self) -> int:
        return self._window_seconds

    def submit_alert(self, alert: EnrichedAlert) -> Optional[CorrelationGroup]:
        """Submit an alert for correlation.

        If the alert correlates with an existing group, it's added.
        If the window has elapsed with no new correlations, the group
        is finalized and returned.

        Args:
            alert: The enriched alert to correlate.

        Returns:
            A finalized CorrelationGroup if the window elapsed, or None
            if the alert was added to an existing group.
        """
        now = datetime.now(timezone.utc)

        # Check for expired groups
        finalized = self._check_expired_groups(now)

        # Find matching group
        matching_group_id = self._find_matching_group(alert)

        if matching_group_id:
            group = self._groups[matching_group_id]
            if len(group["alerts"]) < MAX_ALERTS_PER_GROUP:
                group["alerts"].append(alert)
                self._alert_to_group[alert.incident_id] = matching_group_id
                # Update common labels
                group["common_labels"] = self._compute_common_labels(
                    group["alerts"]
                )
            else:
                logger.warning(
                    "Group %s at max capacity (%d), creating new group",
                    matching_group_id,
                    MAX_ALERTS_PER_GROUP,
                )
                self._create_new_group(alert, now)
        else:
            self._create_new_group(alert, now)

        return finalized

    def get_group(self, incident_id: str) -> Optional[CorrelationGroup]:
        """Get the correlation group for an incident."""
        group_id = self._alert_to_group.get(incident_id)
        if not group_id or group_id not in self._groups:
            return None
        return self._build_correlation_group(group_id)

    def _find_matching_group(self, alert: EnrichedAlert) -> Optional[str]:
        """Find an existing group that shares labels with this alert."""
        alert_labels = self._extract_correlation_labels(alert)

        for group_id, group in self._groups.items():
            for existing_alert in group["alerts"]:
                existing_labels = self._extract_correlation_labels(existing_alert)
                # Match if at least one common label value matches
                for key in CORRELATION_LABELS:
                    if (
                        key in alert_labels
                        and key in existing_labels
                        and alert_labels[key] == existing_labels[key]
                        and alert_labels[key]
                    ):
                        return group_id
        return None

    def _create_new_group(self, alert: EnrichedAlert, now: datetime) -> str:
        """Create a new correlation group with the alert."""
        group_id = str(uuid.uuid4())
        self._groups[group_id] = {
            "alerts": [alert],
            "common_labels": self._extract_correlation_labels(alert),
            "window_start": now,
        }
        self._alert_to_group[alert.incident_id] = group_id
        return group_id

    def _check_expired_groups(self, now: datetime) -> Optional[CorrelationGroup]:
        """Check for and finalize expired groups."""
        for group_id, group in list(self._groups.items()):
            elapsed = (now - group["window_start"]).total_seconds()
            if elapsed >= self._window_seconds:
                result = self._build_correlation_group(group_id)
                # Clean up
                for alert in group["alerts"]:
                    self._alert_to_group.pop(alert.incident_id, None)
                del self._groups[group_id]
                return result
        return None

    def _build_correlation_group(self, group_id: str) -> CorrelationGroup:
        """Build a CorrelationGroup from internal state."""
        group = self._groups[group_id]
        return CorrelationGroup(
            group_id=group_id,
            alerts=group["alerts"],
            common_labels=group["common_labels"],
            window_start=group["window_start"],
            window_end=datetime.now(timezone.utc),
        )

    @staticmethod
    def _extract_correlation_labels(alert: EnrichedAlert) -> dict[str, str]:
        """Extract correlation-relevant labels from an alert."""
        result: dict[str, str] = {}
        for key in CORRELATION_LABELS:
            value = alert.labels.get(key, "")
            if value:
                result[key] = value
        # Also check asset info
        if alert.asset:
            if alert.asset.service_name:
                result.setdefault("service_name", alert.asset.service_name)
            if alert.asset.hostname:
                result.setdefault("instance", alert.asset.hostname)
            if alert.asset.location:
                result.setdefault("location", alert.asset.location)
        return result

    @staticmethod
    def _compute_common_labels(alerts: list[EnrichedAlert]) -> dict[str, str]:
        """Compute labels common to all alerts in a group."""
        if not alerts:
            return {}

        common: dict[str, str] = {}
        first_labels = AlertCorrelator._extract_correlation_labels(alerts[0])

        for key, value in first_labels.items():
            if all(
                AlertCorrelator._extract_correlation_labels(a).get(key) == value
                for a in alerts[1:]
            ):
                common[key] = value

        return common

    @staticmethod
    def _validate_window(value: int) -> int:
        """Validate window seconds, fallback to default if invalid."""
        if MIN_WINDOW_SECONDS <= value <= MAX_WINDOW_SECONDS:
            return value
        return DEFAULT_WINDOW_SECONDS

    @staticmethod
    def _validate_window_str(value: str) -> int:
        """Validate window from string (env var), fallback to default."""
        if not value:
            return DEFAULT_WINDOW_SECONDS
        try:
            parsed = int(value)
            return AlertCorrelator._validate_window(parsed)
        except (ValueError, TypeError):
            return DEFAULT_WINDOW_SECONDS
