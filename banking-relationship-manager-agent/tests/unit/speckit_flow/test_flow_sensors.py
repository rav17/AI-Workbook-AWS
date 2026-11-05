from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import sensors
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
