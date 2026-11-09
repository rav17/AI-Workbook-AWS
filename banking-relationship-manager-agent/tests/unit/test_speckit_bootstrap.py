from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import pytest

ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "speckit_bootstrap.py"


def _run(script: Path, target: Path, action: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), action, "--target", str(target), *args],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_dry_run_does_not_write_target(tmp_path: Path) -> None:
    target = tmp_path / "sample-project"
    target.mkdir()

    result = _run(BOOTSTRAP, target, "install", "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "CREATE" in result.stdout
    assert not (target / "speckit_flow").exists()
    assert not (target / ".specify").exists()


def test_install_is_portable_and_target_doctor_passes(tmp_path: Path) -> None:
    target = tmp_path / "unrelated-python-project"
    target.mkdir()
    existing_instructions = target / ".github" / "copilot-instructions.md"
    existing_instructions.parent.mkdir()
    existing_instructions.write_text("project-owned instructions\n", encoding="utf-8")

    result = _run(BOOTSTRAP, target, "install")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "speckit_flow" / "__main__.py").is_file()
    assert (target / ".github" / "skills" / "speckit-specify" / "SKILL.md").is_file()
    assert not (target / "aria").exists()
    assert not (target / ".specify" / "memory" / "constitution.md").exists()
    assert not (target / ".specify" / "knowledge" / "banking-compliance.md").exists()
    assert not (target / "pyproject.toml").exists()
    assert not (target / ".specify" / "verify.json").exists()
    assert (target / ".specify" / ".gitignore").is_file()
    assert existing_instructions.read_text(encoding="utf-8") == "project-owned instructions\n"

    sensors = json.loads(
        (target / ".specify" / "sensors" / "sensors.json").read_text(encoding="utf-8")
    )
    assert not any(sensor["kind"] == "command" for sensor in sensors["sensors"])

    env = {**os.environ, "PYTHONPATH": str(target)}
    doctor = subprocess.run(
        [sys.executable, "-m", "speckit_flow", "doctor"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    profiles = subprocess.run(
        [sys.executable, "-m", "speckit_flow", "profiles", "validate"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert profiles.returncode == 0, profiles.stdout + profiles.stderr
    assignments = subprocess.run(
        [
            sys.executable,
            "-m",
            "speckit_flow",
            "agents",
            "assign",
            "--profile",
            "feature",
        ],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert assignments.returncode == 0, assignments.stdout + assignments.stderr
    assert "aws-platform" not in assignments.stdout
    assert "support=compliance" not in assignments.stdout

    entry = target / ".github" / "skills" / "speckit-workflow" / "SKILL.md"
    assert "speckit-conductor" in entry.read_text(encoding="utf-8")
    routing = subprocess.run(
        [
            sys.executable, "-m", "speckit_flow", "workflow", "recommend",
            "Create a new reading-list feature", "--json",
        ],
        cwd=target, env=env, capture_output=True, text=True, timeout=120,
    )
    assert routing.returncode == 0, routing.stdout + routing.stderr
    advice = json.loads(routing.stdout)
    assert advice["profile"] == "full-lifecycle"
    assert advice["confirmation_required"] is True
    assert not list((target / "specs").glob("*/state.json"))

    feature = target / "specs" / "001-reading-list"
    feature.mkdir(parents=True, exist_ok=True)
    initialized = subprocess.run(
        [
            sys.executable, "-m", "speckit_flow", "init", "--profile", "full-lifecycle",
            "--feature-dir", str(feature), "--actor", "human:fixture",
        ],
        cwd=target, env=env, capture_output=True, text=True, timeout=120,
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    preflight = subprocess.run(
        [
            sys.executable, "-m", "speckit_flow", "workflow", "dispatch",
            "--feature-dir", str(feature), "--json",
        ],
        cwd=target, env=env, capture_output=True, text=True, timeout=120,
    )
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr
    brief = json.loads(preflight.stdout)
    assert brief["stage"] == "ideation"
    assert brief["lead"]["id"] == "product"
    assert brief["delegated_stage"] == "SPECKIT_DELEGATED_STAGE=ideation"
    assert existing_instructions.read_text(encoding="utf-8") == "project-owned instructions\n"


def test_install_conflict_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "existing-project"
    target.mkdir()
    (target / "speckit_flow").mkdir()
    (target / "speckit_flow" / "__main__.py").write_text("local file\n", encoding="utf-8")

    result = _run(BOOTSTRAP, target, "install")

    assert result.returncode != 0
    assert "CONFLICT" in result.stdout
    assert (target / "speckit_flow" / "__main__.py").read_text(encoding="utf-8") == "local file\n"
    assert not (target / "speckit_flow" / "cli.py").exists()
    assert not (target / ".specify" / "speckit-portable-manifest.json").exists()


def test_install_preserves_target_governance_and_active_feature(tmp_path: Path) -> None:
    target = tmp_path / "existing-project"
    target.mkdir()
    files = {
        ".specify/memory/constitution.md": "# Reading-list principles\n\nNo cloud services.\n",
        ".specify/feature.json": '{"feature_directory": "specs/017-reading-list"}\n',
        ".specify/custom/profiles/local.json": '{"id": "local"}\n',
        ".specify/verify.json": '{"command": ["node", "--test"], "approved_by": ""}\n',
    }
    for relative, content in files.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    installed = _run(BOOTSTRAP, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    for relative, content in files.items():
        assert (target / relative).read_text(encoding="utf-8") == content


def _make_fixture_bundle(root: Path, content: str) -> Path:
    (root / "scripts").mkdir(parents=True)
    (root / "payload").mkdir()
    (root / "payload" / "shared.txt").write_text(content, encoding="utf-8")
    bundle = {
        "bundle_version": "test",
        "files": [
            {
                "source": "payload",
                "destination": "shared",
                "category": "engine",
                "include": ["shared.txt"],
            }
        ],
    }
    (root / "scripts" / "speckit-portable-bundle.json").write_text(
        json.dumps(bundle), encoding="utf-8"
    )
    script = root / "scripts" / "speckit_bootstrap.py"
    shutil.copyfile(BOOTSTRAP, script)
    return script


def test_update_replaces_unchanged_file_and_preserves_custom_files(tmp_path: Path) -> None:
    source = tmp_path / "bundle-source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "version one\n")

    installed = _run(script, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr

    custom = target / ".specify" / "custom" / "local.json"
    custom.parent.mkdir(parents=True)
    custom.write_text('{"local": true}\n', encoding="utf-8")
    (source / "payload" / "shared.txt").write_text("version two\n", encoding="utf-8")

    updated = _run(script, target, "update")

    assert updated.returncode == 0, updated.stdout + updated.stderr
    assert (target / "shared" / "shared.txt").read_text(encoding="utf-8") == "version two\n"
    assert custom.read_text(encoding="utf-8") == '{"local": true}\n'


def test_update_reports_modified_shared_file_without_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "bundle-source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "version one\n")

    installed = _run(script, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr

    modified = target / "shared" / "shared.txt"
    modified.write_text("project modification\n", encoding="utf-8")
    (source / "payload" / "shared.txt").write_text("version two\n", encoding="utf-8")
    added = source / "payload" / "new.txt"
    added.write_text("new shared file\n")
    bundle_path = source / "scripts" / "speckit-portable-bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["files"][0]["include"].append("new.txt")
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    updated = _run(script, target, "update")

    assert updated.returncode != 0
    assert "CONFLICT" in updated.stdout
    assert modified.read_text(encoding="utf-8") == "project modification\n"
    assert not (target / "shared" / "new.txt").exists()


def test_identical_preexisting_file_is_not_claimed_on_install(tmp_path: Path) -> None:
    source = tmp_path / "bundle-source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "version one\n")
    existing = target / "shared"
    existing.mkdir()
    shared = existing / "shared.txt"
    shared.write_text("version one\n", encoding="utf-8")

    installed = _run(script, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    install_manifest = json.loads(
        (target / ".specify" / "speckit-portable-manifest.json").read_text(encoding="utf-8")
    )
    assert "shared/shared.txt" not in {item["path"] for item in install_manifest["files"]}

    (source / "payload" / "shared.txt").write_text("version two\n", encoding="utf-8")
    updated = _run(script, target, "update")

    assert updated.returncode != 0
    assert "CONFLICT" in updated.stdout
    assert shared.read_text(encoding="utf-8") == "version one\n"


def test_bundle_rejects_path_traversal(tmp_path: Path) -> None:
    source = tmp_path / "bundle-source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "payload\n")
    manifest_path = source / "scripts" / "speckit-portable-bundle.json"
    manifest_path.write_text(
        json.dumps(
            {
                "bundle_version": "test",
                "files": [
                    {
                        "source": "payload",
                        "destination": "../outside.txt",
                        "category": "engine",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _run(script, target, "install")

    assert result.returncode == 2
    assert "unsafe destination" in result.stderr
    assert not (tmp_path / "outside.txt").exists()
    assert not (target / ".specify").exists()


def test_directory_bundle_excludes_unlisted_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "shared\n")
    (source / "payload" / "project-private.txt").write_text("do not export\n")
    result = _run(script, target, "install")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (target / "shared" / "project-private.txt").exists()


@pytest.mark.parametrize(
    "destination",
    ["Shared/SHARED.txt", "shared/shared.txt/child", "shared"],
)
def test_bundle_rejects_destination_aliases_and_collisions(
    tmp_path: Path, destination: str
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "shared\n")
    manifest_path = source / "scripts" / "speckit-portable-bundle.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"].append(
        {"source": "payload/shared.txt", "destination": destination, "category": "engine"}
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = _run(script, target, "install")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "collision" in result.stderr.lower()
    assert not list(target.iterdir())


def test_source_and_target_cannot_overlap(tmp_path: Path) -> None:
    source = tmp_path / "source"
    script = _make_fixture_bundle(source, "shared\n")
    target = source / "target"
    target.mkdir()
    result = _run(script, target, "install")
    assert result.returncode == 2
    assert "overlap" in result.stderr
    assert not list(target.iterdir())


def test_seed_configuration_is_project_owned_after_install(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "seed one\n")
    bundle_path = source / "scripts" / "speckit-portable-bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["files"][0]["seed"] = True
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    assert _run(script, target, "install").returncode == 0
    (source / "payload" / "shared.txt").write_text("new seed default\n")
    result = _run(script, target, "update")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "shared" / "shared.txt").read_text() == "seed one\n"
    (target / "shared" / "shared.txt").write_text("local policy\n")
    result = _run(script, target, "update")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "shared" / "shared.txt").read_text() == "local policy\n"


def test_source_plugin_enablement_does_not_leak_to_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "shared\n")
    (source / "payload" / "plugin.json").write_text(
        json.dumps({"name": "example", "version": "1.0", "enabled": True})
    )
    bundle_path = source / "scripts" / "speckit-portable-bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["files"].append(
        {
            "source": "payload/plugin.json",
            "destination": ".specify/plugins/example/plugin.json",
            "category": "plugins",
            "seed": True,
        }
    )
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    result = _run(script, target, "install")
    assert result.returncode == 0, result.stdout + result.stderr
    plugin_path = target / ".specify" / "plugins" / "example" / "plugin.json"
    assert json.loads(plugin_path.read_text())["enabled"] is False
    assert json.loads((source / "payload" / "plugin.json").read_text())["enabled"] is True


def test_update_dry_run_and_missing_file_never_write(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "one\n")
    assert _run(script, target, "install").returncode == 0
    manifest = target / ".specify" / "speckit-portable-manifest.json"
    original_manifest = manifest.read_bytes()
    shared = target / "shared" / "shared.txt"
    (source / "payload" / "shared.txt").write_text("two\n")
    dry_run = _run(script, target, "update", "--dry-run")
    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    assert shared.read_text() == "one\n"
    assert manifest.read_bytes() == original_manifest
    shared.unlink()
    result = _run(script, target, "update")
    assert result.returncode == 1
    assert "missing" in result.stdout
    assert not shared.exists()
    assert manifest.read_bytes() == original_manifest


def test_manual_conflict_resolution_records_new_baseline(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    target.mkdir()
    script = _make_fixture_bundle(source, "one\n")
    assert _run(script, target, "install").returncode == 0
    shared = target / "shared" / "shared.txt"
    (source / "payload" / "shared.txt").write_text("two\n")
    shared.write_text("two\n")
    assert _run(script, target, "update").returncode == 0
    (source / "payload" / "shared.txt").write_text("three\n")
    result = _run(script, target, "update")
    assert result.returncode == 0, result.stdout + result.stderr
    assert shared.read_text() == "three\n"


def _flow(target: Path, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", "speckit_flow", *args],
        cwd=target,
        env={**os.environ, "PYTHONPATH": str(target), "PYTHONNOUSERSITE": "1"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == expected, f"{args}: {result.stdout}\n{result.stderr}"
    return result


def test_non_banking_cli_lifecycle_end_to_end(tmp_path: Path) -> None:
    started = perf_counter()
    target = tmp_path / "reading-list"
    target.mkdir()
    git = subprocess.run(
        ["git", "init", "--quiet", str(target)], capture_output=True, text=True, timeout=30
    )
    assert git.returncode == 0, git.stderr
    installed = _run(BOOTSTRAP, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr

    pointer = json.loads((target / ".specify" / "feature.json").read_text())
    feature = target / pointer["feature_directory"]
    feature.mkdir(parents=True)
    _flow(target, "init", "--profile", "feature", "--actor", "agent:product")
    assert not (target / ".specify" / "verify.json").exists()

    artifacts = {
        "specify": (
            "spec.md",
            "# Reading-list feature\n\n## Requirements\n\n"
            "- **FR-001**: Return unread titles without changing their order.\n",
        ),
        "plan": (
            "plan.md",
            "# Reading-list plan\n\nUse a pure function and standard-library tests.\n"
            "Run the local check before checkpointing the implementation.\n",
        ),
        "tasks": (
            "tasks.md",
            "# Reading-list tasks\n\n"
            "- [ ] T001 Implement unread-title filtering (FR-001)\n"
            "- [ ] T002 Test ordering and empty lists (FR-001)\n",
        ),
    }
    for stage, (name, content) in artifacts.items():
        _flow(target, "stage", "start", stage, "--actor", "agent:developer")
        (feature / name).write_text(content, encoding="utf-8")
        _flow(target, "stage", "done", stage, "--actor", "agent:developer")
        if stage in {"specify", "plan"}:
            blocked = _flow(
                target, "gate", "approve", stage, "--actor", "human:fixture", expected=1
            )
            assert "required sensor" in blocked.stderr
        _flow(target, "sensors", "run", stage, "--actor", "agent:quality")
        if stage in {"specify", "plan"}:
            blocked = _flow(
                target, "gate", "approve", stage, "--actor", "agent:conductor", expected=1
            )
            assert "only a human" in blocked.stderr
            # Synthetic gate decisions in this disposable fixture are user-authorized.
            _flow(target, "gate", "approve", stage, "--actor", "human:fixture")

    _flow(target, "trace", "--require-tests")
    _flow(target, "stage", "start", "implement", "--actor", "agent:developer")
    _flow(
        target,
        "units",
        "add",
        "filter",
        "Unread titles",
        "--tasks",
        "T001,T002",
        "--actor",
        "agent:developer",
    )
    (target / "reading_list.py").write_text(
        "def unread_titles(books):\n"
        "    return [title for title, is_read in books if not is_read]\n",
        encoding="utf-8",
    )
    (target / "check.py").write_text(
        "import unittest\nfrom reading_list import unread_titles\n\n"
        "class ReadingListTests(unittest.TestCase):\n"
        "    def test_unread_order(self):\n"
        "        self.assertEqual(unread_titles([('B', False), ('A', True), "
        "('C', False)]), ['B', 'C'])\n"
        "    def test_empty(self):\n"
        "        self.assertEqual(unread_titles([]), [])\n\n"
        "unittest.main()\n",
        encoding="utf-8",
    )
    _flow(
        target,
        "verify",
        "propose",
        "--actor",
        "agent:developer",
        "--",
        "python",
        "check.py",
    )
    _flow(target, "units", "checkpoint", "filter", "--actor", "agent:developer", expected=1)
    _flow(target, "verify", "approve", "--actor", "agent:developer", expected=1)
    _flow(target, "verify", "approve", "--actor", "human:fixture")
    _flow(target, "units", "checkpoint", "filter", "--actor", "agent:developer")
    (feature / "tasks.md").write_text(
        artifacts["tasks"][1].replace("- [ ]", "- [X]"), encoding="utf-8"
    )
    _flow(target, "sensors", "run", "implement", "--actor", "agent:quality")
    _flow(target, "stage", "done", "implement", "--actor", "agent:developer")
    _flow(target, "resume")
    _flow(target, "doctor")
    state = json.loads((feature / "state.json").read_text())
    assert state["current_stage"] is None
    assert state["pending_gate"] is None
    assert all(state["stages"][stage]["status"] == "done" for stage in (*artifacts, "implement"))
    units = json.loads((feature / "units.json").read_text())
    assert "filter" in units["checkpoints"]
    events = [json.loads(line) for line in (feature / "audit.jsonl").read_text().splitlines()]
    assert {event["stage"] for event in events if event["type"] == "gate_approved"} == {
        "specify",
        "plan",
    }
    assert any(event["type"] == "unit_checkpoint" for event in events)
    assert perf_counter() - started < 600


def test_optional_packs_stay_disabled_after_install(tmp_path: Path) -> None:
    target = tmp_path / "sample-project"
    target.mkdir()

    result = _run(BOOTSTRAP, target, "install")

    assert result.returncode == 0, result.stdout + result.stderr
    for plugin in (
        "compliance", "aidlc-extras", "codebase-analysis", "operational-readiness",
        "walking-skeleton", "stage-contracts",
    ):
        manifest = json.loads(
            (target / ".specify" / "plugins" / plugin / "plugin.json").read_text(encoding="utf-8")
        )
        assert manifest["enabled"] is False
    env = {**os.environ, "PYTHONPATH": str(target)}
    profiles = subprocess.run(
        [sys.executable, "-m", "speckit_flow", "profiles", "list"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert profiles.returncode == 0, profiles.stdout + profiles.stderr
    assert "nfr-hardening" not in profiles.stdout
    assert "brownfield" not in profiles.stdout
    assert "release-ready" not in profiles.stdout
    assert "skeleton-first" not in profiles.stdout


def test_portable_walking_skeleton_proves_entry_to_output(tmp_path: Path) -> None:
    target = tmp_path / "reading-list-skeleton"
    target.mkdir()
    installed = _run(BOOTSTRAP, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert (target / ".github" / "skills" / "speckit-skeleton" / "SKILL.md").is_file()
    plugin_file = target / ".specify" / "plugins" / "walking-skeleton" / "plugin.json"
    plugin = json.loads(plugin_file.read_text(encoding="utf-8"))
    assert plugin["enabled"] is False
    plugin["enabled"] = True
    plugin_file.write_text(json.dumps(plugin), encoding="utf-8")
    _flow(target, "plugins", "validate")
    _flow(target, "doctor")
    assignment = _flow(target, "agents", "assign", "--profile", "skeleton-first").stdout
    assert "walking-skeleton lead=developer support=quality" in assignment

    pointer = json.loads((target / ".specify" / "feature.json").read_text())
    feature = target / pointer["feature_directory"]
    feature.mkdir(parents=True)
    _flow(target, "init", "--profile", "skeleton-first", "--actor", "agent:product")
    for stage, name, content in (
        ("specify", "spec.md",
         "# Reading list\n\n- FR-001: Return unread titles in input order.\n"),
        ("plan", "plan.md", "# Plan\n\nJSON stdin -> reading-list filter -> JSON stdout.\n"),
        ("tasks", "tasks.md", "# Tasks\n\n- [ ] T001 Implement entry journey (FR-001)\n"
         "- [ ] T002 Test exact output (FR-001)\n"),
    ):
        _flow(target, "stage", "start", stage, "--actor", "agent:conductor")
        (feature / name).write_text(content, encoding="utf-8")
        _flow(target, "stage", "done", stage, "--actor", "agent:conductor")
        _flow(target, "sensors", "run", stage, "--actor", "agent:quality")
        if stage != "tasks":
            _flow(target, "gate", "approve", stage, "--actor", "human:fixture")

    _flow(target, "stage", "start", "walking-skeleton", "--actor", "agent:developer")
    (target / "reading_list.py").write_text(
        "def unread_titles(books):\n"
        "    return [book['title'] for book in books if not book['read']]\n", encoding="utf-8",
    )
    (target / "entry.py").write_text(
        "import json\nimport sys\nfrom reading_list import unread_titles\n"
        "json.dump(unread_titles(json.load(sys.stdin)), sys.stdout)\n", encoding="utf-8",
    )
    (target / "check.py").write_text(
        "import json\nimport subprocess\nimport sys\nimport unittest\n\n"
        "class Journey(unittest.TestCase):\n"
        "    def test_exact_entry_output(self):\n"
        "        books = [{'title': 'B', 'read': False}, {'title': 'A', 'read': True},\n"
        "                 {'title': 'C', 'read': False}]\n"
        "        result = subprocess.run([sys.executable, 'entry.py'],\n"
        "            input=json.dumps(books), text=True, capture_output=True, timeout=10)\n"
        "        self.assertEqual(result.returncode, 0, result.stderr)\n"
        "        self.assertEqual(result.stdout, '[\"B\", \"C\"]')\n\n"
        "unittest.main()\n", encoding="utf-8",
    )
    report = feature / "skeleton.md"
    report.write_text(
        "# Thin journey\n\nT001/T002, FR-001. JSON stdin via entry.py -> unread filter "
        "-> exact JSON stdout. check.py asserts B,C order and excludes read title A.\n"
        "No mocks. Local CLI only; persistence/live services out of scope.\n"
        "Review actual checkpoint/test assertions before expanding.\n", encoding="utf-8",
    )
    files = f"entry.py,reading_list.py,check.py,{pointer['feature_directory']}/skeleton.md"
    _flow(
        target, "units", "add", "walking-skeleton", "Thin journey", "--tasks", "T001,T002",
        "--files", files, "--actor", "agent:developer",
    )
    _flow(
        target, "units", "checkpoint", "walking-skeleton", "--actor", "agent:developer", expected=1,
    )
    _flow(target, "verify", "propose", "--actor", "agent:developer", "--", "python", "check.py")
    _flow(target, "verify", "approve", "--actor", "agent:developer", expected=1)
    _flow(target, "verify", "approve", "--actor", "human:fixture")
    _flow(target, "stage", "done", "walking-skeleton", "--actor", "agent:conductor")
    blocked = _flow(target, "stage", "start", "implement", "--actor", "agent:developer", expected=1)
    assert "must be decided" in blocked.stderr
    _flow(target, "sensors", "run", "walking-skeleton", "--actor", "agent:quality", expected=1)
    _flow(target, "gate", "approve", "walking-skeleton", "--actor", "human:fixture", expected=1)
    _flow(target, "units", "checkpoint", "walking-skeleton", "--actor", "agent:developer")
    _flow(target, "sensors", "run", "walking-skeleton", "--actor", "agent:quality")
    report.write_text(
        report.read_text(encoding="utf-8") + "\nReviewed limitations.\n", encoding="utf-8",
    )
    stale = _flow(
        target, "gate", "approve", "walking-skeleton", "--actor", "human:fixture", expected=1,
    )
    assert "stale" in stale.stderr
    _flow(target, "sensors", "run", "walking-skeleton", "--actor", "agent:quality", expected=1)
    _flow(target, "units", "checkpoint", "walking-skeleton", "--actor", "agent:developer")
    _flow(target, "sensors", "run", "walking-skeleton", "--actor", "agent:quality")
    agent = _flow(
        target, "gate", "approve", "walking-skeleton", "--actor", "agent:conductor", expected=1,
    )
    assert "only a human" in agent.stderr
    _flow(target, "gate", "approve", "walking-skeleton", "--actor", "human:fixture")
    _flow(target, "stage", "start", "implement", "--actor", "agent:developer")
    before = json.loads((feature / "units.json").read_text())["checkpoints"]["walking-skeleton"]
    _flow(
        target, "units", "add", "expand", "Remaining work", "--depends-on", "walking-skeleton",
        "--actor", "agent:developer",
    )
    after = json.loads((feature / "units.json").read_text())["checkpoints"]["walking-skeleton"]
    assert after == before
    _flow(target, "resume")
    state = json.loads((feature / "state.json").read_text())
    assert state["stages"]["walking-skeleton"]["status"] == "done"
    assert state["stages"]["implement"]["status"] == "in_progress"


def test_portable_operational_readiness_lifecycle(tmp_path: Path) -> None:
    target = tmp_path / "reading-list-release"
    target.mkdir()
    installed = _run(BOOTSTRAP, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert (target / ".github" / "skills" / "speckit-readiness" / "SKILL.md").is_file()
    plugin_file = target / ".specify" / "plugins" / "operational-readiness" / "plugin.json"
    plugin = json.loads(plugin_file.read_text(encoding="utf-8"))
    assert plugin["enabled"] is False
    plugin["enabled"] = True
    plugin_file.write_text(json.dumps(plugin), encoding="utf-8")
    _flow(target, "plugins", "validate")
    _flow(target, "doctor")
    assignments = _flow(target, "agents", "assign", "--profile", "release-ready").stdout
    assert "lead=pipeline-deploy" in assignments and "lead=operations" in assignments
    assert "aws-platform" not in assignments and "support=compliance" not in assignments
    assert len(json.loads(_flow(target, "stages", "--json").stdout)["stages"]) == 9

    pointer = json.loads((target / ".specify" / "feature.json").read_text())
    feature = target / pointer["feature_directory"]
    feature.mkdir(parents=True)
    _flow(target, "init", "--profile", "release-ready", "--actor", "agent:product")
    artifacts = {
        "specify": ("spec.md", "# Reading list\n\n- FR-001: List books.\n"),
        "plan": ("plan.md", "# Design\n\nA local reading list.\n"),
        "tasks": ("tasks.md", "# Tasks\n\n- [X] T001 Test listing (FR-001)\n"),
    }
    for stage in ("specify", "plan", "tasks", "implement", "deploy", "operate"):
        _flow(target, "stage", "start", stage, "--actor", "agent:conductor")
        if stage in artifacts:
            name, content = artifacts[stage]
            (feature / name).write_text(content, encoding="utf-8")
        _flow(target, "stage", "done", stage, "--actor", "agent:conductor")
        if stage == "tasks":
            continue
        if stage in ("deploy", "operate"):
            # Fixture-only synthetic evidence and human decisions are user-authorized.
            if stage == "deploy":
                _flow(target, "sensors", "run", stage, "--actor", "agent:quality", expected=1)
                blocked = _flow(
                    target, "gate", "approve", stage, "--actor", "human:fixture", expected=1,
                )
                assert "operational-readiness" in blocked.stderr
                sections = {
                    "release.md": (
                        "Ownership and target", "Configuration", "Verification",
                        "Rollout", "Rollback",
                    ),
                    "runbook.md": (
                        "Ownership", "Health signals", "Alerts", "Incidents",
                        "Rollback", "Feedback",
                    ),
                }
                for name, headings in sections.items():
                    (feature / name).write_text(
                        "# Fixture evidence only\n\n" + "\n\n".join(
                            f"## {heading}\n\nProcedure reviewed by fixture release owner.\n"
                            "- Evidence: synthetic review record rev abc123; no live checks run."
                            for heading in headings
                        ), encoding="utf-8",
                    )
            _flow(target, "sensors", "run", stage, "--actor", "agent:quality")
            changed = feature / ("release.md" if stage == "deploy" else "runbook.md")
            changed.write_text(
                changed.read_text(encoding="utf-8") + "\nEvidence revision changed.\n",
                encoding="utf-8",
            )
            blocked = _flow(
                target, "gate", "approve", stage, "--actor", "human:fixture", expected=1,
            )
            assert "stale" in blocked.stderr
        _flow(target, "sensors", "run", stage, "--actor", "agent:quality")
        agent = _flow(
            target, "gate", "approve", stage, "--actor", "agent:conductor", expected=1,
        )
        assert "only a human" in agent.stderr
        _flow(target, "gate", "approve", stage, "--actor", "human:fixture")

    _flow(target, "resume")
    _flow(target, "doctor")
    final = json.loads((feature / "state.json").read_text(encoding="utf-8"))
    assert final["current_stage"] is None and final["pending_gate"] is None
    events = [
        json.loads(line) for line in (feature / "audit.jsonl").read_text().splitlines()
    ]
    for stage in ("deploy", "operate"):
        approved = [
            event for event in events
            if event["type"] == "gate_approved" and event["stage"] == stage
        ]
        assert len(approved) == 1
        assert "operational-readiness" in approved[0]["detail"]
    assert not (target / ".specify" / "verify.json").exists()


@pytest.mark.parametrize("existing", [False, True])
def test_portable_codebase_analysis_route(tmp_path: Path, existing: bool) -> None:
    target = tmp_path / "reading-list"
    target.mkdir()
    installed = _run(BOOTSTRAP, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert (target / ".github" / "skills" / "speckit-codebase" / "SKILL.md").is_file()
    empty = json.loads(_flow(target, "codebase", "scan", "--json").stdout)
    assert empty["existing"] is False

    plugin_file = target / ".specify" / "plugins" / "codebase-analysis" / "plugin.json"
    plugin = json.loads(plugin_file.read_text(encoding="utf-8"))
    assert plugin["enabled"] is False
    plugin["enabled"] = True
    plugin_file.write_text(json.dumps(plugin), encoding="utf-8")
    _flow(target, "plugins", "validate")
    _flow(target, "doctor")
    profiles = json.loads(_flow(target, "profiles", "list", "--json").stdout)
    route = profiles["brownfield"]
    assert route["stages"].index("specify") < route["stages"].index("codebase-analysis")
    assert route["stages"].index("codebase-analysis") < route["stages"].index("plan")
    assignments = _flow(target, "agents", "assign", "--profile", "brownfield")
    assert "codebase-analysis lead=architect" in assignments.stdout

    if existing:
        (target / "app.py").write_text("raise RuntimeError('must not execute')\n", encoding="utf-8")
    pointer = json.loads((target / ".specify" / "feature.json").read_text())
    feature = target / pointer["feature_directory"]
    feature.mkdir(parents=True)
    _flow(target, "init", "--profile", "brownfield", "--actor", "agent:product")
    _flow(target, "stage", "start", "specify", "--actor", "agent:product")
    (feature / "spec.md").write_text("# Reading list\n\n- FR-001: List books.\n", encoding="utf-8")
    _flow(target, "stage", "done", "specify", "--actor", "agent:product")
    blocked = _flow(
        target, "stage", "start", "codebase-analysis", "--actor", "agent:conductor", expected=1,
    )
    assert "must be decided" in blocked.stderr
    _flow(target, "sensors", "run", "specify", "--actor", "agent:quality")
    _flow(target, "gate", "approve", "specify", "--actor", "human:fixture")
    result = json.loads(_flow(
        target, "stage", "start", "codebase-analysis", "--actor", "agent:conductor", "--json",
    ).stdout)
    assert result["stages"]["codebase-analysis"] == ("in_progress" if existing else "skipped")
    events = [json.loads(line) for line in (feature / "audit.jsonl").read_text().splitlines()]
    assert events[-1]["type"] == ("stage_started" if existing else "stage_skipped")
    if existing:
        _flow(target, "stage", "done", "codebase-analysis", "--actor", "agent:conductor")
    else:
        _flow(
            target, "stage", "done", "codebase-analysis", "--actor", "agent:conductor", expected=1,
        )
    _flow(target, "stage", "start", "clarify", "--actor", "agent:product")
    _flow(target, "resume")


def test_enabled_generic_plugin_is_usable_in_target(tmp_path: Path) -> None:
    target = tmp_path / "sample-project"
    target.mkdir()
    installed = _run(BOOTSTRAP, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr

    plugin_file = target / ".specify" / "plugins" / "aidlc-extras" / "plugin.json"
    plugin = json.loads(plugin_file.read_text(encoding="utf-8"))
    plugin["enabled"] = True
    plugin_file.write_text(json.dumps(plugin), encoding="utf-8")

    env = {**os.environ, "PYTHONPATH": str(target)}
    stages = subprocess.run(
        [sys.executable, "-m", "speckit_flow", "stages"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert stages.returncode == 0, stages.stdout + stages.stderr
    assert "nfr-design" in stages.stdout
    doctor = subprocess.run(
        [sys.executable, "-m", "speckit_flow", "doctor"],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr


def test_portable_stage_contracts_support_project_owned_stages(tmp_path: Path) -> None:
    target = tmp_path / "reading-list-contracts"
    target.mkdir()
    installed = _run(BOOTSTRAP, target, "install")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert (target / "speckit_flow" / "contracts.py").is_file()
    assert (target / ".github" / "skills" / "speckit-contracts" / "SKILL.md").is_file()
    plugin_file = target / ".specify" / "plugins" / "stage-contracts" / "plugin.json"
    plugin = json.loads(plugin_file.read_text(encoding="utf-8"))
    assert plugin["enabled"] is False
    hidden = _flow(target, "profiles", "list", "--json")
    assert "contract-driven" not in json.loads(hidden.stdout)

    plugin["enabled"] = True
    plugin_file.write_text(json.dumps(plugin), encoding="utf-8")
    custom = target / ".specify" / "custom"
    custom.mkdir(parents=True, exist_ok=True)
    (custom / "stages.json").write_text(
        json.dumps(
            {
                "stages": [
                    {
                        "id": "project-check",
                        "phase": "construction",
                        "optional": True,
                        "after": "tasks",
                        "lead": "developer",
                        "description": "Project-specific review stage",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    profiles_dir = custom / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "project-workflow.json").write_text(
        json.dumps(
            {
                "id": "project-workflow",
                "description": "Reading-list workflow with a project review stage",
                "stages": ["specify", "plan", "tasks", "project-check", "implement"],
                "depth": "standard",
                "gates": ["specify", "plan"],
                "stage_contracts": True,
            }
        ),
        encoding="utf-8",
    )
    (custom / "stage-contracts.json").write_text(
        json.dumps(
            {
                "version": 1,
                "contracts": [
                    {
                        "stage": "project-check",
                        "purpose": "Review the reading-list integration boundary.",
                        "inputs": [
                            {"id": "tasks", "description": "Approved implementation tasks."}
                        ],
                        "outputs": [
                            {
                                "id": "review",
                                "description": "Project-specific review notes.",
                                "required": True,
                            }
                        ],
                        "acceptance_criteria": [
                            "Project-specific boundary decisions are recorded."
                        ],
                        "review_focus": ["Reading-list data handling"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _flow(target, "plugins", "validate")
    _flow(target, "profiles", "validate")
    shown = json.loads(_flow(target, "contracts", "show", "project-check", "--json").stdout)
    assert shown["contracts"][0]["purpose"] == (
        "Review the reading-list integration boundary."
    )

    pointer = json.loads((target / ".specify" / "feature.json").read_text(encoding="utf-8"))
    feature = target / pointer["feature_directory"]
    feature.mkdir(parents=True)
    _flow(target, "init", "--profile", "project-workflow", "--actor", "human:fixture")
    for stage, filenames in (
        ("specify", ("spec.md",)),
        ("plan", ("plan.md", "research.md", "data-model.md", "quickstart.md")),
    ):
        _flow(target, "stage", "start", stage, "--actor", "agent:developer")
        for filename in filenames:
            (feature / filename).write_text(f"# {filename}\nContent\n", encoding="utf-8")
        _flow(target, "stage", "done", stage, "--actor", "agent:developer")
        _flow(target, "sensors", "run", stage, "--actor", "agent:quality")
        _flow(target, "gate", "approve", stage, "--actor", "human:fixture")
