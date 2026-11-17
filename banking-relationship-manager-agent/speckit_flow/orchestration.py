from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from speckit_flow import agents, assurance, audit, state
from speckit_flow.models import FlowError, Profile, ReviewEvidenceError
from speckit_flow.profiles import DEFAULT_PROFILES_DIR

_INTENTS = {
    "security-patch": r"\b(cve|security patch|security fix|vulnerabilit(?:y|ies)|exploit)\b",
    "bugfix": r"\b(bug(?:fix)?|hotfix|hot fix|fix|repair|defect|crash|regression|broken)\b",
    "refactor": r"\b(refactor|restructure|cleanup|clean up|tech debt|rename)\b",
    "infra": r"\b(infrastructure|terraform|cdk|cloudformation|iac|deployment)\b",
    "poc": r"\b(proof of concept|poc|prototype|feasibility|spike)\b",
    "enterprise": (
        r"\b(enterprise delivery|regulated|compliance|high.assurance|"
        r"payment|payments|authentication|authorization|login|credentials|"
        r"personal data|pii|financial|production|data migration|schema migration|"
        r"encryption|security)\b"
    ),
}
_FEATURE = re.compile(r"\b(new feature|add|build|create|implement|introduce|extend|enhance)\b")

def execution_options(profiles: dict[str, Profile]) -> list[dict[str, Any]]:
    return [
        {
            "id": kind, "label": label,
            "profiles": [p.id for p in profiles.values() if p.execution in modes],
            "limitation": limitation,
        }
        for kind, label, modes, limitation in (
            ("inline", "Inline", ("inline",), "No independent review is implied."),
            (
                "selected", "Inline with selected workers", ("selective", "hybrid"),
                "Confirm named workers; hybrid host evidence remains mandatory.",
            ),
            (
                "delegated", "Delegated", ("delegated",),
                "Requires actual named-worker and conductor capabilities.",
            ),
        )
    ]


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
        if "security-patch" in candidates and "enterprise" in candidates:
            candidates.remove("enterprise")
        if "enterprise" in candidates and "bugfix" in candidates:
            candidates.remove("bugfix")
        # Creation verbs describe infrastructure/POC work too. A separate fix
        # and feature request is deliberately ambiguous rather than prioritized.
        feature_request = bool(_FEATURE.search(text))
        if feature_request and (not candidates or candidates == ["bugfix"]):
            candidates.append("feature")
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
    signals = [
        {
            "category": category,
            "evidence": f"request term: {match.group(0)}",
        }
        for category, pattern in _INTENTS.items()
        if (match := re.search(pattern, description.lower()))
    ]
    return {
        "profile": chosen,
        "candidates": available or sorted(profiles),
        "reason": reason,
        "needs_clarification": chosen is None,
        "confirmation_required": True,
        "execution_options": execution_options(profiles),
        "stages": list(profile.stages) if profile else [],
        "gates": list(profile.gates) if profile else [],
        "execution": profile.execution if profile else None,
        "risk_signals": signals,
        "risk_assessment": "advisory; inspect code and policy, not a numerical risk score",
        "alternatives": [
            {
                "profile": pid, "stages": list(profiles[pid].stages),
                "gates": list(profiles[pid].gates),
                "description": profiles[pid].description,
                "execution": profiles[pid].execution,
                "selection_condition": (
                    "Explicit opt-in for known low-risk work; no independent review."
                    if pid == "quick" else
                    "Explicit opt-in; inspect and confirm all assigned named workers."
                    if pid == "selective" else
                    "Use when policy or high-assurance requirements warrant a strict route."
                ),
            }
            for pid in ("quick", "selective", "enterprise")
            if pid in profiles and pid != chosen
        ],
        "worker_assignments": profile.assignments if profile else {},
        "review_coverage": (
            "explicit assignments; roster defaults apply where unspecified"
            if profile and profile.ceremony_on("reviews") else "no independent review selected"
        ),
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
    snapshot = audit.snapshot(feature_dir)
    if snapshot.problem:
        raise FlowError(f"audit trail integrity problem: {snapshot.problem}")
    if not snapshot.event_count:
        raise FlowError("audit trail is missing or empty; inspect/rebuild before dispatch")
    if snapshot.parked:
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
    hybrid_route = state.load_hybrid_route(feature_dir) if profile.execution == "hybrid" else None
    review_status: dict[str, Any] | None = None
    if hybrid_route is not None and expected == "plan":
        reviewer = roster.get(hybrid_route["reviewer"])
        if reviewer is None:
            review_status = {
                "state": "reviewer_unavailable",
                "reason": "The confirmed plan reviewer is no longer available in the roster.",
                "next_action": (
                    "Stop. Ask a human to explicitly revise or restart the confirmed route; "
                    "do not substitute another reviewer."
                ),
                "invocation_outcome": "not_recorded",
                "verdict": "not_available",
                "freshness": "not_verified",
            }
        elif (
            reviewer.role != "reviewer"
            or reviewer.can_edit
            or "plan" not in reviewer.supports
            or reviewer.id == lead.id
        ):
            review_status = {
                "state": "invalid_reviewer_selection",
                "reason": "The confirmed plan reviewer is no longer eligible.",
                "next_action": (
                    "Stop. Ask a human to explicitly revise or restart the confirmed route; "
                    "do not substitute another reviewer."
                ),
                "invocation_outcome": "not_recorded",
                "verdict": "not_available",
                "freshness": "not_verified",
            }
        else:
            support.append(reviewer)
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
    if profile.execution == "selective" and any(expected not in a.supports for a in support):
        raise FlowError("selected worker does not support the current stage")
    if profile.execution == "inline" and support:
        raise FlowError("inline execution cannot skip assigned supports or reviewers")
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

    if (
        hybrid_route is not None and expected == "plan"
        and review_status is None and reviewer is not None
    ):
        from speckit_flow import calls, host, reviews

        reviewer_id = hybrid_route["reviewer"]
        reviewer_calls = [
            item for item in calls.status(feature_dir, expected) if item["agent"] == reviewer_id
        ]
        invocation_outcome = reviewer_calls[-1]["status"] if reviewer_calls else "not_recorded"
        review_status = {
            "state": "missing_input_evidence",
            "reason": "No host source provides verifiable reviewer invocation inputs.",
            "next_action": (
                "Stop; do not retry dispatch or invoke a reviewer. A human must select "
                "an approved host evidence source before resuming."
            ),
            "invocation_outcome": invocation_outcome,
            "verdict": "not_available",
            "freshness": "not_verified",
        }
        if host.source(feature_dir) is not None:
            review_status.update(
                state="awaiting_review",
                reason="The selected host evidence adapter is configured.",
                next_action="Reserve once; invoke only the selected reviewer with review_prompt.",
            )
            if invocation_outcome == "running":
                review_status.update(
                    state="review_running", reason="The selected reviewer call is running.",
                    next_action="Wait for the existing call; do not invoke another worker.",
                )
            elif invocation_outcome == "failed":
                review_status.update(
                    state="review_failed", reason="The selected reviewer invocation failed.",
                    next_action="Stop; a human must decide recovery. Do not retry automatically.",
                )
            elif invocation_outcome == "succeeded":
                review_status.update(
                    state="review_result_missing",
                    reason="The call succeeded; a host-bound review is still required.",
                    next_action="Save the actual result with its host call ID; do not reinvoke.",
                )
                try:
                    saved_review = reviews.latest_review(feature_dir, "plan")
                    if saved_review is not None:
                        verified = reviews.require_hybrid_review(feature_dir)
                        review_status.update(
                            state="review_current",
                            reason="The host-bound review matches the plan.",
                            next_action="Run sensors and complete the stage; await the human gate.",
                            verdict=verified.verdict, freshness="current",
                            findings=[finding.to_dict() for finding in verified.findings],
                        )
                except ReviewEvidenceError as exc:
                    review_status.update(
                        state=exc.state, reason=str(exc),
                        next_action="Stop and inspect evidence; do not reinvoke automatically.",
                        freshness="stale" if exc.state == "stale_review" else "not_verified",
                    )
                    if exc.state == "stale_review" and saved_review is not None:
                        review_status.update(
                            reason=(
                                "The recorded review is stale; its verdict and findings "
                                "have not been revalidated and do not apply to the current plan."
                            ),
                            verdict=saved_review.verdict,
                            findings=[finding.to_dict() for finding in saved_review.findings],
                        )
                except FlowError as exc:
                    review_status.update(
                        state="invalid_incomplete_review", reason=str(exc),
                        next_action="Stop and inspect the review and evidence; do not auto-retry.",
                    )
            reviewer_meta = agents.parse_frontmatter(
                (root / reviewer.file).read_text(encoding="utf-8")
            )
            if reviewer_meta.get("tools") != []:
                review_status.update(
                    state="blocked_reviewer_tools",
                    reason="The confirmed reviewer has tools; no-tool review is required.",
                    next_action="Stop; do not substitute a reviewer or invoke the selected worker.",
                )
            elif not host.has_no_tool_capability(feature_dir, reviewer.agent_name):
                review_status.update(
                    state="blocked_unverified_no_tool_capability",
                    reason="The host has not verified the selected reviewer's no-tool capability.",
                    next_action="Stop; obtain human approval for a separate no-tool smoke test.",
                )

    if profile.id == "quick" and expected == "plan":
        if not any((feature_dir / "reviews").glob("plan-*.json")):
            review_status = {
                "state": "no_review",
                "reason": "No saved plan review file is available for this feature.",
                "next_action": "Continue under the confirmed quick route; no review is implied.",
                "invocation_outcome": "not_recorded",
                "verdict": "not_available",
                "freshness": "not_verified",
            }

    blocked = (
        hybrid_route is not None
        and review_status is not None
        and review_status["state"] not in ("awaiting_review", "review_current")
    )

    return {
        "status": "blocked" if blocked else "ready",
        "feature": str(feature_dir),
        "project_root": str(root.resolve()),
        "feature_dir": str(feature_dir.resolve()),
        "profile": profile.id,
        "stage": expected,
        "stage_status": current.stages[expected].status,
        "lead": brief(lead),
        "support": [brief(a) for a in support if a.role == "domain"],
        "reviewers": [
            brief(a) for a in support if a.role == "reviewer" and profile.ceremony_on("reviews")
        ],
        "gated": expected in profile.gates,
        "execution": profile.execution,
        "delegation_assurance": assurance.summary(
            expected, profile,
            next((e for e in snapshot.assurance_acceptances if e.stage == expected), None),
        ),
        "next_action": (
            review_status["next_action"] if blocked and review_status
            else "Inspect recorded work and worker calls before continuing this stage."
            if current.stages[expected].status == "in_progress"
            else "Start this stage; execute only the confirmed route and assigned workers."
        ),
        "required_evidence": {
            "human_gate": expected in profile.gates,
            "independent_reviewers": [
                a.id for a in support if a.role == "reviewer" and profile.ceremony_on("reviews")
            ],
            "stage_contracts": profile.stage_contracts,
            "contract_inputs": profile.contract_inputs,
            "sensors": "run configured stage sensors; absence is not a passing check",
        },
        **({"review_status": review_status} if review_status is not None else {}),
        **(
            {"reviewer_rationale": hybrid_route["rationale"]}
            if hybrid_route is not None and expected == "plan"
            else {}
        ),
        "delegated_stage": f"SPECKIT_DELEGATED_STAGE={expected}",
        "note": (
            "Hybrid plan execution is unavailable; stop without invoking workers."
            if blocked
            else "Eligibility only; the host executes inline and reports actual results."
            if profile.execution in ("inline", "hybrid", "selective")
            else "Eligibility only; the host must invoke these agents and report actual results."
        ),
    }


def _directive(
    feature_dir: Path,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    roster_file: Path = agents.DEFAULT_ROSTER_FILE,
    root: Path = agents.REPO_ROOT,
    _recorded_calls: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Read-only directive; never advances state, invokes workers or grants approval."""
    try:
        current = state.load_state(feature_dir)
        snapshot = audit.snapshot(feature_dir)
        if snapshot.problem or not snapshot.event_count:
            raise FlowError(f"invalid audit: {snapshot.problem or 'missing or empty trail'}")
        # Validate frozen policy even while waiting at a gate.
        state.profile_for(feature_dir, current.profile, profiles_dir)
        if current.pending_gate:
            return {
                "action": "await_human", "stage": current.pending_gate,
                "reason": "A human gate is pending.",
                "next_action": (
                    "Present artifacts, actual checks, reviews and risks; await a decision."
                ),
            }
        if snapshot.parked:
            return {
                "action": "parked", "stage": current.current_stage,
                "reason": "This feature is parked.",
                "next_action": "Inspect work and explicitly unpark before dispatch.",
            }
        brief = dispatch(
            feature_dir, profiles_dir=profiles_dir, roster_file=roster_file, root=root
        )
        if brief["status"] == "complete":
            return {
                "action": "complete", "reason": "All routed stages are complete.",
                "next_action": "Report lifecycle results; no further stage dispatch.",
            }
        if brief["status"] == "blocked":
            return {
                "action": "blocked", "reason": brief["review_status"]["reason"],
                "next_action": brief["next_action"], "dispatch": brief,
            }
        if brief["stage_status"] == "in_progress":
            from speckit_flow import calls

            recorded = calls.status(feature_dir, brief["stage"])
            if _recorded_calls is not None:
                _recorded_calls[brief["stage"]] = recorded
            if any(call["status"] == "running" for call in recorded):
                action, reason = "wait", "A recorded worker call is still running."
                step = "Inspect the existing host call; do not redispatch or transfer ownership."
            elif any(call["status"] == "failed" for call in recorded):
                action, reason = "recover", "A recorded worker call failed."
                step = "Inspect recovery status; only a human may authorize a new attempt."
            else:
                action, reason = "inspect", "The stage is already in progress."
                step = "Inspect artifacts, checkpoints and host execution; confirm before resuming."
        else:
            action, reason = "execute", "The next confirmed stage is eligible."
            step = brief["next_action"]
        return {
            "action": action, "reason": reason, "next_action": step, "dispatch": brief,
        }
    except FlowError as exc:
        return {
            "action": "blocked", "reason": str(exc),
            "next_action": "Stop and resolve the reported state, policy or evidence error.",
        }


def next_action(
    feature_dir: Path,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    roster_file: Path = agents.DEFAULT_ROSTER_FILE,
    root: Path = agents.REPO_ROOT,
    sensors_file: Path | None = None,
) -> dict[str, Any]:
    """One navigation surface; inspection is not stage completion or approval."""
    from speckit_flow import calls, contracts, questions, reviews, sensors

    recorded_calls: dict[str, list[dict[str, Any]]] = {}
    result = _directive(
        feature_dir, profiles_dir=profiles_dir, roster_file=roster_file, root=root,
        _recorded_calls=recorded_calls,
    )
    if result["action"] == "blocked" and "dispatch" not in result:
        return result
    try:
        current = state.load_state(feature_dir)
        profile = state.profile_for(feature_dir, current.profile, profiles_dir)
        stage = current.pending_gate or current.current_stage
        result["profile"] = profile.id
        result["execution"] = profile.execution
        result["execution_choice"] = (
            "inline" if profile.execution == "inline"
            else "selected" if profile.execution in ("hybrid", "selective")
            else "delegated"
        )
        result["route"] = list(profile.stages)
        result["gates"] = list(profile.gates)
        if stage is None:
            return result
        artifacts = list(sensors.stage_artifacts(stage))
        if profile.stage_contracts:
            contract = contracts.load_contracts(profiles_dir.parent).get(stage)
            if contract is None:
                raise FlowError(f"no stage contract found for {stage!r}")
            artifacts.extend(
                output.path for output in contract.outputs if output.required and output.path
            )
        open_items = questions.open_questions(feature_dir)
        saved = reviews.latest_review(feature_dir, stage)
        sensor_path = sensors_file if sensors_file is not None else sensors.DEFAULT_SENSORS_FILE
        result["readiness"] = {
            "stage": stage,
            "artifacts": [
                {"path": path, "present": (feature_dir / path).is_file()}
                for path in dict.fromkeys(artifacts)
            ],
            "sensors": (
                sensors.evidence_status(feature_dir, stage, sensor_path)
                if sensor_path.is_file() else []
            ),
            "sensor_config": "configured" if sensor_path.is_file() else "not_configured",
            "questions": {
                "open_count": len(open_items),
                "items": [
                    {"id": q.id, "role": q.role, "text": q.text[:160]} for q in open_items[:5]
                ],
                "truncated": len(open_items) > 5 or any(len(q.text) > 160 for q in open_items[:5]),
            },
            "worker_calls": (
                recorded_calls[stage] if stage in recorded_calls
                else calls.status(feature_dir, stage)
            ),
            "review": (
                {"id": saved.id, "verdict": saved.verdict,
                 "freshness": "stale" if reviews.is_stale(feature_dir, saved) else "stored_current"}
                if saved else {"verdict": "not_available", "freshness": "not_verified"}
            ),
            "notice": (
                "Read-only evidence summary, not completion permission or host authentication. "
                "Artifact presence is not validity; "
                "stored review freshness is not host verification. "
                "No checks, workers, approvals or ownership changes were executed."
            ),
        }
        if current.pending_gate:
            result["approval_package"] = {
                "decision": f"Approve or reject {stage}",
                "required_sections": [
                    "decision and scope", "artifacts and change summary",
                    "actual verification and review results", "findings and unresolved risks",
                    "authorization provenance", "what approval allows and excludes",
                ],
                "authorizes": (
                    "Only the next confirmed route segment after an actual human decision."
                ),
                "excludes": (
                    "No deployment, command approval, plugin activation or ownership transfer."
                ),
                "decision_recorded": False,
            }
        return result
    except (FlowError, OSError) as exc:
        return {
            **result, "action": "blocked", "reason": f"readiness inspection failed: {exc}",
            "next_action": "Resolve the evidence error; do not advance or use a partial summary.",
        }
