from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from speckit_flow import audit, cli, codebase, models, state
from speckit_flow.models import FlowError, Profile
from speckit_flow.stagedefs import CORE_FILE, StageDefError, load_stage_defs


def _file(root: Path, name: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not executed or copied", encoding="utf-8")


def test_inventory_is_path_only_sorted_and_excludes_tooling(tmp_path: Path) -> None:
    for name in (
        "src/main.ts",
        "tests/main.test.ts",
        "package.json",
        "infra/main.tf",
        "speckit_flow/cli.py",
        "scripts/speckit_guard.py",
        "scripts/speckit_session.py",
        "scripts/speckit_bootstrap.py",
        "node_modules/pkg/index.js",
        ".venv311/lib/x.py",
        "dist/bundle.js",
        ".specify/x.py",
        "graphify-out/x.py",
        "specs/example/test.py",
        ".github/example.py",
    ):
        _file(tmp_path, name)
    result = codebase.scan(tmp_path)
    assert result.sources == ("infra/main.tf", "src/main.ts", "tests/main.test.ts")
    assert result.tests == ("tests/main.test.ts",)
    assert result.manifests == ("package.json",)
    assert result.existing
    assert "not executed" not in json.dumps(result.to_dict())


def test_tooling_and_manifests_alone_are_not_existing_code(tmp_path: Path) -> None:
    _file(tmp_path, "speckit_flow/cli.py")
    _file(tmp_path, "package.json")
    _file(tmp_path, "README.md")
    assert not codebase.scan(tmp_path).existing


def test_limit_and_access_errors_are_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _file(tmp_path, "src/main.py")
    assert codebase.scan(tmp_path, max_entries=2).examined_entries == 2
    with pytest.raises(FlowError, match="limit"):
        codebase.scan(tmp_path, max_entries=1)
    with pytest.raises(FlowError, match="positive"):
        codebase.scan(tmp_path, max_entries=0)

    def denied(path: Path) -> None:
        raise PermissionError("fixture denied")

    monkeypatch.setattr(os, "scandir", denied)
    with pytest.raises(FlowError, match="fixture denied"):
        codebase.scan(tmp_path)


def test_symlinks_are_not_followed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _file(outside, "main.py")
    root = tmp_path / "project"
    root.mkdir()
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
        (root / "linked.py").symlink_to(outside / "main.py")
    except OSError:
        pytest.skip("symlink creation unavailable")
    assert not codebase.scan(root).existing


def test_windows_junction_metadata_is_excluded() -> None:
    info = Mock(
        spec=os.stat_result,
        st_mode=stat.S_IFDIR,
        st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
    )
    assert codebase._is_link(info)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction traversal check")
def test_windows_junction_is_not_traversed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _file(outside, "main.py")
    root = tmp_path / "project"
    root.mkdir()
    result = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(root / "linked"), str(outside)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not codebase.scan(root).existing


def test_cli_inventory_does_not_require_feature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _file(tmp_path, "app.py")
    monkeypatch.setattr(cli, "_REPO_ROOT", tmp_path)
    assert cli.main(["codebase", "scan", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["sources"] == ["app.py"]


@pytest.mark.parametrize(
    ("condition", "optional"),
    [("unknown", True), ("existing-codebase", False), (None, True), ([], True)],
)
def test_invalid_conditions_rejected(
    tmp_path: Path,
    condition: object,
    optional: bool,
) -> None:
    data = json.loads(CORE_FILE.read_text(encoding="utf-8"))
    data["stages"].append(
        {
            "id": "extra",
            "phase": "design",
            "optional": optional,
            "condition": condition,
        }
    )
    path = tmp_path / "stages" / "stages.json"
    path.parent.mkdir()
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(StageDefError, match="condition"):
        load_stage_defs(path)


def test_conditional_gate_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(models, "STAGE_CONDITIONS", {"plan": "existing-codebase"})
    with pytest.raises(FlowError, match="conditional"):
        Profile.from_dict(
            {
                "id": "sample",
                "description": "sample",
                "stages": ["specify", "plan"],
                "depth": "standard",
                "gates": ["plan"],
            }
        )


@pytest.mark.parametrize("existing", [False, True])
def test_conditional_start_uses_inventory_and_audits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
) -> None:
    monkeypatch.setattr(state, "STAGE_CONDITIONS", {"ideation": "existing-codebase"})
    monkeypatch.setattr(codebase, "ROOT", tmp_path)
    feature = tmp_path / "specs" / "028-sample"
    feature.mkdir(parents=True)
    if existing:
        _file(tmp_path, "src/app.py")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "sample.json").write_text(
        json.dumps(
            {
                "id": "sample",
                "description": "sample",
                "depth": "standard",
                "stages": ["ideation", "specify", "plan"],
                "gates": ["specify", "plan"],
            }
        ),
        encoding="utf-8",
    )
    state.init_state(feature, "sample", "agent:test", profiles)
    result = state.start_stage(feature, "ideation", "agent:test", profiles)
    assert result.stages["ideation"].status == ("in_progress" if existing else "skipped")
    assert result.current_stage == ("ideation" if existing else "specify")
    events = audit.read_events(feature)
    assert events[-1].type == ("stage_started" if existing else "stage_skipped")
    assert audit.verify_chain(feature) is None


@pytest.mark.parametrize("block", ["gate", "parked", "order", "in_progress"])
def test_conditional_start_preserves_existing_guards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    block: str,
) -> None:
    monkeypatch.setattr(state, "STAGE_CONDITIONS", {"ideation": "existing-codebase"})
    feature = tmp_path / "028-sample"
    feature.mkdir()
    st = state.init_state(feature, "full-lifecycle", "agent:test")
    if block == "gate":
        st.pending_gate = "specify"
    elif block == "parked":
        monkeypatch.setattr(audit, "is_parked", lambda _: True)
    elif block == "order":
        st.stages["ideation"].status = "done"
    else:
        st.stages["specify"].status = "in_progress"
    state.save_state(feature, st)

    def unexpected_scan(*args: object, **kwargs: object) -> None:
        pytest.fail("guard must reject before applicability scan")

    monkeypatch.setattr(codebase, "scan", unexpected_scan)
    with pytest.raises(FlowError):
        state.start_stage(feature, "ideation", "agent:test")


def test_scan_failure_is_audited_without_advancing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(state, "STAGE_CONDITIONS", {"ideation": "existing-codebase"})
    feature = tmp_path / "028-sample"
    feature.mkdir()
    state.init_state(feature, "full-lifecycle", "agent:test")
    before = (feature / "state.json").read_bytes()

    def fail_scan(*args: object, **kwargs: object) -> None:
        raise FlowError("fixture scan limit exceeded")

    monkeypatch.setattr(codebase, "scan", fail_scan)
    # Keep this conditional test stage ungated without altering real profile data.
    profile = Profile(
        "sample",
        "sample",
        ("ideation", "specify"),
        "standard",
        ("specify",),
    )
    monkeypatch.setattr(state, "profile_for", lambda *args: profile)
    with pytest.raises(FlowError, match="scan limit"):
        state.start_stage(feature, "ideation", "agent:test")
    assert (feature / "state.json").read_bytes() == before
    assert audit.read_events(feature)[-1].type == "failure"
    assert audit.verify_chain(feature) is None
