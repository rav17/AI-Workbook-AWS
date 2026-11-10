from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import sensors
from speckit_flow import state as flow_state
from speckit_flow.models import FlowError

ACTOR = "human:t"


def _sensor_file(tmp_path: Path, **over: object) -> Path:
    item: dict[str, object] = {
        "id": "needs-risk",
        "kind": "builtin",
        "builtin": "section",
        "options": {"heading": "Risk"},
        "stages": ["plan"],
        "required": True,
    } | over
    path = tmp_path / "sensors" / "sensors.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sensors": [item]}), encoding="utf-8")
    return path


def _feature(tmp_path: Path, plan: str, profile: str = "feature") -> Path:
    fdir = tmp_path / "specs" / "001-x"
    fdir.mkdir(parents=True)
    (fdir / "spec.md").write_text("# Spec\n\nbody\n", encoding="utf-8")
    (fdir / "plan.md").write_text(plan, encoding="utf-8")
    flow_state.init_state(fdir, profile, ACTOR)
    return fdir


def _status(fdir: Path, path: Path) -> dict[str, str]:
    out = sensors.run_stage(fdir, "plan", ACTOR, path)
    return {o["id"]: o["reason"] for o in out}


def test_section_passes_with_body(tmp_path: Path) -> None:
    path = _sensor_file(tmp_path)
    fdir = _feature(tmp_path, "# Plan\n\n## Risk assessment\n\nLow.\n\n## Other\n")
    assert sensors.run_sensor(sensors.load_sensors(path)[0], fdir, "plan")[0] is True


@pytest.mark.parametrize(
    ("plan", "reason"),
    [
        ("# Plan\n\n## Other\n\ntext\n", "no 'Risk' section"),
        ("# Plan\n\n## Risk\n\n## Other\n\ntext\n", "section is empty"),
    ],
)
def test_section_fails(tmp_path: Path, plan: str, reason: str) -> None:
    path = _sensor_file(tmp_path)
    fdir = _feature(tmp_path, plan)
    ok, message = sensors.run_sensor(sensors.load_sensors(path)[0], fdir, "plan")
    assert not ok
    assert reason in message


@pytest.mark.parametrize(
    "over",
    [
        {"options": {}},
        {"options": {"heading": "  "}},
        {"options": {"heading": "X", "artifact": "other.md"}},
        {"profiles": []},
        {"profiles": "feature"},
    ],
)
def test_invalid_sensor_options_rejected(tmp_path: Path, over: dict[str, object]) -> None:
    with pytest.raises(FlowError):
        sensors.load_sensors(_sensor_file(tmp_path, **over))


def test_profile_scope_limits_sensor(tmp_path: Path) -> None:
    path = _sensor_file(tmp_path, profiles=["enterprise"])
    fdir = _feature(tmp_path, "# Plan\n\n## Other\n\ntext\n", profile="feature")
    assert "needs-risk" not in _status(fdir, path)
    assert sensors.gate_problems(fdir, "plan", path)[0] == []


def test_profile_scope_applies_to_listed_profile(tmp_path: Path) -> None:
    path = _sensor_file(tmp_path, profiles=["enterprise"])
    fdir = _feature(tmp_path, "# Plan\n\n## Other\n\ntext\n", profile="enterprise")
    assert "needs-risk" in _status(fdir, path)
    assert sensors.gate_problems(fdir, "plan", path)[0]
