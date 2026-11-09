from __future__ import annotations

import os
from typing import Any

from aria.api.lambda_entry import invoke_agent
from aria.api.runtime_session import RuntimeSessionCoordinator
from aria.framework.agentcore import AgentCoreRuntimeAdapter, AgentCoreRuntimeClient
from aria.persistence.store import IdempotencyStore
from aria.session.manager import SessionManager


def _is_authenticated(event: dict[str, Any]) -> bool:
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    if not isinstance(authorizer, dict):
        return False

    claims = authorizer.get("claims") or {}
    if not isinstance(claims, dict):
        return False

    tenant_claim = os.environ.get("TENANT_CLAIM_NAME", "custom:tenant_id")
    subject = claims.get("sub") or authorizer.get("sub")
    tenant_id = claims.get(tenant_claim) or claims.get("tenant_id") or authorizer.get("tenant_id")
    return bool(subject and tenant_id)


def _idempotency_key(event: dict[str, Any]) -> str | None:
    headers = event.get("headers") or {}
    if not isinstance(headers, dict):
        return None
    value = next(
        (
            header_value
            for name, header_value in headers.items()
            if isinstance(name, str) and name.lower() == "idempotency-key"
        ),
        None,
    )
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError("Idempotency-Key must contain 1 to 256 characters")
    return value.strip()


def _build_runtime_coordinator() -> tuple[RuntimeSessionCoordinator, AgentCoreRuntimeClient]:
    table_name = os.environ.get("SESSION_TABLE_NAME")
    runtime_arn_parameter = os.environ.get("AGENTCORE_RUNTIME_ARN_PARAMETER")
    if not table_name:
        raise RuntimeError("SESSION_TABLE_NAME is required for durable client sessions")
    if not runtime_arn_parameter:
        raise RuntimeError("AGENTCORE_RUNTIME_ARN_PARAMETER is required for Runtime invocation")

    boto3 = __import__("boto3")
    runtime_arn = boto3.client("ssm").get_parameter(Name=runtime_arn_parameter)["Parameter"][
        "Value"
    ]
    table = boto3.resource("dynamodb").Table(table_name)
    runtime_client = AgentCoreRuntimeClient(runtime_arn=runtime_arn)
    coordinator = RuntimeSessionCoordinator(
        AgentCoreRuntimeAdapter(SessionManager(table=table), client=runtime_client),
        IdempotencyStore.from_environment(),
    )
    return coordinator, runtime_client


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    del context
    if not _is_authenticated(event):
        return {
            "statusCode": 401,
            "body": '{"error":"unauthorized"}',
            "headers": {"content-type": "application/json"},
        }

    coordinator, runtime_client = _build_runtime_coordinator()
    return invoke_agent(
        event,
        lambda payload, _state: coordinator.run(
            event,
            payload,
            lambda runtime_session, _session_state: runtime_client.invoke(
                payload,
                runtime_session_id=runtime_session.runtime_session_id,
                tenant_id=runtime_session.tenant_id,
                user_id=runtime_session.user_id,
            ),
            idempotency_key=_idempotency_key(event),
        ),
    )
