from aria.framework.config import FrameworkConfig, load_framework_config
from aria.framework.contracts import ParsedTurn
from aria.framework.gateway import GatewayClient
from aria.framework.memory import MemoryEntry, MemoryStore


def test_framework_config_has_safe_defaults():
    config = load_framework_config()

    assert isinstance(config, FrameworkConfig)
    assert config.max_tool_calls > 0
    assert config.max_context_tokens > 0


def test_framework_config_loads_environment_overrides_and_rejects_invalid_limits():
    config = load_framework_config(
        environ={
            "ARIA_RUNTIME_SESSION_TTL_SECONDS": "900",
            "ARIA_MAX_CONTEXT_TOKENS": "2000",
            "ARIA_MAX_TOOL_CALLS": "4",
            "ARIA_ENVIRONMENT": "test",
        }
    )

    assert config.environment == "test"
    assert config.max_context_tokens == 2000

    try:
        load_framework_config(overrides={"max_tool_calls": 0})
    except ValueError as exc:
        assert "max_tool_calls" in str(exc)
    else:
        raise AssertionError("invalid framework limits must fail closed")


def test_gateway_client_filters_tools_by_scope():
    gateway = GatewayClient(client_id="client-1", scopes=["crm.read", "risk.read"])
    tools = [{"name": "crm_tool"}, {"name": "admin_tool"}]

    filtered = gateway.filter_tools(tools, {"crm_tool"})
    assert [tool["name"] for tool in filtered] == ["crm_tool"]


def test_memory_store_is_scoped_and_bounded():
    store = MemoryStore(
        entries=[
            MemoryEntry(key="pref", value="likes concise answers", tenant_id="tenant-a"),
            MemoryEntry(key="pref2", value="wants tax help", tenant_id="tenant-b"),
        ]
    )

    result = store.retrieve("tenant-a", limit=5)
    assert len(result) == 1
    assert result[0].tenant_id == "tenant-a"


def test_parsed_turn_tracks_session_and_payload():
    turn = ParsedTurn(
        user_id="u-1",
        session_id="sess-1",
        payload={"message": "hello"},
        workflow_state={"risk_appetite": "moderate"},
    )

    assert turn.session_id == "sess-1"
    assert turn.workflow_state["risk_appetite"] == "moderate"
