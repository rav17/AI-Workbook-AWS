from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import audit, state
from speckit_flow.cli import main
from speckit_flow.models import FlowError

H = "human:workflow-test"
STAGES = ["specify", "plan", "tasks", "implement"]
GATES = ["specify", "plan"]


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    feature = tmp_path / "specs" / "020-demo"
    feature.mkdir(parents=True)
    return feature


def _begin(feature_dir: Path, stages: list[str] = STAGES, gates: list[str] = GATES) -> None:
    state.begin_workflow(feature_dir, stages, gates, H)


def _types(feature_dir: Path) -> list[str]:
    return [event.type for event in audit.read_events(feature_dir)]


def test_begin_initializes_default_profile_and_checks_expected_route(feature_dir: Path) -> None:
    result = state.begin_workflow(feature_dir, STAGES, GATES, H)

    assert result.profile == "feature"
    assert result.current_stage == "specify"
    assert (feature_dir / "state.json").exists()
    assert audit.verify_chain(feature_dir) is None


def test_begin_does_not_reinitialize_existing_state(feature_dir: Path) -> None:
    state.init_state(feature_dir, "feature", H)
    state.start_stage(feature_dir, "specify", H)
    before = {
        name: (feature_dir / name).read_bytes()
        for name in ("state.json", "state.md", "audit.jsonl")
    }

    result = state.begin_workflow(feature_dir, STAGES, GATES, H)

    assert result.current_stage == "specify"
    assert {name: (feature_dir / name).read_bytes() for name in before} == before


def test_begin_rejects_profile_route_mismatch_without_mutation(feature_dir: Path) -> None:
    state.init_state(feature_dir, "bugfix", H)
    before = (feature_dir / "state.json").read_bytes()
    events_before = (feature_dir / "audit.jsonl").read_bytes()

    with pytest.raises(FlowError, match="does not match"):
        state.begin_workflow(feature_dir, STAGES, GATES, H)

    assert (feature_dir / "state.json").read_bytes() == before
    assert (feature_dir / "audit.jsonl").read_bytes() == events_before


def test_begin_rejects_broken_audit_without_mutation(feature_dir: Path) -> None:
    state.init_state(feature_dir, "feature", H)
    path = feature_dir / "audit.jsonl"
    path.write_text(
        path.read_text(encoding="utf-8").replace('"profile_selected"', '"failure"'),
        encoding="utf-8",
    )
    before = path.read_bytes()

    with pytest.raises(FlowError, match="audit trail integrity"):
        state.begin_workflow(feature_dir, STAGES, GATES, H)

    assert path.read_bytes() == before


def test_begin_rejects_malformed_state_without_mutation(feature_dir: Path) -> None:
    path = feature_dir / "state.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(FlowError, match="corrupt"):
        state.begin_workflow(feature_dir, STAGES, GATES, H)

    assert path.read_text(encoding="utf-8") == "{"


def test_begin_does_not_initialize_when_audit_exists_without_state(feature_dir: Path) -> None:
    audit_path = feature_dir / "audit.jsonl"
    audit_path.write_text("", encoding="utf-8")

    with pytest.raises(FlowError, match="run 'rebuild'"):
        state.begin_workflow(feature_dir, STAGES, GATES, H)

    assert not (feature_dir / "state.json").exists()
    assert audit_path.read_text(encoding="utf-8") == ""


def test_begin_rejects_broken_audit_without_state(feature_dir: Path) -> None:
    audit_path = feature_dir / "audit.jsonl"
    audit_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FlowError, match="audit trail integrity"):
        state.begin_workflow(feature_dir, STAGES, GATES, H)

    assert not (feature_dir / "state.json").exists()
    assert audit_path.read_text(encoding="utf-8") == "{}\n"


@pytest.mark.parametrize(
    ("stages", "gates"),
    [
        ([], GATES),
        (["specify", "specify"], GATES),
        (["specify", "unknown"], GATES),
        (["specify", "tasks", "implement"], ["specify"]),
        (STAGES, ["plan", "specify"]),
        (STAGES, ["unknown"]),
    ],
)
def test_begin_rejects_invalid_expected_route(
    feature_dir: Path, stages: list[str], gates: list[str]
) -> None:
    with pytest.raises(FlowError):
        state.begin_workflow(feature_dir, stages, gates, H)

    assert not (feature_dir / "state.json").exists()


def test_workflow_begin_cli(feature_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "workflow",
            "begin",
            "--stages",
            ",".join(STAGES),
            "--gates",
            ",".join(GATES),
            "--feature-dir",
            str(feature_dir),
            "--actor",
            H,
        ]
    )

    assert code == 0
    assert "profile=feature" in capsys.readouterr().out


def test_workflow_begin_cli_rejects_missing_route_options(
    feature_dir: Path,
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["workflow", "begin", "--feature-dir", str(feature_dir), "--actor", H])

    assert exc.value.code == 2
    assert not (feature_dir / "state.json").exists()


def test_workflow_yaml_dispatches_profile_aware_session() -> None:
    yaml = pytest.importorskip("yaml")
    repo = Path(__file__).resolve().parents[3]
    workflow = yaml.safe_load(
        (repo / ".specify" / "workflows" / "speckit" / "workflow.yml").read_text(encoding="utf-8")
    )
    assert len(workflow["steps"]) == 1
    session = workflow["steps"][0]
    assert session["type"] == "prompt"
    assert session["integration"] == "{{ inputs.integration }}"
    assert "{{ inputs.spec }}" in session["prompt"]
    assert "speckit-workflow" in session["prompt"]
    assert "speckit-conductor" in session["prompt"]
    assert "workflow dispatch" in session["prompt"]
    assert "human gates" in session["prompt"]
    assert "Session completion" in session["prompt"]
    assert "stage start specify" not in session["prompt"]
    assert workflow["requires"]["integrations"]["any"] == ["copilot"]


def test_workflow_stage_transition_order(feature_dir: Path) -> None:
    _begin(feature_dir)
    expected: list[str] = []
    for stage in STAGES:
        state.start_stage(feature_dir, stage, "agent:workflow")
        expected.append("stage_started")
        state.done_stage(feature_dir, stage, "agent:workflow")
        expected.append("stage_completed")
        if stage in GATES:
            state.decide_gate(feature_dir, stage, True, H)
            expected.append("gate_approved")

    actual = [
        event.type
        for event in audit.read_events(feature_dir)
        if event.type in {"stage_started", "stage_completed", "gate_approved"}
    ]
    assert actual == expected


def test_rejected_gate_is_audited_and_blocks_later_stage(feature_dir: Path) -> None:
    _begin(feature_dir)
    state.start_stage(feature_dir, "specify", "agent:workflow")
    state.done_stage(feature_dir, "specify", "agent:workflow")
    state.decide_gate(feature_dir, "specify", False, H, "rejected in workflow")

    assert state.load_state(feature_dir).pending_gate is None
    assert state.load_state(feature_dir).stages["specify"].status == "pending"
    assert _types(feature_dir)[-1] == "gate_rejected"
    with pytest.raises(FlowError, match="out of order"):
        state.start_stage(feature_dir, "plan", "agent:workflow")


def test_failed_stage_is_not_completed(feature_dir: Path) -> None:
    _begin(feature_dir)
    state.start_stage(feature_dir, "specify", "agent:workflow")

    assert state.load_state(feature_dir).stages["specify"].status == "in_progress"
    assert "stage_completed" not in _types(feature_dir)


def test_status_and_resume_fail_on_broken_audit(feature_dir: Path) -> None:
    state.init_state(feature_dir, "feature", H)
    audit_path = feature_dir / "audit.jsonl"
    audit_path.write_text(audit_path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")

    for command in ("status", "resume"):
        assert main([command, "--feature-dir", str(feature_dir), "--actor", H]) == 1


def test_workflow_registry_matches_profile_aware_definition() -> None:
    yaml = pytest.importorskip("yaml")
    repo = Path(__file__).resolve().parents[3]
    workflow = yaml.safe_load(
        (repo / ".specify" / "workflows" / "speckit" / "workflow.yml").read_text(encoding="utf-8")
    )
    registry = json.loads(
        (repo / ".specify" / "workflows" / "workflow-registry.json").read_text("utf-8")
    )
    installed = registry["workflows"]["speckit"]
    assert installed["version"] == workflow["workflow"]["version"]
    assert installed["name"] == workflow["workflow"]["name"]


def test_workflow_definition_passes_installed_engine_validation() -> None:
    engine = pytest.importorskip("specify_cli.workflows.engine")
    repo = Path(__file__).resolve().parents[3]
    definition = engine.WorkflowDefinition.from_yaml(
        repo / ".specify" / "workflows" / "speckit" / "workflow.yml"
    )

    assert engine.validate_workflow(definition) == []
