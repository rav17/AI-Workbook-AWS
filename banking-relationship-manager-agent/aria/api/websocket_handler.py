from __future__ import annotations

from typing import Any

from aria.api.lambda_entry import invoke_agent
from aria.api.rest_handler import _build_runtime_coordinator, _idempotency_key
from aria.api.rest_handler import _is_authenticated as _is_api_authenticated


def _is_authenticated(event: dict[str, Any]) -> bool:
    return _is_api_authenticated(event)


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
