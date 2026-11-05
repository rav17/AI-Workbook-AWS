from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import audit, state
from speckit_flow.models import FlowError

A = "human:tester"


@pytest.fixture
def fdir(tmp_path: Path) -> Path:
    d = tmp_path / "010-demo"
    d.mkdir()
    return d


def _types(d: Path) -> list[str]:
    return [e.type for e in audit.read_events(d)]


def test_init_bugfix_skips_omitted_stages(fdir: Path) -> None:
    st = state.init_state(fdir, "bugfix", A)
    assert st.stages["plan"].status == "skipped"
    assert st.stages["analyze"].status == "skipped"
    assert st.current_stage == "specify"
    assert _types(fdir).count("stage_skipped") == 3
    assert (fdir / "state.md").exists()


def test_init_unknown_profile_fails_without_writing(fdir: Path) -> None:
    with pytest.raises(FlowError, match="valid profiles"):
        state.init_state(fdir, "nope", A)
    assert not (fdir / "state.json").exists()
    assert not (fdir / "audit.jsonl").exists()


def test_init_twice_rejected(fdir: Path) -> None:
    state.init_state(fdir, "feature", A)
    with pytest.raises(FlowError, match="already initialized"):
        state.init_state(fdir, "feature", A)


def test_full_feature_flow_with_gates(fdir: Path) -> None:
    state.init_state(fdir, "feature", A)
    state.start_stage(fdir, "specify", A)
    st = state.done_stage(fdir, "specify", A)
    assert st.pending_gate == "specify"
    with pytest.raises(FlowError, match="gate"):
        state.start_stage(fdir, "plan", A)
    state.decide_gate(fdir, "specify", True, A)
    state.start_stage(fdir, "plan", A)
    state.done_stage(fdir, "plan", A)
    st = state.decide_gate(fdir, "plan", False, A, "needs more detail")
    assert st.stages["plan"].status == "pending"
    assert st.current_stage == "plan"
    types = _types(fdir)
    assert "gate_approved" in types and "gate_rejected" in types
    assert audit.verify_chain(fdir) is None


def test_ungated_stage_has_no_pending_gate(fdir: Path) -> None:
    state.init_state(fdir, "feature", A)
    for s in ("specify", "plan"):
        state.start_stage(fdir, s, A)
        state.done_stage(fdir, s, A)
        state.decide_gate(fdir, s, True, A)
    state.start_stage(fdir, "tasks", A)
    assert state.done_stage(fdir, "tasks", A).pending_gate is None


def test_out_of_order_and_unrouted_rejected(fdir: Path) -> None:
    state.init_state(fdir, "bugfix", A)
    with pytest.raises(FlowError, match="not in profile"):
        state.start_stage(fdir, "plan", A)
    with pytest.raises(FlowError, match="out of order"):
        state.start_stage(fdir, "tasks", A)
    assert "failure" in _types(fdir)


def test_done_requires_in_progress(fdir: Path) -> None:
    state.init_state(fdir, "bugfix", A)
    with pytest.raises(FlowError, match="not in progress"):
        state.done_stage(fdir, "specify", A)


def test_switch_rules(fdir: Path) -> None:
    state.init_state(fdir, "bugfix", A)
    with pytest.raises(FlowError, match="--confirm"):
        state.switch_profile(fdir, "enterprise", A, confirm=False)
    state.start_stage(fdir, "specify", A)
    with pytest.raises(FlowError, match="stage boundary"):
        state.switch_profile(fdir, "enterprise", A, confirm=True)
    state.done_stage(fdir, "specify", A)
    state.decide_gate(fdir, "specify", True, A)
    st = state.switch_profile(fdir, "enterprise", A, confirm=True)
    assert st.profile == "enterprise"
    assert st.stages["specify"].status == "done"
    assert st.stages["plan"].status == "pending"
    assert "profile_changed" in _types(fdir)


def test_revision_increments(fdir: Path) -> None:
    s1 = state.init_state(fdir, "poc", A)
    s2 = state.start_stage(fdir, "specify", A)
    assert s2.revision == s1.revision + 1


def test_audit_failure_leaves_state_unchanged(fdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    state.init_state(fdir, "bugfix", A)
    before = (fdir / "state.json").read_text("utf-8")

    def boom(*_a: object, **_k: object) -> None:
        raise FlowError("disk full")

    monkeypatch.setattr(audit, "append_event", boom)
    with pytest.raises(FlowError):
        state.start_stage(fdir, "specify", A)
    assert (fdir / "state.json").read_text("utf-8") == before


def test_features_are_isolated(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    state.init_state(a, "bugfix", A)
    state.init_state(b, "enterprise", A)
    assert state.load_state(a).profile == "bugfix"
    assert len(audit.read_events(b)) == 1


def test_corrupt_state_reported(fdir: Path) -> None:
    (fdir / "state.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(FlowError, match="corrupt"):
        state.load_state(fdir)
    (fdir / "state.json").write_text(json.dumps({"feature": "x"}), encoding="utf-8")
    with pytest.raises(FlowError, match="corrupt"):
        state.load_state(fdir)


def test_missing_state_then_rebuild(fdir: Path) -> None:
    state.init_state(fdir, "feature", A)
    (fdir / "spec.md").write_text("s", encoding="utf-8")
    (fdir / "plan.md").write_text("p", encoding="utf-8")
    (fdir / "state.json").unlink()
    with pytest.raises(FlowError, match="not found"):
        state.load_state(fdir)
    st = state.rebuild_state(fdir, A)
    assert st.profile == "feature"
    assert st.stages["specify"].status == "done"
    assert st.stages["plan"].status == "done"
    assert st.current_stage == "tasks"
    assert audit.verify_chain(fdir) is None
