from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from speckit_flow import audit
from speckit_flow.models import Finding, FlowError, Review

REVIEWS_DIR = "reviews"
_ID_RE = re.compile(r"^([a-z]+)-(\d+)$")


def _resolve(feature_dir: Path, rel: str) -> Path | None:
    """Resolve a reviewed path against the feature dir, then the project root."""
    candidate = Path(rel)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise FlowError(f"reviewed path must be relative without '..': {rel!r}")
    for base in (feature_dir, feature_dir.parent.parent):
        path = base / candidate
        if path.is_file():
            return path
    return None


def fingerprint(feature_dir: Path, rel: str) -> str:
    path = _resolve(feature_dir, rel)
    if path is None:
        raise FlowError(f"reviewed file not found: {rel!r}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _review_path(feature_dir: Path, review_id: str) -> Path:
    return feature_dir / REVIEWS_DIR / f"{review_id}.json"


def _next_id(feature_dir: Path, stage: str) -> str:
    numbers = [
        int(m.group(2))
        for p in (feature_dir / REVIEWS_DIR).glob(f"{stage}-*.json")
        if (m := _ID_RE.match(p.stem)) and m.group(1) == stage
    ]
    return f"{stage}-{max(numbers, default=0) + 1}"


def build_review(feature_dir: Path, stage: str, payload: dict[str, Any]) -> Review:
    """Validate a review payload; fingerprints are always computed here, never trusted."""
    allowed = {"stage", "reviewer", "author", "verdict", "findings", "files", "id", "created_at"}
    unknown = set(payload) - allowed
    if unknown:
        raise FlowError(f"review has unknown fields: {sorted(unknown)}")
    if payload.get("stage", stage) != stage:
        raise FlowError("review stage does not match the command stage")
    raw_files = payload.get("files")
    if not isinstance(raw_files, (list, dict)) or not raw_files:
        raise FlowError("review must list the files it covers")
    files = {str(rel): fingerprint(feature_dir, str(rel)) for rel in raw_files}
    try:
        findings = tuple(Finding(**item) for item in payload.get("findings", []))
        review = Review(
            id="pending",
            stage=stage,
            reviewer=str(payload["reviewer"]),
            author=str(payload["author"]),
            verdict=str(payload["verdict"]),
            findings=findings,
            files=files,
            created_at=audit.now_iso(),
        )
    except (KeyError, TypeError) as exc:
        raise FlowError(f"review is malformed: {exc!r}") from exc
    review.validate()
    for finding in findings:
        audit.check_redaction(finding.note)
    return review


def save_review(feature_dir: Path, stage: str, payload: dict[str, Any], actor: str) -> Review:
    built = build_review(feature_dir, stage, payload)
    review = Review(
        id=_next_id(feature_dir, stage),
        stage=built.stage,
        reviewer=built.reviewer,
        author=built.author,
        verdict=built.verdict,
        findings=built.findings,
        files=built.files,
        created_at=built.created_at,
    )
    audit.append_event(
        feature_dir,
        "review_recorded",
        stage,
        actor,
        f"review={review.id} reviewer={review.reviewer} verdict={review.verdict} "
        f"findings={len(review.findings)}",
    )
    target = _review_path(feature_dir, review.id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(review.to_dict(), indent=2) + "\n", encoding="utf-8")
    return review


def load_review(feature_dir: Path, review_id: str) -> Review:
    path = _review_path(feature_dir, review_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        review = Review(
            id=data["id"],
            stage=data["stage"],
            reviewer=data["reviewer"],
            author=data["author"],
            verdict=data["verdict"],
            findings=tuple(Finding(**f) for f in data["findings"]),
            files=dict(data["files"]),
            created_at=data["created_at"],
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise FlowError(f"review {review_id} is unreadable: {exc}") from exc
    review.validate()
    return review


def list_reviews(feature_dir: Path, stage: str | None = None) -> list[Review]:
    folder = feature_dir / REVIEWS_DIR
    if not folder.is_dir():
        return []
    found: list[tuple[str, int, Review]] = []
    for path in folder.glob("*.json"):
        match = _ID_RE.match(path.stem)
        if not match or (stage and match.group(1) != stage):
            continue
        found.append((match.group(1), int(match.group(2)), load_review(feature_dir, path.stem)))
    return [r for _, _, r in sorted(found, key=lambda item: (item[0], item[1]))]


def is_stale(feature_dir: Path, review: Review) -> bool:
    for rel, digest in review.files.items():
        path = _resolve(feature_dir, rel)
        if path is None or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return True
    return False


def latest_review(feature_dir: Path, stage: str) -> Review | None:
    reviews = list_reviews(feature_dir, stage)
    return reviews[-1] if reviews else None
