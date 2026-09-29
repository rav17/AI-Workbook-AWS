"""Approval Gate — requires human approval for high/critical risk actions.

Skips approval for low/medium risk. Sends approval requests for
high/critical risk with configurable timeout and delivery retry.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
"""

import asyncio
import logging
from typing import Callable, Coroutine, Optional

from src.guardrails.models import (
    CheckResult,
    CheckResultType,
    RemediationAction,
    RiskLevel,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 300
MIN_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 1800
MAX_DELIVERY_RETRIES = 2
INITIAL_BACKOFF_SECONDS = 2.0


class ApprovalGate:
    """Requires human approval for high/critical risk remediation actions.

    - Low/medium risk: ALLOW immediately.
    - High/critical risk: Send approval request, wait for response.
    - Timeout expiry or delivery failure: DENY.
    """

    def __init__(
        self,
        notify_func: Optional[Callable[..., Coroutine]] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize ApprovalGate.

        Args:
            notify_func: Async callable to dispatch approval requests.
            timeout_seconds: Timeout for approval response (clamped to valid range).
        """
        self._notify_func = notify_func
        self._timeout_seconds = self._clamp_timeout(timeout_seconds)
        # Pending approvals: incident_id -> asyncio.Event
        self._pending: dict[str, asyncio.Event] = {}
        self._responses: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "approval_gate"

    @staticmethod
    def _clamp_timeout(value: int) -> int:
        """Clamp timeout to valid range."""
        if value < MIN_TIMEOUT_SECONDS or value > MAX_TIMEOUT_SECONDS:
            return DEFAULT_TIMEOUT_SECONDS
        return value

    async def check(self, action: RemediationAction) -> CheckResult:
        """Check if action requires and has approval.

        Low/medium risk: ALLOW immediately.
        High/critical risk: Attempt to send approval request.
        """
        risk = action.risk_level or RiskLevel.HIGH

        # Skip approval for low/medium risk
        if risk in (RiskLevel.LOW, RiskLevel.MEDIUM):
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason=f"Approval not required for {risk.value} risk",
            )

        # High/critical risk — send approval request
        if self._notify_func is None:
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason="No notification handler configured for approvals",
            )

        # Try to deliver approval request with retry
        delivered = await self._deliver_with_retry(action)
        if not delivered:
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason="Failed to deliver approval request after retries",
            )

        # Wait for response with timeout
        event = asyncio.Event()
        self._pending[action.incident_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=self._timeout_seconds)
        except asyncio.TimeoutError:
            self._pending.pop(action.incident_id, None)
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason="Approval request timed out",
                metadata={"timeout_seconds": str(self._timeout_seconds)},
            )

        # Check response
        response = self._responses.pop(action.incident_id, {})
        self._pending.pop(action.incident_id, None)

        if response.get("approved"):
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason=f"Approved by {response.get('responder', 'unknown')}",
            )
        else:
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason=f"Denied by {response.get('responder', 'unknown')}",
                metadata={"responder": response.get("responder", "")},
            )

    async def resolve(
        self, incident_id: str, approved: bool, responder: str = ""
    ) -> None:
        """Resolve a pending approval request.

        Args:
            incident_id: The incident ID being approved/denied.
            approved: Whether the action was approved.
            responder: Identity of the human responder.
        """
        self._responses[incident_id] = {
            "approved": approved,
            "responder": responder,
        }
        event = self._pending.get(incident_id)
        if event:
            event.set()

    async def _deliver_with_retry(self, action: RemediationAction) -> bool:
        """Deliver approval request with exponential backoff retry.

        Returns:
            True if delivery succeeded, False after all retries exhausted.
        """
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(MAX_DELIVERY_RETRIES + 1):
            try:
                await self._notify_func(action)
                return True
            except Exception as e:
                logger.warning(
                    "Approval delivery attempt %d failed: %s",
                    attempt + 1,
                    e,
                )
                if attempt < MAX_DELIVERY_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2

        return False
