"""Unit tests for the synth-time playbook catalog used by the findings Lambda."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agentic_ai.infra.constructs.advisory_context import (
    CONTEXT_FILENAME,
    build_advisory_context,
    write_advisory_context,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "playbooks").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "playbooks" / "fix_cpu.yml").write_text(
        "---\n# Fix CPU \u2014 kills hogs.\n# Second line.\n"
        "- name: Fix high CPU\n  hosts: all\n  tasks:\n"
        "    - name: Kill stress-ng\n      ansible.builtin.shell: pkill stress-ng\n"
        "    - ansible.builtin.debug:\n        msg: no name\n",
        encoding="utf-8",
    )
    (tmp_path / "playbooks" / "a_notes.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / "config" / "playbook_mapping.yml").write_text(
        "rules:\n"
        "  - name: a\n    conditions: {alert_name: HighCPUUsage}\n"
        "    playbook_path: playbooks/fix_cpu.yml\n"
        "  - name: b\n    conditions: {alert_name: HighCPUUsage, service_name: web}\n"
        "    playbook_path: playbooks/fix_cpu.yml\n"
        "  - name: c\n    conditions: {alert_name: CPUSaturation}\n"
        "    playbook_path: playbooks\\fix_cpu.yml\n",
        encoding="utf-8",
    )
    (tmp_path / "config" / "denied_commands.yml").write_text(
        "denied_patterns:\n  - pattern: 'dd\\s+if='\n    reason: Raw disk write\n"
        "  - pattern: ''\n    reason: empty\n",
        encoding="utf-8",
    )
    return tmp_path


def test_describes_each_playbook(tmp_path) -> None:
    context = build_advisory_context(_repo(tmp_path))

    (playbook,) = context["playbooks"]
    assert playbook["path"] == "playbooks/fix_cpu.yml"
    assert playbook["summary"] == "Fix high CPU"
    assert playbook["tasks"] == ["Kill stress-ng"]  # unnamed tasks are skipped
    assert playbook["alerts"] == [
        "HighCPUUsage",
        "CPUSaturation",
    ]  # deduped, \ normalised
    assert playbook["description"].startswith("Fix CPU")
    assert "Second line." in playbook["description"]
    assert playbook["description"].isascii()


def test_denied_patterns_are_copied_and_empty_ones_skipped(tmp_path) -> None:
    context = build_advisory_context(_repo(tmp_path))
    assert context["denied_patterns"] == [
        {"pattern": "dd\\s+if=", "reason": "Raw disk write"}
    ]


def test_missing_config_files_give_empty_sections(tmp_path) -> None:
    (tmp_path / "playbooks").mkdir()
    assert build_advisory_context(tmp_path) == {"playbooks": [], "denied_patterns": []}


def test_write_is_idempotent(tmp_path) -> None:
    (tmp_path / "repo").mkdir()
    repo = _repo(tmp_path / "repo")
    out = tmp_path / "out"
    out.mkdir()
    target = write_advisory_context(repo, out)
    assert target.name == CONTEXT_FILENAME
    first = target.stat().st_mtime_ns
    write_advisory_context(repo, out)
    assert target.stat().st_mtime_ns == first
    assert json.loads(target.read_text(encoding="utf-8"))["playbooks"]


def test_real_repository_playbooks_and_alert_mapping() -> None:
    context = build_advisory_context(REPO_ROOT)
    by_path = {p["path"]: p for p in context["playbooks"]}

    on_disk = {f"playbooks/{p.name}" for p in (REPO_ROOT / "playbooks").glob("*.yml")}
    assert set(by_path) == on_disk
    assert by_path["playbooks/fix_high_memory.yml"]["alerts"] == ["HighMemoryUsage"]
    assert by_path["playbooks/fix_high_memory.yml"]["tasks"]
    assert any("rm" in p["pattern"] for p in context["denied_patterns"])
