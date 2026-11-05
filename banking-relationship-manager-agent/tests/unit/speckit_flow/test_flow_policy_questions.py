from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import questions, sensors, state
from speckit_flow.models import FlowError, Profile

H = "human:tester"
ROOT = Path(__file__).resolve().parents[3]


def _feature(tmp_path: Path) -> Path:
    d = tmp_path / "specs" / "016-demo"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# Spec\n- **FR-001**: thing\n", encoding="utf-8")
    return d


def test_question_round_trip_and_roles(tmp_path: Path) -> None:
    d = _feature(tmp_path)
    state.init_state(d, "feature", H)
    q = questions.add_question(d, "Which users?", "product", "agent:product", {"product"})
    assert q.id == "Q1" and q.status == "open"
    assert [x.id for x in questions.open_questions(d)] == ["Q1"]
    with pytest.raises(FlowError, match="unknown role"):
        questions.add_question(d, "x?", "wizard", "agent:product", {"product"})
    answered = questions.answer_question(d, "Q1", "Branch staff", H)
    assert answered.status == "answered"
    assert questions.open_questions(d) == []
    with pytest.raises(FlowError, match="already answered"):
        questions.answer_question(d, "Q1", "again", H)


def test_agent_cannot_answer(tmp_path: Path) -> None:
    d = _feature(tmp_path)
    state.init_state(d, "feature", H)
    questions.add_question(d, "Which users?", "product", "agent:product")
    with pytest.raises(FlowError, match="only a human"):
        questions.answer_question(d, "Q1", "me", "agent:product")


def test_hand_edited_answer_is_recognised(tmp_path: Path) -> None:
    d = _feature(tmp_path)
    state.init_state(d, "feature", H)
    questions.add_question(d, "Which users?", "product", "agent:product")
    path = d / questions.QUESTIONS_FILE
    path.write_text(path.read_text(encoding="utf-8").rstrip() + " Branch staff\n", encoding="utf-8")
    assert questions.open_questions(d) == []
    assert questions.load_questions(d)[0].answer == "Branch staff"


def test_questions_sensor_blocks_while_open(tmp_path: Path) -> None:
    d = _feature(tmp_path)
    state.init_state(d, "feature", H)
    questions.add_question(d, "Which users?", "product", "agent:product")
    sensor = sensors.Sensor("q", "builtin", ("plan",), True, builtin="questions")
    ok, detail = sensors.run_sensor(sensor, d, "plan")
    assert not ok and "Q1" in detail
    questions.answer_question(d, "Q1", "staff", H)
    assert sensors.run_sensor(sensor, d, "plan")[0]


def _profiles(tmp_path: Path, **extra: object) -> Path:
    pdir = tmp_path / ".specify" / "profiles"
    pdir.mkdir(parents=True)
    base = json.loads((ROOT / ".specify" / "profiles" / "feature.json").read_text())
    base.update(extra)
    (pdir / "feature.json").write_text(json.dumps(base))
    return pdir


def _at_gate(tmp_path: Path, pdir: Path) -> Path:
    d = _feature(tmp_path)
    state.init_state(d, "feature", H, pdir)
    state.start_stage(d, "specify", H)
    state.done_stage(d, "specify", H, pdir)
    return d


def test_profile_policy_fields_validate() -> None:
    base = json.loads((ROOT / ".specify" / "profiles" / "feature.json").read_text())
    assert Profile.from_dict(base).strict is False
    assert Profile.from_dict({**base, "guard_policy": "strict"}).strict is True
    assert Profile.from_dict({**base, "depth": "comprehensive"}).strict is True
    with pytest.raises(FlowError):
        Profile.from_dict({**base, "test_strategy": "bogus"})
    with pytest.raises(FlowError):
        Profile.from_dict({**base, "guard_policy": "bogus"})


def test_strict_guard_requires_review_and_closed_questions(tmp_path: Path) -> None:
    pdir = _profiles(tmp_path, guard_policy="strict")
    d = _at_gate(tmp_path, pdir)
    with pytest.raises(FlowError, match="strict guard policy"):
        state.decide_gate(d, "specify", True, H, profiles_dir=pdir)


def test_strict_guard_overrides_comprehensive_default(tmp_path: Path) -> None:
    pdir = _profiles(tmp_path, depth="comprehensive", guard_policy="standard")
    d = _at_gate(tmp_path, pdir)
    assert state.decide_gate(d, "specify", True, H, profiles_dir=pdir).pending_gate is None


def test_test_strategy_required_blocks_untested_requirement(tmp_path: Path) -> None:
    pdir = _profiles(
        tmp_path, test_strategy="required", stages=["specify", "tasks"], gates=["specify", "tasks"]
    )
    d = _feature(tmp_path)
    (d / "tasks.md").write_text("- [ ] T001 Build FR-001\n", encoding="utf-8")
    state.init_state(d, "feature", H, pdir)
    state.start_stage(d, "specify", H)
    state.done_stage(d, "specify", H, pdir)
    state.decide_gate(d, "specify", True, H, profiles_dir=pdir)
    state.start_stage(d, "tasks", H)
    state.done_stage(d, "tasks", H, pdir)
    with pytest.raises(FlowError, match="test strategy"):
        state.decide_gate(d, "tasks", True, H, profiles_dir=pdir)
    (d / "tasks.md").write_text("- [ ] T001 Build FR-001\n- [ ] T002 Test FR-001\n")
    assert state.decide_gate(d, "tasks", True, H, profiles_dir=pdir).pending_gate is None
