from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from speckit_flow import plugins, profiles, sensors
from speckit_flow.cli import main
from speckit_flow.models import FlowError
from speckit_flow.stagedefs import CORE_FILE, StageDefError, load_stage_defs

SPECIFY = Path(__file__).resolve().parents[3] / ".specify"


@pytest.fixture
def spec_dir(tmp_path: Path) -> Path:
    root = tmp_path / ".specify"
    shutil.copytree(SPECIFY / "profiles", root / "profiles")
    shutil.copytree(SPECIFY / "sensors", root / "sensors")
    shutil.copytree(SPECIFY / "stages", root / "stages")
    return root


def _plugin(root: Path, name: str = "testing-pack", **manifest: object) -> Path:
    folder = root / "plugins" / name
    folder.mkdir(parents=True)
    data = {"name": name, "version": "1.0.0", **manifest}
    (folder / "plugin.json").write_text(json.dumps(data), encoding="utf-8")
    return folder


def _sensor(sid: str) -> dict:
    return {"id": sid, "kind": "command", "argv": ["python", "-c", "pass"], "stages": ["implement"]}


def test_plugin_adds_profile_sensor_and_stage(spec_dir: Path) -> None:
    folder = _plugin(spec_dir)
    (folder / "profiles").mkdir()
    base = json.loads((spec_dir / "profiles" / "bugfix.json").read_text("utf-8"))
    base["id"] = "perf-fix"
    (folder / "profiles" / "perf-fix.json").write_text(json.dumps(base), encoding="utf-8")
    (folder / "sensors.json").write_text(json.dumps({"sensors": [_sensor("perf")]}), "utf-8")
    stage = {"id": "perf-check", "phase": "design", "optional": True, "after": "plan"}
    (folder / "stages.json").write_text(json.dumps({"stages": [stage]}), encoding="utf-8")

    assert "perf-fix" in profiles.load_profiles(spec_dir / "profiles")
    assert "perf" in {s.id for s in sensors.load_sensors(spec_dir / "sensors" / "sensors.json")}
    ids = [s.id for s in load_stage_defs(spec_dir / "stages" / "stages.json")]
    assert ids.index("perf-check") == ids.index("plan") + 1


def test_plugin_cannot_override_core_profile_or_sensor(spec_dir: Path) -> None:
    folder = _plugin(spec_dir)
    (folder / "profiles").mkdir()
    shutil.copy(spec_dir / "profiles" / "bugfix.json", folder / "profiles" / "bugfix.json")
    with pytest.raises(FlowError, match="only add profiles"):
        profiles.load_profiles(spec_dir / "profiles")
    shutil.rmtree(folder / "profiles")
    core_id = sensors.load_sensors(spec_dir / "sensors" / "sensors.json")[0].id
    (folder / "sensors.json").write_text(json.dumps({"sensors": [_sensor(core_id)]}), "utf-8")
    with pytest.raises(FlowError, match="only add sensors"):
        sensors.load_sensors(spec_dir / "sensors" / "sensors.json")


def test_disabled_plugin_is_ignored(spec_dir: Path) -> None:
    folder = _plugin(spec_dir, enabled=False)
    (folder / "sensors.json").write_text(json.dumps({"sensors": [_sensor("perf")]}), "utf-8")
    assert "perf" not in {s.id for s in sensors.load_sensors(spec_dir / "sensors" / "sensors.json")}
    assert plugins.discover(spec_dir) == []
    assert len(plugins.discover(spec_dir, enabled_only=False)) == 1


@pytest.mark.parametrize(
    "manifest",
    [
        {"name": "other", "version": "1"},
        {"name": "testing-pack"},
        {"name": "Bad Name", "version": "1"},
    ],
)
def test_invalid_manifest_is_refused(spec_dir: Path, manifest: dict) -> None:
    folder = spec_dir / "plugins" / "testing-pack"
    folder.mkdir(parents=True)
    (folder / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(plugins.PluginError):
        plugins.discover(spec_dir)
    with pytest.raises(FlowError):
        profiles.load_profiles(spec_dir / "profiles")


def test_plugin_folder_without_manifest_is_refused(spec_dir: Path) -> None:
    (spec_dir / "plugins" / "orphan").mkdir(parents=True)
    with pytest.raises(plugins.PluginError):
        plugins.discover(spec_dir)


def test_two_plugins_cannot_define_the_same_stage(spec_dir: Path) -> None:
    stage = {"id": "perf-check", "phase": "design", "optional": True, "after": "plan"}
    for name in ("a-pack", "b-pack"):
        folder = _plugin(spec_dir, name)
        (folder / "stages.json").write_text(json.dumps({"stages": [stage]}), encoding="utf-8")
    with pytest.raises(StageDefError, match="duplicates"):
        load_stage_defs(spec_dir / "stages" / "stages.json")
    assert CORE_FILE.is_file()


def test_plugins_cli_lists_and_validates(
    spec_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = _plugin(spec_dir)
    (folder / "sensors.json").write_text(json.dumps({"sensors": [_sensor("perf")]}), "utf-8")
    args = [
        "--profiles-dir", str(spec_dir / "profiles"),
        "--sensors-file", str(spec_dir / "sensors" / "sensors.json"),
        "--json",
    ]  # fmt: skip
    assert main(["plugins", "validate", *args]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["plugins"][0]["name"] == "testing-pack"
    assert data["plugins"][0]["provides"] == ["sensors"]
