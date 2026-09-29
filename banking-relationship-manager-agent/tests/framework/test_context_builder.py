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
