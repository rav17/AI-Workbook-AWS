from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from speckit_flow import audit, calls, orchestration, reviews, session, state
from speckit_flow.cli import main
from speckit_flow.models import FlowError

ACTOR = "agent:conductor"
STAGE = "specify"


@pytest.fixture
def feature(tmp_path: Path) -> Path:
    directory = tmp_path / "specs" / "001-call-bounds"
    directory.mkdir(parents=True)
    state.init_state(directory, "feature", "human:test")
    state.start_stage(directory, STAGE, ACTOR)
    return directory


def reserve(feature: Path, agent: str) -> int:
    result = calls.reserve(feature, STAGE, agent, ACTOR)
    return int(result["id"])


def finish(feature: Path, call_id: int, outcome: str = "succeeded") -> None:
    calls.finish(feature, STAGE, call_id, outcome, ACTOR)


def supports(feature: Path) -> None:
    # Reservations are serialized; the independent workers may run concurrently.
    ids = [reserve(feature, a["id"]) for a in orchestration.dispatch(feature)["support"]]
    for call_id in ids:
        finish(feature, call_id)


def lead(feature: Path) -> int:
    supports(feature)
    call_id = reserve(feature, "product")
    finish(feature, call_id)
    return call_id


def test_persistent_duplicate_and_support_budget(feature: Path) -> None:
    call_id = reserve(feature, "design")
    with pytest.raises(FlowError, match="duplicate dispatch"):
        reserve(feature, "design")
    finish(feature, call_id)
    with pytest.raises(FlowError, match="budget exhausted"):
        reserve(feature, "design")
    assert calls.status(feature, STAGE) == [
        {"id": call_id, "agent": "design", "status": "succeeded"}
    ]
    assert audit.verify_chain(feature) is None


def test_call_audit_keeps_only_safe_synthetic_metadata(feature: Path) -> None:
    call_id = reserve(feature, "design")
    finish(feature, call_id)

    audit_text = (feature / audit.AUDIT_FILE).read_text(encoding="utf-8")
    reservations = [event for event in audit.read_events(feature) if event.type == "call_reserved"]
    assert [event.detail for event in reservations] == ["design"]
    assert "review_prompt" not in audit_text
    assert "BEGIN_PLAN" not in audit_text


def test_one_revision_and_one_followup_review(feature: Path) -> None:
    lead(feature)
    with pytest.raises(FlowError, match="initial assigned reviews"):
        reserve(feature, "product")
    review_id = reserve(feature, "product-lead")
    finish(feature, review_id)
    with pytest.raises(FlowError, match="single lead revision"):
        reserve(feature, "product-lead")
    finish(feature, reserve(feature, "product"))
    finish(feature, reserve(feature, "product-lead"))
    for agent in ("product", "product-lead"):
        with pytest.raises(FlowError, match="budget exhausted"):
            reserve(feature, agent)
    # 2 supports + 2 lead calls + 2 review calls, never more in this attempt.
    assert len(calls.status(feature, STAGE)) == 6
    state.done_stage(feature, STAGE, ACTOR)
    assert state.load_state(feature).pending_gate == STAGE
    with pytest.raises(FlowError, match="pending human gate"):
        calls.reserve(feature, "plan", "architect", ACTOR)


def test_revision_requires_a_followup_before_completion(feature: Path) -> None:
    lead(feature)
    finish(feature, reserve(feature, "product-lead"))
    finish(feature, reserve(feature, "product"))
    with pytest.raises(FlowError, match="reviews of the latest lead work"):
        state.done_stage(feature, STAGE, ACTOR)
    finish(feature, reserve(feature, "product-lead"))
    state.done_stage(feature, STAGE, ACTOR)
    assert state.load_state(feature).pending_gate == STAGE


def test_full_feature_route_with_bounded_accounting(tmp_path: Path) -> None:
    directory = tmp_path / "specs" / "001-feature-route"
    directory.mkdir(parents=True)
    state.init_state(directory, "feature", "human:test")
    completed = []
    gates = []
    for stage in ("specify", "plan", "tasks", "implement"):
        brief = orchestration.dispatch(directory)
        assert brief["stage"] == stage
        assert brief["execution"] == "delegated"
        state.start_stage(directory, stage, ACTOR)
        for worker in brief["support"]:
            call_id = calls.reserve(directory, stage, worker["id"], ACTOR)["id"]
            calls.finish(directory, stage, call_id, "succeeded", ACTOR)
        call_id = calls.reserve(directory, stage, brief["lead"]["id"], ACTOR)["id"]
        calls.finish(directory, stage, call_id, "succeeded", ACTOR)
        for worker in brief["reviewers"]:
            call_id = calls.reserve(directory, stage, worker["id"], ACTOR)["id"]
            calls.finish(directory, stage, call_id, "succeeded", ACTOR)
        state.done_stage(directory, stage, ACTOR)
        completed.append(stage)
        if brief["gated"]:
            gates.append(stage)
            with pytest.raises(FlowError, match="pending human gate"):
                orchestration.dispatch(directory)
            with pytest.raises(FlowError, match="only a human"):
                state.decide_gate(directory, stage, True, ACTOR)
            state.decide_gate(directory, stage, True, "human:test")
    assert completed == ["specify", "plan", "tasks", "implement"]
    assert gates == ["specify", "plan"]
    assert orchestration.dispatch(directory)["status"] == "complete"
    assert audit.verify_chain(directory) is None


def _selective_feature(tmp_path: Path) -> Path:
    directory = tmp_path / "specs" / "001-selective"
    directory.mkdir(parents=True)
    state.init_state(
        directory, "selective", "human:test", confirm_route=True, rationale="Selected plan review"
    )
    return directory


def _selective_review(directory: Path, verdict: str = "pass") -> None:
    call_id = calls.reserve(directory, "plan", "architecture-reviewer", "agent:workflow")["id"]
    calls.finish(directory, "plan", call_id, "succeeded", "agent:workflow")
    reviews.save_review(
        directory, "plan",
        {
            "reviewer": "plan", "author": "agent:workflow", "verdict": verdict,
            "files": ["plan.md"],
            "findings": [] if verdict == "pass" else [{
                "severity": "blocker", "file": "plan.md", "section": "Design",
                "note": "Synthetic unresolved design constraint",
            }],
        },
        "agent:architecture-reviewer",
    )


def test_selective_full_route_preserves_gates_and_requires_actual_review_records(
    tmp_path: Path,
) -> None:
    directory = _selective_feature(tmp_path)
    for stage, artifact in (
        ("specify", "spec.md"), ("plan", "plan.md"),
        ("tasks", "tasks.md"), ("implement", "tasks.md"),
    ):
        assert orchestration.next_action(directory)["action"] == "execute"
        state.start_stage(directory, stage, "agent:workflow")
        (directory / artifact).write_text(f"# Synthetic {stage}\n", encoding="utf-8")
        with pytest.raises(FlowError, match="recorded inline"):
            state.done_stage(directory, stage, "agent:workflow")
        calls.record_inline(directory, stage, "agent:workflow")
        if stage == "plan":
            with pytest.raises(FlowError, match="assigned worker results"):
                state.done_stage(directory, stage, "agent:workflow")
            _selective_review(directory)
        state.done_stage(directory, stage, "agent:workflow")
        if stage in ("specify", "plan"):
            assert orchestration.next_action(directory)["action"] == "await_human"
            with pytest.raises(FlowError, match="only a human"):
                state.decide_gate(directory, stage, True, "agent:workflow")
            state.decide_gate(directory, stage, True, "human:test")
    assert orchestration.next_action(directory)["action"] == "complete"
    assert audit.verify_chain(directory) is None


def _selective_plan(tmp_path: Path) -> Path:
    directory = _selective_feature(tmp_path)
    state.start_stage(directory, "specify", "agent:workflow")
    (directory / "spec.md").write_text("# Specification\n", encoding="utf-8")
    calls.record_inline(directory, "specify", "agent:workflow")
    state.done_stage(directory, "specify", "agent:workflow")
    state.decide_gate(directory, "specify", True, "human:test")
    state.start_stage(directory, "plan", "agent:workflow")
    (directory / "plan.md").write_text("# Plan\n", encoding="utf-8")
    return directory


def test_selective_review_order_freshness_and_revision_bound(tmp_path: Path) -> None:
    directory = _selective_plan(tmp_path)
    with pytest.raises(FlowError, match="current recorded inline"):
        calls.reserve(directory, "plan", "architecture-reviewer", "agent:workflow")
    calls.record_inline(directory, "plan", "agent:workflow")
    _selective_review(directory)
    (directory / "plan.md").write_text("# Revised plan\n", encoding="utf-8")
    with pytest.raises(FlowError, match="recorded inline"):
        state.done_stage(directory, "plan", "agent:workflow")
    calls.record_inline(directory, "plan", "agent:workflow")
    with pytest.raises(FlowError, match="latest inline work"):
        state.done_stage(directory, "plan", "agent:workflow")
    _selective_review(directory)
    with pytest.raises(FlowError, match="revision budget exhausted"):
        calls.record_inline(directory, "plan", "agent:workflow")
    state.done_stage(directory, "plan", "agent:workflow")
    (directory / "plan.md").write_text("# Changed after review\n", encoding="utf-8")
    with pytest.raises(FlowError, match="stale"):
        state.decide_gate(directory, "plan", True, "human:test")


def test_selective_block_needs_audited_human_override(tmp_path: Path) -> None:
    directory = _selective_plan(tmp_path)
    calls.record_inline(directory, "plan", "agent:workflow")
    _selective_review(directory, "block")
    state.done_stage(directory, "plan", "agent:workflow")
    with pytest.raises(FlowError, match="override-reason"):
        state.decide_gate(directory, "plan", True, "human:test")
    state.decide_gate(
        directory, "plan", True, "human:test", override_reason="Synthetic risk acceptance"
    )
    assert any(event.type == "gate_overridden" for event in audit.read_events(directory))


def test_selective_confirmation_cannot_be_replaced_or_rebuilt(tmp_path: Path) -> None:
    directory = tmp_path / "specs" / "001-selective"
    directory.mkdir(parents=True)
    with pytest.raises(FlowError, match="confirm-route"):
        state.init_state(directory, "selective", "human:test")
    assert list(directory.iterdir()) == []
    state.init_state(
        directory, "selective", "human:test", confirm_route=True, rationale="Explicit selection"
    )
    with pytest.raises(FlowError, match="cannot be rebuilt"):
        state.rebuild_state(directory, "human:test")
    path = directory / state.SELECTIVE_ROUTE_FILE
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert orchestration.next_action(directory)["action"] == "blocked"
    path.unlink()
    assert orchestration.next_action(directory)["action"] == "blocked"


def test_selective_supports_precede_inline_work_and_do_not_dispatch_a_lead(tmp_path: Path) -> None:
    directory = tmp_path / "specs" / "001-selective"
    directory.mkdir(parents=True)
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    from speckit_flow.profiles import get_profile

    profile = get_profile("selective").to_dict()
    profile["assignments"]["specify"]["support"] = ["design"]
    (profiles / "selective.json").write_text(json.dumps(profile), encoding="utf-8")
    state.init_state(
        directory, "selective", "human:test", profiles,
        confirm_route=True, rationale="Design input and plan review",
    )
    state.start_stage(directory, "specify", "agent:workflow", profiles)
    (directory / "spec.md").write_text("# Specification\n", encoding="utf-8")
    with pytest.raises(FlowError, match="successful assigned supports"):
        calls.record_inline(directory, "specify", "agent:workflow", profiles)
    with pytest.raises(FlowError, match="not assigned"):
        calls.reserve(directory, "specify", "product", "agent:workflow", profiles_dir=profiles)
    call_id = calls.reserve(
        directory, "specify", "design", "agent:workflow", profiles_dir=profiles
    )["id"]
    calls.finish(directory, "specify", call_id, "succeeded", "agent:workflow")
    calls.record_inline(directory, "specify", "agent:workflow", profiles)
    state.done_stage(directory, "specify", "agent:workflow", profiles)


def test_selective_successful_call_without_a_stage_review_cannot_complete(tmp_path: Path) -> None:
    directory = _selective_plan(tmp_path)
    calls.record_inline(directory, "plan", "agent:workflow")
    call_id = calls.reserve(directory, "plan", "architecture-reviewer", "agent:workflow")["id"]
    calls.finish(directory, "plan", call_id, "succeeded", "agent:workflow")
    with pytest.raises(FlowError, match="actual review result"):
        state.done_stage(directory, "plan", "agent:workflow")
    (directory / "unrelated.md").write_text("Synthetic unrelated artifact", encoding="utf-8")
    reviews.save_review(
        directory, "plan",
        {
            "reviewer": "plan", "author": "agent:workflow", "verdict": "pass",
            "findings": [], "files": ["unrelated.md"],
        },
        "agent:architecture-reviewer",
    )
    with pytest.raises(FlowError, match="did not review the stage artifact"):
        state.done_stage(directory, "plan", "agent:workflow")


def test_dependencies_and_authority(feature: Path) -> None:
    for actor in ("agent:product", "human:test", "agent:workflow"):
        with pytest.raises(FlowError, match="only agent:conductor"):
            calls.reserve(feature, STAGE, "design", actor)
    with pytest.raises(FlowError, match="not assigned"):
        reserve(feature, "conductor")
    with pytest.raises(FlowError, match="successful assigned supports"):
        reserve(feature, "product")
    with pytest.raises(FlowError, match="successful lead"):
        reserve(feature, "product-lead")
    supports(feature)
    lead_id = reserve(feature, "product")
    with pytest.raises(FlowError, match="successful lead"):
        reserve(feature, "product-lead")
    finish(feature, lead_id)


def test_failed_calls_freeze_attempt_and_completion(feature: Path) -> None:
    call_id = reserve(feature, "design")
    finish(feature, call_id, "failed")
    with pytest.raises(FlowError, match="human calls reset"):
        reserve(feature, "compliance")
    with pytest.raises(FlowError, match="running or failed"):
        state.done_stage(feature, STAGE, ACTOR)
    for actor, reason in ((ACTOR, "retry"), ("human:test", " ")):
        with pytest.raises(FlowError, match="only a human"):
            calls.reset(feature, STAGE, actor, reason)
    calls.reset(feature, STAGE, "human:test", "Tool availability restored")
    assert calls.status(feature, STAGE) == []
    assert reserve(feature, "design") > call_id
    assert audit.verify_chain(feature) is None


def test_interrupted_worker_is_not_automatically_retried(feature: Path) -> None:
    call_id = reserve(feature, "design")
    with pytest.raises(FlowError, match="running workers"):
        calls.reset(feature, STAGE, "human:test", "Resume interrupted work")
    with pytest.raises(FlowError, match="running or failed"):
        state.done_stage(feature, STAGE, ACTOR)
    # Mark failed only after the actual worker has stopped; no timeout frees a slot.
    finish(feature, call_id, "failed")
    with pytest.raises(FlowError, match="not running"):
        finish(feature, call_id)


def test_redo_starts_new_attempt_only_by_human_direction(feature: Path) -> None:
    lead(feature)
    with pytest.raises(FlowError, match="only a human"):
        session.redo_stage(feature, STAGE, ACTOR, "retry")
    session.redo_stage(feature, STAGE, "human:test", "Revised requirements")
    state.start_stage(feature, STAGE, ACTOR)
    assert calls.status(feature, STAGE) == []
    supports(feature)


def test_pending_and_inline_stages_cannot_reserve(tmp_path: Path) -> None:
    for profile in ("feature", "quick"):
        directory = tmp_path / profile
        directory.mkdir()
        state.init_state(directory, profile, "human:test")
        with pytest.raises(FlowError, match="already in progress"):
            reserve(directory, "design")
        if profile == "quick":
            state.start_stage(directory, STAGE, ACTOR)
            with pytest.raises(FlowError, match="delegated stage"):
                reserve(directory, "product")


def test_hybrid_blocks_reservations_and_preserves_existing_call_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "specs" / "001-hybrid"
    directory.mkdir(parents=True)
    state.init_state(
        directory, "hybrid-plan", "human:test", reviewer="architecture-reviewer",
        confirm_route=True, rationale="Independent plan review",
    )
    state.start_stage(directory, "specify", "agent:workflow")
    state.done_stage(directory, "specify", "agent:workflow")
    state.decide_gate(directory, "specify", True, "human:test")
    state.start_stage(directory, "plan", "agent:workflow")
    (directory / "plan.md").write_text("# Synthetic plan\n", encoding="utf-8")
    with pytest.raises(FlowError, match="workflow host or conductor"):
        calls.reserve(directory, "plan", "architecture-reviewer", "agent:architect")
    with pytest.raises(FlowError, match="dispatch blocked"):
        calls.reserve(directory, "plan", "architect", "agent:workflow")
    cli_args = [
        "--feature-dir", str(directory), "--stage", "plan",
        "--actor", "agent:workflow", "--json",
    ]
    before = (directory / audit.AUDIT_FILE).read_bytes()
    for _ in range(2):
        assert main(["workflow", "calls", "reserve", "architecture-reviewer", *cli_args]) == 1
        assert "do not retry" in capsys.readouterr().err
    assert calls.status(directory, "plan") == []
    assert (directory / audit.AUDIT_FILE).read_bytes() == before
    assert not (directory / calls.LOCK_FILE).exists()
    # An interrupted invocation from before dispatch was blocked can still be closed.
    call_id = audit.append_event(
        directory, "call_reserved", "plan", "agent:workflow", "architecture-reviewer"
    ).seq
    assert calls.status(directory, "plan") == [
        {"id": call_id, "agent": "architecture-reviewer", "status": "running"}
    ]
    assert (
        main(
            [
                "workflow", "calls", "finish", str(call_id),
                "--outcome", "succeeded", *cli_args,
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert orchestration.dispatch(directory)["review_status"]["invocation_outcome"] == "succeeded"
    with pytest.raises(FlowError, match="host-observed review input evidence"):
        state.done_stage(directory, "plan", "agent:workflow")
    assert state.load_state(directory).stages["plan"].status == "in_progress"
    with pytest.raises(FlowError, match="dispatch blocked"):
        calls.reserve(directory, "plan", "architecture-reviewer", "agent:workflow")
    current = state.load_state(directory)
    current.pending_gate = "plan"
    state.save_state(directory, current)
    with pytest.raises(FlowError, match="host.*review input evidence"):
        state.decide_gate(directory, "plan", True, "human:test")


def test_hybrid_failed_reviewer_is_not_retried_or_reported_as_a_verdict(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "specs" / "001-hybrid-failure"
    directory.mkdir(parents=True)
    state.init_state(
        directory, "hybrid-plan", "human:test", reviewer="architecture-reviewer",
        confirm_route=True, rationale="Independent plan review",
    )
    state.start_stage(directory, "specify", "agent:workflow")
    state.done_stage(directory, "specify", "agent:workflow")
    state.decide_gate(directory, "specify", True, "human:test")
    state.start_stage(directory, "plan", "agent:workflow")
    (directory / "plan.md").write_text("# Synthetic plan\n", encoding="utf-8")
    call_id = audit.append_event(
        directory, "call_reserved", "plan", "agent:workflow", "architecture-reviewer"
    ).seq
    calls.finish(directory, "plan", call_id, "failed", "agent:workflow")
    status = orchestration.dispatch(directory)["review_status"]
    assert status["invocation_outcome"] == "failed"
    assert status["verdict"] == "not_available"
    with pytest.raises(FlowError, match="invocation failed"):
        state.done_stage(directory, "plan", "agent:workflow")
    with pytest.raises(FlowError, match="dispatch blocked"):
        calls.reserve(directory, "plan", "architecture-reviewer", "agent:workflow")


def test_corrupt_audit_and_abandoned_lock_fail_explicitly(feature: Path) -> None:
    lock = feature / calls.LOCK_FILE
    lock.write_text("existing owner", encoding="utf-8")
    with pytest.raises(FlowError, match="lock"):
        reserve(feature, "design")
    assert lock.read_text(encoding="utf-8") == "existing owner"
    lock.unlink()
    path = feature / audit.AUDIT_FILE
    path.write_text(path.read_text(encoding="utf-8").replace("profile=feature", "changed"))
    with pytest.raises(FlowError, match="audit trail integrity"):
        reserve(feature, "design")
    assert not lock.exists()


def test_cli_reservation_and_result(feature: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--feature-dir", str(feature), "--stage", STAGE, "--actor", ACTOR, "--json"]
    assert main(["workflow", "calls", "reserve", "design", *args]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["used"] == data["limit"] == 1
    assert (
        main(
            [
                "workflow",
                "calls",
                "finish",
                str(data["id"]),
                "--outcome",
                "succeeded",
                *args,
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["workflow", "calls", "status", *args]) == 0
    assert json.loads(capsys.readouterr().out)["calls"][0]["status"] == "succeeded"
    assert main(["workflow", "calls", "reserve", "design", *args]) == 1
    assert "budget exhausted" in capsys.readouterr().err


def test_preflight_and_status_do_not_consume_calls(feature: Path) -> None:
    before = (feature / audit.AUDIT_FILE).read_bytes()
    for _ in range(3):
        orchestration.dispatch(feature)
        assert calls.status(feature, STAGE) == []
    assert (feature / audit.AUDIT_FILE).read_bytes() == before
    with pytest.raises(FlowError, match="not recorded"):
        calls.status(feature, "operate")


def test_invalid_result_and_reset_reason_do_not_mutate_audit(feature: Path) -> None:
    call_id = reserve(feature, "design")
    before = (feature / audit.AUDIT_FILE).read_bytes()
    with pytest.raises(FlowError, match="outcome"):
        finish(feature, call_id, "pass")
    with pytest.raises(FlowError, match="only agent:conductor"):
        calls.finish(feature, STAGE, call_id, "succeeded", "agent:design")
    assert (feature / audit.AUDIT_FILE).read_bytes() == before
    finish(feature, call_id)
    with pytest.raises(FlowError, match="secret"):
        calls.reset(feature, STAGE, "human:test", "password=not-allowed")
    assert not (feature / calls.LOCK_FILE).exists()
    assert len(calls.status(feature, STAGE)) == 1


def test_missing_workers_cannot_complete_managed_stage(feature: Path) -> None:
    finish(feature, reserve(feature, "design"))
    with pytest.raises(FlowError, match="without assigned worker results"):
        state.done_stage(feature, STAGE, ACTOR)
    calls.reset(feature, STAGE, "human:test", "Start over with a complete worker set")
    with pytest.raises(FlowError, match="without assigned worker results"):
        state.done_stage(feature, STAGE, ACTOR)


def test_concurrent_duplicate_reservations_fail_closed(feature: Path) -> None:
    def attempt() -> int | str:
        try:
            return reserve(feature, "design")
        except FlowError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(type(result) is int for result in results) == 1
    assert len(calls.status(feature, STAGE)) == 1
    assert audit.verify_chain(feature) is None


def test_budget_survives_separate_cli_processes(feature: Path) -> None:
    root = Path(__file__).resolve().parents[3]
    command = [
        sys.executable,
        "-m",
        "speckit_flow",
        "workflow",
        "calls",
        "reserve",
        "design",
        "--feature-dir",
        str(feature),
        "--stage",
        STAGE,
        "--actor",
        ACTOR,
        "--json",
    ]
    first = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
    assert first.returncode == 0, first.stderr
    second = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
    assert second.returncode == 1
    assert "duplicate dispatch" in second.stderr
    assert len(calls.status(feature, STAGE)) == 1
