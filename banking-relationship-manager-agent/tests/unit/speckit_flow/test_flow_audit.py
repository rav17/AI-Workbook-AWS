from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow import audit
from speckit_flow.cli import main
from speckit_flow.models import FlowError

A = "agent:test"


def test_seq_and_hash_chain(tmp_path: Path) -> None:
    e1 = audit.append_event(tmp_path, "stage_started", "specify", A, "go")
    e2 = audit.append_event(tmp_path, "stage_completed", "specify", A, "ok")
    assert (e1.seq, e2.seq) == (1, 2)
    assert e1.prev_hash == ""
    first = (tmp_path / "audit.jsonl").read_text("utf-8").splitlines()[0]
    assert e2.prev_hash == audit.line_hash(first)
    assert audit.verify_chain(tmp_path) is None


def test_existing_lines_never_modified(tmp_path: Path) -> None:
    audit.append_event(tmp_path, "stage_started", "specify", A, "go")
    before = (tmp_path / "audit.jsonl").read_bytes()
    audit.append_event(tmp_path, "stage_completed", "specify", A, "ok")
    assert (tmp_path / "audit.jsonl").read_bytes().startswith(before)


def test_tamper_detected(tmp_path: Path) -> None:
    for i in range(3):
        audit.append_event(tmp_path, "stage_started", "specify", A, f"n{i}")
    path = tmp_path / "audit.jsonl"
    lines = path.read_text("utf-8").splitlines()
    data = json.loads(lines[1])
    data["detail"] = "changed"
    lines[1] = json.dumps(data, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert "line 3" in (audit.verify_chain(tmp_path) or "")


def test_deleted_line_detected(tmp_path: Path) -> None:
    for i in range(3):
        audit.append_event(tmp_path, "stage_started", "specify", A, f"n{i}")
    path = tmp_path / "audit.jsonl"
    lines = path.read_text("utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    assert audit.verify_chain(tmp_path) is not None


@pytest.mark.parametrize(
    "detail",
    [
        "key AKIAABCDEFGHIJKLMNOP",
        "Authorization: Bearer abcdef123456",
        "a" * 8 + "0123456789abcdef" * 3,
        "account 123456789012",
        "password=hunter2",
    ],
)
def test_secret_like_detail_rejected(tmp_path: Path, detail: str) -> None:
    with pytest.raises(FlowError, match="secret"):
        audit.append_event(tmp_path, "failure", None, A, detail)
    assert not (tmp_path / "audit.jsonl").exists()


def test_bad_actor_and_type_rejected(tmp_path: Path) -> None:
    with pytest.raises(FlowError, match="actor"):
        audit.append_event(tmp_path, "failure", None, "bob", "x")
    with pytest.raises(FlowError, match="event type"):
        audit.append_event(tmp_path, "nope", None, A, "x")


def test_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    d = tmp_path / "011-cli"
    d.mkdir()
    base = [
        "--feature-dir",
        str(d),
        "--actor",
        "human:test",
        "--sensors-file",
        str(tmp_path / "none.json"),
    ]
    assert main(["init", "--profile", "express", *base]) == 0
    assert main(["stage", "start", "specify", *base]) == 0
    assert main(["stage", "done", "specify", *base]) == 0
    assert main(["gate", "approve", "specify", *base]) == 0
    assert main(["status", *base, "--json"]) == 0
    out = capsys.readouterr().out
    assert '"next_stage": "tasks"' in out
    assert main(["init", "--profile", "nope", "--feature-dir", str(tmp_path)]) == 1
    assert main(["profiles", "validate"]) == 0
    assert main(["profiles", "suggest", "fix a bug"]) == 0
