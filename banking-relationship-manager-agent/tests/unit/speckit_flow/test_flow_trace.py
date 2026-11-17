from __future__ import annotations

from pathlib import Path

import pytest

from speckit_flow import trace
from speckit_flow.cli import main
from speckit_flow.models import FlowError

SPEC = "- **FR-001**: a\n- **FR-002**: b\n- **FR-003**: c\n"


def make(tmp_path: Path, tasks: str) -> Path:
    (tmp_path / "spec.md").write_text(SPEC, encoding="utf-8")
    (tmp_path / "tasks.md").write_text(tasks, encoding="utf-8")
    return tmp_path


def test_matrix_and_gaps(tmp_path: Path) -> None:
    tasks = (
        "- [ ] T001 FR-001 build it\n"
        "- [x] T002 FR-001 FR-002 add test for it\n"
        "- [ ] T003 FR-099 unknown\n"
        "- [ ] T004 no refs\n"
    )
    matrix = trace.build_matrix(make(tmp_path, tasks))
    assert matrix.requirements["FR-001"] == {"tasks": ["T001", "T002"], "tests": ["T002"]}
    assert matrix.uncovered == ["FR-003"]
    assert matrix.untested == []
    assert matrix.unknown_refs == ["T003:FR-099"]
    assert matrix.orphan_tasks == ["T004"]
    assert not matrix.ok()
    assert "uncovered: FR-003" in trace.render(matrix)


def test_untested_only_fails_when_required(tmp_path: Path) -> None:
    tasks = "- [ ] T001 FR-001 FR-002 FR-003 build\n"
    matrix = trace.build_matrix(make(tmp_path, tasks))
    assert matrix.ok()
    assert not matrix.ok(require_tests=True)


def test_missing_files(tmp_path: Path) -> None:
    with pytest.raises(FlowError):
        trace.build_matrix(tmp_path)


def test_cli_exit_codes(tmp_path: Path) -> None:
    d = make(tmp_path, "- [ ] T001 FR-001 FR-002 test FR-003\n")
    assert main(["trace", "--feature-dir", str(d)]) == 0
    d = make(tmp_path, "- [ ] T001 FR-001\n")
    assert main(["trace", "--feature-dir", str(d)]) == 1


def test_feature_013_is_traceable() -> None:
    root = Path(__file__).resolve().parents[3] / "specs" / "013-sensors-traceability-doctor"
    assert trace.build_matrix(root).ok(require_tests=False)


def test_task_progress_is_bounded_and_excludes_fenced_examples(tmp_path: Path) -> None:
    text = (
        "```markdown\n- [ ] T999 FR-099 example\n```\n"
        "~~~~markdown\n- [ ] T998 FR-099 another example\n~~~~\n"
        "- [X] T001 FR-001 done\n"
        "- [x] T002 FR-002 done\n"
    )
    text += "\n".join(f"- [ ] T{i:03d} FR-003 {'detail ' * 60}" for i in range(3, 503))
    make(tmp_path, text)
    progress = trace.task_progress(tmp_path)
    assert progress["total"] == 502
    assert progress["completed"] == 2
    assert progress["pending"] == 500
    assert progress["omitted_pending"] == 495
    preview = progress["pending_preview"]
    assert isinstance(preview, list)
    assert len(preview) == 5
    assert preview[0]["id"] == "T003"
    assert preview[0]["line"] == 9
    assert all(len(item["description"]) == 160 and item["truncated"] for item in preview)
    assert trace.build_matrix(tmp_path).unknown_refs == []


def test_task_progress_distinguishes_missing_empty_and_duplicate_tasks(tmp_path: Path) -> None:
    assert trace.task_progress(tmp_path) == {"status": "missing"}
    path = tmp_path / "tasks.md"
    path.write_text("# Tasks\n", encoding="utf-8")
    assert trace.task_progress(tmp_path)["status"] == "empty"
    path.write_text("- [ ] T001 one\n- [x] T001 repeated\n", encoding="utf-8")
    with pytest.raises(FlowError, match="duplicate task"):
        trace.task_progress(tmp_path)
    path.write_bytes(b"\xff")
    with pytest.raises(FlowError, match="cannot read tasks.md"):
        trace.task_progress(tmp_path)


@pytest.mark.parametrize(
    ("spec", "tasks", "message"),
    [
        ("# No requirements\n", "- [ ] T001 test\n", "no requirement"),
        ("FR-001\n", "# No tasks\n", "no task"),
        ("FR-001\n", "- [ ] T001 test FR-001\n- [x] T001 duplicate\n", "duplicate task"),
    ],
)
def test_invalid_trace_inputs_fail_explicitly(
    tmp_path: Path, spec: str, tasks: str, message: str,
) -> None:
    (tmp_path / "spec.md").write_text(spec, encoding="utf-8")
    (tmp_path / "tasks.md").write_text(tasks, encoding="utf-8")
    with pytest.raises(FlowError, match=message):
        trace.build_matrix(tmp_path)


def test_unknown_references_fail_even_when_all_requirements_are_tested(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    make(tmp_path, "- [ ] T001 test FR-001 FR-002 FR-003 FR-999\n")
    matrix = trace.build_matrix(tmp_path)
    assert not matrix.ok()
    assert not matrix.ok(True)
    assert main(["trace", "--feature-dir", str(tmp_path)]) == 1
    assert "T001:FR-999" in capsys.readouterr().out


def test_setup_tasks_without_references_remain_advisory(tmp_path: Path) -> None:
    make(tmp_path, "- [ ] T001 test FR-001 FR-002 FR-003\n- [ ] T002 setup\n")
    assert trace.build_matrix(tmp_path).ok(True)
