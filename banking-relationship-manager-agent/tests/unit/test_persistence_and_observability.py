from aria.observability import Observability
from aria.persistence.store import IdempotencyStore, StateStore
from aria.session.manager import SessionManager


def test_state_store_rejects_stale_revision_and_keeps_idempotency():
    store = StateStore()
    session = {"session_id": "sess-1", "state": {"risk_appetite": "moderate"}, "revision": 1}
    store.save(session)

    assert store.update_if_unmodified("sess-1", {"segment": "premier"}, expected_revision=1) is True
    assert store.update_if_unmodified("sess-1", {"segment": "retail"}, expected_revision=1) is False

    idem = IdempotencyStore()
    assert idem.mark_processed("client-1", "evt-1") is True
    assert idem.mark_processed("client-1", "evt-1") is False


def test_session_manager_supports_revision_and_retries():
    manager = SessionManager()
    session = manager.start_session("tenant-1", "user-1")

    manager.update_session_state(
        session["session_id"], {"risk_appetite": "moderate"}, expected_revision=None
    )
    assert manager.get_session(session["session_id"])["revision"] == 2

    assert (
        manager.update_session_state(
            session["session_id"], {"segment": "premier"}, expected_revision=2
        )
        is True
    )
    assert (
        manager.update_session_state(
            session["session_id"], {"segment": "retail"}, expected_revision=2
        )
        is False
    )


def test_state_store_applies_idempotent_update_and_runs_side_effect_once():
    store = StateStore()
    store.save({"session_id": "sess-2", "state": {}, "revision": 1})
    calls: list[int] = []

    first = store.apply_idempotent_update(
        "sess-2",
        {"segment": "premier"},
        expected_revision=1,
        tenant_id="tenant-1",
        idempotency_key="event-1",
        side_effect=lambda session: calls.append(session["revision"]),
    )
    duplicate = store.apply_idempotent_update(
        "sess-2",
        {"segment": "retail"},
        expected_revision=2,
        tenant_id="tenant-1",
        idempotency_key="event-1",
        side_effect=lambda session: calls.append(session["revision"]),
    )

    assert first == {"applied": True, "revision": 2, "reason": "accepted"}
    assert duplicate["applied"] is False
    assert duplicate["reason"] == "duplicate_event"
    assert calls == [2]
    assert store.get("sess-2")["state"]["segment"] == "premier"


def test_state_store_releases_idempotency_key_when_side_effect_fails():
    store = StateStore()
    store.save({"session_id": "sess-3", "state": {}, "revision": 1})
    attempts = 0

    def flaky_effect(session: dict) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary downstream failure")

    failed = store.apply_idempotent_update(
        "sess-3",
        {"segment": "premier"},
        expected_revision=1,
        tenant_id="tenant-1",
        idempotency_key="event-2",
        side_effect=flaky_effect,
    )
    retried = store.apply_idempotent_update(
        "sess-3",
        {"segment": "premier"},
        expected_revision=1,
        tenant_id="tenant-1",
        idempotency_key="event-2",
        side_effect=flaky_effect,
    )

    assert failed == {
        "applied": False,
        "revision": 1,
        "reason": "side_effect_failed",
        "retryable": True,
    }
    assert retried["applied"] is True
    assert attempts == 2


def test_idempotency_store_persists_claims_across_instances_and_releases_for_retry():
    class ConditionalFailure(Exception):
        response = {"Error": {"Code": "ConditionalCheckFailedException"}}

    class FakeTable:
        def __init__(self):
            self.items = {}

        def put_item(self, *, Item, ConditionExpression, **kwargs):
            key = Item["idempotency_id"]
            if key in self.items:
                raise ConditionalFailure()
            self.items[key] = Item

        def delete_item(self, *, Key, **kwargs):
            self.items.pop(Key["idempotency_id"], None)

    table = FakeTable()
    first = IdempotencyStore(table=table)
    after_restart = IdempotencyStore(table=table)

    assert first.claim("tenant-1", "event-1") is True
    assert after_restart.claim("tenant-1", "event-1") is False
    first.release("tenant-1", "event-1")
    assert after_restart.claim("tenant-1", "event-1") is True


def test_idempotency_store_from_environment_uses_configured_dynamodb_table(monkeypatch):
    import sys
    from types import SimpleNamespace

    class FakeTable:
        def put_item(self, **kwargs):
            self.item = kwargs["Item"]

    table = FakeTable()
    boto3 = SimpleNamespace(resource=lambda service: SimpleNamespace(Table=lambda name: table))
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setenv("IDEMPOTENCY_TABLE_NAME", "aria-idempotency-test")
    monkeypatch.setenv("IDEMPOTENCY_TTL_SECONDS", "3600")

    store = IdempotencyStore.from_environment()
    assert store.mark_processed("tenant-1", "event-1") is True
    assert table.item["expires_at"] > 0


def test_state_store_rejects_duplicate_after_restart_with_dynamodb_idempotency():
    class ConditionalFailure(Exception):
        response = {"Error": {"Code": "ConditionalCheckFailedException"}}

    class FakeTable:
        def __init__(self):
            self.items = {}

        def put_item(self, *, Item, ConditionExpression, **kwargs):
            key = Item["idempotency_id"]
            if key in self.items:
                raise ConditionalFailure()
            self.items[key] = Item

        def update_item(
            self,
            *,
            Key,
            UpdateExpression,
            ConditionExpression,
            ExpressionAttributeNames,
            ExpressionAttributeValues,
        ):
            item = self.items[Key["idempotency_id"]]
            assert item["claim_id"] == ExpressionAttributeValues[":claim_id"]
            item["status"] = ExpressionAttributeValues[":processed"]
            item.pop("lease_until", None)

    table = FakeTable()
    first = StateStore(idempotency_store=IdempotencyStore(table=table))
    after_restart = StateStore(idempotency_store=IdempotencyStore(table=table))
    first.save({"session_id": "session-1", "state": {}, "revision": 1})
    after_restart.save({"session_id": "session-1", "state": {}, "revision": 1})

    accepted = first.apply_idempotent_update(
        "session-1",
        {"stage": "approved"},
        expected_revision=1,
        tenant_id="tenant-1",
        idempotency_key="event-1",
    )
    duplicate = after_restart.apply_idempotent_update(
        "session-1",
        {"stage": "rejected"},
        expected_revision=1,
        tenant_id="tenant-1",
        idempotency_key="event-1",
    )

    assert accepted["applied"] is True
    assert duplicate["reason"] == "duplicate_event"
    assert after_restart.get("session-1")["state"] == {}


def test_idempotency_store_reclaims_expired_in_progress_claim(monkeypatch):
    import aria.persistence.store as persistence_store

    class ConditionalFailure(Exception):
        response = {"Error": {"Code": "ConditionalCheckFailedException"}}

    class FakeTable:
        def __init__(self):
            self.items = {}

        def put_item(
            self,
            *,
            Item,
            ConditionExpression,
            ExpressionAttributeNames,
            ExpressionAttributeValues,
        ):
            key = Item["idempotency_id"]
            previous = self.items.get(key)
            claim_time = ExpressionAttributeValues[":now"]
            expired_lease = previous is not None and (
                previous["status"] == "in_progress" and previous["lease_until"] < claim_time
            )
            expired_record = previous is not None and (
                previous["status"] == "processed"
                and previous.get("expires_at", claim_time) < claim_time
            )
            if previous is not None and not (expired_lease or expired_record):
                raise ConditionalFailure()
            self.items[key] = Item

        def delete_item(self, *, Key, ExpressionAttributeValues, **kwargs):
            item = self.items.get(Key["idempotency_id"])
            if item is None or item["claim_id"] != ExpressionAttributeValues[":claim_id"]:
                raise ConditionalFailure()
            del self.items[Key["idempotency_id"]]

        def update_item(self, *, Key, ExpressionAttributeValues, **kwargs):
            item = self.items[Key["idempotency_id"]]
            if item["claim_id"] != ExpressionAttributeValues[":claim_id"]:
                raise ConditionalFailure()
            item["status"] = ExpressionAttributeValues[":processed"]
            item.pop("lease_until", None)
            if ":expires" in ExpressionAttributeValues:
                item["expires_at"] = ExpressionAttributeValues[":expires"]

    now = 1000
    monkeypatch.setattr(persistence_store.time, "time", lambda: now)
    table = FakeTable()
    first = IdempotencyStore(table=table, lease_seconds=30)

    assert first.claim("tenant-1", "event-1") is True
    now = 1031
    restarted = IdempotencyStore(table=table, lease_seconds=30)
    assert restarted.claim("tenant-1", "event-1") is True
    assert table.items[next(iter(table.items))]["lease_until"] == 1061
    first.release("tenant-1", "event-1")
    restarted.mark_completed("tenant-1", "event-1")
    assert table.items[next(iter(table.items))]["status"] == "processed"
    assert restarted.claim("tenant-1", "event-1") is False

    expiring = IdempotencyStore(table=table, ttl_seconds=10, lease_seconds=30)
    assert expiring.claim("tenant-1", "event-2") is True
    expiring.mark_completed("tenant-1", "event-2")
    now = 1042
    after_expiry = IdempotencyStore(table=table, ttl_seconds=10, lease_seconds=30)
    assert after_expiry.claim("tenant-1", "event-2") is True


def test_observability_redacts_and_records_context_metadata():
    event = Observability().log_event(
        "workflow.update",
        {
            "password": "secret",
            "client_id": "CUST-1",
            "workflow_revision": 2,
            "changed_fields": ["risk_appetite"],
        },
        correlation_id="corr-123",
    )

    assert event["event"] == "workflow.update"
    assert event["correlation_id"] == "corr-123"
    assert event["workflow_revision"] == 2
    assert "secret" not in str(event)


def test_observability_redacts_nested_sensitive_values_and_secret_text():
    event = Observability().log_event(
        "request.invoke",
        {
            "authorization": "Bearer opaque-token-value",
            "nested": {"account_password": "secret-value"},
            "message": "My OTP is 123456 and my password=abc123",
        },
    )

    rendered = str(event)
    assert "opaque-token-value" not in rendered
    assert "secret-value" not in rendered
    assert "123456" not in rendered
    assert "abc123" not in rendered
