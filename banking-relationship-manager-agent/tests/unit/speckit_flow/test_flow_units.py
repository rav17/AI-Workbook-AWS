from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

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


@pytest.mark.parametrize("include_evidence", [False, True])
def test_unit_inspection_reuses_validated_dependency_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, include_evidence: bool,
) -> None:
    feature, base = _feature(tmp_path)
    flow_state.init_state(feature, "express", "human:test")
    _approve(base)
    units.add_unit(feature, "first", "First", [], [], "agent:developer")
    units.add_unit(feature, "dependent", "Dependent", ["first"], [], "agent:developer")
    data = json.loads((feature / units.UNITS_FILE).read_text("utf-8"))
    data["units"].reverse()
    (feature / units.UNITS_FILE).write_text(json.dumps(data), encoding="utf-8")
    before = (feature / units.UNITS_FILE).read_bytes()
    original = units._validate
    observed: list[list[str]] = []

    def validate(items: list[dict[str, Any]]) -> list[str]:
        order = original(items)
        observed.append(order)
        return order

    monkeypatch.setattr(units, "_validate", validate)
    result = units.list_units(feature, Path(base[-1]), include_evidence=include_evidence)
    assert observed == [["first", "dependent"]]
    assert result["ready"] == ["first"]
    by_id = {unit["id"]: unit for unit in result["units"]}
    assert by_id["dependent"]["blocked_by"] == ["first"]
    assert by_id["dependent"]["status"] == "blocked"
    if include_evidence:
        assert result["dependency_order"] == ["first", "dependent"]
        assert by_id["dependent"]["checkpoint_evidence"]["reason_codes"] == [
            "dependencies_not_verified", "checkpoint_missing",
        ]
    else:
        assert set(result) == {"units", "ready", "notice"}
        assert "checkpoint_evidence" not in by_id["dependent"]
    units.list_units(feature, Path(base[-1]), include_evidence=include_evidence)
    assert len(observed) == 2
    assert before == (feature / units.UNITS_FILE).read_bytes()


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
    assert units.unchecked_units(d, Path(base[-1])) == []


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


def _tracked_graph(root: Path) -> tuple[Path, Path]:
    feature = root / "specs" / "035-test"
    feature.mkdir(parents=True)
    verify = root / ".specify" / "verify.json"
    verify.parent.mkdir()
    units.propose_verify([sys.executable, "-c", "pass"], "agent:test", verify)
    units.approve_verify("human:test", verify)
    for uid, deps in (("a", []), ("b", ["a"]), ("c", ["b"]), ("independent", [])):
        (root / f"{uid}.py").write_text(f"# {uid}\n", encoding="utf-8")
        units.add_unit(
            feature, uid, uid, deps, [], "agent:test", files=[f"{uid}.py"]
        )
    return feature, verify


def _statuses(feature: Path, verify: Path) -> dict[str, dict[str, Any]]:
    return {u["id"]: u for u in units.list_units(feature, verify)["units"]}


def _checkpoint_all(feature: Path, verify: Path) -> None:
    for uid in ("a", "b", "c", "independent"):
        assert units.checkpoint_unit(feature, uid, "agent:test", verify)[0]


def test_ready_reporting_is_read_only_and_never_executes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature, verify = _tracked_graph(tmp_path)
    before = (feature / "units.json").read_bytes()

    def forbidden(*args: object) -> None:
        pytest.fail("status reporting must not run verification")

    monkeypatch.setattr(units, "run_verify", forbidden)
    statuses = _statuses(feature, verify)
    assert statuses["a"]["status"] == "ready"
    assert statuses["a"]["coverage"] == "tracked-files"
    assert statuses["b"]["status"] == "blocked"
    assert statuses["b"]["blocked_by"] == ["a"]
    assert statuses["c"]["blocked_by"] == ["b"]
    assert statuses["independent"]["status"] == "ready"
    assert not statuses["a"]["checkpoint_present"]
    assert before == (feature / "units.json").read_bytes()


def test_stale_source_propagates_and_requires_dependent_recheck(tmp_path: Path) -> None:
    feature, verify = _tracked_graph(tmp_path)
    _checkpoint_all(feature, verify)
    (tmp_path / "a.py").write_text("changed\n", encoding="utf-8")
    statuses = _statuses(feature, verify)
    assert statuses["a"]["status"] == "stale"
    assert statuses["b"]["status"] == "stale"
    assert statuses["b"]["blocked_by"] == ["a"]
    assert statuses["c"]["status"] == "stale"
    assert statuses["independent"]["status"] == "verified"
    assert units.unchecked_units(feature, verify) == ["a", "b", "c"]
    assert units.checkpoint_unit(feature, "a", "agent:test", verify)[0]
    assert _statuses(feature, verify)["b"]["status"] == "stale"
    assert units.checkpoint_unit(feature, "b", "agent:test", verify)[0]
    assert _statuses(feature, verify)["c"]["status"] == "stale"
    assert units.checkpoint_unit(feature, "c", "agent:test", verify)[0]
    assert units.unchecked_units(feature, verify) == []


@pytest.mark.parametrize("change", ["definition", "missing-file", "unapproved", "command"])
def test_freshness_changes_have_reasons(tmp_path: Path, change: str) -> None:
    feature, verify = _tracked_graph(tmp_path)
    _checkpoint_all(feature, verify)
    if change == "definition":
        path = feature / "units.json"
        data = json.loads(path.read_text())
        data["units"][0]["title"] = "changed"
        path.write_text(json.dumps(data), encoding="utf-8")
    elif change == "missing-file":
        (tmp_path / "a.py").unlink()
    else:
        units.propose_verify([sys.executable, "-c", "print('new')"], "agent:test", verify)
        if change == "command":
            units.approve_verify("human:test", verify)
    item = _statuses(feature, verify)["a"]
    assert item["status"] == "stale"
    assert item["checkpoint_present"] and not item["checkpointed"]
    assert item["reasons"]


def test_dependency_must_be_fresh_before_command_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature, verify = _tracked_graph(tmp_path)
    units.checkpoint_unit(feature, "a", "agent:test", verify)
    (tmp_path / "a.py").write_text("changed", encoding="utf-8")

    def forbidden(*args: object) -> None:
        pytest.fail("must reject stale dependencies before executing")

    monkeypatch.setattr(units, "run_verify", forbidden)
    with pytest.raises(FlowError, match="dependencies.*a"):
        units.checkpoint_unit(feature, "b", "agent:test", verify)


def test_recheckpoint_revision_invalidates_dependents_even_in_same_second(tmp_path: Path) -> None:
    feature, verify = _tracked_graph(tmp_path)
    _checkpoint_all(feature, verify)
    old = units.checkpointed(feature)["a"]
    assert units.checkpoint_unit(feature, "a", "agent:test", verify)[0]
    assert units.checkpointed(feature)["a"]["revision"] != old["revision"]
    assert _statuses(feature, verify)["b"]["status"] == "stale"


def test_untracked_units_have_command_only_coverage_and_failed_rechecks_clear_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature, verify = _tracked_graph(tmp_path)
    units.add_unit(feature, "untracked", "Command only", [], [], "agent:test")
    assert units.checkpoint_unit(feature, "untracked", "agent:test", verify)[0]
    item = _statuses(feature, verify)["untracked"]
    assert item["status"] == "verified"
    assert item["coverage"] == "command-only"
    monkeypatch.setattr(units, "run_verify", lambda *args: (False, "failed", "digest"))
    assert not units.checkpoint_unit(feature, "untracked", "agent:test", verify)[0]
    assert "untracked" not in units.checkpointed(feature)


def test_legacy_checkpoint_is_stale_not_silently_upgraded(tmp_path: Path) -> None:
    feature, verify = _tracked_graph(tmp_path)
    path = feature / "units.json"
    data = json.loads(path.read_text())
    data["checkpoints"]["a"] = {"at": "old", "command": "old", "actor": "agent:test"}
    path.write_text(json.dumps(data), encoding="utf-8")
    item = _statuses(feature, verify)["a"]
    assert item["status"] == "stale"
    assert "legacy" in " ".join(item["reasons"])
    assert units.checkpoint_unit(feature, "a", "agent:test", verify)[0]
    assert _statuses(feature, verify)["a"]["status"] == "verified"


def test_dependency_changes_during_command_reject_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature, verify = _tracked_graph(tmp_path)
    units.checkpoint_unit(feature, "a", "agent:test", verify)
    command = units._digest(units.approved_command(verify))

    def mutate(*args: object) -> tuple[bool, str, str]:
        (tmp_path / "a.py").write_text("changed during command", encoding="utf-8")
        return True, "exit code 0", command

    monkeypatch.setattr(units, "run_verify", mutate)
    ok, reason = units.checkpoint_unit(feature, "b", "agent:test", verify)
    assert not ok and "changed" in reason
    assert "b" not in units.checkpointed(feature)


def test_implement_gate_rejects_stale_evidence(tmp_path: Path) -> None:
    feature, verify = _tracked_graph(tmp_path)
    flow_state.init_state(feature, "quick", "agent:test")
    _checkpoint_all(feature, verify)
    data = json.loads((feature / flow_state.STATE_FILE).read_text())
    data["pending_gate"] = "implement"
    (feature / flow_state.STATE_FILE).write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "a.py").write_text("changed", encoding="utf-8")
    with pytest.raises(FlowError, match="units.*(stale|checkpointed)"):
        flow_state.decide_gate(feature, "implement", True, "human:test")


def test_diamond_dependencies_refresh_in_order_without_blocking_independent_work(
    tmp_path: Path,
) -> None:
    feature, verify = _tracked_graph(tmp_path)
    units.add_unit(feature, "left", "Left", ["a"], [], "agent:test")
    units.add_unit(feature, "right", "Right", ["a"], [], "agent:test")
    units.add_unit(feature, "join", "Join", ["left", "right"], [], "agent:test")
    _checkpoint_all(feature, verify)
    for uid in ("left", "right", "join"):
        assert units.checkpoint_unit(feature, uid, "agent:test", verify)[0]
    units.checkpoint_unit(feature, "a", "agent:test", verify)
    item = _statuses(feature, verify)["join"]
    assert item["status"] == "stale"
    assert item["blocked_by"] == ["left", "right"]
    units.checkpoint_unit(feature, "left", "agent:test", verify)
    assert _statuses(feature, verify)["join"]["blocked_by"] == ["right"]
    units.checkpoint_unit(feature, "right", "agent:test", verify)
    assert units.checkpoint_unit(feature, "join", "agent:test", verify)[0]
    assert _statuses(feature, verify)["independent"]["checkpointed"]


@pytest.mark.parametrize("change", ["definition", "command", "dependency-revision"])
def test_mutations_during_command_reject_untracked_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    feature, verify = _tracked_graph(tmp_path)
    units.checkpoint_unit(feature, "a", "agent:test", verify)
    units.add_unit(feature, "plain", "Untracked", ["a"], [], "agent:test")
    command = units._digest(units.approved_command(verify))

    def mutate(*args: object) -> tuple[bool, str, str]:
        path = feature / "units.json"
        data = json.loads(path.read_text())
        if change == "definition":
            data["units"][-1]["title"] = "changed"
        elif change == "dependency-revision":
            data["checkpoints"]["a"]["revision"] += 1
        else:
            units.propose_verify([sys.executable, "-c", "print('new')"], "agent:test", verify)
            units.approve_verify("human:test", verify)
        path.write_text(json.dumps(data), encoding="utf-8")
        return True, "exit code 0", command

    monkeypatch.setattr(units, "run_verify", mutate)
    ok, reason = units.checkpoint_unit(feature, "plain", "agent:test", verify)
    assert not ok and "changed" in reason
    assert "plain" not in units.checkpointed(feature)


def test_untracked_policy_failure_removes_prior_pass(tmp_path: Path) -> None:
    feature, verify = _tracked_graph(tmp_path)
    units.add_unit(feature, "plain", "Untracked", [], [], "agent:test")
    units.checkpoint_unit(feature, "plain", "agent:test", verify)
    units.propose_verify([sys.executable, "-c", "print('new')"], "agent:test", verify)
    with pytest.raises(FlowError, match="not approved"):
        units.checkpoint_unit(feature, "plain", "agent:test", verify)
    assert "plain" not in units.checkpointed(feature)


def test_cli_custom_policy_json_and_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    feature, base = _feature(tmp_path)
    _approve(base)
    units.add_unit(feature, "plain", "Untracked", [], [], "agent:test")
    capsys.readouterr()
    assert main(["units", "list", *base, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ready"] == ["plain"]
    assert data["units"][0]["status"] == "ready"
    assert main(["units", "checkpoint", "plain", *base]) == 0
    capsys.readouterr()
    assert main(["units", "list", *base]) == 0
    text = capsys.readouterr().out
    assert "[verified]" in text and "coverage=command-only" in text
    assert "dispatch authorization" in text
    assert units.list_units(feature)["units"][0]["status"] == "stale"


@pytest.mark.parametrize(
    "bad",
    [
        {"units": [None]}, {"units": [{"id": []}]},
        {"units": [], "checkpoints": []},
        {"units": [], "checkpoints": {"a": None}},
        {"units": [{"id": "a", "title": "A", "depends_on": ["ghost"], "tasks": []}]},
        {"units": [{"id": "a", "title": "A", "depends_on": ["a"], "tasks": []}]},
        {"units": [{"id": "a", "title": "A", "depends_on": "b", "tasks": []}]},
    ],
)
def test_invalid_metadata_fails_explicitly(tmp_path: Path, bad: dict[str, Any]) -> None:
    feature, _ = _feature(tmp_path)
    (feature / "units.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(FlowError):
        units.list_units(feature)


def test_access_failure_is_reported_as_stale_not_a_silent_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature, verify = _tracked_graph(tmp_path)
    _checkpoint_all(feature, verify)

    def denied(*args: object) -> dict[str, str]:
        raise FlowError("cannot read tracked file path: PermissionError")

    monkeypatch.setattr(units, "tracked_fingerprints", denied)
    item = _statuses(feature, verify)["a"]
    assert item["status"] == "stale"
    assert "PermissionError" in " ".join(item["reasons"])


def test_reporting_empty_graph_needs_no_verification_policy(tmp_path: Path) -> None:
    feature, _ = _feature(tmp_path)
    assert units.list_units(feature)["units"] == []
    assert units.list_units(feature)["ready"] == []
