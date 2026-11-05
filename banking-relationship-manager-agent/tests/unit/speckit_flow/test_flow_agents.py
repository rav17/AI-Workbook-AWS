from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from speckit_flow import agents as ag
from speckit_flow.cli import main
from speckit_flow.models import FlowError
from speckit_flow.profiles import load_profiles
from speckit_flow.state import decide_gate


@pytest.fixture(scope="module")
def roster() -> dict[str, ag.Agent]:
    return ag.load_roster()


def test_roster_counts_and_valid(roster: dict[str, ag.Agent]) -> None:
    counts: dict[str, int] = {}
    for a in roster.values():
        counts[a.role] = counts.get(a.role, 0) + 1
    assert counts == ag.EXPECTED_COUNTS
    assert ag.validate_roster(roster) == []


def test_every_profile_stage_has_lead(roster: dict[str, ag.Agent]) -> None:
    for profile in load_profiles().values():
        result = ag.resolve_assignments(profile, roster)
        assert set(result) == set(profile.stages)
        assert all(v["lead"] in roster for v in result.values())


def test_assignment_override_and_rejection(roster: dict[str, ag.Agent]) -> None:
    profile = next(iter(load_profiles().values()))
    stage = profile.stages[0]
    ok = dataclasses.replace(profile, assignments={stage: {"lead": "developer"}})
    assert ag.resolve_assignments(ok, roster)[stage]["lead"] == "developer"
    for bad in ({"lead": "ghost"}, {"lead": "product-lead"}):
        broken = dataclasses.replace(profile, assignments={stage: bad})
        with pytest.raises(FlowError):
            ag.resolve_assignments(broken, roster)


def test_check_actor(roster: dict[str, ag.Agent]) -> None:
    ag.check_actor("agent:conductor", roster)
    ag.check_actor("human:someone", roster)
    with pytest.raises(FlowError):
        ag.check_actor("agent:ghost", roster)


def test_agents_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["agents", "list"]) == 0
    assert main(["agents", "validate"]) == 0
    assert main(["agents", "assign", "--profile", "feature"]) == 0
    assert "roster valid" in capsys.readouterr().out


def test_cli_actor_and_gate_rules(tmp_path: Path) -> None:
    d = tmp_path / "012-x"
    d.mkdir()
    base = ["--feature-dir", str(d), "--sensors-file", str(tmp_path / "none.json")]
    assert main(["init", "--profile", "express", *base, "--actor", "human:a"]) == 0
    assert main(["stage", "start", "specify", *base, "--actor", "agent:conductor"]) == 0
    assert main(["stage", "done", "specify", *base, "--actor", "agent:ghost"]) == 1
    assert main(["stage", "done", "specify", *base, "--actor", "agent:developer"]) == 0
    assert main(["gate", "approve", "specify", *base, "--actor", "agent:developer"]) == 1
    with pytest.raises(FlowError):
        decide_gate(d, "specify", "approve", "agent:developer")
    assert main(["gate", "approve", "specify", *base, "--actor", "human:a"]) == 0
