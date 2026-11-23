"""FPL StormForce Data Lambda — query_stormforce_teams, query_stormforce_work_order,
update_stormforce_eta, create_team_page_note, update_sms_consent.
"""

import os
from datetime import datetime, timezone
from typing import Any
from shared import dispatch_tool, now_iso

_dynamodb = None
_secrets = None
_sf_token = None


def _ddb():
    global _dynamodb
    if _dynamodb is None:
        import boto3
        _dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION_NAME", "us-east-1"))
    return _dynamodb


def _get_sf_token():
    global _secrets, _sf_token
    if _sf_token:
        return _sf_token
    import boto3
    _secrets = _secrets or boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION_NAME", "us-east-1"))
    try:
        resp = _secrets.get_secret_value(SecretId=os.environ.get("STORMFORCE_SECRET_ID", "fpl-dev/stormforce-oauth-token"))
        _sf_token = resp["SecretString"]
    except Exception:
        _sf_token = ""
    return _sf_token


def query_stormforce_teams(args: dict[str, Any]) -> dict[str, Any]:
    event_id = args.get("event_id", "")
    if not event_id:
        return {"success": False, "error": "event_id is required"}
    table = _ddb().Table(os.environ.get("DYNAMODB_WORKFLOW_TABLE", ""))
    try:
        resp = table.scan(FilterExpression="attribute_exists(team_id)", Limit=100)
        teams = [{"team_id": i.get("team_id"), "team_lead_name": i.get("team_lead_name", ""),
                  "team_lead_phone": i.get("team_lead_phone", ""), "status": i.get("current_state", ""),
                  "work_order_id": i.get("work_order_id", "")} for i in resp.get("Items", [])]
        return {"result": {"teams": teams, "count": len(teams), "event_id": event_id}}
    except Exception as e:
        return {"success": False, "error": str(e)}


def query_stormforce_work_order(args: dict[str, Any]) -> dict[str, Any]:
    work_order_id = args.get("work_order_id", "")
    if not work_order_id:
        return {"success": False, "error": "work_order_id is required"}
    table = _ddb().Table(os.environ.get("DYNAMODB_WORKFLOW_TABLE", ""))
    try:
        resp = table.scan(FilterExpression="work_order_id = :woid",
                          ExpressionAttributeValues={":woid": work_order_id}, Limit=1)
        items = resp.get("Items", [])
        if not items:
            return {"success": False, "error": f"Work order {work_order_id} not found"}
        wo = items[0]
        return {"result": {"work_order_id": wo.get("work_order_id"), "status": wo.get("current_state", ""),
                           "departure_location": wo.get("departure_location", ""),
                           "processing_site_name": wo.get("processing_site_name", ""),
                           "processing_site_address": wo.get("processing_site_address", "")}}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_stormforce_eta(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args.get("team_id", "")
    if not team_id:
        return {"success": False, "error": "team_id is required"}
    table = _ddb().Table(os.environ.get("DYNAMODB_WORKFLOW_TABLE", ""))
    try:
        table.update_item(
            Key={"team_id": team_id, "work_order_id": args.get("work_order_id", "unknown")},
            UpdateExpression="SET expected_arrival_time = :eta, departure_time = :dep, departure_location = :loc, updated_at = :t",
            ExpressionAttributeValues={
                ":eta": args.get("expected_arrival_time", ""), ":dep": args.get("departure_time", ""),
                ":loc": args.get("departure_location", ""), ":t": now_iso()})
        return {"result": {"success": True, "team_id": team_id}}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_team_page_note(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args.get("team_id", "")
    work_order_id = args.get("work_order_id", "")
    note_type = args.get("note_type", "")
    note_content = args.get("note_content", "")
    if not team_id or not note_content:
        return {"success": False, "error": "team_id and note_content are required"}
    # In production, writes to Salesforce Team_Page_Note__c. For now, log + return success.
    import json
    print(json.dumps({"event": "TEAM_PAGE_NOTE", "team_id": team_id, "work_order_id": work_order_id,
                       "note_type": note_type, "timestamp": now_iso()}))
    return {"result": {"success": True, "note_id": f"note-{team_id}-{now_iso()}", "note_type": note_type}}


def update_sms_consent(args: dict[str, Any]) -> dict[str, Any]:
    team_id = args.get("team_id", "")
    phone_number = args.get("phone_number", "")
    consent_status = args.get("consent_status", "")
    if not team_id or not consent_status:
        return {"success": False, "error": "team_id and consent_status are required"}
    if consent_status not in ("OPTED_IN", "OPTED_OUT"):
        return {"success": False, "error": f"Invalid consent_status: {consent_status}. Use OPTED_IN or OPTED_OUT"}
    table = _ddb().Table(os.environ.get("DYNAMODB_WORKFLOW_TABLE", ""))
    try:
        table.update_item(
            Key={"team_id": team_id, "work_order_id": args.get("work_order_id", "unknown")},
            UpdateExpression="SET sms_consent_status = :s, sms_consent_timestamp = :t, updated_at = :u",
            ExpressionAttributeValues={":s": consent_status, ":t": args.get("timestamp", now_iso()), ":u": now_iso()})
        return {"result": {"success": True, "consent_status": consent_status}}
    except Exception as e:
        return {"success": False, "error": str(e)}


TOOL_MAP = {
    "query_stormforce_teams": query_stormforce_teams,
    "query_stormforce_work_order": query_stormforce_work_order,
    "update_stormforce_eta": update_stormforce_eta,
    "create_team_page_note": create_team_page_note,
    "update_sms_consent": update_sms_consent,
}


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return dispatch_tool(event, TOOL_MAP)
