"""Shared utilities for FPL StormForce Gateway Lambda functions.

Contains: dispatch helper, DynamoDB helpers, and config constants.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any


ENV_NAME = os.environ.get("ENV_NAME", "dev")
WORKFLOW_TABLE = os.environ.get("DYNAMODB_WORKFLOW_TABLE", "fpl-dev-workflow-state")
CONVERSATION_TABLE = os.environ.get("DYNAMODB_CONVERSATION_TABLE", "fpl-dev-conversation-history")
SNS_TOPIC_ARN = os.environ.get("SNS_SMS_TOPIC_ARN", "")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "fpl-dev-agent-events")
STORMFORCE_SECRET_ID = os.environ.get("STORMFORCE_SECRET_ID", "")
TTL_DAYS = 90


def _get_boto3():
    """Lazy import boto3 — allows local testing without AWS deps."""
    import boto3
    return boto3


def dispatch_tool(event: dict[str, Any], tool_map: dict[str, Any]) -> dict[str, Any]:
    """Route a Gateway Lambda invocation to the correct tool function.

    Gateway sends tool arguments directly as the event payload.
    """
    if len(tool_map) == 1:
        handler = next(iter(tool_map.values()))
        try:
            return handler(event)
        except Exception as e:
            return {"success": False, "error": f"{next(iter(tool_map.keys()))} failed: {e}"}

    raw_tool_name = event.pop("tool_name", "")
    if raw_tool_name:
        tool_name = raw_tool_name.split("___")[-1] if "___" in raw_tool_name else raw_tool_name
        handler = tool_map.get(tool_name)
        if handler:
            try:
                return handler(event)
            except Exception as e:
                return {"success": False, "error": f"{tool_name} failed: {e}"}

    for name, handler in tool_map.items():
        try:
            return handler(event)
        except (TypeError, KeyError):
            continue

    return {"success": False, "error": f"Could not match event to any tool. Keys: {list(event.keys())}"}


def ttl_epoch() -> int:
    return int(time.time()) + (TTL_DAYS * 86400)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
