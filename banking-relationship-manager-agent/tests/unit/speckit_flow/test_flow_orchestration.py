from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from speckit_flow import audit, orchestration, reviews, state
from speckit_flow.cli import main
from speckit_flow.models import FlowError
from speckit_flow.profiles import DEFAULT_PROFILES_DIR, load_profiles

ROOT = Path(__file__).resolve().parents[3]
HUMAN = "human:test"


@pytest.mark.parametrize(
    ("description", "profile"),
    [
        ("Create a new feature for export", "full-lifecycle"),
        ("Add reading lists", "full-lifecycle"),
        ("Fix a crash in the parser", "bugfix"),
        ("Hotfix the login failure", "bugfix"),
        ("Patch a CVE in a dependency", "security-patch"),
        ("Fix a security vulnerability", "security-patch"),
        ("Refactor request handling", "refactor"),
        ("Add Terraform infrastructure", "infra"),
        ("Build a proof of concept", "poc"),
        ("Plan high-assurance delivery", "enterprise"),
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
    del available["full-lifecycle"]
    assert orchestration.recommend("Create a new feature", available)["needs_clarification"]


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
    assert payload["profile"] == "full-lifecycle"
    assert list(tmp_path.iterdir()) == []


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


@pytest.mark.parametrize("profile", list(load_profiles()))
def test_every_profile_has_callable_initial_stage(feature: Path, profile: str) -> None:
    state.init_state(feature, profile, HUMAN)
    result = orchestration.dispatch(feature)
    assert result["stage"] == load_profiles()[profile].stages[0]
    assert result["lead"]["agent_name"].startswith("speckit-")


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


def test_standard_entry_and_direct_stage_skills_have_recursion_guard() -> None:
    entry = ROOT / ".github" / "skills" / "speckit-workflow" / "SKILL.md"
    text = entry.read_text(encoding="utf-8")
    assert "workflow recommend" in text
    assert "speckit-conductor" in text
    for stage in ("specify", "clarify", "plan", "tasks", "analyze", "implement"):
        body = (entry.parent.parent / f"speckit-{stage}" / "SKILL.md").read_text(encoding="utf-8")
        assert f"SPECKIT_DELEGATED_STAGE={stage}" in body
        assert "speckit-workflow" in body
        assert body.index("## Lifecycle Handoff") < body.index("## User Input")


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
