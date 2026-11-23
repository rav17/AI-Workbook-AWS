"""Team Page note creation in StormForce per Req 18."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


class TeamPageService:
    """Creates interaction summary notes on Team Pages in StormForce.

    Always creates NEW notes — never appends or overwrites (Req 18 AC2).
    """

    def __init__(self, stormforce_client: Any, audit_logger: Any):
        self._sf = stormforce_client
        self._audit = audit_logger
        self._tz = ZoneInfo("America/New_York")

    def create_note(
        self,
        team_id: str,
        work_order_id: str,
        note_type: str,
        note_content: str,
    ) -> dict[str, Any]:
        """Create a new Team Page note in StormForce."""
        now = datetime.now(self._tz)
        payload = {
            "Team__c": team_id,
            "Work_Order__c": work_order_id,
            "Note_Type__c": note_type,
            "Note_Content__c": note_content,
            "AI_Facilitated__c": True,
            "Created_Timestamp__c": now.isoformat(),
        }

        result = self._sf.create_record("Team_Page_Note__c", payload)

        self._audit.log_event(
            event_type="TEAM_PAGE_NOTE_CREATED",
            team_id=team_id,
            work_order_id=work_order_id,
            details={"note_type": note_type, "note_id": result.get("id", "")},
        )

        return {
            "success": result.get("success", False),
            "note_id": result.get("id", ""),
        }

    def create_interaction_summary(
        self,
        team_id: str,
        work_order_id: str,
        workflow_state: str,
        summary_lines: list[str],
    ) -> dict[str, Any]:
        """Create a formatted interaction summary note."""
        now = datetime.now(self._tz)
        header = f"[AI Agent — {now.strftime('%m/%d/%Y %I:%M %p ET')}]"
        body = "\n".join([header, f"Workflow State: {workflow_state}", ""] + summary_lines)
        return self.create_note(
            team_id=team_id,
            work_order_id=work_order_id,
            note_type="Interaction_Summary",
            note_content=body,
        )
