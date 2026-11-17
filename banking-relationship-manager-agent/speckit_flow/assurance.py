from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from speckit_flow import agents, audit, state
from speckit_flow.models import AuditEvent, FlowError, Profile
from speckit_flow.profiles import DEFAULT_PROFILES_DIR

EVENT = "delegation_assurance_accepted"
PROFILES = frozenset({"feature", "bugfix", "refactor", "selective"})
STAGES = frozenset({"ideation", "specify", "clarify", "plan", "tasks", "analyze", "implement"})
MISSING = "Runtime worker tool enforcement is unverified"
RISK = "Worker tools may exceed declared restrictions"
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")
_DIGEST = re.compile(r"[a-f0-9]{8}(?:-[a-f0-9]{8}){7}")


def _identifier(value: str, limit: int) -> None:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= limit
        or not _IDENTIFIER.fullmatch(value)
    ):
        raise FlowError(f"host/session identifier must be nonempty and at most {limit} characters")


def _events(feature_dir: Path) -> list[AuditEvent]:
    snapshot = audit.snapshot(feature_dir)
    if snapshot.problem or not snapshot.event_count:
        raise FlowError(f"invalid assurance audit: {snapshot.problem or 'missing audit'}")
    try:
        return audit.read_events(feature_dir)
    except (OSError, UnicodeError) as exc:
        raise FlowError(f"cannot read assurance audit: {exc}") from exc


def _latest(events: list[AuditEvent], stage: str) -> AuditEvent | None:
    return next((e for e in reversed(events) if e.type == EVENT and e.stage == stage), None)


def _payload(event: AuditEvent) -> dict[str, Any]:
    try:
        data = json.loads(event.detail)
    except ValueError as exc:
        raise FlowError("malformed assurance acceptance") from exc
    fields = {
        "version",
        "host",
        "session_id",
        "scope",
        "reason",
        "observation",
        "missing_evidence",
        "residual_risk",
    }
    if (
        not event.actor.startswith("human:")
        or not event.actor[6:].strip()
        or not isinstance(data, dict)
        or set(data) != fields
        or type(data["version"]) is not int
        or data["version"] != 1
        or any(not isinstance(data[key], str) for key in fields - {"version"})
    ):
        raise FlowError("malformed or nonhuman assurance acceptance")
    _identifier(data["host"], 24)
    _identifier(data["session_id"], 64)
    if (
        not _DIGEST.fullmatch(data["scope"])
        or any(not data[key].strip() or len(data[key]) > 60 for key in ("reason", "observation"))
        or data["missing_evidence"] != MISSING
        or data["residual_risk"] != RISK
        or len(event.detail) > 500
    ):
        raise FlowError("invalid assurance acceptance disclosure or scope")
    audit.check_redaction(event.detail)
    return data


def _eligible(profile: Profile, stage: str) -> bool:
    return profile.id in PROFILES and not profile.strict and stage in STAGES


def summary(stage: str, profile: Profile, event: AuditEvent | None) -> dict[str, Any]:
    """Report stored consent without pretending to validate the current host context."""
    if event is not None:
        _payload(event)
    eligible = _eligible(profile, stage)
    return {
        "status": "ineligible" if not eligible else "context_required" if event else "not_accepted",
        "runtime_enforcement": "unverified",
        "acceptance_event": event.seq if event else None,
        "reason": (
            "Lower assurance is ineligible for this profile or stage."
            if not eligible
            else "Current host/session and worker scope must be checked before invoking workers."
            if event
            else "No human acceptance; missing required runtime evidence remains a stop."
        ),
    }


def status(
    feature_dir: Path,
    stage: str,
    host: str,
    session_id: str,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    roster_file: Path = agents.DEFAULT_ROSTER_FILE,
    root: Path = agents.REPO_ROOT,
) -> dict[str, Any]:
    from speckit_flow import calls, orchestration

    _identifier(host, 24)
    _identifier(session_id, 64)
    brief = orchestration.dispatch(
        feature_dir,
        stage,
        profiles_dir=profiles_dir,
        roster_file=roster_file,
        root=root,
    )
    profile = state.profile_for(feature_dir, brief["profile"], profiles_dir)
    events = _events(feature_dir)
    result = {
        **brief["delegation_assurance"],
        "feature": str(feature_dir.resolve()),
        "stage": stage,
        "host": host,
        "session_id": session_id,
        "missing_evidence": MISSING,
        "residual_risk": RISK,
    }
    if not _eligible(profile, stage):
        return result
    selected = [*brief["support"], *brief["reviewers"]]
    if brief["execution"] == "delegated":
        selected.insert(0, brief["lead"])
    result["workers"] = selected
    if any(call["status"] in ("running", "failed") for call in calls.status(feature_dir, stage)):
        return {
            **result,
            "status": "blocked",
            "reason": "Running or failed worker calls require the existing recovery procedure.",
        }
    definitions = {}
    roster = agents.load_roster(roster_file)
    for name in sorted({"conductor", *(worker["id"] for worker in selected)}):
        try:
            definitions[name] = (root / roster[name].file).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise FlowError(f"cannot read configured worker {name}: {exc}") from exc
    result["declared_tools"] = {
        worker["agent_name"]: agents.parse_frontmatter(definitions[worker["id"]])["tools"]
        for worker in selected
    }
    boundary = max(
        (e.seq for e in events if e.stage == stage and e.type in ("stage_redone", "calls_reset")),
        default=0,
    )
    scope = {
        "feature": str(feature_dir.resolve()),
        "stage": stage,
        "profile": profile.to_dict(),
        "workers": selected,
        "definitions": definitions,
        "host": host,
        "session_id": session_id,
        "boundary": boundary,
    }
    digest = hashlib.sha256(
        json.dumps(scope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result["scope"] = "-".join(digest[i : i + 8] for i in range(0, len(digest), 8))
    event = _latest(events, stage)
    if event is None:
        return result
    data = _payload(event)
    if data["host"] != host or data["session_id"] != session_id or data["scope"] != result["scope"]:
        return {
            **result,
            "status": "stale",
            "reason": "Acceptance does not match the current attested context or worker scope.",
        }
    return {
        **result,
        "status": "unverified_accepted",
        "reason": "Human accepted missing runtime proof; isolation remains unverified.",
        "observation": data["observation"],
        "rationale": data["reason"],
    }


def accept(
    feature_dir: Path,
    stage: str,
    host: str,
    session_id: str,
    actor: str,
    reason: str,
    observation: str,
    confirm_ordinary_work: bool,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    roster_file: Path = agents.DEFAULT_ROSTER_FILE,
    root: Path = agents.REPO_ROOT,
) -> dict[str, Any]:
    if not actor.startswith("human:") or not actor[6:].strip():
        raise FlowError("only a human may accept delegation assurance")
    if confirm_ordinary_work is not True:
        raise FlowError("explicit ordinary-work confirmation is required")
    options = {"profiles_dir": profiles_dir, "roster_file": roster_file, "root": root}
    current = status(feature_dir, stage, host, session_id, **options)
    if current["status"] in ("blocked", "ineligible"):
        raise FlowError(f"assurance acceptance is {current['status']}: {current['reason']}")
    detail = json.dumps(
        {
            "version": 1,
            "host": host,
            "session_id": session_id,
            "scope": current["scope"],
            "reason": reason,
            "observation": observation,
            "missing_evidence": MISSING,
            "residual_risk": RISK,
        },
        separators=(",", ":"),
    )
    _payload(AuditEvent(0, "", EVENT, stage, actor, detail, ""))
    audit.append_event(feature_dir, EVENT, stage, actor, detail)
    return status(feature_dir, stage, host, session_id, **options)
