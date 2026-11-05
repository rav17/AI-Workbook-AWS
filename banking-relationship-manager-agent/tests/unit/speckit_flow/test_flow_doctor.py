from __future__ import annotations

import json
from pathlib import Path

from speckit_flow import doctor
from speckit_flow.agents import DEFAULT_ROSTER_FILE
from speckit_flow.cli import main
from speckit_flow.profiles import DEFAULT_PROFILES_DIR
from speckit_flow.rules import DEFAULT_RULES_FILE
from speckit_flow.sensors import DEFAULT_SENSORS_FILE

ROOT = Path(__file__).resolve().parents[3]


def checks(feature_dir: Path | None = None, **over: Path) -> dict[str, doctor.Check]:
    kwargs = {
        "profiles_dir": DEFAULT_PROFILES_DIR,
        "roster_file": DEFAULT_ROSTER_FILE,
        "sensors_file": DEFAULT_SENSORS_FILE,
        "rules_file": DEFAULT_RULES_FILE,
    } | over
    result = doctor.run_doctor(ROOT, feature_dir=feature_dir, **kwargs)
    return {c.name: c for c in result}


def test_healthy_repo() -> None:
    result = checks()
    assert not [c for c in result.values() if c.status == "fail"]
    assert result["feature"].status == "skip"


def test_unknown_phase_rule_file_fails(tmp_path: Path) -> None:
    rules_file = tmp_path / "rules.json"
    rules_file.write_text('{"rules": []}', encoding="utf-8")
    (tmp_path / "phase").mkdir()
    (tmp_path / "phase" / "nonsense.json").write_text('{"rules": []}', encoding="utf-8")
    assert checks(rules_file=rules_file)["rules"].status == "fail"
    (tmp_path / "phase" / "nonsense.json").rename(tmp_path / "phase" / "plan.json")
    assert checks(rules_file=rules_file)["rules"].status == "ok"


def test_broken_pieces_fail(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    result = checks(roster_file=bad, sensors_file=bad)
    assert result["roster"].status == "fail"
    assert result["sensors"].status == "fail"
    assert result["profiles"].status == "ok"


def test_audit_chain_tamper_detected(tmp_path: Path) -> None:
    d = tmp_path / "specs" / "013-x"
    d.mkdir(parents=True)
    base = ["--feature-dir", str(d), "--actor", "human:a"]
    assert main(["init", "--profile", "express", *base]) == 0
    assert main(["stage", "start", "specify", *base]) == 0
    assert checks(d)["audit-chain"].status == "ok"
    audit_file = d / "audit.jsonl"
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["detail"] = "tampered"
    lines[0] = json.dumps(first, separators=(",", ":"))
    audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert checks(d)["audit-chain"].status == "fail"


def test_cli_doctor(capsys: object) -> None:
    assert main(["doctor", "--feature-dir", str(ROOT / "specs" / "does-not-exist")]) == 0
