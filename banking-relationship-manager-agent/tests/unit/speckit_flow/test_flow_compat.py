from __future__ import annotations

from pathlib import Path

from speckit_flow import audit, state
from speckit_flow.profiles import DEFAULT_PROFILES_DIR, load_profiles

H = "human:tester"
LEGACY = ["specify", "clarify", "plan", "tasks", "analyze", "implement"]


def test_009_profiles_still_valid_and_unchanged_stage_sets() -> None:
    profiles = load_profiles(DEFAULT_PROFILES_DIR)
    for pid, profile in profiles.items():
        if pid != "full-lifecycle":
            assert set(profile.stages) <= set(LEGACY), pid


def test_009_style_audit_trail_verifies(tmp_path: Path) -> None:
    d = tmp_path / "017-demo"
    d.mkdir()
    state.init_state(d, "feature", H)
    state.start_stage(d, "specify", H)
    state.done_stage(d, "specify", H)
    state.decide_gate(d, "specify", True, H)
    assert audit.verify_chain(d) is None
    assert [e.type for e in audit.read_events(d)].count("gate_approved") == 1
