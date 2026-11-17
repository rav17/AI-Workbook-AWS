from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from speckit_flow import agents, audit, calls, host, orchestration, reviews, state
from speckit_flow.cli import main
from speckit_flow.models import FlowError
from speckit_flow.profiles import DEFAULT_PROFILES_DIR, load_profiles

ROOT = Path(__file__).resolve().parents[3]
HUMAN = "human:test"


@pytest.mark.parametrize(
    ("description", "profile"),
    [
        ("Create a new feature for export", "feature"),
        ("Add reading lists", "feature"),
        ("Add a small reading-list feature", "feature"),
        ("Fix a simple parser crash", "bugfix"),
        ("Add a small payment feature", "enterprise"),
        ("Fix a crash in the parser", "bugfix"),
        ("Hotfix the login failure", "enterprise"),
        ("Patch a CVE in a dependency", "security-patch"),
        ("Fix a security vulnerability", "security-patch"),
        ("Refactor request handling", "refactor"),
        ("Add Terraform infrastructure", "infra"),
        ("Build a proof of concept", "poc"),
        ("Plan high-assurance delivery", "enterprise"),
        ("Add a security feature", "enterprise"),
        ("Add a production migration", "enterprise"),
        ("Add deployment support", "infra"),
    ],
)
def test_recommendation_matrix(description: str, profile: str) -> None:
    result = orchestration.recommend(description, load_profiles())
    assert result["profile"] == profile
    assert result["confirmation_required"] is True
    assert result["needs_clarification"] is False
    assert result["stages"]


@pytest.mark.parametrize("description", ["", "help with this", "Add export and fix parser crash"])
def test_ambiguous_request_requires_question(description: str) -> None:
    result = orchestration.recommend(description, load_profiles())
    assert result["profile"] is None
    assert result["needs_clarification"] is True
    assert result["confirmation_required"] is True


def test_explicit_profile_wins_and_unavailable_profile_fails() -> None:
    assert (
        orchestration.recommend("Fix a crash", load_profiles(), "enterprise")["profile"]
        == "enterprise"
    )
    with pytest.raises(FlowError, match="valid profiles"):
        orchestration.recommend("anything", load_profiles(), "disabled-pack-profile")
    available = load_profiles()
    del available["feature"]
    assert orchestration.recommend("Create a new feature", available)["needs_clarification"]


def test_routing_explanation_discloses_evidence_and_alternative_review_limits() -> None:
    result = orchestration.recommend("Add an authorization feature", load_profiles())
    assert result["profile"] == "enterprise"
    assert {"category": "enterprise", "evidence": "request term: authorization"} in (
        result["risk_signals"]
    )
    quick = next(item for item in result["alternatives"] if item["profile"] == "quick")
    assert quick["execution"] == "inline"
    assert "no independent review" in quick["selection_condition"]
    assert result["confirmation_required"]


def test_recommend_cli_is_read_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "workflow",
                "recommend",
                "Add reading lists",
                "--json",
                "--feature-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "feature"
    assert payload["execution"] == "delegated"
    assert list(tmp_path.iterdir()) == []


def test_execution_choices_are_presentation_not_profile_migrations() -> None:
    profiles = load_profiles()
    before = {name: profile.to_dict() for name, profile in profiles.items()}
    result = orchestration.recommend("Build a new feature", profiles)
    choices = {item["id"]: item for item in result["execution_options"]}
    assert "quick" in choices["inline"]["profiles"]
    assert {"selective", "hybrid-plan"} <= set(choices["selected"]["profiles"])
    assert "enterprise" in choices["delegated"]["profiles"]
    assert result["profile"] == "feature"
    assert {name: profile.to_dict() for name, profile in profiles.items()} == before


@pytest.fixture
def feature(tmp_path: Path) -> Path:
    result = tmp_path / "specs" / "001-reading-list"
    result.mkdir(parents=True)
    return result


def test_preflight_separates_support_and_independent_reviewers(feature: Path) -> None:
    state.init_state(feature, "feature", HUMAN)
    before = {p.name: p.read_bytes() for p in feature.iterdir()}
    result = orchestration.dispatch(feature)
    assert result["status"] == "ready"
    assert result["stage"] == "specify"
    assert result["lead"]["id"] == "product"
    assert "design" in {a["id"] for a in result["support"]}
    assert "product-lead" in {a["id"] for a in result["reviewers"]}
    assert all(a["role"] == "domain" for a in result["support"])
    assert all(not a["can_edit"] for a in result["reviewers"])
    assert before == {p.name: p.read_bytes() for p in feature.iterdir()}


def test_quick_route_inline_without_agents_and_with_gate(feature: Path) -> None:
    state.init_state(feature, "quick", HUMAN)
    for stage in ("specify", "plan", "tasks"):
        brief = orchestration.dispatch(feature)
        assert brief["stage"] == stage
        assert brief["execution"] == "inline"
        assert brief["support"] == []
        assert brief["reviewers"] == []
        state.start_stage(feature, stage, "agent:workflow")
        state.done_stage(feature, stage, "agent:workflow")
    with pytest.raises(FlowError, match="pending.*gate|gate.*pending"):
        orchestration.dispatch(feature)
    with pytest.raises(FlowError, match="only a human"):
        state.decide_gate(feature, "tasks", True, "agent:workflow")
    state.decide_gate(feature, "tasks", True, HUMAN)
    assert orchestration.dispatch(feature)["stage"] == "implement"


def test_quick_plan_reports_no_recorded_review_without_blocking(
    feature: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state.init_state(feature, "quick", HUMAN)
    state.start_stage(feature, "specify", "agent:workflow")
    state.done_stage(feature, "specify", "agent:workflow")

    assert main(["workflow", "dispatch", "--feature-dir", str(feature)]) == 0
    output = capsys.readouterr().out
    assert "Review state: no_review" in output
    assert "no review" in output
    assert "No saved plan review file is available" in output
    assert "Invocation outcome: not_recorded" in output

    (feature / "reviews").mkdir()
    (feature / "reviews" / "plan-1.json").write_text("{}", encoding="utf-8")
    assert main(["workflow", "dispatch", "--feature-dir", str(feature)]) == 0
    assert "Review state: no_review" not in capsys.readouterr().out


def test_inline_preflight_refuses_to_skip_assigned_support(feature: Path, tmp_path: Path) -> None:
    profiles = tmp_path / "profiles"
    shutil.copytree(DEFAULT_PROFILES_DIR, profiles)
    path = profiles / "quick.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["assignments"]["specify"]["support"] = ["design"]
    path.write_text(json.dumps(data), encoding="utf-8")
    state.init_state(feature, "quick", HUMAN, profiles)
    with pytest.raises(FlowError, match="cannot skip assigned supports"):
        orchestration.dispatch(feature, profiles_dir=profiles)


@pytest.mark.parametrize("profile", list(load_profiles()))
def test_every_profile_has_callable_initial_stage(feature: Path, profile: str) -> None:
    if profile == "hybrid-plan":
        state.init_state(
            feature,
            profile,
            HUMAN,
            reviewer="architecture-reviewer",
            confirm_route=True,
            rationale="Independent plan review",
        )
    elif profile == "selective":
        state.init_state(
            feature, profile, HUMAN, confirm_route=True, rationale="Selected plan review"
        )
    else:
        state.init_state(feature, profile, HUMAN)
    result = orchestration.dispatch(feature)
    assert result["stage"] == load_profiles()[profile].stages[0]
    assert result["lead"]["agent_name"].startswith("speckit-")


def test_hybrid_route_requires_confirmed_eligible_selection(feature: Path) -> None:
    with pytest.raises(FlowError, match="confirmed"):
        state.init_state(feature, "hybrid-plan", HUMAN, reviewer="architecture-reviewer")
    for reviewer in ("", "architect", "product-lead", "missing"):
        with pytest.raises(FlowError, match="reviewer"):
            state.init_state(
                feature,
                "hybrid-plan",
                HUMAN,
                reviewer=reviewer,
                confirm_route=True,
                rationale="Independent plan review",
            )
    assert list(feature.iterdir()) == []


@pytest.mark.parametrize(
    ("reviewer", "expected"),
    [
        (None, "missing_reviewer_selection"),
        ("product-lead", "invalid_reviewer_selection"),
    ],
)
def test_hybrid_init_displays_selection_statuses_without_persisting(
    feature: Path,
    capsys: pytest.CaptureFixture[str],
    reviewer: str | None,
    expected: str,
) -> None:
    for json_output in (True, False):
        args = [
            "init", "--profile", "hybrid-plan", "--confirm-route",
            "--feature-dir", str(feature),
        ]
        if reviewer is not None:
            args.extend(["--reviewer", reviewer])
        if json_output:
            args.append("--json")

        assert main(args) == 1
        output = capsys.readouterr().out
        if json_output:
            result = json.loads(output)
            assert result["status"] == "blocked"
            status = result["review_status"]
            assert status["state"] == expected
            assert status["invocation_outcome"] == "not_recorded"
            assert status["verdict"] == "not_available"
            assert status["freshness"] == "not_verified"
            assert status["next_action"]
        else:
            assert f"Review state: {expected}" in output
            assert "Reason:" in output
            assert "Next action:" in output
    assert list(feature.iterdir()) == []


def test_missing_hybrid_selection_has_readable_plain_text(
    feature: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([
        "init", "--profile", "hybrid-plan", "--confirm-route",
        "--feature-dir", str(feature),
    ]) == 1
    output = capsys.readouterr().out
    assert "Review state: missing_reviewer_selection" in output
    assert "Invocation outcome: not_recorded" in output
    assert "Next action: Select an eligible" in output


def test_hybrid_route_persists_selection_and_blocks_unverified_plan(feature: Path) -> None:
    state.init_state(
        feature,
        "hybrid-plan",
        HUMAN,
        reviewer="architecture-reviewer",
        confirm_route=True,
        rationale="Independent plan review",
    )
    state.start_stage(feature, "specify", "agent:workflow")
    state.done_stage(feature, "specify", "agent:workflow")
    state.decide_gate(feature, "specify", True, HUMAN)
    before = {p.name: p.read_bytes() for p in feature.iterdir()}
    brief = orchestration.dispatch(feature)
    assert brief["status"] == "blocked"
    assert brief["execution"] == "hybrid"
    assert brief["reviewers"][0]["id"] == "architecture-reviewer"
    assert brief["reviewer_rationale"] == "Independent plan review"
    assert brief["review_status"]["state"] == "missing_input_evidence"
    assert brief["review_status"]["invocation_outcome"] == "not_recorded"
    assert "do not retry" in brief["review_status"]["next_action"]
    assert orchestration.dispatch(feature) == brief
    assert before == {p.name: p.read_bytes() for p in feature.iterdir()}
    state.start_stage(feature, "plan", "agent:workflow")
    with pytest.raises(FlowError, match="review invocation is missing"):
        state.done_stage(feature, "plan", "agent:workflow")
    assert state.load_state(feature).stages["plan"].status == "in_progress"


@pytest.mark.parametrize("as_json", [False, True])
def test_hybrid_blocked_dispatch_cli_fails_with_actionable_output(
    feature: Path, capsys: pytest.CaptureFixture[str], as_json: bool
) -> None:
    state.init_state(
        feature, "hybrid-plan", HUMAN, reviewer="architecture-reviewer",
        confirm_route=True, rationale="Independent plan review",
    )
    state.start_stage(feature, "specify", "agent:workflow")
    state.done_stage(feature, "specify", "agent:workflow")
    state.decide_gate(feature, "specify", True, HUMAN)
    args = ["workflow", "dispatch", "--feature-dir", str(feature)]
    if as_json:
        args.append("--json")
    assert main(args) == 1
    output = capsys.readouterr().out
    if as_json:
        result = json.loads(output)
        assert result["status"] == "blocked"
        assert result["review_status"]["invocation_outcome"] == "not_recorded"
    assert "verifiable reviewer invocation inputs" in output
    assert "do not retry" in output
    assert "missing_input_evidence" in output
    assert "not_recorded" in output


def test_hybrid_snapshot_tampering_fails_closed(feature: Path) -> None:
    state.init_state(
        feature,
        "hybrid-plan",
        HUMAN,
        reviewer="architecture-reviewer",
        confirm_route=True,
        rationale="Independent plan review",
    )
    path = feature / "hybrid-route.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["reviewer"] = "product-lead"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FlowError, match="route.*changed"):
        orchestration.dispatch(feature)


@pytest.mark.parametrize(
    ("reviewer", "expected"),
    [
        ("architecture-reviewer", "blocked_reviewer_tools"),
        ("hybrid-plan-reviewer", "blocked_unverified_no_tool_capability"),
    ],
)
def test_hybrid_dispatch_blocks_unproven_tool_boundary(
    feature: Path, tmp_path: Path, reviewer: str, expected: str,
) -> None:
    state.init_state(
        feature, "hybrid-plan", HUMAN, reviewer=reviewer,
        confirm_route=True, rationale="Independent plan review",
    )
    log = tmp_path / "events.jsonl"
    log.write_text('{"type":"session.start","data":{}}\n', encoding="utf-8")
    host.configure(feature, log, HUMAN)
    state.start_stage(feature, "specify", "agent:workflow")
    state.done_stage(feature, "specify", "agent:workflow")
    state.decide_gate(feature, "specify", True, HUMAN)
    state.start_stage(feature, "plan", "agent:workflow")
    (feature / "plan.md").write_text("# Synthetic plan\n", encoding="utf-8")
    brief = orchestration.dispatch(feature)
    assert brief["status"] == "blocked"
    assert brief["review_status"]["state"] == expected
    with pytest.raises(FlowError, match="dispatch blocked"):
        calls.reserve(feature, "plan", reviewer, "agent:workflow")
    assert calls.status(feature, "plan") == []


def test_hybrid_dispatch_reports_confirmed_reviewer_unavailable(
    feature: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state.init_state(
        feature,
        "hybrid-plan",
        HUMAN,
        reviewer="hybrid-plan-reviewer",
        confirm_route=True,
        rationale="Independent plan review",
    )
    state.start_stage(feature, "specify", "agent:workflow")
    state.done_stage(feature, "specify", "agent:workflow")
    state.decide_gate(feature, "specify", True, HUMAN)
    state.start_stage(feature, "plan", "agent:workflow")
    (feature / "plan.md").write_text("# Synthetic plan\n", encoding="utf-8")
    roster = agents.load_roster()
    roster.pop("hybrid-plan-reviewer")
    monkeypatch.setattr(agents, "load_roster", lambda _path: roster)

    brief = orchestration.dispatch(feature)

    assert brief["status"] == "blocked"
    assert brief["review_status"]["state"] == "reviewer_unavailable"
    assert brief["review_status"]["invocation_outcome"] == "not_recorded"
    assert "do not substitute" in brief["review_status"]["next_action"]
    assert calls.status(feature, "plan") == []
    assert main(["workflow", "dispatch", "--feature-dir", str(feature)]) == 1
    assert "Review state: reviewer_unavailable" in capsys.readouterr().out


def test_preflight_supports_in_progress_resume(feature: Path) -> None:
    state.init_state(feature, "feature", HUMAN)
    state.start_stage(feature, "specify", "agent:conductor")
    assert orchestration.dispatch(feature)["stage_status"] == "in_progress"


def test_full_lifecycle_preflight_tracks_every_stage_and_completion(feature: Path) -> None:
    profile = load_profiles()["full-lifecycle"]
    state.init_state(feature, profile.id, HUMAN)
    observed = []
    for stage in profile.stages:
        result = orchestration.dispatch(feature)
        observed.append(result["stage"])
        assert result["lead"]["role"] == "domain"
        assert result["lead"]["id"] not in {a["id"] for a in result["reviewers"]}
        state.start_stage(feature, stage, "agent:conductor")
        state.done_stage(feature, stage, "agent:conductor")
        if stage in profile.gates:
            with pytest.raises(FlowError, match="pending"):
                orchestration.dispatch(feature)
            state.decide_gate(feature, stage, True, HUMAN)
    assert observed == list(profile.stages)
    assert orchestration.dispatch(feature)["status"] == "complete"
    assert "lead" not in orchestration.dispatch(feature)


def test_missing_audit_blocks_preflight(feature: Path) -> None:
    state.init_state(feature, "feature", HUMAN)
    (feature / "audit.jsonl").unlink()
    with pytest.raises(FlowError, match="audit trail is missing"):
        orchestration.dispatch(feature)


def test_strict_profile_has_independent_review_for_every_gate(feature: Path) -> None:
    profile = load_profiles()["enterprise"]
    state.init_state(feature, profile.id, HUMAN)
    (feature / "review-target.md").write_text("Fixture stage output.\n", encoding="utf-8")
    for stage in profile.stages:
        brief = orchestration.dispatch(feature)
        assert brief["reviewers"], stage
        reviewer = brief["reviewers"][0]
        assert reviewer["id"] != brief["lead"]["id"]
        state.start_stage(feature, stage, "agent:conductor")
        state.done_stage(feature, stage, "agent:conductor")
        reviews.save_review(
            feature,
            stage,
            {
                "reviewer": "spec" if reviewer["id"] == "product-lead" else "plan",
                "author": f"agent:{brief['lead']['id']}",
                "verdict": "pass",
                "files": ["review-target.md"],
                "findings": [],
            },
            f"agent:{reviewer['id']}",
        )
        state.decide_gate(feature, stage, True, HUMAN)
    assert orchestration.dispatch(feature)["status"] == "complete"


def test_preflight_rejects_out_of_order_or_omitted_stage(feature: Path) -> None:
    state.init_state(feature, "bugfix", HUMAN)
    for stage in ("implement", "plan"):
        with pytest.raises(FlowError, match="next stage|not in"):
            orchestration.dispatch(feature, stage)


def test_preflight_blocks_pending_gate_and_parked_work(feature: Path) -> None:
    state.init_state(feature, "feature", HUMAN)
    audit.append_event(feature, "intent_parked", None, HUMAN, "paused")
    with pytest.raises(FlowError, match="parked"):
        orchestration.dispatch(feature)
    audit.append_event(feature, "intent_resumed", None, HUMAN, "resumed")
    state.start_stage(feature, "specify", "agent:conductor")
    state.done_stage(feature, "specify", "agent:conductor")
    with pytest.raises(FlowError, match="pending.*gate|gate.*pending"):
        orchestration.dispatch(feature)


def test_preflight_blocks_corrupt_audit_without_mutation(feature: Path) -> None:
    state.init_state(feature, "feature", HUMAN)
    path = feature / "audit.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8").replace("profile_selected", "broken"),
        encoding="utf-8",
    )
    before = path.read_bytes()
    with pytest.raises(FlowError, match="audit"):
        orchestration.dispatch(feature)
    assert path.read_bytes() == before


@pytest.mark.parametrize("profile", ["quick", "feature"])
def test_dispatch_reads_audit_once(
    feature: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    state.init_state(feature, profile, HUMAN)
    original = Path.open
    reads = 0

    def counted(path: Path, *args: object, **kwargs: object):
        nonlocal reads
        if path.name == "audit.jsonl":
            reads += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted)
    assert orchestration.dispatch(feature)["profile"] == profile
    assert reads == 1


@pytest.mark.parametrize("failure", ["model-disabled", "allowlist", "agent-tool"])
def test_invalid_dispatch_configuration_fails(feature: Path, failure: str) -> None:
    root = feature.parents[1]
    shutil.copytree(ROOT / ".github" / "agents", root / ".github" / "agents")
    shutil.copytree(ROOT / ".specify" / "agents", root / ".specify" / "agents")
    path = (
        root
        / ".github"
        / "agents"
        / (
            "speckit-product.agent.md"
            if failure == "model-disabled"
            else "speckit-conductor.agent.md"
        )
    )
    text = path.read_text(encoding="utf-8")
    if failure == "model-disabled":
        text = text.replace(
            "name: speckit-product", "disable-model-invocation: true\nname: speckit-product"
        )
    elif failure == "allowlist":
        text = text.replace("'speckit-product', ", "")
    else:
        text = text.replace(", 'agent'", "")
    path.write_text(text, encoding="utf-8")
    state.init_state(feature, "feature", HUMAN)
    with pytest.raises(FlowError, match="roster invalid"):
        orchestration.dispatch(
            feature, roster_file=root / ".specify" / "agents" / "roster.json", root=root
        )


def test_dispatch_cli_returns_brief(feature: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state.init_state(feature, "full-lifecycle", HUMAN)
    assert main(["workflow", "dispatch", "--feature-dir", str(feature), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["stage"] == "ideation"
    assert payload["profile"] == "full-lifecycle"
    assert payload["project_root"] == str(ROOT.resolve())
    assert payload["feature_dir"] == str(feature.resolve())


def test_worker_execution_contract_roots_commands_and_preserves_tool_restrictions() -> None:
    from speckit_flow import agents

    conductor = (ROOT / ".github" / "agents" / "speckit-conductor.agent.md").read_text(
        encoding="utf-8"
    )
    assert "Set-Location -LiteralPath '<project_root>' -ErrorAction Stop" in conductor
    assert "Test-Path -LiteralPath '<absolute-test-file>' -PathType Leaf" in conductor
    assert "Do not wrap workers in generic" in conductor
    assert "A prompt prohibition is not hard enforcement" in conductor
    roster = agents.load_roster()
    for agent in roster.values():
        if agent.role == "conductor":
            continue
        meta = agents.parse_frontmatter((ROOT / agent.file).read_text(encoding="utf-8"))
        assert "agent" not in meta["tools"], agent.id


@pytest.mark.parametrize(
    "relative_path",
    [".github/agents/speckit-conductor.agent.md", "docs/speckit-profiles.md"],
)
def test_worker_tool_diagnostics_preserve_unknown_and_failure_boundaries(
    relative_path: str,
) -> None:
    guidance = " ".join((ROOT / relative_path).read_text(encoding="utf-8").split())
    assert "Missing per-call tool overrides alone do not prove unsupported restrictions" in guidance
    assert "An unavailable diagnostic is not an observed enforcement failure" in guidance
    assert "If required enforcement remains unverified, stop" in guidance
    assert "If named-worker selection fails or forbidden delegation is observed, stop" in guidance
    assert "No observed nested calls does not prove that nesting was unavailable" in guidance
    assert "Static contract tests are not live-host enforcement evidence" in guidance
    assert "unverified_accepted" in guidance
    assert "workflow assurance status" in guidance


def test_standard_entry_and_direct_stage_skills_have_recursion_guard() -> None:
    entry = ROOT / ".github" / "skills" / "speckit-workflow" / "SKILL.md"
    text = entry.read_text(encoding="utf-8")
    assert "workflow recommend" in text
    assert "speckit-conductor" in text
    for stage in ("specify", "clarify", "plan", "tasks", "analyze", "implement"):
        body = (entry.parent.parent / f"speckit-{stage}" / "SKILL.md").read_text(encoding="utf-8")
        assert f"SPECKIT_DELEGATED_STAGE={stage}" in body
        assert f"SPECKIT_INLINE_STAGE={stage}" in body
        assert "speckit-workflow" in body
        assert body.index("## Lifecycle Handoff") < body.index("## User Input")


def test_review_instructions_bound_automatic_cycles_without_waiving_gates() -> None:
    conductor = (ROOT / ".github" / "agents" / "speckit-conductor.agent.md").read_text(
        encoding="utf-8"
    )
    entry = (ROOT / ".github" / "skills" / "speckit-workflow" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    review = (ROOT / ".github" / "skills" / "speckit-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "at most one automatic revision and one follow-up" in conductor
    assert "wait for explicit user direction" in conductor
    assert "Never bypass strict review, sensor or gate" in conductor
    assert "standalone read-only review" in entry
    assert "not source-bound lifecycle gate evidence" in entry
    assert "one automatic\n   follow-up per reviewer" in review
    assert "never treat a stale" in review.lower()


def test_delegated_entry_distinguishes_active_conductor_from_host() -> None:
    entry = (ROOT / ".github/skills/speckit-workflow/SKILL.md").read_text(encoding="utf-8")
    conductor = (ROOT / ".github/agents/speckit-conductor.agent.md").read_text(encoding="utf-8")
    assert "choose exactly one coordinator path" in entry
    assert "Already running as `speckit-conductor`" in entry
    assert "Another host with named conductor and nested-worker support" in entry
    assert "Otherwise:" in entry
    assert "No-progress stop" in entry
    assert "Never invoke another conductor" in conductor
    assert "record the\ninvocation failed and stop" in conductor


@pytest.mark.parametrize("stage", ["specify", "plan", "tasks", "implement", "clarify", "analyze"])
def test_assigned_worker_bad_marker_stops_instead_of_reentering(stage: str) -> None:
    body = (ROOT / f".github/skills/speckit-{stage}/SKILL.md").read_text(encoding="utf-8")
    guard = body.split("## Lifecycle Handoff", 1)[1].split("## User Input", 1)[0]
    assert "active invocation brief, not marker examples" in guard
    assert "missing, conflicting or mismatched stage marker" in guard
    assert "stop and report it to the conductor; do not invoke workflow or conductor" in guard
    assert "An unassigned direct stage command may hand off once" in guard


def test_workflow_file_handles_top_level_conductor_and_inline_routes() -> None:
    import yaml

    path = ROOT / ".specify/workflows/speckit/workflow.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    prompt = workflow["steps"][0]["prompt"]
    assert "For inline routes" in prompt
    assert "already active speckit-conductor coordinates one stage directly" in prompt
    assert "Never invoke another conductor" in prompt
    assert "Do not re-enter the same handoff on no progress" in prompt


@pytest.mark.parametrize("available", [True, False])
def test_installed_engine_prompt_dispatch(available: bool) -> None:
    yaml = pytest.importorskip("yaml")
    prompt_step = pytest.importorskip("specify_cli.workflows.steps.prompt")
    base = pytest.importorskip("specify_cli.workflows.base")
    from unittest.mock import patch

    workflow = yaml.safe_load(
        (ROOT / ".specify" / "workflows" / "speckit" / "workflow.yml").read_text("utf-8")
    )
    config = workflow["steps"][0]
    context = base.StepContext(
        project_root=str(ROOT),
        inputs={"spec": "Add reading lists", "integration": "copilot"},
    )
    with patch.object(
        prompt_step.PromptStep,
        "_try_dispatch",
        return_value={"exit_code": 0, "stdout": "", "stderr": ""} if available else None,
    ) as invoked:
        result = prompt_step.PromptStep().execute(config, context)
    expected = base.StepStatus.COMPLETED if available else base.StepStatus.FAILED
    assert result.status == expected
    assert result.output["dispatched"] is available
    assert "Add reading lists" in invoked.call_args.args[0]
    assert "speckit-workflow" in invoked.call_args.args[0]


def test_profile_overrides_are_used(feature: Path, tmp_path: Path) -> None:
    profiles = tmp_path / ".specify" / "profiles"
    shutil.copytree(DEFAULT_PROFILES_DIR, profiles)
    path = profiles / "feature.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["assignments"] = {"specify": {"lead": "architect", "support": ["quality"]}}
    path.write_text(json.dumps(data), encoding="utf-8")
    state.init_state(feature, "feature", HUMAN, profiles)
    result = orchestration.dispatch(feature, profiles_dir=profiles)
    assert result["lead"]["id"] == "architect"
    assert [a["id"] for a in result["support"]] == ["quality"]
    data["assignments"] = {"specify": {"lead": "design", "support": []}}
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FlowError, match="needs edit and execute"):
        orchestration.dispatch(feature, profiles_dir=profiles)
