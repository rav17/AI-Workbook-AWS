"""Typed escalation management with structured StormForce payloads."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo


class EscalationType(str, Enum):
    NON_RESPONSE = "Non-Response"
    NOT_TEAM_LEAD = "Not Team Lead"
    TEAM_NOT_TOGETHER = "Team Not Traveling Together"
    IMPLAUSIBLE_ETA = "Implausible ETA"
    DELAY_EXCEPTION = "Delay Exception"
    MISSING_INFORMATION = "Missing Information"


class EscalationManager:
    """Creates and manages escalation records in StormForce."""

    def __init__(self, stormforce_client: Any, audit_logger: Any):
        self._sf = stormforce_client
        self._audit = audit_logger
        self._tz = ZoneInfo("America/New_York")

    def create_escalation(
        self,
        team_id: str,
        work_order_id: str,
        escalation_type: EscalationType,
        trigger_reason: str,
        interaction_context: dict[str, Any],
        message_history: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a typed escalation record in StormForce.

        Returns dict with escalation_id, escalation_timestamp, and success flag.
        """
        now = datetime.now(self._tz)
        payload = {
            "Team__c": team_id,
            "Work_Order__c": work_order_id,
            "Escalation_Type__c": escalation_type.value,
            "Escalation_Status__c": "Open",
            "Trigger_Reason__c": trigger_reason,
            "Escalation_Timestamp__c": now.isoformat(),
            "Interaction_Context__c": str(interaction_context),
            "Message_History__c": "\n".join(message_history) if message_history else "",
        }

        result = self._sf.create_record("Escalation__c", payload)

        self._audit.log_event(
            event_type="ESCALATION_CREATED",
            team_id=team_id,
            work_order_id=work_order_id,
            details={
                "escalation_type": escalation_type.value,
                "trigger_reason": trigger_reason,
                "escalation_id": result.get("id", ""),
            },
        )

        return {
            "success": result.get("success", False),
            "escalation_id": result.get("id", ""),
            "escalation_timestamp": now.isoformat(),
        }
