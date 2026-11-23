"""Normalizer component for transforming raw Alertmanager payloads into normalized alert objects."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.models import (
    AlertmanagerAlert,
    AlertmanagerPayload,
    AlertStatus,
    NormalizedAlert,
    Severity,
)

logger = logging.getLogger(__name__)


class Normalizer:
    """Transforms raw Alertmanager payloads into normalized alert objects.

    The Normalizer extracts individual alerts from grouped Alertmanager payloads,
    maps severity labels to internal severity levels, handles missing fields with
    sensible defaults, and generates unique incident IDs for each alert.
    """

    SEVERITY_MAP: dict[str, Severity] = {
        "critical": Severity.P1,
        "warning": Severity.P2,
        "info": Severity.P3,
    }

    def normalize(self, payload: AlertmanagerPayload) -> list[NormalizedAlert]:
        """Extract individual alerts from a grouped payload and normalize them.

        Produces one NormalizedAlert per individual alert in the payload.
        Each alert gets a unique UUID-based incident ID.

        Args:
            payload: The full Alertmanager webhook payload containing one or more alerts.

        Returns:
            A list of NormalizedAlert objects, one per alert in the payload.
        """
        normalized_alerts: list[NormalizedAlert] = []

        for alert in payload.alerts:
            normalized = self._normalize_alert(alert)
            normalized_alerts.append(normalized)

        return normalized_alerts

    def _normalize_alert(self, alert: AlertmanagerAlert) -> NormalizedAlert:
        """Normalize a single Alertmanager alert into the internal format.

        Args:
            alert: A single alert from the Alertmanager payload.

        Returns:
            A NormalizedAlert with all fields populated (using defaults where needed).
        """
        incident_id = str(uuid.uuid4())
        alert_name = self._extract_alert_name(alert)
        severity = self._map_severity(alert)
        status = self._extract_status(alert)
        starts_at = self._parse_starts_at(alert)
        ends_at = self._parse_ends_at(alert)

        return NormalizedAlert(
            incident_id=incident_id,
            alert_name=alert_name,
            severity=severity,
            status=status,
            labels=alert.labels,
            annotations=alert.annotations,
            starts_at=starts_at,
            ends_at=ends_at,
            raw_fingerprint=alert.fingerprint,
        )

    def _extract_alert_name(self, alert: AlertmanagerAlert) -> str:
        """Extract alert name from labels, defaulting to empty string if missing.

        Args:
            alert: A single Alertmanager alert.

        Returns:
            The alert name string, or empty string if not present.
        """
        alert_name = alert.labels.get("alertname", "")
        if not alert_name:
            logger.warning("Missing alert name in alert labels, using empty string default")
        return alert_name

    def _map_severity(self, alert: AlertmanagerAlert) -> Severity:
        """Map Alertmanager severity label to internal Severity enum.

        Mapping: critical→P1, warning→P2, info→P3.
        Unknown or missing severity values default to P3.

        Args:
            alert: A single Alertmanager alert.

        Returns:
            The mapped Severity enum value.
        """
        raw_severity = alert.labels.get("severity", "")
        severity = self.SEVERITY_MAP.get(raw_severity.lower() if raw_severity else "")

        if severity is None:
            if raw_severity:
                logger.warning(
                    "Unrecognized severity value '%s', defaulting to P3", raw_severity
                )
            else:
                logger.warning("Missing severity in alert labels, defaulting to P3")
            return Severity.P3

        return severity

    def _extract_status(self, alert: AlertmanagerAlert) -> AlertStatus:
        """Extract alert status, defaulting to FIRING if missing or unrecognized.

        Args:
            alert: A single Alertmanager alert.

        Returns:
            The AlertStatus enum value.
        """
        raw_status = alert.status.strip() if alert.status else ""

        if not raw_status:
            logger.warning("Missing status in alert, defaulting to 'firing'")
            return AlertStatus.FIRING

        try:
            return AlertStatus(raw_status.lower())
        except ValueError:
            logger.warning(
                "Unrecognized status value '%s', defaulting to 'firing'", raw_status
            )
            return AlertStatus.FIRING

    def _parse_starts_at(self, alert: AlertmanagerAlert) -> datetime:
        """Parse the starts_at timestamp, defaulting to current time if missing or invalid.

        Args:
            alert: A single Alertmanager alert.

        Returns:
            A datetime object representing when the alert started.
        """
        if not alert.starts_at or not alert.starts_at.strip():
            logger.warning("Missing starts_at timestamp, using current time as default")
            return datetime.now(timezone.utc)

        try:
            return datetime.fromisoformat(alert.starts_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            logger.warning(
                "Invalid starts_at timestamp '%s', using current time as default",
                alert.starts_at,
            )
            return datetime.now(timezone.utc)

    def _parse_ends_at(self, alert: AlertmanagerAlert) -> Optional[datetime]:
        """Parse the ends_at timestamp, returning None if missing or representing zero time.

        The Alertmanager uses '0001-01-01T00:00:00Z' to indicate an alert that hasn't ended.

        Args:
            alert: A single Alertmanager alert.

        Returns:
            A datetime object if the alert has ended, None otherwise.
        """
        if not alert.ends_at or not alert.ends_at.strip():
            return None

        # Alertmanager uses this zero value to indicate "not ended"
        if alert.ends_at.startswith("0001-01-01"):
            return None

        try:
            return datetime.fromisoformat(alert.ends_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
