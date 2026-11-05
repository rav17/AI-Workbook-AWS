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
