"""FPL StormForce Notification Lambda — send_sms."""

import os
from typing import Any
from shared import dispatch_tool, now_iso

_sms = None


def _sms_client():
    global _sms
    if _sms is None:
        import boto3
        _sms = boto3.client("pinpoint-sms-voice-v2", region_name=os.environ.get("AWS_REGION_NAME", "us-east-1"))
    return _sms


def send_sms(args: dict[str, Any]) -> dict[str, Any]:
    phone_number = (args.get("phone_number") or "").strip()
    message = (args.get("message") or "").strip()
    if not phone_number or not message:
        return {"success": False, "error": "phone_number and message are required"}
    if not phone_number.startswith("+1") or len(phone_number) != 12:
        return {"success": False, "error": f"Invalid US phone number: {phone_number}"}
    include_opt_out = args.get("include_opt_out", True)
    body = message + "\nReply STOP to opt out." if include_opt_out else message
    try:
        resp = _sms_client().send_text_message(
            DestinationPhoneNumber=phone_number, MessageBody=body, MessageType="TRANSACTIONAL")
        return {"result": {"success": True, "message_id": resp.get("MessageId", ""),
                           "delivery_status": "SENT", "timestamp": now_iso()}}
    except Exception as e:
        return {"success": False, "error": f"SMS send failed: {e}"}


TOOL_MAP = {"send_sms": send_sms}


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return dispatch_tool(event, TOOL_MAP)
