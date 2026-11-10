"""Construction units with a dependency graph, and a human-approved verification command."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from speckit_flow import audit
from speckit_flow.models import FlowError

UNITS_FILE = "units.json"
DEFAULT_VERIFY_FILE = Path(__file__).resolve().parent.parent / ".specify" / "verify.json"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
_TASK_RE = re.compile(r"^T\d{3,}$")
VERIFY_TIMEOUT = 600
MAX_TRACKED_FILES = 100
MAX_TRACKED_BYTES = 1024 * 1024
SKELETON_UNIT = "walking-skeleton"


def _digest(argv: list[str]) -> str:
    return hashlib.sha256(json.dumps(argv).encode("utf-8")).hexdigest()[:16]


def _write(path: Path, data: dict[str, Any]) -> None:
    from speckit_flow.state import atomic_write

    atomic_write(path, json.dumps(data, indent=2) + "\n")


def _read(path: Path, what: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"cannot read {what}: {exc}") from exc
    if not isinstance(data, dict):
        raise FlowError(f"{what} must be a JSON object")
    return data


# ---- verification command -------------------------------------------------


def load_verify(path: Path = DEFAULT_VERIFY_FILE) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = _read(path, "verify file")
    argv = data.get("command")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise FlowError("verify file: command must be a non-empty list of strings")
    return data


def propose_verify(argv: list[str], actor: str, path: Path = DEFAULT_VERIFY_FILE) -> dict[str, Any]:
    if not argv or any(not a for a in argv):
        raise FlowError("verification command must be a non-empty argv list")
    data = {
        "command": argv,
        "proposed_by": actor,
        "proposed_at": audit.now_iso(),
        "approved_by": "",
    }
    _write(path, data)
    return data


def approve_verify(actor: str, path: Path = DEFAULT_VERIFY_FILE) -> dict[str, Any]:
    if not actor.startswith("human:"):
        raise FlowError("only a human can approve the verification command")
    data = load_verify(path)
    if data is None:
        raise FlowError("no verification command proposed")
    data["approved_by"] = actor
    data["approved_at"] = audit.now_iso()
    data["approved_digest"] = _digest(data["command"])
    _write(path, data)
    return data


def approved_command(path: Path = DEFAULT_VERIFY_FILE) -> list[str]:
    data = load_verify(path)
    if data is None:
        raise FlowError("no verification command; run 'verify propose' and have a human approve it")
    if not data.get("approved_by") or data.get("approved_digest") != _digest(data["command"]):
        raise FlowError("verification command is not approved (or changed since approval)")
    return list(data["command"])


def run_verify(root: Path, path: Path = DEFAULT_VERIFY_FILE) -> tuple[bool, str, str]:
    argv = approved_command(path)
    digest = _digest(argv)
    if argv[0] in ("python", "python3"):
        argv[0] = sys.executable
    try:
        proc = subprocess.run(  # noqa: S603 - approved argv, no shell
            argv, cwd=root, capture_output=True, timeout=VERIFY_TIMEOUT, check=False
        )
    except FileNotFoundError:
        return False, "command not found", digest
    except subprocess.TimeoutExpired:
        return False, f"timed out after {VERIFY_TIMEOUT}s", digest
    except OSError as exc:
        return False, f"cannot run: {type(exc).__name__}", digest
    return proc.returncode == 0, f"exit code {proc.returncode}", digest


# ---- units ----------------------------------------------------------------


def load_units(feature_dir: Path) -> list[dict[str, Any]]:
    path = feature_dir / UNITS_FILE
    if not path.is_file():
        return []
    items = _read(path, UNITS_FILE).get("units")
    if not isinstance(items, list):
        raise FlowError(f"{UNITS_FILE}: 'units' must be a list")
    return items


def _validate(units: list[dict[str, Any]]) -> None:
    ids = [u["id"] for u in units]
    if len(set(ids)) != len(ids):
        raise FlowError("duplicate unit id")
    for unit in units:
        for dep in unit["depends_on"]:
            if dep not in ids:
                raise FlowError(f"unit {unit['id']}: unknown dependency {dep!r}")
    remaining = {u["id"]: set(u["depends_on"]) for u in units}
    while remaining:
        ready = [i for i, deps in remaining.items() if not deps & remaining.keys()]
        if not ready:
            raise FlowError("unit dependencies contain a cycle")
        for i in ready:
            del remaining[i]


def add_unit(
    feature_dir: Path,
    uid: str,
    title: str,
    depends_on: list[str],
    tasks: list[str],
    actor: str,
    *,
    files: list[str] | None = None,
) -> dict[str, Any]:
    if not _ID_RE.match(uid):
        raise FlowError(f"invalid unit id {uid!r}")
    if not title.strip():
        raise FlowError("unit title is required")
    for task in tasks:
        if not _TASK_RE.match(task):
            raise FlowError(f"invalid task id {task!r}; expected T001 style")
    units = load_units(feature_dir)
    unit = {"id": uid, "title": title.strip(), "depends_on": depends_on, "tasks": tasks}
    if files:
        normalized = _file_paths(files)
        tracked_fingerprints(feature_dir.parent.parent, normalized)
        unit["files"] = normalized
    units.append(unit)
    _validate(units)
    _write(feature_dir / UNITS_FILE, {"units": units, "checkpoints": checkpointed(feature_dir)})
    audit.append_event(feature_dir, "unit_defined", None, actor, f"{uid} deps={len(depends_on)}")
    return unit


def checkpointed(feature_dir: Path) -> dict[str, dict[str, Any]]:
    path = feature_dir / UNITS_FILE
    if not path.is_file():
        return {}
    cps = _read(path, UNITS_FILE).get("checkpoints", {})
    return cps if isinstance(cps, dict) else {}


def checkpoint_unit(
    feature_dir: Path, uid: str, actor: str, verify_file: Path = DEFAULT_VERIFY_FILE
) -> tuple[bool, str]:
    units = load_units(feature_dir)
    unit = next((u for u in units if u["id"] == uid), None)
    if unit is None:
        raise FlowError(f"unknown unit {uid!r}")
    done = checkpointed(feature_dir)
    tracked = bool(unit.get("files"))
    if tracked:
        done.pop(uid, None)
        _write(feature_dir / UNITS_FILE, {"units": units, "checkpoints": done})
    try:
        return _checkpoint(feature_dir, unit, units, done, actor, verify_file)
    except FlowError:
        if tracked:
            audit.append_event(
                feature_dir,
                "unit_checkpoint",
                None,
                actor,
                f"{uid} failed: invalid evidence or policy",
            )
        raise


def _checkpoint(
    feature_dir: Path,
    unit: dict[str, Any],
    units: list[dict[str, Any]],
    done: dict[str, dict[str, Any]],
    actor: str,
    verify_file: Path,
) -> tuple[bool, str]:
    uid = unit["id"]
    missing = [d for d in unit["depends_on"] if d not in done]
    if missing:
        raise FlowError(f"unit {uid}: dependencies not checkpointed: {', '.join(missing)}")
    files = _file_paths(unit.get("files", []))
    before = tracked_fingerprints(feature_dir.parent.parent, files) if files else {}
    ok, note, digest = run_verify(feature_dir.parent.parent, verify_file)
    if ok and files:
        current = next((u for u in load_units(feature_dir) if u["id"] == uid), None)
        if (
            tracked_fingerprints(feature_dir.parent.parent, files) != before
            or current != unit
            or _digest(approved_command(verify_file)) != digest
        ):
            ok, note = False, "tracked files, definition or command changed during verification"
    audit.append_event(
        feature_dir, "unit_checkpoint", None, actor, f"{uid} {'passed' if ok else 'failed'}: {note}"
    )
    if ok:
        done[uid] = {"at": audit.now_iso(), "command": digest, "actor": actor}
        if files:
            done[uid].update(files=before, definition=_definition(unit))
        _write(feature_dir / UNITS_FILE, {"units": units, "checkpoints": done})
    return ok, note


def _file_paths(files: Any) -> list[str]:
    if not isinstance(files, list) or len(files) > MAX_TRACKED_FILES:
        raise FlowError(f"tracked files must be a path list of at most {MAX_TRACKED_FILES}")
    result: list[str] = []
    for label in files:
        if not isinstance(label, str):
            raise FlowError("tracked file path must be a string")
        value = label.replace("\\", "/")
        path = PurePosixPath(value)
        if (
            not value
            or not path.parts
            or value.strip() != value
            or path.is_absolute()
            or str(path) != value
            or ".." in path.parts
            or any(c in value for c in ':*?"<>|\0')
            or any(
                part.endswith((".", " "))
                or part.split(".")[0].upper()
                in {
                    "CON",
                    "PRN",
                    "AUX",
                    "NUL",
                    *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10)),
                }
                for part in path.parts
            )
        ):
            raise FlowError(
                "tracked file path must be canonical and root-relative without traversal"
            )
        result.append(value)
    if len({p.casefold() for p in result}) != len(result):
        raise FlowError("duplicate or aliased tracked file path")
    return result


def tracked_fingerprints(root: Path, files: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for label in _file_paths(files):
        try:
            path = root
            for part in PurePosixPath(label).parts:
                path = path / part
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode) or (
                    getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise FlowError("tracked file path cannot traverse a symlink or reparse point")
            if not stat.S_ISREG(info.st_mode):
                raise FlowError("tracked file path must name a regular file")
            with path.open("rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise FlowError("tracked file path must name a regular file")
                data = handle.read(MAX_TRACKED_BYTES + 1)
            if len(data) > MAX_TRACKED_BYTES:
                raise FlowError(f"tracked file exceeds size limit ({MAX_TRACKED_BYTES} bytes)")
            result[label] = hashlib.sha256(data).hexdigest()
        except OSError as exc:
            raise FlowError(f"cannot read tracked file path: {type(exc).__name__}") from exc
    return result


def _definition(unit: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(unit, sort_keys=True).encode("utf-8")).hexdigest()


def skeleton_fingerprints(feature_dir: Path) -> dict[str, str]:
    root = feature_dir.parent.parent
    unit = next((u for u in load_units(feature_dir) if u["id"] == SKELETON_UNIT), None)
    policy = load_verify(root / ".specify" / "verify.json")
    payload = {"units": load_units(feature_dir), "checkpoints": checkpointed(feature_dir)}
    result = {
        "skeleton:units": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
        "skeleton:verify": hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
    }
    if unit:
        result.update(
            {
                f"skeleton:file:{name}": digest
                for name, digest in tracked_fingerprints(root, unit.get("files", [])).items()
            }
        )
    return result


def skeleton_problems(feature_dir: Path) -> list[str]:
    try:
        unit = next((u for u in load_units(feature_dir) if u["id"] == SKELETON_UNIT), None)
        if unit is None:
            return ["walking-skeleton unit missing"]
        files = _file_paths(unit.get("files", []))
        report = (feature_dir / "skeleton.md").relative_to(feature_dir.parent.parent).as_posix()
        if len(files) < 3 or report not in files:
            return ["skeleton needs tracked implementation, test and feature-local skeleton.md"]
        try:
            tasks = (feature_dir / "tasks.md").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise FlowError("cannot read skeleton task references") from exc
        known = set(re.findall(r"^\s*-\s+\[[ xX]\]\s+(T\d{3,})\b", tasks, re.MULTILINE))
        if not unit["tasks"] or any(task not in known for task in unit["tasks"]):
            return ["skeleton unit must reference actual feature tasks"]
        cp = checkpointed(feature_dir).get(SKELETON_UNIT)
        if not cp:
            return ["walking-skeleton has no passing checkpoint"]
        command = approved_command(feature_dir.parent.parent / ".specify" / "verify.json")
        if (
            cp.get("definition") != _definition(unit)
            or cp.get("files") != tracked_fingerprints(feature_dir.parent.parent, files)
            or cp.get("command") != _digest(command)
        ):
            return ["skeleton checkpoint is stale; run checkpoint again"]
        return []
    except FlowError as exc:
        return [str(exc)]


def unchecked_units(feature_dir: Path) -> list[str]:
    done = checkpointed(feature_dir)
    return [u["id"] for u in load_units(feature_dir) if u["id"] not in done]


def list_units(feature_dir: Path) -> dict[str, Any]:
    done = checkpointed(feature_dir)
    return {"units": [{**u, "checkpointed": u["id"] in done} for u in load_units(feature_dir)]}
