from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from speckit_flow import state as flow_state
from speckit_flow import units
from speckit_flow.cli import main
from speckit_flow.models import FlowError


def _feature(tmp_path: Path) -> tuple[Path, list[str]]:
    d = tmp_path / "specs" / "018-x"
    d.mkdir(parents=True)
    verify = tmp_path / "verify.json"
    base = ["--feature-dir", str(d), "--verify-file", str(verify)]
    return d, base


def _approve(base: list[str]) -> None:
    argv = [sys.executable, "-c", "pass"]
    assert main(["verify", "propose", *base, "--actor", "agent:developer", "--", *argv]) == 0
    assert main(["verify", "approve", *base, "--actor", "human:a"]) == 0


def test_unit_graph_rejects_cycles_and_unknown_deps(tmp_path: Path) -> None:
    d, _ = _feature(tmp_path)
    units.add_unit(d, "a", "A", [], ["T001"], "human:a")
    with pytest.raises(FlowError):
        units.add_unit(d, "b", "B", ["ghost"], [], "human:a")
    with pytest.raises(FlowError):
        units.add_unit(d, "a", "dup", [], [], "human:a")
    with pytest.raises(FlowError):
        units.add_unit(d, "c", "C", [], ["bad"], "human:a")
    assert [u["id"] for u in units.load_units(d)] == ["a"]


def test_agent_cannot_approve_verification_command(tmp_path: Path) -> None:
    _, base = _feature(tmp_path)
    assert main(["verify", "propose", "echo", "hi", *base, "--actor", "agent:developer"]) == 0
    assert main(["verify", "approve", *base, "--actor", "agent:developer"]) == 1
    assert main(["verify", "run", *base]) == 1


def test_changed_command_needs_reapproval(tmp_path: Path) -> None:
    _, base = _feature(tmp_path)
    _approve(base)
    assert main(["verify", "run", *base]) == 0
    assert main(["verify", "propose", *base, "--", sys.executable, "-c", "pass", "x"]) == 0
    assert main(["verify", "run", *base]) == 1


def test_checkpoint_requires_dependencies_and_passing_command(tmp_path: Path) -> None:
    d, base = _feature(tmp_path)
    assert main(["units", "add", "a", "First", "--tasks", "T001", *base]) == 0
    assert main(["units", "add", "b", "Second", "--depends-on", "a", *base]) == 0
    _approve(base)
    assert main(["units", "checkpoint", "b", *base]) == 1
    assert main(["units", "checkpoint", "a", *base]) == 0
    assert main(["units", "checkpoint", "b", *base]) == 0
    assert units.unchecked_units(d) == []


def test_failing_verification_does_not_checkpoint(tmp_path: Path) -> None:
    d, base = _feature(tmp_path)
    main(["units", "add", "a", "First", *base])
    argv = [sys.executable, "-c", "raise SystemExit(3)"]
    main(["verify", "propose", *base, "--", *argv])
    main(["verify", "approve", *base, "--actor", "human:a"])
    assert main(["units", "checkpoint", "a", *base]) == 1
    assert units.unchecked_units(d) == ["a"]


def test_implement_gate_blocks_until_units_checkpointed(tmp_path: Path) -> None:
    d, base = _feature(tmp_path)
    sensors = str(tmp_path / "none.json")
    assert main(["init", "--profile", "express", *base, "--sensors-file", sensors]) == 0
    main(["units", "add", "a", "First", *base])
    data = json.loads((d / flow_state.STATE_FILE).read_text("utf-8"))
    data["pending_gate"] = "implement"
    (d / flow_state.STATE_FILE).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FlowError, match="units not checkpointed"):
        flow_state.decide_gate(d, "implement", True, "human:a")
