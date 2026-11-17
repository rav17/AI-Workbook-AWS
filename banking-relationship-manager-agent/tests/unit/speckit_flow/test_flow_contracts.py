from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from speckit_flow import contracts, sensors, state
from speckit_flow.models import FlowError, Profile


def _contract(
    stage: str = "specify",
    *,
    purpose: str = "Define the user need",
    output_path: str | None = "spec.md",
) -> dict[str, object]:
    output: dict[str, object] = {
        "id": "specification",
        "description": "A complete specification",
        "required": True,
    }
    if output_path is not None:
        output["path"] = output_path
    return {
        "stage": stage,
        "purpose": purpose,
        "inputs": [{"id": "request", "description": "The feature request"}],
        "outputs": [output],
        "acceptance_criteria": ["User needs and outcomes are testable"],
        "review_focus": ["Requirement clarity"],
    }


def _write_plugin(specify_dir: Path, contracts: list[dict[str, object]]) -> None:
    plugin = specify_dir / "plugins" / "stage-contracts"
    (plugin / "contracts").mkdir(parents=True, exist_ok=True)
    (plugin / "plugin.json").write_text(
        json.dumps(
            {
                "name": "stage-contracts",
                "version": "1.0.0",
                "enabled": True,
            }
        ),
        encoding="utf-8",
    )
    (plugin / "contracts" / "stages.json").write_text(
        json.dumps({"version": 1, "contracts": contracts}), encoding="utf-8"
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
    sensors = specify_dir / "sensors" / "sensors.json"
    sensors.parent.mkdir(parents=True, exist_ok=True)
    sensors.write_text(json.dumps({"sensors": []}), encoding="utf-8")


def _profile(*, stages: tuple[str, ...] = ("specify",), gates: tuple[str, ...] = ()) -> Profile:
    return Profile(
        id="contract-test",
        description="Contract fixture",
        stages=stages,
        depth="standard",
        gates=gates,
        stage_contracts=True,
    )


def test_loads_plugin_contract_and_project_override(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract()])
    custom = specify_dir / "custom" / "stage-contracts.json"
    custom.parent.mkdir()
    custom.write_text(
        json.dumps({"version": 1, "contracts": [_contract(purpose="Project contract")]}),
        encoding="utf-8",
    )

    loaded = contracts.load_contracts(specify_dir)

    assert loaded["specify"].purpose == "Project contract"
    assert loaded["specify"].outputs[0].path == "spec.md"


@pytest.mark.parametrize(
    "items",
    [
        [_contract("unknown-stage")],
        [_contract(), _contract(purpose="Duplicate")],
        [_contract(output_path="../outside.md")],
        [_contract(output_path="C:/outside.md")],
        [_contract(output_path="folder\\outside.md")],
    ],
)
def test_rejects_invalid_contract_declarations(
    tmp_path: Path, items: list[dict[str, object]]
) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, items)
    with pytest.raises(FlowError):
        contracts.load_contracts(specify_dir)


def test_rejects_malformed_contract_file(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract()])
    path = specify_dir / "plugins" / "stage-contracts" / "contracts" / "stages.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(FlowError, match="valid JSON"):
        contracts.load_contracts(specify_dir)


def test_profile_requires_contracts_for_all_routed_stages(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract()])
    with pytest.raises(FlowError, match="missing contracts.*plan"):
        contracts.validate_profile(
            _profile(stages=("specify", "plan")), specify_dir
        )


def test_gated_required_output_needs_a_path(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract(output_path=None)])
    with pytest.raises(FlowError, match="required output.*path"):
        contracts.validate_profile(
            _profile(stages=("specify",), gates=("specify",)), specify_dir
        )


def test_profile_enforces_contract_output_count_limit(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    outputs = [
        {
            "id": f"output-{index}",
            "description": "Required deliverable",
            "required": True,
            "path": f"output-{index}.md",
        }
        for index in range(contracts.MAX_OUTPUTS + 1)
    ]
    declaration = _contract()
    declaration["outputs"] = outputs
    _write_plugin(specify_dir, [declaration])
    with pytest.raises(FlowError, match="100-file limit"):
        contracts.validate_profile(
            _profile(stages=("specify",), gates=("specify",)), specify_dir
        )


def test_check_outputs_reports_missing_and_empty_files(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract()])
    feature_dir = tmp_path / "specs" / "feature"
    feature_dir.mkdir(parents=True)

    passed, reason = contracts.check_outputs(feature_dir, "specify", specify_dir)
    assert not passed
    assert "spec.md" in reason

    (feature_dir / "spec.md").write_text("", encoding="utf-8")
    passed, reason = contracts.check_outputs(feature_dir, "specify", specify_dir)
    assert not passed
    assert "empty" in reason

    (feature_dir / "spec.md").write_text("# Specification\n", encoding="utf-8")
    assert contracts.check_outputs(feature_dir, "specify", specify_dir)[0]


def test_check_outputs_reports_inaccessible_parent(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract(output_path="nested/spec.md")])
    feature_dir = tmp_path / "specs" / "feature"
    feature_dir.mkdir(parents=True)
    (feature_dir / "nested").write_text("not a directory", encoding="utf-8")

    passed, reason = contracts.check_outputs(feature_dir, "specify", specify_dir)
    assert not passed
    assert "parent is not a directory" in reason


def test_check_outputs_rejects_symlink(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract()])
    feature_dir = tmp_path / "specs" / "feature"
    feature_dir.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    try:
        (feature_dir / "spec.md").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    passed, reason = contracts.check_outputs(feature_dir, "specify", specify_dir)
    assert not passed
    assert "symlink" in reason


def test_check_outputs_rejects_oversized_file(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract()])
    feature_dir = tmp_path / "specs" / "feature"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_bytes(b"x" * (contracts.MAX_OUTPUT_BYTES + 1))
    passed, reason = contracts.check_outputs(feature_dir, "specify", specify_dir)
    assert not passed
    assert "exceeds" in reason


def test_fingerprints_change_when_required_output_changes(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    _write_plugin(specify_dir, [_contract()])
    feature_dir = tmp_path / "specs" / "feature"
    feature_dir.mkdir(parents=True)
    output = feature_dir / "spec.md"
    output.write_text("# First\n", encoding="utf-8")
    before = contracts.fingerprints(feature_dir, "specify", specify_dir)
    output.write_text("# Second\n", encoding="utf-8")
    after = contracts.fingerprints(feature_dir, "specify", specify_dir)
    assert before != after


def test_opted_in_contract_inputs_block_missing_and_stale_gate_evidence(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    declaration = _contract()
    declaration["inputs"] = [{
        "id": "source", "description": "Source evidence", "path": "inputs/source.md",
    }]
    _write_plugin(specify_dir, [declaration])
    profile = replace(_profile(gates=("specify",)), contract_inputs=True)
    profiles = specify_dir / "profiles"
    profiles.mkdir()
    (profiles / f"{profile.id}.json").write_text(json.dumps(profile.to_dict()), encoding="utf-8")
    feature = tmp_path / "specs" / "001-inputs"
    feature.mkdir(parents=True)
    state.init_state(feature, profile.id, "human:test", profiles)
    state.start_stage(feature, "specify", "human:test", profiles)
    (feature / "spec.md").write_text("# Specification\n", encoding="utf-8")
    config = specify_dir / "sensors" / "sensors.json"
    result = sensors.run_stage(feature, "specify", "agent:workflow", config)
    assert result[0]["status"] == "fail"
    assert "input inputs/source.md missing" in result[0]["reason"]
    (feature / "inputs").mkdir()
    source = feature / "inputs" / "source.md"
    source.write_text("Synthetic input v1", encoding="utf-8")
    assert sensors.run_stage(feature, "specify", "agent:workflow", config)[0]["status"] == "pass"
    state.done_stage(feature, "specify", "human:test", profiles)
    source.write_text("Synthetic input v2", encoding="utf-8")
    with pytest.raises(FlowError, match="stale"):
        state.decide_gate(
            feature, "specify", True, "human:test", sensors_file=config, profiles_dir=profiles
        )
    sensors.run_stage(feature, "specify", "agent:workflow", config)
    state.decide_gate(
        feature, "specify", True, "human:test", sensors_file=config, profiles_dir=profiles
    )


def test_path_bound_input_checks_do_not_change_legacy_output_scope(tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    declaration = _contract()
    declaration["inputs"] = [{"id": "source", "description": "Input", "path": "source.md"}]
    _write_plugin(specify_dir, [declaration])
    feature = tmp_path / "specs" / "001-inputs"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("Synthetic output", encoding="utf-8")
    assert contracts.check_outputs(feature, "specify", specify_dir)[0]
    assert not contracts.check_inputs(feature, "specify", specify_dir)[0]
    before = contracts.fingerprints(feature, "specify", specify_dir)
    source = feature / "source.md"
    source.write_bytes(b"x" * (contracts.MAX_OUTPUT_BYTES + 1))
    assert not contracts.check_inputs(feature, "specify", specify_dir)[0]
    assert before == contracts.fingerprints(feature, "specify", specify_dir)
    assert before != contracts.fingerprints(feature, "specify", specify_dir, include_inputs=True)
