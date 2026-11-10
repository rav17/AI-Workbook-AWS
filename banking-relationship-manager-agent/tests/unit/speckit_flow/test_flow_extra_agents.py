from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from speckit_flow import agents as ag
from speckit_flow.models import FlowError

REAL = ag.DEFAULT_ROSTER_FILE


def _setup(tmp_path: Path) -> Path:
    roster = tmp_path / "agents" / "roster.json"
    roster.parent.mkdir(parents=True)
    shutil.copy(REAL, roster)
    return tmp_path


def _agent(agent_id: str, **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": agent_id,
        "role": "domain",
        "tier": "balanced",
        "file": f".github/agents/speckit-{agent_id}.agent.md",
        "leads": [],
        "supports": ["plan"],
        "can_edit": False,
    }
    base.update(over)
    return base


def _write(path: Path, *items: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"agents": list(items)}), encoding="utf-8")


def test_custom_agent_is_added_with_source(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    _write(root / "custom" / "agents.json", _agent("risk"))
    roster = ag.load_roster(root / "agents" / "roster.json")
    assert roster["risk"].source == "custom"
    assert roster["product"].source == "core"


def test_plugin_agent_is_added(tmp_path: Path) -> None:
    root = _setup(tmp_path)
    plug = root / "plugins" / "sec"
    plug.mkdir(parents=True)
    (plug / "plugin.json").write_text(json.dumps({"name": "sec", "version": "1"}), encoding="utf-8")
    _write(plug / "agents.json", _agent("pentest"))
    assert ag.load_roster(root / "agents" / "roster.json")["pentest"].source == "plugin:sec"


@pytest.mark.parametrize(
    "item",
    [
        _agent("product"),
        _agent("lead2", leads=["plan"], supports=[]),
        _agent("rev2", role="reviewer"),
    ],
)
def test_extras_cannot_override_or_lead(tmp_path: Path, item: dict[str, object]) -> None:
    root = _setup(tmp_path)
    _write(root / "custom" / "agents.json", item)
    with pytest.raises(FlowError):
        ag.load_roster(root / "agents" / "roster.json")


def test_core_validation_ignores_extras() -> None:
    roster = ag.load_roster()
    extra = ag.Agent("zed", "domain", "balanced", "x", (), ("plan",), False, "custom")
    problems = ag.validate_roster({**roster, "zed": extra})
    assert not any("expected" in p for p in problems)
