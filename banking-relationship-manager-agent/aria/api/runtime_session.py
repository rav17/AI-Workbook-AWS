from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from aria.framework.agentcore import AgentCoreRuntimeAdapter
from aria.persistence.store import IdempotencyStore


class RuntimeSessionBusy(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class RuntimeSessionCoordinator:
    def __init__(
        self,
        runtime_adapter: AgentCoreRuntimeAdapter,
        idempotency_store: IdempotencyStore | None = None,
    ) -> None:
        self.runtime_adapter = runtime_adapter
        self.idempotency_store = idempotency_store or IdempotencyStore()

    def _identity(
        self,
        event: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[str, str, str]:
        request_context = event.get("requestContext") or {}
        authorizer = request_context.get("authorizer") or {}
        claims = authorizer.get("claims", {}) if isinstance(authorizer, dict) else {}
        if not isinstance(claims, dict):
            claims = {}
        tenant_claim = os.environ.get("TENANT_CLAIM_NAME", "custom:tenant_id")
        tenant_id = (
            claims.get(tenant_claim)
            or claims.get("tenant_id")
            or (authorizer.get("tenant_id") if isinstance(authorizer, dict) else None)
        )
        user_id = claims.get("sub") or (
            authorizer.get("sub") if isinstance(authorizer, dict) else None
        )
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ValueError("authenticated tenant claim is required")
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("authenticated subject claim is required")
        conversation_id = payload.get("conversation_id", "default")
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise ValueError("conversation_id must be a non-empty string")
        if len(conversation_id) > 128:
            raise ValueError("conversation_id exceeds the 128 character limit")
        return tenant_id, user_id, conversation_id

    def run(
        self,
        event: dict[str, Any],
        payload: dict[str, Any],
        callback: Callable[[Any, dict[str, Any]], dict[str, Any]],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        tenant_id, user_id, conversation_id = self._identity(event, payload)
        scoped_key: str | None = None
        claimed = False
        if idempotency_key is not None:
            if not idempotency_key.strip() or len(idempotency_key) > 256:
                raise ValueError("Idempotency-Key must contain 1 to 256 characters")
            scoped_key = f"{user_id}:{conversation_id}:{idempotency_key}"
            claimed = self.idempotency_store.claim(tenant_id, scoped_key)
            if not claimed:
                raise IdempotencyConflict("duplicate_request")

        try:
            runtime_session = self.runtime_adapter.resolve(tenant_id, user_id, conversation_id)
        except Exception:
            if claimed and scoped_key is not None:
                self.idempotency_store.release(tenant_id, scoped_key)
            raise
        if not self.runtime_adapter.acquire(runtime_session):
            if claimed and scoped_key is not None:
                self.idempotency_store.release(tenant_id, scoped_key)
            raise RuntimeSessionBusy("runtime_session_busy")
        completed = False
        try:
            session = self.runtime_adapter.session_manager.get_session(runtime_session.session_id)
            session_state = dict(session.get("state", {}))
            result = callback(runtime_session, session_state)
            if claimed and scoped_key is not None:
                self.idempotency_store.mark_completed(tenant_id, scoped_key)
                completed = True
            revision = runtime_session.revision
            if session_state != session.get("state", {}):
                if not self.runtime_adapter.session_manager.update_session_state(
                    runtime_session.session_id,
                    session_state,
                    expected_revision=runtime_session.revision,
                ):
                    raise RuntimeSessionBusy("runtime_session_revision_conflict")
                revision += 1
            return {
                **result,
                "session_id": runtime_session.session_id,
                "runtime_session_id": runtime_session.runtime_session_id,
                "runtime_revision": revision,
            }
        except Exception:
            if claimed and not completed and scoped_key is not None:
                self.idempotency_store.release(tenant_id, scoped_key)
            raise
        finally:
            self.runtime_adapter.release(runtime_session)
