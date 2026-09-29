from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GatewayClient:
    client_id: str
    scopes: list[str]
    timeout_seconds: int = 30

    def authorize(self, required_scope: str) -> bool:
        return required_scope in self.scopes

    def filter_tools(self, tools: list[Any], allowed_names: set[str]) -> list[Any]:
        return [
            tool
            for tool in tools
            if (getattr(tool, "name", None) in allowed_names or tool.get("name") in allowed_names)
        ]
