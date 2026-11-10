from __future__ import annotations

from pathlib import Path

import pytest

from speckit_flow import audit, rules
from speckit_flow.knowledge import list_knowledge
from speckit_flow.models import FlowError

H = "human:tester"


@pytest.fixture
def env(tmp_path: Path) -> tuple[Path, Path]:
    fdir = tmp_path / "011-demo"
    fdir.mkdir()
    return fdir, tmp_path / "rules.json"


def test_propose_is_pending_and_audited(env: tuple[Path, Path]) -> None:
    fdir, path = env
    rule = rules.propose_rule(
        fdir, "Always log decisions", "agent:bot", from_gate="plan", path=path
    )
    assert (rule.id, rule.status, rule.origin) == ("R-001", "pending", "gate:011-demo:plan")
    assert audit.read_events(fdir)[-1].type == "rule_proposed"
    assert rules.list_rules(path, stage="plan")["rules"] == []


def test_agent_cannot_approve(env: tuple[Path, Path]) -> None:
    fdir, path = env
    rules.propose_rule(fdir, "Keep it short", "agent:bot", path=path)
    with pytest.raises(FlowError, match="human"):
        rules.decide_rule(fdir, "R-001", True, "agent:bot", path)


def test_approve_activates_and_lists_for_stage(env: tuple[Path, Path]) -> None:
    fdir, path = env
    rules.propose_rule(fdir, "Mask account ids", H, from_gate="plan", path=path)
    rules.propose_rule(fdir, "Write docstrings", H, from_gate="tasks", path=path)
    rules.decide_rule(fdir, "R-001", True, H, path)
    rules.decide_rule(fdir, "R-002", True, H, path)
    shown = rules.list_rules(path, stage="plan")["rules"]
    assert [r["id"] for r in shown] == ["R-001"]


def test_transitions(env: tuple[Path, Path]) -> None:
    fdir, path = env
    rules.propose_rule(fdir, "Rule one", H, path=path)
    rules.decide_rule(fdir, "R-001", False, H, path)
    with pytest.raises(FlowError, match="cannot move"):
        rules.decide_rule(fdir, "R-001", True, H, path)
    with pytest.raises(FlowError, match="unknown rule"):
        rules.decide_rule(fdir, "R-099", True, H, path)


def test_text_limits_and_redaction(env: tuple[Path, Path]) -> None:
    fdir, path = env
    with pytest.raises(FlowError):
        rules.propose_rule(fdir, "x" * 301, H, path=path)
    with pytest.raises(FlowError):
        rules.propose_rule(fdir, " ", H, path=path)
    with pytest.raises(FlowError):
        rules.propose_rule(fdir, "use token=abcdef123456", H, path=path)
    assert not path.exists()


def test_stage_list_capped_at_ten_newest(env: tuple[Path, Path]) -> None:
    fdir, path = env
    for i in range(12):
        rules.propose_rule(fdir, f"Rule number {i}", H, path=path)
        rules.decide_rule(fdir, f"R-{i + 1:03d}", True, H, path)
    result = rules.list_rules(path, stage="plan")
    assert len(result["rules"]) == 10
    assert result["omitted"] == 2
    assert result["rules"][-1]["id"] == "R-012"


def test_conflicts_flagged(env: tuple[Path, Path]) -> None:
    fdir, path = env
    rules.propose_rule(fdir, "Use retries on calls", H, path=path)
    rules.propose_rule(fdir, "Do not use retries on calls", H, path=path)
    for rid in ("R-001", "R-002"):
        rules.decide_rule(fdir, rid, True, H, path)
    shown = rules.list_rules(path, stage="plan")["rules"]
    assert all(r["conflict"] for r in shown)


def test_finding_origin_validated(env: tuple[Path, Path]) -> None:
    fdir, path = env
    with pytest.raises(FlowError, match="from-finding"):
        rules.propose_rule(fdir, "A rule", H, from_finding="bad", path=path)
    rule = rules.propose_rule(fdir, "A rule", H, from_finding="plan-1:2", path=path)
    assert rule.origin == "finding:011-demo:plan-1:2"
    rules.decide_rule(fdir, rule.id, True, H, path)
    assert rules.list_rules(path, stage="plan")["rules"]
    assert not rules.list_rules(path, stage="tasks")["rules"]


def test_knowledge_titles_and_stage_filter(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("title: Alpha\nstages: plan, implement\nbody", encoding="utf-8")
    (tmp_path / "b.md").write_text("no header", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    docs = {d.path: d for d in list_knowledge(None, tmp_path)}
    assert set(docs) == {"a.md", "b.md"}
    assert docs["a.md"].title == "Alpha" and docs["b.md"].title == "b"
    assert docs["b.md"].stages == ("all",)
    assert [d.path for d in list_knowledge("tasks", tmp_path)] == ["b.md"]
    assert list_knowledge("plan", tmp_path / "missing") == []
