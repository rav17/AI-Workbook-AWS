from pathlib import Path

import yaml

from aria.agents.framework_smoke.agentcore_entrypoint import main


def test_smoke_agent_manifest_is_valid():
    path = Path("aria/agents/framework_smoke/agent.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert data["name"] == "framework_smoke"
    assert data["runtime"]["mode"] == "sync"


def test_smoke_agent_entrypoint_runs_and_returns_state():
    result = main({"name": "Aisha"}, {"segment": "premier"})

    assert result["status"] == "ok"
    assert "Aisha" in result["response"]
    assert result["state"]["segment"] == "premier"
