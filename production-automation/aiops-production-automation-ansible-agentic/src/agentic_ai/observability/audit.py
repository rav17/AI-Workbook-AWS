"""Audit trail for the AIOps system.

Emits structured JSON audit events with full reasoning chain context.
Includes incident_id, pipeline_stage, duration, outcome, AI reasoning summary,
model_id, input/output token counts, and reasoning latency.

Implements audit write retry (up to 3 times with exponential backoff)
and publishes failure notification if all retries fail.

Requirements: 7.2, 7.3, 11.1, 11.2, 11.3, 11.6
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

MAX_WRITE_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


@dataclass
class AuditEvent:
    """Structured audit event for the AI reasoning pipeline.

    Contains the full reasoning chain context for compliance and debugging.
    """

    incident_id: str
    pipeline_stage: str
    timestamp: str = ""
    duration_ms: float = 0.0
    outcome: str = ""
    environment: str = ""

    # AI reasoning fields
    model_id: Optional[str] = None
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None
    reasoning_latency_ms: Optional[float] = None
    confidence_score: Optional[float] = None
    reasoning_summary: str = ""

    # Context fields
    alert_name: str = ""
    severity: str = ""
    affected_service: str = ""
    target_resource: str = ""
    selected_action: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""
    escalation_status: str = ""

    # Historical context
    historical_incidents_consulted: int = 0
    historical_success_count: int = 0
    historical_failure_count: int = 0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        """Serialize to a single valid JSON string."""
        data = asdict(self)
        # Remove None values for cleaner output
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


class AuditTrail:
    """Emits and persists structured JSON audit events.

    Implements retry logic for audit writes and publishes failure
    notification if all retries fail.
    """

    def __init__(
        self,
        environment: str = "dev",
        notify_func: Optional[Callable[..., Coroutine]] = None,
        log_group_name: Optional[str] = None,
    ) -> None:
        self._environment = environment
        self._notify_func = notify_func
        self._log_group_name = log_group_name

    async def record(self, event: AuditEvent) -> bool:
        """Record an audit event with retry logic.

        Attempts to write the audit event up to 3 times with
        exponential backoff. Publishes failure notification if
        all retries fail.

        Returns:
            True if the event was written successfully.
        """
        event.environment = self._environment
        json_str = event.to_json()

        backoff = INITIAL_BACKOFF_SECONDS
        for attempt in range(MAX_WRITE_RETRIES):
            try:
                self._write_event(json_str)
                return True
            except Exception as e:
                logger.warning(
                    "Audit write attempt %d failed: %s", attempt + 1, e
                )
                if attempt < MAX_WRITE_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2

        # All retries failed — publish failure notification
        logger.error(
            "Audit write failed after %d retries for incident %s",
            MAX_WRITE_RETRIES,
            event.incident_id,
        )
        if self._notify_func:
            try:
                await self._notify_func(
                    f"Audit write failed for incident {event.incident_id}"
                )
            except Exception:
                pass

        return False

    def _write_event(self, json_str: str) -> None:
        """Write a JSON audit event string.

        Emits to the configured logger. In production, this would
        also write to CloudWatch Logs.
        """
        logger.info(json_str, extra={
            "incident_id": "",
            "pipeline_stage": "audit",
            "duration_ms": None,
            "outcome": "",
        })

    async def record_ai_decision(
        self,
        incident_id: str,
        alert_name: str,
        severity: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        confidence: float,
        selected_action: str,
        reasoning_summary: str,
        outcome: str = "pending",
    ) -> bool:
        """Convenience method to record an AI decision audit event."""
        event = AuditEvent(
            incident_id=incident_id,
            pipeline_stage="ai_reasoning",
            outcome=outcome,
            alert_name=alert_name,
            severity=severity,
            model_id=model_id,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            reasoning_latency_ms=latency_ms,
            confidence_score=confidence,
            selected_action=selected_action,
            reasoning_summary=reasoning_summary[:2048],
        )
        return await self.record(event)
