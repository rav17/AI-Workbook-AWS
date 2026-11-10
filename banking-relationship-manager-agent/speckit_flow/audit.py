from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from speckit_flow.models import AuditEvent, FlowError

AUDIT_FILE = "audit.jsonl"

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}"),
    re.compile(r"\b\d{9,}\b"),
    re.compile(r"(?:password|secret|token|api[_-]?key)\s*[=:]\s*\S+", re.IGNORECASE),
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def check_redaction(text: str) -> None:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise FlowError("event detail looks like it contains a secret or customer data")


def _last_line(path: Path) -> str | None:
    if not path.exists():
        return None
    last: str | None = None
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            if raw.strip():
                last = raw.rstrip("\n")
    return last


def append_event(
    feature_dir: Path, event_type: str, stage: str | None, actor: str, detail: str
) -> AuditEvent:
    """Append one event; the file is only ever opened in append mode."""
    path = feature_dir / AUDIT_FILE
    last = _last_line(path)
    if last is None:
        seq, prev_hash = 1, ""
    else:
        try:
            seq = int(json.loads(last)["seq"]) + 1
        except (ValueError, KeyError, TypeError) as exc:
            raise FlowError(f"{AUDIT_FILE} is corrupt: last line is unreadable") from exc
        prev_hash = line_hash(last)
    event = AuditEvent(seq, now_iso(), event_type, stage, actor, detail, prev_hash)
    event.validate()
    check_redaction(detail)
    line = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
    try:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
    except OSError as exc:
        raise FlowError(f"cannot write {AUDIT_FILE}: {exc}") from exc
    return event


def read_events(feature_dir: Path) -> list[AuditEvent]:
    path = feature_dir / AUDIT_FILE
    if not path.exists():
        return []
    events: list[AuditEvent] = []
    with path.open("r", encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            if not raw.strip():
                continue
            try:
                events.append(AuditEvent(**json.loads(raw)))
            except (ValueError, TypeError) as exc:
                raise FlowError(f"{AUDIT_FILE} line {number} is unreadable") from exc
    return events


def is_parked(feature_dir: Path) -> bool:
    """A feature is parked when its latest park/resume event is a park."""
    parked = False
    for event in read_events(feature_dir):
        if event.type == "intent_parked":
            parked = True
        elif event.type == "intent_resumed":
            parked = False
    return parked


def verify_chain(feature_dir: Path) -> str | None:
    """Return a description of the first broken line, or None when the chain is intact."""
    path = feature_dir / AUDIT_FILE
    if not path.exists():
        return None
    prev_line: str | None = None
    expected_seq = 1
    with path.open("r", encoding="utf-8") as handle:
        for number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                seq, prev_hash = int(data["seq"]), data["prev_hash"]
            except (ValueError, KeyError, TypeError):
                return f"line {number}: unreadable event"
            if seq != expected_seq:
                return f"line {number}: expected seq {expected_seq}, found {seq}"
            expected = "" if prev_line is None else line_hash(prev_line)
            if prev_hash != expected:
                return f"line {number}: hash chain broken (an earlier line was modified)"
            prev_line = line
            expected_seq += 1
    return None
