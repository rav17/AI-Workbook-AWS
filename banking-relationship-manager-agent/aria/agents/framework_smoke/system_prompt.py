from __future__ import annotations


def build_system_prompt() -> str:
    return (
        "You are a minimal smoke-test agent used to validate the framework contract. "
        "Keep responses short, safe, and deterministic."
    )
