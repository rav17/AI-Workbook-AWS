from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aria.tools.maturity_tool import evaluate_maturity_event, evaluate_outflow_event


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    detail = event.get("detail", event)
    if not isinstance(detail, dict):
        raise ValueError("event detail must be a JSON object")

    event_id = str(event.get("id") or detail.get("event_id") or "")
    if not event_id:
        raise ValueError("event id is required for idempotent processing")

    client_id = str(detail.get("client_id") or "")
    if not client_id:
        raise ValueError("client_id is required")

    return {
        "event_id": event_id,
        "event_type": str(event.get("detail-type") or detail.get("event_type") or "unknown"),
        "client_id": client_id,
        "payload": detail,
    }


def handle_event(
    event: dict[str, Any],
    processor: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    normalized = normalize_event(event)
    result = processor(normalized)
    return {
        "status": "processed",
        "event_id": normalized["event_id"],
        "result": result,
    }


def process_event(event: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_event(event)
    event_type = normalized["event_type"].lower()
    payload = normalized["payload"]
    if "outflow" in event_type:
        result = evaluate_outflow_event(payload)
        category = "outflow"
    elif "maturity" in event_type or "mature" in event_type:
        result = evaluate_maturity_event(payload)
        category = "maturity"
    else:
        result = {"status": "ignored", "recommended_action": "no_action"}
        category = "unknown"

    return {
        "event_id": normalized["event_id"],
        "client_id": normalized["client_id"],
        "event_type": category,
        **result,
    }
