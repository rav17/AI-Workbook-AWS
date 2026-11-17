from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from speckit_flow import audit, calls, orchestration, plugins, recovery, session, units
from speckit_flow import state as flow_state
from speckit_flow.cli import main
from speckit_flow.models import FlowError

ROOT = Path(__file__).resolve().parents[3]
NONE = "none.json"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".specify").mkdir()
    for name in ("014-a", "015-b"):
        d = tmp_path / "specs" / name
        d.mkdir(parents=True)
        flow_state.init_state(d, "express", "human:t")
    return tmp_path


def cli(repo: Path, name: str, *args: str, actor: str = "human:t") -> int:
    d = repo / "specs" / name
    return main([*args, "--feature-dir", str(d), "--actor", actor, "--sensors-file", NONE])


def test_list_and_switch(repo: Path) -> None:
    (repo / "specs" / "099-empty").mkdir()
    assert [i.name for i in session.list_intents(repo)] == ["014-a", "015-b"]
    assert not any(i.active for i in session.list_intents(repo))
    session.switch_intent(repo, "015-b", "human:t")
    assert [i.name for i in session.list_intents(repo) if i.active] == ["015-b"]
    assert "intent_switched" in (repo / "specs" / "015-b" / "audit.jsonl").read_text("utf-8")
    for bad in ("099-empty", "../x", "nope"):
        with pytest.raises(FlowError):
            session.switch_intent(repo, bad, "human:t")
    assert [i.name for i in session.list_intents(repo) if i.active] == ["015-b"]


def test_park_blocks_stage_start_until_resumed(repo: Path) -> None:
    d = repo / "specs" / "014-a"
    session.park(d, "human:t", "waiting")
    assert audit.is_parked(d)
    assert session.list_intents(repo)[0].parked
    assert cli(repo, "014-a", "stage", "start", "specify") == 1
    with pytest.raises(FlowError):
        session.park(d, "human:t")
    session.unpark(d, "human:t")
    assert not audit.is_parked(d)
    assert cli(repo, "014-a", "stage", "start", "specify") == 0
    with pytest.raises(FlowError):
        session.unpark(d, "human:t")


def advance(repo: Path, name: str) -> Path:
    d = repo / "specs" / name
    assert cli(repo, name, "stage", "start", "specify") == 0
    assert cli(repo, name, "stage", "done", "specify") == 0
    return d


def test_redo_resets_later_stages_and_gate(repo: Path) -> None:
    d = advance(repo, "014-a")
    assert flow_state.load_state(d).pending_gate == "specify"
    st = session.redo_stage(d, "specify", "human:t", "scope changed")
    assert st.pending_gate is None
    assert st.current_stage == "specify"
    assert st.stages["specify"].status == "pending"
    assert "stage_redone" in (d / "audit.jsonl").read_text("utf-8")
    assert audit.verify_chain(d) is None


def test_redo_refusals(repo: Path) -> None:
    d = advance(repo, "014-a")
    with pytest.raises(FlowError):
        session.redo_stage(d, "specify", "agent:conductor", "x")
    with pytest.raises(FlowError):
        session.redo_stage(d, "specify", "human:t", "  ")
    with pytest.raises(FlowError):
        session.redo_stage(d, "tasks", "human:t", "forward")
    assert cli(repo, "014-a", "jump", "specify", "--reason", "back") == 0
    assert cli(repo, "014-a", "jump", "tasks", "--reason", "forward") == 1


def test_cli_intents(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("speckit_flow.cli._REPO_ROOT", repo)
    assert main(["intents", "list"]) == 0
    assert main(["intents", "switch", "014-a", "--actor", "human:t"]) == 0
    assert main(["intents", "park", "--reason", "pause", "--actor", "human:t"]) == 0
    assert main(["intents", "unpark", "--actor", "human:t"]) == 0
    assert main(["intents", "switch", "nope"]) == 1


def test_session_hook_script(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = importlib.util.spec_from_file_location("sess", ROOT / "scripts" / "speckit_session.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = repo
    assert mod.main() == 0
    assert capsys.readouterr().out == ""
    session.switch_intent(repo, "014-a", "human:t")
    assert mod.main() == 0
    assert "active=014-a" in capsys.readouterr().out
    (repo / ".specify" / "feature.json").write_text("{bad", encoding="utf-8")
    assert mod.main() == 0


def test_hook_config_valid() -> None:
    data = json.loads((ROOT / ".github" / "hooks" / "speckit-session.json").read_text("utf-8"))
    assert data["hooks"]["sessionStart"][0]["type"] == "command"


def test_recovery_checkpoint_freshness_preserves_unrelated_units(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "001-recovery"
    feature.mkdir(parents=True)
    policy = tmp_path / ".specify" / "verify.json"
    policy.parent.mkdir()
    flow_state.init_state(feature, "express", "human:test")
    units.propose_verify([sys.executable, "-c", "pass"], "agent:developer", policy)
    units.approve_verify("human:test", policy)
    for name in ("first", "independent"):
        (tmp_path / f"{name}.py").write_text("# Synthetic input\n", encoding="utf-8")
        units.add_unit(feature, name, name, [], [], "agent:developer", files=[f"{name}.py"])
        units.checkpoint_unit(feature, name, "agent:developer", policy)
    before = {path.name: path.read_bytes() for path in feature.iterdir() if path.is_file()}
    report = recovery.status(feature)
    assert set(report["verified_units"]) == {"first", "independent"}
    assert report["resume_allowed"]
    package = recovery.decision_package(report)
    assert set(package["scope"]["tracked_current_units"]) == {"first", "independent"}
    assert package["verification"]["resume_boundary"] == "not_selected"
    assert not package["decision"]["continuation_authorized"]
    assert before == {path.name: path.read_bytes() for path in feature.iterdir() if path.is_file()}
    (tmp_path / "first.py").write_text("# Changed input\n", encoding="utf-8")
    report = recovery.status(feature)
    assert report["status"] == "unknown"
    assert report["verified_units"] == ["independent"]
    assert report["uncertain_units"] == ["first"]
    assert not report["resume_allowed"]
    assert not report["ownership_transfer_allowed"]
    package = recovery.decision_package(report)
    assert package["scope"]["tracked_current_units"] == ["independent"]
    assert package["scope"]["uncertain_units"] == ["first"]


@pytest.mark.parametrize("outcome", ["running", "delayed", "unavailable", "unknown"])
def test_correlated_host_observation_never_authorizes_takeover(
    tmp_path: Path, outcome: str,
) -> None:
    feature = tmp_path / "specs" / "001-recovery"
    feature.mkdir(parents=True)
    flow_state.init_state(feature, "feature", "human:test")
    flow_state.start_stage(feature, "specify", "agent:conductor")
    call_id = calls.reserve(feature, "specify", "design", "agent:conductor")["id"]
    assert recovery.status(feature)["status"] == "unavailable"
    assert orchestration.next_action(feature)["action"] == "wait"
    report = recovery.status(
        feature, observation=recovery.WorkerObservation(call_id, outcome),
    )
    assert report["status"] == outcome
    assert not report["resume_allowed"]
    assert not report["ownership_transfer_allowed"]
    package = recovery.decision_package(report)
    assert package["evidence"]["worker_status"] == outcome
    assert package["evidence"]["worker_identity"] == "not_verified"
    assert not package["decision"]["continuation_authorized"]
    assert not package["decision"]["ownership_transfer_authorized"]
    with pytest.raises(FlowError, match="does not match"):
        recovery.status(feature, observation=recovery.WorkerObservation(call_id + 1, outcome))
    calls.finish(feature, "specify", call_id, "failed", "agent:conductor")
    assert orchestration.next_action(feature)["action"] == "recover"
    assert recovery.status(feature)["status"] == "unknown"


def test_next_and_recovery_cli_surface_blockers_without_advancing(
    repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    feature = repo / "specs" / "014-a"
    args = ["--feature-dir", str(feature), "--json"]
    assert main(["workflow", "next", *args]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "execute"
    session.park(feature, "human:t", "Synthetic pause")
    assert main(["workflow", "next", *args]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "parked"
    assert main(["workflow", "recovery", *args]) == 0
    assert not json.loads(capsys.readouterr().out)["resume_allowed"]
    (feature / audit.AUDIT_FILE).write_text("broken\n", encoding="utf-8")
    assert main(["workflow", "next", *args]) == 1
    assert json.loads(capsys.readouterr().out)["action"] == "blocked"
    assert main(["workflow", "recovery", *args]) == 1
    assert "invalid recovery audit" in capsys.readouterr().err
    assert main(["workflow", "recovery", "--approval-package", *args]) == 1
    failure = capsys.readouterr()
    assert failure.out == ""
    assert "invalid recovery audit" in failure.err


def test_next_gate_package_is_read_only_and_reports_missing_checks(
    repo: Path,
) -> None:
    feature = advance(repo, "014-a")
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    result = orchestration.next_action(feature)
    assert result["action"] == "await_human"
    assert result["approval_package"]["decision_recorded"] is False
    assert result["readiness"]["sensors"][0]["status"] == "not_run"
    assert result["readiness"]["artifacts"] == [{"path": "spec.md", "present": False}]
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    assert flow_state.load_state(feature).pending_gate == "specify"


@pytest.mark.parametrize(
    ("profile", "execution"),
    [("quick", "inline"), ("selective", "selected"), ("feature", "delegated")],
)
def test_consolidated_navigation_preserves_route_and_output_shape(
    tmp_path: Path, profile: str, execution: str,
) -> None:
    feature = tmp_path / "specs" / "001-navigation"
    feature.mkdir(parents=True)
    if profile == "selective":
        flow_state.init_state(
            feature, profile, "human:test", confirm_route=True, rationale="Synthetic route"
        )
    else:
        flow_state.init_state(feature, profile, "human:test")
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    result = orchestration.next_action(feature, sensors_file=Path(NONE))
    assert set(result) == {
        "action", "dispatch", "execution", "execution_choice", "gates", "next_action",
        "profile", "readiness", "reason", "route",
    }
    assert result["action"] == "execute" and result["execution_choice"] == execution
    assert result["profile"] == profile
    assert result["route"] == ["specify", "plan", "tasks", "implement"]
    assert result["gates"] == (["tasks"] if profile == "quick" else ["specify", "plan"])
    assert result["readiness"]["sensor_config"] == "not_configured"
    assert result["readiness"]["sensors"] == []
    assert result["dispatch"]["stage"] == "specify"
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


@pytest.mark.parametrize(
    ("outcome", "action"), [("running", "wait"), ("failed", "recover"), ("succeeded", "inspect")]
)
def test_next_action_reuses_one_call_observation_without_caching_between_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str, action: str,
) -> None:
    feature = _running_recovery_feature(tmp_path)
    call_id = calls.status(feature, "specify")[0]["id"]
    if outcome != "running":
        calls.finish(feature, "specify", call_id, outcome, "agent:conductor")
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    original = calls.status
    observations: list[list[dict[str, Any]]] = []

    def observe(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        observed = original(*args, **kwargs)
        observations.append(observed)
        return observed

    monkeypatch.setattr(calls, "status", observe)
    first = orchestration.next_action(feature)
    assert first["action"] == action
    assert len(observations) == 1
    assert first["readiness"]["worker_calls"] == observations[0]
    assert first["readiness"]["worker_calls"][0]["status"] == outcome
    second = orchestration.next_action(feature)
    assert first == second and len(observations) == 2
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


@dataclass
class SyntheticRecoveryAdapter:
    name: str = "synthetic"
    delay: float = 0
    identity_verified: bool = False
    call_delta: int = 0
    exclusion_verified: bool | None = None

    def observe(self, feature_dir: Path, call_id: int) -> recovery.HostObservation:
        time.sleep(self.delay)
        return recovery.HostObservation(
            call_id + self.call_delta, "running", "synthetic-worker",
            self.identity_verified,
            self.identity_verified if self.exclusion_verified is None else self.exclusion_verified,
        )


def _running_recovery_feature(tmp_path: Path) -> Path:
    feature = tmp_path / "specs" / "001-recovery"
    feature.mkdir(parents=True)
    flow_state.init_state(feature, "feature", "human:test")
    flow_state.start_stage(feature, "specify", "agent:conductor")
    calls.reserve(feature, "specify", "design", "agent:conductor")
    return feature


@pytest.mark.parametrize(
    ("identity_verified", "exclusion_verified"), [(False, False), (True, False), (True, True)]
)
def test_recovery_adapter_requires_identity_and_never_grants_transfer(
    tmp_path: Path, identity_verified: bool, exclusion_verified: bool,
) -> None:
    feature = _running_recovery_feature(tmp_path)
    report = recovery.status(
        feature, adapter=SyntheticRecoveryAdapter(
            identity_verified=identity_verified, exclusion_verified=exclusion_verified
        )
    )
    assert report["status"] == ("running" if identity_verified else "unknown")
    assert report["worker_identity"] == (
        "synthetic-worker" if identity_verified else "not_verified"
    )
    assert not report["resume_allowed"]
    assert not report["ownership_transfer_allowed"]
    package = recovery.decision_package(report)
    assert package["evidence"]["worker_identity"] == (
        "adapter_reported" if identity_verified else "not_verified"
    )
    assert package["evidence"]["exclusion"] == (
        "adapter_reported" if exclusion_verified else "not_verified"
    )
    assert package["provenance"]["human_authorization"] == "not_recorded"
    assert not package["decision"]["ownership_transfer_authorized"]
    assert "synthetic-worker" not in json.dumps(package)
    with pytest.raises(FlowError, match="does not match"):
        recovery.status(feature, adapter=SyntheticRecoveryAdapter(call_delta=1))


def test_recovery_watchdog_bounds_slow_adapter_and_preserves_task_worker(
    tmp_path: Path,
) -> None:
    feature = _running_recovery_feature(tmp_path)
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    started = time.monotonic()
    report = recovery.bounded_status(
        feature, 0.5, adapter=SyntheticRecoveryAdapter(delay=30), include_evidence=True,
    )
    elapsed = time.monotonic() - started
    assert elapsed < 2.5, f"watchdog exceeded deadline plus cleanup allowance: {elapsed:g}s"
    assert report["timed_out"] and report["status"] == "unknown"
    assert report["progress_evidence"] == "not_observed"
    assert not report["resume_allowed"] and not report["ownership_transfer_allowed"]
    package = recovery.decision_package(report)
    assert package["evidence"]["inspection"] == "timed_out"
    assert package["evidence"]["checkpoint_coverage"] == "not_observed"
    assert package["evidence"]["audit_integrity"] == "not_verified"
    assert not package["decision"]["continuation_authorized"]
    assert "coverage not_observed" in recovery.decision_package_text(package)
    assert package["checkpoint_inventory"]["total"] is None
    assert package["revalidation_plan"]["status"] == "blocked"
    assert package["revalidation_plan"]["steps"] == []
    assert package["evidence_snapshot"]["fingerprint"] is None
    assert recovery.decision_package(report, "0" * 64)["evidence_snapshot"]["comparison"] == (
        "not_verified"
    )
    assert calls.status(feature, "specify")[0]["status"] == "running"
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


def test_recovery_watchdog_native_cli_returns_complete_read_only_report(repo: Path) -> None:
    feature = repo / "specs" / "014-a"
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    result = subprocess.run(
        [
            sys.executable, "-B", "-m", "speckit_flow", "workflow", "recovery",
            "--timeout-seconds", "15", "--feature-dir", str(feature), "--json",
            "--approval-package",
        ],
        # CLI startup is outside the inspector's unchanged 15-second deadline.
        cwd=ROOT, capture_output=True, text=True, timeout=45, check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert not report["timed_out"]
    assert report["stage"] == "specify"
    assert not report["ownership_transfer_allowed"]
    assert report["approval_package"]["evidence"]["inspection"] == "complete"
    assert report["approval_package"]["checkpoint_inventory"]["total"] == 0
    assert report["approval_package"]["revalidation_plan"]["steps"] == []
    assert not report["approval_package"]["revalidation_plan"]["executable"]
    assert len(report["approval_package"]["revalidation_plan"]["blockers"]) == 3
    assert report["approval_package"]["evidence_snapshot"]["status"] == "stable_at_read_boundaries"
    assert not report["approval_package"]["decision"]["recorded"]
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


def test_recovery_package_concurrent_inspection_and_duplicate_dispatch_are_read_only(
    tmp_path: Path,
) -> None:
    feature = _running_recovery_feature(tmp_path)
    (feature / "synthetic-host-hints.json").write_text(
        json.dumps({"heartbeat_expired": True, "listed": False}), encoding="utf-8"
    )
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}

    def inspect() -> dict[str, Any]:
        return recovery.decision_package(recovery.status(feature))

    with ThreadPoolExecutor(max_workers=2) as executor:
        reports = list(executor.map(lambda _: inspect(), range(2)))
    assert reports[0] == reports[1]
    assert reports[0]["evidence"]["worker_status"] == "unavailable"
    assert not reports[0]["decision"]["ownership_transfer_authorized"]
    assert not reports[0]["decision"]["continuation_authorized"]
    with pytest.raises(FlowError, match="duplicate dispatch"):
        calls.reserve(feature, "specify", "design", "agent:conductor")
    assert len(calls.status(feature, "specify")) == 1
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


@pytest.mark.parametrize("change", ["incomplete", "definition", "command", "dependency"])
def test_recovery_package_excludes_invalidated_declared_progress(
    tmp_path: Path, change: str,
) -> None:
    feature = tmp_path / "specs" / "001-recovery"
    feature.mkdir(parents=True)
    policy = tmp_path / ".specify" / "verify.json"
    policy.parent.mkdir()
    flow_state.init_state(feature, "express", "human:test")
    units.propose_verify([sys.executable, "-c", "pass"], "agent:developer", policy)
    units.approve_verify("human:test", policy)
    for name, dependencies in (("first", []), ("dependent", ["first"])):
        (tmp_path / f"{name}.py").write_text("# Synthetic declared input\n", encoding="utf-8")
        units.add_unit(
            feature, name, name, dependencies, [], "agent:developer", files=[f"{name}.py"]
        )
        assert units.checkpoint_unit(feature, name, "agent:developer", policy)[0]
    data = json.loads((feature / units.UNITS_FILE).read_text("utf-8"))
    if change == "incomplete":
        del data["checkpoints"]["first"]["files"]
    elif change == "definition":
        data["units"][0]["title"] = "Changed synthetic completion scope"
    elif change == "dependency":
        data["checkpoints"]["first"]["revision"] += 1
    else:
        units.propose_verify(
            [sys.executable, "-c", "print('synthetic')"], "agent:developer", policy
        )
        units.approve_verify("human:test", policy)
    (feature / units.UNITS_FILE).write_text(json.dumps(data), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    package = recovery.decision_package(recovery.status(feature, include_evidence=True))
    assert "dependent" in package["scope"]["uncertain_units"]
    assert "dependent" not in package["scope"]["tracked_current_units"]
    assert package["verification"]["semantic_completion"] == "not_verified"
    assert package["verification"]["resume_boundary"] == "not_selected"
    entries = {unit["id"]: unit for unit in package["checkpoint_inventory"]["units"]}
    assert entries["dependent"]["status"] == "stale"
    expected_reason = {
        "incomplete": "checkpoint_metadata_incomplete",
        "definition": "unit_definition_changed",
        "command": "verification_command_changed",
        "dependency": "verification_record_unverified",
    }[change]
    assert expected_reason in entries["first"]["reason_codes"]
    steps = {step["unit"]: step for step in package["revalidation_plan"]["steps"]}
    expected_action = {
        "incomplete": "review_incomplete_checkpoint",
        "definition": "review_unit_definition",
        "command": "review_verification_change",
        "dependency": "review_verification_record",
    }[change]
    assert expected_action in {action["code"] for action in steps["first"]["actions"]}
    assert steps["dependent"]["prerequisite_units"] == ["first"]
    assert entries["dependent"]["recorded_verification"] == "recorded_pass"
    assert not package["decision"]["continuation_authorized"]
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


def test_recovery_package_omits_payloads_and_preserves_governance_and_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = tmp_path / "specs" / "001-recovery"
    feature.mkdir(parents=True)
    flow_state.init_state(feature, "express", "human:test")
    policy = tmp_path / ".specify" / "verify.json"
    policy.parent.mkdir()
    marker = "SYNTHETIC_UNEXPORTED_PAYLOAD"
    units.propose_verify([sys.executable, "-c", f"print('{marker}')"], "agent:developer", policy)
    units.approve_verify("human:test", policy)
    (tmp_path / "first.py").write_text("# Synthetic input\n", encoding="utf-8")
    units.add_unit(feature, "first", marker, [], [], "agent:developer", files=["first.py"])
    assert units.checkpoint_unit(feature, "first", "agent:developer", policy)[0]
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text(marker, encoding="utf-8")
    plugin = tmp_path / ".specify" / "plugins" / "synthetic"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(
        json.dumps({"name": "synthetic", "version": "1", "enabled": False}), encoding="utf-8"
    )
    (tmp_path / "synthetic-side-effect.once").write_text(marker, encoding="utf-8")
    before = {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("recovery review must not execute commands or write audit events")

    monkeypatch.setattr(units, "run_verify", forbidden)
    monkeypatch.setattr(audit, "append_event", forbidden)
    package = recovery.decision_package(recovery.status(feature, include_evidence=True))
    text = recovery.decision_package_text(package)
    assert marker not in json.dumps(package) + text
    assert str(tmp_path) not in json.dumps(package) + text
    assert package["scope"]["tracked_current_units"] == ["first"]
    assert package["verification"]["external_side_effects"] == "not_verified"
    assert package["verification"]["keyboard_screen_reader"] == "not_verified"
    assert package["verification"]["checks_run_now"] is False
    assert package["checkpoint_inventory"]["units"][0]["recorded_verification"] == "recorded_pass"
    assert plugins.discover(policy.parent) == []
    assert before == {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("in_progress", [False, True])
def test_recovery_package_cli_preserves_default_shape_and_blocked_exit_status(
    repo: Path, capsys: pytest.CaptureFixture[str], in_progress: bool,
) -> None:
    feature = repo / "specs" / "014-a"
    if in_progress:
        flow_state.start_stage(feature, "specify", "human:t")
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    args = ["workflow", "recovery", "--feature-dir", str(feature)]
    expected_exit = 1 if in_progress else 0
    assert main([*args, "--json"]) == expected_exit
    default = json.loads(capsys.readouterr().out)
    assert "approval_package" not in default
    assert main([*args, "--approval-package", "--json"]) == expected_exit
    expanded = json.loads(capsys.readouterr().out)
    package = expanded.pop("approval_package")
    assert default == expanded
    assert package["evidence"]["worker_status"] == ("unknown" if in_progress else "delayed")
    assert not package["decision"]["recorded"]
    assert main([*args, "--approval-package"]) == expected_exit
    text = capsys.readouterr().out
    for heading in (
        "Decision:", "Scope:", "Evidence:", "Verification:", "Authorization provenance:",
        "Unresolved risks:", "Allows:", "Excludes:", "Next action:",
    ):
        assert heading in text
    assert "keyboard/screen-reader acceptance: not_verified" in text
    assert not package["decision"]["continuation_authorized"]
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


def _checkpoint_evidence_feature(tmp_path: Path) -> Path:
    feature = tmp_path / "specs" / "001-evidence"
    feature.mkdir(parents=True)
    flow_state.init_state(feature, "express", "human:test")
    policy = tmp_path / ".specify" / "verify.json"
    policy.parent.mkdir()
    units.propose_verify([sys.executable, "-c", "pass"], "agent:developer", policy)
    units.approve_verify("human:test", policy)
    (tmp_path / "first.py").write_text("# Synthetic input\n", encoding="utf-8")
    units.add_unit(
        feature, "first", "Synthetic first", [], [], "agent:developer", files=["first.py"]
    )
    assert units.checkpoint_unit(feature, "first", "agent:developer", policy)[0]
    return feature


def test_checkpoint_inventory_is_complete_and_separates_freshness_from_recorded_verification(
    tmp_path: Path,
) -> None:
    feature = _checkpoint_evidence_feature(tmp_path)
    policy = tmp_path / ".specify" / "verify.json"
    for uid in ("stale", "command-only", "unverified", "missing", "blocked"):
        files = [] if uid == "command-only" else [f"{uid}.py"]
        for name in files:
            (tmp_path / name).write_text("# Synthetic input\n", encoding="utf-8")
        units.add_unit(
            feature, uid, uid, ["stale"] if uid == "blocked" else [], [],
            "agent:developer", files=files,
        )
        if uid not in ("missing", "blocked"):
            assert units.checkpoint_unit(feature, uid, "agent:developer", policy)[0]
    (tmp_path / "stale.py").write_text("# Changed synthetic input\n", encoding="utf-8")
    data = json.loads((feature / units.UNITS_FILE).read_text("utf-8"))
    data["checkpoints"]["unverified"]["revision"] += 1
    (feature / units.UNITS_FILE).write_text(json.dumps(data), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}
    default = recovery.status(feature)
    assert "checkpoint_inventory" not in default and "evidence_snapshot" not in default
    report = recovery.status(feature, include_evidence=True)
    package = recovery.decision_package(report)
    inventory = package["checkpoint_inventory"]
    assert inventory["status"] == "observed" and inventory["total"] == 6
    assert inventory["counts"] == {
        "current": 1, "stale": 1, "missing": 1, "blocked": 1, "command_only": 1, "unverified": 1,
    }
    entries = {unit["id"]: unit for unit in inventory["units"]}
    assert entries["unverified"]["freshness"] == "current"
    assert entries["unverified"]["recorded_verification"] == "recorded_pass"
    assert not entries["unverified"]["checkpoint_record_matches"]
    assert entries["stale"]["changed_files"] == ["stale.py"]
    assert "tracked_inputs_changed" in entries["stale"]["reason_codes"]
    assert "dependencies_not_verified" in entries["blocked"]["reason_codes"]
    assert package["scope"]["tracked_current_units"] == ["first"]
    assert len(package["scope"]["uncertain_units"]) == 5
    assert all(unit["semantic_completion"] == "not_verified" for unit in entries.values())
    assert not package["decision"]["continuation_authorized"]
    assert "changed declared files: stale.py" in recovery.decision_package_text(package)
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


def test_checkpoint_inventory_reports_failed_verification_without_inventing_a_checkpoint(
    tmp_path: Path,
) -> None:
    feature = _checkpoint_evidence_feature(tmp_path)
    policy = tmp_path / ".specify" / "verify.json"
    units.propose_verify(
        [sys.executable, "-c", "raise SystemExit(1)"], "agent:developer", policy
    )
    units.approve_verify("human:test", policy)
    assert not units.checkpoint_unit(feature, "first", "agent:developer", policy)[0]
    package = recovery.decision_package(recovery.status(feature, include_evidence=True))
    entry = package["checkpoint_inventory"]["units"][0]
    assert entry["status"] == "missing" and not entry["checkpoint_present"]
    assert entry["recorded_verification"] == "recorded_failure"
    assert "verification_recorded_failure" in entry["reason_codes"]
    assert entry["checkpoint_revision"] is None and entry["verification_revision"] > 0
    assert not entry["checkpoint_record_matches"]
    actions = package["revalidation_plan"]["steps"][0]["actions"]
    assert {"review_failed_verification", "review_missing_checkpoint"} <= {
        action["code"] for action in actions
    }
    assert package["scope"]["tracked_current_units"] == []
    assert package["verification"]["checks_run_now"] is False


def test_recovery_snapshot_comparison_ignores_unrelated_files_but_detects_declared_changes(
    tmp_path: Path,
) -> None:
    feature = _checkpoint_evidence_feature(tmp_path)
    original = recovery.decision_package(recovery.status(feature, include_evidence=True))
    fingerprint = original["evidence_snapshot"]["fingerprint"]
    assert len(fingerprint) == 64
    (tmp_path / "unrelated.txt").write_text("Synthetic unrelated edit\n", encoding="utf-8")
    unchanged = recovery.decision_package(
        recovery.status(feature, include_evidence=True), fingerprint
    )
    assert unchanged["evidence_snapshot"]["comparison"] == "unchanged"
    (tmp_path / "first.py").write_text("# Changed declared input\n", encoding="utf-8")
    changed = recovery.decision_package(
        recovery.status(feature, include_evidence=True), fingerprint
    )
    assert changed["evidence_snapshot"]["comparison"] == "changed"
    assert changed["scope"]["tracked_current_units"] == []
    assert changed["checkpoint_inventory"]["units"][0]["changed_files"] == ["first.py"]
    assert changed["revalidation_plan"]["status"] == "blocked"
    assert changed["revalidation_plan"]["steps"] == []
    assert not changed["decision"]["continuation_authorized"]


def test_recovery_snapshot_detects_midinspection_changes_without_emitting_a_usable_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = _checkpoint_evidence_feature(tmp_path)
    original = units.list_units

    def change_during_inspection(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = original(*args, **kwargs)
        (tmp_path / "first.py").write_text("# Concurrent synthetic edit\n", encoding="utf-8")
        return result

    monkeypatch.setattr(units, "list_units", change_during_inspection)
    package = recovery.decision_package(
        recovery.status(feature, include_evidence=True), "0" * 64
    )
    assert package["evidence_snapshot"]["status"] == "changed_during_inspection"
    assert package["evidence_snapshot"]["fingerprint"] is None
    assert package["evidence_snapshot"]["comparison"] == "not_verified"
    assert package["checkpoint_inventory"]["status"] == "not_verified"
    assert package["scope"]["tracked_current_units"] == []
    assert package["revalidation_plan"]["steps"] == []
    assert not package["decision"]["continuation_authorized"]


def test_revalidation_plan_orders_dependencies_and_preserves_independent_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = _checkpoint_evidence_feature(tmp_path)
    policy = tmp_path / ".specify" / "verify.json"
    for uid, dependencies in (
        ("child", ["first"]), ("grandchild", ["child"]), ("command-only", []),
    ):
        files = [] if uid == "command-only" else [f"{uid}.py"]
        for name in files:
            (tmp_path / name).write_text("# Synthetic dependent input\n", encoding="utf-8")
        units.add_unit(feature, uid, uid, dependencies, [], "agent:developer", files=files)
        assert units.checkpoint_unit(feature, uid, "agent:developer", policy)[0]
    (tmp_path / "independent.py").write_text("# Independent input\n", encoding="utf-8")
    units.add_unit(
        feature, "independent", "Independent", [], [], "agent:developer",
        files=["independent.py"],
    )
    assert units.checkpoint_unit(feature, "independent", "agent:developer", policy)[0]
    # Declaration order must not become the review dependency order.
    data = json.loads((feature / units.UNITS_FILE).read_text("utf-8"))
    data["units"].reverse()
    (feature / units.UNITS_FILE).write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "first.py").write_text("# Changed input\n", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("advisory planning must not execute or alter workflow records")

    monkeypatch.setattr(units, "run_verify", forbidden)
    monkeypatch.setattr(audit, "append_event", forbidden)
    package = recovery.decision_package(recovery.status(feature, include_evidence=True))
    plan = package["revalidation_plan"]
    assert plan["status"] == "advisory" and not plan["executable"]
    assert plan["preserve_units"] == ["independent"]
    steps = {step["unit"]: step for step in plan["steps"]}
    order = [step["unit"] for step in plan["steps"]]
    assert order.index("first") < order.index("child") < order.index("grandchild")
    assert steps["child"]["prerequisite_units"] == ["first"]
    assert steps["grandchild"]["prerequisite_units"] == ["child"]
    assert steps["first"]["changed_files"] == ["first.py"]
    assert "review_changed_inputs" in {action["code"] for action in steps["first"]["actions"]}
    assert "review_source_coverage" in {
        action["code"] for action in steps["command-only"]["actions"]
    }
    assert {item["code"] for item in plan["blockers"]} == {
        "host_execution_not_authorized", "external_side_effects_not_verified",
        "normal_preflight_required",
    }
    text = recovery.decision_package_text(package)
    assert "Revalidation plan: advisory; executable False" in text
    assert "Preserve current units: independent" in text
    assert before == {p.name: p.read_bytes() for p in feature.iterdir() if p.is_file()}


def test_revalidation_plan_distinguishes_missing_policy_and_blocked_dependencies(
    tmp_path: Path,
) -> None:
    feature = _checkpoint_evidence_feature(tmp_path)
    policy = tmp_path / ".specify" / "verify.json"
    (tmp_path / "missing.py").write_text("# Synthetic input\n", encoding="utf-8")
    units.add_unit(
        feature, "missing", "Missing", ["first"], [], "agent:developer", files=["missing.py"],
    )
    units.propose_verify([sys.executable, "-c", "pass"], "agent:developer", policy)
    package = recovery.decision_package(recovery.status(feature, include_evidence=True))
    steps = package["revalidation_plan"]["steps"]
    assert [step["unit"] for step in steps] == ["first", "missing"]
    assert steps[1]["prerequisite_units"] == ["first"]
    for step in steps:
        assert "review_verification_policy" in {action["code"] for action in step["actions"]}
    assert "review_missing_checkpoint" in {action["code"] for action in steps[1]["actions"]}
    assert package["revalidation_plan"]["preserve_units"] == []
    assert not package["decision"]["continuation_authorized"]


def test_recovery_snapshot_cli_compares_only_requested_evidence_packages(
    repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    feature = repo / "specs" / "014-a"
    args = ["workflow", "recovery", "--feature-dir", str(feature), "--json"]
    assert main([*args, "--approval-package"]) == 0
    first = json.loads(capsys.readouterr().out)["approval_package"]
    fingerprint = first["evidence_snapshot"]["fingerprint"]
    assert main([*args, "--approval-package", "--expected-fingerprint", fingerprint]) == 0
    comparison = json.loads(capsys.readouterr().out)["approval_package"]
    assert comparison["evidence_snapshot"]["comparison"] == "unchanged"
    assert main([*args, "--approval-package", "--expected-fingerprint", "0" * 64]) == 1
    mismatch = json.loads(capsys.readouterr().out)["approval_package"]
    assert mismatch["evidence_snapshot"]["comparison"] == "changed"
    assert not mismatch["decision"]["continuation_authorized"]
    assert main([*args, "--expected-fingerprint", fingerprint]) == 1
    assert "requires --approval-package" in capsys.readouterr().err
    assert main([*args, "--approval-package", "--expected-fingerprint", "invalid"]) == 1
    failure = capsys.readouterr()
    assert failure.out == "" and "lowercase SHA-256" in failure.err


def test_recovery_snapshot_rejects_oversized_metadata_as_unbound_evidence(tmp_path: Path) -> None:
    feature = _checkpoint_evidence_feature(tmp_path)
    data = json.loads((feature / units.UNITS_FILE).read_text("utf-8"))
    data["units"][0]["title"] = "S" * (units.MAX_TRACKED_BYTES + 1)
    (feature / units.UNITS_FILE).write_text(json.dumps(data), encoding="utf-8")
    assert (feature / units.UNITS_FILE).stat().st_size > units.MAX_TRACKED_BYTES
    package = recovery.decision_package(
        recovery.status(feature, include_evidence=True), "0" * 64
    )
    assert package["evidence_snapshot"]["status"] == "unavailable"
    assert package["revalidation_plan"]["status"] == "blocked"
    assert package["revalidation_plan"]["steps"] == []
    assert package["evidence_snapshot"]["fingerprint"] is None
    assert package["evidence_snapshot"]["comparison"] == "not_verified"
    assert package["checkpoint_inventory"]["status"] == "not_verified"
    assert package["scope"]["tracked_current_units"] == []
    assert not package["decision"]["continuation_authorized"]
