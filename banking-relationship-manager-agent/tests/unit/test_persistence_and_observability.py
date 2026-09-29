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
