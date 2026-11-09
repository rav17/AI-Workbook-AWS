from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from aria.api.runtime_session import IdempotencyConflict
from aria.observability import Observability


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
    started = time.perf_counter()
    observability = Observability()
    try:
        payload = parse_body(event)
        result = agent_handler(payload, {})
        response = make_response(200, result)
        observability.emit_operation(
            "request.invoke",
            {"status_code": response["statusCode"]},
            correlation_id=event.get("requestContext", {}).get("requestId"),
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        return response
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        observability.emit_operation(
            "request.invoke",
            {"status_code": 400, "error_type": type(exc).__name__},
            correlation_id=event.get("requestContext", {}).get("requestId"),
            latency_ms=(time.perf_counter() - started) * 1000,
            status="error",
        )
        return make_response(400, {"error": str(exc)})
    except IdempotencyConflict:
        observability.emit_operation(
            "request.invoke",
            {"status_code": 409, "error_type": "IdempotencyConflict"},
            correlation_id=event.get("requestContext", {}).get("requestId"),
            latency_ms=(time.perf_counter() - started) * 1000,
            status="error",
        )
        return make_response(409, {"error": "duplicate_request"})
    except Exception:
        observability.emit_operation(
            "request.invoke",
            {"status_code": 500, "error_type": "UnhandledError"},
            correlation_id=event.get("requestContext", {}).get("requestId"),
            latency_ms=(time.perf_counter() - started) * 1000,
            status="error",
        )
        return make_response(500, {"error": "request could not be processed"})


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    from aria.api.rest_handler import handler as runtime_handler

    return runtime_handler(event, context)
