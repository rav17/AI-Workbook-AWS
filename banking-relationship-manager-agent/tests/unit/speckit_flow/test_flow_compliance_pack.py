from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from speckit_flow import agents, doctor, plugins, sensors
from speckit_flow import state as flow_state
from speckit_flow.models import FlowError
from speckit_flow.profiles import load_profiles

ROOT = Path(__file__).resolve().parents[3]
SPECIFY = ROOT / ".specify"
ACTOR = "human:t"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A copy of the core config plus the shipped pack, so tests never touch the repo."""
    dest = tmp_path / ".specify"
    for name in ("profiles", "sensors", "agents", "stages", "rules"):
        if (SPECIFY / name).is_dir():
            shutil.copytree(SPECIFY / name, dest / name)
    shutil.copytree(SPECIFY / "plugins" / "compliance", dest / "plugins" / "compliance")
    return dest


def _enable(project: Path, enabled: bool) -> None:
    path = project / "plugins" / "compliance" / "plugin.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["enabled"] = enabled
    path.write_text(json.dumps(data), encoding="utf-8")


def test_shipped_pack_is_disabled_and_valid() -> None:
    found = plugins.discover(SPECIFY, enabled_only=False)
    pack = next(p for p in found if p.name == "compliance")
    assert pack.enabled is False


def test_profile_only_when_enabled(project: Path) -> None:
    _enable(project, False)
    assert "compliance" not in load_profiles(project / "profiles")
    _enable(project, True)
    profiles = load_profiles(project / "profiles")
    assert "compliance" in profiles
    assert "feature" in profiles


def test_sensor_blocks_gate_until_section_added(project: Path, tmp_path: Path) -> None:
    _enable(project, True)
    sensors_file = project / "sensors" / "sensors.json"
    fdir = tmp_path / "specs" / "001-x"
    fdir.mkdir(parents=True)
    (fdir / "spec.md").write_text("# Spec\n\nbody\n", encoding="utf-8")
    plan = fdir / "plan.md"
    plan.write_text("# Plan\n\nbody\n", encoding="utf-8")
    flow_state.init_state(fdir, "compliance", ACTOR, project / "profiles")
    sensors.run_stage(fdir, "plan", ACTOR, sensors_file)
    problems, _ = sensors.gate_problems(fdir, "plan", sensors_file)
    assert any("compliance-section" in p for p in problems)
    plan.write_text("# Plan\n\n## Compliance\n\nAudit log kept.\n", encoding="utf-8")
    sensors.run_stage(fdir, "plan", ACTOR, sensors_file)
    problems, relied = sensors.gate_problems(fdir, "plan", sensors_file)
    assert "compliance-section" in relied
    assert not any("compliance-section" in p for p in problems)


def test_sensor_not_applied_to_other_profiles(project: Path, tmp_path: Path) -> None:
    _enable(project, True)
    sensors_file = project / "sensors" / "sensors.json"
    fdir = tmp_path / "specs" / "001-x"
    fdir.mkdir(parents=True)
    (fdir / "spec.md").write_text("# Spec\n\nbody\n", encoding="utf-8")
    (fdir / "plan.md").write_text("# Plan\n\nbody\n", encoding="utf-8")
    flow_state.init_state(fdir, "feature", ACTOR, project / "profiles")
    _, relied = sensors.gate_problems(fdir, "plan", sensors_file)
    assert "compliance-section" not in relied


def test_plugin_cannot_reuse_core_sensor_id(project: Path) -> None:
    _enable(project, True)
    path = project / "plugins" / "compliance" / "sensors.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sensors"][0]["id"] = "consistency"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FlowError):
        sensors.load_sensors(project / "sensors" / "sensors.json")


def test_agent_only_when_enabled_and_roster_valid(project: Path) -> None:
    roster_file = project / "agents" / "roster.json"
    _enable(project, False)
    assert "compliance-reviewer" not in agents.load_roster(roster_file)
    assert agents.validate_roster(agents.load_roster(roster_file), ROOT) == []
    _enable(project, True)
    roster = agents.load_roster(roster_file)
    assert roster["compliance-reviewer"].source == "plugin:compliance"
    assert roster["compliance-reviewer"].leads == ()
    assert agents.validate_roster(roster, ROOT) == []


@pytest.mark.parametrize("enabled", [False, True])
def test_doctor_has_no_failures(project: Path, enabled: bool) -> None:
    _enable(project, enabled)
    result = doctor.run_doctor(
        ROOT,
        profiles_dir=project / "profiles",
        roster_file=project / "agents" / "roster.json",
        sensors_file=project / "sensors" / "sensors.json",
        rules_file=project / "rules" / "rules.json",
    )
    assert not [
        c
        for c in result
        if c.status == "fail" and c.name in ("profiles", "roster", "sensors", "plugins")
    ]
