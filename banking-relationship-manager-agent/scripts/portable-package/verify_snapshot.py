#!/usr/bin/env python3
"""Offline snapshot verifier for the Spec Kit Flow portable package.

Delivered at the package root; standard library only; works offline with the
source checkout inaccessible (contracts/speckit-package-cli.md section 3).

Standalone by design: the path-safety rules of the maintainer tooling
(``_relative_path`` / ``_resolve_within`` in ``scripts/speckit_bootstrap.py``)
are deliberately RE-IMPLEMENTED here rather than imported, because the package
must not depend on the maintainer tool and because ``SNAPSHOT.json`` is
untrusted input: every path read from it is validated (relative, no dot
segments, no forbidden characters, no Windows reserved device names, no
casefold collisions, no symlink traversal, contained in the package directory)
before it is joined to the package directory.

Exit codes: 0 intact; 1 drift, marker mismatch or marker missing; 2 unreadable
or invalid inventory, unsafe inventory path, or invocation error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath

INVENTORY_NAME = "SNAPSHOT.json"
MARKER_NAME = "SNAPSHOT.json.sha256"
DIGEST_RE = re.compile(r"[a-f0-9]{64}")
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:\d{2}|Z)")
_RESERVED_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class InventoryError(Exception):
    """Invalid, unreadable or unsafe SNAPSHOT.json content (exit 2)."""


def _safe_relative_path(value: object, label: str) -> PurePosixPath:
    """Re-implementation of the installer's ``_relative_path`` rules; the same
    rejection cases are pinned for both tools by the repository test suite."""
    if not isinstance(value, str) or not value:
        raise InventoryError(f"{label} must be a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise InventoryError(f"unsafe {label}: {value!r}")
    if any(char in value for char in '\\:<>"|?*\0') or any(
        part.endswith((" ", ".")) or part.split(".")[0].upper() in _RESERVED_DEVICE_NAMES
        for part in path.parts
    ):
        raise InventoryError(f"unsafe {label}: {value!r}")
    return path


def _is_junction(path: Path) -> bool:
    checker = getattr(os.path, "isjunction", None)  # Python >= 3.12
    return bool(checker(path)) if checker is not None else False


def _contained_path(root: Path, relative: PurePosixPath, label: str) -> Path:
    """Containment + per-component symlink/junction denial before any read."""
    root_resolved = root.resolve()
    candidate = root_resolved.joinpath(*relative.parts)
    current = root_resolved
    for part in relative.parts:
        current = current / part
        if current.is_symlink() or _is_junction(current):
            raise InventoryError(f"{label} must not traverse symlinks: {relative.as_posix()}")
    if not candidate.resolve().is_relative_to(root_resolved):
        raise InventoryError(f"{label} escapes the package directory: {relative.as_posix()}")
    return candidate


def _require_text(mapping: dict[str, object], key: str, owner: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value or len(value) > 200 or not value.isprintable():
        raise InventoryError(f"{owner}.{key} is missing or invalid")
    return value


def _reject_unknown_properties(mapping: dict[str, object], allowed: set[str], owner: str) -> None:
    unknown = mapping.keys() - allowed
    if unknown:
        raise InventoryError(f"{owner} has unknown properties: {', '.join(sorted(unknown))}")


def _load_inventory(package: Path) -> tuple[str, list[dict[str, object]], bytes]:
    """Parse and shape-validate SNAPSHOT.json (hand-rolled, schema-equivalent).

    Returns ``(label, file_entries, raw_inventory_bytes)``.
    """
    inventory_path = package / INVENTORY_NAME
    try:
        raw = inventory_path.read_bytes()
    except OSError as exc:
        raise InventoryError(f"cannot read {INVENTORY_NAME}: {exc}") from exc
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise InventoryError(f"{INVENTORY_NAME} is not valid UTF-8 JSON: {exc}") from exc
    if (
        not isinstance(document, dict)
        or type(document.get("schema_version")) is not int
        or document["schema_version"] != 1
    ):
        raise InventoryError(f"{INVENTORY_NAME} has a missing or unsupported schema_version")
    _reject_unknown_properties(document, {"schema_version", "snapshot", "files"}, "inventory")
    snapshot = document.get("snapshot")
    if not isinstance(snapshot, dict):
        raise InventoryError("snapshot identifier object is missing")
    _reject_unknown_properties(
        snapshot,
        {
            "label",
            "captured_at",
            "captured_by",
            "source_reference",
            "bundle_version",
            "digest_algorithm",
        },
        "snapshot",
    )
    label = _require_text(snapshot, "label", "snapshot")
    captured_at = _require_text(snapshot, "captured_at", "snapshot")
    if not TIMESTAMP_RE.fullmatch(captured_at):
        raise InventoryError("snapshot.captured_at is not an ISO-8601 timestamp with offset")
    _require_text(snapshot, "captured_by", "snapshot")
    _require_text(snapshot, "bundle_version", "snapshot")
    if snapshot.get("digest_algorithm") != "sha256":
        raise InventoryError("snapshot.digest_algorithm must be sha256")
    reference = snapshot.get("source_reference")
    if not isinstance(reference, dict):
        raise InventoryError("snapshot.source_reference object is missing")
    _reject_unknown_properties(
        reference, {"repository", "branch", "commit"}, "snapshot.source_reference"
    )
    for field in ("repository", "branch", "commit"):
        value = reference.get(field)
        if not isinstance(value, str) or not value:
            raise InventoryError(f"snapshot.source_reference.{field} is missing or invalid")
    files = document.get("files")
    if not isinstance(files, list) or not files:
        raise InventoryError("files list is missing or empty")
    collision_keys: list[str] = [INVENTORY_NAME.casefold(), MARKER_NAME.casefold()]
    entries: list[dict[str, object]] = []
    for item in files:
        if not isinstance(item, dict):
            raise InventoryError("every files entry must be an object")
        _reject_unknown_properties(
            item, {"path", "sha256", "bytes", "origin", "source_path"}, "files entry"
        )
        rel = _safe_relative_path(item.get("path"), "inventory path")
        text = rel.as_posix()
        key = text.casefold()
        for existing in collision_keys:
            if key == existing or key.startswith(existing + "/") or existing.startswith(key + "/"):
                raise InventoryError(f"inventory path collision: {text}")
        collision_keys.append(key)
        digest = item.get("sha256")
        if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
            raise InventoryError(f"invalid sha256 digest for {text}")
        length = item.get("bytes")
        if not isinstance(length, int) or isinstance(length, bool) or length < 0:
            raise InventoryError(f"invalid byte length for {text}")
        origin = item.get("origin")
        if not isinstance(origin, str) or origin not in {"source", "package-doc"}:
            raise InventoryError(f"invalid origin for {text}")
        source_path = item.get("source_path")
        if source_path is not None:
            if origin != "package-doc":
                raise InventoryError(f"source_path is only allowed on package-doc entries: {text}")
            _safe_relative_path(source_path, "source_path")
        entries.append(item)
    return label, entries, raw


def _print_honesty() -> None:
    print(
        "Note: unsigned digests detect corruption and casual tampering only; integrity "
        "otherwise rests on the delivery channel plus the out-of-band snapshot identifier "
        "and inventory digest (no code signing, no PKI)."
    )
    print(
        "Note: this verifier's check of its own inventory entry detects accidental "
        "corruption only; a tampered verifier can misreport its own digest. Use an "
        "independent digest command (Get-FileHash / certutil / sha256sum) against the "
        "out-of-band recorded inventory digest for tamper evidence."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a Spec Kit Flow portable package snapshot (offline, stdlib-only)."
    )
    parser.add_argument(
        "--package",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="package root directory (default: this script's own directory)",
    )
    args = parser.parse_args(argv)
    package: Path = args.package
    if not package.is_dir():
        print(f"ERROR package directory does not exist: {package}")
        return 2
    package = package.resolve()

    try:
        label, entries, raw = _load_inventory(package)
        targets = [
            (
                entry,
                _contained_path(
                    package, _safe_relative_path(entry["path"], "inventory path"), "inventory path"
                ),
            )
            for entry in entries
        ]
    except InventoryError as exc:
        print(f"ERROR {exc}")
        return 2

    drift: list[str] = []
    verified = 0
    for entry, target in targets:
        text = str(entry["path"])
        if target.is_symlink() or not target.is_file():
            drift.append(f"DRIFT {text} (missing)")
            continue
        try:
            content = target.read_bytes()
        except OSError:
            drift.append(f"DRIFT {text} (missing)")
            continue
        if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
            drift.append(f"DRIFT {text} (digest mismatch)")
            continue
        verified += 1

    listed = {str(entry["path"]) for entry in entries}
    allowed_extra = {INVENTORY_NAME, MARKER_NAME}
    for base, dirs, names in os.walk(package, followlinks=False):
        base_path = Path(base)
        kept_dirs: list[str] = []
        for directory in dirs:
            candidate = base_path / directory
            if candidate.is_symlink() or _is_junction(candidate):
                drift.append(f"DRIFT {candidate.relative_to(package).as_posix()} (unlisted file)")
            else:
                kept_dirs.append(directory)
        dirs[:] = kept_dirs
        for name in names:
            candidate = base_path / name
            rel_text = candidate.relative_to(package).as_posix()
            if candidate.is_symlink():
                drift.append(f"DRIFT {rel_text} (unlisted file)")
            elif rel_text not in listed and rel_text not in allowed_extra:
                drift.append(f"DRIFT {rel_text} (unlisted file)")

    marker_path = package / MARKER_NAME
    marker_missing = not marker_path.is_file()
    if not marker_missing:
        expected_marker = f"{hashlib.sha256(raw).hexdigest()}  {INVENTORY_NAME}\n".encode("ascii")
        try:
            if marker_path.read_bytes() != expected_marker:
                drift.append(f"DRIFT {MARKER_NAME} (digest mismatch)")
        except OSError:
            marker_missing = True

    if marker_missing:
        print(f"assembly never completed - not the named snapshot {label}")
    if drift or marker_missing:
        for line in drift:
            print(line)
        print(f"this folder must not be treated as snapshot {label}.")
        _print_honesty()
        return 1
    print(f"OK {verified} files verified; snapshot {label} intact")
    _print_honesty()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
