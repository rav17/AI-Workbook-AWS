from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from speckit_flow import audit, trace
from speckit_flow.models import STAGES, FlowError

DEFAULT_SENSORS_FILE = (
    Path(__file__).resolve().parent.parent / ".specify" / "sensors" / "sensors.json"
)
SENSORS_DIR = "sensors"
BUILTINS = ("consistency", "traceability")
ARTIFACTS = ("spec.md", "plan.md", "tasks.md")
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_PLACEHOLDER_RE = re.compile(r"NEEDS CLARIFICATION|\[FEATURE NAME\]|\[DATE\]|ACTION REQUIRED")
_STAGE_ARTIFACTS = {
    "specify": ("spec.md",),
    "clarify": ("spec.md",),
    "plan": ("spec.md", "plan.md"),
    "tasks": ("spec.md", "plan.md", "tasks.md"),
    "analyze": ("spec.md", "plan.md", "tasks.md"),
    "implement": ("spec.md", "plan.md", "tasks.md"),
}


@dataclass
class Sensor:
    id: str
    kind: str
    stages: tuple[str, ...]
    required: bool = False
    description: str = ""
    builtin: str = ""
    options: dict[str, Any] = field(default_factory=dict)
    argv: tuple[str, ...] = ()
    timeout: int = 120

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "stages": list(self.stages),
            "required": self.required,
            "description": self.description,
        }


def _parse(raw: Any, index: int) -> Sensor:
    if not isinstance(raw, dict):
        raise FlowError(f"sensor #{index} must be an object")
    sid = raw.get("id")
    if not isinstance(sid, str) or not _ID_RE.match(sid):
        raise FlowError(f"sensor #{index} needs an id like 'my-sensor'")
    kind = raw.get("kind")
    stages = raw.get("stages")
    if not isinstance(stages, list) or not stages or any(s not in STAGES for s in stages):
        raise FlowError(f"sensor {sid}: stages must be a non-empty list of {list(STAGES)}")
    required = raw.get("required", False)
    if not isinstance(required, bool):
        raise FlowError(f"sensor {sid}: required must be true or false")
    sensor = Sensor(sid, str(kind), tuple(stages), required, str(raw.get("description", "")))
    if kind == "builtin":
        if raw.get("builtin") not in BUILTINS:
            raise FlowError(f"sensor {sid}: builtin must be one of {list(BUILTINS)}")
        options = raw.get("options", {})
        if not isinstance(options, dict):
            raise FlowError(f"sensor {sid}: options must be an object")
        sensor.builtin, sensor.options = str(raw["builtin"]), options
    elif kind == "command":
        argv = raw.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            raise FlowError(f"sensor {sid}: argv must be a non-empty list of strings")
        timeout = raw.get("timeout", 120)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 600:
            raise FlowError(f"sensor {sid}: timeout must be 1-600 seconds")
        sensor.argv, sensor.timeout = tuple(argv), timeout
    else:
        raise FlowError(f"sensor {sid}: kind must be 'builtin' or 'command'")
    return sensor


def load_sensors(path: Path = DEFAULT_SENSORS_FILE) -> list[Sensor]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FlowError(f"cannot read sensors file {path.name}: {exc}") from exc
    except ValueError as exc:
        raise FlowError(f"sensors file {path.name} is not valid JSON: {exc}") from exc
    items = data.get("sensors") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise FlowError("sensors file must contain a 'sensors' list")
    sensors = [_parse(item, i + 1) for i, item in enumerate(items)]
    ids = [s.id for s in sensors]
    if len(ids) != len(set(ids)):
        raise FlowError("sensor ids must be unique")
    return sensors


def for_stage(sensors: list[Sensor], stage: str) -> list[Sensor]:
    return [s for s in sensors if stage in s.stages]


def _fingerprints(feature_dir: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ARTIFACTS:
        path = feature_dir / name
        if path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _consistency(feature_dir: Path, stage: str) -> tuple[bool, str]:
    problems: list[str] = []
    for name in _STAGE_ARTIFACTS.get(stage, ()):
        path = feature_dir / name
        if not path.is_file():
            problems.append(f"{name} missing")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            problems.append(f"{name} empty")
        elif _PLACEHOLDER_RE.search(text):
            problems.append(f"{name} has unresolved placeholders")
    return (not problems, "; ".join(problems) or "artifacts consistent")


def _traceability(feature_dir: Path, options: dict[str, Any]) -> tuple[bool, str]:
    matrix = trace.build_matrix(feature_dir)
    require_tests = bool(options.get("require_tests", False))
    if matrix.ok(require_tests):
        return True, "all requirements covered"
    gaps = matrix.uncovered + (matrix.untested if require_tests else [])
    return False, "uncovered: " + ", ".join(gaps)


def _command(sensor: Sensor, root: Path) -> tuple[bool, str]:
    argv = list(sensor.argv)
    if argv[0] in ("python", "python3"):
        argv[0] = sys.executable
    try:
        proc = subprocess.run(  # noqa: S603 - argv list from a committed file, no shell
            argv, cwd=root, capture_output=True, timeout=sensor.timeout, check=False
        )
    except FileNotFoundError:
        return False, "command not found"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {sensor.timeout}s"
    except OSError as exc:
        return False, f"cannot run: {type(exc).__name__}"
    return proc.returncode == 0, f"exit code {proc.returncode}"


def run_sensor(sensor: Sensor, feature_dir: Path, stage: str) -> tuple[bool, str]:
    try:
        if sensor.kind == "command":
            return _command(sensor, feature_dir.parent.parent)
        if sensor.builtin == "consistency":
            return _consistency(feature_dir, stage)
        return _traceability(feature_dir, sensor.options)
    except FlowError as exc:
        return False, str(exc)


def _results_path(feature_dir: Path, stage: str) -> Path:
    return feature_dir / SENSORS_DIR / f"{stage}.json"


def _load_results(feature_dir: Path, stage: str) -> dict[str, Any]:
    try:
        data = json.loads(_results_path(feature_dir, stage).read_text(encoding="utf-8"))
        results = data.get("results", {})
        return results if isinstance(results, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def run_stage(
    feature_dir: Path, stage: str, actor: str, path: Path = DEFAULT_SENSORS_FILE
) -> list[dict[str, Any]]:
    selected = for_stage(load_sensors(path), stage)
    results = _load_results(feature_dir, stage)
    outcomes: list[dict[str, Any]] = []
    for sensor in selected:
        passed, reason = run_sensor(sensor, feature_dir, stage)
        status = "pass" if passed else "fail"
        results[sensor.id] = {
            "status": status,
            "ts": audit.now_iso(),
            "reason": reason,
            "fingerprints": _fingerprints(feature_dir),
        }
        audit.append_event(
            feature_dir, "sensor_run", stage, actor, f"sensor={sensor.id} status={status}"
        )
        outcomes.append({"id": sensor.id, "status": status, "reason": reason})
    out = _results_path(feature_dir, stage)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    return outcomes


def gate_problems(
    feature_dir: Path, stage: str, path: Path = DEFAULT_SENSORS_FILE
) -> tuple[list[str], list[str]]:
    """Return (problems, relied-on sensor ids) for approving the stage's gate."""
    required = [s for s in for_stage(load_sensors(path), stage) if s.required]
    results = _load_results(feature_dir, stage)
    current = _fingerprints(feature_dir)
    problems: list[str] = []
    for sensor in required:
        entry = results.get(sensor.id)
        if not isinstance(entry, dict):
            problems.append(f"required sensor {sensor.id!r} has not been run")
        elif entry.get("status") != "pass":
            problems.append(f"required sensor {sensor.id!r} failed: {entry.get('reason', '')}")
        elif entry.get("fingerprints") != current:
            problems.append(f"required sensor {sensor.id!r} result is stale; re-run it")
    return problems, [s.id for s in required]
