from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from speckit_flow import rules

NOW = "2026-01-01T00:00:00+00:00"
_GUARD = Path(__file__).resolve().parents[3] / "scripts" / "speckit_guard.py"
_spec = importlib.util.spec_from_file_location("speckit_guard_phase", _GUARD)
assert _spec and _spec.loader
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    item = {
        "id": "R-001",
        "text": text,
        "origin": "manual",
        "status": "active",
        "proposed_at": NOW,
        "decided_by": "human:t",
    }
    path.write_text(json.dumps({"rules": [item]}), encoding="utf-8")


def test_phase_rules_apply_only_to_their_stage(tmp_path: Path) -> None:
    _write(tmp_path / "rules.json", "Keep functions small")
    _write(tmp_path / "phase" / "plan.json", "Record every design decision")
    plan = rules.effective_rules(tmp_path / "rules.json", "plan")
    assert [(r["layer"], r["text"]) for r in plan["rules"]] == [
        ("project", "Keep functions small"),
        ("phase", "Record every design decision"),
    ]
    tasks = rules.effective_rules(tmp_path / "rules.json", "tasks")
    assert [r["layer"] for r in tasks["rules"]] == ["project"]
    assert [r["layer"] for r in rules.effective_rules(tmp_path / "rules.json")["rules"]] == [
        "project"
    ]


def test_phase_layer_overrides_project_rule(tmp_path: Path) -> None:
    _write(tmp_path / "rules.json", "Always write long comments")
    _write(tmp_path / "phase" / "implement.json", "Never write long comments")
    result = rules.effective_rules(tmp_path / "rules.json", "implement")
    assert [r["layer"] for r in result["rules"]] == ["phase"]
    assert result["overridden"] == [{"layer": "project", "id": "R-001"}]


def test_guard_protects_phase_rule_files() -> None:
    cmd = {"toolName": "bash", "toolArgs": {"command": "echo {} > .specify/rules/phase/plan.json"}}
    assert guard.evaluate(cmd)
