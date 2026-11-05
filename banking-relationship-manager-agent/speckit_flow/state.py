from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from speckit_flow import audit, reviews
from speckit_flow import sensors as sensors_mod
from speckit_flow.models import (
    STAGES,
    FeatureState,
    FlowError,
    Profile,
    Route,
    StageRecord,
)
from speckit_flow.profiles import get_profile

STATE_FILE = "state.json"
STATE_MD = "state.md"
ROUTE_FILE = "route.json"
OPTIONAL_STAGES = ("ideation", "deploy", "operate")
_ARTIFACTS = {"specify": "spec.md", "plan": "plan.md", "tasks": "tasks.md"}
_PROFILE_RE = re.compile(r"profile=([a-z][a-z0-9-]*)")


def atomic_write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except OSError as exc:
        Path(tmp).unlink(missing_ok=True)
        raise FlowError(f"cannot write {path.name}: {exc}") from exc


def load_state(feature_dir: Path) -> FeatureState:
    path = feature_dir / STATE_FILE
    if not path.exists():
        raise FlowError(f"{STATE_FILE} not found; run 'init' (or 'rebuild') first")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"{STATE_FILE} is corrupt: {exc}") from exc
    return FeatureState.from_dict(data)


def save_state(feature_dir: Path, state: FeatureState) -> None:
    state.revision += 1
    state.updated_at = audit.now_iso()
    atomic_write(feature_dir / STATE_FILE, json.dumps(state.to_dict(), indent=2) + "\n")
    atomic_write(feature_dir / STATE_MD, render_markdown(state))


def route_stages(state: FeatureState) -> list[str]:
    return [s for s in STAGES if s in state.stages and state.stages[s].status != "skipped"]


def next_stage(state: FeatureState) -> str | None:
    for stage in route_stages(state):
        if state.stages[stage].status in ("pending", "in_progress"):
            return stage
    return None


def render_markdown(state: FeatureState) -> str:
    lines = [
        f"# Workflow State: {state.feature}",
        "",
        f"- **Profile**: {state.profile} ({state.depth})",
        f"- **Current stage**: {state.current_stage or 'none (finished)'}",
        f"- **Pending gate**: {state.pending_gate or 'none'}",
        f"- **Revision**: {state.revision} (updated {state.updated_at})",
        "",
        "| Stage | Status | Note |",
        "|-------|--------|------|",
    ]
    for stage in STAGES:
        record = state.stages.get(stage)
        if record:
            lines.append(f"| {stage} | {record.status} | {record.reason or ''} |")
    return "\n".join(lines) + "\n"


def _set(state: FeatureState, stage: str, status: str, reason: str | None = None) -> None:
    state.stages[stage] = StageRecord(status=status, reason=reason, updated_at=audit.now_iso())


def _refresh_current(state: FeatureState) -> None:
    state.current_stage = next_stage(state)


def _reject(feature_dir: Path, stage: str | None, actor: str, message: str) -> FlowError:
    """Record a failure event (best effort) and return the error to raise."""
    try:
        audit.append_event(feature_dir, "failure", stage, actor, message[:400])
    except FlowError:
        pass
    return FlowError(message)


def _build_state(feature_dir: Path, profile: Profile) -> FeatureState:
    state = FeatureState(feature=feature_dir.name, profile=profile.id, depth=profile.depth)
    for stage in STAGES:
        if stage in profile.stages:
            _set(state, stage, "pending")
        elif stage not in OPTIONAL_STAGES:
            _set(state, stage, "skipped", f"not in profile {profile.id}")
    return state


def init_state(
    feature_dir: Path, profile_id: str, actor: str, profiles_dir: Path | None = None
) -> FeatureState:
    if not feature_dir.is_dir():
        raise FlowError(f"feature directory not found: {feature_dir}")
    if (feature_dir / STATE_FILE).exists():
        raise FlowError("already initialized; use 'switch' to change the profile")
    profile = _lookup(profile_id, profiles_dir)
    return init_from_route(feature_dir, Route(profile, {}), actor)


def _lookup(profile_id: str, profiles_dir: Path | None) -> Profile:
    return (
        get_profile(profile_id) if profiles_dir is None else get_profile(profile_id, profiles_dir)
    )


def load_route(feature_dir: Path) -> Route:
    path = feature_dir / ROUTE_FILE
    try:
        route = Route.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"{ROUTE_FILE} is unreadable: {exc}") from exc
    route.validate(feature_dir.name)
    return route


def profile_for(feature_dir: Path, profile_id: str, profiles_dir: Path | None) -> Profile:
    """Resolve a profile id; a composed route lives in the feature folder."""
    if profile_id == f"custom-{feature_dir.name}" and (feature_dir / ROUTE_FILE).exists():
        return load_route(feature_dir).profile
    return _lookup(profile_id, profiles_dir)


def init_from_route(feature_dir: Path, route: Route, actor: str) -> FeatureState:
    """Initialize state from an already validated and saved route."""
    if not feature_dir.is_dir():
        raise FlowError(f"feature directory not found: {feature_dir}")
    if (feature_dir / STATE_FILE).exists():
        raise FlowError("already initialized; use 'switch' to change the profile")
    profile = route.profile
    state = _build_state(feature_dir, profile)
    audit.append_event(
        feature_dir, "profile_selected", None, actor, f"profile={profile.id} depth={profile.depth}"
    )
    for stage in STAGES:
        record = state.stages.get(stage)
        if record is not None and record.status == "skipped":
            audit.append_event(feature_dir, "stage_skipped", stage, actor, record.reason or "")
    _refresh_current(state)
    save_state(feature_dir, state)
    return state


def begin_workflow(
    feature_dir: Path,
    expected_stages: list[str],
    expected_gates: list[str],
    actor: str,
    profiles_dir: Path | None = None,
) -> FeatureState:
    """Initialize the default route once, or verify existing state for a workflow run."""
    if not feature_dir.is_dir():
        raise FlowError(f"feature directory not found: {feature_dir}")
    if not expected_stages:
        raise FlowError("workflow stages must not be empty")
    if len(set(expected_stages)) != len(expected_stages):
        raise FlowError("workflow stages must not contain duplicates")
    if len(set(expected_gates)) != len(expected_gates):
        raise FlowError("workflow gates must not contain duplicates")
    for stage in expected_stages:
        if stage not in STAGES:
            raise FlowError(f"unknown workflow stage {stage!r}")
    stage_order = [STAGES.index(stage) for stage in expected_stages]
    if stage_order != sorted(stage_order):
        raise FlowError(f"workflow stages must be in canonical order {list(STAGES)}")
    for gate in expected_gates:
        if gate not in STAGES:
            raise FlowError(f"unknown workflow gate {gate!r}")
        if gate not in expected_stages:
            raise FlowError(f"workflow gate {gate!r} is not in workflow stages")
    gate_order = [STAGES.index(gate) for gate in expected_gates]
    if gate_order != sorted(gate_order):
        raise FlowError(f"workflow gates must be in canonical order {list(STAGES)}")

    def check_profile(profile: Profile) -> None:
        if list(profile.stages) != expected_stages or list(profile.gates) != expected_gates:
            raise FlowError(
                f"profile {profile.id!r} does not match this workflow; "
                f"expected stages {expected_stages} and gates {expected_gates}, "
                f"found stages {list(profile.stages)} and gates {list(profile.gates)}. "
                "Use the speckit-profile skill for a different route."
            )

    state_path = feature_dir / STATE_FILE
    broken = audit.verify_chain(feature_dir)
    if broken:
        raise FlowError(f"audit trail integrity problem: {broken}")
    if state_path.exists():
        state = load_state(feature_dir)
        profile = profile_for(feature_dir, state.profile, profiles_dir)
        check_profile(profile)
        return state
    if (feature_dir / audit.AUDIT_FILE).exists():
        raise FlowError(
            f"{STATE_FILE} is missing but {audit.AUDIT_FILE} exists; "
            "run 'rebuild' to recover explicitly"
        )
    profile = _lookup("feature", profiles_dir)
    check_profile(profile)
    return init_state(feature_dir, "feature", actor, profiles_dir)


def start_stage(feature_dir: Path, stage: str, actor: str) -> FeatureState:
    state = load_state(feature_dir)
    if stage not in route_stages(state):
        raise _reject(
            feature_dir, stage, actor, f"stage {stage!r} is not in profile {state.profile}"
        )
    if state.pending_gate:
        raise _reject(
            feature_dir, stage, actor, f"gate for {state.pending_gate!r} must be decided first"
        )
    if audit.is_parked(feature_dir):
        raise _reject(feature_dir, stage, actor, "feature is parked; run 'intents unpark' first")
    if any(r.status == "in_progress" for r in state.stages.values()):
        raise _reject(feature_dir, stage, actor, "another stage is already in progress")
    if next_stage(state) != stage:
        raise _reject(
            feature_dir, stage, actor, f"out of order: next stage is {next_stage(state)!r}"
        )
    audit.append_event(feature_dir, "stage_started", stage, actor, "started")
    _set(state, stage, "in_progress")
    state.current_stage = stage
    save_state(feature_dir, state)
    return state


def done_stage(
    feature_dir: Path, stage: str, actor: str, profiles_dir: Path | None = None
) -> FeatureState:
    state = load_state(feature_dir)
    if state.stages.get(stage, StageRecord()).status != "in_progress":
        raise _reject(feature_dir, stage, actor, f"stage {stage!r} is not in progress")
    profile = profile_for(feature_dir, state.profile, profiles_dir)
    gated = stage in profile.gates
    audit.append_event(
        feature_dir,
        "stage_completed",
        stage,
        actor,
        "completed; awaiting gate" if gated else "completed",
    )
    _set(state, stage, "done")
    state.pending_gate = stage if gated else None
    _refresh_current(state)
    save_state(feature_dir, state)
    return state


def decide_gate(
    feature_dir: Path,
    stage: str,
    approve: bool,
    actor: str,
    reason: str = "",
    override_reason: str = "",
    sensors_file: Path | None = None,
) -> FeatureState:
    state = load_state(feature_dir)
    if not actor.startswith("human:"):
        raise _reject(feature_dir, stage, actor, "only a human can approve or reject a gate")
    if state.pending_gate != stage:
        raise _reject(feature_dir, stage, actor, f"no pending gate for stage {stage!r}")
    detail = reason or ("approved" if approve else "rejected")
    review_note = ""
    if approve and sensors_file is not None:
        try:
            problems, relied = sensors_mod.gate_problems(feature_dir, stage, sensors_file)
        except FlowError as exc:
            raise _reject(
                feature_dir, stage, actor, f"sensor configuration invalid: {exc}"
            ) from exc
        if problems:
            raise _reject(feature_dir, stage, actor, "; ".join(problems))
        if relied:
            review_note = " sensors=" + ",".join(relied)
    if approve:
        review = reviews.latest_review(feature_dir, stage)
        fresh = review if review and not reviews.is_stale(feature_dir, review) else None
        if state.depth == "comprehensive" and fresh is None:
            why = "is stale" if review else "is missing"
            raise _reject(
                feature_dir,
                stage,
                actor,
                f"comprehensive depth needs a current review for {stage!r}; it {why}",
            )
        if fresh is not None:
            review_note += f" review={fresh.id}"
            if fresh.verdict == "block":
                if not override_reason:
                    raise _reject(
                        feature_dir,
                        stage,
                        actor,
                        f"review {fresh.id} blocks this gate; use --override-reason to proceed",
                    )
                if not actor.startswith("human:"):
                    raise _reject(feature_dir, stage, actor, "only a human can override a block")
                audit.append_event(
                    feature_dir,
                    "gate_overridden",
                    stage,
                    actor,
                    f"review={fresh.id} reason={override_reason}"[:500],
                )
    audit.append_event(
        feature_dir,
        "gate_approved" if approve else "gate_rejected",
        stage,
        actor,
        (detail + review_note)[:500],
    )
    state.pending_gate = None
    if not approve:
        _set(state, stage, "pending", f"rejected: {detail}")
    _refresh_current(state)
    save_state(feature_dir, state)
    return state


def switch_profile(
    feature_dir: Path,
    profile_id: str,
    actor: str,
    confirm: bool,
    profiles_dir: Path | None = None,
) -> FeatureState:
    state = load_state(feature_dir)
    if not confirm:
        raise _reject(feature_dir, None, actor, "profile change requires --confirm")
    if state.pending_gate or any(r.status == "in_progress" for r in state.stages.values()):
        raise _reject(feature_dir, None, actor, "profile can only change at a stage boundary")
    profile = _lookup(profile_id, profiles_dir)
    audit.append_event(
        feature_dir,
        "profile_changed",
        None,
        actor,
        f"profile={profile.id} depth={profile.depth} (was {state.profile})",
    )
    for stage in STAGES:
        existing = state.stages.get(stage)
        if existing is not None and existing.status == "done":
            continue
        if stage in profile.stages:
            _set(state, stage, "pending")
        elif existing is not None or stage not in OPTIONAL_STAGES:
            reason = f"not in profile {profile.id}"
            audit.append_event(feature_dir, "stage_skipped", stage, actor, reason)
            _set(state, stage, "skipped", reason)
    state.profile, state.depth = profile.id, profile.depth
    _refresh_current(state)
    save_state(feature_dir, state)
    return state


def last_profile_from_audit(feature_dir: Path) -> str | None:
    for event in reversed(audit.read_events(feature_dir)):
        if event.type in ("profile_selected", "profile_changed"):
            match = _PROFILE_RE.search(event.detail)
            if match:
                return match.group(1)
    return None


def rebuild_state(
    feature_dir: Path,
    actor: str,
    profile_id: str | None = None,
    profiles_dir: Path | None = None,
) -> FeatureState:
    """Reconstruct state from existing artifacts; the profile comes from the audit trail."""
    if not feature_dir.is_dir():
        raise FlowError(f"feature directory not found: {feature_dir}")
    chosen = profile_id or last_profile_from_audit(feature_dir) or "feature"
    profile = profile_for(feature_dir, chosen, profiles_dir)
    state = _build_state(feature_dir, profile)
    for stage, artifact in _ARTIFACTS.items():
        if stage in profile.stages and (feature_dir / artifact).exists():
            _set(state, stage, "done", f"rebuilt from {artifact}")
    _refresh_current(state)
    audit.append_event(
        feature_dir, "profile_selected", None, actor, f"rebuilt state; profile={profile.id}"
    )
    save_state(feature_dir, state)
    return state
