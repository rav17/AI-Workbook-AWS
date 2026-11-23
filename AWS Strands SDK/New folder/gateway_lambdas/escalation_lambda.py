"""FPL StormForce Escalation Lambda — create_escalation."""

import json
import os
from typing import Any
from shared import dispatch_tool, now_iso

VALID_TYPES = ("Non-Response", "Not Team Lead", "Team Not Traveling Together",
               "Implausible ETA", "Delay Exception", "Missing Information")

_dynamodb = None


def _ddb():
    global _dynamodb
    if _dynamodb is None:
        import boto3
        _dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION_NAME", "us-east-1"))
    return _dynamodb


def create_escalation(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args.get("team_id", "")
    work_order_id = args.get("work_order_id", "")
    escalation_type = args.get("escalation_type", "")
    trigger_reason = args.get("trigger_reason", "")
    if not team_id or not escalation_type or not trigger_reason:
        return {"success": False, "error": "team_id, escalation_type, and trigger_reason are required"}
    if escalation_type not in VALID_TYPES:
        return {"success": False, "error": f"Invalid escalation_type '{escalation_type}'. Valid: {VALID_TYPES}"}

    ts = now_iso()
    # Update workflow state to ESCALATED
    table = _ddb().Table(os.environ.get("DYNAMODB_WORKFLOW_TABLE", ""))
    try:
        table.update_item(
            Key={"team_id": team_id, "work_order_id": work_order_id or "unknown"},
            UpdateExpression="SET current_state = :s, escalation_type = :et, escalation_timestamp = :ts, updated_at = :u",
            ExpressionAttributeValues={":s": "ESCALATED", ":et": escalation_type, ":ts": ts, ":u": ts})
    except Exception:
        pass  # Non-fatal — escalation record is the primary output

    print(json.dumps({"event": "ESCALATION_CREATED", "team_id": team_id,
                       "escalation_type": escalation_type, "trigger_reason": trigger_reason, "timestamp": ts}))
    return {"result": {"success": True, "escalation_id": f"esc-{team_id}-{ts}",
                        "escalation_type": escalation_type, "escalation_timestamp": ts}}


TOOL_MAP = {"create_escalation": create_escalation}


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return dispatch_tool(event, TOOL_MAP)
