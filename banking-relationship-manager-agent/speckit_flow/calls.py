from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from speckit_flow import agents, audit, orchestration, state
from speckit_flow.models import AuditEvent, FlowError, Profile
from speckit_flow.profiles import DEFAULT_PROFILES_DIR

LOCK_FILE = ".calls.lock"
INLINE_ARTIFACTS = {
    "specify": "spec.md", "clarify": "spec.md", "plan": "plan.md",
    "tasks": "tasks.md", "analyze": "tasks.md", "implement": "tasks.md",
}


@dataclass
class Call:
    id: int
    agent: str
    status: str = "running"


@contextmanager
def _lock(feature_dir: Path) -> Iterator[None]:
    path = feature_dir / LOCK_FILE
    try:
        handle = path.open("x", encoding="utf-8")
    except OSError as exc:
        raise FlowError(
            f"cannot acquire call-accounting lock: {exc}; stop, inspect concurrent "
            "commands, and have a human resolve any abandoned lock"
        ) from exc
    try:
        with handle:
            yield
    finally:
        path.unlink()


def _events(feature_dir: Path) -> list[AuditEvent]:
    snapshot = audit.snapshot(feature_dir)
    if snapshot.problem or not snapshot.event_count:
        raise FlowError(f"invalid call audit: {snapshot.problem or 'missing or empty trail'}")
    return audit.read_events(feature_dir)


def _current(events: list[AuditEvent], stage: str) -> list[Call]:
    calls: dict[int, Call] = {}
    for event in events:
        if event.stage != stage:
            continue
        if event.type in ("stage_started", "calls_reset"):
            calls.clear()
        elif event.type == "call_reserved":
            calls[event.seq] = Call(event.seq, event.detail)
        elif event.type == "call_finished":
            try:
                data = json.loads(event.detail)
                call_id, outcome = data["id"], data["outcome"]
                if type(call_id) is not int or outcome not in ("succeeded", "failed"):
                    raise ValueError("invalid result")
                call = calls[call_id]
                if call.status != "running":
                    raise ValueError("duplicate result")
                call.status = outcome
            except (ValueError, KeyError, TypeError) as exc:
                raise FlowError(f"invalid call accounting at audit event {event.seq}") from exc
    return list(calls.values())


def _conductor(actor: str) -> None:
    if actor != "agent:conductor":
        raise FlowError("only agent:conductor may reserve or finish worker calls")


def _hybrid_caller(actor: str) -> None:
    if actor not in ("agent:conductor", "agent:workflow"):
        raise FlowError("hybrid reviewer calls require the workflow host or conductor")


def _selective(feature_dir: Path) -> bool:
    return (feature_dir / state.SELECTIVE_ROUTE_FILE).exists()


def _inline_digest(feature_dir: Path, stage: str) -> str:
    from speckit_flow import reviews, units

    primary = INLINE_ARTIFACTS[stage]
    hashes = {primary: reviews.fingerprint(feature_dir, primary)}
    for name in ("spec.md", "plan.md", "tasks.md"):
        if (feature_dir / name).is_file():
            hashes[name] = reviews.fingerprint(feature_dir, name)
    if stage == "implement":
        for unit in units.load_units(feature_dir):
            hashes.update(
                units.tracked_fingerprints(feature_dir.parent.parent, unit.get("files", []))
            )
    return state._route_digest(json.dumps(hashes, sort_keys=True).encode())


def _inline_events(events: list[AuditEvent], stage: str) -> list[AuditEvent]:
    current: list[AuditEvent] = []
    for event in events:
        if event.stage == stage:
            if event.type in ("stage_started", "calls_reset"):
                current.clear()
            elif event.type == "inline_work_recorded":
                current.append(event)
    return current


def record_inline(
    feature_dir: Path, stage: str, actor: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> None:
    _hybrid_caller(actor)
    with _lock(feature_dir):
        brief = orchestration.dispatch(feature_dir, stage, profiles_dir=profiles_dir)
        if brief["execution"] != "selective" or brief["stage_status"] != "in_progress":
            raise FlowError("inline accounting requires an in-progress selective stage")
        events = _events(feature_dir)
        current = _current(events, stage)
        if any(call.status != "succeeded" for call in current):
            raise FlowError("inline work cannot be recorded with running or failed calls")
        supports = {worker["id"] for worker in brief["support"]}
        if supports - {call.agent for call in current}:
            raise FlowError("inline work requires successful assigned supports first")
        anchors = _inline_events(events, stage)
        if len(anchors) >= 2:
            raise FlowError("inline revision budget exhausted; human reset required")
        if anchors and any(
            not any(call.agent == worker["id"] for call in current) for worker in brief["reviewers"]
        ):
            raise FlowError("inline revision requires initial assigned reviews")
        audit.append_event(
            feature_dir, "inline_work_recorded", stage, actor, _inline_digest(feature_dir, stage)
        )


def reserve(
    feature_dir: Path,
    stage: str,
    agent_id: str,
    actor: str,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    roster_file: Path = agents.DEFAULT_ROSTER_FILE,
    root: Path = agents.REPO_ROOT,
) -> dict[str, Any]:
    current_state = state.load_state(feature_dir)
    if current_state.profile == state.HYBRID_PROFILE or _selective(feature_dir):
        _hybrid_caller(actor)
    else:
        _conductor(actor)
    with _lock(feature_dir):
        brief = orchestration.dispatch(
            feature_dir, stage, profiles_dir=profiles_dir, roster_file=roster_file, root=root
        )
        if brief["status"] == "blocked":
            review_status = brief["review_status"]
            raise FlowError(
                f"dispatch blocked: {review_status['reason']} {review_status['next_action']}"
            )
        if brief["stage_status"] != "in_progress":
            raise FlowError("worker calls require a stage already in progress")
        hybrid = brief["execution"] == "hybrid" and stage == "plan"
        selective = brief["execution"] == "selective"
        if brief["execution"] != "delegated" and not hybrid and not selective:
            raise FlowError("worker calls require a delegated stage or selected hybrid reviewer")
        if hybrid and not (feature_dir / "plan.md").is_file():
            raise FlowError("hybrid reviewer cannot be invoked before inline plan.md exists")
        lead = brief["lead"]["id"]
        supports = {a["id"] for a in brief["support"]}
        reviewers = {a["id"] for a in brief["reviewers"]}
        if hybrid or selective:
            lead = ""
        if hybrid:
            supports.clear()
        if agent_id not in {lead, *supports, *reviewers}:
            raise FlowError(f"agent {agent_id!r} is not assigned to this stage")
        events = _events(feature_dir)
        calls = _current(events, stage)
        anchors = _inline_events(events, stage)
        if any(c.status == "failed" for c in calls):
            raise FlowError("worker invocation failed; human calls reset required before retry")
        previous = [c for c in calls if c.agent == agent_id]
        if any(c.status == "running" for c in previous):
            raise FlowError(f"duplicate dispatch: {agent_id!r} already has a running call")
        limit = 1 if hybrid or agent_id in supports else 2
        if len(previous) >= limit:
            raise FlowError(f"call budget exhausted for {agent_id!r}: limit {limit}")
        if agent_id in supports and any(c.agent == lead for c in calls):
            raise FlowError("domain support must finish before lead work")
        if selective and agent_id in supports and anchors:
            raise FlowError("domain support must finish before inline work")
        if selective and agent_id in reviewers:
            if not anchors or anchors[-1].detail != _inline_digest(feature_dir, stage):
                raise FlowError("review requires current recorded inline work")
            if previous and len(anchors) != 2:
                raise FlowError("follow-up review requires the single inline revision")
        if agent_id == lead:
            if any(
                not any(c.agent == s and c.status == "succeeded" for c in calls) for s in supports
            ):
                raise FlowError("lead requires successful assigned supports")
            if any(c.status == "running" for c in calls):
                raise FlowError("lead cannot run while other workers are active")
            if previous and any(not any(c.agent == r for c in calls) for r in reviewers):
                raise FlowError("revision requires the initial assigned reviews")
        if hybrid and (calls or agent_id not in reviewers):
            raise FlowError("hybrid plan permits one selected reviewer call after inline planning")
        if agent_id in reviewers and not hybrid and not selective:
            leads = [c for c in calls if c.agent == lead]
            if not leads or leads[-1].status != "succeeded":
                raise FlowError("review requires a successful lead call")
            if previous and len(leads) != 2:
                raise FlowError("follow-up review requires the single lead revision")
        plan: bytes | None = None
        if hybrid:
            from speckit_flow import host

            plan = host.plan_bytes(feature_dir)
        event = audit.append_event(feature_dir, "call_reserved", stage, actor, agent_id)
        request: dict[str, Any] = {}
        if hybrid:
            from speckit_flow import host

            request = host.bind_request(feature_dir, event, actor, plan=plan)
        return {
            "id": event.seq,
            "agent": agent_id,
            "stage": stage,
            "status": "running",
            "used": len(previous) + 1,
            "limit": limit,
            **request,
        }


def finish(feature_dir: Path, stage: str, call_id: int, outcome: str, actor: str) -> None:
    current_state = state.load_state(feature_dir)
    if current_state.profile == state.HYBRID_PROFILE or _selective(feature_dir):
        _hybrid_caller(actor)
    else:
        _conductor(actor)
    if outcome not in ("succeeded", "failed"):
        raise FlowError("call outcome must be succeeded or failed")
    with _lock(feature_dir):
        current = state.load_state(feature_dir)
        if stage not in current.stages or current.stages[stage].status != "in_progress":
            raise FlowError("call stage is not in progress")
        call = next((c for c in _current(_events(feature_dir), stage) if c.id == call_id), None)
        if call is None or call.status != "running":
            raise FlowError("call is not running in this stage attempt")
        audit.append_event(
            feature_dir,
            "call_finished",
            stage,
            actor,
            json.dumps({"id": call_id, "outcome": outcome}),
        )


def reset(feature_dir: Path, stage: str, actor: str, reason: str) -> None:
    if not actor.startswith("human:") or not reason.strip():
        raise FlowError("only a human may reset call budgets, with a nonempty reason")
    with _lock(feature_dir):
        current = state.load_state(feature_dir)
        if stage not in current.stages or current.stages[stage].status != "in_progress":
            raise FlowError("reset requires a stage in progress")
        calls = _current(_events(feature_dir), stage)
        if any(c.status == "running" for c in calls):
            raise FlowError("running workers must be stopped and recorded failed before reset")
        audit.append_event(feature_dir, "calls_reset", stage, actor, reason)


def status(feature_dir: Path, stage: str) -> list[dict[str, Any]]:
    if stage not in state.load_state(feature_dir).stages:
        raise FlowError(f"stage {stage!r} is not recorded for this feature")
    return [vars(c) for c in _current(_events(feature_dir), stage)]


def check_completion(
    feature_dir: Path, stage: str, profiles_dir: Path = DEFAULT_PROFILES_DIR
) -> None:
    """Keep legacy stages without reservations compatible."""
    events = _events(feature_dir)
    current_state = state.load_state(feature_dir)
    profile = state.profile_for(feature_dir, current_state.profile, profiles_dir)
    if profile.execution == "selective":
        brief = orchestration.dispatch(feature_dir, stage, profiles_dir=profiles_dir)
        current = _current(events, stage)
        anchors = _inline_events(events, stage)
        if not anchors or anchors[-1].detail != _inline_digest(feature_dir, stage):
            raise FlowError("selective stage needs current recorded inline work")
        if any(call.status != "succeeded" for call in current):
            raise FlowError("cannot complete stage with running or failed worker calls")
        assigned = {worker["id"] for worker in [*brief["support"], *brief["reviewers"]]}
        if assigned - {call.agent for call in current}:
            raise FlowError("cannot complete selective stage without assigned worker results")
        for reviewer in brief["reviewers"]:
            if not any(
                call.agent == reviewer["id"] and call.id > anchors[-1].seq for call in current
            ):
                raise FlowError("selective stage needs reviews of the latest inline work")
        check_selective_reviews(feature_dir, stage, profile)
        return
    if profile.execution == "hybrid" and stage == "plan":
        from speckit_flow import reviews

        reviewer_id = state.load_hybrid_route(feature_dir)["reviewer"]
        reviewer_calls = [c for c in _current(events, stage) if c.agent == reviewer_id]
        if not reviewer_calls:
            raise FlowError("hybrid plan review invocation is missing")
        if reviewer_calls[-1].status != "succeeded":
            raise FlowError("hybrid plan reviewer invocation failed")
        reviews.require_hybrid_review(feature_dir)
        return
    if not any(e.stage == stage and e.type == "call_reserved" for e in events):
        return
    calls = _current(events, stage)
    if any(c.status != "succeeded" for c in calls):
        raise FlowError("cannot complete stage with running or failed worker calls")
    brief = orchestration.dispatch(feature_dir, stage, profiles_dir=profiles_dir)
    assigned = {a["id"] for a in [brief["lead"], *brief["support"], *brief["reviewers"]]}
    missing = assigned - {c.agent for c in calls}
    if missing:
        raise FlowError(
            "cannot complete stage without assigned worker results: " + ", ".join(sorted(missing))
        )
    last_lead = max(c.id for c in calls if c.agent == brief["lead"]["id"])
    if any(
        not any(c.agent == reviewer["id"] and c.id > last_lead for c in calls)
        for reviewer in brief["reviewers"]
    ):
        raise FlowError("cannot complete stage before assigned reviews of the latest lead work")


def check_selective_reviews(
    feature_dir: Path, stage: str, profile: Profile, *, reject_blocks: bool = False,
) -> list[str]:
    """Bind required reviews to selected recorded calls, not merely a reviewer label."""
    from speckit_flow import reviews

    roster = agents.load_roster()
    assignment = agents.resolve_assignments(profile, roster)[stage]
    selected = [name for name in assignment["support"] if roster[name].role == "reviewer"]
    events = _events(feature_dir)
    current = _current(events, stage)
    anchors = _inline_events(events, stage)
    if not anchors or anchors[-1].detail != _inline_digest(feature_dir, stage):
        raise FlowError("selective inline evidence is missing or stale")
    saved = reviews.list_reviews(feature_dir, stage)
    blocks: list[str] = []
    for name in selected:
        matching = [
            call for call in current
            if call.agent == name and call.status == "succeeded" and call.id > anchors[-1].seq
        ]
        if not matching:
            raise FlowError(f"selected reviewer {name!r} has no current successful call")
        finish_seq = max(
            event.seq for event in events
            if event.type == "call_finished" and event.stage == stage
            and json.loads(event.detail)["id"] == matching[-1].id
        )
        recorded_ids = {
            event.detail.split()[0].removeprefix("review=")
            for event in events
            if event.type == "review_recorded" and event.stage == stage
            and event.actor == f"agent:{name}" and event.seq > finish_seq
        }
        current_reviews = [review for review in saved if review.id in recorded_ids]
        if not current_reviews:
            raise FlowError(f"selected reviewer {name!r} must save its actual review result")
        review = current_reviews[-1]
        if review.author != "agent:workflow" or reviews.is_stale(feature_dir, review):
            raise FlowError(f"selected reviewer {name!r} evidence is stale or has the wrong author")
        if INLINE_ARTIFACTS[stage] not in review.files:
            raise FlowError(f"selected reviewer {name!r} did not review the stage artifact")
        if review.verdict == "block":
            blocks.append(review.id)
    if reject_blocks and blocks:
        raise FlowError(
            "selected reviews block approval; human --override-reason required: "
            + ", ".join(blocks)
        )
    return blocks
