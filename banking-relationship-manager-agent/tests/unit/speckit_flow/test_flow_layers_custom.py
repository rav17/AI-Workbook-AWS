from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import custom, rules, sensors
from speckit_flow.models import FlowError
from speckit_flow.profiles import load_profiles

NOW = "2026-01-01T00:00:00+00:00"


def _write_rules(path: Path, items: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "id": rid,
            "text": text,
            "origin": "manual",
            "status": "active",
            "proposed_at": NOW,
            "decided_by": "human:t",
        }
        for rid, text in items
    ]
    path.write_text(json.dumps({"rules": data}), encoding="utf-8")


def test_effective_rules_merge_layers(tmp_path: Path) -> None:
    _write_rules(tmp_path / "org.json", [("R-001", "Use structured logging")])
    _write_rules(tmp_path / "rules.json", [("R-001", "Keep functions small")])
    result = rules.effective_rules(tmp_path / "rules.json")
    assert [(r["layer"], r["text"]) for r in result["rules"]] == [
        ("org", "Use structured logging"),
        ("project", "Keep functions small"),
    ]


def test_narrower_layer_overrides_opposite_rule(tmp_path: Path) -> None:
    _write_rules(tmp_path / "team.json", [("R-001", "Always use tabs")])
    _write_rules(tmp_path / "rules.json", [("R-001", "Never use tabs")])
    result = rules.effective_rules(tmp_path / "rules.json")
    assert [r["layer"] for r in result["rules"]] == ["project"]
    assert result["overridden"] == [{"layer": "team", "id": "R-001"}]


def test_effective_rules_ignore_pending_and_missing_layers(tmp_path: Path) -> None:
    assert rules.effective_rules(tmp_path / "rules.json")["rules"] == []


def _profile(pid: str, stages: list[str]) -> dict[str, object]:
    return {"id": pid, "name": pid, "description": "d", "stages": stages}


def test_custom_profile_overlay(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3] / ".specify" / "profiles"
    spec = tmp_path / ".specify"
    (spec / "profiles").mkdir(parents=True)
    for src in root.glob("*.json"):
        (spec / "profiles" / src.name).write_text(src.read_text(encoding="utf-8"))
    base = json.loads((root / "bugfix.json").read_text(encoding="utf-8"))
    base["id"] = "team-fix"
    (spec / "custom" / "profiles").mkdir(parents=True)
    (spec / "custom" / "profiles" / "team-fix.json").write_text(json.dumps(base))
    assert "team-fix" in load_profiles(spec / "profiles")
    listed = custom.describe(spec / "profiles", spec / "sensors" / "sensors.json")
    assert listed["items"] == [{"type": "profile", "id": "team-fix", "effect": "add"}]


def test_invalid_custom_profile_is_an_error(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[3] / ".specify" / "profiles"
    spec = tmp_path / ".specify"
    (spec / "profiles").mkdir(parents=True)
    (spec / "profiles" / "bugfix.json").write_text((root / "bugfix.json").read_text())
    (spec / "custom" / "profiles").mkdir(parents=True)
    (spec / "custom" / "profiles" / "bad.json").write_text("{not json")
    with pytest.raises(FlowError):
        load_profiles(spec / "profiles")


def _sensor(sid: str, required: bool, stages: list[str]) -> dict[str, object]:
    return {
        "id": sid,
        "kind": "builtin",
        "builtin": "consistency",
        "stages": stages,
        "required": required,
    }


def test_custom_sensor_adds_but_cannot_weaken(tmp_path: Path) -> None:
    spec = tmp_path / ".specify"
    (spec / "sensors").mkdir(parents=True)
    core = spec / "sensors" / "sensors.json"
    core.write_text(json.dumps({"sensors": [_sensor("core-check", True, ["plan", "tasks"])]}))
    overlay = spec / "custom" / "sensors.json"
    overlay.parent.mkdir()
    overlay.write_text(json.dumps({"sensors": [_sensor("extra", False, ["plan"])]}))
    assert {s.id for s in sensors.load_sensors(core)} == {"core-check", "extra"}
    overlay.write_text(json.dumps({"sensors": [_sensor("core-check", False, ["plan", "tasks"])]}))
    with pytest.raises(FlowError, match="cannot replace"):
        sensors.load_sensors(core)
    overlay.write_text(json.dumps({"sensors": [_sensor("core-check", True, ["plan", "tasks"])]}))
    with pytest.raises(FlowError, match="cannot replace"):
        sensors.load_sensors(core)
