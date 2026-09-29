from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aria.framework.contracts import GatewayTransport, MemoryClient, RuntimeClient
from aria.framework.memory import MemoryEntry, MemoryStore
from aria.session.manager import SessionManager


@dataclass(frozen=True)
class RuntimeSession:
    session_id: str
    tenant_id: str
    user_id: str
    runtime_session_id: str
    revision: int


class AgentCoreRuntimeAdapter:
    """Maps an authenticated conversation to one recoverable Runtime session."""

    def __init__(
        self,
        session_manager: SessionManager,
        client: RuntimeClient | None = None,
    ) -> None:
        self.session_manager = session_manager
        self.client = client

    def resolve(self, tenant_id: str, user_id: str) -> RuntimeSession:
        session = self.session_manager.start_session(tenant_id, user_id)
        runtime_session_id = session["state"].get("runtime_session_id")
        if not runtime_session_id:
            runtime_session_id = self._create_or_recover(session["session_id"])
            updated = self.session_manager.update_session_state(
                session["session_id"],
                {"runtime_session_id": runtime_session_id},
                expected_revision=session["revision"],
            )
            if not updated:
                session = self.session_manager.get_session(session["session_id"])
                runtime_session_id = session["state"].get(
                    "runtime_session_id", runtime_session_id
                )
            else:
                session = self.session_manager.get_session(session["session_id"])

        return RuntimeSession(
            session_id=session["session_id"],
            tenant_id=tenant_id,
            user_id=user_id,
            runtime_session_id=runtime_session_id,
            revision=session["revision"],
        )

    def _create_or_recover(self, session_id: str) -> str:
        if self.client is None:
            return session_id
        return self.client.create_or_recover_session(session_id)

    def acquire(self, runtime_session: RuntimeSession) -> bool:
        return self.session_manager.lock_session(runtime_session.session_id)

    def release(self, runtime_session: RuntimeSession) -> None:
        self.session_manager.release_session(runtime_session.session_id)


class AgentCoreMemoryAdapter:
    """Applies tenant and retrieval bounds around an AgentCore Memory client."""

    def __init__(
        self,
        client: MemoryClient | None = None,
        local_store: MemoryStore | None = None,
        max_items: int = 5,
    ) -> None:
        self.client = client
        self.local_store = local_store or MemoryStore()
        self.max_items = max(1, max_items)

    def retrieve(self, tenant_id: str, limit: int | None = None) -> list[Any]:
        bounded_limit = min(max(1, limit or self.max_items), self.max_items)
        if self.client is not None:
            return self.client.retrieve(tenant_id, bounded_limit)
        return self.local_store.retrieve(tenant_id, bounded_limit)

    def add(self, tenant_id: str, key: str, value: str) -> None:
        if self.client is not None:
            self.client.add(tenant_id, key, value)
            return
        self.local_store.add(MemoryEntry(key=key, value=value, tenant_id=tenant_id))


class AgentCoreGatewayAdapter:
    """Separates Gateway discovery/tool visibility from authorization."""

    def __init__(self, transport: GatewayTransport, scopes: list[str]) -> None:
        self.transport = transport
        self.scopes = list(scopes)

    def discover(self, query: str) -> list[Any]:
        return self.transport.discover_tools(query, self.scopes)

    def authorize(self, tool_name: str) -> bool:
        return self.transport.authorize(tool_name, self.scopes)

    def discover_authorized(self, query: str) -> list[Any]:
        tools = self.discover(query)
        return [
            tool
            for tool in tools
            if self.authorize(self._tool_name(tool))
        ]

    @staticmethod
    def _tool_name(tool: Any) -> str:
        if isinstance(tool, dict):
            return str(tool.get("name", ""))
        return str(getattr(tool, "name", ""))