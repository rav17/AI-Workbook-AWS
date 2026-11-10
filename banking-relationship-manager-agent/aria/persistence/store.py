from __future__ import annotations

import hashlib
import importlib
import json
import os
import time
import uuid
from collections.abc import Callable
from typing import Any


class StateStore:
    def __init__(self, *, idempotency_store: IdempotencyStore | None = None) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._idempotency = idempotency_store or IdempotencyStore()

    def get(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        return dict(session) if session is not None else None

    def save(self, session: dict[str, Any]) -> dict[str, Any]:
        self._sessions[session["session_id"]] = session
        return session

    def update_if_unmodified(
        self, session_id: str, updates: dict[str, Any], expected_revision: int | None
    ) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if expected_revision is not None and session.get("revision") != expected_revision:
            return False
        session["state"] = {**session.get("state", {}), **updates}
        session["revision"] = int(session.get("revision", 0)) + 1
        return True

    def apply_idempotent_update(
        self,
        session_id: str,
        updates: dict[str, Any],
        *,
        expected_revision: int | None,
        tenant_id: str,
        idempotency_key: str,
        side_effect: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            return {"applied": False, "revision": None, "reason": "missing_session"}

        current_revision = int(session.get("revision", 0))
        if expected_revision is not None and current_revision != expected_revision:
            return {
                "applied": False,
                "revision": current_revision,
                "reason": "stale_revision",
                "retryable": True,
            }

        if not self._idempotency.claim(tenant_id, idempotency_key):
            return {
                "applied": False,
                "revision": current_revision,
                "reason": "duplicate_event",
            }

        candidate = {
            **session,
            "state": {**session.get("state", {}), **updates},
            "revision": current_revision + 1,
        }
        try:
            if side_effect is not None:
                side_effect(dict(candidate))
        except Exception:
            self._idempotency.release(tenant_id, idempotency_key)
            return {
                "applied": False,
                "revision": current_revision,
                "reason": "side_effect_failed",
                "retryable": True,
            }

        self._idempotency.mark_completed(tenant_id, idempotency_key)
        self._sessions[session_id] = candidate
        return {"applied": True, "revision": candidate["revision"], "reason": "accepted"}


class IdempotencyStore:
    def __init__(
        self,
        *,
        table: Any = None,
        ttl_seconds: int | None = None,
        lease_seconds: int = 60,
    ) -> None:
        if ttl_seconds is not None and ttl_seconds < 1:
            raise ValueError("idempotency TTL must be a positive number of seconds")
        if lease_seconds < 1:
            raise ValueError("idempotency lease must be a positive number of seconds")
        self._processed: set[tuple[str, str]] = set()
        self._table = table
        self._ttl_seconds = ttl_seconds
        self._lease_seconds = lease_seconds
        self._claims: dict[tuple[str, str], str] = {}

    @classmethod
    def from_environment(cls) -> IdempotencyStore:
        table_name = os.environ.get("IDEMPOTENCY_TABLE_NAME")
        if not table_name:
            raise RuntimeError("IDEMPOTENCY_TABLE_NAME is required for durable idempotency")
        ttl_value = os.environ.get("IDEMPOTENCY_TTL_SECONDS")
        ttl_seconds = int(ttl_value) if ttl_value else None
        table = importlib.import_module("boto3").resource("dynamodb").Table(table_name)
        return cls(table=table, ttl_seconds=ttl_seconds)

    @staticmethod
    def _key(tenant_id: str, event_id: str) -> str:
        identity = json.dumps([tenant_id, event_id], separators=(",", ":"))
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_conditional_failure(error: Exception) -> bool:
        response = getattr(error, "response", {})
        return (
            isinstance(response, dict)
            and response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"
        )

    def claim(self, tenant_id: str, event_id: str) -> bool:
        if self._table is None:
            return self.mark_processed(tenant_id, event_id)
        if not tenant_id.strip() or not event_id.strip():
            raise ValueError("tenant ID and idempotency key must be non-empty")

        now = int(time.time())
        claim_id = uuid.uuid4().hex
        item: dict[str, Any] = {
            "idempotency_id": self._key(tenant_id, event_id),
            "tenant_hash": hashlib.sha256(tenant_id.encode("utf-8")).hexdigest(),
            "status": "in_progress",
            "claim_id": claim_id,
            "lease_until": now + self._lease_seconds,
        }
        if self._ttl_seconds is not None:
            item["expires_at"] = item["lease_until"] + self._ttl_seconds
            claim_condition = (
                "attribute_not_exists(idempotency_id) OR "
                "(#status = :in_progress AND lease_until < :now) OR "
                "(#status = :processed AND expires_at < :now)"
            )
        else:
            claim_condition = (
                "attribute_not_exists(idempotency_id) OR "
                "(#status = :in_progress AND lease_until < :now)"
            )
        try:
            self._table.put_item(
                Item=item,
                ConditionExpression=claim_condition,
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":in_progress": "in_progress", ":now": now},
            )
        except Exception as exc:
            if self._is_conditional_failure(exc):
                return False
            raise
        self._claims[(tenant_id, event_id)] = claim_id
        return True

    def mark_completed(self, tenant_id: str, event_id: str) -> None:
        if self._table is None:
            return
        claim_id = self._claims.get((tenant_id, event_id))
        if claim_id is None:
            raise RuntimeError("idempotency claim is not owned by this store instance")
        values: dict[str, Any] = {
            ":processed": "processed",
            ":in_progress": "in_progress",
            ":tenant_hash": hashlib.sha256(tenant_id.encode("utf-8")).hexdigest(),
            ":claim_id": claim_id,
        }
        update_expression = "SET #status = :processed REMOVE lease_until"
        if self._ttl_seconds is not None:
            values[":expires"] = int(time.time()) + self._ttl_seconds
            update_expression = "SET #status = :processed, expires_at = :expires REMOVE lease_until"
        try:
            self._table.update_item(
                Key={"idempotency_id": self._key(tenant_id, event_id)},
                UpdateExpression=update_expression,
                ConditionExpression=(
                    "#status = :in_progress AND tenant_hash = :tenant_hash AND claim_id = :claim_id"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=values,
            )
        except Exception as exc:
            if not self._is_conditional_failure(exc):
                raise
            raise RuntimeError("idempotency claim was lost before completion") from exc
        self._claims.pop((tenant_id, event_id), None)

    def mark_processed(self, tenant_id: str, event_id: str) -> bool:
        if not tenant_id.strip() or not event_id.strip():
            raise ValueError("tenant ID and idempotency key must be non-empty")
        if self._table is not None:
            item: dict[str, Any] = {
                "idempotency_id": self._key(tenant_id, event_id),
                "tenant_hash": hashlib.sha256(tenant_id.encode("utf-8")).hexdigest(),
                "status": "processed",
            }
            if self._ttl_seconds is not None:
                item["expires_at"] = int(time.time()) + self._ttl_seconds
            try:
                self._table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(idempotency_id)",
                )
            except Exception as exc:
                if self._is_conditional_failure(exc):
                    return False
                raise
            return True
        key = (tenant_id, event_id)
        if key in self._processed:
            return False
        self._processed.add(key)
        return True

    def release(self, tenant_id: str, event_id: str) -> None:
        if self._table is not None:
            claim_id = self._claims.get((tenant_id, event_id))
            if claim_id is None:
                return
            try:
                self._table.delete_item(
                    Key={"idempotency_id": self._key(tenant_id, event_id)},
                    ConditionExpression=(
                        "tenant_hash = :tenant_hash AND #status = :in_progress "
                        "AND claim_id = :claim_id"
                    ),
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":tenant_hash": hashlib.sha256(tenant_id.encode("utf-8")).hexdigest(),
                        ":in_progress": "in_progress",
                        ":claim_id": claim_id,
                    },
                )
            except Exception as exc:
                if not self._is_conditional_failure(exc):
                    raise
            self._claims.pop((tenant_id, event_id), None)
            return
        self._processed.discard((tenant_id, event_id))
