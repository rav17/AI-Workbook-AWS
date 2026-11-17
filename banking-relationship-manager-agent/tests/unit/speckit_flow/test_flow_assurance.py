from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from speckit_flow import assurance, audit, orchestration, state
from speckit_flow.cli import main
from speckit_flow.models import FlowError

ROOT = Path(__file__).resolve().parents[3]
HUMAN = "human:test"
HOST = "copilot-sdk"
SESSION = "session-a"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "project"
    shutil.copytree(ROOT / ".github" / "agents", root / ".github" / "agents")
    feature = root / "specs" / "001-example"
    feature.mkdir(parents=True)
    monkeypatch.setattr("speckit_flow.cli._REPO_ROOT", root)
    return root, feature


@pytest.fixture
def feature(project: tuple[Path, Path]) -> tuple[Path, Path]:
    root, directory = project
    state.init_state(directory, "feature", HUMAN)
    return root, directory


def accept(root: Path, directory: Path) -> dict[str, object]:
    return assurance.accept(
        directory,
        "specify",
        HOST,
        SESSION,
        HUMAN,
        "Accept ordinary development without isolation proof",
        "Named smoke test returned expected stages",
        True,
        root=root,
    )


def test_missing_acceptance_is_explicit_and_read_only(feature: tuple[Path, Path]) -> None:
    root, directory = feature
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    result = assurance.status(directory, "specify", HOST, SESSION, root=root)
    assert result["status"] == "not_accepted"
    assert result["runtime_enforcement"] == "unverified"
    assert "agent" not in result["declared_tools"]["speckit-product"]
    assert result["reason"]
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}


def test_acceptance_preserves_history_and_never_certifies_runtime(
    feature: tuple[Path, Path],
) -> None:
    root, directory = feature
    prior_audit = (directory / "audit.jsonl").read_bytes()
    prior_state = (directory / "state.json").read_bytes()
    result = accept(root, directory)
    assert result["status"] == "unverified_accepted"
    assert result["runtime_enforcement"] == "unverified"
    assert (directory / "state.json").read_bytes() == prior_state
    assert (directory / "audit.jsonl").read_bytes().startswith(prior_audit)
    event = audit.read_events(directory)[-1]
    detail = json.loads(event.detail)
    assert detail["observation"] == "Named smoke test returned expected stages"
    assert "unverified" in detail["missing_evidence"].lower()
    assert detail["residual_risk"]
    assert len(event.detail) <= 500
    inspection = orchestration.dispatch(directory, root=root)["delegation_assurance"]
    assert inspection["status"] == "context_required"
    assert inspection["runtime_enforcement"] == "unverified"
    state.start_stage(directory, "specify", "agent:conductor")
    assert assurance.status(directory, "specify", HOST, SESSION, root=root)["status"] == (
        "unverified_accepted"
    )


@pytest.mark.parametrize(
    ("actor", "confirmed", "reason", "observation"),
    [
        ("agent:workflow", True, "Ordinary work", "No runtime proof"),
        ("human:", True, "Ordinary work", "No runtime proof"),
        (HUMAN, False, "Ordinary work", "No runtime proof"),
        (HUMAN, True, "", "No runtime proof"),
        (HUMAN, True, "x" * 61, "No runtime proof"),
        (HUMAN, True, "Ordinary work", ""),
        (HUMAN, True, "Ordinary work", "x" * 61),
        (HUMAN, True, "password=unsafe-example", "No runtime proof"),
    ],
)
def test_invalid_acceptance_does_not_append(
    feature: tuple[Path, Path], actor: str, confirmed: bool, reason: str, observation: str
) -> None:
    root, directory = feature
    before = (directory / "audit.jsonl").read_bytes()
    with pytest.raises(FlowError):
        assurance.accept(
            directory,
            "specify",
            HOST,
            SESSION,
            actor,
            reason,
            observation,
            confirmed,
            root=root,
        )
    assert (directory / "audit.jsonl").read_bytes() == before


@pytest.mark.parametrize(("host", "session"), [("", SESSION), (HOST, ""), ("x" * 25, SESSION)])
def test_unknown_or_oversized_context_is_not_invented(
    feature: tuple[Path, Path], host: str, session: str
) -> None:
    root, directory = feature
    with pytest.raises(FlowError, match="identifier"):
        assurance.status(directory, "specify", host, session, root=root)


@pytest.mark.parametrize("change", ["session", "worker", "redo", "reset"])
def test_changed_scope_requires_fresh_acceptance(feature: tuple[Path, Path], change: str) -> None:
    root, directory = feature
    accept(root, directory)
    session = SESSION
    if change == "session":
        session = "session-b"
    elif change == "worker":
        path = root / ".github" / "agents" / "speckit-product.agent.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    else:
        event_type = "stage_redone" if change == "redo" else "calls_reset"
        audit.append_event(directory, event_type, "specify", HUMAN, "new bounded attempt")
    result = assurance.status(directory, "specify", HOST, session, root=root)
    assert result["status"] == "stale"
    assert result["runtime_enforcement"] == "unverified"


@pytest.mark.parametrize("profile", ["hybrid-plan", "enterprise", "security-patch", "quick"])
def test_strict_or_nonordinary_routes_cannot_use_acceptance(
    project: tuple[Path, Path], profile: str
) -> None:
    root, directory = project
    options = (
        {"reviewer": "hybrid-plan-reviewer", "confirm_route": True, "rationale": "Plan review"}
        if profile == "hybrid-plan"
        else {}
    )
    state.init_state(directory, profile, HUMAN, **options)
    before = (directory / "audit.jsonl").read_bytes()
    result = assurance.status(directory, "specify", HOST, SESSION, root=root)
    assert result["status"] == "ineligible"
    with pytest.raises(FlowError, match="ineligible"):
        accept(root, directory)
    assert (directory / "audit.jsonl").read_bytes() == before


def test_custom_profile_does_not_inherit_the_exception(project: tuple[Path, Path]) -> None:
    root, directory = project
    profiles = root / "profiles"
    profiles.mkdir()
    (profiles / "custom.json").write_text(
        json.dumps(
            {
                "id": "custom",
                "description": "Ordinary custom work",
                "stages": ["specify"],
                "depth": "standard",
                "gates": [],
            }
        ),
        encoding="utf-8",
    )
    state.init_state(directory, "custom", HUMAN, profiles)
    assert (
        assurance.status(
            directory,
            "specify",
            HOST,
            SESSION,
            root=root,
            profiles_dir=profiles,
        )["status"]
        == "ineligible"
    )


@pytest.mark.parametrize("damage", ["malformed", "nonhuman", "chain", "version"])
def test_bad_latest_evidence_cannot_fall_back_to_older_acceptance(
    feature: tuple[Path, Path], damage: str
) -> None:
    root, directory = feature
    accept(root, directory)
    if damage == "chain":
        path = directory / "audit.jsonl"
        path.write_text(
            path.read_text(encoding="utf-8").replace("human:test", "human:other", 1),
            encoding="utf-8",
        )
    else:
        detail = "{}" if damage == "malformed" else audit.read_events(directory)[-1].detail
        if damage == "version":
            payload = json.loads(detail)
            payload["version"] = True
            detail = json.dumps(payload, separators=(",", ":"))
        actor = "agent:workflow" if damage == "nonhuman" else HUMAN
        audit.append_event(directory, "delegation_assurance_accepted", "specify", actor, detail)
    with pytest.raises(FlowError):
        assurance.status(directory, "specify", HOST, SESSION, root=root)


@pytest.mark.parametrize("outcome", ["running", "failed"])
def test_known_call_problems_are_not_overridden(feature: tuple[Path, Path], outcome: str) -> None:
    root, directory = feature
    accept(root, directory)
    state.start_stage(directory, "specify", "agent:conductor")
    reserved = audit.append_event(
        directory,
        "call_reserved",
        "specify",
        "agent:conductor",
        "product",
    )
    if outcome == "failed":
        audit.append_event(
            directory,
            "call_finished",
            "specify",
            "agent:conductor",
            json.dumps({"id": reserved.seq, "outcome": "failed"}),
        )
    before = (directory / "audit.jsonl").read_bytes()
    assert assurance.status(directory, "specify", HOST, SESSION, root=root)["status"] == "blocked"
    with pytest.raises(FlowError, match="blocked"):
        accept(root, directory)
    assert (directory / "audit.jsonl").read_bytes() == before


def test_pending_gate_and_other_feature_do_not_inherit_acceptance(
    feature: tuple[Path, Path],
) -> None:
    root, directory = feature
    accept(root, directory)
    other = directory.parent / "002-other"
    other.mkdir()
    state.init_state(other, "feature", HUMAN)
    assert assurance.status(other, "specify", HOST, SESSION, root=root)["status"] == "not_accepted"
    state.start_stage(directory, "specify", "agent:conductor")
    state.done_stage(directory, "specify", "agent:conductor")
    with pytest.raises(FlowError, match="gate"):
        assurance.status(directory, "plan", HOST, SESSION, root=root)


def test_cli_acceptance_and_non_authorizing_inspection(
    feature: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    _, directory = feature
    common = [
        "--feature-dir",
        str(directory),
        "--stage",
        "specify",
        "--host",
        HOST,
        "--session-id",
        SESSION,
        "--json",
    ]
    assert main(["workflow", "assurance", "status", *common]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "not_accepted"
    assert (
        main(
            [
                "workflow",
                "assurance",
                "accept",
                *common,
                "--actor",
                HUMAN,
                "--reason",
                "Ordinary development",
                "--observation",
                "No runtime proof",
                "--confirm-ordinary-work",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "unverified_accepted"
    assert main(["workflow", "dispatch", "--feature-dir", str(directory), "--json"]) == 0
    inspection = json.loads(capsys.readouterr().out)
    assert inspection["status"] == "ready"
    assert inspection["delegation_assurance"]["status"] == "context_required"


def test_exact_field_limit_and_aggregate_serialization_limit(
    feature: tuple[Path, Path],
) -> None:
    root, directory = feature
    result = assurance.accept(
        directory,
        "specify",
        HOST,
        SESSION,
        HUMAN,
        "ordinary " * 6 + "sample",
        "Current named agent returned expected results",
        True,
        root=root,
    )
    assert result["status"] == "unverified_accepted"
    before = (directory / "audit.jsonl").read_bytes()
    with pytest.raises(FlowError):
        assurance.accept(
            directory,
            "specify",
            HOST,
            SESSION,
            HUMAN,
            "\\" * 60,
            "\\" * 60,
            True,
            root=root,
        )
    assert (directory / "audit.jsonl").read_bytes() == before


def test_pending_implementation_uses_the_same_existing_feature_route(
    feature: tuple[Path, Path],
) -> None:
    root, directory = feature
    for stage in ("specify", "plan", "tasks"):
        state.start_stage(directory, stage, "agent:conductor")
        state.done_stage(directory, stage, "agent:conductor")
        if stage != "tasks":
            state.decide_gate(directory, stage, True, HUMAN)
    previous_state = (directory / "state.json").read_bytes()
    result = assurance.accept(
        directory,
        "implement",
        HOST,
        SESSION,
        HUMAN,
        "Ordinary packaging work",
        "Missing runtime isolation evidence",
        True,
        root=root,
    )
    assert result["status"] == "unverified_accepted"
    assert (directory / "state.json").read_bytes() == previous_state
    assert state.load_state(directory).stages["implement"].status == "pending"
