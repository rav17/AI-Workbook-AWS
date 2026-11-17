from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import audit, state
from speckit_flow.cli import main


def test_context_is_bounded_read_only_and_reports_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state.init_state(tmp_path, "quick", "human:test")
    for stage in ("specify", "plan", "tasks"):
        state.start_stage(tmp_path, stage, "agent:workflow")
        state.done_stage(tmp_path, stage, "agent:workflow")
    (tmp_path / "spec.md").write_text("FR-001\n", encoding="utf-8")
    (tmp_path / "tasks.md").write_text(
        "\n".join(f"- [ ] T{i:03d} {'detail ' * 100}" for i in range(1, 501)),
        encoding="utf-8",
    )
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert main(["context", "--feature-dir", str(tmp_path), "--json"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["profile"] == "quick"
    assert payload["execution"] == "inline"
    assert payload["pending_gate"] == "tasks"
    assert payload["parked"] is False
    assert payload["artifacts"] == {"spec.md": True, "plan.md": False, "tasks.md": True}
    assert payload["tasks"]["pending"] == 500
    assert len(payload["tasks"]["pending_preview"]) == 5
    assert len(output) < 6000
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert state.load_state(tmp_path).pending_gate == "tasks"


@pytest.mark.parametrize("audit_problem", ["missing", "corrupt"])
def test_context_fails_on_invalid_audit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], audit_problem: str
) -> None:
    state.init_state(tmp_path, "quick", "human:test")
    path = tmp_path / "audit.jsonl"
    if audit_problem == "missing":
        path.unlink()
    else:
        path.write_text(path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    assert main(["context", "--feature-dir", str(tmp_path), "--json"]) == 1
    assert "audit" in capsys.readouterr().err


def test_context_reports_parked_feature_and_missing_tasks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state.init_state(tmp_path, "quick", "human:test")
    audit.append_event(tmp_path, "intent_parked", None, "human:test", "paused")
    assert main(["context", "--feature-dir", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["parked"] is True
    assert payload["tasks"] == {"status": "missing"}


def test_context_rejects_missing_profile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state.init_state(tmp_path, "quick", "human:test")
    assert main([
        "context", "--feature-dir", str(tmp_path),
        "--profiles-dir", str(tmp_path / "missing-profiles"), "--json",
    ]) == 1
    assert "profiles directory not found" in capsys.readouterr().err


def test_workflow_guidance_requires_scoped_verification() -> None:
    root = Path(__file__).resolve().parents[3]
    tasks = (root / ".github" / "skills" / "speckit-tasks" / "SKILL.md").read_text("utf-8")
    implement = (root / ".github" / "skills" / "speckit-implement" / "SKILL.md").read_text(
        "utf-8"
    )
    template = (root / ".specify" / "templates" / "tasks-template.md").read_text("utf-8")
    assert "Tests are OPTIONAL" not in tasks + template
    assert "acceptance and regression test" in tasks
    assert "FR-..." in tasks
    assert "do not create a subagent per task" in implement
    assert "Run final affected checks after the last relevant edit" in implement


def test_guidance_wires_grounding_and_fresh_practices_without_new_stages() -> None:
    root = Path(__file__).resolve().parents[3]
    skills = root / ".github" / "skills"
    for stage in ("specify", "clarify"):
        text = (skills / f"speckit-{stage}" / "SKILL.md").read_text("utf-8")
        assert "document-grounded" in text
        assert "confirmation" in text
        assert "gaps" in text
    clarify = (skills / "speckit-clarify" / "SKILL.md").read_text("utf-8")
    assert "only a human decision closes a question" in clarify
    for stage in ("plan", "implement"):
        text = (skills / f"speckit-{stage}" / "SKILL.md").read_text("utf-8")
        assert "codebase practices --json" in text
        assert "--project-dir <package-root>" in text
        assert "fingerprint" in text
        assert "plan.md" in text
    implement = (skills / "speckit-implement" / "SKILL.md").read_text("utf-8")
    assert "never required tests or sensors" in implement
    docs = (root / "docs" / "speckit-profiles.md").read_text("utf-8")
    assert "no stage, agent, gate or runtime dependency" in docs
    assert "not whether an LLM consistently follows" in docs


def test_context_reads_audit_once_without_caching_across_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    state.init_state(tmp_path, "quick", "human:test")
    original = Path.open
    reads = 0

    def counted(path: Path, *args: object, **kwargs: object):
        nonlocal reads
        if path.name == "audit.jsonl":
            reads += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted)
    assert main(["context", "--feature-dir", str(tmp_path), "--json"]) == 0
    assert reads == 1
    assert not json.loads(capsys.readouterr().out)["parked"]
    monkeypatch.setattr(Path, "open", original)
    audit.append_event(tmp_path, "intent_parked", None, "human:test", "pause")
    monkeypatch.setattr(Path, "open", counted)
    reads = 0
    assert main(["context", "--feature-dir", str(tmp_path), "--json"]) == 0
    assert reads == 1
    assert json.loads(capsys.readouterr().out)["parked"]


def test_plan_template_is_compact_without_losing_required_sections() -> None:
    root = Path(__file__).resolve().parents[3]
    template = (root / ".specify" / "templates" / "plan-template.md").read_bytes()
    assert len(template) <= 3682 * 0.75
    text = template.decode("utf-8")
    for section in ("Technical Context", "Constitution Check", "Project Structure", "Complexity"):
        assert section in text
    for artifact in ("research.md", "data-model.md", "quickstart.md", "contracts/"):
        assert artifact in text
    assert "quick" in text
    assert "Option 1" not in text
