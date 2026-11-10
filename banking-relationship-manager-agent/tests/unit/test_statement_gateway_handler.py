from __future__ import annotations

from typing import Any

from aria.api.gateway_handler import invoke_gateway_tool


class FakeStatementStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_authorized_statements(self, tenant_id: str, user_id: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("list_authorized_statements", {"tenant_id": tenant_id, "user_id": user_id, **kwargs}))
        return {"status": "ok", "statements": []}

    def get_statement_transactions(
        self,
        tenant_id: str,
        user_id: str,
        statement_ref: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "get_statement_transactions",
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "statement_ref": statement_ref,
                    **kwargs,
                },
            )
        )
        return {"status": "ok", "statement_ref": statement_ref, "rows": []}


def _gateway_context(tool_name: str) -> Any:
    return type(
        "Context",
        (),
        {"client_context": type("ClientContext", (), {"custom": {"bedrockAgentCoreToolName": tool_name}})()},
    )()


def test_list_statements_dispatches_verified_identity_to_store_only() -> None:
    store = FakeStatementStore()
    result = invoke_gateway_tool(
        {"arguments": {"tenant_id": "tenant-a", "user_id": "user-a"}},
        _gateway_context("aria-statements___list_authorized_statements"),
        statement_store=store,
    )

    assert result == {"status": "ok", "statements": []}
    assert store.calls == [
        (
            "list_authorized_statements",
            {"tenant_id": "tenant-a", "user_id": "user-a", "limit": 25, "page_token": None},
        )
    ]


def test_transaction_read_rejects_model_supplied_identity_fields() -> None:
    store = FakeStatementStore()
    result = invoke_gateway_tool(
        {
            "arguments": {
                "tenant_id": "tenant-a",
                "user_id": "user-a",
                "statement_ref": "stmt-opaque-001",
                "account_id": "untrusted-account",
            }
        },
        _gateway_context("aria-statements___get_statement_transactions"),
        statement_store=store,
    )

    assert result["error"] == "invalid_arguments"
    assert store.calls == []


def test_transaction_read_passes_only_declared_bounded_filters() -> None:
    store = FakeStatementStore()
    result = invoke_gateway_tool(
        {
            "arguments": {
                "tenant_id": "tenant-a",
                "user_id": "user-a",
                "statement_ref": "stmt-opaque-001",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "page_size": 10,
            }
        },
        _gateway_context("aria-statements___get_statement_transactions"),
        statement_store=store,
    )

    assert result["status"] == "ok"
    assert store.calls[0][0] == "get_statement_transactions"
    assert store.calls[0][1]["tenant_id"] == "tenant-a"
    assert store.calls[0][1]["user_id"] == "user-a"
    assert store.calls[0][1]["page_size"] == 10


def test_statement_access_denial_is_generic() -> None:
    class DeniedStore(FakeStatementStore):
        def get_statement_transactions(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise PermissionError("principal user-a is not assigned to private-account-99")

    result = invoke_gateway_tool(
        {
            "arguments": {
                "tenant_id": "tenant-a",
                "user_id": "user-a",
                "statement_ref": "stmt-opaque-001",
            }
        },
        _gateway_context("aria-statements___get_statement_transactions"),
        statement_store=DeniedStore(),
    )

    assert result == {
        "status": "error",
        "error": "statement_not_found",
        "toolName": "get_statement_transactions",
    }
    assert "private-account-99" not in str(result)
