from __future__ import annotations

from typing import Any

from aria.agent import AriaAgent
from aria.api.lambda_entry import invoke_agent


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    del context
    agent = AriaAgent()
    return invoke_agent(event, agent.handle_client_message)
