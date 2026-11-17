from __future__ import annotations

import hashlib
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


def test_practices_are_read_only_sorted_and_do_not_emit_content(tmp_path: Path) -> None:
    for name in (
        "pyproject.toml", "README.md", ".github/workflows/check.yml",
        ".github/instructions/python.instructions.md", ".github/copilot-instructions.md",
        "src/app.py", ".env", "node_modules/package.json", "child/package.json",
    ):
        _file(tmp_path, name)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    snapshot = codebase.practices(tmp_path)
    assert snapshot["status"] == "found"
    assert snapshot["project_root"] == str(tmp_path.resolve())
    paths = [source["path"] for source in snapshot["sources"]]
    assert paths == [
        ".github/copilot-instructions.md",
        ".github/instructions/python.instructions.md",
        ".github/workflows/check.yml", "README.md", "pyproject.toml",
    ]
    assert all(
        source["sha256"] == hashlib.sha256(b"not executed or copied").hexdigest()
        for source in snapshot["sources"]
    )
    assert "not executed or copied" not in json.dumps(snapshot)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert codebase.practices(tmp_path) == snapshot
    assert "No commands were executed" in snapshot["notice"]


@pytest.mark.parametrize("change", ["edit", "add", "delete", "rename"])
def test_practices_fingerprint_tracks_source_changes(tmp_path: Path, change: str) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text("before", encoding="utf-8")
    stamp = path.stat()
    before = codebase.practices(tmp_path)["fingerprint"]
    if change == "edit":
        path.write_text("after!", encoding="utf-8")
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    elif change == "add":
        _file(tmp_path, "Makefile")
    elif change == "delete":
        path.unlink()
    else:
        path.rename(tmp_path / "ruff.toml")
    assert codebase.practices(tmp_path)["fingerprint"] != before


def test_practices_empty_and_nested_package_scope(tmp_path: Path) -> None:
    nested = tmp_path / "frontend"
    _file(nested, "package.json")
    assert codebase.practices(tmp_path)["status"] == "empty"
    snapshot = codebase.practices(nested)
    assert snapshot["status"] == "found"
    assert [s["path"] for s in snapshot["sources"]] == ["package.json"]


@pytest.mark.parametrize(
    ("limit", "value", "message"),
    [
        ("max_bytes", 1, "byte limit"),
        ("max_sources", 1, "source limit"),
        ("max_entries", 1, "entry limit"),
        ("max_sources", 0, "positive"),
    ],
)
def test_practices_limits_fail_explicitly(
    tmp_path: Path, limit: str, value: int, message: str
) -> None:
    _file(tmp_path, "pyproject.toml")
    _file(tmp_path, "Makefile")
    with pytest.raises(FlowError, match=message):
        codebase.practices(tmp_path, **{limit: value})


def test_practices_io_failures_are_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _file(tmp_path, "pyproject.toml")

    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("fixture denied")

    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(FlowError, match="cannot inspect practices.*fixture denied"):
        codebase.practices(tmp_path)


def test_practices_exact_limits_and_ignored_changes(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_bytes(b"{}")
    snapshot = codebase.practices(tmp_path, max_bytes=2, max_sources=1, max_entries=1)
    _file(tmp_path, ".env")
    assert codebase.practices(tmp_path)["fingerprint"] == snapshot["fingerprint"]


@pytest.mark.parametrize("invalid", ["root", "source", "directory"])
def test_practices_reject_invalid_file_types(tmp_path: Path, invalid: str) -> None:
    if invalid == "root":
        _file(tmp_path, "root.txt")
        root = tmp_path / "root.txt"
    else:
        root = tmp_path
        if invalid == "source":
            (tmp_path / "package.json").mkdir()
        else:
            _file(tmp_path, ".github")
    with pytest.raises(FlowError, match="non-symlink"):
        codebase.practices(root)


def test_practices_reject_relevant_symlinks(tmp_path: Path) -> None:
    target = tmp_path / "source.txt"
    _file(tmp_path, "source.txt")
    try:
        (tmp_path / "pyproject.toml").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(FlowError, match="non-symlink"):
        codebase.practices(tmp_path)


def test_practices_reject_junction_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    github = tmp_path / ".github"
    github.mkdir()
    original = Path.lstat

    def junction(path: Path) -> os.stat_result:
        if path == github:
            return Mock(
                spec=os.stat_result, st_mode=stat.S_IFDIR,
                st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
            )
        return original(path)

    monkeypatch.setattr(Path, "lstat", junction)
    with pytest.raises(FlowError, match="non-symlink directory"):
        codebase.practices(tmp_path)


def test_practices_cli_needs_no_feature_and_reports_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_REPO_ROOT", tmp_path)
    assert cli.main(["codebase", "practices", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "empty"
    package = tmp_path / "package"
    _file(package, "package.json")
    assert cli.main([
        "codebase", "practices", "--project-dir", str(package), "--json",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["project_root"] == str(package.resolve())
    assert cli.main([
        "codebase", "practices", "--project-dir", str(tmp_path / "missing"), "--json",
    ]) == 1
    assert "cannot inspect practices" in capsys.readouterr().err


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
