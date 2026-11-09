from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from speckit_flow import audit, questions, readiness, trace
from speckit_flow import contracts as contracts_mod
from speckit_flow import plugins as plugins_mod
from speckit_flow import units as units_mod
from speckit_flow.models import STAGES, FlowError

DEFAULT_SENSORS_FILE = (
    Path(__file__).resolve().parent.parent / ".specify" / "sensors" / "sensors.json"
)
DEFAULT_PROFILES_DIR = (
    Path(__file__).resolve().parent.parent / ".specify" / "profiles"
)
SENSORS_DIR = "sensors"
BUILTINS = (
    "consistency",
    "traceability",
    "questions",
    "section",
    "readiness",
    "skeleton",
    "stage-contract",
)
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
    profiles: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "stages": list(self.stages),
            "required": self.required,
            "description": self.description,
            "profiles": list(self.profiles),
        }


def _parse(raw: Any, index: int) -> Sensor:
    if not isinstance(raw, dict):
        raise FlowError(f"sensor #{index} must be an object")
    sid = raw.get("id")
    if not isinstance(sid, str) or not _ID_RE.match(sid):
        raise FlowError(f"sensor #{index} needs an id like 'my-sensor'")
    kind = raw.get("kind")
    stages = raw.get("stages")
    if (
        not isinstance(stages, list)
        or not stages
        or ("*" in stages and stages != ["*"])
        or any(s not in STAGES and s != "*" for s in stages)
    ):
        raise FlowError(
            f"sensor {sid}: stages must be a non-empty list of stage ids or ['*']"
        )
    required = raw.get("required", False)
    if not isinstance(required, bool):
        raise FlowError(f"sensor {sid}: required must be true or false")
    sensor = Sensor(sid, str(kind), tuple(stages), required, str(raw.get("description", "")))
    scope = raw.get("profiles")
    if scope is not None:
        if not isinstance(scope, list) or not scope or not all(isinstance(p, str) for p in scope):
            raise FlowError(f"sensor {sid}: profiles must be a non-empty list of profile ids")
        sensor.profiles = tuple(scope)
    if kind == "builtin":
        if raw.get("builtin") not in BUILTINS:
            raise FlowError(f"sensor {sid}: builtin must be one of {list(BUILTINS)}")
        options = raw.get("options", {})
        if not isinstance(options, dict):
            raise FlowError(f"sensor {sid}: options must be an object")
        if raw["builtin"] in ("readiness", "skeleton", "stage-contract") and options:
            raise FlowError(f"sensor {sid}: {raw['builtin']} does not accept options")
        if raw["builtin"] == "section":
            heading = options.get("heading")
            if not isinstance(heading, str) or not heading.strip():
                raise FlowError(f"sensor {sid}: section needs a non-empty 'heading' option")
            artifact = options.get("artifact")
            if artifact is not None and artifact not in ARTIFACTS:
                raise FlowError(f"sensor {sid}: artifact must be one of {list(ARTIFACTS)}")
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


def _read_sensors(path: Path) -> list[Sensor]:
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


def load_sensors(path: Path = DEFAULT_SENSORS_FILE) -> list[Sensor]:
    sensors = _read_sensors(path)
    try:
        found = plugins_mod.discover(path.parent.parent)
    except plugins_mod.PluginError as exc:
        raise FlowError(str(exc)) from exc
    for plugin in found:
        if plugin.sensors_file.is_file():
            known = {s.id for s in sensors}
            for extra in _read_sensors(plugin.sensors_file):
                if extra.id in known:
                    raise FlowError(
                        f"plugin {plugin.name}: sensor {extra.id!r} already exists; "
                        "plugins can only add sensors"
                    )
                sensors.append(extra)
    # Project overlay: .specify/custom/sensors.json adds sensors or tightens existing ones.
    overlay = path.parent.parent / "custom" / "sensors.json"
    if not overlay.is_file():
        return sensors
    by_id = {s.id: s for s in sensors}
    for extra in _read_sensors(overlay):
        base = by_id.get(extra.id)
        if base and base.required:
            raise FlowError(f"custom sensor {extra.id} cannot replace required core sensor")
        by_id[extra.id] = extra
    return list(by_id.values())


def for_stage(
    sensors: list[Sensor],
    stage: str,
    profile: str | None = None,
    stage_contracts: bool = False,
) -> list[Sensor]:
    return [
        s
        for s in sensors
        if ("*" in s.stages or stage in s.stages)
        and (not s.profiles or profile is None or profile in s.profiles)
        and (s.builtin != "stage-contract" or stage_contracts)
    ]


def _feature_profile(feature_dir: Path) -> tuple[str | None, bool]:
    from speckit_flow import state as flow_state

    try:
        state = flow_state.load_state(feature_dir)
    except (FlowError, OSError):
        return None, False
    candidates = (
        feature_dir.parent.parent / ".specify" / "profiles",
        DEFAULT_PROFILES_DIR,
    )
    for profiles_dir in candidates:
        try:
            profile = flow_state.profile_for(feature_dir, state.profile, profiles_dir)
            return profile.id, profile.stage_contracts
        except FlowError:
            continue
    return state.profile, False


def _section(feature_dir: Path, stage: str, options: dict[str, Any]) -> tuple[bool, str]:
    heading = str(options["heading"]).strip().lower()
    name = options.get("artifact") or ("plan.md" if stage == "plan" else "spec.md")
    path = feature_dir / name
    if not path.is_file():
        return False, f"{name} missing"
    in_section, has_body = False, False
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if match:
            if in_section:
                break
            in_section = match.group(1).strip().lower().startswith(heading)
        elif in_section and line.strip():
            has_body = True
    if not in_section and not has_body:
        return False, f"{name} has no '{options['heading']}' section"
    if not has_body:
        return False, f"{name} '{options['heading']}' section is empty"
    return True, f"{name} has a '{options['heading']}' section"


def _fingerprints(
    feature_dir: Path, sensor: Sensor | None = None, stage: str | None = None
) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in ARTIFACTS:
        path = feature_dir / name
        if path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if sensor is not None and sensor.builtin == "readiness":
        result.update(readiness.fingerprints(feature_dir))
    if sensor is not None and sensor.builtin == "skeleton":
        result.update(units_mod.skeleton_fingerprints(feature_dir))
    if sensor is not None and sensor.builtin == "stage-contract" and stage is not None:
        result.update(
            contracts_mod.fingerprints(
                feature_dir, stage, feature_dir.parent.parent / ".specify"
            )
        )
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
        if sensor.builtin == "questions":
            pending = questions.open_questions(feature_dir)
            ids = ", ".join(q.id for q in pending)
            return (not pending, f"open questions: {ids}" if pending else "no open questions")
        if sensor.builtin == "section":
            return _section(feature_dir, stage, sensor.options)
        if sensor.builtin == "readiness":
            return readiness.check(feature_dir)
        if sensor.builtin == "skeleton":
            problems = units_mod.skeleton_problems(feature_dir)
            return not problems, "; ".join(problems) or (
                "current skeleton checkpoint; human journey review still required"
            )
        if sensor.builtin == "stage-contract":
            return contracts_mod.check_outputs(
                feature_dir, stage, feature_dir.parent.parent / ".specify"
            )
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
    profile, has_contracts = _feature_profile(feature_dir)
    selected = for_stage(load_sensors(path), stage, profile, has_contracts)
    results = _load_results(feature_dir, stage)
    outcomes: list[dict[str, Any]] = []
    for sensor in selected:
        before = (
            _fingerprints(feature_dir, sensor, stage)
            if sensor.builtin in ("readiness", "skeleton", "stage-contract") else None
        )
        passed, reason = run_sensor(sensor, feature_dir, stage)
        fingerprints = _fingerprints(feature_dir, sensor, stage)
        if before is not None and before != fingerprints:
            passed, reason = False, f"{sensor.builtin} artifacts changed during validation; re-run"
        status = "pass" if passed else "fail"
        results[sensor.id] = {
            "status": status,
            "ts": audit.now_iso(),
            "reason": reason,
            "fingerprints": fingerprints,
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
    profile, has_contracts = _feature_profile(feature_dir)
    required = [
        s
        for s in for_stage(load_sensors(path), stage, profile, has_contracts)
        if s.required
    ]
    results = _load_results(feature_dir, stage)
    problems: list[str] = []
    for sensor in required:
        try:
            current = _fingerprints(feature_dir, sensor, stage)
        except FlowError as exc:
            problems.append(f"required sensor {sensor.id!r}: {exc}")
            continue
        entry = results.get(sensor.id)
        if not isinstance(entry, dict):
            problems.append(f"required sensor {sensor.id!r} has not been run")
        elif entry.get("status") != "pass":
            problems.append(f"required sensor {sensor.id!r} failed: {entry.get('reason', '')}")
        elif entry.get("fingerprints") != current:
            problems.append(f"required sensor {sensor.id!r} result is stale; re-run it")
    return problems, [s.id for s in required]
