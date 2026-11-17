from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from speckit_flow.models import FlowError

_REQ_RE = re.compile(r"\bFR-\d{3,}\b")
_TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(T\d+)\b(.*)$")
_TEST_RE = re.compile(r"\btests?\b", re.IGNORECASE)
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


@dataclass
class TraceMatrix:
    requirements: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    uncovered: list[str] = field(default_factory=list)
    untested: list[str] = field(default_factory=list)
    unknown_refs: list[str] = field(default_factory=list)
    orphan_tasks: list[str] = field(default_factory=list)

    def ok(self, require_tests: bool = False) -> bool:
        gaps = self.uncovered + (self.untested if require_tests else [])
        return bool(self.requirements) and not (gaps or self.unknown_refs)

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
    except (OSError, UnicodeError) as exc:
        raise FlowError(f"cannot read {path.name}: {exc}") from exc


def _tasks(text: str) -> Iterator[tuple[str, str, bool, int]]:
    fence = ""
    seen: set[str] = set()
    for number, line in enumerate(text.splitlines(), 1):
        marker = _FENCE_RE.match(line)
        if marker:
            run, suffix = marker.groups()
            if not fence:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence) and not suffix.strip():
                fence = ""
            continue
        if fence:
            continue
        found = _TASK_RE.match(line)
        if found:
            checked, task_id, description = found.groups()
            if task_id in seen:
                raise FlowError(f"duplicate task id {task_id!r} in tasks.md")
            seen.add(task_id)
            yield task_id, description.strip(), checked.lower() == "x", number


def task_progress(feature_dir: Path) -> dict[str, object]:
    """Return bounded checkbox progress, not dependency readiness or test evidence."""
    path = feature_dir / "tasks.md"
    if not path.exists():
        return {"status": "missing"}
    tasks = list(_tasks(_read(path)))
    pending: list[dict[str, object]] = []
    completed = 0
    for task_id, description, checked, line in tasks:
        if checked:
            completed += 1
        elif len(pending) < 5:
            pending.append({
                "id": task_id,
                "line": line,
                "description": description[:160],
                "truncated": len(description) > 160,
            })
    count = len(tasks) - completed
    return {
        "status": "present" if tasks else "empty",
        "total": len(tasks),
        "completed": completed,
        "pending": count,
        "pending_preview": pending,
        "omitted_pending": max(0, count - len(pending)),
    }


def build_matrix(feature_dir: Path) -> TraceMatrix:
    spec, tasks = feature_dir / "spec.md", feature_dir / "tasks.md"
    if not spec.is_file():
        raise FlowError("spec.md not found; cannot trace requirements")
    if not tasks.is_file():
        raise FlowError("tasks.md not found; cannot trace requirements")
    ids = sorted(set(_REQ_RE.findall(_read(spec))))
    if not ids:
        raise FlowError("spec.md has no requirement IDs; expected FR-001 style requirements")
    entries = list(_tasks(_read(tasks)))
    if not entries:
        raise FlowError("tasks.md has no task entries; expected '- [ ] T001 ...'")
    matrix = TraceMatrix(requirements={i: {"tasks": [], "tests": []} for i in ids})
    unknown: set[str] = set()
    for task_id, rest, _, _ in entries:
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
