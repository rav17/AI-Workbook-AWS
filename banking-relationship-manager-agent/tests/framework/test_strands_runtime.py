from pathlib import Path

from strands import Agent, tool
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.session import FileSessionManager

from aria.agent import AriaAgent
from aria.framework.strands_runtime import build_strands_agent, cancel_strands_agent


def test_build_strands_agent_uses_pinned_runtime_apis(tmp_path: Path):
    agent = build_strands_agent(
        agent_id="aria",
        session_id="session-1",
        model_id="amazon.nova-lite-v1:0",
        region_name="us-east-1",
        session_dir=tmp_path,
        context_window_messages=12,
    )

    assert isinstance(agent, Agent)
    assert isinstance(agent.conversation_manager, SlidingWindowConversationManager)
    assert isinstance(agent._session_manager, FileSessionManager)
    assert agent.agent_id == "aria"

    cancel_strands_agent(agent)


def test_aria_agent_exposes_strands_runtime_builder(tmp_path: Path):
    @tool
    def ping_client(client_id: str) -> str:
        """Return a test client acknowledgement."""
        return client_id

    agent = AriaAgent().build_runtime_agent(
        agent_id="aria",
        session_id="session-2",
        model_id="amazon.nova-lite-v1:0",
        region_name="us-east-1",
        session_dir=str(tmp_path),
        tools=[ping_client],
    )

    assert isinstance(agent, Agent)
    assert agent.tool_names == ["ping_client"]
