from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from speckit_flow import agents, audit, state
from speckit_flow.models import FlowError, Profile
from speckit_flow.profiles import DEFAULT_PROFILES_DIR

_INTENTS = {
    "security-patch": r"\b(cve|security patch|security fix|vulnerabilit(?:y|ies)|exploit)\b",
    "bugfix": r"\b(bug(?:fix)?|hotfix|hot fix|fix|repair|defect|crash|regression|broken)\b",
    "refactor": r"\b(refactor|restructure|cleanup|clean up|tech debt|rename)\b",
    "infra": r"\b(infrastructure|terraform|cdk|cloudformation|iac)\b",
    "poc": r"\b(proof of concept|poc|prototype|feasibility|spike)\b",
    "enterprise": r"\b(enterprise delivery|regulated delivery|high-assurance)\b",
}
_FEATURE = re.compile(r"\b(new feature|add|build|create|implement|introduce|extend|enhance)\b")


def recommend(
    description: str, profiles: dict[str, Profile], explicit: str | None = None
) -> dict[str, Any]:
    """Return read-only routing advice; the host obtains selection/confirmation."""
    if not profiles:
        raise FlowError("no profiles available")
    if explicit is not None:
        if explicit not in profiles:
            raise FlowError(
                f"unknown profile {explicit!r}; valid profiles: {', '.join(sorted(profiles))}"
            )
        candidates = [explicit]
        reason = "explicit profile selection"
    else:
        text = description.lower()
        candidates = [pid for pid, pattern in _INTENTS.items() if re.search(pattern, text)]
        if "security-patch" in candidates and "bugfix" in candidates:
            candidates.remove("bugfix")
        # Creation verbs describe infrastructure/POC work too. A separate fix
        # and feature request is deliberately ambiguous rather than prioritized.
        if _FEATURE.search(text) and (not candidates or candidates == ["bugfix"]):
            candidates.append("full-lifecycle")
        reason = (
            "recognized work category; confirm the route"
            if len(candidates) == 1
            else "unclear or mixed work category; ask the user to select a profile"
        )
    available = [pid for pid in candidates if pid in profiles]
    chosen = available[0] if len(candidates) == 1 and len(available) == 1 else None
    if candidates and not available:
        reason = "recommended profile is unavailable; ask the user to select an available profile"
    profile = profiles.get(chosen or "")
    return {
        "profile": chosen,
        "candidates": available or sorted(profiles),
        "reason": reason,
        "needs_clarification": chosen is None,
        "confirmation_required": True,
        "stages": list(profile.stages) if profile else [],
        "gates": list(profile.gates) if profile else [],
    }


def dispatch(
    feature_dir: Path,
    stage: str | None = None,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    roster_file: Path = agents.DEFAULT_ROSTER_FILE,
    root: Path = agents.REPO_ROOT,
) -> dict[str, Any]:
    """Validate eligibility and return a brief; only the host can invoke agents."""
    current = state.load_state(feature_dir)
    try:
        broken = audit.verify_chain(feature_dir)
        events = audit.read_events(feature_dir)
    except OSError as exc:
        raise FlowError(f"cannot read audit trail: {exc}") from exc
    if broken:
        raise FlowError(f"audit trail integrity problem: {broken}")
    if not events:
        raise FlowError("audit trail is missing or empty; inspect/rebuild before dispatch")
    if audit.is_parked(feature_dir):
        raise FlowError("feature is parked; unpark before dispatch")
    if current.pending_gate:
        raise FlowError(f"pending human gate for {current.pending_gate!r}; no dispatch")
    profile = state.profile_for(feature_dir, current.profile, profiles_dir)
    expected = state.next_stage(current)
    if stage is not None and stage not in profile.stages:
        raise FlowError(f"stage {stage!r} is not in profile {profile.id}")
    if stage is not None and stage != expected:
        raise FlowError(f"out of order: next stage is {expected!r}, not {stage!r}")
    if current.current_stage != expected:
        raise FlowError("state current stage does not match next stage; inspect/rebuild state")
    if expected is None:
        return {"status": "complete", "feature": str(feature_dir), "profile": profile.id}
    if expected not in profile.stages:
        raise FlowError(f"state stage {expected!r} is not in profile {profile.id}")

    roster = agents.load_roster(roster_file)
    problems = agents.validate_roster(roster, root)
    if problems:
        raise FlowError("roster invalid: " + "; ".join(problems))
    assignment = agents.resolve_assignments(profile, roster)[expected]
    lead = roster[assignment["lead"]]
    try:
        lead_meta = agents.parse_frontmatter((root / lead.file).read_text(encoding="utf-8"))
    except OSError as exc:
        raise FlowError(f"cannot read assigned lead: {exc}") from exc
    if not lead.can_edit or "execute" not in lead_meta.get("tools", []):
        raise FlowError(f"assigned lead {lead.id!r} needs edit and execute for stage work")
    support = [roster[name] for name in assignment["support"]]
    if (
        profile.strict
        and expected in profile.gates
        and not any(agent.role == "reviewer" for agent in support)
    ):
        reviewer_id = (
            "product-lead"
            if expected in ("ideation", "specify", "clarify")
            else "architecture-reviewer"
        )
        support.append(roster[reviewer_id])
    if len({a.id for a in support}) != len(support):
        raise FlowError("duplicate supporting agents in stage assignment")
    if any(a.role not in ("domain", "reviewer") for a in support):
        raise FlowError("stage supports must be domain agents or independent reviewers")
    conductor = roster["conductor"]
    try:
        meta = agents.parse_frontmatter((root / conductor.file).read_text(encoding="utf-8"))
    except OSError as exc:
        raise FlowError(f"cannot read conductor: {exc}") from exc
    selected = [lead, *support]
    missing = [a.agent_name for a in selected if a.agent_name not in meta.get("agents", [])]
    if missing:
        raise FlowError("conductor cannot dispatch assigned agents: " + ", ".join(missing))

    def brief(agent: agents.Agent) -> dict[str, Any]:
        return {**agent.to_dict(), "agent_name": agent.agent_name}

    return {
        "status": "ready",
        "feature": str(feature_dir),
        "profile": profile.id,
        "stage": expected,
        "stage_status": current.stages[expected].status,
        "lead": brief(lead),
        "support": [brief(a) for a in support if a.role == "domain"],
        "reviewers": [
            brief(a) for a in support if a.role == "reviewer" and profile.ceremony_on("reviews")
        ],
        "gated": expected in profile.gates,
        "delegated_stage": f"SPECKIT_DELEGATED_STAGE={expected}",
        "note": "Eligibility only; the host must invoke these agents and report actual results.",
    }
