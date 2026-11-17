from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from speckit_flow import audit, questions, reviews, trace
from speckit_flow import sensors as sensors_mod
from speckit_flow import units as units_mod
from speckit_flow.models import (
    OPTIONAL_STAGES,
    STAGE_CONDITIONS,
    STAGES,
    FeatureState,
    FlowError,
    Profile,
    ReviewSelectionError,
    Route,
    StageRecord,
)
from speckit_flow.profiles import get_profile

STATE_FILE = "state.json"
STATE_MD = "state.md"
ROUTE_FILE = "route.json"
HYBRID_ROUTE_FILE = "hybrid-route.json"
HYBRID_PROFILE = "hybrid-plan"
SELECTIVE_ROUTE_FILE = "selective-route.json"
_ARTIFACTS = {"specify": "spec.md", "plan": "plan.md", "tasks": "tasks.md"}
_PROFILE_RE = re.compile(r"profile=([a-z][a-z0-9-]*)")
TEST_GATED = ("tasks", "analyze", "implement")


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
    feature_dir: Path,
    profile_id: str,
    actor: str,
    profiles_dir: Path | None = None,
    *,
    reviewer: str | None = None,
    confirm_route: bool = False,
    rationale: str = "",
    roster_file: Path | None = None,
) -> FeatureState:
    if not feature_dir.is_dir():
        raise FlowError(f"feature directory not found: {feature_dir}")
    if (feature_dir / STATE_FILE).exists():
        raise FlowError("already initialized; use 'switch' to change the profile")
    profile = _lookup(profile_id, profiles_dir)
    if profile.execution == "selective":
        if reviewer is not None:
            raise FlowError("selective workers must be declared in profile assignments")
        if not confirm_route or not rationale.strip() or len(rationale.strip()) > 150:
            raise FlowError(
                "selective route requires --confirm-route and a 1-150 character rationale"
            )
        audit.check_redaction(rationale)
        from speckit_flow import agents

        roster = agents.load_roster(roster_file or agents.DEFAULT_ROSTER_FILE)
        assignments = agents.resolve_assignments(profile, roster)
        for stage, assignment in assignments.items():
            for name in assignment["support"]:
                worker = roster[name]
                if name == "hybrid-plan-reviewer":
                    raise FlowError("the no-tool hybrid reviewer requires the hybrid-plan route")
                if worker.role not in ("domain", "reviewer") or stage not in worker.supports:
                    raise FlowError(f"selective worker {name!r} cannot support {stage!r}")
            if not profile.ceremony_on("reviews") and any(
                roster[name].role == "reviewer" for name in assignment["support"]
            ):
                raise FlowError("selective route cannot disable assigned reviewers")
            if profile.strict and stage in profile.gates and not any(
                roster[name].role == "reviewer" for name in assignment["support"]
            ):
                raise FlowError(f"strict selective gate {stage!r} needs an explicit reviewer")
        if profile.stage_contracts:
            from speckit_flow import contracts

            contracts.validate_profile(profile, feature_dir.parent.parent / ".specify")
        path = feature_dir / SELECTIVE_ROUTE_FILE
        if path.exists() or (feature_dir / audit.AUDIT_FILE).exists():
            raise FlowError("selective route or audit already exists; inspect before initializing")
        content = json.dumps(
            {"profile": profile.to_dict(), "rationale": rationale.strip()}, sort_keys=True, indent=2
        ) + "\n"
        atomic_write(path, content)
        return init_from_route(
            feature_dir, Route(profile, {}), actor, route_binding=_route_digest(content.encode())
        )
    if profile.execution == "hybrid":
        if not confirm_route:
            raise FlowError("hybrid route must be explicitly confirmed before initialization")
        from speckit_flow import agents

        roster = agents.load_roster(roster_file or agents.DEFAULT_ROSTER_FILE)
        if not reviewer or not reviewer.strip():
            raise ReviewSelectionError(
                "missing_reviewer_selection",
                "reviewer selection is missing.",
                "Select an eligible independent plan reviewer, then initialize the route.",
            )
        selected = roster.get(reviewer or "")
        lead = agents.resolve_assignments(profile, roster)["plan"]["lead"]
        if (
            selected is None
            or selected.role != "reviewer"
            or selected.can_edit
            or "plan" not in selected.supports
            or selected.id == lead
        ):
            raise ReviewSelectionError(
                "invalid_reviewer_selection",
                "reviewer selection is invalid or ineligible.",
                "Choose an eligible independent plan reviewer; do not substitute one silently.",
            )
        if not rationale.strip() or len(rationale.strip()) > 150:
            raise FlowError("hybrid reviewer rationale must be 1-150 characters")
        audit.check_redaction(rationale)
        path = feature_dir / HYBRID_ROUTE_FILE
        if path.exists() or (feature_dir / audit.AUDIT_FILE).exists():
            raise FlowError("hybrid route or audit already exists; inspect before initializing")
        payload = {
            "profile": profile.to_dict(),
            "reviewer": selected.id,
            "rationale": rationale.strip(),
        }
        content = json.dumps(payload, sort_keys=True, indent=2) + "\n"
        binding = _route_digest(content.encode("utf-8"))
        atomic_write(path, content)
        return init_from_route(feature_dir, Route(profile, {}), actor, route_binding=binding)
    if reviewer is not None or confirm_route or rationale:
        raise FlowError("reviewer selection is only supported for the hybrid plan profile")
    return init_from_route(feature_dir, Route(profile, {}), actor)


def _route_digest(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    return "-".join(digest[i : i + 8] for i in range(0, len(digest), 8))


def load_hybrid_route(feature_dir: Path) -> dict[str, Any]:
    path = feature_dir / HYBRID_ROUTE_FILE
    try:
        content = path.read_bytes()
        payload = json.loads(content)
    except (OSError, ValueError) as exc:
        raise FlowError(f"hybrid route is unreadable: {exc}") from exc
    snapshot = audit.snapshot(feature_dir)
    if snapshot.problem or not snapshot.event_count:
        raise FlowError("hybrid route audit is missing or invalid")
    binding = f"route={_route_digest(content)}"
    events = audit.read_events(feature_dir)
    if not any(
        event.type == "profile_selected"
        and f"profile={HYBRID_PROFILE}" in event.detail
        and binding in event.detail.split()
        for event in events
    ):
        raise FlowError("confirmed hybrid route changed or has no matching audit evidence")
    if (
        not isinstance(payload, dict)
        or set(payload) != {"profile", "reviewer", "rationale"}
        or not isinstance(payload["profile"], dict)
        or not isinstance(payload["reviewer"], str)
        or not isinstance(payload["rationale"], str)
        or not payload["rationale"].strip()
    ):
        raise FlowError("confirmed hybrid route is malformed")
    return payload


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
    selective_path = feature_dir / SELECTIVE_ROUTE_FILE
    if profile_id == "selective" or selective_path.exists():
        try:
            if selective_path.is_symlink() or (
                getattr(selective_path.lstat(), "st_file_attributes", 0) & 0x400
            ):
                raise FlowError("selective route must not be a link or reparse point")
            if selective_path.stat().st_size > 256 * 1024:
                raise FlowError("selective route exceeds 256 KiB")
            content = selective_path.read_bytes()
            payload = json.loads(content)
        except (OSError, ValueError) as exc:
            raise FlowError(f"selective route is unreadable: {exc}") from exc
        if (
            not isinstance(payload, dict) or set(payload) != {"profile", "rationale"}
            or not isinstance(payload["profile"], dict)
            or not isinstance(payload["rationale"], str) or not payload["rationale"].strip()
        ):
            raise FlowError("confirmed selective route is malformed")
        snapshot = audit.snapshot(feature_dir)
        if snapshot.problem or not snapshot.event_count:
            raise FlowError("selective route audit is missing or invalid")
        binding = f"route={_route_digest(content)}"
        if not any(
            event.type == "profile_selected"
            and f"profile={profile_id}" in event.detail.split()
            and binding in event.detail.split()
            for event in audit.read_events(feature_dir)
        ):
            raise FlowError("selective route changed or has no matching confirmation evidence")
        selected = Profile.from_dict(payload["profile"], profile_id)
        if selected.execution != "selective":
            raise FlowError("confirmed selective route has invalid execution")
        return selected
    if profile_id == HYBRID_PROFILE:
        return Profile.from_dict(load_hybrid_route(feature_dir)["profile"], HYBRID_PROFILE)
    if profile_id == f"custom-{feature_dir.name}" and (feature_dir / ROUTE_FILE).exists():
        return load_route(feature_dir).profile
    profile = _lookup(profile_id, profiles_dir)
    if profile.execution == "selective":
        raise FlowError("confirmed selective route is missing")
    return profile


def init_from_route(
    feature_dir: Path, route: Route, actor: str, *, route_binding: str = ""
) -> FeatureState:
    """Initialize state from an already validated and saved route."""
    if not feature_dir.is_dir():
        raise FlowError(f"feature directory not found: {feature_dir}")
    if (feature_dir / STATE_FILE).exists():
        raise FlowError("already initialized; use 'switch' to change the profile")
    profile = route.profile
    if profile.execution == "hybrid" and not route_binding:
        raise FlowError("hybrid initialization requires a confirmed reviewer selection")
    if profile.execution == "selective" and not route_binding:
        raise FlowError("selective initialization requires a confirmed worker route")
    if profile.stage_contracts:
        from speckit_flow import contracts

        contracts.validate_profile(profile, feature_dir.parent.parent / ".specify")
    state = _build_state(feature_dir, profile)
    audit.append_event(
        feature_dir,
        "profile_selected",
        None,
        actor,
        f"profile={profile.id} depth={profile.depth}"
        + (f" route={route_binding}" if route_binding else ""),
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


def start_stage(
    feature_dir: Path, stage: str, actor: str, profiles_dir: Path | None = None,
) -> FeatureState:
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
    if STAGE_CONDITIONS.get(stage) == "existing-codebase":
        from speckit_flow import codebase

        try:
            profile = profile_for(feature_dir, state.profile, profiles_dir)
            profile.validate()
            if stage in profile.gates:
                raise FlowError(f"conditional stage {stage!r} cannot be a gate")
            inventory = codebase.scan()
        except FlowError as exc:
            raise _reject(feature_dir, stage, actor, str(exc)) from exc
        if not inventory.existing:
            reason = "existing-codebase: no recognized application source (heuristic)"
            audit.append_event(feature_dir, "stage_skipped", stage, actor, reason)
            _set(state, stage, "skipped", reason)
            _refresh_current(state)
            save_state(feature_dir, state)
            return state
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
    from speckit_flow import calls

    if profiles_dir is None:
        calls.check_completion(feature_dir, stage)
    else:
        calls.check_completion(feature_dir, stage, profiles_dir)
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
    profiles_dir: Path | None = None,
) -> FeatureState:
    state = load_state(feature_dir)
    if not actor.startswith("human:"):
        raise _reject(feature_dir, stage, actor, "only a human can approve or reject a gate")
    if state.pending_gate != stage:
        raise _reject(feature_dir, stage, actor, f"no pending gate for stage {stage!r}")
    detail = reason or ("approved" if approve else "rejected")
    review_note = ""
    selected_blocks: list[str] = []
    try:
        profile = profile_for(feature_dir, state.profile, profiles_dir)
    except FlowError as exc:
        raise _reject(feature_dir, stage, actor, f"profile cannot be loaded: {exc}") from exc
    strict = profile.strict
    if approve and profile.execution == "hybrid" and stage == "plan":
        try:
            reviews.require_hybrid_review(feature_dir)
        except FlowError as exc:
            raise _reject(feature_dir, stage, actor, str(exc)) from exc
    if approve and profile.execution == "selective":
        from speckit_flow import calls

        try:
            selected_blocks = calls.check_selective_reviews(
                feature_dir, stage, profile, reject_blocks=not bool(override_reason)
            )
        except FlowError as exc:
            raise _reject(feature_dir, stage, actor, str(exc)) from exc
    if approve and profile.test_strategy == "required" and stage in TEST_GATED:
        try:
            matrix = trace.build_matrix(feature_dir)
        except FlowError as exc:
            raise _reject(
                feature_dir, stage, actor, f"invalid requirement trace: {exc}"
            ) from exc
        if not matrix.ok(True):
            gaps = ", ".join(matrix.uncovered + matrix.untested + matrix.unknown_refs)
            raise _reject(
                feature_dir, stage, actor,
                f"test strategy 'required': uncovered, untested or unknown references: {gaps}",
            )
    if approve and stage == "implement":
        try:
            unchecked = units_mod.unchecked_units(feature_dir)
        except FlowError as exc:
            raise _reject(
                feature_dir, stage, actor, f"invalid unit checkpoint evidence: {exc}"
            ) from exc
        if unchecked:
            raise _reject(
                feature_dir, stage, actor,
                f"units not checkpointed or stale: {', '.join(unchecked)}",
            )
    if approve and strict and questions.open_questions(feature_dir):
        raise _reject(feature_dir, stage, actor, "strict guard policy: open questions remain")
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
        if strict and fresh is None:
            why = "is stale" if review else "is missing"
            raise _reject(
                feature_dir,
                stage,
                actor,
                f"strict guard policy needs a current review for {stage!r}; it {why}",
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
        if selected_blocks and override_reason and (
            fresh is None or fresh.id not in selected_blocks
        ):
            audit.append_event(
                feature_dir, "gate_overridden", stage, actor,
                f"reviews={','.join(selected_blocks)} reason={override_reason}"[:500],
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
    if profile.execution == "selective" or (feature_dir / SELECTIVE_ROUTE_FILE).exists():
        raise _reject(
            feature_dir, None, actor,
            "selective routes cannot be switched; explicitly initialize a new confirmed feature",
        )
    if profile.execution == "hybrid" or state.profile == HYBRID_PROFILE:
        raise _reject(
            feature_dir, None, actor, "hybrid routes cannot be switched in this increment"
        )
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
    if chosen == HYBRID_PROFILE:
        raise FlowError("hybrid state cannot be rebuilt from artifacts without review evidence")
    profile = profile_for(feature_dir, chosen, profiles_dir)
    if profile.execution == "selective":
        raise FlowError("selective state cannot be rebuilt from artifacts without worker evidence")
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
