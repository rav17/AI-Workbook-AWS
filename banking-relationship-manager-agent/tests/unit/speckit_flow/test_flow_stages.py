from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from speckit_flow import audit, state
from speckit_flow.models import FlowError, Profile
from speckit_flow.profiles import DEFAULT_PROFILES_DIR, load_profiles

H = "human:tester"


def _p(stages: list[str], **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "t",
        "description": "d",
        "stages": stages,
        "depth": "standard",
        "gates": [],
    }
    base.update(over)
    return base


def test_full_lifecycle_valid_and_complete() -> None:
    profile = load_profiles(DEFAULT_PROFILES_DIR)["full-lifecycle"]
    assert profile.stages[0] == "ideation" and profile.stages[-1] == "operate"
    assert len(profile.stages) == 9


@pytest.mark.parametrize(
    "stages",
    [
        ["specify", "tasks", "deploy"],
        ["specify", "tasks", "implement", "operate"],
        ["ideation", "plan"],
        ["ideation"],
        ["specify", "ideation"],
    ],
)
def test_bad_extended_orders_rejected(stages: list[str]) -> None:
    with pytest.raises(FlowError):
        Profile.from_dict(_p(stages))


def test_ideation_before_specify_allowed() -> None:
    Profile.from_dict(_p(["ideation", "specify"]))


def test_full_lifecycle_runs_end_to_end(tmp_path: Path) -> None:
    d = tmp_path / "013-demo"
    d.mkdir()
    st = state.init_state(d, "full-lifecycle", H)
    assert st.current_stage == "ideation"
    for stage in st.stages:
        state.start_stage(d, stage, H)
        done = state.done_stage(d, stage, H)
        if done.pending_gate:
            state.decide_gate(d, stage, True, H)
    final = state.load_state(d)
    assert final.current_stage is None
    assert audit.verify_chain(d) is None


def test_omitted_optional_stages_not_recorded(tmp_path: Path) -> None:
    d = tmp_path / "014-demo"
    d.mkdir()
    st = state.init_state(d, "feature", H)
    assert not {"ideation", "deploy", "operate"} & set(st.stages)


def test_switch_to_full_lifecycle_adds_stages(tmp_path: Path) -> None:
    d = tmp_path / "015-demo"
    d.mkdir()
    state.init_state(d, "feature", H)
    st = state.switch_profile(d, "full-lifecycle", H, confirm=True)
    assert st.stages["deploy"].status == "pending"
    assert st.current_stage == "ideation"


def test_legacy_state_without_new_stages_still_loads(tmp_path: Path) -> None:
    d = tmp_path / "016-demo"
    d.mkdir()
    state.init_state(d, "feature", H)
    data = json.loads((d / "state.json").read_text())
    assert "ideation" not in data["stages"]
    assert state.load_state(d).current_stage == "specify"
