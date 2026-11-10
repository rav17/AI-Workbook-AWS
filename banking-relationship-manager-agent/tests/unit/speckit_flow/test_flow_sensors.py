from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import audit, sensors, state
from speckit_flow.cli import main
from speckit_flow.models import FlowError
from speckit_flow.state import decide_gate

CONFIG = {
    "sensors": [
        {
            "id": "consistency",
            "kind": "builtin",
            "builtin": "consistency",
            "stages": ["specify"],
            "required": True,
        },
        {
            "id": "ok-cmd",
            "kind": "command",
            "argv": ["python", "-c", "raise SystemExit(0)"],
            "stages": ["implement"],
            "required": True,
        },
        {
            "id": "bad-cmd",
            "kind": "command",
            "argv": ["python", "-c", "raise SystemExit(3)"],
            "stages": ["implement"],
            "required": False,
        },
    ]
}


@pytest.fixture
def feature(tmp_path: Path) -> tuple[Path, Path]:
    feature_dir = tmp_path / "specs" / "013-x"
    feature_dir.mkdir(parents=True)
    cfg = tmp_path / "sensors.json"
    cfg.write_text(json.dumps(CONFIG), encoding="utf-8")
    base = ["--feature-dir", str(feature_dir), "--sensors-file", str(cfg), "--actor"]
    assert main(["init", "--profile", "express", *base, "human:a"]) == 0
    assert main(["stage", "start", "specify", *base, "human:a"]) == 0
    (feature_dir / "spec.md").write_text("# Spec\nFR-001 thing\n", encoding="utf-8")
    assert main(["stage", "done", "specify", *base, "human:a"]) == 0
    return feature_dir, cfg


def approve(feature_dir: Path, cfg: Path) -> int:
    return main(
        [
            "gate",
            "approve",
            "specify",
            "--feature-dir",
            str(feature_dir),
            "--sensors-file",
            str(cfg),
            "--actor",
            "human:a",
        ]
    )


def run(feature_dir: Path, cfg: Path, stage: str = "specify") -> int:
    return main(
        [
            "sensors",
            "run",
            stage,
            "--feature-dir",
            str(feature_dir),
            "--sensors-file",
            str(cfg),
            "--actor",
            "agent:quality",
        ]
    )


def test_gate_refused_without_result_then_approved(feature: tuple[Path, Path]) -> None:
    feature_dir, cfg = feature
    assert approve(feature_dir, cfg) == 1
    assert run(feature_dir, cfg) == 0
    assert approve(feature_dir, cfg) == 0
    audit_text = (feature_dir / "audit.jsonl").read_text(encoding="utf-8")
    assert "sensor_run" in audit_text
    assert "sensors=consistency" in audit_text


def test_stale_result_refused(feature: tuple[Path, Path]) -> None:
    feature_dir, cfg = feature
    assert run(feature_dir, cfg) == 0
    (feature_dir / "spec.md").write_text("# Spec\nFR-001 changed\n", encoding="utf-8")
    assert approve(feature_dir, cfg) == 1


def test_failing_sensor_refused(feature: tuple[Path, Path]) -> None:
    feature_dir, cfg = feature
    (feature_dir / "spec.md").write_text("NEEDS CLARIFICATION", encoding="utf-8")
    assert run(feature_dir, cfg) == 1
    assert approve(feature_dir, cfg) == 1


def test_command_sensors(feature: tuple[Path, Path]) -> None:
    feature_dir, cfg = feature
    assert run(feature_dir, cfg, "implement") == 1
    results = json.loads((feature_dir / "sensors" / "implement.json").read_text("utf-8"))["results"]
    assert results["ok-cmd"]["status"] == "pass"
    assert results["bad-cmd"]["status"] == "fail"
    assert "stdout" not in results["bad-cmd"]


def test_no_config_unchanged(feature: tuple[Path, Path], tmp_path: Path) -> None:
    feature_dir, _ = feature
    assert approve(feature_dir, tmp_path / "missing.json") == 0


def test_invalid_config(tmp_path: Path) -> None:
    bad = tmp_path / "s.json"
    for payload in (
        {"sensors": [{"id": "A", "kind": "builtin"}]},
        {"sensors": [{"id": "x", "kind": "command", "argv": [], "stages": ["plan"]}]},
        {"sensors": [{"id": "x", "kind": "weird", "stages": ["plan"]}]},
        {"sensors": [{"id": "x", "kind": "builtin", "builtin": "nope", "stages": ["plan"]}]},
        {"nothing": 1},
    ):
        bad.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(FlowError):
            sensors.load_sensors(bad)


def test_decide_gate_rejects_missing_command(feature: tuple[Path, Path], tmp_path: Path) -> None:
    feature_dir, cfg = feature
    with pytest.raises(FlowError):
        decide_gate(feature_dir, "specify", True, "human:a", sensors_file=cfg)


def test_default_config_valid() -> None:
    assert {s.id for s in sensors.load_sensors()} >= {"consistency", "traceability"}


def test_stage_wildcard_matches_project_owned_stage(tmp_path: Path) -> None:
    config = tmp_path / "sensors.json"
    config.write_text(
        json.dumps(
            {
                "sensors": [
                    {
                        "id": "stage-contract",
                        "kind": "builtin",
                        "builtin": "stage-contract",
                        "stages": ["*"],
                        "required": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    selected = sensors.for_stage(
        sensors.load_sensors(config), "project-check", stage_contracts=True
    )
    assert [sensor.id for sensor in selected] == ["stage-contract"]


def _contract_feature(
    tmp_path: Path, include_plan: bool = False, enabled: bool = True
) -> tuple[Path, Path, Path]:
    specify_dir = tmp_path / ".specify"
    profiles_dir = specify_dir / "profiles"
    profiles_dir.mkdir(parents=True)
    plugin = specify_dir / "plugins" / "stage-contracts"
    (plugin / "contracts").mkdir(parents=True)
    (plugin / "plugin.json").write_text(
        json.dumps({"name": "stage-contracts", "version": "1.0.0", "enabled": True}),
        encoding="utf-8",
    )
    stages = ["specify", "plan"] if include_plan else ["specify"]
    contracts_payload = []
    for stage in stages:
        filename = "spec.md" if stage == "specify" else "plan.md"
        contracts_payload.append(
            {
                "stage": stage,
                "purpose": f"Complete {stage}",
                "inputs": [{"id": "request", "description": "Approved request"}],
                "outputs": [
                    {
                        "id": f"{stage}-output",
                        "description": f"{stage} deliverable",
                        "required": True,
                        "path": filename,
                    }
                ],
                "acceptance_criteria": ["Acceptance criteria are reviewed"],
                "review_focus": ["Completeness"],
            }
        )
    (plugin / "contracts" / "stages.json").write_text(
        json.dumps({"version": 1, "contracts": contracts_payload}), encoding="utf-8"
    )
    (plugin / "sensors.json").write_text(
        json.dumps(
            {
                "sensors": [
                    {
                        "id": "stage-contract",
                        "kind": "builtin",
                        "builtin": "stage-contract",
                        "stages": ["*"],
                        "required": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    sensor_file = specify_dir / "sensors" / "sensors.json"
    sensor_file.parent.mkdir(parents=True)
    sensor_file.write_text(json.dumps({"sensors": []}), encoding="utf-8")
    profile = {
        "id": "contract-test",
        "description": "Contract test route",
        "stages": stages,
        "depth": "standard",
        "gates": ["specify"],
        "stage_contracts": enabled,
    }
    (profiles_dir / "contract-test.json").write_text(json.dumps(profile), encoding="utf-8")
    feature_dir = tmp_path / "specs" / "feature"
    feature_dir.mkdir(parents=True)
    state.init_state(feature_dir, "contract-test", "human:test", profiles_dir)
    state.start_stage(feature_dir, "specify", "agent:developer", profiles_dir)
    state.done_stage(feature_dir, "specify", "agent:developer", profiles_dir)
    return feature_dir, sensor_file, profiles_dir


def test_contract_sensor_blocks_missing_and_stale_gate_evidence(tmp_path: Path) -> None:
    feature_dir, sensor_file, profiles_dir = _contract_feature(tmp_path)
    with pytest.raises(FlowError, match="has not been run"):
        state.decide_gate(
            feature_dir,
            "specify",
            True,
            "human:reviewer",
            sensors_file=sensor_file,
            profiles_dir=profiles_dir,
        )
    assert (
        sensors.run_stage(feature_dir, "specify", "agent:quality", sensor_file)[0]["status"]
        == "fail"
    )
    with pytest.raises(FlowError, match="failed"):
        state.decide_gate(
            feature_dir,
            "specify",
            True,
            "human:reviewer",
            sensors_file=sensor_file,
            profiles_dir=profiles_dir,
        )

    (feature_dir / "spec.md").write_text("# Specification\n", encoding="utf-8")
    assert (
        sensors.run_stage(feature_dir, "specify", "agent:quality", sensor_file)[0]["status"]
        == "pass"
    )
    (feature_dir / "spec.md").write_text("# Changed after check\n", encoding="utf-8")
    with pytest.raises(FlowError, match="stale"):
        state.decide_gate(
            feature_dir,
            "specify",
            True,
            "human:reviewer",
            sensors_file=sensor_file,
            profiles_dir=profiles_dir,
        )

    assert (
        sensors.run_stage(feature_dir, "specify", "agent:quality", sensor_file)[0]["status"]
        == "pass"
    )
    with pytest.raises(FlowError, match="only a human"):
        state.decide_gate(
            feature_dir,
            "specify",
            True,
            "agent:developer",
            sensors_file=sensor_file,
            profiles_dir=profiles_dir,
        )
    state.decide_gate(
        feature_dir,
        "specify",
        True,
        "human:reviewer",
        sensors_file=sensor_file,
        profiles_dir=profiles_dir,
    )
    events = (feature_dir / audit.AUDIT_FILE).read_text(encoding="utf-8")
    assert "# Changed after check" not in events


def test_contract_sensor_is_advisory_for_non_gated_stage(tmp_path: Path) -> None:
    feature_dir, sensor_file, profiles_dir = _contract_feature(tmp_path, include_plan=True)
    (feature_dir / "spec.md").write_text("# Specification\n", encoding="utf-8")
    sensors.run_stage(feature_dir, "specify", "agent:quality", sensor_file)
    state.decide_gate(
        feature_dir,
        "specify",
        True,
        "human:reviewer",
        sensors_file=sensor_file,
        profiles_dir=profiles_dir,
    )
    state.start_stage(feature_dir, "plan", "agent:developer", profiles_dir)
    result = sensors.run_stage(feature_dir, "plan", "agent:quality", sensor_file)
    assert result[0]["status"] == "fail"
    assert (
        state.done_stage(feature_dir, "plan", "agent:developer", profiles_dir).pending_gate is None
    )


def test_contract_sensor_does_not_change_profiles_that_opt_out(tmp_path: Path) -> None:
    feature_dir, sensor_file, profiles_dir = _contract_feature(tmp_path, enabled=False)
    assert sensors.run_stage(feature_dir, "specify", "agent:quality", sensor_file) == []
    assert state.decide_gate(
        feature_dir,
        "specify",
        True,
        "human:reviewer",
        sensors_file=sensor_file,
        profiles_dir=profiles_dir,
    ).pending_gate is None
