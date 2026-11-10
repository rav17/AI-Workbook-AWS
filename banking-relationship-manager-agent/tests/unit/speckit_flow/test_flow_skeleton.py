from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from speckit_flow import audit, sensors, units
from speckit_flow.models import FlowError


def _fixture(root: Path) -> tuple[Path, Path, list[str]]:
    feature = root / "specs" / "030-demo"
    feature.mkdir(parents=True)
    (feature / "tasks.md").write_text("- [ ] T001 Prove journey\n", encoding="utf-8")
    files = ["app.py", "test_app.py", "specs/030-demo/skeleton.md"]
    for label in files:
        (root / label).write_text("fixture content\n", encoding="utf-8")
    verify = root / ".specify" / "verify.json"
    verify.parent.mkdir()
    units.propose_verify([sys.executable, "-c", "pass"], "agent:test", verify)
    units.approve_verify("human:fixture", verify)
    return feature, verify, files


def _unit(feature: Path, files: list[str]) -> None:
    units.add_unit(
        feature,
        "walking-skeleton",
        "Thin journey",
        [],
        ["T001"],
        "agent:test",
        files=files,
    )


def test_tracked_checkpoint_is_source_bound_and_later_units_preserve_it(tmp_path: Path) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)
    assert units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)[0]
    cp = units.checkpointed(feature)["walking-skeleton"]
    assert set(cp["files"]) == set(files)
    assert cp["definition"]
    assert not units.skeleton_problems(feature)
    units.add_unit(feature, "next", "Next", ["walking-skeleton"], [], "agent:test")
    assert units.checkpointed(feature)["walking-skeleton"] == cp
    assert not units.skeleton_problems(feature)
    assert audit.verify_chain(feature) is None


@pytest.mark.parametrize("index", [0, 1, 2])
def test_changed_source_test_or_report_requires_new_checkpoint(tmp_path: Path, index: int) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)
    units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    (tmp_path / files[index]).write_text("changed\n", encoding="utf-8")
    assert "stale" in "; ".join(units.skeleton_problems(feature))
    assert units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)[0]
    assert not units.skeleton_problems(feature)


def test_failed_recheck_invalidates_prior_pass(tmp_path: Path) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)
    units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    with patch.object(units, "run_verify", return_value=(False, "exit code 3", "digest")):
        assert not units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)[0]
    assert "walking-skeleton" not in units.checkpointed(feature)
    assert units.skeleton_problems(feature)


def test_unapproved_recheck_and_command_change_block_old_evidence(tmp_path: Path) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)
    units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    units.propose_verify([sys.executable, "-c", "print('new')"], "agent:test", verify)
    assert units.skeleton_problems(feature)
    with pytest.raises(FlowError, match="not approved"):
        units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    assert "walking-skeleton" not in units.checkpointed(feature)
    units.approve_verify("human:fixture", verify)
    assert units.skeleton_problems(feature)
    assert units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)[0]
    assert not units.skeleton_problems(feature)


def test_changes_during_verification_fail_checkpoint(tmp_path: Path) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)

    def mutate(*args: object) -> tuple[bool, str, str]:
        (tmp_path / files[0]).write_text("changed during verify", encoding="utf-8")
        return True, "exit code 0", "digest"

    with patch.object(units, "run_verify", side_effect=mutate):
        ok, reason = units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    assert not ok and "changed" in reason
    assert not units.checkpointed(feature)


@pytest.mark.parametrize(
    "bad",
    [
        "../outside.py",
        "/root.py",
        "C:\\outside.py",
        "a/../app.py",
        "./app.py",
        "app.py/",
        "a//b.py",
        "a:stream",
        "a/./b.py",
        ".",
        "NUL.py",
    ],
)
def test_unsafe_tracked_paths_are_rejected(tmp_path: Path, bad: str) -> None:
    feature, _, _ = _fixture(tmp_path)
    with pytest.raises(FlowError, match="path"):
        _unit(feature, [bad])
    assert not units.load_units(feature)


def test_duplicate_and_file_limits_are_enforced(tmp_path: Path) -> None:
    feature, _, _ = _fixture(tmp_path)
    many = [f"file{i}.txt" for i in range(units.MAX_TRACKED_FILES + 1)]
    for label in many:
        (tmp_path / label).write_text("bounded", encoding="utf-8")
    assert len(units.tracked_fingerprints(tmp_path, many[:-1])) == units.MAX_TRACKED_FILES
    for files in (["app.py", "APP.py"], many):
        with pytest.raises(FlowError):
            _unit(feature, files)
    (tmp_path / "app.py").write_bytes(b"x" * units.MAX_TRACKED_BYTES)
    assert units.tracked_fingerprints(tmp_path, ["app.py"])
    (tmp_path / "app.py").write_bytes(b"x" * (units.MAX_TRACKED_BYTES + 1))
    with pytest.raises(FlowError, match="limit"):
        units.tracked_fingerprints(tmp_path, ["app.py"])
    with pytest.raises(FlowError):
        units.tracked_fingerprints(tmp_path, ["missing.py"])
    with pytest.raises(FlowError, match="regular"):
        units.tracked_fingerprints(tmp_path, ["specs"])


def test_windows_separators_are_normalized(tmp_path: Path) -> None:
    feature, _, files = _fixture(tmp_path)
    _unit(feature, [p.replace("/", "\\") for p in files])
    assert units.load_units(feature)[0]["files"] == files


def test_symlink_ancestors_are_not_followed(tmp_path: Path) -> None:
    feature, _, _ = _fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "app.py").write_text("not followed", encoding="utf-8")
    try:
        (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(FlowError, match="symlink"):
        units.tracked_fingerprints(tmp_path, ["linked/app.py"])


@pytest.mark.parametrize("case", ["missing", "no-files", "unknown-task", "no-report"])
def test_skeleton_requires_real_tasks_report_files_and_checkpoint(
    tmp_path: Path,
    case: str,
) -> None:
    feature, _, files = _fixture(tmp_path)
    if case != "missing":
        selected = [] if case == "no-files" else files
        if case == "no-report":
            selected = files[:2]
        _unit(feature, selected)
        if case == "unknown-task":
            (feature / "tasks.md").write_text("- [ ] T999 Other\n", encoding="utf-8")
    assert units.skeleton_problems(feature)


def test_sensor_freshness_includes_checkpoint_and_source(tmp_path: Path) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)
    config = tmp_path / ".specify" / "sensors" / "sensors.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps(
            {
                "sensors": [
                    {
                        "id": "skeleton-check",
                        "kind": "builtin",
                        "builtin": "skeleton",
                        "stages": ["implement"],
                        "required": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert sensors.run_stage(feature, "implement", "agent:test", config)[0]["status"] == "fail"
    units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    assert sensors.run_stage(feature, "implement", "agent:test", config)[0]["status"] == "pass"
    assert not sensors.gate_problems(feature, "implement", config)[0]
    (tmp_path / files[0]).write_text("changed\n", encoding="utf-8")
    assert sensors.gate_problems(feature, "implement", config)[0]
    assert sensors.run_stage(feature, "implement", "agent:test", config)[0]["status"] == "fail"


def test_unit_metadata_changes_make_checkpoint_stale(tmp_path: Path) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)
    units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    path = feature / "units.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["units"][0]["title"] = "different journey"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "stale" in "; ".join(units.skeleton_problems(feature))


def test_missing_file_recheck_invalidates_prior_pass(tmp_path: Path) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)
    units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    (tmp_path / files[0]).unlink()
    with pytest.raises(FlowError, match="cannot read"):
        units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    assert not units.checkpointed(feature)
    assert audit.read_events(feature)[-1].type == "unit_checkpoint"
    assert "failed" in audit.read_events(feature)[-1].detail


def test_timeout_invalidates_old_checkpoint(tmp_path: Path) -> None:
    feature, verify, files = _fixture(tmp_path)
    _unit(feature, files)
    units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("fixture", 600)):
        ok, reason = units.checkpoint_unit(feature, "walking-skeleton", "agent:test", verify)
    assert not ok and "timed out" in reason
    assert not units.checkpointed(feature)


def test_tracked_access_and_reparse_errors_are_explicit(tmp_path: Path) -> None:
    with patch.object(Path, "lstat", side_effect=PermissionError("fixture")):
        with pytest.raises(FlowError, match="PermissionError"):
            units.tracked_fingerprints(tmp_path, ["app.py"])
    info = SimpleNamespace(
        st_mode=stat.S_IFDIR,
        st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
    )
    with patch.object(Path, "lstat", return_value=info):
        with pytest.raises(FlowError, match="reparse"):
            units.tracked_fingerprints(tmp_path, ["linked/app.py"])


@pytest.mark.skipif(os.name != "nt", reason="Windows junction traversal check")
def test_tracked_windows_junction_is_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "app.py").write_text("not followed", encoding="utf-8")
    result = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(tmp_path / "linked"), str(outside)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(FlowError, match="reparse"):
        units.tracked_fingerprints(tmp_path, ["linked/app.py"])


def test_skeleton_options_not_silently_accepted(tmp_path: Path) -> None:
    config = tmp_path / "sensors.json"
    config.write_text(
        json.dumps(
            {
                "sensors": [
                    {
                        "id": "test",
                        "kind": "builtin",
                        "builtin": "skeleton",
                        "stages": ["implement"],
                        "options": {"skip_verify": True},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FlowError, match="does not accept options"):
        sensors.load_sensors(config)


def test_skeleton_sensor_scope_does_not_apply_to_default_profiles(tmp_path: Path) -> None:
    sensor = sensors.Sensor(
        "test",
        "builtin",
        ("implement",),
        True,
        builtin="skeleton",
        profiles=("skeleton-first",),
    )
    assert sensors.for_stage([sensor], "implement", "feature") == []
    assert sensors.for_stage([sensor], "implement", "skeleton-first") == [sensor]
