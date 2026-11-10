from __future__ import annotations

import json
import stat
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from speckit_flow import audit, readiness, sensors, state
from speckit_flow.models import FlowError

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / ".specify" / "plugins" / "operational-readiness"


def _record(headings: tuple[str, ...]) -> str:
    return "# Sample operational record\n\n" + "\n\n".join(
        f"## {heading}\n\nDocumented procedure owned by the release team.\n"
        "- Evidence: review/record-42 at revision abc123, reviewed by release owner."
        for heading in headings
    )


def _records(feature: Path) -> None:
    feature.mkdir(parents=True, exist_ok=True)
    for name, headings in readiness.SECTIONS.items():
        (feature / name).write_text(_record(headings), encoding="utf-8")


def _sensor_file(root: Path, profiles: list[str] | None = None) -> Path:
    path = root / ".specify" / "sensors" / "sensors.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    sensor: dict[str, object] = {
        "id": "operational-readiness",
        "kind": "builtin",
        "builtin": "readiness",
        "stages": ["deploy", "operate"],
        "required": True,
    }
    if profiles is not None:
        sensor["profiles"] = profiles
    path.write_text(json.dumps({"sensors": [sensor]}), encoding="utf-8")
    return path


def test_complete_records_pass_without_executing_evidence(tmp_path: Path) -> None:
    _records(tmp_path)
    with patch("subprocess.run", side_effect=AssertionError("must not execute")):
        passed, reason = readiness.check(tmp_path)
    assert passed
    assert "structur" in reason
    assert set(readiness.fingerprints(tmp_path)) == {"release.md", "runbook.md"}


@pytest.mark.parametrize(
    ("name", "heading"),
    [
        (name, heading)
        for name, headings in (
            (
                "release.md",
                (
                    "Ownership and target",
                    "Configuration",
                    "Verification",
                    "Rollout",
                    "Rollback",
                ),
            ),
            (
                "runbook.md",
                ("Ownership", "Health signals", "Alerts", "Incidents", "Rollback", "Feedback"),
            ),
        )
        for heading in headings
    ],
)
def test_each_required_section_and_evidence_is_checked(
    tmp_path: Path,
    name: str,
    heading: str,
) -> None:
    _records(tmp_path)
    path = tmp_path / name
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original.replace(f"## {heading}\n", f"## Missing {heading}\n"), encoding="utf-8"
    )
    passed, reason = readiness.check(tmp_path)
    assert not passed
    assert name in reason and heading in reason
    path.write_text(
        original.replace(
            f"## {heading}\n\nDocumented procedure owned by the release team.\n" "- Evidence:",
            f"## {heading}\n\nProcedure.\n- Reference:",
        ),
        encoding="utf-8",
    )
    assert not readiness.check(tmp_path)[0]


@pytest.mark.parametrize(
    "body",
    [
        "- Evidence: approved-record\n",
        "Procedure.\n- Evidence: \n",
        "{{fill this}}\n- Evidence: approved-record\n",
        "TBD\n- Evidence: approved-record\n",
        "[OWNER]\n- Evidence: approved-record\n",
        "TODO: confirm.\n- Evidence: approved-record\n",
        "todo: confirm.\n- Evidence: approved-record\n",
        "- [ ] Confirm rollback.\n- Evidence: approved-record\n",
        "<!-- Procedure.\n- Evidence: approved-record -->\n",
        "```markdown\nProcedure.\n- Evidence: approved-record\n```\n",
        "~~~markdown\nProcedure.\n- Evidence: approved-record\n~~~\n",
        "Procedure.\n<!-- - Evidence: approved-record -->\n",
        "    Procedure.\n    - Evidence: approved-record\n",
    ],
)
def test_incomplete_or_example_only_sections_fail(tmp_path: Path, body: str) -> None:
    _records(tmp_path)
    release = tmp_path / "release.md"
    release.write_text(
        _record(readiness.SECTIONS["release.md"]) + "\n\n## Verification\n" + body,
        encoding="utf-8",
    )
    # Replace the original verification section so this tests body validation, not duplication.
    original = (
        "## Verification\n\nDocumented procedure owned by the release team.\n"
        "- Evidence: review/record-42 at revision abc123, reviewed by release owner."
    )
    release.write_text(release.read_text(encoding="utf-8").replace(original, ""), encoding="utf-8")
    assert not readiness.check(tmp_path)[0]


def test_duplicate_headings_fail(tmp_path: Path) -> None:
    _records(tmp_path)
    path = tmp_path / "runbook.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n\n## Alerts\nDuplicate.\n- Evidence: review.",
        encoding="utf-8",
    )
    assert not readiness.check(tmp_path)[0]


def test_templates_do_not_pass_as_readiness(tmp_path: Path) -> None:
    _records(tmp_path)
    for name in readiness.SECTIONS:
        (tmp_path / name).write_bytes((PACK / "templates" / name).read_bytes())
    assert not readiness.check(tmp_path)[0]


def test_record_access_and_size_fail_explicitly(tmp_path: Path) -> None:
    _records(tmp_path)
    path = tmp_path / "release.md"
    original = path.read_bytes()
    path.write_bytes(original + b" " * (readiness.MAX_BYTES - len(original)))
    assert readiness.check(tmp_path)[0]
    path.write_bytes(b"x" * (readiness.MAX_BYTES + 1))
    with pytest.raises(FlowError, match="limit"):
        readiness.fingerprints(tmp_path)
    assert not readiness.check(tmp_path)[0]
    path.write_bytes(b"\xff")
    assert "UTF-8" in readiness.check(tmp_path)[1]
    path.unlink()
    assert "release.md" in readiness.check(tmp_path)[1]
    path.mkdir()
    assert "regular" in readiness.check(tmp_path)[1]


def test_checked_tasks_are_not_treated_as_placeholders(tmp_path: Path) -> None:
    _records(tmp_path)
    path = tmp_path / "release.md"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n- [X] Reviewed.\n- [x] Reviewed again.\n",
        encoding="utf-8",
    )
    assert readiness.check(tmp_path)[0]


def test_reparse_point_artifacts_are_rejected(tmp_path: Path) -> None:
    info = SimpleNamespace(
        st_mode=stat.S_IFREG,
        st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
    )
    with patch.object(Path, "lstat", return_value=info):
        assert "non-symlink" in readiness.check(tmp_path)[1]


def test_permission_error_is_not_swallowed(tmp_path: Path) -> None:
    _records(tmp_path)
    with patch.object(Path, "open", side_effect=PermissionError("fixture denied")):
        assert "cannot read release.md" in readiness.check(tmp_path)[1]


def test_symlink_artifact_is_rejected(tmp_path: Path) -> None:
    _records(tmp_path)
    target = tmp_path / "actual.md"
    (tmp_path / "release.md").rename(target)
    try:
        (tmp_path / "release.md").symlink_to(target)
    except OSError:
        pytest.skip("symlink creation unavailable")
    assert not readiness.check(tmp_path)[0]


@pytest.mark.parametrize("name", ["release.md", "runbook.md"])
@pytest.mark.parametrize("stage", ["deploy", "operate"])
def test_readiness_results_stale_on_record_change_and_deletion(
    tmp_path: Path,
    name: str,
    stage: str,
) -> None:
    feature = tmp_path / "specs" / "029-demo"
    _records(feature)
    config = _sensor_file(tmp_path)
    assert sensors.gate_problems(feature, stage, config)[0]
    assert sensors.run_stage(feature, stage, "agent:test", config)[0]["status"] == "pass"
    assert not sensors.gate_problems(feature, stage, config)[0]
    path = feature / name
    path.write_text(path.read_text(encoding="utf-8") + "\nChanged evidence.\n", encoding="utf-8")
    assert "stale" in sensors.gate_problems(feature, stage, config)[0][0]
    sensors.run_stage(feature, stage, "agent:test", config)
    assert not sensors.gate_problems(feature, stage, config)[0]
    path.unlink()
    assert "stale" in sensors.gate_problems(feature, stage, config)[0][0]
    assert sensors.run_stage(feature, stage, "agent:test", config)[0]["status"] == "fail"
    assert audit.verify_chain(feature) is None


def test_readiness_fingerprints_do_not_change_unrelated_sensor_results(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "029-demo"
    _records(feature)
    (feature / "spec.md").write_text("# Sample\n\n## Risk\nLow.\n", encoding="utf-8")
    config = _sensor_file(tmp_path)
    data = json.loads(config.read_text(encoding="utf-8"))
    data["sensors"].append(
        {
            "id": "section",
            "kind": "builtin",
            "builtin": "section",
            "stages": ["deploy"],
            "required": True,
            "options": {"heading": "Risk"},
        }
    )
    config.write_text(json.dumps(data), encoding="utf-8")
    sensors.run_stage(feature, "deploy", "agent:test", config)
    (feature / "runbook.md").write_text("changed", encoding="utf-8")
    problems, _ = sensors.gate_problems(feature, "deploy", config)
    assert len(problems) == 1 and "operational-readiness" in problems[0]


def test_sensor_is_profile_scoped(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "029-demo"
    feature.mkdir(parents=True)
    state.init_state(feature, "feature", "agent:test")
    config = _sensor_file(tmp_path, ["release-ready"])
    assert sensors.run_stage(feature, "deploy", "agent:test", config) == []
    assert sensors.gate_problems(feature, "deploy", config) == ([], [])


def test_sensor_options_are_explicitly_rejected(tmp_path: Path) -> None:
    config = _sensor_file(tmp_path)
    data = json.loads(config.read_text(encoding="utf-8"))
    data["sensors"][0]["options"] = {"pretend_live": True}
    config.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FlowError, match="does not accept options"):
        sensors.load_sensors(config)


def test_invalid_record_blocks_reuse_of_passed_result(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "029-demo"
    _records(feature)
    config = _sensor_file(tmp_path)
    sensors.run_stage(feature, "deploy", "agent:test", config)
    (feature / "release.md").write_bytes(b"\xff")
    problems, _ = sensors.gate_problems(feature, "deploy", config)
    assert len(problems) == 1 and "UTF-8" in problems[0]


def test_changes_during_validation_do_not_create_passing_result(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "029-demo"
    _records(feature)
    config = _sensor_file(tmp_path)
    check = readiness.check

    def changing_check(path: Path) -> tuple[bool, str]:
        passed, reason = check(path)
        (path / "release.md").write_text("changed during check", encoding="utf-8")
        return passed, reason

    with patch.object(readiness, "check", side_effect=changing_check):
        outcomes = sensors.run_stage(feature, "deploy", "agent:test", config)
    assert outcomes[0]["status"] == "fail"
    assert "changed during" in outcomes[0]["reason"]
