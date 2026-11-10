from aria.framework.context import ContextBuilder
from aria.framework.memory import MemoryEntry, MemoryStore


def test_context_builder_prefers_current_workflow_state_over_memory():
    builder = ContextBuilder()
    store = MemoryStore(
        entries=[
            MemoryEntry(key="risk_appetite", value="conservative", tenant_id="tenant-a"),
            MemoryEntry(key="segment", value="retail", tenant_id="tenant-a"),
        ]
    )

    context = builder.build_context(
        tenant_id="tenant-a",
        workflow_state={"risk_appetite": "moderate", "segment": "premier"},
        memory_store=store,
        user_message="I want a product recommendation.",
    )

    assert context["current_workflow_state"]["risk_appetite"] == "moderate"
    assert context["current_workflow_state"]["segment"] == "premier"
    assert "I want a product recommendation." in context["user_message"]


def test_context_builder_redacts_sensitive_values_and_provides_fallback_text():
    builder = ContextBuilder()
    context = builder.build_context(
        tenant_id="tenant-z",
        workflow_state={"client_id": "CUST-1", "password": "secret-123"},
        memory_store=MemoryStore(entries=[]),
        user_message="My password is secret-123",
    )

    assert context["fallback_text"]
    assert "secret-123" not in str(context)


def test_context_builder_exposes_memory_without_overriding_current_state():
    context = ContextBuilder().build_context(
        tenant_id="tenant-a",
        workflow_state={"risk_appetite": "moderate"},
        memory_store=MemoryStore(
            entries=[
                MemoryEntry(
                    key="risk_appetite",
                    value="conservative",
                    tenant_id="tenant-a",
                ),
                MemoryEntry(key="preference", value="concise", tenant_id="tenant-a"),
            ]
        ),
        user_message="Continue.",
    )

    assert context["current_workflow_state"]["risk_appetite"] == "moderate"
    assert context["memory"]["risk_appetite"] == "moderate"
    assert context["memory"]["preference"] == "concise"


def test_context_builder_accepts_remote_adapter_records_in_normalized_shape():
    from aria.framework.agentcore import AgentCoreMemoryAdapter

    class RemoteMemoryClient:
        def retrieve(self, tenant_id: str, limit: int, query: str) -> list[dict[str, str]]:
            return [{"key": "preference", "value": "concise", "tenant_id": tenant_id}][:limit]

        def add(self, tenant_id: str, key: str, value: str) -> None:
            raise NotImplementedError

        def delete(self, tenant_id: str, key: str | None = None) -> int:
            raise NotImplementedError

    context = ContextBuilder().build_context(
        tenant_id="tenant-a",
        workflow_state={},
        memory_store=AgentCoreMemoryAdapter(client=RemoteMemoryClient()),
        user_message="Continue.",
    )

    assert context["history"] == ["concise"]
    assert context["memory"] == {"preference": "concise"}


def test_context_builder_accepts_an_absent_memory_backend():
    context = ContextBuilder().build_context(
        tenant_id="tenant-a",
        workflow_state={"step": "collect-goal"},
        memory_store=None,
        user_message="Continue.",
    )

    assert context["history"] == []
    assert context["memory"] == {"step": "collect-goal"}
    assert context["fallback_text"]
