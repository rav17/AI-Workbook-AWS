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
        "echo x >> specs/012-a/audit.jsonl",
        "echo {} > .specify/rules/rules.json",
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
        "cat specs/012-a/audit.jsonl",
    ],
)
def test_allowed(cmd: str) -> None:
    assert guard.evaluate(shell(cmd)) is None


def test_edit_protected_file_denied() -> None:
    payload = {"toolName": "edit", "toolArgs": {"path": "specs/012-a/state.json"}}
    assert guard.evaluate(payload)


@pytest.mark.parametrize(
    "path", ["specs/013-a/sensors/tasks.json", ".specify/sensors/sensors.json"]
)
def test_sensor_files_protected(path: str) -> None:
    assert guard.evaluate({"toolName": "edit", "toolArgs": {"path": path}})


def test_unparseable_allows() -> None:
    assert guard.evaluate(None) is None
    assert guard.evaluate("junk") is None
