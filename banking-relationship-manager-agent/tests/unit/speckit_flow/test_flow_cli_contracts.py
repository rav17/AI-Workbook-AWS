from __future__ import annotations

import json
from pathlib import Path

from speckit_flow.cli import main


def _write_contracts(specify_dir: Path) -> None:
    plugin = specify_dir / "plugins" / "stage-contracts"
    (plugin / "contracts").mkdir(parents=True)
    (plugin / "plugin.json").write_text(
        json.dumps({"name": "stage-contracts", "version": "1.0.0", "enabled": True}),
        encoding="utf-8",
    )
    contract = {
        "stage": "specify",
        "purpose": "Define the user need",
        "inputs": [{"id": "request", "description": "Feature request"}],
        "outputs": [
            {
                "id": "specification",
                "description": "Feature specification",
                "required": True,
                "path": "spec.md",
            }
        ],
        "acceptance_criteria": ["Outcomes are testable"],
        "review_focus": ["Clarity"],
    }
    (plugin / "contracts" / "stages.json").write_text(
        json.dumps({"version": 1, "contracts": [contract]}), encoding="utf-8"
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
    sensors.parent.mkdir(parents=True)
    sensors.write_text(json.dumps({"sensors": []}), encoding="utf-8")


def test_contract_list_and_show(capsys, tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    profiles_dir = specify_dir / "profiles"
    profiles_dir.mkdir(parents=True)
    _write_contracts(specify_dir)

    assert main(["contracts", "list", "--profiles-dir", str(profiles_dir)]) == 0
    assert "specify: Define the user need" in capsys.readouterr().out

    assert (
        main(
            [
                "contracts",
                "show",
                "specify",
                "--profiles-dir",
                str(profiles_dir),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["contracts"][0]["stage"] == "specify"


def test_contract_show_checks_active_profile_and_route(capsys, tmp_path: Path) -> None:
    specify_dir = tmp_path / ".specify"
    profiles_dir = specify_dir / "profiles"
    profiles_dir.mkdir(parents=True)
    _write_contracts(specify_dir)
    profile = {
        "id": "contracts",
        "description": "Contract-enabled route",
        "stages": ["specify"],
        "depth": "standard",
        "gates": ["specify"],
        "stage_contracts": True,
    }
    (profiles_dir / "contracts.json").write_text(json.dumps(profile), encoding="utf-8")
    feature_dir = tmp_path / "specs" / "feature"
    feature_dir.mkdir(parents=True)
    assert (
        main(
            [
                "init",
                "--profile",
                "contracts",
                "--profiles-dir",
                str(profiles_dir),
                "--feature-dir",
                str(feature_dir),
                "--actor",
                "human:test",
            ]
        )
        == 0
    )

    assert (
        main(
            [
                "contracts",
                "show",
                "specify",
                "--profiles-dir",
                str(profiles_dir),
                "--feature-dir",
                str(feature_dir),
            ]
        )
        == 0
    )
    assert "specify: Define the user need" in capsys.readouterr().out
