"""Generic Lambda invoker for tool functions. Routes tool calls to AWS Lambda."""
from __future__ import annotations

import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)

# Environment-driven config
_REGION = os.environ.get("AWS_REGION", "us-east-1")
_LAMBDA_PREFIX = os.environ.get("LAMBDA_PREFIX", "smartbanker")
_USE_LAMBDA = os.environ.get("USE_LAMBDA", "false").lower() == "true"

_client: boto3.client | None = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("lambda", region_name=_REGION)
    return _client


def invoke_tool_lambda(tool_name: str, payload: dict) -> dict:
    """Invoke a Lambda function for a tool and return the parsed response.

    The Lambda function name is derived as ``{LAMBDA_PREFIX}-{tool_name}``.
    Falls back to returning the payload unchanged if USE_LAMBDA is false
    (local dev mode).
    """
    if not _USE_LAMBDA:
        raise RuntimeError(
            f"Lambda invocation disabled (USE_LAMBDA=false). "
            f"Tool '{tool_name}' should use local implementation."
        )

    function_name = f"{_LAMBDA_PREFIX}-{tool_name}"
    logger.info("Invoking Lambda %s with payload keys: %s", function_name, list(payload.keys()))

    response = _get_client().invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )

    response_payload = json.loads(response["Payload"].read())

    if response.get("FunctionError"):
        error_msg = response_payload.get("errorMessage", "Unknown Lambda error")
        logger.error("Lambda %s returned error: %s", function_name, error_msg)
        raise RuntimeError(f"Lambda {function_name} error: {error_msg}")

    # Handle API Gateway proxy response format
    if isinstance(response_payload, dict) and "body" in response_payload:
        return json.loads(response_payload["body"])

    return response_payload


def is_lambda_enabled() -> bool:
    """Check if Lambda-backed tools are enabled."""
    return _USE_LAMBDA
