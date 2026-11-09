from __future__ import annotations

import json
import os
from typing import Any

from aria.agent import AriaAgent
from aria.guardrails.processor import GuardrailProcessor
from aria.persistence.statement_store import StatementAccessDenied, StatementReadStore

ALLOWED_GATEWAY_TOOLS = frozenset(
    {
        "get_risk_questionnaire",
        "list_authorized_statements",
        "get_statement_transactions",
    }
)
TOOL_REQUIRED_ARGUMENT_KEYS: dict[str, frozenset[str]] = {
    "get_risk_questionnaire": frozenset(),
    "list_authorized_statements": frozenset({"tenant_id", "user_id"}),
    "get_statement_transactions": frozenset({"tenant_id", "user_id", "statement_ref"}),
}
TOOL_OPTIONAL_ARGUMENT_KEYS: dict[str, frozenset[str]] = {
    "get_risk_questionnaire": frozenset(),
    "list_authorized_statements": frozenset({"limit", "page_token"}),
    "get_statement_transactions": frozenset(
        {"start_date", "end_date", "page_size", "page_token", "trans_id"}
    ),
}
_TRUSTED_IDENTITY_KEYS = frozenset({"tenant_id", "user_id"})
_MAX_GATEWAY_PAGE_SIZE = 25
MAX_TOOL_PAYLOAD_BYTES = 16 * 1024


def _serialized_payload(value: Any) -> str | None:
    try:
        serialized = json.dumps(value, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        return None
    if len(serialized.encode("utf-8")) > MAX_TOOL_PAYLOAD_BYTES:
        return None
    return serialized


def _statement_store_from_environment() -> StatementReadStore:
    entitlement_table_name = os.environ.get("STATEMENT_ENTITLEMENTS_TABLE")
    transaction_table_name = os.environ.get("STATEMENT_TRANSACTIONS_TABLE")
    if not entitlement_table_name or not transaction_table_name:
        raise RuntimeError("Statement Gateway table configuration is unavailable")
    boto3 = __import__("boto3")
    dynamodb = boto3.resource("dynamodb")
    return StatementReadStore(
        entitlements_table=dynamodb.Table(entitlement_table_name),
        transactions_table=dynamodb.Table(transaction_table_name),
    )


def invoke_gateway_tool(
    event: dict[str, Any],
    context: Any = None,
    agent: AriaAgent | None = None,
    guardrails: GuardrailProcessor | None = None,
    statement_store: StatementReadStore | None = None,
) -> dict[str, Any]:
    client_context = getattr(context, "client_context", None)
    custom_context = getattr(client_context, "custom", None)
    context_tool_name = (
        custom_context.get("bedrockAgentCoreToolName") if isinstance(custom_context, dict) else None
    )
    tool_name = str(event.get("toolName") or event.get("name") or context_tool_name or "")
    if "___" in tool_name:
        tool_name = tool_name.rsplit("___", maxsplit=1)[-1]
    if tool_name not in ALLOWED_GATEWAY_TOOLS:
        return {
            "status": "error",
            "error": "tool_not_allowed",
            "toolName": tool_name,
        }

    if "arguments" in event:
        arguments = event["arguments"]
    elif "input" in event:
        arguments = event["input"]
    else:
        arguments = event
    if not isinstance(arguments, dict):
        return {"status": "error", "error": "invalid_arguments", "toolName": tool_name}
    required_keys = TOOL_REQUIRED_ARGUMENT_KEYS[tool_name]
    allowed_keys = required_keys | TOOL_OPTIONAL_ARGUMENT_KEYS[tool_name]
    if not required_keys.issubset(arguments) or not set(arguments).issubset(allowed_keys):
        return {"status": "error", "error": "invalid_arguments", "toolName": tool_name}

    guardrail_arguments = {
        key: value for key, value in arguments.items() if key not in _TRUSTED_IDENTITY_KEYS
    }
    serialized_arguments = _serialized_payload(guardrail_arguments)
    if serialized_arguments is None:
        return {"status": "error", "error": "invalid_arguments", "toolName": tool_name}

    processor = guardrails or GuardrailProcessor()
    input_result = processor.process_input(serialized_arguments)
    if input_result.blocked:
        return {"status": "error", "error": "tool_input_blocked", "toolName": tool_name}

    try:
        if tool_name == "list_authorized_statements":
            store = statement_store or _statement_store_from_environment()
            result = store.list_authorized_statements(
                str(arguments["tenant_id"]),
                str(arguments["user_id"]),
                limit=int(arguments.get("limit", 25)),
                page_token=arguments.get("page_token"),
            )
        elif tool_name == "get_statement_transactions":
            page_size = int(arguments.get("page_size", _MAX_GATEWAY_PAGE_SIZE))
            if not 1 <= page_size <= _MAX_GATEWAY_PAGE_SIZE:
                return {"status": "error", "error": "invalid_arguments", "toolName": tool_name}
            store = statement_store or _statement_store_from_environment()
            result = store.get_statement_transactions(
                str(arguments["tenant_id"]),
                str(arguments["user_id"]),
                str(arguments["statement_ref"]),
                start_date=arguments.get("start_date"),
                end_date=arguments.get("end_date"),
                page_size=page_size,
                page_token=arguments.get("page_token"),
                trans_id=arguments.get("trans_id"),
            )
        else:
            result = (agent or AriaAgent()).execute_tool(tool_name, arguments)
        serialized_result = _serialized_payload(result)
        if serialized_result is None:
            return {"status": "error", "error": "invalid_tool_result", "toolName": tool_name}
        output_result = processor.process_output(serialized_result)
        if output_result.blocked:
            return {"status": "error", "error": "tool_result_blocked", "toolName": tool_name}
        sanitized_result = json.loads(output_result.sanitized_message)
        if isinstance(sanitized_result, dict):
            return sanitized_result
        return {"result": sanitized_result}
    except (StatementAccessDenied, PermissionError):
        return {
            "status": "error",
            "error": "statement_not_found",
            "toolName": tool_name,
        }
    except ValueError:
        return {"status": "error", "error": "invalid_arguments", "toolName": tool_name}
    except Exception:
        error_code = "statement_backend_unavailable" if tool_name.startswith("statement_") or tool_name == "list_authorized_statements" else "tool_execution_failed"
        return {"status": "error", "error": error_code, "toolName": tool_name}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    return invoke_gateway_tool(event, context)
