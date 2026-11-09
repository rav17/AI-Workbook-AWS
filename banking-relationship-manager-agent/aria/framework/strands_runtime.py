from __future__ import annotations

from pathlib import Path

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel
from strands.session import FileSessionManager


def build_strands_agent(
    *,
    agent_id: str,
    session_id: str,
    model_id: str,
    region_name: str,
    session_dir: str | Path,
    system_prompt: str | None = None,
    context_window_messages: int = 40,
    tools: list[object] | None = None,
) -> Agent:
    """Build a Strands Agent without invoking the model during construction."""
    model = BedrockModel(model_id=model_id, region_name=region_name)
    conversation_manager = SlidingWindowConversationManager(
        window_size=context_window_messages,
        should_truncate_results=True,
        per_turn=True,
    )
    session_manager = FileSessionManager(
        session_id=session_id,
        storage_dir=str(Path(session_dir)),
    )
    return Agent(
        model=model,
        tools=tools or [],
        system_prompt=system_prompt,
        conversation_manager=conversation_manager,
        session_manager=session_manager,
        agent_id=agent_id,
    )


def cancel_strands_agent(agent: Agent) -> None:
    """Request cancellation through the installed Strands Agent API."""
    agent.cancel()
