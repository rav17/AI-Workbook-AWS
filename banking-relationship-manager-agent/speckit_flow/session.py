from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from speckit_flow import audit
from speckit_flow import state as flow_state
from speckit_flow.models import STAGES, FeatureState, FlowError

_POINTER = Path(".specify") / "feature.json"


@dataclass
class Intent:
    name: str
    profile: str
    current_stage: str | None
    pending_gate: str | None
    parked: bool
    active: bool

    def to_dict(self) -> dict[str, object]:
        return dict(vars(self))

    def line(self) -> str:
        mark = "*" if self.active else " "
        tail = " [parked]" if self.parked else ""
        return (
            f"{mark} {self.name:36} {self.profile:14} stage={self.current_stage or '-'} "
            f"gate={self.pending_gate or '-'}{tail}"
        )


def _active_name(root: Path) -> str | None:
    try:
        data = json.loads((root / _POINTER).read_text(encoding="utf-8"))
        return Path(str(data["feature_directory"]).replace("\\", "/")).name
    except (OSError, ValueError, KeyError):
        return None


def list_intents(root: Path) -> list[Intent]:
    active = _active_name(root)
    intents: list[Intent] = []
    for state_file in sorted((root / "specs").glob(f"*/{flow_state.STATE_FILE}")):
        feature_dir = state_file.parent
        try:
            st = flow_state.load_state(feature_dir)
            parked = audit.is_parked(feature_dir)
        except FlowError:
            continue
        intents.append(
            Intent(
                feature_dir.name,
                st.profile,
                st.current_stage,
                st.pending_gate,
                parked,
                feature_dir.name == active,
            )
        )
    return intents


def switch_intent(root: Path, name: str, actor: str) -> Path:
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        raise FlowError("intent name must be a feature directory name")
    feature_dir = root / "specs" / name
    if not (feature_dir / flow_state.STATE_FILE).is_file():
        raise FlowError(f"no initialized feature named {name!r}")
    audit.append_event(feature_dir, "intent_switched", None, actor, "active")
    flow_state.atomic_write(
        root / _POINTER, json.dumps({"feature_directory": f"specs\\{name}"}, indent=None)
    )
    return feature_dir


def park(feature_dir: Path, actor: str, reason: str = "") -> None:
    flow_state.load_state(feature_dir)
    if audit.is_parked(feature_dir):
        raise flow_state._reject(feature_dir, None, actor, "feature is already parked")
    audit.append_event(feature_dir, "intent_parked", None, actor, reason or "parked")


def unpark(feature_dir: Path, actor: str) -> None:
    flow_state.load_state(feature_dir)
    if not audit.is_parked(feature_dir):
        raise flow_state._reject(feature_dir, None, actor, "feature is not parked")
    audit.append_event(feature_dir, "intent_resumed", None, actor, "resumed")


def redo_stage(feature_dir: Path, stage: str, actor: str, reason: str) -> FeatureState:
    state = flow_state.load_state(feature_dir)
    if not actor.startswith("human:"):
        raise flow_state._reject(feature_dir, stage, actor, "only a human can redo a stage")
    if not reason.strip():
        raise flow_state._reject(feature_dir, stage, actor, "redo needs a --reason")
    route = flow_state.route_stages(state)
    if stage not in route:
        raise flow_state._reject(feature_dir, stage, actor, f"stage {stage!r} is not in the route")
    if state.stages[stage].status == "pending":
        raise flow_state._reject(
            feature_dir, stage, actor, f"stage {stage!r} has not been reached; nothing to redo"
        )
    reset = [s for s in STAGES if s in route and STAGES.index(s) >= STAGES.index(stage)]
    audit.append_event(
        feature_dir,
        "stage_redone",
        stage,
        actor,
        f"from={stage} reset={','.join(reset)} reason={reason}"[:500],
    )
    for name in reset:
        flow_state._set(state, name, "pending", f"redo: {reason}"[:200])
    state.pending_gate = None
    flow_state._refresh_current(state)
    flow_state.save_state(feature_dir, state)
    return state
