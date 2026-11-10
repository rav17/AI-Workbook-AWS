from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from speckit_flow.models import FlowError

_REQ_RE = re.compile(r"\bFR-\d{3,}\b")
_TASK_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*(T\d+)\b(.*)$")
_TEST_RE = re.compile(r"\btests?\b", re.IGNORECASE)


@dataclass
class TraceMatrix:
    requirements: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    uncovered: list[str] = field(default_factory=list)
    untested: list[str] = field(default_factory=list)
    unknown_refs: list[str] = field(default_factory=list)
    orphan_tasks: list[str] = field(default_factory=list)

    def ok(self, require_tests: bool = False) -> bool:
        gaps = self.uncovered + (self.untested if require_tests else [])
        return not gaps

    def to_dict(self) -> dict[str, object]:
        return {
            "requirements": self.requirements,
            "uncovered": self.uncovered,
            "untested": self.untested,
            "unknown_refs": self.unknown_refs,
            "orphan_tasks": self.orphan_tasks,
        }


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FlowError(f"cannot read {path.name}: {exc}") from exc


def build_matrix(feature_dir: Path) -> TraceMatrix:
    spec, tasks = feature_dir / "spec.md", feature_dir / "tasks.md"
    if not spec.is_file():
        raise FlowError("spec.md not found; cannot trace requirements")
    if not tasks.is_file():
        raise FlowError("tasks.md not found; cannot trace requirements")
    ids = sorted(set(_REQ_RE.findall(_read(spec))))
    matrix = TraceMatrix(requirements={i: {"tasks": [], "tests": []} for i in ids})
    unknown: set[str] = set()
    for line in _read(tasks).splitlines():
        found = _TASK_RE.match(line)
        if not found:
            continue
        task_id, rest = found.group(1), found.group(2)
        refs = set(_REQ_RE.findall(rest))
        if not refs:
            matrix.orphan_tasks.append(task_id)
        is_test = bool(_TEST_RE.search(rest))
        for ref in sorted(refs):
            if ref not in matrix.requirements:
                unknown.add(f"{task_id}:{ref}")
                continue
            matrix.requirements[ref]["tasks"].append(task_id)
            if is_test:
                matrix.requirements[ref]["tests"].append(task_id)
    matrix.uncovered = [r for r, v in matrix.requirements.items() if not v["tasks"]]
    matrix.untested = [r for r, v in matrix.requirements.items() if v["tasks"] and not v["tests"]]
    matrix.unknown_refs = sorted(unknown)
    return matrix


def render(matrix: TraceMatrix) -> str:
    lines = ["requirement  tasks  tests"]
    for req, row in matrix.requirements.items():
        lines.append(f"{req:12} {','.join(row['tasks']) or '-':20} {','.join(row['tests']) or '-'}")
    if matrix.uncovered:
        lines.append("uncovered: " + ", ".join(matrix.uncovered))
    if matrix.untested:
        lines.append("no test task: " + ", ".join(matrix.untested))
    if matrix.unknown_refs:
        lines.append("unknown references: " + ", ".join(matrix.unknown_refs))
    if matrix.orphan_tasks:
        lines.append("tasks citing no requirement: " + ", ".join(matrix.orphan_tasks))
    return "\n".join(lines)
