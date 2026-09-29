"""Notification Dispatcher component for the self-healing infrastructure system.

Dispatches notifications to configured channels (Slack, Email, PagerDuty) with
retry logic and independent channel failure handling.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.models import EnrichedAlert, ExecutionResult

logger = logging.getLogger(__name__)


# --- Notification Content Models ---


@dataclass
class NotificationMessage:
    """Structured notification message content."""

    alert_name: str
    severity: str
    affected_host: str
    timestamp: str
    message_type: str  # "incident", "remediation", "manual_triage"
    action_taken: Optional[str] = None
    outcome: Optional[str] = None
    duration_seconds: Optional[float] = None
    requires_manual_intervention: bool = False


# --- Channel Interface ---


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the channel name."""
        ...

    @abstractmethod
    async def send(self, message: NotificationMessage) -> None:
        """Send a notification message through this channel.

        Raises:
            Exception: If the notification delivery fails.
        """
        ...


# --- Channel Implementations ---


class SlackChannel(NotificationChannel):
    """Sends notifications via Slack webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "slack"

    async def send(self, message: NotificationMessage) -> None:
        """Send notification to Slack webhook."""
        # In production, this would make an HTTP POST to the webhook URL
        logger.info(f"Slack notification sent: {message.alert_name}")


class EmailChannel(NotificationChannel):
    """Sends notifications via email (SMTP)."""

    def __init__(self, smtp_host: str, smtp_port: int, recipients: list[str]):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.recipients = recipients

    @property
    def name(self) -> str:
        return "email"

    async def send(self, message: NotificationMessage) -> None:
        """Send notification via email."""
        # In production, this would send an email via SMTP
        logger.info(f"Email notification sent: {message.alert_name}")


class PagerDutyChannel(NotificationChannel):
    """Sends notifications via PagerDuty integration."""

    def __init__(self, routing_key: str):
        self.routing_key = routing_key

    @property
    def name(self) -> str:
        return "pagerduty"

    async def send(self, message: NotificationMessage) -> None:
        """Send notification to PagerDuty."""
        # In production, this would make an HTTP POST to PagerDuty Events API
        logger.info(f"PagerDuty notification sent: {message.alert_name}")


# --- Notification Dispatcher ---


class NotificationDispatcher:
    """Dispatches notifications to Slack, email, and PagerDuty.

    Handles individual channel failures independently and implements
    retry logic with exponential backoff.
    """

    MAX_RETRIES = 3
    BACKOFF_BASE_SECONDS = 2  # 2s, 4s, 8s

    def __init__(self, channels: list[NotificationChannel]):
        self.channels = channels

    def _build_incident_message(self, alert: EnrichedAlert) -> NotificationMessage:
        """Build a notification message for an incident detection.

        The message SHALL contain alert name, severity, affected host, and timestamp.
        """
        affected_host = ""
        if alert.asset and alert.asset.hostname:
            affected_host = alert.asset.hostname
        elif alert.labels.get("instance"):
            affected_host = alert.labels["instance"]
        elif alert.labels.get("hostname"):
            affected_host = alert.labels["hostname"]
        elif alert.labels.get("job"):
            affected_host = alert.labels["job"]

        return NotificationMessage(
            alert_name=alert.alert_name,
            severity=alert.severity.value,
            affected_host=affected_host,
            timestamp=alert.starts_at.isoformat(),
            message_type="incident",
        )

    def _build_manual_triage_message(self, alert: EnrichedAlert) -> NotificationMessage:
        """Build a notification message for manual triage.

        The message SHALL contain alert name, severity, affected host, timestamp,
        and an indication that manual intervention is required.
        """
        affected_host = ""
        if alert.asset and alert.asset.hostname:
            affected_host = alert.asset.hostname
        elif alert.labels.get("instance"):
            affected_host = alert.labels["instance"]
        elif alert.labels.get("hostname"):
            affected_host = alert.labels["hostname"]
        elif alert.labels.get("job"):
            affected_host = alert.labels["job"]

        return NotificationMessage(
            alert_name=alert.alert_name,
            severity=alert.severity.value,
            affected_host=affected_host,
            timestamp=alert.starts_at.isoformat(),
            message_type="manual_triage",
            requires_manual_intervention=True,
        )

    def _build_remediation_message(
        self, result: ExecutionResult, alert: EnrichedAlert
    ) -> NotificationMessage:
        """Build a notification message for a remediation outcome.

        The message SHALL contain the action taken, outcome, and execution duration.
        """
        affected_host = result.target_host

        return NotificationMessage(
            alert_name=alert.alert_name,
            severity=alert.severity.value,
            affected_host=affected_host,
            timestamp=alert.starts_at.isoformat(),
            message_type="remediation",
            action_taken=result.playbook_path,
            outcome=result.status.value,
            duration_seconds=result.duration_seconds,
        )

    async def _send_with_retry(
        self, channel: NotificationChannel, message: NotificationMessage
    ) -> bool:
        """Send a notification to a single channel with retry logic.

        Retries up to 3 times with exponential backoff (2s, 4s, 8s).

        Returns:
            True if the notification was sent successfully, False otherwise.
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                await channel.send(message)
                return True
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self.BACKOFF_BASE_SECONDS * (2**attempt)
                    logger.warning(
                        f"Notification to {channel.name} failed (attempt {attempt + 1}/"
                        f"{self.MAX_RETRIES}), retrying in {backoff}s: {e}"
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        f"All retry attempts for channel {channel.name} failed: {e}"
                    )
        return False

    async def _dispatch_to_all_channels(
        self, message: NotificationMessage
    ) -> dict[str, bool]:
        """Dispatch a notification to all configured channels independently.

        Individual channel failures do not prevent other channels from receiving
        notifications.

        Returns:
            A dict mapping channel name to success status.
        """
        results = {}
        for channel in self.channels:
            success = await self._send_with_retry(channel, message)
            results[channel.name] = success
            if not success:
                logger.error(
                    f"Notification delivery failed for channel: {channel.name}"
                )
        return results

    async def notify_incident(self, alert: EnrichedAlert) -> dict[str, bool]:
        """Send incident detection notification to all configured channels.

        The notification SHALL contain alert name, severity, affected host,
        and timestamp.

        Args:
            alert: The enriched alert representing the detected incident.

        Returns:
            A dict mapping channel name to success status.
        """
        message = self._build_incident_message(alert)
        return await self._dispatch_to_all_channels(message)

    async def notify_manual_triage(self, alert: EnrichedAlert) -> dict[str, bool]:
        """Send manual triage notification to all configured channels.

        The notification SHALL contain alert name, severity, affected host,
        timestamp, and an indication that manual intervention is required.

        Args:
            alert: The enriched alert requiring manual triage.

        Returns:
            A dict mapping channel name to success status.
        """
        message = self._build_manual_triage_message(alert)
        return await self._dispatch_to_all_channels(message)

    async def notify_remediation(
        self, result: ExecutionResult, alert: EnrichedAlert
    ) -> dict[str, bool]:
        """Send remediation outcome notification to all configured channels.

        The notification SHALL contain the action taken, outcome
        (success/failure/timeout), and execution duration.

        Args:
            result: The execution result of the remediation.
            alert: The enriched alert that was remediated.

        Returns:
            A dict mapping channel name to success status.
        """
        message = self._build_remediation_message(result, alert)
        return await self._dispatch_to_all_channels(message)
