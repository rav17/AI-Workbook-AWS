import json
from dataclasses import dataclass
from io import BytesIO

from aria.framework.agentcore import (
    AgentCoreGatewayAdapter,
    AgentCoreMemoryAdapter,
    AgentCoreMemoryDataPlaneClient,
    AgentCoreRuntimeAdapter,
    AgentCoreRuntimeClient,
)
from aria.framework.memory import MemoryEntry, MemoryStore
from aria.session.manager import SessionManager


class FakeRuntimeClient:
    def create_or_recover_session(self, session_id: str) -> str:
        return f"runtime:{session_id}"


class FakeMemoryClient:
    def __init__(self) -> None:
        self.entries: list[tuple[str, str, str]] = []

    def retrieve(self, tenant_id: str, limit: int, query: str) -> list[dict[str, str]]:
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


class SemanticGatewayTransport:
    def discover_tools(self, query: str, scopes: list[str]) -> list[dict[str, object]]:
        return [
            {
                "name": "crm.profile.read",
                "description": "Read a client profile and account context",
                "capabilities": ["crm.read"],
            },
            {
                "name": "admin.delete",
                "description": "Delete a client record",
                "capabilities": ["admin.write"],
            },
        ]

    def authorize(self, tool_name: str, scopes: list[str]) -> bool:
        return tool_name == "crm.profile.read" and "crm.read" in scopes


def test_runtime_adapter_reuses_and_recovers_runtime_session():
    adapter = AgentCoreRuntimeAdapter(SessionManager(), FakeRuntimeClient())

    first = adapter.resolve("tenant-a", "user-a")
    second = adapter.resolve("tenant-a", "user-a")

    assert first.runtime_session_id == "runtime:tenant-a:user-a:default"
    assert second.runtime_session_id == first.runtime_session_id
    assert second.revision == first.revision


def test_runtime_client_invokes_scoped_runtime_with_verified_principal():
    class FakeRuntimeDataPlane:
        def invoke_agent_runtime(self, **kwargs):
            self.request = kwargs
            return {
                "statusCode": 200,
                "response": BytesIO(b'{"status":"processed","response":"hello"}'),
            }

    fake = FakeRuntimeDataPlane()
    client = AgentCoreRuntimeClient(runtime_arn="runtime-arn", client=fake)

    result = client.invoke(
        {
            "prompt": "hello",
            "conversation_id": "conversation-1",
            "_verified_principal": {"tenant_id": "attacker", "user_id": "attacker"},
        },
        runtime_session_id="a" * 64,
        tenant_id="tenant-1",
        user_id="user-1",
    )

    request = fake.request
    assert request["agentRuntimeArn"] == "runtime-arn"
    assert request["runtimeSessionId"] == "a" * 64
    assert len(request["runtimeUserId"]) == 64
    assert json.loads(request["payload"])["_verified_principal"] == {
        "tenant_id": "tenant-1",
        "user_id": "user-1",
    }
    assert result["response"] == "hello"


def test_memory_adapter_bounds_provider_retrieval_and_preserves_tenant_scope():
    client = FakeMemoryClient()
    adapter = AgentCoreMemoryAdapter(client=client, max_items=2)
    adapter.add("tenant-a", "one", "1")
    adapter.add("tenant-a", "two", "2")
    adapter.add("tenant-a", "three", "3")
    adapter.add("tenant-b", "other", "x")

    result = adapter.retrieve("tenant-a", limit=20)

    assert len(result) == 2
    assert all(entry.tenant_id == "tenant-a" for entry in result)


def test_memory_adapter_rejects_invalid_or_cross_tenant_remote_records():
    import pytest

    class FakeRemoteClient:
        def __init__(self, records: list[dict[str, str]]) -> None:
            self.records = records

        def retrieve(self, tenant_id: str, limit: int, query: str) -> list[dict[str, str]]:
            return self.records

        def add(self, tenant_id: str, key: str, value: str) -> None:
            raise NotImplementedError

        def delete(self, tenant_id: str, key: str | None = None) -> int:
            raise NotImplementedError

    for record, error in (
        ({"key": "preference", "tenant_id": "tenant-a"}, ValueError),
        (
            {"key": "preference", "value": "private", "tenant_id": "tenant-b"},
            PermissionError,
        ),
    ):
        adapter = AgentCoreMemoryAdapter(client=FakeRemoteClient([record]))
        with pytest.raises(error):
            adapter.retrieve("tenant-a")


def test_memory_adapter_does_not_delete_locally_when_remote_delete_is_unsupported():
    import pytest

    class RemoteClientWithoutDelete:
        def retrieve(self, tenant_id: str, limit: int, query: str) -> list[dict[str, str]]:
            return []

        def add(self, tenant_id: str, key: str, value: str) -> None:
            raise NotImplementedError

    store = MemoryStore(entries=[MemoryEntry(key="local", value="keep", tenant_id="tenant-a")])
    adapter = AgentCoreMemoryAdapter(client=RemoteClientWithoutDelete(), local_store=store)

    with pytest.raises(RuntimeError, match="does not support deletion"):
        adapter.delete("tenant-a", "local")

    assert [entry.key for entry in store.retrieve("tenant-a")] == ["local"]


def test_agentcore_memory_data_plane_scopes_retrieval_to_authenticated_tenant():
    class FakeDataPlane:
        def retrieve_memory_records(self, **kwargs):
            self.request = kwargs
            return {
                "memoryRecordSummaries": [
                    {
                        "memoryRecordId": "mem-record1",
                        "content": {"text": "prefers concise answers"},
                        "namespaces": [client.namespace_path + "facts"],
                    }
                ]
            }

    fake = FakeDataPlane()
    client = AgentCoreMemoryDataPlaneClient(
        memory_id="aria-memory-1234567890",
        tenant_id="tenant-a",
        user_id="user-a",
        session_id="session-a",
        client=fake,
    )

    result = client.retrieve("tenant-a", 50, "communication preference")

    assert result[0]["value"] == "prefers concise answers"
    assert fake.request["maxResults"] == 5
    assert fake.request["searchCriteria"]["topK"] == 5
    assert fake.request["searchCriteria"]["searchQuery"] == "communication preference"
    assert fake.request["namespacePath"].startswith("/tenants/")


def test_agentcore_memory_data_plane_writes_tenant_variable_and_rejects_other_tenant():
    class FakeDataPlane:
        def create_event(self, **kwargs):
            self.request = kwargs

    fake = FakeDataPlane()
    client = AgentCoreMemoryDataPlaneClient(
        memory_id="aria-memory-1234567890",
        tenant_id="tenant-a",
        user_id="user-a",
        session_id="session-a",
        client=fake,
    )

    import pytest

    with pytest.raises(PermissionError, match="writes are disabled"):
        client.add("tenant-a", "preference", "prefers concise answers")

    assert not hasattr(fake, "request")
    with pytest.raises(PermissionError, match="tenant"):
        client.add("tenant-b", "preference", "must not cross tenants")


def test_agentcore_memory_data_plane_deletes_all_actor_records_across_pages():
    class FakeDataPlane:
        def __init__(self):
            self.list_calls = []
            self.delete_calls = []

        def list_memory_records(self, **kwargs):
            self.list_calls.append(kwargs)
            if "nextToken" not in kwargs:
                return {
                    "memoryRecordSummaries": [
                        {
                            "memoryRecordId": "mem-record000000000000000000000000000000000001",
                            "namespaces": [client.namespace_path + "facts"],
                        }
                    ],
                    "nextToken": "next-page",
                }
            return {
                "memoryRecordSummaries": [
                    {
                        "memoryRecordId": "mem-record000000000000000000000000000000000002",
                        "namespaces": [client.namespace_path + "summaries/session-a"],
                    }
                ]
            }

        def delete_memory_record(self, **kwargs):
            self.delete_calls.append(kwargs)

    fake = FakeDataPlane()
    client = AgentCoreMemoryDataPlaneClient(
        memory_id="aria-memory-1234567890",
        tenant_id="tenant-a",
        user_id="user-a",
        session_id="session-a",
        client=fake,
    )

    deleted = client.delete_all_for_user("tenant-a")

    assert deleted == 2
    assert len(fake.list_calls) == 2
    assert fake.list_calls[0]["namespacePath"] == client.namespace_path.rstrip("/")
    assert fake.list_calls[0]["maxResults"] == 100
    assert fake.list_calls[1]["nextToken"] == "next-page"
    assert [call["memoryRecordId"] for call in fake.delete_calls] == [
        "mem-record000000000000000000000000000000000001",
        "mem-record000000000000000000000000000000000002",
    ]


def test_agentcore_memory_user_erasure_fails_incomplete_for_out_of_scope_record():
    import pytest

    class FakeDataPlane:
        def list_memory_records(self, **kwargs):
            return {
                "memoryRecordSummaries": [
                    {
                        "memoryRecordId": "mem-record000000000000000000000000000000000001",
                        "namespaces": ["/tenants/other/users/other/facts"],
                    }
                ]
            }

        def delete_memory_record(self, **kwargs):
            raise AssertionError("out-of-scope Memory record must not be deleted")

    client = AgentCoreMemoryDataPlaneClient(
        memory_id="aria-memory-1234567890",
        tenant_id="tenant-a",
        user_id="user-a",
        session_id="session-a",
        client=FakeDataPlane(),
    )

    with pytest.raises(ValueError, match="outside the authenticated user namespace"):
        client.delete_all_for_user("tenant-a")


def test_agentcore_memory_user_erasure_propagates_delete_failure():
    import pytest

    class FakeDataPlane:
        def list_memory_records(self, **kwargs):
            return {
                "memoryRecordSummaries": [
                    {
                        "memoryRecordId": "mem-record000000000000000000000000000000000001",
                        "namespaces": [client.namespace_path + "facts"],
                    }
                ]
            }

        def delete_memory_record(self, **kwargs):
            raise RuntimeError("provider delete failed")

    client = AgentCoreMemoryDataPlaneClient(
        memory_id="aria-memory-1234567890",
        tenant_id="tenant-a",
        user_id="user-a",
        session_id="session-a",
        client=FakeDataPlane(),
    )

    with pytest.raises(RuntimeError, match="provider delete failed"):
        client.delete_all_for_user("tenant-a")


def test_agentcore_memory_data_plane_requires_record_id_for_delete():
    client = AgentCoreMemoryDataPlaneClient(
        memory_id="aria-memory-1234567890",
        tenant_id="tenant-a",
        user_id="user-a",
        session_id="session-a",
        client=object(),
    )

    try:
        client.delete("tenant-a")
    except ValueError as exc:
        assert "record ID" in str(exc)
    else:
        raise AssertionError("unscoped Memory deletion must be rejected")


def test_memory_adapter_supports_tenant_scoped_delete_and_retention():
    from datetime import UTC, datetime, timedelta

    store = MemoryStore(
        entries=[
            MemoryEntry(
                key="expired",
                value="old",
                tenant_id="tenant-a",
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            ),
            MemoryEntry(key="live", value="current", tenant_id="tenant-a"),
            MemoryEntry(key="other", value="keep", tenant_id="tenant-b"),
        ]
    )
    adapter = AgentCoreMemoryAdapter(local_store=store, max_items=5)

    result = adapter.retrieve("tenant-a")
    deleted = adapter.delete("tenant-a", "live")

    assert [entry.key for entry in result] == ["live"]
    assert deleted == 1
    assert [entry.key for entry in adapter.retrieve("tenant-a")] == []
    assert [entry.key for entry in adapter.retrieve("tenant-b")] == ["other"]


def test_gateway_adapter_filters_discovered_tools_through_authorization():
    adapter = AgentCoreGatewayAdapter(FakeGatewayTransport(), ["crm.read"])

    result = adapter.discover_authorized("client profile")

    assert [tool.name for tool in result] == ["crm.read"]


def test_gateway_adapter_semantic_discovery_applies_capability_and_backend_auth():
    adapter = AgentCoreGatewayAdapter(SemanticGatewayTransport(), ["crm.read"])

    result = adapter.discover_semantic_authorized(
        "client profile",
        capability_filter={"crm.read"},
    )

    assert [tool["name"] for tool in result] == ["crm.profile.read"]


def test_gateway_mcp_url_validates_identifiers_and_builds_documented_endpoint():
    import pytest

    from aria.framework.gateway import gateway_mcp_url

    assert gateway_mcp_url("gateway_123", "us-east-1") == (
        "https://gateway_123.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
    )
    with pytest.raises(ValueError, match="Gateway ID"):
        gateway_mcp_url("https://attacker.example", "us-east-1")


def test_gateway_sigv4_auth_signs_for_agentcore_service():
    import httpx
    from botocore.credentials import Credentials

    from aria.framework.gateway import AgentCoreGatewaySigV4Auth

    class FakeSession:
        def get_credentials(self):
            return Credentials("access-key", "secret-key", "session-token")

    request = httpx.Request(
        "POST",
        "https://gateway.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
        headers={"content-type": "application/json"},
        content=b"{}",
    )
    signed_request = next(AgentCoreGatewaySigV4Auth("us-east-1", FakeSession()).auth_flow(request))

    assert "AWS4-HMAC-SHA256" in signed_request.headers["authorization"]
    assert "/us-east-1/bedrock-agentcore/aws4_request" in signed_request.headers["authorization"]
    assert signed_request.headers["x-amz-security-token"] == "session-token"


def test_runtime_gateway_tool_filter_keeps_only_allowlisted_name():
    from aria.framework.gateway import filter_allowed_gateway_tools

    tools = [
        {"name": "aria-messages___get_risk_questionnaire"},
        {"name": "aria-messages___handle_client_message"},
    ]

    assert filter_allowed_gateway_tools(tools) == [tools[0]]


def test_gateway_lambda_adapter_allows_only_published_tools():
    from aria.api.gateway_handler import invoke_gateway_tool

    class FakeAgent:
        def execute_tool(self, name, payload):
            return {"tool": name, "payload": payload}

    allowed = invoke_gateway_tool(
        {
            "toolName": "get_risk_questionnaire",
            "arguments": {},
        },
        agent=FakeAgent(),
    )
    denied = invoke_gateway_tool(
        {"toolName": "handle_client_message", "arguments": {}}, agent=FakeAgent()
    )

    assert allowed["tool"] == "get_risk_questionnaire"
    assert denied == {
        "status": "error",
        "error": "tool_not_allowed",
        "toolName": "handle_client_message",
    }


def test_gateway_lambda_uses_agentcore_tool_name_from_lambda_context():
    from types import SimpleNamespace

    from aria.api.gateway_handler import invoke_gateway_tool

    class FakeAgent:
        def execute_tool(self, name, payload):
            return ["questionnaire"]

    context = SimpleNamespace(
        client_context=SimpleNamespace(
            custom={"bedrockAgentCoreToolName": "aria-messages___get_risk_questionnaire"}
        )
    )
    result = invoke_gateway_tool({"arguments": {}}, context, FakeAgent())

    assert result == {"result": ["questionnaire"]}


def test_gateway_lambda_rejects_arguments_and_blocks_sensitive_results():
    from aria.api.gateway_handler import invoke_gateway_tool

    class FakeAgent:
        def __init__(self, result):
            self.result = result
            self.calls = 0

        def execute_tool(self, name, payload):
            self.calls += 1
            assert name == "get_risk_questionnaire"
            assert payload == {}
            return self.result

    invalid_arguments_agent = FakeAgent(["not called"])
    invalid_arguments = invoke_gateway_tool(
        {
            "toolName": "get_risk_questionnaire",
            "arguments": {"client_id": "caller-controlled"},
        },
        agent=invalid_arguments_agent,
    )
    sensitive_result = invoke_gateway_tool(
        {"toolName": "get_risk_questionnaire", "arguments": {}},
        agent=FakeAgent({"result": "PIN is 1234"}),
    )

    assert invalid_arguments["error"] == "invalid_arguments"
    assert invalid_arguments_agent.calls == 0
    assert sensitive_result == {
        "status": "error",
        "error": "tool_result_blocked",
        "toolName": "get_risk_questionnaire",
    }
