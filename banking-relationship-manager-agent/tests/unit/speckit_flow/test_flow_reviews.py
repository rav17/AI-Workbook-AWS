from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from speckit_flow import audit, reviews, state
from speckit_flow.models import FlowError

H = "human:tester"
AUTHOR = "agent:writer"


@pytest.fixture
def fdir(tmp_path: Path) -> Path:
    d = tmp_path / "specs" / "011-demo"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# Spec\n\n## Goals\ntext\n", encoding="utf-8")
    return d


def _payload(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "reviewer": "spec",
        "author": AUTHOR,
        "verdict": "pass",
        "findings": [],
        "files": ["spec.md"],
    }
    base.update(over)
    return base


def _finding(severity: str = "warning", **over: Any) -> dict[str, Any]:
    base = {"severity": severity, "file": "spec.md", "section": "Goals", "note": "unclear goal"}
    base.update(over)
    return base


def test_pass_review_saved_with_fingerprint_and_audit(fdir: Path) -> None:
    review = reviews.save_review(fdir, "specify", _payload(), H)
    assert review.id == "specify-1"
    assert len(review.files["spec.md"]) == 64
    assert (fdir / "reviews" / "specify-1.json").exists()
    assert audit.read_events(fdir)[-1].type == "review_recorded"


def test_ids_increment_per_stage(fdir: Path) -> None:
    reviews.save_review(fdir, "specify", _payload(), H)
    second = reviews.save_review(fdir, "specify", _payload(), H)
    other = reviews.save_review(fdir, "plan", _payload(), H)
    assert (second.id, other.id) == ("specify-2", "plan-1")


def test_blocker_requires_block_verdict(fdir: Path) -> None:
    bad = _payload(verdict="concerns", findings=[_finding("blocker")])
    with pytest.raises(FlowError, match="forces verdict"):
        reviews.save_review(fdir, "specify", bad, H)
    ok = _payload(verdict="block", findings=[_finding("blocker")])
    assert reviews.save_review(fdir, "specify", ok, H).verdict == "block"


def test_pass_invalid_with_major(fdir: Path) -> None:
    with pytest.raises(FlowError, match="invalid with major"):
        reviews.save_review(fdir, "specify", _payload(findings=[_finding("major")]), H)


def test_empty_findings_only_for_pass(fdir: Path) -> None:
    with pytest.raises(FlowError, match="empty only"):
        reviews.save_review(fdir, "specify", _payload(verdict="concerns"), H)


def test_reviewer_must_differ_from_author(fdir: Path) -> None:
    with pytest.raises(FlowError, match="differ"):
        reviews.save_review(fdir, "specify", _payload(author="agent:spec"), H)


@pytest.mark.parametrize(
    "finding",
    [
        _finding(file="other.md"),
        _finding(section=" "),
        _finding(note="x" * 501),
        _finding(note="password=hunter2hunter2"),
    ],
)
def test_bad_findings_rejected(fdir: Path, finding: dict[str, Any]) -> None:
    with pytest.raises(FlowError):
        reviews.save_review(fdir, "specify", _payload(verdict="concerns", findings=[finding]), H)


def test_paths_must_exist_and_stay_relative(fdir: Path) -> None:
    with pytest.raises(FlowError, match="not found"):
        reviews.save_review(fdir, "specify", _payload(files=["missing.md"]), H)
    with pytest.raises(FlowError, match="relative"):
        reviews.save_review(fdir, "specify", _payload(files=["../x.md"]), H)


def test_review_becomes_stale_when_file_changes(fdir: Path) -> None:
    review = reviews.save_review(fdir, "specify", _payload(), H)
    assert not reviews.is_stale(fdir, review)
    (fdir / "spec.md").write_text("changed", encoding="utf-8")
    assert reviews.is_stale(fdir, review)
    assert reviews.latest_review(fdir, "specify") == reviews.load_review(fdir, "specify-1")


def test_failed_save_leaves_no_file(fdir: Path) -> None:
    with pytest.raises(FlowError):
        reviews.save_review(fdir, "specify", _payload(reviewer="nobody"), H)
    assert not (fdir / "reviews").exists()


def test_list_reviews_orders_numerically(fdir: Path) -> None:
    for _ in range(11):
        reviews.save_review(fdir, "specify", _payload(), H)
    assert reviews.list_reviews(fdir, "specify")[-1].id == "specify-11"
    assert reviews.list_reviews(fdir, "plan") == []


def test_state_unaffected_by_reviews(fdir: Path) -> None:
    state.init_state(fdir, "feature", H)
    reviews.save_review(fdir, "specify", _payload(), H)
    assert state.load_state(fdir).current_stage == "specify"
    assert audit.verify_chain(fdir) is None
