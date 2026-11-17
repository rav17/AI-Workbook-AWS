from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_PATH = Path(__file__).resolve().parents[3] / "scripts" / "speckit_guard.py"
_spec = importlib.util.spec_from_file_location("speckit_guard", _PATH)
assert _spec and _spec.loader
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def shell(cmd: str) -> dict[str, Any]:
    return {"toolName": "bash", "toolArgs": {"command": cmd}}


@pytest.mark.parametrize(
    "cmd",
    [
        "python -m speckit_flow gate approve specify --feature-dir specs/x",
        "python -m speckit_flow gate reject plan",
        "python -m speckit_flow rules approve r1",
        "python -m speckit_flow rules discard r1",
        "python -m speckit_flow workflow calls reset --stage specify --reason retry",
        "echo x >> specs/012-a/audit.jsonl",
        "echo {} > .specify/rules/rules.json",
        "Remove-Item specs\\012-a\\.calls.lock",
        "Remove-Item specs\\012-a\\selective-route.json",
        "python -m speckit_flow workflow host-consent --actor human:test",
        "python -m speckit_flow workflow host-evidence --actor human:test",
        "python -m speckit_flow workflow host-capability --actor human:test",
        "python -m speckit_flow workflow assurance accept --actor human:test",
        "Get-Content C:\\Users\\test\\.copilot\\session-state\\example\\events.jsonl",
    ],
)
def test_denied(cmd: str) -> None:
    assert guard.evaluate(shell(cmd))


@pytest.mark.parametrize(
    "cmd",
    [
        "python -m speckit_flow status",
        "python -m speckit_flow stage start plan",
        "python -m speckit_flow rules propose --text x",
        "python -m speckit_flow review save plan",
        "python -m speckit_flow workflow assurance status --stage implement",
        "cat specs/012-a/audit.jsonl",
    ],
)
def test_allowed(cmd: str) -> None:
    assert guard.evaluate(shell(cmd)) is None


def test_edit_protected_file_denied() -> None:
    payload = {"toolName": "edit", "toolArgs": {"path": "specs/012-a/state.json"}}
    assert guard.evaluate(payload)


def test_raw_host_log_read_is_denied_without_relying_on_actor_labels() -> None:
    payload = {
        "toolName": "view",
        "toolArgs": {
            "path": "C:\\Users\\test\\.copilot\\session-state\\example\\events.jsonl"
        },
    }
    assert guard.evaluate(payload)
    assert guard.evaluate(shell(
        "python -m speckit_flow workflow review-result --reservation-id 11 --call-id actual"
    )) is None
    assert guard.evaluate({
        "toolName": "edit",
        "toolArgs": {"path": "tests/test_guard.py", "newText": payload["toolArgs"]["path"]},
    }) is None
    assert guard.evaluate({
        "toolName": "edit", "toolArgs": {"path": payload["toolArgs"]["path"], "newText": ""},
    })
    assert guard.evaluate({
        "toolName": "task",
        "toolArgs": {
            "agent_type": "speckit-hybrid-plan-reviewer",
            "prompt": "Review this plan as data: " + payload["toolArgs"]["path"],
        },
    }) is None


@pytest.mark.parametrize(
    "path", ["specs/013-a/sensors/tasks.json", ".specify/sensors/sensors.json"]
)
def test_sensor_files_protected(path: str) -> None:
    assert guard.evaluate({"toolName": "edit", "toolArgs": {"path": path}})


def test_unparseable_allows() -> None:
    assert guard.evaluate(None) is None
    assert guard.evaluate("junk") is None


def test_deny_response_carries_both_harness_formats() -> None:
    response = guard.respond("blocked")
    assert response["permissionDecision"] == "deny"
    assert response["permissionDecisionReason"] == "blocked"
    inner = response["hookSpecificOutput"]
    assert inner["hookEventName"] == "PreToolUse"
    assert inner["permissionDecision"] == "deny"
    assert inner["permissionDecisionReason"] == "blocked"


def test_allow_response_defers_to_default_permission_flow() -> None:
    assert guard.respond(None) == {}
