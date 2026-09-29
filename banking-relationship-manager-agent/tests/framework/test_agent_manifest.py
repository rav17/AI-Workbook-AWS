from pathlib import Path

import yaml

from aria.agents.aria.system_prompt import build_system_prompt


def test_agent_manifest_is_valid_and_parsable():
    path = Path("aria/agents/aria/agent.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert data["name"] == "aria"
    assert data["runtime"]["mode"] == "sync"
    assert "crm_tool" in data["allowed_tools"]


def test_system_prompt_builds_nonempty_prompt():
    prompt = build_system_prompt()

    assert isinstance(prompt, str)
    assert len(prompt) > 20
    assert "safe" in prompt.lower()
