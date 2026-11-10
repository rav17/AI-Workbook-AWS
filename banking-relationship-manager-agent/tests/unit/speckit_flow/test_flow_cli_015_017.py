from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from speckit_flow.cli import main

_GUARD = Path(__file__).resolve().parents[3] / "scripts" / "speckit_guard.py"
_spec = importlib.util.spec_from_file_location("speckit_guard_cli", _GUARD)
assert _spec and _spec.loader
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _shell(cmd: str) -> dict[str, Any]:
    return {"toolName": "bash", "toolArgs": {"command": cmd}}


@pytest.mark.parametrize(
    "cmd",
    [
        'python -m speckit_flow questions answer Q1 "ok"',
        "python -m speckit_flow verify approve",
        "echo {} > .specify/verify.json",
        "echo {} > .specify/rules/org.json",
        "echo {} > .specify/rules/team.json",
        "echo {} > .specify/custom/sensors.json",
    ],
)
def test_guard_denies_new_protected_actions(cmd: str) -> None:
    assert guard.evaluate(_shell(cmd))


@pytest.mark.parametrize(
    "cmd",
    [
        'python -m speckit_flow questions add "Who?" --role product',
        "python -m speckit_flow questions list --open",
        "python -m speckit_flow custom list",
    ],
)
def test_guard_allows_agent_question_actions(cmd: str) -> None:
    assert guard.evaluate(_shell(cmd)) is None


def test_questions_cli_flow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = tmp_path / "016-x"
    d.mkdir()
    base = ["--feature-dir", str(d), "--sensors-file", str(tmp_path / "none.json")]
    assert main(["init", "--profile", "express", *base, "--actor", "human:a"]) == 0
    add = ["questions", "add", "Which users?", "--role", "product", *base]
    assert main([*add, "--actor", "agent:product"]) == 0
    assert (
        main(["questions", "add", "x?", "--role", "ghost", *base, "--actor", "agent:product"]) == 1
    )
    assert main(["questions", "check", *base]) == 1
    assert main(["questions", "list", "--open", "--role", "product", *base]) == 0
    assert "Q1" in capsys.readouterr().out
    assert main(["questions", "answer", "Q1", "staff", *base, "--actor", "agent:product"]) == 1
    assert main(["questions", "answer", "Q1", "staff", *base, "--actor", "human:a"]) == 0
    assert main(["questions", "check", *base]) == 0


def test_custom_and_effective_rules_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["custom", "list"]) == 0
    assert main(["custom", "validate"]) == 0
    capsys.readouterr()
    assert main(["rules", "list", "--effective", "--json"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["rules"] == []


def test_doctor_reports_custom_check(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    assert "custom:" in capsys.readouterr().out
