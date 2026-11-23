"""Tests for ``scripts/speckit_package.py`` and the packaged snapshot verifier.

Feature 039 (standalone speckit-flow portable package). Convention per decision
D-B: tests copy the real ``scripts/speckit_package.py``,
``scripts/speckit_bootstrap.py`` and ``scripts/portable-package/verify_snapshot.py``
into a pytest tmp fixture tree and exercise them by subprocess, exactly like
``tests/unit/test_speckit_bootstrap.py``. No test touches any real external
destination.

detect-secrets (pinned ``>=1.5.0`` in ``requirements-dev.txt``) is a HARD
requirement for the screen-dependent tests (T011/T013): there is no ``skipif``
on scanner availability — a missing scanner must fail the suite, otherwise the
secret-screen gate is vacuously green (T003).
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import warnings
from pathlib import Path, PurePosixPath
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PACKAGER_SOURCE = ROOT / "scripts" / "speckit_package.py"
BOOTSTRAP_SOURCE = ROOT / "scripts" / "speckit_bootstrap.py"
VERIFIER_SOURCE = ROOT / "scripts" / "portable-package" / "verify_snapshot.py"
README_SOURCE = ROOT / "scripts" / "portable-package" / "README.md"

# Secret-literal convention (tasks.md): the canary value is always constructed at
# runtime from concatenated parts, never written as one contiguous literal,
# because scripts/check_secrets.py scans tests/ and specs/. The same constant is
# documented in specs/039-standalone-speckit-flow-package/quickstart.md section F.
CANARY_LABEL = "aws_access_key_id"
CANARY_VALUE = "AKIA" + "IOSFODNN7EXAMPLE"

HEX64 = re.compile(r"[a-f0-9]{64}")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)$")

FIXTURE_CLOSURE = {
    "payload/shared.txt",
    "plugins/demo-pack/plugin.json",
    "seeds/defaults.json",
    "scripts/speckit_bootstrap.py",
    "scripts/speckit-portable-bundle.json",
    "README.md",
    "verify_snapshot.py",
}


def _run(
    script: Path,
    *args: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=cwd,
        env=env,
    )


def _env(**extra: str) -> dict[str, str]:
    return {**os.environ, **extra}


def _import_scripts_module(name: str, directory: Path) -> ModuleType:
    path = str(directory)
    if path not in sys.path:
        sys.path.insert(0, path)
    return importlib.import_module(name)


def _tree_state(root: Path) -> dict[str, str]:
    state: dict[str, str] = {}
    for base, _dirs, names in os.walk(root):
        for name in names:
            file_path = Path(base) / name
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            state[file_path.relative_to(root).as_posix()] = digest
    return state


def _make_package_fixture(tmp_path: Path, *, real_readme: bool = False) -> Path:
    """Decision D-B fixture: copies of the real scripts inside a synthetic tree."""
    fixture = tmp_path / "fixture-source"
    scripts = fixture / "scripts"
    portable = scripts / "portable-package"
    portable.mkdir(parents=True)
    shutil.copyfile(PACKAGER_SOURCE, scripts / "speckit_package.py")
    shutil.copyfile(BOOTSTRAP_SOURCE, scripts / "speckit_bootstrap.py")
    shutil.copyfile(VERIFIER_SOURCE, portable / "verify_snapshot.py")
    if real_readme:
        shutil.copyfile(README_SOURCE, portable / "README.md")
    else:
        (portable / "README.md").write_bytes(
            b"# Synthetic fixture package README\n\nSynthetic content for tests only.\n"
        )
    payload = fixture / "payload"
    payload.mkdir()
    (payload / "shared.txt").write_bytes(b"shared content v1\n")
    plugin_dir = fixture / "plugins" / "demo-pack"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_bytes(b'{\n  "id": "demo-pack",\n  "enabled": true\n}\n')
    seeds = fixture / "seeds"
    seeds.mkdir()
    (seeds / "defaults.json").write_bytes(b'{"seed": "v1"}\n')
    bundle = {
        "bundle_version": "fixture-1.0",
        "files": [
            {
                "source": "payload",
                "destination": "shared",
                "category": "engine",
                "include": ["shared.txt"],
            },
            {
                "source": "plugins/demo-pack/plugin.json",
                "destination": "plugin-packs/demo-pack/plugin.json",
                "category": "plugins",
            },
            {
                "source": "seeds/defaults.json",
                "destination": "config/defaults.json",
                "category": "configuration",
                "seed": True,
            },
        ],
    }
    (scripts / "speckit-portable-bundle.json").write_text(
        json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
    )
    return fixture


def _packager(fixture: Path) -> Path:
    return fixture / "scripts" / "speckit_package.py"


def _review_dir(fixture: Path) -> Path:
    """Reviewed inventories live outside tmp_path so tree-state checks are unaffected."""
    review = fixture.parent.parent / f"{fixture.parent.name}-reviewed"
    review.mkdir(exist_ok=True)
    return review


def _save_inventory(
    fixture: Path, label: str = "fixture-snap"
) -> tuple[subprocess.CompletedProcess[str], Path, str]:
    """Run ``inventory --output`` and return (result, reviewed file, approved digest)."""
    review = _review_dir(fixture)
    output = review / f"inventory-{len(list(review.iterdir()))}.json"
    result = _run(
        _packager(fixture),
        "inventory",
        "--label",
        label,
        "--captured-by",
        "pytest-harness",
        "--output",
        str(output),
    )
    digest = hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else ""
    return result, output, digest


def _assemble(
    fixture: Path,
    dest: Path | str,
    *extra: str,
    label: str = "fixture-snap",
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    reviewed: tuple[Path, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Assemble from a reviewed inventory; by default one is captured just before."""
    if reviewed is None:
        inventory_result, inventory_path, digest = _save_inventory(fixture, label)
        if inventory_result.returncode != 0:
            return inventory_result
        reviewed = (inventory_path, digest)
    return _run(
        _packager(fixture),
        "assemble",
        "--dest",
        str(dest),
        "--inventory",
        str(reviewed[0]),
        "--inventory-sha256",
        reviewed[1],
        *extra,
        env=env,
        cwd=cwd,
    )


def _inventory(
    fixture: Path, *extra: str, label: str = "fixture-snap"
) -> subprocess.CompletedProcess[str]:
    return _run(
        _packager(fixture),
        "inventory",
        "--label",
        label,
        "--captured-by",
        "pytest-harness",
        *extra,
    )


# ---------------------------------------------------------------------------
# T006 — import-surface pin for the frozen speckit_bootstrap helpers
# ---------------------------------------------------------------------------


def test_import_surface_pins_bootstrap_helpers() -> None:
    bootstrap = _import_scripts_module("speckit_bootstrap", ROOT / "scripts")
    for helper in ("_sha256", "_relative_path", "_resolve_within", "_atomic_write"):
        assert callable(getattr(bootstrap, helper)), helper
    empty_digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert bootstrap._sha256(b"") == empty_digest
    for bad in ("../x", "a\\b"):
        try:
            bootstrap._relative_path(bad, "test")
        except ValueError:
            pass
        else:
            raise AssertionError(f"_relative_path accepted {bad!r}")
    try:
        bootstrap._resolve_within(ROOT, bootstrap._relative_path("scripts", "t"), "t")
    except ValueError:
        raise AssertionError("_resolve_within rejected a contained path") from None
    escaping = PurePosixPath("..") / ".."
    try:
        bootstrap._resolve_within(ROOT, escaping, "t")
    except ValueError:
        pass
    else:
        raise AssertionError("_resolve_within accepted an escaping path")
    parameters = list(inspect.signature(bootstrap._atomic_write).parameters)
    assert parameters == ["path", "content"]


# ---------------------------------------------------------------------------
# T007–T019 — User Story 1 acceptance/regression tests (subprocess, fixture)
# ---------------------------------------------------------------------------


def test_inventory_prints_valid_snapshot_and_writes_nothing(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    before = _tree_state(tmp_path)

    result = _inventory(fixture)

    assert result.returncode == 0, result.stdout + result.stderr
    document = json.loads(result.stdout)
    assert document["schema_version"] == 1
    snapshot = document["snapshot"]
    assert snapshot["label"] == "fixture-snap"
    assert snapshot["captured_by"] == "pytest-harness"
    assert snapshot["bundle_version"] == "fixture-1.0"
    assert snapshot["digest_algorithm"] == "sha256"
    assert TIMESTAMP.fullmatch(snapshot["captured_at"]), snapshot["captured_at"]
    reference = snapshot["source_reference"]
    for field in ("repository", "branch", "commit"):
        assert isinstance(reference[field], str) and reference[field]
    files = document["files"]
    paths = [entry["path"] for entry in files]
    assert paths == sorted(paths)
    assert set(paths) == FIXTURE_CLOSURE
    for entry in files:
        assert HEX64.fullmatch(entry["sha256"]), entry
        assert isinstance(entry["bytes"], int) and entry["bytes"] >= 0
        assert entry["origin"] in {"source", "package-doc"}
        if entry["origin"] == "package-doc":
            assert entry["source_path"].startswith("scripts/portable-package/")
        else:
            assert "source_path" not in entry
    assert str(len(files)) in result.stderr
    document_digest = hashlib.sha256(result.stdout.encode("utf-8")).hexdigest()
    assert document_digest in result.stderr
    assert _tree_state(tmp_path) == before


def test_assemble_refusals_exit_2_zero_writes(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)

    # non-empty destination
    occupied = tmp_path / "occupied-dest"
    occupied.mkdir()
    (occupied / "existing.txt").write_bytes(b"keep\n")
    before = _tree_state(tmp_path)
    result = _assemble(fixture, occupied)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "CONFLICT" in result.stdout + result.stderr
    assert _tree_state(tmp_path) == before

    # destination inside the fixture source root
    result = _assemble(fixture, fixture / "sub")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "overlap" in (result.stdout + result.stderr).lower()
    assert _tree_state(tmp_path) == before

    # fixture source root inside the destination
    result = _assemble(fixture, tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "overlap" in (result.stdout + result.stderr).lower()
    assert _tree_state(tmp_path) == before

    # destination exists as a regular file
    dest_file = tmp_path / "dest-as-file"
    dest_file.write_bytes(b"file\n")
    before = _tree_state(tmp_path)
    result = _assemble(fixture, dest_file)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "CONFLICT" in result.stdout + result.stderr
    assert _tree_state(tmp_path) == before

    # non-absolute raw destination (covers the drive-relative C:foo gap)
    result = _assemble(fixture, "relative-dest", cwd=tmp_path)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "CONFLICT" in result.stdout + result.stderr
    assert not (tmp_path / "relative-dest").exists()

    # destination exists as a symlink (leg skipped only without symlink privilege)
    link_target = tmp_path / "link-target"
    link_target.mkdir()
    link = tmp_path / "dest-as-symlink"
    try:
        link.symlink_to(link_target, target_is_directory=True)
    except OSError as exc:  # Windows without symlink privilege
        warnings.warn(f"symlink refusal leg SKIPPED (no symlink privilege): {exc}", stacklevel=1)
    else:
        before = _tree_state(tmp_path)
        result = _assemble(fixture, link)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "CONFLICT" in result.stdout + result.stderr
        assert _tree_state(tmp_path) == before


def test_assemble_dry_run_creates_nothing(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "dry-dest"
    before = _tree_state(tmp_path)

    result = _assemble(fixture, dest, "--dry-run")

    assert result.returncode == 0, result.stdout + result.stderr
    created = {
        line.split(" ", 1)[1] for line in result.stdout.splitlines() if line.startswith("CREATE ")
    }
    assert created == FIXTURE_CLOSURE
    assert "fixture-snap" in result.stdout
    assert not dest.exists()
    assert _tree_state(tmp_path) == before


def test_capture_is_byte_verbatim_including_plugin_json(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    modified = b"locally modified, uncommitted change\r\nsecond line, CRLF preserved\r\n"
    (fixture / "payload" / "shared.txt").write_bytes(modified)
    dest = tmp_path / "package-dest"

    result = _assemble(fixture, dest)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (dest / "payload" / "shared.txt").read_bytes() == modified
    source_plugin = (fixture / "plugins" / "demo-pack" / "plugin.json").read_bytes()
    packaged_plugin = (dest / "plugins" / "demo-pack" / "plugin.json").read_bytes()
    assert packaged_plugin == source_plugin
    assert b'"enabled": true' in packaged_plugin


def test_assemble_success_then_verifier_passes_without_source(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"

    result = _assemble(fixture, dest)

    assert result.returncode == 0, result.stdout + result.stderr
    inventory_bytes = (dest / "SNAPSHOT.json").read_bytes()
    assert not inventory_bytes.startswith(b"\xef\xbb\xbf")  # no BOM
    assert b"\r" not in inventory_bytes  # LF only
    assert inventory_bytes.endswith(b"\n") and not inventory_bytes.endswith(b"\n\n")
    document = json.loads(inventory_bytes.decode("utf-8"))
    paths = [entry["path"] for entry in document["files"]]
    assert paths == sorted(paths)
    digest = hashlib.sha256(inventory_bytes).hexdigest()
    marker = (dest / "SNAPSHOT.json.sha256").read_bytes()
    assert marker == f"{digest}  SNAPSHOT.json\n".encode("ascii")
    assert digest in result.stdout
    match = re.search(r"screen submitted (\d+) paths", result.stdout)
    assert match, result.stdout
    assert int(match.group(1)) == len(document["files"]) + 1
    assert "assemble complete: snapshot fixture-snap" in result.stdout

    # receiving side: source tree renamed away, cwd unrelated
    fixture.rename(tmp_path / "renamed-away-source")
    unrelated = tmp_path / "unrelated-cwd"
    unrelated.mkdir()
    verify = _run(dest / "verify_snapshot.py", cwd=unrelated)
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert f"OK {len(document['files'])} files verified" in verify.stdout
    assert "fixture-snap intact" in verify.stdout


def test_verifier_drift_missing_marker_and_unlisted_file(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    assert _assemble(fixture, dest).returncode == 0

    # (a) digest mismatch on a packaged file
    shared = dest / "payload" / "shared.txt"
    original = shared.read_bytes()
    shared.write_bytes(original + b"tampered\n")
    verify = _run(dest / "verify_snapshot.py")
    assert verify.returncode == 1, verify.stdout + verify.stderr
    assert "DRIFT payload/shared.txt (digest mismatch)" in verify.stdout
    assert "must not be treated as snapshot" in verify.stdout
    shared.write_bytes(original)

    # (b) completion marker missing
    marker = dest / "SNAPSHOT.json.sha256"
    marker_bytes = marker.read_bytes()
    marker.unlink()
    verify = _run(dest / "verify_snapshot.py")
    assert verify.returncode == 1, verify.stdout + verify.stderr
    assert "assembly never completed" in verify.stdout
    marker.write_bytes(marker_bytes)

    # (b2) completion marker content mismatch
    marker.write_bytes(b"0" * 64 + b"  SNAPSHOT.json\n")
    verify = _run(dest / "verify_snapshot.py")
    assert verify.returncode == 1, verify.stdout + verify.stderr
    assert "DRIFT SNAPSHOT.json.sha256 (digest mismatch)" in verify.stdout
    marker.write_bytes(marker_bytes)

    # (c) unlisted file
    extra = dest / "extra.txt"
    extra.write_bytes(b"unlisted\n")
    verify = _run(dest / "verify_snapshot.py")
    assert verify.returncode == 1, verify.stdout + verify.stderr
    assert "DRIFT extra.txt (unlisted file)" in verify.stdout
    extra.unlink()

    # sanity: intact again
    assert _run(dest / "verify_snapshot.py").returncode == 0

    # exit-2 legs: corrupted then missing inventory (quality gap G5)
    snapshot = dest / "SNAPSHOT.json"
    snapshot.write_bytes(b"not valid json\n")
    verify = _run(dest / "verify_snapshot.py")
    assert verify.returncode == 2, verify.stdout + verify.stderr
    assert "ERROR" in verify.stdout + verify.stderr
    snapshot.unlink()
    verify = _run(dest / "verify_snapshot.py")
    assert verify.returncode == 2, verify.stdout + verify.stderr
    assert "ERROR" in verify.stdout + verify.stderr


def test_planted_secret_blocks_marker_and_rerun(tmp_path: Path) -> None:
    """Findings 1+5 positive control: a planted synthetic secret fails the gate."""
    fixture = _make_package_fixture(tmp_path)
    planted = f'{CANARY_LABEL} = "{CANARY_VALUE}"\n'.encode("ascii")
    (fixture / "payload" / "shared.txt").write_bytes(planted)
    dest = tmp_path / "package-dest"

    result = _assemble(fixture, dest)

    assert result.returncode == 1, result.stdout + result.stderr
    output = result.stdout + result.stderr
    assert "screen" in output.lower()
    # the finding line itself names the planted file, line and detector type
    assert re.search(r"payload/shared\.txt:\d+ \(AWS Access Key\)", output), output
    assert CANARY_VALUE not in output  # locations only, never secret content
    assert "must not be treated as snapshot fixture-snap" in output
    assert not (dest / "SNAPSHOT.json.sha256").exists()  # marker withheld
    assert (dest / "SNAPSHOT.json").is_file()  # written before the screen
    assert (dest / "payload" / "shared.txt").read_bytes() == planted  # nothing deleted

    rerun = _assemble(fixture, dest)
    assert rerun.returncode == 2, rerun.stdout + rerun.stderr
    assert "CONFLICT" in rerun.stdout + rerun.stderr


def test_scan_findings_parsed_from_baseline_json() -> None:
    """Finding 1: findings come from the emitted baseline JSON ``results``, never
    the exit code — detect-secrets exits 0 even with findings. In-repo precedent:
    ``scripts/check_secrets.py`` lines 37-40 parse ``report.get("results")``.
    Every malformed-output branch fails closed.
    """
    packager = _import_scripts_module("speckit_package", ROOT / "scripts")
    finding_report = json.dumps(
        {"results": {"x.txt": [{"type": "AWS Access Key"}]}, "plugins_used": []}
    )
    ok, _detail = packager._screen_verdict(0, finding_report)
    assert ok is False  # returncode 0 + non-empty results => gate fails
    ok, _detail = packager._screen_verdict(
        0, json.dumps({"results": {}, "plugins_used": [{"name": "AWSKeyDetector"}]})
    )
    assert ok is True
    for returncode, stdout in [
        (0, ""),  # empty stdout
        (0, "   "),
        (0, "not json"),  # parse error
        (0, json.dumps({"results": []})),  # non-dict results
        (0, json.dumps([])),  # non-dict report
        (0, json.dumps({})),  # missing results
        (0, json.dumps({"results": {}})),  # plugins_used absent: schema drift fails closed
        (0, json.dumps({"results": {}, "plugins_used": []})),  # no plugins ran: fails closed
        (1, json.dumps({"results": {}, "plugins_used": [{"name": "x"}]})),  # non-zero return
    ]:
        ok, _detail = packager._screen_verdict(returncode, stdout)
        assert ok is False, (returncode, stdout)

    malformed_reports = [
        '{"results":{},"results":{"unexpected.txt":[]},"plugins_used":[{"name":"x"}]}',
        '{"results":{"x.txt":[]},"plugins_used":[{"name":"x","name":"y"}]}',
        json.dumps({"results": {}, "plugins_used": [None]}),
        json.dumps({"results": {"x.txt": [None]}, "plugins_used": [{"name": "x"}]}),
        json.dumps(
            {
                "results": {"x.txt": [{"type": "AWS Access Key"}]},
                "plugins_used": [{"name": "x"}],
            }
        ),
        json.dumps(
            {
                "results": {"x.txt": [{"type": "x", "line_number": True}]},
                "plugins_used": [{"name": "x"}],
            }
        ),
    ]
    for stdout in malformed_reports:
        ok, detail = packager._screen_verdict(0, stdout)
        assert ok is False, (stdout, detail)


def test_scan_coverage_assertion() -> None:
    """Finding 3: submitted >= inventory + 1 (the +1 is SNAPSHOT.json)."""
    packager = _import_scripts_module("speckit_package", ROOT / "scripts")
    assert packager._assert_coverage(0, 0) is False
    assert packager._assert_coverage(5, 5) is False  # submitted < inventory + 1
    assert packager._assert_coverage(6, 5) is True  # == inventory + 1
    assert packager._assert_coverage(7, 5) is True  # > inventory + 1 (contract: >=)
    assert packager._assert_coverage(1, 0) is True


def test_scanner_missing_fails_closed_label_withheld(tmp_path: Path) -> None:
    """Quality gap 2: scanner unavailability fails the gate (never exit 0)."""
    packager = _import_scripts_module("speckit_package", ROOT / "scripts")
    argv = packager._scan_argv(["a.txt", "-leading-dash.json"])
    assert argv[0] == sys.executable
    assert argv[1:4] == ["-m", "detect_secrets", "scan"]
    assert "--all-files" in argv and "--force-use-all-plugins" in argv
    assert "a.txt" in argv
    assert "./-leading-dash.json" in argv  # argv-injection defense
    assert "-leading-dash.json" not in argv

    screen_dir = tmp_path / "screen-dest"
    screen_dir.mkdir()
    (screen_dir / "a.txt").write_bytes(b"plain\n")
    ok, submitted, detail = packager._run_screen(
        screen_dir, ["a.txt"], 0, module="speckit_no_such_module_123"
    )
    assert ok is False
    assert submitted == 1
    assert detail

    # E2E leg (decision D-B compliant: no CLI flags): shadow detect_secrets via
    # PYTHONPATH so the real subprocess scanner fails at import — assembly must
    # fail closed with exit 1, label withheld, marker absent, nothing deleted.
    shadow = tmp_path / "shadow-site"
    shadow.mkdir()
    (shadow / "detect_secrets.py").write_text(
        'raise ImportError("detect-secrets unavailable (test shadow)")\n', encoding="utf-8"
    )
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    result = _assemble(fixture, dest, env=_env(PYTHONPATH=str(shadow)))
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "screen" in output.lower()
    assert "must not be treated as snapshot fixture-snap" in output
    assert "assemble complete" not in output  # label withheld
    assert (dest / "SNAPSHOT.json").is_file()  # written before the screen, not deleted
    assert not (dest / "SNAPSHOT.json.sha256").exists()  # marker absent


def test_marker_last_ordering_via_fault_injection(tmp_path: Path) -> None:
    """Finding 2 / decision D-A: SPECKIT_PACKAGE_FAULT=corrupt-after-inventory."""
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"

    result = _assemble(fixture, dest, env=_env(SPECKIT_PACKAGE_FAULT="corrupt-after-inventory"))
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "SPECKIT_PACKAGE_FAULT" in output  # unmistakable ERROR line names the env var
    assert "DRIFT" in output and "digest mismatch" in output
    assert "must not be treated as snapshot" in output
    assert not (dest / "SNAPSHOT.json.sha256").exists()  # marker absent when hook fired
    assert (dest / "SNAPSHOT.json").is_file()  # nothing deleted

    rerun = _assemble(fixture, dest)  # fault unset: partial destination refused
    assert rerun.returncode == 2, rerun.stdout + rerun.stderr
    assert "CONFLICT" in rerun.stdout + rerun.stderr

    bogus_dest = tmp_path / "bogus-dest"
    bogus = _assemble(fixture, bogus_dest, env=_env(SPECKIT_PACKAGE_FAULT="bogus-value"))
    assert bogus.returncode == 2, bogus.stdout + bogus.stderr
    assert "SPECKIT_PACKAGE_FAULT" in bogus.stdout + bogus.stderr
    assert not bogus_dest.exists()

    clean_dest = tmp_path / "clean-dest"
    clean = _assemble(fixture, clean_dest, env=_env(SPECKIT_PACKAGE_FAULT=""))
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert (clean_dest / "SNAPSHOT.json.sha256").is_file()


def test_label_and_captured_by_validation(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "never-created"

    bad_values = ["bad\tlabel", "bad\x07bell", "x" * 201]
    for value in bad_values:
        result = _assemble(fixture, dest, label=value)
        assert result.returncode == 2, (value, result.stderr)
        assert not dest.exists()  # exit 2 before any write

    for flag in ("--captured-by", "--source-ref"):
        result = _inventory(fixture, flag, "bad\x1fvalue")
        assert result.returncode == 2, (flag, result.stderr)
        assert "must be printable" in result.stderr
        assert not dest.exists()

    boundary = "x" * 200  # exactly 200 printable chars accepted
    result = _inventory(fixture, label=boundary)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["snapshot"]["label"] == boundary


def test_source_tree_untouched_by_assemble(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    before = _tree_state(fixture)

    result = _assemble(fixture, dest)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _tree_state(fixture) == before


def test_missing_closure_source_file_aborts_with_zero_writes(tmp_path: Path) -> None:
    """A manifest-listed source file deleted after approval aborts capture with
    ``ERROR <path> (<reason>)``, exit 2 and zero writes anywhere (T020)."""
    fixture = _make_package_fixture(tmp_path)
    (fixture / "payload" / "shared.txt").unlink()
    dest = tmp_path / "never-dest"
    before = _tree_state(tmp_path)

    result = _assemble(fixture, dest)
    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert "ERROR" in output
    assert "payload/shared.txt" in output
    assert not dest.exists()
    assert _tree_state(tmp_path) == before

    # inventory takes the same exit-2 path (contract section 1)
    result = _inventory(fixture)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "payload/shared.txt" in result.stdout + result.stderr
    assert _tree_state(tmp_path) == before


def test_manifest_destinations_are_validated_before_capture(tmp_path: Path) -> None:
    """Malformed destinations and expanded destination collisions fail closed."""
    fixture = _make_package_fixture(tmp_path)
    manifest_path = fixture / "scripts" / "speckit-portable-bundle.json"
    original = json.loads(manifest_path.read_text(encoding="utf-8"))
    invalid_bundles = []

    unsafe_destination = json.loads(json.dumps(original))
    unsafe_destination["files"][0]["destination"] = "../outside"
    invalid_bundles.append(unsafe_destination)

    missing_destination = json.loads(json.dumps(original))
    del missing_destination["files"][0]["destination"]
    invalid_bundles.append(missing_destination)

    expanded_collision = json.loads(json.dumps(original))
    # The first directory entry expands to shared/shared.txt; this file entry
    # targets its parent, which is an ancestor/descendant collision.
    expanded_collision["files"][1]["destination"] = "shared"
    invalid_bundles.append(expanded_collision)

    reserved_destination = json.loads(json.dumps(original))
    reserved_destination["files"][1]["destination"] = ".specify/feature.json"
    invalid_bundles.append(reserved_destination)

    dest = tmp_path / "never-created"
    for bundle in invalid_bundles:
        manifest_path.write_text(json.dumps(bundle), encoding="utf-8")
        result = _assemble(fixture, dest)
        output = result.stdout + result.stderr
        assert result.returncode == 2, output
        assert "speckit-portable-bundle.json" in output or "CONFLICT" in output
        assert not dest.exists()


def test_packager_destination_walk_error_fails_verification(tmp_path: Path) -> None:
    """An unreadable subtree reported by os.walk must not pass verification."""
    packager = _import_scripts_module("speckit_package", ROOT / "scripts")
    dest = tmp_path / "package-dest"
    dest.mkdir()
    inventory = b"inventory\n"
    (dest / "SNAPSHOT.json").write_bytes(inventory)

    def failed_walk(_path: Path, *, followlinks: bool = False, onerror: object = None) -> object:
        assert followlinks is False
        if callable(onerror):
            onerror(PermissionError("denied", str(dest / "private")))
        return iter([(str(dest), [], ["SNAPSHOT.json"])])

    with patch.object(packager.os, "walk", failed_walk):
        drift = packager._verify_destination(dest, [], inventory)

    assert any("directory walk failed" in item for item in drift), drift


def test_standalone_verifier_walk_error_fails_closed(tmp_path: Path, capsys: object) -> None:
    """The delivered verifier must fail when os.walk cannot inspect a subtree."""
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    assert _assemble(fixture, dest).returncode == 0
    verifier = _import_scripts_module("verify_snapshot", ROOT / "scripts" / "portable-package")

    def failed_walk(_path: Path, *, followlinks: bool = False, onerror: object = None) -> object:
        assert followlinks is False
        if callable(onerror):
            onerror(PermissionError("denied", str(dest / "private")))
        return iter([])

    with patch.object(verifier.os, "walk", failed_walk):
        result = verifier.main(["--package", str(dest)])

    output = capsys.readouterr().out
    assert result == 1, output
    assert "directory walk failed" in output


def test_screen_self_digest_suppression_scoped_to_inventory() -> None:
    """The only allowed screen suppression: a finding inside SNAPSHOT.json whose
    ``hashed_secret`` equals the SHA-1 of a machine-generated hex value the
    packager itself wrote there (per-file digest / commit reference). The same
    value in any other file, or an unknown value anywhere, still fails."""
    packager = _import_scripts_module("speckit_package", ROOT / "scripts")
    digest_value = hashlib.sha256(b"self-digest-suppression-probe").hexdigest()
    hashed = hashlib.sha1(digest_value.encode("utf-8")).hexdigest()
    allowed = frozenset({hashed})
    plugins = [{"name": "HexHighEntropyString"}]
    finding = {"type": "Hex High Entropy String", "line_number": 7, "hashed_secret": hashed}

    report = json.dumps({"results": {"SNAPSHOT.json": [finding]}, "plugins_used": plugins})
    ok, _detail = packager._screen_verdict(0, report, allowed)
    assert ok is True

    report = json.dumps({"results": {"other.txt": [finding]}, "plugins_used": plugins})
    ok, detail = packager._screen_verdict(0, report, allowed)
    assert ok is False and "other.txt" in detail

    unknown = dict(finding, hashed_secret="0" * 40)
    report = json.dumps({"results": {"SNAPSHOT.json": [unknown]}, "plugins_used": plugins})
    ok, detail = packager._screen_verdict(0, report, allowed)
    assert ok is False and "SNAPSHOT.json" in detail

    # without an allowlist nothing is suppressed
    report = json.dumps({"results": {"SNAPSHOT.json": [finding]}, "plugins_used": plugins})
    ok, _detail = packager._screen_verdict(0, report)
    assert ok is False


def test_verifier_rejects_unsafe_inventory_paths(tmp_path: Path) -> None:
    """SNAPSHOT.json is untrusted input: the standalone verifier re-implements
    the installer's path-safety rules and must refuse (exit 2) before joining
    any unsafe path to the package directory. The rejection cases mirror the
    packager-side pins in test_import_surface_pins_bootstrap_helpers (D4)."""
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    assert _assemble(fixture, dest).returncode == 0
    snapshot = dest / "SNAPSHOT.json"
    original = snapshot.read_bytes()
    unsafe = [
        "../escape.txt",
        "a\\b",
        "CON/x.txt",
        "nul.txt",
        "/absolute.txt",
        "a/../b",
        "a//b",
        "trailing. ",
        "SNAPSHOT.json",  # casefold collision with the reserved inventory name
        "snapshot.json.sha256",  # casefold collision with the reserved marker name
    ]
    for bad in unsafe:
        document = json.loads(original.decode("utf-8"))
        document["files"][0]["path"] = bad
        snapshot.write_bytes((json.dumps(document, indent=2) + "\n").encode("utf-8"))
        verify = _run(dest / "verify_snapshot.py")
        output = verify.stdout + verify.stderr
        assert verify.returncode == 2, (bad, output)
        assert "ERROR" in output, (bad, output)
    snapshot.write_bytes(original)
    assert _run(dest / "verify_snapshot.py").returncode == 0


def test_verifier_rejects_malformed_inventory_shapes(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    assert _assemble(fixture, dest).returncode == 0
    snapshot = dest / "SNAPSHOT.json"
    original = snapshot.read_bytes()
    malformed = [
        ((), "schema_version", True),
        ((), "unexpected", True),
        (("snapshot",), "unexpected", True),
        (("snapshot", "source_reference"), "unexpected", True),
        (("files", 0), "unexpected", True),
        (("files", 0), "origin", []),
        (("files", 0), "origin", {}),
    ]

    for path, key, value in malformed:
        document = json.loads(original.decode("utf-8"))
        target = document
        for component in path:
            target = target[component]
        target[key] = value
        mutated = (json.dumps(document) + "\n").encode("utf-8")
        snapshot.write_bytes(mutated)
        (dest / "SNAPSHOT.json.sha256").write_bytes(
            f"{hashlib.sha256(mutated).hexdigest()}  SNAPSHOT.json\n".encode("ascii")
        )
        verify = _run(dest / "verify_snapshot.py")
        output = verify.stdout + verify.stderr
        assert verify.returncode == 2, (path, key, output)
        assert "ERROR" in output, (path, key, output)
        assert "Traceback" not in output, (path, key, output)

    snapshot.write_bytes(original)
    (dest / "SNAPSHOT.json.sha256").write_bytes(
        f"{hashlib.sha256(original).hexdigest()}  SNAPSHOT.json\n".encode("ascii")
    )
    assert _run(dest / "verify_snapshot.py").returncode == 0


def test_verifier_rejects_duplicate_inventory_json_keys(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    assert _assemble(fixture, dest).returncode == 0

    snapshot = dest / "SNAPSHOT.json"
    original = snapshot.read_bytes()
    duplicated = original.replace(
        b'"schema_version": 1,',
        b'"schema_version": 1,\n  "schema_version": 1,',
        1,
    )
    assert duplicated != original
    snapshot.write_bytes(duplicated)

    verify = _run(dest / "verify_snapshot.py")

    output = verify.stdout + verify.stderr
    assert verify.returncode == 2, output
    assert "ERROR" in output
    assert "duplicate JSON object key: schema_version" in output
    assert "Traceback" not in output


def test_verifier_rejects_unsorted_inventory_files(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    assert _assemble(fixture, dest).returncode == 0

    snapshot = dest / "SNAPSHOT.json"
    document = json.loads(snapshot.read_text(encoding="utf-8"))
    document["files"][0], document["files"][1] = document["files"][1], document["files"][0]
    mutated = (json.dumps(document, indent=2) + "\n").encode("utf-8")
    snapshot.write_bytes(mutated)
    (dest / "SNAPSHOT.json.sha256").write_bytes(
        f"{hashlib.sha256(mutated).hexdigest()}  SNAPSHOT.json\n".encode("ascii")
    )

    verify = _run(dest / "verify_snapshot.py")

    output = verify.stdout + verify.stderr
    assert verify.returncode == 2, output
    assert "ERROR" in output
    assert "files must be sorted by path" in output
    assert "Traceback" not in output


def test_assemble_destination_reservation_is_exclusive(tmp_path: Path) -> None:
    """Concurrent assembly contenders must not hold the destination reservation
    simultaneously; the OS-level exclusive create is shared across processes."""
    packager = _import_scripts_module("speckit_package", ROOT / "scripts")
    dest = tmp_path / "concurrent-destination"
    entered = threading.Event()
    release = threading.Event()
    holder_errors: list[BaseException] = []

    def hold_reservation() -> None:
        try:
            with packager._destination_reservation(dest):
                entered.set()
                if not release.wait(timeout=10):
                    holder_errors.append(TimeoutError("reservation test timed out"))
        except BaseException as exc:
            holder_errors.append(exc)

    holder = threading.Thread(target=hold_reservation)
    holder.start()
    assert entered.wait(timeout=10), "first contender did not acquire the reservation"
    try:
        acquired = False
        try:
            with packager._destination_reservation(dest):
                acquired = True
        except packager.CaptureError as exc:
            assert "reservation" in str(exc).lower()
        assert not acquired, "second contender entered while the first still held the lock"
    finally:
        release.set()
        holder.join(timeout=10)

    assert not holder.is_alive(), "reservation holder did not exit"
    assert not holder_errors, holder_errors
    assert not list(tmp_path.glob(".speckit-package-*.lock"))


# ---------------------------------------------------------------------------
# T031 / T035 / T038 — User Stories 2-4 automated legs
# ---------------------------------------------------------------------------


def test_packaged_installer_dry_run_from_assembled_package(tmp_path: Path) -> None:
    """T031: the packaged (unchanged) installer works by explicit path from the
    assembled package: dry-run plans CREATE actions and writes nothing."""
    fixture = _make_package_fixture(tmp_path)
    dest = tmp_path / "package-dest"
    assert _assemble(fixture, dest).returncode == 0
    target = tmp_path / "install-target"
    target.mkdir()
    unrelated = tmp_path / "unrelated-cwd"
    unrelated.mkdir()
    before_package = _tree_state(dest)
    before_target = _tree_state(target)
    before_fixture = _tree_state(fixture)

    result = _run(
        dest / "scripts" / "speckit_bootstrap.py",
        "install",
        "--target",
        str(target),
        "--dry-run",
        cwd=unrelated,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    created = {
        line.split(" ", 1)[1] for line in result.stdout.splitlines() if line.startswith("CREATE ")
    }
    assert "shared/shared.txt" in created
    assert "plugin-packs/demo-pack/plugin.json" in created
    assert "config/defaults.json" in created
    assert "DRY RUN install complete" in result.stdout
    assert _tree_state(dest) == before_package
    assert _tree_state(target) == before_target
    assert _tree_state(fixture) == before_fixture


def test_assemble_twice_produces_independent_update_fixtures(tmp_path: Path) -> None:
    """T035: two assembles from an evolved fixture tree yield two independent
    packages whose digests differ only for the changed files (quickstart D
    update-fixture enabler)."""
    fixture = _make_package_fixture(tmp_path)
    dest_a = tmp_path / "package-a"
    assert _assemble(fixture, dest_a, label="fixture-snap-a").returncode == 0
    state_a = _tree_state(dest_a)

    (fixture / "payload" / "shared.txt").write_bytes(b"shared content v2\n")
    (fixture / "seeds" / "defaults.json").write_bytes(b'{"seed": "v2"}\n')
    dest_b = tmp_path / "package-b"
    result = _assemble(fixture, dest_b, label="fixture-snap-b")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _tree_state(dest_a) == state_a  # A untouched by the second run
    inventory_a = json.loads((dest_a / "SNAPSHOT.json").read_bytes())
    inventory_b = json.loads((dest_b / "SNAPSHOT.json").read_bytes())
    assert inventory_a["snapshot"]["label"] == "fixture-snap-a"
    assert inventory_b["snapshot"]["label"] == "fixture-snap-b"
    digests_a = {entry["path"]: entry["sha256"] for entry in inventory_a["files"]}
    digests_b = {entry["path"]: entry["sha256"] for entry in inventory_b["files"]}
    assert set(digests_a) == set(digests_b) == FIXTURE_CLOSURE
    changed = {path for path in digests_a if digests_a[path] != digests_b[path]}
    assert changed == {"payload/shared.txt", "seeds/defaults.json"}


def test_package_readme_boundaries_links_and_timestamp_note(tmp_path: Path) -> None:
    """T038: on an assembled fixture package carrying the real README, every
    relative Markdown link resolves inside the package, the rights/assurance
    boundary precedes the repository-preparation (distribution-adjacent)
    section, and the timestamp-nondeterminism note (finding 4) is present."""
    fixture = _make_package_fixture(tmp_path, real_readme=True)
    dest = tmp_path / "package-dest"
    result = _assemble(fixture, dest)
    assert result.returncode == 0, result.stdout + result.stderr

    content = (dest / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", content)
    assert links, "README should contain relative links"
    for target in links:
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        assert (dest / target).is_file(), f"README link does not resolve in package: {target}"
    rights = content.index("## 5. Rights and assurance boundary")
    repo_prep = content.index("## 6. Repository preparation")
    assert rights < repo_prep  # boundary before distribution-adjacent guidance
    assert "captured_at" in content
    assert "per-file, not per-inventory" in content  # finding 4 nondeterminism note


# ---------------------------------------------------------------------------
# Reviewed-inventory binding (implement-6 major finding; FR-002)
# ---------------------------------------------------------------------------


def test_assemble_copies_exactly_the_reviewed_inventory(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    result, reviewed, digest = _save_inventory(fixture)
    assert result.returncode == 0, result.stdout + result.stderr
    assert digest in result.stderr  # printed digest equals the saved file's digest
    dest = tmp_path / "package-dest"

    result = _assemble(fixture, dest, reviewed=(reviewed, digest))

    assert result.returncode == 0, result.stdout + result.stderr
    assert (dest / "SNAPSHOT.json").read_bytes() == reviewed.read_bytes()
    assert f"inventory sha256 {digest}" in result.stdout
    assert digest in (dest / "SNAPSHOT.json.sha256").read_text(encoding="ascii")


def test_assemble_refuses_source_changed_after_review(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    result, reviewed, digest = _save_inventory(fixture)
    assert result.returncode == 0, result.stdout + result.stderr
    (fixture / "payload" / "shared.txt").write_bytes(b"changed after review\n")
    dest = tmp_path / "never-created"
    before = _tree_state(tmp_path)

    for extra in ((), ("--dry-run",)):
        result = _assemble(fixture, dest, *extra, reviewed=(reviewed, digest))
        output = result.stdout + result.stderr
        assert result.returncode == 2, output
        assert "DRIFT payload/shared.txt (changed since review)" in output
        assert "assemble complete" not in output
        assert not dest.exists()
        assert _tree_state(tmp_path) == before


def test_assemble_refuses_reviewed_bundle_version_mismatch_without_writes(
    tmp_path: Path,
) -> None:
    fixture = _make_package_fixture(tmp_path)
    result, reviewed, _original_digest = _save_inventory(fixture)
    assert result.returncode == 0, result.stdout + result.stderr

    document = json.loads(reviewed.read_text(encoding="utf-8"))
    document["snapshot"]["bundle_version"] = "fixture-2.0"
    reviewed.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    approved_digest = hashlib.sha256(reviewed.read_bytes()).hexdigest()
    dest = tmp_path / "empty-destination"
    dest.mkdir()
    before = _tree_state(tmp_path)

    result = _assemble(fixture, dest, reviewed=(reviewed, approved_digest))

    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert "DRIFT snapshot.bundle_version" in output
    assert "does not match current bundle manifest" in output
    assert list(dest.iterdir()) == []
    assert _tree_state(tmp_path) == before


def test_assemble_refuses_file_added_after_review(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    (fixture / "payload" / "extra.txt").write_bytes(b"later\n")
    manifest_path = fixture / "scripts" / "speckit-portable-bundle.json"
    bundle = json.loads(manifest_path.read_text(encoding="utf-8"))
    result, reviewed, digest = _save_inventory(fixture)
    assert result.returncode == 0, result.stdout + result.stderr
    bundle["files"][0]["include"] = ["shared.txt", "extra.txt"]
    manifest_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    dest = tmp_path / "never-created"

    result = _assemble(fixture, dest, reviewed=(reviewed, digest))

    output = result.stdout + result.stderr
    assert result.returncode == 2, output
    assert "(not in reviewed inventory)" in output
    assert "scripts/speckit-portable-bundle.json (changed since review)" in output
    assert not dest.exists()


def test_assemble_refuses_wrong_or_malformed_approved_digest(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    result, reviewed, digest = _save_inventory(fixture)
    assert result.returncode == 0, result.stdout + result.stderr
    dest = tmp_path / "never-created"

    for bad in ("0" * 64, "not-a-digest", digest[:-1]):
        result = _assemble(fixture, dest, reviewed=(reviewed, bad))
        assert result.returncode == 2, result.stdout + result.stderr
        assert not dest.exists()

    # editing the reviewed file after approval breaks the digest binding
    edited = reviewed.read_bytes().replace(b"fixture-snap", b"fixture-snq")
    reviewed.write_bytes(edited)
    result = _assemble(fixture, dest, reviewed=(reviewed, digest))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "does not match approved digest" in result.stderr
    assert not dest.exists()

    missing = _assemble(fixture, dest, reviewed=(tmp_path / "absent.json", digest))
    assert missing.returncode == 2
    assert not dest.exists()


def test_assemble_refuses_schema_invalid_reviewed_inventory_without_writes(tmp_path: Path) -> None:
    """A matching digest does not make an incomplete or out-of-schema review valid."""
    fixture = _make_package_fixture(tmp_path)
    result, reviewed, _digest = _save_inventory(fixture)
    assert result.returncode == 0, result.stdout + result.stderr
    valid_document = json.loads(reviewed.read_text(encoding="utf-8"))

    malformed_documents: list[dict[str, object]] = []
    missing_timestamp = json.loads(json.dumps(valid_document))
    del missing_timestamp["snapshot"]["captured_at"]
    malformed_documents.append(missing_timestamp)

    missing_reference_field = json.loads(json.dumps(valid_document))
    del missing_reference_field["snapshot"]["source_reference"]["commit"]
    malformed_documents.append(missing_reference_field)

    extra_property = json.loads(json.dumps(valid_document))
    extra_property["unexpected"] = True
    malformed_documents.append(extra_property)

    for index, document in enumerate(malformed_documents):
        reviewed_path = tmp_path / f"malformed-reviewed-{index}.json"
        reviewed_bytes = (json.dumps(document) + "\n").encode("utf-8")
        reviewed_path.write_bytes(reviewed_bytes)
        digest = hashlib.sha256(reviewed_bytes).hexdigest()
        dest = tmp_path / f"empty-destination-{index}"
        dest.mkdir()

        result = _assemble(fixture, dest, reviewed=(reviewed_path, digest))

        output = result.stdout + result.stderr
        assert result.returncode == 2, output
        assert "missing or invalid" in output or "unknown properties" in output, output
        assert list(dest.iterdir()) == []


def test_inventory_output_never_overwrites_or_writes_into_source(tmp_path: Path) -> None:
    fixture = _make_package_fixture(tmp_path)
    existing = tmp_path / "existing.json"
    existing.write_bytes(b"keep\n")

    result = _inventory(fixture, "--output", str(existing))
    assert result.returncode == 2, result.stdout + result.stderr
    assert existing.read_bytes() == b"keep\n"

    before = _tree_state(fixture)
    inside = fixture / "inventory.json"
    result = _inventory(fixture, "--output", str(inside))
    assert result.returncode == 2, result.stdout + result.stderr
    assert "outside the source repository" in result.stderr
    assert _tree_state(fixture) == before
