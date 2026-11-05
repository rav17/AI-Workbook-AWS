from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from speckit_flow import audit
from speckit_flow.models import FlowError

QUESTIONS_FILE = "questions.md"
MAX_TEXT = 500
_ROLE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_HEADER_RE = re.compile(r"^## (Q\d+) \[role: ([a-z][a-z0-9-]*)\]\s*$")
_ANSWER_MARK = "**Answer:**"
_TITLE = "# Clarifying Questions\n"


@dataclass
class Question:
    id: str
    role: str
    text: str
    answer: str

    @property
    def status(self) -> str:
        return "answered" if self.answer else "open"

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "role": self.role,
            "status": self.status,
            "text": self.text,
            "answer": self.answer,
        }


def load_questions(feature_dir: Path) -> list[Question]:
    """Parse questions.md; humans may also edit it by hand to answer."""
    path = feature_dir / QUESTIONS_FILE
    if not path.is_file():
        return []
    questions: list[Question] = []
    current: tuple[str, str] | None = None
    body: list[str] = []

    def flush() -> None:
        if current is None:
            return
        text_lines: list[str] = []
        answer_lines: list[str] = []
        target = text_lines
        for line in body:
            if line.startswith(_ANSWER_MARK):
                target = answer_lines
                line = line[len(_ANSWER_MARK) :]
            target.append(line)
        questions.append(
            Question(
                current[0],
                current[1],
                " ".join(s.strip() for s in text_lines if s.strip()),
                " ".join(s.strip() for s in answer_lines if s.strip()),
            )
        )

    for line in path.read_text(encoding="utf-8").splitlines():
        match = _HEADER_RE.match(line)
        if match:
            flush()
            current, body = (match.group(1), match.group(2)), []
        elif current is not None:
            body.append(line)
        if line.startswith("## ") and not match:
            raise FlowError(f"questions.md has a malformed heading: {line[:40]!r}")
    flush()
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise FlowError("questions.md has duplicate question ids")
    return questions


def _save(feature_dir: Path, questions: list[Question]) -> None:
    from speckit_flow.state import atomic_write  # deferred: state imports this module

    parts = [_TITLE]
    for q in questions:
        parts.append(f"\n## {q.id} [role: {q.role}]\n{q.text}\n\n{_ANSWER_MARK} {q.answer}\n")
    atomic_write(feature_dir / QUESTIONS_FILE, "".join(parts))


def add_question(
    feature_dir: Path,
    text: str,
    role: str,
    actor: str,
    valid_roles: set[str] | None = None,
) -> Question:
    text = text.strip()
    if not 1 <= len(text) <= MAX_TEXT or "\n" in text:
        raise FlowError(f"question must be 1-{MAX_TEXT} characters on one line")
    if not _ROLE_RE.match(role) or (valid_roles is not None and role not in valid_roles):
        raise FlowError(f"unknown role {role!r}")
    audit.check_redaction(text)
    questions = load_questions(feature_dir)
    number = max((int(q.id[1:]) for q in questions), default=0) + 1
    question = Question(f"Q{number}", role, text, "")
    audit.append_event(feature_dir, "question_asked", None, actor, f"{question.id} role={role}")
    _save(feature_dir, [*questions, question])
    return question


def answer_question(feature_dir: Path, qid: str, answer: str, actor: str) -> Question:
    if not actor.startswith("human:"):
        raise FlowError("only a human can answer a question")
    answer = answer.strip()
    if not 1 <= len(answer) <= MAX_TEXT or "\n" in answer:
        raise FlowError(f"answer must be 1-{MAX_TEXT} characters on one line")
    audit.check_redaction(answer)
    questions = load_questions(feature_dir)
    question = next((q for q in questions if q.id == qid), None)
    if question is None:
        raise FlowError(f"unknown question {qid!r}")
    if question.answer:
        raise FlowError(f"question {qid} is already answered")
    audit.append_event(feature_dir, "question_answered", None, actor, f"{qid} role={question.role}")
    question.answer = answer
    _save(feature_dir, questions)
    return question


def list_questions(
    feature_dir: Path, open_only: bool = False, role: str | None = None
) -> dict[str, Any]:
    items = [
        q
        for q in load_questions(feature_dir)
        if (not open_only or not q.answer) and (role is None or q.role == role)
    ]
    return {"questions": [q.to_dict() for q in items]}


def open_questions(feature_dir: Path) -> list[Question]:
    return [q for q in load_questions(feature_dir) if not q.answer]
