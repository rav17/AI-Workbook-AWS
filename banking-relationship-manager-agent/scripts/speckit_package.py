#!/usr/bin/env python3
"""Maintainer-side packager for the standalone Spec Kit Flow portable package.

Subcommands (contracts/speckit-package-cli.md):

* ``inventory`` — enumerate the capture closure and print the exact
  ``SNAPSHOT.json`` document to stdout; zero filesystem writes.
* ``assemble`` — preflight, byte-verbatim copy, ``SNAPSHOT.json`` write,
  blocking detect-secrets screen, two-directional verification, completion
  marker written last.

Stdlib-only except the subprocess call to ``detect-secrets`` (pinned
``>=1.5.0`` in ``requirements-dev.txt``). The tool is never delivered inside
the package. Exit codes: 0 success / 1 content problem / 2 refusal or invalid
invocation, matching ``scripts/speckit_bootstrap.py``.

Test-only fault hook (tasks.md decision D-A): the environment variable
``SPECKIT_PACKAGE_FAULT`` is read once in ``main``; unset or empty is inert,
the single allowlisted value ``corrupt-after-inventory`` flips one byte of one
destination file after ``SNAPSHOT.json`` is written and before post-write
verification, and any other value is an exit-2 invalid invocation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    # Defensive shim: make `import speckit_bootstrap` work regardless of how
    # this script is invoked (absolute path, relative path, other cwd).
    sys.path.insert(0, str(_SCRIPT_DIR))
# The inventory contract is "zero filesystem writes anywhere" and assemble must
# never write into the source tree (FR-005); importing the sibling module must
# therefore not leave a __pycache__ behind.
sys.dont_write_bytecode = True

from speckit_bootstrap import (  # noqa: E402
    _atomic_write,
    _relative_path,
    _resolve_within,
    _sha256,
)

__all__ = ["CaptureEntry", "main"]

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_MANIFEST_REL = "scripts/speckit-portable-bundle.json"
BUNDLE_MANIFEST = ROOT / "scripts" / "speckit-portable-bundle.json"
ENTRY_POINTS = ("scripts/speckit_bootstrap.py", BUNDLE_MANIFEST_REL)
PACKAGE_DOCS = (
    ("scripts/portable-package/README.md", "README.md"),
    ("scripts/portable-package/verify_snapshot.py", "verify_snapshot.py"),
)
INVENTORY_NAME = "SNAPSHOT.json"
MARKER_NAME = "SNAPSHOT.json.sha256"
SCHEMA_VERSION = 1
DIGEST_RE = re.compile(r"[a-f0-9]{64}")
COMMIT_RE = re.compile(r"[0-9a-fA-F]{7,64}")
FAULT_ENV = "SPECKIT_PACKAGE_FAULT"
FAULT_CORRUPT_AFTER_INVENTORY = "corrupt-after-inventory"
FAULT_ALLOWED = frozenset({FAULT_CORRUPT_AFTER_INVENTORY})
SCAN_TIMEOUT_SECONDS = 300

# Mirrored from scripts/speckit_bootstrap.py CATEGORIES. Mirror, don't import:
# only the four pinned helpers are part of the imported surface (plan coupling
# policy), and `_collect_bundle` itself is unusable here because it applies the
# consumer-install plugin.json rewrite and returns consumer destinations.
CATEGORIES = {
    "agents",
    "configuration",
    "documentation",
    "engine",
    "hooks",
    "integration",
    "instructions",
    "plugins",
    "scripts",
    "skills",
    "templates",
    "workflow",
}

EXIT_OK = 0
EXIT_CONTENT = 1
EXIT_REFUSED = 2

_BYTES = bytes  # alias: the dataclass field named "bytes" must not shadow the type


class CaptureError(Exception):
    """Capture/preflight problem; message follows ``<path> (<reason>)`` form."""


@dataclass(frozen=True)
class CaptureEntry:
    """One captured file (data-model.md section 2.1) plus its raw content."""

    path: str  # package-relative POSIX path
    sha256: str
    bytes: int
    origin: str  # "source" | "package-doc"
    content: _BYTES  # raw bytes, read in binary mode, never transformed
    source_path: str | None = None  # only for package-doc entries


def _free_text(label: str) -> Callable[[str], str]:
    """argparse type validating free-text metadata (data-model.md section 1).

    Verbatim constraint: printable, no control characters, <= 200 chars.
    Applied at parse time, before any filesystem effect.
    """

    def _validate(value: str) -> str:
        if not value or len(value) > 200 or not value.isprintable():
            raise argparse.ArgumentTypeError(
                f"{label} must be printable, contain no control characters "
                f"and be at most 200 characters"
            )
        return value

    return _validate


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble or inspect the standalone Spec Kit Flow portable package."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("inventory", "assemble"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--label", required=True, type=_free_text("--label"))
        sub.add_argument("--captured-by", required=True, type=_free_text("--captured-by"))
        sub.add_argument("--source-ref", type=_free_text("--source-ref"))
        if command == "assemble":
            sub.add_argument("--dest", required=True, help="absolute destination directory")
            sub.add_argument("--dry-run", action="store_true")
    return parser


def _is_junction(path: Path) -> bool:
    checker = getattr(os.path, "isjunction", None)  # Python >= 3.12
    return bool(checker(path)) if checker is not None else False


def _read_source(path: Path, rel: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CaptureError(f"{rel} ({exc})") from exc


def _capture_closure() -> tuple[str, list[CaptureEntry]]:
    """Enumerate the capture closure: manifest allowlist + 2 packaging entry
    points + 2 package-docs. Raw bytes, no transformation (the plugin.json
    ``enabled=False`` rewrite is a consumer-install-time transform and must not
    happen at capture). Raises :class:`CaptureError` on any invalid manifest,
    unsafe path, collision, or missing/unreadable file — before any write.
    """
    try:
        bundle = json.loads(BUNDLE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CaptureError(f"{BUNDLE_MANIFEST_REL} (cannot read bundle manifest: {exc})") from exc
    if not isinstance(bundle, dict) or not isinstance(bundle.get("files"), list):
        raise CaptureError(f"{BUNDLE_MANIFEST_REL} (bundle manifest must contain a files list)")
    version = bundle.get("bundle_version")
    if not isinstance(version, str) or not version:
        raise CaptureError(f"{BUNDLE_MANIFEST_REL} (bundle_version must be a non-empty string)")

    collected: dict[str, CaptureEntry] = {}

    def _add(package_path: str, content: bytes, origin: str, source_path: str | None) -> None:
        key = package_path.casefold()
        for existing in [*collected, INVENTORY_NAME.casefold(), MARKER_NAME.casefold()]:
            if key == existing or key.startswith(existing + "/") or existing.startswith(key + "/"):
                raise CaptureError(f"{package_path} (package path collision with {existing})")
        collected[key] = CaptureEntry(
            path=package_path,
            sha256=_sha256(content),
            bytes=len(content),
            origin=origin,
            content=content,
            source_path=source_path,
        )

    for entry in bundle["files"]:
        if not isinstance(entry, dict):
            raise CaptureError(f"{BUNDLE_MANIFEST_REL} (each bundle entry must be an object)")
        try:
            source_rel = _relative_path(entry.get("source"), "source")
        except ValueError as exc:
            raise CaptureError(f"{BUNDLE_MANIFEST_REL} ({exc})") from exc
        category = entry.get("category")
        if not isinstance(category, str) or category not in CATEGORIES:
            raise CaptureError(f"{BUNDLE_MANIFEST_REL} (unknown bundle category: {category!r})")
        seed = entry.get("seed", False)
        if not isinstance(seed, bool):
            raise CaptureError(f"{BUNDLE_MANIFEST_REL} (bundle seed flag must be boolean)")
        try:
            source = _resolve_within(ROOT, source_rel, "bundle source")
        except ValueError as exc:
            raise CaptureError(f"{source_rel.as_posix()} ({exc})") from exc
        if source.is_file():
            sources = [source]
        elif source.is_dir():
            included = entry.get("include")
            if not isinstance(included, list) or not included:
                raise CaptureError(
                    f"{source_rel.as_posix()} (directory bundle source needs an explicit "
                    f"include list)"
                )
            try:
                sources = [
                    _resolve_within(source, _relative_path(name, "included file"), "included file")
                    for name in included
                ]
            except ValueError as exc:
                raise CaptureError(f"{source_rel.as_posix()} ({exc})") from exc
        else:
            raise CaptureError(f"{source_rel.as_posix()} (missing or not a regular file)")
        for source_file in sources:
            rel_text = source_file.relative_to(ROOT).as_posix()
            if source_file.is_symlink() or not source_file.is_file():
                raise CaptureError(f"{rel_text} (missing or not a regular file)")
            try:
                _relative_path(rel_text, "captured path")
            except ValueError as exc:
                raise CaptureError(f"{rel_text} ({exc})") from exc
            _add(rel_text, _read_source(source_file, rel_text), "source", None)

    for entry_point in ENTRY_POINTS:
        path = _resolve_within(ROOT, _relative_path(entry_point, "entry point"), "entry point")
        if path.is_symlink() or not path.is_file():
            raise CaptureError(f"{entry_point} (missing or not a regular file)")
        _add(entry_point, _read_source(path, entry_point), "source", None)

    for doc_source, doc_package in PACKAGE_DOCS:
        _relative_path(doc_package, "package doc destination")
        path = _resolve_within(ROOT, _relative_path(doc_source, "package doc"), "package doc")
        if path.is_symlink() or not path.is_file():
            raise CaptureError(f"{doc_source} (missing or not a regular file)")
        _add(doc_package, _read_source(path, doc_source), "package-doc", doc_source)

    entries = sorted(collected.values(), key=lambda item: item.path)
    if not entries:
        raise CaptureError(f"{BUNDLE_MANIFEST_REL} (capture closure is empty)")
    return version, entries


def _git_output(arguments: Sequence[str]) -> str | None:
    """Read-only git query; never a mutation. Returns None when unavailable."""
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _snapshot_object(
    label: str, captured_by: str, source_ref: str | None, bundle_version: str
) -> dict[str, object]:
    """Snapshot identifier (data-model.md section 1). The source reference is
    recorded as reference only — never a fidelity claim; ``--source-ref`` is
    recorded text and is never passed to git.
    """
    fallback = source_ref or "unavailable"
    repository = (
        _git_output(["config", "--get", "remote.origin.url"])
        or _git_output(["rev-parse", "--show-toplevel"])
        or fallback
    )
    branch = _git_output(["rev-parse", "--abbrev-ref", "HEAD"]) or fallback
    commit = _git_output(["rev-parse", "HEAD"]) or fallback
    return {
        "label": label,
        "captured_at": datetime.now().astimezone().isoformat(),
        "captured_by": captured_by,
        "source_reference": {"repository": repository, "branch": branch, "commit": commit},
        "bundle_version": bundle_version,
        "digest_algorithm": "sha256",
    }


def _inventory_bytes(entries: Sequence[CaptureEntry], snapshot: dict[str, object]) -> bytes:
    """Serialize SNAPSHOT.json: UTF-8 without BOM, LF, one trailing newline,
    files sorted ascending by path, digests regex-validated, duplicates rejected
    (contracts/snapshot-inventory.schema.json).
    """
    seen: set[str] = set()
    files: list[dict[str, object]] = []
    for entry in sorted(entries, key=lambda item: item.path):
        if not DIGEST_RE.fullmatch(entry.sha256):
            raise CaptureError(f"{entry.path} (invalid sha256 digest)")
        if entry.bytes < 0:
            raise CaptureError(f"{entry.path} (invalid byte length)")
        if entry.path in seen:
            raise CaptureError(f"{entry.path} (duplicate inventory path)")
        seen.add(entry.path)
        item: dict[str, object] = {
            "path": entry.path,
            "sha256": entry.sha256,
            "bytes": entry.bytes,
            "origin": entry.origin,
        }
        if entry.source_path is not None:
            item["source_path"] = entry.source_path
        files.append(item)
    document = {"schema_version": SCHEMA_VERSION, "snapshot": snapshot, "files": files}
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def _preflight_destination(dest_argument: str, root: Path) -> list[str]:
    """Exit-2 refusal reasons, all evaluated before any filesystem write.

    Known limitation (documented, not solved): ``Path.resolve()`` does not
    canonicalize subst/mapped-drive or hardlink aliases.
    """
    raw = Path(dest_argument)
    if not raw.is_absolute():
        return [f"destination must be an absolute path: {dest_argument}"]
    conflicts: list[str] = []
    dest_resolved = raw.resolve()
    root_resolved = root.resolve()
    if dest_resolved.is_relative_to(root_resolved) or root_resolved.is_relative_to(dest_resolved):
        conflicts.append(f"destination and source root overlap: {dest_resolved} / {root_resolved}")
    if raw.is_symlink() or _is_junction(raw) or (raw.exists() and not raw.is_dir()):
        conflicts.append(f"destination exists and is not a plain directory: {dest_argument}")
    elif raw.is_dir() and any(raw.iterdir()):
        conflicts.append(f"destination directory is not empty: {dest_argument}")
    return conflicts


@contextmanager
def _destination_reservation(dest: Path) -> Iterator[None]:
    """Reserve one destination using an exclusive sibling lock file.

    The reservation prevents simultaneous assemblers from both passing the
    empty-destination preflight. It is not a transaction or rollback mechanism.
    """
    canonical_dest = dest.resolve()
    reservation_id = hashlib.sha256(str(canonical_dest).casefold().encode("utf-8")).hexdigest()
    reservation = canonical_dest.parent / f".speckit-package-{reservation_id}.lock"
    try:
        reservation.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            reservation,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
            0o600,
        )
        os.close(descriptor)
        created = reservation.lstat()
    except FileExistsError as exc:
        raise CaptureError(f"destination reservation is held or stale: {reservation}") from exc
    except OSError as exc:
        raise CaptureError(f"cannot reserve destination {canonical_dest}: {exc}") from exc

    try:
        yield
    finally:
        try:
            current = reservation.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise CaptureError(
                f"cannot inspect destination reservation {reservation}: {exc}"
            ) from exc
        else:
            if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                try:
                    reservation.unlink()
                except OSError as exc:
                    raise CaptureError(
                        f"cannot release destination reservation {reservation}: {exc}"
                    ) from exc


def _assert_coverage(submitted_count: int, inventory_count: int) -> bool:
    """Finding 3: the screen must submit every inventoried path plus
    SNAPSHOT.json, so a silently empty scan fails assembly."""
    return submitted_count >= inventory_count + 1


def _scan_argv(rel_paths: Sequence[str], *, module: str = "detect_secrets") -> list[str]:
    """Build the detect-secrets argv (shell=False list; research D5). Paths
    starting with ``-`` are ``./``-prefixed so they can never be parsed as
    options (argv-injection defense)."""
    safe_paths = [path if not path.startswith("-") else f"./{path}" for path in rel_paths]
    return [
        sys.executable,
        "-m",
        module,
        "scan",
        "--all-files",
        "--force-use-all-plugins",
        *safe_paths,
    ]


def _screen_verdict(
    returncode: int,
    stdout: str,
    allowed_hashed_secrets: frozenset[str] = frozenset(),
) -> tuple[bool, str]:
    """Interpret a detect-secrets baseline document, failing closed on every
    parse path (missing output, invalid JSON, schema drift, missing plugins).

    Findings come from the emitted baseline JSON ``results``, never the exit
    code — detect-secrets exits 0 even with findings (in-repo precedent:
    ``scripts/check_secrets.py`` parses ``report.get("results")``; unlike that
    lenient wrapper, an absent/malformed ``results`` key here is a failure).

    ``allowed_hashed_secrets`` suppresses, only inside ``SNAPSHOT.json``,
    findings whose ``hashed_secret`` equals the SHA-1 of a machine-generated
    hex value the packager itself just wrote there (per-file SHA-256 digests
    and the git commit reference). Empirically (detect-secrets 1.5.0) the
    HexHighEntropyString plugin flags those self-generated digests; the
    suppression is matched by exact secret hash so every free-text field in
    the inventory — and every captured file — remains fully screened.
    """
    if returncode != 0:
        return False, f"scanner exited with code {returncode}"
    text = stdout.strip()
    if not text:
        return False, "scanner produced no output"

    def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        parsed: dict[str, object] = {}
        for key, value in pairs:
            if key in parsed:
                raise ValueError(f"duplicate JSON key: {key}")
            parsed[key] = value
        return parsed

    try:
        report = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, ValueError):
        return False, "scanner output is not valid JSON"
    if not isinstance(report, dict):
        return False, "scanner report is not a JSON object"
    results = report.get("results")
    if not isinstance(results, dict):
        return False, "scanner report has no results object (schema drift)"
    plugins = report.get("plugins_used")
    if not isinstance(plugins, list) or not plugins:
        return False, "scanner report lists no plugins_used (schema drift)"
    if any(
        not isinstance(plugin, dict)
        or not isinstance(plugin.get("name"), str)
        or not plugin["name"]
        for plugin in plugins
    ):
        return False, "malformed plugins_used entry (schema drift)"
    findings: list[str] = []
    for filename, items in results.items():
        if not isinstance(filename, str):
            return False, "malformed results filename (schema drift)"
        if not isinstance(items, list):
            return False, f"malformed results entry for {filename} (schema drift)"
        for item in items:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("type"), str)
                or not item["type"]
                or not isinstance(item.get("line_number"), int)
                or isinstance(item.get("line_number"), bool)
                or item["line_number"] < 1
                or ("hashed_secret" in item and not isinstance(item["hashed_secret"], str))
            ):
                return False, f"malformed finding entry for {filename} (schema drift)"
            hashed = item.get("hashed_secret")
            location = str(filename).replace("\\", "/")  # stable POSIX display on Windows
            if (
                location == INVENTORY_NAME
                and isinstance(hashed, str)
                and hashed in allowed_hashed_secrets
            ):
                continue  # self-generated digest/commit hex, matched by secret hash
            # Locations only — file, line, detector type; never secret content.
            findings.append(f"{location}:{item.get('line_number')} ({item.get('type')})")
    if findings:
        return False, "findings:\n" + "\n".join(findings)
    return True, ""


def _run_screen(
    dest: Path,
    rel_paths: Sequence[str],
    inventory_count: int,
    *,
    module: str = "detect_secrets",
    allowed_hashed_secrets: frozenset[str] = frozenset(),
) -> tuple[bool, int, str]:
    """Blocking content screen over the explicit file list, cwd=destination.

    Returns ``(ok, submitted_count, detail)``. Fails closed on coverage
    shortfall, scanner unavailability, and every malformed-output branch.
    """
    submitted = len(rel_paths)
    if not _assert_coverage(submitted, inventory_count):
        return (
            False,
            submitted,
            f"coverage assertion failed: submitted {submitted} < inventory {inventory_count} + 1",
        )
    argv = _scan_argv(rel_paths, module=module)
    try:
        completed = subprocess.run(
            argv,
            cwd=dest,
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, submitted, f"scanner invocation failed: {exc}"
    ok, detail = _screen_verdict(completed.returncode, completed.stdout, allowed_hashed_secrets)
    return ok, submitted, detail


def _screen_allowlist(
    entries: Sequence[CaptureEntry], snapshot: dict[str, object]
) -> frozenset[str]:
    """detect-secrets ``hashed_secret`` values (SHA-1 of the secret string) for
    the machine-generated hex the packager writes into SNAPSHOT.json."""
    values = {entry.sha256 for entry in entries}
    reference = snapshot.get("source_reference")
    if isinstance(reference, dict):
        commit = reference.get("commit")
        if isinstance(commit, str) and COMMIT_RE.fullmatch(commit):
            values.add(commit)
    return frozenset(
        hashlib.sha1(value.encode("utf-8")).hexdigest()  # matches scanner output, not security
        for value in values
    )


def _verify_destination(
    dest: Path, entries: Sequence[CaptureEntry], inventory_bytes: bytes
) -> list[str]:
    """Two-directional post-write verification. Returns DRIFT reasons
    (``<path> (missing|digest mismatch|unlisted file)``); symlinks and
    junctions in the destination are reported as unlisted files (deny policy,
    ``followlinks=False``)."""
    expected: dict[str, tuple[str, int]] = {
        entry.path: (entry.sha256, entry.bytes) for entry in entries
    }
    expected[INVENTORY_NAME] = (_sha256(inventory_bytes), len(inventory_bytes))
    drift: list[str] = []
    seen: set[str] = set()
    for base, dirs, names in os.walk(dest, followlinks=False):
        base_path = Path(base)
        kept_dirs: list[str] = []
        for directory in dirs:
            candidate = base_path / directory
            if candidate.is_symlink() or _is_junction(candidate):
                drift.append(f"{candidate.relative_to(dest).as_posix()} (unlisted file)")
            else:
                kept_dirs.append(directory)
        dirs[:] = kept_dirs
        for name in names:
            candidate = base_path / name
            rel_text = candidate.relative_to(dest).as_posix()
            if candidate.is_symlink():
                drift.append(f"{rel_text} (unlisted file)")
                continue
            if rel_text not in expected:
                drift.append(f"{rel_text} (unlisted file)")
                continue
            seen.add(rel_text)
            digest_expected, length_expected = expected[rel_text]
            try:
                content = candidate.read_bytes()
            except OSError:
                drift.append(f"{rel_text} (missing)")
                continue
            if len(content) != length_expected or _sha256(content) != digest_expected:
                drift.append(f"{rel_text} (digest mismatch)")
    for rel_text in sorted(expected):
        if rel_text not in seen:
            drift.append(f"{rel_text} (missing)")
    return drift


def _inject_fault(point: str, dest: Path, entries: Sequence[CaptureEntry]) -> str:
    """Test-only fault hook (decision D-A): flip one byte of one named
    destination file. Only reachable for the allowlisted fault value."""
    if point != FAULT_CORRUPT_AFTER_INVENTORY:  # pragma: no cover - guarded in main()
        raise CaptureError(f"{FAULT_ENV} (unsupported fault point: {point!r})")
    entry = next((item for item in entries if item.bytes > 0), None)
    if entry is None:  # pragma: no cover - closure always has non-empty files
        raise CaptureError(f"{FAULT_ENV} (no non-empty destination file to corrupt)")
    target = _resolve_within(dest, _relative_path(entry.path, "fault target"), "fault target")
    corrupted = bytearray(target.read_bytes())
    corrupted[0] ^= 0xFF
    _atomic_write(target, bytes(corrupted))
    return entry.path


def _print_failure_summary(label: str, what: str) -> None:
    print(f"{what}; the destination is incomplete and must not be treated as snapshot {label}.")
    print(
        "Compare the destination against the snapshot inventory record (SNAPSHOT.json, or "
        "the capture output if it was never written) to confirm incompleteness."
    )
    print(
        "Recovery is user-directed: inspect, then remove or relocate the partial destination "
        "yourself, or choose a different empty destination before rerunning. Nothing already "
        "written was deleted; no rollback is claimed."
    )


def _cmd_inventory(args: argparse.Namespace) -> int:
    version, entries = _capture_closure()
    snapshot = _snapshot_object(args.label, args.captured_by, args.source_ref, version)
    data = _inventory_bytes(entries, snapshot)
    sys.stdout.buffer.write(data)  # exact document bytes, no newline translation
    sys.stdout.buffer.flush()
    print(f"{len(entries)} files inventoried", file=sys.stderr)
    print(f"inventory sha256 {_sha256(data)}", file=sys.stderr)
    return EXIT_OK


def _assemble_into_destination(
    dest: Path,
    entries: list[CaptureEntry],
    snapshot: dict[str, object],
    label: str,
    fault: str,
) -> int:
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"CONFLICT cannot create destination: {exc}")
        return EXIT_REFUSED

    for entry in entries:
        try:
            target = _resolve_within(
                dest, _relative_path(entry.path, "destination path"), "destination path"
            )
            _atomic_write(target, entry.content)
        except (OSError, ValueError) as exc:
            print(f"ERROR {entry.path} ({exc})")
            _print_failure_summary(label, "copying failed")
            return EXIT_CONTENT
        print(f"CREATE {entry.path}")

    inventory_data = _inventory_bytes(entries, snapshot)
    inventory_digest = _sha256(inventory_data)
    try:
        target = _resolve_within(dest, _relative_path(INVENTORY_NAME, "inventory"), "inventory")
        _atomic_write(target, inventory_data)
    except (OSError, ValueError) as exc:
        print(f"ERROR {INVENTORY_NAME} ({exc})")
        _print_failure_summary(label, "writing the snapshot inventory failed")
        return EXIT_CONTENT

    ok, submitted, detail = _run_screen(
        dest,
        [*(entry.path for entry in entries), INVENTORY_NAME],
        len(entries),
        allowed_hashed_secrets=_screen_allowlist(entries, snapshot),
    )
    print(f"screen submitted {submitted} paths")
    if not ok:
        for line in detail.splitlines():
            print(f"ERROR screen {line}")
        _print_failure_summary(label, "the blocking content screen failed")
        return EXIT_CONTENT

    if fault == FAULT_CORRUPT_AFTER_INVENTORY:
        flipped = _inject_fault(fault, dest, entries)
        print(f"ERROR {FAULT_ENV}={fault} fired: flipped one byte of {flipped}")

    drift = _verify_destination(dest, entries, inventory_data)
    if drift:
        for line in drift:
            print(f"DRIFT {line}")
        _print_failure_summary(label, "post-write verification found drift")
        return EXIT_CONTENT

    try:
        marker = _resolve_within(dest, _relative_path(MARKER_NAME, "marker"), "marker")
        _atomic_write(marker, f"{inventory_digest}  {INVENTORY_NAME}\n".encode("ascii"))
    except (OSError, ValueError) as exc:
        print(f"ERROR {MARKER_NAME} ({exc})")
        _print_failure_summary(label, "writing the completion marker failed")
        return EXIT_CONTENT
    print(f"inventory sha256 {inventory_digest}")
    print(f"assemble complete: snapshot {label}")
    return EXIT_OK


def _cmd_assemble(args: argparse.Namespace, fault: str) -> int:
    conflicts = _preflight_destination(args.dest, ROOT)
    if conflicts:
        for conflict in conflicts:
            print(f"CONFLICT {conflict}")
        return EXIT_REFUSED
    version, entries = _capture_closure()
    label: str = args.label
    snapshot = _snapshot_object(label, args.captured_by, args.source_ref, version)

    if args.dry_run:
        for entry in entries:
            print(f"CREATE {entry.path}")
        print(f"DRY RUN assemble: snapshot {label} ({len(entries)} files planned, zero writes)")
        return EXIT_OK

    dest = Path(args.dest).resolve()
    with _destination_reservation(dest):
        conflicts = _preflight_destination(args.dest, ROOT)
        if conflicts:
            for conflict in conflicts:
                print(f"CONFLICT {conflict}")
            return EXIT_REFUSED
        return _assemble_into_destination(dest, entries, snapshot, label, fault)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    fault = os.environ.get(FAULT_ENV, "")
    if fault and fault not in FAULT_ALLOWED:
        print(f"ERROR unrecognized {FAULT_ENV} value: {fault!r}", file=sys.stderr)
        return EXIT_REFUSED
    try:
        if args.command == "inventory":
            return _cmd_inventory(args)
        return _cmd_assemble(args, fault)
    except CaptureError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
