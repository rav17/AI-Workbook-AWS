"""Unit tests for the HighMemoryUsage playbook and its mapping."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest
import yaml

from src.executor import RemediationExecutor

pytestmark = pytest.mark.unit

PLAYBOOK = "playbooks/fix_high_memory.yml"
MAPPING = "config/playbook_mapping.yml"


def _commands() -> list[str]:
    return RemediationExecutor()._extract_commands_from_playbook(PLAYBOOK)


def test_memory_pressure_rule_maps_to_fix_high_memory() -> None:
    """HighMemoryUsage must map to the memory playbook, and the file must exist."""
    with open(MAPPING, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh)["rules"]
    rule = next(r for r in rules if r["name"] == "memory-pressure")
    assert rule["conditions"] == {"alert_name": "HighMemoryUsage"}
    assert rule["playbook_path"] == PLAYBOOK
    assert os.path.isfile(PLAYBOOK)


def test_playbook_commands_are_extractable_and_not_templated() -> None:
    """The executor runs only shell tasks and does not render Jinja."""
    commands = _commands()
    script = "\n".join(commands)
    assert len(commands) > 4
    assert "{{" not in script
    assert "pkill -TERM '^stress-ng'" in script
    # Matching by process name (no -f) cannot hit the shell running the script.
    assert "pkill -f" not in script


def test_playbook_never_targets_root_or_protected_processes() -> None:
    """The generic fallback must skip root-owned and critical processes."""
    script = "\n".join(_commands())
    assert '$2 != "root"' in script
    for protected in ("systemd", "sshd", "amazon-ssm-agen"):
        assert protected in script


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_generated_script_has_valid_bash_syntax() -> None:
    """The combined script must parse as bash."""
    script = "\n".join(_commands())
    # Pass bytes: text mode would turn "\n" into "\r\n" on Windows and break "\" continuations.
    result = subprocess.run(
        ["bash", "-n"], input=script.encode("utf-8"), capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
