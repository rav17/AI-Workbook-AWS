from dataclasses import dataclass

from aria.framework.agentcore import (
    AgentCoreGatewayAdapter,
    AgentCoreMemoryAdapter,
    AgentCoreRuntimeAdapter,
)
from aria.session.manager import SessionManager


class FakeRuntimeClient:
    def create_or_recover_session(self, session_id: str) -> str:
        return f"runtime:{session_id}"


class FakeMemoryClient:
    def __init__(self) -> None:
        self.entries: list[tuple[str, str, str]] = []

    def retrieve(self, tenant_id: str, limit: int) -> list[dict[str, str]]:
        return [
            {"tenant_id": tenant, "key": key, "value": value}
            for tenant, key, value in self.entries
            if tenant == tenant_id
        ][:limit]

    def add(self, tenant_id: str, key: str, value: str) -> None:
        self.entries.append((tenant_id, key, value))


@dataclass
class Tool:
    name: str


class FakeGatewayTransport:
    def discover_tools(self, query: str, scopes: list[str]) -> list[Tool]:
        return [Tool("crm.read"), Tool("admin.delete")]

    def authorize(self, tool_name: str, scopes: list[str]) -> bool:
        return tool_name in scopes


def test_runtime_adapter_reuses_and_recovers_runtime_session():
    adapter = AgentCoreRuntimeAdapter(SessionManager(), FakeRuntimeClient())

    first = adapter.resolve("tenant-a", "user-a")
    second = adapter.resolve("tenant-a", "user-a")

    assert first.runtime_session_id == "runtime:tenant-a:user-a"
    assert second.runtime_session_id == first.runtime_session_id
    assert second.revision == first.revision


def test_memory_adapter_bounds_provider_retrieval_and_preserves_tenant_scope():
    client = FakeMemoryClient()
    adapter = AgentCoreMemoryAdapter(client=client, max_items=2)
    adapter.add("tenant-a", "one", "1")
    adapter.add("tenant-a", "two", "2")
    adapter.add("tenant-a", "three", "3")
    adapter.add("tenant-b", "other", "x")

    result = adapter.retrieve("tenant-a", limit=20)

    assert len(result) == 2
    assert all(entry["tenant_id"] == "tenant-a" for entry in result)


def test_gateway_adapter_filters_discovered_tools_through_authorization():
    adapter = AgentCoreGatewayAdapter(FakeGatewayTransport(), ["crm.read"])

    result = adapter.discover_authorized("client profile")

    assert [tool.name for tool in result] == ["crm.read"]