from __future__ import annotations

from pathlib import Path

SKILL = Path(__file__).resolve().parents[3] / ".github" / "skills" / "speckit-clarify" / "SKILL.md"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_clarify_skill_documents_modes_and_commands() -> None:
    text = _text()
    for needle in ("guided", "file", "discussion", "questions add", "questions check"):
        assert needle in text


def test_clarify_skill_forbids_agent_answering() -> None:
    text = _text()
    assert "MUST NOT run `questions answer`" in text


def test_clarify_skill_keeps_original_loop() -> None:
    assert "Sequential questioning loop" in _text()
