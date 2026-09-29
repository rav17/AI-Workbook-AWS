from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PromptBuilder(Protocol):
    def build(self, *args: Any, **kwargs: Any) -> str: ...


@runtime_checkable
class PayloadParser(Protocol):
    def parse(self, payload: dict[str, Any]) -> Any: ...


@runtime_checkable
class ToolFilter(Protocol):
    def filter(self, tools: list[Any], context: dict[str, Any]) -> list[Any]: ...


@runtime_checkable
class PreInvocationGuard(Protocol):
    def validate(self, payload: dict[str, Any]) -> bool: ...


@runtime_checkable
class RuntimeClient(Protocol):
    def create_or_recover_session(self, session_id: str) -> str: ...


@runtime_checkable
class MemoryClient(Protocol):
    def retrieve(self, tenant_id: str, limit: int) -> list[dict[str, Any]]: ...

    def add(self, tenant_id: str, key: str, value: str) -> None: ...


@runtime_checkable
class GatewayTransport(Protocol):
    def discover_tools(self, query: str, scopes: list[str]) -> list[Any]: ...

    def authorize(self, tool_name: str, scopes: list[str]) -> bool: ...


@dataclass
class ParsedTurn:
    user_id: str
    session_id: str
    payload: dict[str, Any]
    workflow_state: dict[str, Any]
