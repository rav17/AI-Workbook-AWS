from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


def make_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body", event)
    if isinstance(body, str):
        parsed = json.loads(body)
    else:
        parsed = body
    if not isinstance(parsed, dict):
        raise ValueError("request body must be a JSON object")
    return parsed


def invoke_agent(
    event: dict[str, Any],
    agent_handler: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    try:
        payload = parse_body(event)
        result = agent_handler(payload, {})
        return make_response(200, result)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return make_response(400, {"error": str(exc)})
    except Exception:
        return make_response(500, {"error": "request could not be processed"})
