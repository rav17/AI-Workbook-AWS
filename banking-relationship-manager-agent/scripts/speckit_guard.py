"""Copilot preToolUse hook: block agent gate/rule decisions and lifecycle-file tampering."""

from __future__ import annotations

import json
import re
import sys
from typing import Any

_DECISION_CMD = re.compile(
    r"speckit_flow\b.*?\b(gate\s+(approve|reject)|rules\s+(approve|discard)|questions\s+answer)\b",
    re.IGNORECASE | re.DOTALL,
)
_PROTECTED = re.compile(
    r"(audit\.jsonl|\.specify[\\/]+(rules[\\/]+(rules|org|team)|sensors[\\/]+sensors)\.json"
    r"|\.specify[\\/]+custom[\\/]"
    r"|\.specify[\\/]+stages[\\/]"
    r"|specs[\\/]+[^\s\"']*?(state\.(json|md)|(reviews|sensors)[\\/]+[\w.-]+\.json))",
    re.IGNORECASE,
)
_WRITE_TOOL = re.compile(r"(edit|write|create|replace|patch|delete)", re.IGNORECASE)
_SHELL_WRITE = re.compile(
    r"(>>?|\bSet-Content\b|\bAdd-Content\b|\bOut-File\b|\bRemove-Item\b|\brm\b|\bdel\b"
    r"|\bmv\b|\bMove-Item\b|\bcp\b|\bCopy-Item\b|\btee\b|\bsed\s+-i\b|\bwrite_text\b|\bopen\()",
    re.IGNORECASE,
)


def _flatten(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)


def evaluate(payload: Any) -> str | None:
    """Return a denial reason, or None to allow."""
    if not isinstance(payload, dict):
        return None
    name = str(payload.get("toolName") or payload.get("tool_name") or "")
    args = payload.get("toolArgs")
    if args is None:
        args = payload.get("tool_input", payload.get("toolInput", payload.get("arguments", {})))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            pass
    text = _flatten(args)
    if _DECISION_CMD.search(text):
        return "Only a human may approve or reject gates and learned rules; run it yourself."
    if _PROTECTED.search(text):
        if _WRITE_TOOL.search(name) or _SHELL_WRITE.search(text):
            return (
                "Lifecycle audit, state, rules and review files are written only by speckit_flow."
            )
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = None
    reason = evaluate(payload)
    if reason:
        print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": reason}))
    else:
        print(json.dumps({"permissionDecision": "allow"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
