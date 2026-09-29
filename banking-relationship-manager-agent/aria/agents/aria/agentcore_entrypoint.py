from __future__ import annotations

from aria.agent import AriaAgent


def main(payload: dict, state: dict | None = None) -> dict:
    agent = AriaAgent()
    return agent.handle_client_message(payload, state or {})
