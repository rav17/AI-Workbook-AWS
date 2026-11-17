"""preToolUse hook: block agent gate/rule decisions and lifecycle-file tampering.

Emits a response readable by both the Copilot harness (top-level
``permissionDecision``) and the VS Code Local harness (nested
``hookSpecificOutput``); each harness ignores the other's fields.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

_DECISION_CMD = re.compile(
    r"speckit_flow\b.*?\b(gate\s+(approve|reject)|rules\s+(approve|discard)|questions\s+answer|verify\s+approve|calls\s+reset|host-consent|host-evidence|host-capability|assurance\s+accept)\b",
    re.IGNORECASE | re.DOTALL,
)
_PROTECTED = re.compile(
    r"(audit\.jsonl|\.specify[\\/]+(rules[\\/]+(rules|org|team|phase[\\/]+[\w-]+)|sensors[\\/]+sensors)\.json"
    r"|\.specify[\\/]+custom[\\/]"
    r"|\.specify[\\/]+stages[\\/]"
    r"|\.specify[\\/]+plugins[\\/]"
    r"|\.specify[\\/]+verify\.json"
    r"|specs[\\/]+[^\s\"']*?(state\.(json|md)|selective-route\.json|\.calls\.lock|(reviews|sensors)[\\/]+[\w.-]+\.json))",
    re.IGNORECASE,
)
_WRITE_TOOL = re.compile(r"(edit|write|create|replace|patch|delete)", re.IGNORECASE)
_SHELL_WRITE = re.compile(
    r"(>>?|\bSet-Content\b|\bAdd-Content\b|\bOut-File\b|\bRemove-Item\b|\brm\b|\bdel\b"
    r"|\bmv\b|\bMove-Item\b|\bcp\b|\bCopy-Item\b|\btee\b|\bsed\s+-i\b|\bwrite_text\b|\bopen\()",
    re.IGNORECASE,
)
_HOST_LOG = re.compile(
    r"\.copilot[\\/]+session-state[\\/]+[^\"'\s]+[\\/]+events\.jsonl",
    re.IGNORECASE,
)
_SOURCE_READ_TOOL = re.compile(r"(read|view|shell|bash|exec|grep|(?:^|\.)rg$)", re.IGNORECASE)


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
        return "Only a human may make workflow decisions or reset call budgets; run it yourself."
    targets = (
        _flatten([args.get(key, "") for key in ("path", "filePath", "file_path")])
        if isinstance(args, dict) else ""
    )
    if _HOST_LOG.search(text) and (
        (_SOURCE_READ_TOOL.search(name) and not _WRITE_TOOL.search(name))
        or _HOST_LOG.search(targets)
    ):
        return (
            "Do not read raw Copilot session logs through agent tools. A human must approve "
            "the exact source first; use the audit-bound speckit_flow host adapter."
        )
    if _PROTECTED.search(text):
        if _WRITE_TOOL.search(name) or _SHELL_WRITE.search(text):
            return (
                "Lifecycle audit, state, rules and review files are written only by speckit_flow."
            )
    return None


def respond(reason: str | None) -> dict[str, Any]:
    """Build the hook response in both Copilot and Local harness formats.

    An allow is an empty object so both harnesses fall through to their
    default permission flow instead of pre-approving the tool call.
    """
    if not reason:
        return {}
    decision = {"permissionDecision": "deny", "permissionDecisionReason": reason}
    return {**decision, "hookSpecificOutput": {"hookEventName": "PreToolUse", **decision}}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = None
    print(json.dumps(respond(evaluate(payload))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
