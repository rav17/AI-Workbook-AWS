"""FPL StormForce State Lambda — get_workflow_state, update_workflow_state, schedule_checkin_timer, log_audit_event."""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from shared import dispatch_tool, ttl_epoch, now_iso

_dynamodb = None
_events = None


def _ddb():
    global _dynamodb
    if _dynamodb is None:
        import boto3
        _dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION_NAME", "us-east-1"))
    return _dynamodb


def _events_client():
    global _events
    if _events is None:
        import boto3
        _events = boto3.client("events", region_name=os.environ.get("AWS_REGION_NAME", "us-east-1"))
    return _events


def get_workflow_state(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args.get("team_id", "")
    work_order_id = args.get("work_order_id", "")
    if not team_id or not work_order_id:
        return {"success": False, "error": "team_id and work_order_id required"}
    table = _ddb().Table(os.environ.get("DYNAMODB_WORKFLOW_TABLE", ""))
    try:
        item = table.get_item(Key={"team_id": team_id, "work_order_id": work_order_id}).get("Item")
        if not item:
            return {"success": False, "error": f"No state for {team_id}/{work_order_id}"}
        return {"result": item}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_workflow_state(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args.get("team_id", "")
    work_order_id = args.get("work_order_id", "")
    new_state = args.get("new_state", "")
    if not team_id or not work_order_id or not new_state:
        return {"success": False, "error": "team_id, work_order_id, new_state required"}
    table = _ddb().Table(os.environ.get("DYNAMODB_WORKFLOW_TABLE", ""))
    try:
        table.update_item(
            Key={"team_id": team_id, "work_order_id": work_order_id},
            UpdateExpression="SET current_state = :s, updated_at = :t, ttl_epoch = :ttl",
            ExpressionAttributeValues={":s": new_state, ":t": now_iso(), ":ttl": ttl_epoch()})
        return {"result": {"success": True, "new_state": new_state}}
    except Exception as e:
        return {"success": False, "error": str(e)}


def schedule_checkin_timer(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args.get("team_id", "")
    if not team_id:
        return {"success": False, "error": "team_id required"}
    delay = int(args.get("delay_minutes", 60))
    fire_at = datetime.now(timezone.utc) + timedelta(minutes=delay)
    try:
        _events_client().put_events(Entries=[{
            "Source": "fpl.stormforce.agent", "DetailType": "CheckInTimer",
            "Detail": json.dumps({"team_id": team_id, "work_order_id": args.get("work_order_id", ""),
                                   "scheduled_fire_time": fire_at.isoformat(), "delay_minutes": delay}),
            "EventBusName": os.environ.get("EVENT_BUS_NAME", "default")}])
        return {"result": {"success": True, "team_id": team_id,
                           "scheduled_fire_time": fire_at.isoformat(), "delay_minutes": delay}}
    except Exception as e:
        return {"success": False, "error": str(e)}


def log_audit_event(args: dict[str, Any]) -> dict[str, Any]:
    entry = {"timestamp": now_iso(), "agent": "agentcore-gateway",
             "event_type": args.get("event_type", "UNKNOWN"), "team_id": args.get("team_id", ""),
             "work_order_id": args.get("work_order_id", ""), "details": args.get("details", "")}
    print(json.dumps(entry, default=str))
    return {"result": {"success": True, "event_type": entry["event_type"]}}


TOOL_MAP = {
    "get_workflow_state": get_workflow_state,
    "update_workflow_state": update_workflow_state,
    "schedule_checkin_timer": schedule_checkin_timer,
    "log_audit_event": log_audit_event,
}


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return dispatch_tool(event, TOOL_MAP)
