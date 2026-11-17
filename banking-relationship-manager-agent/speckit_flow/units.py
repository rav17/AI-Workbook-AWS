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
from speckit_flow.models import AuditEvent, FlowError

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
    except (OSError, ValueError) as exc:
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
    return _load_units(feature_dir)[0]


def _load_units(feature_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = feature_dir / UNITS_FILE
    if not path.is_file():
        return [], []
    items = _read(path, UNITS_FILE).get("units")
    if not isinstance(items, list):
        raise FlowError(f"{UNITS_FILE}: 'units' must be a list")
    return items, _validate(items)


def _validate(units: list[dict[str, Any]]) -> list[str]:
    for unit in units:
        if not isinstance(unit, dict) or not isinstance(unit.get("id"), str):
            raise FlowError("unit must be an object with a string id")
        if not _ID_RE.fullmatch(unit["id"]):
            raise FlowError(f"invalid unit id {unit['id']!r}")
        if not isinstance(unit.get("title"), str) or not unit["title"].strip():
            raise FlowError("unit title is required")
        for field in ("depends_on", "tasks"):
            values = unit.get(field)
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise FlowError(f"unit {unit['id']}: {field} must be a list of strings")
            if len(values) != len(set(values)):
                raise FlowError(f"unit {unit['id']}: duplicate {field}")
        if any(not _TASK_RE.fullmatch(task) for task in unit["tasks"]):
            raise FlowError(f"unit {unit['id']}: invalid task id; expected T001 style")
        _file_paths(unit.get("files", []))
    ids = [u["id"] for u in units]
    if len(set(ids)) != len(ids):
        raise FlowError("duplicate unit id")
    for unit in units:
        for dep in unit["depends_on"]:
            if dep not in ids:
                raise FlowError(f"unit {unit['id']}: unknown dependency {dep!r}")
    remaining = {u["id"]: set(u["depends_on"]) for u in units}
    ordered: list[str] = []
    while remaining:
        ready = [i for i, deps in remaining.items() if not deps & remaining.keys()]
        if not ready:
            raise FlowError("unit dependencies contain a cycle")
        for i in ready:
            ordered.append(i)
            del remaining[i]
    return ordered


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
    if not isinstance(cps, dict) or not all(isinstance(cp, dict) for cp in cps.values()):
        raise FlowError(f"{UNITS_FILE}: checkpoints must map unit ids to objects")
    return cps


def checkpoint_unit(
    feature_dir: Path, uid: str, actor: str, verify_file: Path | None = None
) -> tuple[bool, str]:
    units = load_units(feature_dir)
    unit = next((u for u in units if u["id"] == uid), None)
    if unit is None:
        raise FlowError(f"unknown unit {uid!r}")
    done = checkpointed(feature_dir)
    done.pop(uid, None)
    _write(feature_dir / UNITS_FILE, {"units": units, "checkpoints": done})
    try:
        return _checkpoint(
            feature_dir, unit, units, done, actor, _verify_path(feature_dir, verify_file)
        )
    except FlowError:
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
    reports = _assess(feature_dir, units, done, verify_file)
    missing = [d for d in unit["depends_on"] if not reports[d]["checkpointed"]]
    if missing:
        raise FlowError(
            f"unit {uid}: dependencies not checkpointed or stale: {', '.join(missing)}"
        )
    dependencies = {dep: _definition(done[dep]) for dep in unit["depends_on"]}
    files = _file_paths(unit.get("files", []))
    before = tracked_fingerprints(feature_dir.parent.parent, files) if files else {}
    ok, note, digest = run_verify(feature_dir.parent.parent, verify_file)
    current_units = load_units(feature_dir)
    current_done = checkpointed(feature_dir)
    if ok:
        current = next((u for u in current_units if u["id"] == uid), None)
        current_reports = _assess(feature_dir, current_units, current_done, verify_file)
        dependency_changed = any(
            dep not in current_reports
            or not current_reports[dep]["checkpointed"]
            or _definition(current_done[dep]) != dependencies[dep]
            for dep in unit["depends_on"]
        )
        if (
            tracked_fingerprints(feature_dir.parent.parent, files) != before
            or current != unit
            or _digest(approved_command(verify_file)) != digest
            or dependency_changed
            or uid in current_done
        ):
            ok, note = False, (
                "tracked files, definition, command or dependencies changed during verification"
            )
    event = audit.append_event(
        feature_dir, "unit_checkpoint", None, actor, f"{uid} {'passed' if ok else 'failed'}: {note}"
    )
    if ok:
        current_done[uid] = {
            "at": event.ts, "command": digest, "actor": actor, "revision": event.seq,
            "files": before, "definition": _definition(unit), "dependencies": dependencies,
        }
        _write(feature_dir / UNITS_FILE, {"units": current_units, "checkpoints": current_done})
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
        report_status = next(
            item for item in list_units(feature_dir)["units"] if item["id"] == SKELETON_UNIT
        )
        if not report_status["checkpointed"]:
            return ["skeleton checkpoint is stale; " + "; ".join(report_status["reasons"])]
        return []
    except FlowError as exc:
        return [str(exc)]


def _verify_path(feature_dir: Path, verify_file: Path | None) -> Path:
    return verify_file if verify_file is not None else (
        feature_dir.parent.parent / ".specify" / "verify.json"
    )


def _assess(
    feature_dir: Path,
    units: list[dict[str, Any]],
    done: dict[str, dict[str, Any]],
    verify_file: Path | None,
    *,
    include_evidence: bool = False,
    dependency_order: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    if not units:
        return reports
    latest_checks: dict[str, AuditEvent] = {}
    if include_evidence:
        snapshot = audit.snapshot(feature_dir)
        if snapshot.problem or not snapshot.event_count:
            raise FlowError("checkpoint evidence requires an intact, nonempty audit trail")
        for event in audit.read_events(feature_dir):
            if event.type == "unit_checkpoint":
                latest_checks[event.detail.split(" ", 1)[0]] = event
    try:
        command = _digest(approved_command(_verify_path(feature_dir, verify_file)))
        policy_problem = ""
    except FlowError as exc:
        command, policy_problem = None, str(exc)
    by_id = {unit["id"]: unit for unit in units}
    for uid in dependency_order if dependency_order is not None else _validate(units):
        unit = by_id[uid]
        cp = done.get(uid)
        present = uid in done
        reasons: list[str] = []
        reason_codes: list[str] = []
        blocked = [dep for dep in unit["depends_on"] if not reports[dep]["checkpointed"]]
        if blocked:
            reasons.append("dependencies not verified: " + ", ".join(blocked))
            reason_codes.append("dependencies_not_verified")
        if policy_problem:
            reasons.append(policy_problem)
            reason_codes.append("verification_policy_not_approved")
        try:
            files = tracked_fingerprints(feature_dir.parent.parent, unit.get("files", []))
        except FlowError as exc:
            files = None
            reasons.append(str(exc))
            reason_codes.append("tracked_inputs_unavailable")
        dependencies = {
            dep: _definition(done[dep]) for dep in unit["depends_on"] if dep in done
        }
        if present:
            assert cp is not None
            if (
                not all(key in cp for key in ("definition", "files", "dependencies", "revision"))
                or type(cp.get("revision")) is not int
                or cp["revision"] < 1
            ):
                reasons.append("legacy checkpoint lacks freshness metadata; run checkpoint again")
                reason_codes.append("checkpoint_metadata_incomplete")
            if cp.get("definition") != _definition(unit):
                reasons.append("unit definition changed")
                reason_codes.append("unit_definition_changed")
            if cp.get("files") != files:
                reasons.append("tracked files changed or unavailable")
                reason_codes.append("tracked_inputs_changed")
            if command is not None and cp.get("command") != command:
                reasons.append("approved command changed")
                reason_codes.append("verification_command_changed")
            if cp.get("dependencies") != dependencies:
                reasons.append("dependency checkpoint evidence changed")
                reason_codes.append("dependency_evidence_changed")
            status = "stale" if reasons else "verified"
        else:
            status = "blocked" if reasons else "ready"
            if not reasons:
                reasons.append("no checkpoint; dependencies and verification policy ready")
            reason_codes.append("checkpoint_missing")
        reports[uid] = {
            "status": status, "checkpointed": status == "verified",
            "checkpoint_present": present, "reasons": reasons, "blocked_by": blocked,
            "coverage": "tracked-files" if unit.get("files") else "command-only",
        }
        if include_evidence:
            check = latest_checks.get(uid)
            revision = cp.get("revision") if cp else None
            checkpoint_record_matches = (
                check is not None
                and cp is not None
                and type(revision) is int
                and revision > 0
                and check.seq == revision
                and check.ts == cp.get("at")
                and check.actor == cp.get("actor")
                and check.detail.startswith(f"{uid} passed: ")
            )
            verification = (
                "recorded_pass" if check and check.detail.startswith(f"{uid} passed: ")
                else "recorded_failure" if check and check.detail.startswith(f"{uid} failed: ")
                else "not_verified" if check or cp is not None
                else "not_recorded"
            )
            if verification == "recorded_failure":
                reason_codes.append("verification_recorded_failure")
            if present and not checkpoint_record_matches:
                reason_codes.append("verification_record_unverified")
            disposition = (
                "stale" if status == "stale"
                else "blocked" if status == "blocked"
                else "missing" if not present
                else "unverified" if not checkpoint_record_matches
                else "command_only" if not unit.get("files")
                else "current"
            )
            saved_files = cp.get("files") if cp else None
            reports[uid]["checkpoint_evidence"] = {
                "status": disposition,
                "freshness": "current" if status == "verified" else (
                    "stale" if status == "stale" else "not_verified"
                ),
                "reason_codes": reason_codes,
                "changed_files": [
                    name for name in unit.get("files", [])
                    if cp is not None and files is not None
                    and (not isinstance(saved_files, dict) or saved_files.get(name) != files[name])
                ],
                "checkpoint_revision": (
                    revision if type(revision) is int and revision > 0 else None
                ),
                "verification_revision": check.seq if check else None,
                "recorded_verification": verification,
                "checkpoint_record_matches": checkpoint_record_matches,
                "semantic_completion": "not_verified",
                "fingerprints": {
                    "definition": _definition(unit),
                    "files": files,
                    "approved_command": command,
                    "dependencies": dependencies,
                },
            }
    return reports


def unchecked_units(feature_dir: Path, verify_file: Path | None = None) -> list[str]:
    return [
        unit["id"] for unit in list_units(feature_dir, verify_file)["units"]
        if not unit["checkpointed"]
    ]


def list_units(
    feature_dir: Path, verify_file: Path | None = None, *, include_evidence: bool = False
) -> dict[str, Any]:
    units, dependency_order = _load_units(feature_dir)
    reports = _assess(
        feature_dir, units, checkpointed(feature_dir), verify_file,
        include_evidence=include_evidence,
        dependency_order=dependency_order,
    )
    result = {
        "units": [{**unit, **reports[unit["id"]]} for unit in units],
        "ready": [uid for uid, report in reports.items() if report["status"] == "ready"],
        "notice": (
            "Read-only declared-input freshness, not test execution or dispatch authorization. "
            "Command-only units have no source freshness guarantee. "
            "Ready units still require normal gates and shared-file coordination."
        ),
    }
    if include_evidence:
        result["dependency_order"] = dependency_order
    return result
