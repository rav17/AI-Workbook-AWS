from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from aria.agents.aria.statement_explainer.models import AgentActivityEvent

_TOOL_NAMES = {
    "get_transactions",
    "summarise_period",
    "categorise_spend",
    "detect_anomalies",
    "explain_transaction",
}
_EVENT_TYPES = {
    "run.started",
    "agent.handoff",
    "tool.started",
    "tool.completed",
    "tool.failed",
    "answer.completed",
    "run.failed",
}
_ERROR_CODES = {
    "invalid_request",
    "statement_unavailable",
    "bedrock_not_configured",
    "tool_failed",
    "internal_error",
}
_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"(?i)\b(password|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
)
_TRANSACTION_ID = re.compile(r"[A-Za-z0-9/_-]{1,64}\Z")


def sanitize_summary(value: Any, *, max_length: int = 220) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").strip()
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            text = pattern.sub(r"\1[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    if len(text) > max_length:
        return text[: max_length - 1] + "…"
    return text


def normalize_activity_event(event: Mapping[str, Any]) -> AgentActivityEvent:
    payload = dict(event)
    event_type = str(payload.get("event_type", "run.started"))
    if event_type not in _EVENT_TYPES:
        raise ValueError("event_type is not allowed")
    tool_name = payload.get("tool_name")
    if tool_name is not None and str(tool_name) not in _TOOL_NAMES:
        raise ValueError("tool_name is not allowed")
    transaction_ids = [
        str(item)
        for item in payload.get("transaction_ids", [])
        if _TRANSACTION_ID.fullmatch(str(item))
    ][:20]
    error_code = payload.get("error_code")
    return AgentActivityEvent(
        run_id=re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("run_id", "demo-run")))[:64]
        or "demo-run",
        sequence=int(payload.get("sequence", 0)),
        event_type=event_type,
        statement_id=str(payload["statement_id"])[:80] if payload.get("statement_id") else None,
        tool_name=str(tool_name) if tool_name is not None else None,
        summary=sanitize_summary(payload.get("summary", "")),
        transaction_ids=transaction_ids,
        status=payload.get("status"),
        error_code=str(error_code) if error_code in _ERROR_CODES else None,
        message=sanitize_summary(payload.get("message", "")) or None,
    )


def normalize_strands_event(
    event: Mapping[str, Any],
    *,
    run_id: str,
    sequence: int,
) -> AgentActivityEvent | None:
    """Map known Strands lifecycle envelopes; never forward arbitrary event data."""
    event_type = event.get("event_type", event.get("type"))
    tool_name = event.get("tool_name", event.get("name"))
    mapping = {
        "tool_use": "tool.started",
        "tool.started": "tool.started",
        "tool_result": "tool.completed",
        "tool.completed": "tool.completed",
        "tool_error": "tool.failed",
        "tool.failed": "tool.failed",
    }
    normalized_type = mapping.get(str(event_type))
    if normalized_type is None:
        if event_type in {"run.started", "agent.handoff", "answer.completed", "run.failed"}:
            normalized_type = str(event_type)
        else:
            return None
    if normalized_type.startswith("tool.") and str(tool_name) not in _TOOL_NAMES:
        return None

    if normalized_type == "tool.started":
        summary = f"Started {tool_name.replace('_', ' ')}."
    elif normalized_type == "tool.completed":
        summary = f"Completed {tool_name.replace('_', ' ')} using selected statement rows."
    elif normalized_type == "tool.failed":
        summary = f"{tool_name.replace('_', ' ')} failed; unsupported results were omitted."
    elif normalized_type == "agent.handoff":
        summary = "Aria handed the request to the statement specialist."
    elif normalized_type == "answer.completed":
        summary = "A statement-grounded answer is ready."
    elif normalized_type == "run.failed":
        summary = "The statement analysis could not be completed."
    else:
        summary = "Statement analysis started."

    return normalize_activity_event(
        {
            "run_id": run_id,
            "sequence": sequence,
            "event_type": normalized_type,
            "tool_name": tool_name if normalized_type.startswith("tool.") else None,
            "summary": summary,
            "transaction_ids": event.get("transaction_ids", []),
            "status": "failed" if normalized_type.endswith("failed") else "ok",
            "error_code": "tool_failed" if normalized_type.endswith("failed") else None,
            "message": "The statement analysis could not be completed."
            if normalized_type == "run.failed"
            else "",
        }
    )


__all__ = [
    "AgentActivityEvent",
    "normalize_activity_event",
    "normalize_strands_event",
    "sanitize_summary",
]
