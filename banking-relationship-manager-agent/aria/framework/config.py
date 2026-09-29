from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True)
class FrameworkConfig:
    runtime_session_ttl_seconds: int = 1800
    max_context_tokens: int = 4000
    max_tool_calls: int = 8
    environment: str = "dev"

    def __post_init__(self) -> None:
        if self.runtime_session_ttl_seconds <= 0:
            raise ValueError("runtime_session_ttl_seconds must be positive")
        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        if not self.environment:
            raise ValueError("environment must not be empty")


def load_framework_config(
    overrides: dict[str, Any] | None = None,
    environ: dict[str, str] | None = None,
) -> FrameworkConfig:
    source = environ if environ is not None else os.environ
    config: dict[str, Any] = dict(
        runtime_session_ttl_seconds=int(source.get("ARIA_RUNTIME_SESSION_TTL_SECONDS", "1800")),
        max_context_tokens=int(source.get("ARIA_MAX_CONTEXT_TOKENS", "4000")),
        max_tool_calls=int(source.get("ARIA_MAX_TOOL_CALLS", "8")),
        environment=source.get("ARIA_ENVIRONMENT", "dev"),
    )
    if overrides:
        config.update(overrides)
    return FrameworkConfig(
        runtime_session_ttl_seconds=cast(int, config["runtime_session_ttl_seconds"]),
        max_context_tokens=cast(int, config["max_context_tokens"]),
        max_tool_calls=cast(int, config["max_tool_calls"]),
        environment=cast(str, config["environment"]),
    )
