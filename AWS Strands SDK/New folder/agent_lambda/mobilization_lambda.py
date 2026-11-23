"""Mobilization Agent Lambda — proxy to AgentCore runtime.

This Lambda is the entry point for:
  - EventBridge check-in sweep (every 5 min)
  - Direct invocations from other services

It forwards requests to the AgentCore runtime where the Strands agent runs.
The AgentCore runtime is deployed separately by another team member via deploy.py.

Until the runtime is deployed, this Lambda returns a placeholder response.
"""

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("fpl.mobilization-agent")
logger.setLevel(logging.INFO)

AGENT_ARN = os.environ.get("AGENTCORE_AGENT_ARN", "")
AGENT_REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")

_agentcore = None


def _get_agentcore():
    global _agentcore
    if _agentcore is None:
        _agentcore = boto3.client("bedrock-agentcore-runtime", region_name=AGENT_REGION)
    return _agentcore


def invoke_agent(prompt: str, session_id: str = "default", actor_id: str = "system") -> dict[str, Any]:
    """Invoke the AgentCore runtime with a prompt."""
    if not AGENT_ARN:
        return {"status": "NOT_DEPLOYED", "message": "AgentCore runtime not yet deployed. Set AGENTCORE_AGENT_ARN env var."}

    try:
        response = _get_agentcore().invoke_agent(
            agentId=AGENT_ARN.split("/")[-1],
            sessionId=session_id,
            inputText=prompt,
        )
        result = ""
        for event in response.get("completion", []):
            if "chunk" in event:
                result += event["chunk"].get("bytes", b"").decode("utf-8")
        return {"status": "OK", "response": result, "session_id": session_id}
    except ClientError as e:
        logger.error("AgentCore invocation failed: %s", e)
        return {"status": "ERROR", "error": str(e)}


def handle_checkin_sweep(event: dict) -> dict[str, Any]:
    """Handle EventBridge check-in sweep — query teams in MONITORING state and trigger check-ins."""
    logger.info("Check-in sweep triggered")
    table_name = os.environ.get("DYNAMODB_WORKFLOW_TABLE", "")
    if not table_name:
        return {"status": "ERROR", "error": "DYNAMODB_WORKFLOW_TABLE not set"}

    ddb = boto3.resource("dynamodb", region_name=AGENT_REGION)
    table = ddb.Table(table_name)

    try:
        resp = table.scan(
            FilterExpression="current_state = :s",
            ExpressionAttributeValues={":s": "MONITORING"},
            Limit=100,
        )
        teams = resp.get("Items", [])
        logger.info("Found %d teams in MONITORING state", len(teams))

        results = []
        for team in teams:
            team_id = team.get("team_id", "")
            work_order_id = team.get("work_order_id", "")
            prompt = f"Check in on team {team_id} (work order {work_order_id}). They are in MONITORING state. Verify their travel status and ETA."
            result = invoke_agent(prompt, session_id=f"checkin-{team_id}")
            results.append({"team_id": team_id, "result": result.get("status")})

        return {"status": "OK", "teams_checked": len(results), "results": results}
    except Exception as e:
        logger.error("Check-in sweep failed: %s", e)
        return {"status": "ERROR", "error": str(e)}


def handle_direct_invoke(event: dict) -> dict[str, Any]:
    """Handle direct invocation with a prompt."""
    prompt = event.get("prompt", "")
    session_id = event.get("session_id", "default")
    actor_id = event.get("actor_id", "system")

    if not prompt:
        return {"status": "ERROR", "error": "prompt is required"}

    return invoke_agent(prompt, session_id, actor_id)


def lambda_handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Route based on event source."""
    logger.info("Event received: %s", json.dumps(event, default=str)[:500])

    action = event.get("action", "")

    if action == "checkin_sweep":
        return handle_checkin_sweep(event)
    elif "prompt" in event:
        return handle_direct_invoke(event)
    else:
        return {
            "status": "OK",
            "message": "Mobilization Agent Lambda ready",
            "agent_arn": AGENT_ARN or "NOT_DEPLOYED",
            "supported_actions": ["checkin_sweep", "direct invoke (pass 'prompt' key)"],
        }
