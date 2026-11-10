from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from speckit_flow import audit, reviews, state
from speckit_flow.models import FlowError

H = "human:tester"


def _review(fdir: Path, verdict: str = "pass", stage: str = "specify") -> None:
    findings: list[dict[str, Any]] = []
    if verdict != "pass":
        sev = "blocker" if verdict == "block" else "warning"
        findings = [{"severity": sev, "file": "spec.md", "section": "Goals", "note": "issue"}]
    reviews.save_review(
        fdir,
        stage,
        {
            "reviewer": "spec",
            "author": "agent:writer",
            "verdict": verdict,
            "findings": findings,
            "files": ["spec.md"],
        },
        H,
    )


def _at_gate(tmp_path: Path, profile: str = "feature") -> Path:
    d = tmp_path / "specs" / "011-demo"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# Spec\n", encoding="utf-8")
    state.init_state(d, profile, H)
    state.start_stage(d, "specify", H)
    state.done_stage(d, "specify", H)
    return d


def _types(d: Path) -> list[str]:
    return [e.type for e in audit.read_events(d)]


def test_approval_without_review_allowed_at_standard_depth(tmp_path: Path) -> None:
    d = _at_gate(tmp_path)
    assert state.decide_gate(d, "specify", True, H).pending_gate is None


def test_approval_records_review_id(tmp_path: Path) -> None:
    d = _at_gate(tmp_path)
    _review(d)
    state.decide_gate(d, "specify", True, H)
    approved = [e for e in audit.read_events(d) if e.type == "gate_approved"][0]
    assert "review=specify-1" in approved.detail


def test_block_review_refuses_approval(tmp_path: Path) -> None:
    d = _at_gate(tmp_path)
    _review(d, "block")
    with pytest.raises(FlowError, match="override-reason"):
        state.decide_gate(d, "specify", True, H)
    assert state.load_state(d).pending_gate == "specify"


def test_block_review_override_is_audited_and_human_only(tmp_path: Path) -> None:
    d = _at_gate(tmp_path)
    _review(d, "block")
    with pytest.raises(FlowError, match="human"):
        state.decide_gate(d, "specify", True, "agent:bot", override_reason="because")
    state.decide_gate(d, "specify", True, H, override_reason="accepted risk")
    types = _types(d)
    assert types.index("gate_overridden") < types.index("gate_approved")


def test_reject_ignores_block_review(tmp_path: Path) -> None:
    d = _at_gate(tmp_path)
    _review(d, "block")
    assert state.decide_gate(d, "specify", False, H, "needs work").pending_gate is None


def test_comprehensive_requires_current_review(tmp_path: Path) -> None:
    d = _at_gate(tmp_path, "enterprise")
    with pytest.raises(FlowError, match="missing"):
        state.decide_gate(d, "specify", True, H)
    _review(d)
    (d / "spec.md").write_text("edited", encoding="utf-8")
    with pytest.raises(FlowError, match="stale"):
        state.decide_gate(d, "specify", True, H)
    _review(d)
    state.decide_gate(d, "specify", True, H)


def test_stale_block_review_does_not_block_at_standard(tmp_path: Path) -> None:
    d = _at_gate(tmp_path)
    _review(d, "block")
    (d / "spec.md").write_text("fixed", encoding="utf-8")
    state.decide_gate(d, "specify", True, H)
