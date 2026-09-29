"""Escalation Manager — handles human escalation workflow.

Dispatches escalation notifications, manages timeout behavior,
and handles human responses (approve/reject/reject-with-alternative).

Requirements: 8.1, 8.2, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Coroutine, Optional

from src.agentic_ai.models.domain import HumanResponse, RemediationPlan
from src.agentic_ai.models.enums import EscalationStatus

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MINUTES = 30
MIN_TIMEOUT_MINUTES = 5
MAX_TIMEOUT_MINUTES = 120
MAX_NOTIFICATION_RETRIES = 3
RETRY_INTERVAL_SECONDS = 10


@dataclass
class EscalationRecord:
    """Tracks an active escalation."""

    incident_id: str
    plan: RemediationPlan
    escalated_at: datetime
    timeout_minutes: int
    status: EscalationStatus = EscalationStatus.PENDING
    response: Optional[HumanResponse] = None


class EscalationManager:
    """Manages human escalation workflow for uncertain AI decisions.

    - Dispatches notifications to Slack/PagerDuty within 30 seconds.
    - Retries notification up to 3 times at 10-second intervals.
    - Records escalation and pauses automated remediation.
    - On timeout: executes if confidence > 0.3, marks unresolved otherwise.
    """

    def __init__(
        self,
        notify_func: Optional[Callable[..., Coroutine]] = None,
        incident_store=None,
        timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
    ) -> None:
        # Clamp timeout
        if timeout_minutes < MIN_TIMEOUT_MINUTES or timeout_minutes > MAX_TIMEOUT_MINUTES:
            self._timeout_minutes = DEFAULT_TIMEOUT_MINUTES
        else:
            self._timeout_minutes = timeout_minutes

        self._notify_func = notify_func
        self._incident_store = incident_store
        self._active_escalations: dict[str, EscalationRecord] = {}

    async def escalate(
        self, incident_id: str, plan: RemediationPlan
    ) -> EscalationRecord:
        """Escalate to human for approval.

        Dispatches notification and records escalation.
        Pauses automated remediation.
        """
        record = EscalationRecord(
            incident_id=incident_id,
            plan=plan,
            escalated_at=datetime.now(timezone.utc),
            timeout_minutes=self._timeout_minutes,
        )
        self._active_escalations[incident_id] = record

        # Dispatch notification with retry
        await self._dispatch_with_retry(record)

        logger.info(
            "Escalation created for incident %s (timeout: %d min)",
            incident_id,
            self._timeout_minutes,
        )
        return record

    async def check_timeout(self, incident_id: str) -> Optional[EscalationStatus]:
        """Check if an escalation has timed out.

        If timed out:
        - confidence > 0.3 → execute (TIMED_OUT_EXECUTED)
        - confidence ≤ 0.3 → mark unresolved (TIMED_OUT_UNRESOLVED)

        Returns:
            New status if timed out, None if still pending.
        """
        record = self._active_escalations.get(incident_id)
        if not record or record.status != EscalationStatus.PENDING:
            return None

        elapsed = (datetime.now(timezone.utc) - record.escalated_at).total_seconds()
        timeout_seconds = record.timeout_minutes * 60

        if elapsed < timeout_seconds:
            return None

        # Timeout reached
        confidence = record.plan.confidence_score
        if confidence > 0.3:
            record.status = EscalationStatus.TIMED_OUT_EXECUTED
            logger.info(
                "Escalation timed out for %s (confidence %.2f > 0.3): executing",
                incident_id,
                confidence,
            )
        else:
            record.status = EscalationStatus.TIMED_OUT_UNRESOLVED
            logger.info(
                "Escalation timed out for %s (confidence %.2f ≤ 0.3): unresolved",
                incident_id,
                confidence,
            )

        return record.status

    async def handle_response(
        self, incident_id: str, response: HumanResponse
    ) -> bool:
        """Handle a human response to an escalation.

        Accepts: approve, reject, reject_with_alternative.
        Records responder identity and timestamp.

        Returns:
            True if response was handled, False if no active escalation.
        """
        record = self._active_escalations.get(incident_id)
        if not record or record.status != EscalationStatus.PENDING:
            return False

        record.response = response

        if response.action == "approve":
            record.status = EscalationStatus.APPROVED
            logger.info(
                "Escalation approved for %s by %s",
                incident_id,
                response.responder_identity,
            )
        elif response.action in ("reject", "reject_with_alternative"):
            record.status = EscalationStatus.REJECTED
            logger.info(
                "Escalation rejected for %s by %s",
                incident_id,
                response.responder_identity,
            )

        # Record in incident store
        if self._incident_store:
            try:
                self._incident_store.record_outcome(
                    incident_id=incident_id,
                    outcome=f"escalation_{response.action}",
                    execution_duration_seconds=0.0,
                )
            except Exception as e:
                logger.warning("Failed to record escalation outcome: %s", e)

        return True

    def get_status(self, incident_id: str) -> Optional[EscalationStatus]:
        """Get the current status of an escalation."""
        record = self._active_escalations.get(incident_id)
        return record.status if record else None

    async def _dispatch_with_retry(self, record: EscalationRecord) -> bool:
        """Dispatch escalation notification with retry."""
        if self._notify_func is None:
            logger.warning("No notification function configured for escalation")
            return False

        for attempt in range(MAX_NOTIFICATION_RETRIES):
            try:
                await self._notify_func(record)
                return True
            except Exception as e:
                logger.warning(
                    "Escalation notification attempt %d failed: %s",
                    attempt + 1,
                    e,
                )
                if attempt < MAX_NOTIFICATION_RETRIES - 1:
                    await asyncio.sleep(RETRY_INTERVAL_SECONDS)

        logger.error(
            "Failed to dispatch escalation for %s after %d retries",
            record.incident_id,
            MAX_NOTIFICATION_RETRIES,
        )
        return False
