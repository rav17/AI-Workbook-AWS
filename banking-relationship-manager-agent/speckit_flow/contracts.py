"""Structured, project-owned contracts for workflow stages."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from speckit_flow import plugins
from speckit_flow.models import STAGES, FlowError, Profile

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPECIFY_DIR = ROOT / ".specify"
CUSTOM_FILE = Path("custom") / "stage-contracts.json"
PLUGIN_CONTRACT_FILE = Path("contracts") / "stages.json"
MAX_OUTPUTS = 100
MAX_OUTPUT_BYTES = 1024 * 1024
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class ContractInput:
    id: str
    description: str
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {"id": self.id, "description": self.description}
        if self.path is not None:
            value["path"] = self.path
        return value


@dataclass(frozen=True)
class ContractOutput:
    id: str
    description: str
    required: bool
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "required": self.required,
        }
        if self.path is not None:
            value["path"] = self.path
        return value


@dataclass(frozen=True)
class StageContract:
    stage: str
    purpose: str
    inputs: tuple[ContractInput, ...]
    outputs: tuple[ContractOutput, ...]
    acceptance_criteria: tuple[str, ...]
    review_focus: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "purpose": self.purpose,
            "inputs": [item.to_dict() for item in self.inputs],
            "outputs": [item.to_dict() for item in self.outputs],
            "acceptance_criteria": list(self.acceptance_criteria),
            "review_focus": list(self.review_focus),
        }


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FlowError(f"{label} must be a non-empty string")
    return value.strip()


def _relative_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise FlowError(f"{label} must be a canonical feature-relative path")
    if "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise FlowError(f"{label} must be a canonical feature-relative path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise FlowError(f"{label} must not contain empty, '.' or '..' path segments")
    if PurePosixPath(value).as_posix() != value:
        raise FlowError(f"{label} must be a canonical feature-relative path")
    return value


def _parse_inputs(raw: Any, stage: str) -> tuple[ContractInput, ...]:
    if not isinstance(raw, list):
        raise FlowError(f"stage {stage}: inputs must be a list")
    result: list[ContractInput] = []
    seen: set[str] = set()
    for index, item in enumerate(raw, 1):
        label = f"stage {stage} input #{index}"
        if not isinstance(item, dict) or set(item) - {"id", "description", "path"}:
            raise FlowError(f"{label} must be an object with supported fields")
        input_id = _nonempty(item.get("id"), f"{label} id")
        if not _ID_RE.fullmatch(input_id) or input_id in seen:
            raise FlowError(f"{label} has an invalid or duplicate id {input_id!r}")
        seen.add(input_id)
        path = _relative_path(item["path"], f"{label} path") if "path" in item else None
        result.append(
            ContractInput(
                input_id,
                _nonempty(item.get("description"), f"{label} description"),
                path,
            )
        )
    return tuple(result)


def _parse_outputs(raw: Any, stage: str) -> tuple[ContractOutput, ...]:
    if not isinstance(raw, list):
        raise FlowError(f"stage {stage}: outputs must be a list")
    result: list[ContractOutput] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, item in enumerate(raw, 1):
        label = f"stage {stage} output #{index}"
        if not isinstance(item, dict) or set(item) - {
            "id",
            "description",
            "required",
            "path",
        }:
            raise FlowError(f"{label} must be an object with supported fields")
        output_id = _nonempty(item.get("id"), f"{label} id")
        if not _ID_RE.fullmatch(output_id) or output_id in seen_ids:
            raise FlowError(f"{label} has an invalid or duplicate id {output_id!r}")
        seen_ids.add(output_id)
        required = item.get("required")
        if not isinstance(required, bool):
            raise FlowError(f"{label} required must be true or false")
        path = _relative_path(item["path"], f"{label} path") if "path" in item else None
        if path is not None and path in seen_paths:
            raise FlowError(f"stage {stage}: duplicate output path {path!r}")
        if path is not None:
            seen_paths.add(path)
        result.append(
            ContractOutput(
                output_id,
                _nonempty(item.get("description"), f"{label} description"),
                required,
                path,
            )
        )
    return tuple(result)


def _parse_contract(raw: Any, source: Path, index: int) -> StageContract:
    label = f"{source}: contract #{index}"
    required_fields = {
        "stage",
        "purpose",
        "inputs",
        "outputs",
        "acceptance_criteria",
        "review_focus",
    }
    if not isinstance(raw, dict) or set(raw) != required_fields:
        raise FlowError(f"{label} must contain exactly {sorted(required_fields)}")
    stage = _nonempty(raw.get("stage"), f"{label} stage")
    if stage not in STAGES:
        raise FlowError(f"{label} references unknown stage {stage!r}")
    acceptance = raw.get("acceptance_criteria")
    review = raw.get("review_focus")
    if (
        not isinstance(acceptance, list)
        or not acceptance
        or not all(isinstance(item, str) and item.strip() for item in acceptance)
    ):
        raise FlowError(f"{label} acceptance_criteria must be a non-empty list of strings")
    if not isinstance(review, list) or not all(
        isinstance(item, str) and item.strip() for item in review
    ):
        raise FlowError(f"{label} review_focus must be a list of non-empty strings")
    return StageContract(
        stage=stage,
        purpose=_nonempty(raw.get("purpose"), f"{label} purpose"),
        inputs=_parse_inputs(raw.get("inputs"), stage),
        outputs=_parse_outputs(raw.get("outputs"), stage),
        acceptance_criteria=tuple(item.strip() for item in acceptance),
        review_focus=tuple(item.strip() for item in review),
    )


def _read_file(path: Path) -> list[StageContract]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FlowError(f"stage contracts file {path} is not valid JSON: {exc}") from exc
    except OSError as exc:
        raise FlowError(f"cannot read stage contracts file {path}: {exc}") from exc
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "contracts"}
        or type(data.get("version")) is not int
        or data["version"] != 1
        or not isinstance(data.get("contracts"), list)
    ):
        raise FlowError(f"stage contracts file {path} must have version 1 and a contracts list")
    parsed = [_parse_contract(item, path, index) for index, item in enumerate(data["contracts"], 1)]
    stages = [item.stage for item in parsed]
    if len(stages) != len(set(stages)):
        raise FlowError(f"stage contracts file {path} contains duplicate stages")
    return parsed


def load_contracts(specify_dir: Path = DEFAULT_SPECIFY_DIR) -> dict[str, StageContract]:
    """Load enabled plugin contracts and apply project-owned stage overrides."""
    contracts_by_stage: dict[str, StageContract] = {}
    try:
        found = plugins.discover(specify_dir)
    except plugins.PluginError as exc:
        raise FlowError(str(exc)) from exc
    for plugin in found:
        path = plugin.path / PLUGIN_CONTRACT_FILE
        if not path.is_file():
            continue
        for contract in _read_file(path):
            if contract.stage in contracts_by_stage:
                raise FlowError(
                    f"plugin {plugin.name}: duplicate contract for stage {contract.stage!r}"
                )
            contracts_by_stage[contract.stage] = contract

    custom_path = specify_dir / CUSTOM_FILE
    if custom_path.is_file():
        contracts_by_stage.update({item.stage: item for item in _read_file(custom_path)})
    return contracts_by_stage


def validate_profile(profile: Profile, specify_dir: Path = DEFAULT_SPECIFY_DIR) -> None:
    """Require complete contracts and checkable gated outputs for opted-in profiles."""
    if not profile.stage_contracts:
        return
    contracts_by_stage = load_contracts(specify_dir)
    missing = [stage for stage in profile.stages if stage not in contracts_by_stage]
    if missing:
        raise FlowError(
            f"profile {profile.id}: missing contracts for routed stages: {', '.join(missing)}"
        )
    from speckit_flow import sensors

    try:
        configured_sensors = sensors.load_sensors(specify_dir / "sensors" / "sensors.json")
    except FlowError as exc:
        raise FlowError(f"profile {profile.id}: cannot load contract sensors: {exc}") from exc
    checked_paths: set[str] = set()
    for stage in profile.stages:
        contract = contracts_by_stage[stage]
        stage_sensors = [
            sensor
            for sensor in sensors.for_stage(configured_sensors, stage, profile.id, True)
            if sensor.builtin == "stage-contract"
        ]
        if not stage_sensors:
            raise FlowError(
                f"profile {profile.id}: stage {stage!r} has no applicable stage-contract sensor"
            )
        if stage in profile.gates:
            if not any(sensor.required for sensor in stage_sensors):
                raise FlowError(
                    f"profile {profile.id}: gated stage {stage!r} needs a required "
                    "stage-contract sensor"
                )
            missing_paths = [
                output.id
                for output in contract.outputs
                if output.required and output.path is None
            ]
            if missing_paths:
                raise FlowError(
                    f"profile {profile.id}: gated stage {stage!r} has required outputs "
                    f"without a path: {', '.join(missing_paths)}"
                )
        checked_paths.update(
            output.path
            for output in contract.outputs
            if output.required and output.path is not None
        )
    if len(checked_paths) > MAX_OUTPUTS:
        raise FlowError(
            f"profile {profile.id}: contract outputs exceed the {MAX_OUTPUTS}-file limit"
        )


def _output_path(feature_dir: Path, relative: str) -> tuple[Path | None, str | None]:
    try:
        root = feature_dir.resolve(strict=True)
    except OSError as exc:
        return None, f"feature directory inaccessible ({type(exc).__name__})"
    current = root
    parts = relative.split("/")
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None, "missing"
        except OSError as exc:
            return None, f"inaccessible ({type(exc).__name__})"
        reparse = bool(getattr(info, "st_file_attributes", 0) & 0x400)
        if stat.S_ISLNK(info.st_mode) or reparse:
            return None, "symlink or reparse point"
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            return None, "parent is not a directory"
    try:
        resolved = current.resolve(strict=True)
    except OSError as exc:
        return None, f"inaccessible ({type(exc).__name__})"
    if not resolved.is_relative_to(root):
        return None, "path escapes feature directory"
    if not stat.S_ISREG(info.st_mode):
        return None, "not a regular file"
    if info.st_size == 0:
        return None, "empty"
    if info.st_size > MAX_OUTPUT_BYTES:
        return None, f"exceeds {MAX_OUTPUT_BYTES}-byte limit"
    return resolved, None


def check_outputs(
    feature_dir: Path, stage: str, specify_dir: Path = DEFAULT_SPECIFY_DIR
) -> tuple[bool, str]:
    """Check current required, path-addressable outputs without reading contents."""
    contract = load_contracts(specify_dir).get(stage)
    if contract is None:
        raise FlowError(f"no stage contract found for {stage!r}")
    required = [output for output in contract.outputs if output.required]
    if not required:
        return True, "no required outputs"
    problems: list[str] = []
    unchecked: list[str] = []
    for output in required:
        if output.path is None:
            unchecked.append(output.id)
            continue
        _, problem = _output_path(feature_dir, output.path)
        if problem:
            problems.append(f"{output.path} {problem}")
    details = problems + ([f"not path-checkable: {', '.join(unchecked)}"] if unchecked else [])
    if problems:
        return False, "; ".join(details)
    if unchecked:
        return True, "; ".join(details)
    return True, f"{len(required)} required output(s) present and non-empty"


def fingerprints(
    feature_dir: Path, stage: str, specify_dir: Path = DEFAULT_SPECIFY_DIR
) -> dict[str, str]:
    """Return bounded content hashes for the contract and path-bound required outputs."""
    contract = load_contracts(specify_dir).get(stage)
    if contract is None:
        raise FlowError(f"no stage contract found for {stage!r}")
    encoded = json.dumps(contract.to_dict(), sort_keys=True, separators=(",", ":")).encode()
    result = {f"contract:{stage}": hashlib.sha256(encoded).hexdigest()}
    for output in contract.outputs:
        if not output.required or output.path is None:
            continue
        key = f"output:{output.path}"
        path, problem = _output_path(feature_dir, output.path)
        if problem:
            result[key] = hashlib.sha256(problem.encode()).hexdigest()
            continue
        try:
            if path is None:
                data = b""
            else:
                with path.open("rb") as handle:
                    data = handle.read(MAX_OUTPUT_BYTES + 1)
        except OSError as exc:
            raise FlowError(
                f"cannot fingerprint contract output {output.path!r}: {type(exc).__name__}"
            ) from exc
        if len(data) > MAX_OUTPUT_BYTES:
            result[key] = hashlib.sha256(b"oversized").hexdigest()
        else:
            result[key] = hashlib.sha256(data).hexdigest()
    return result
