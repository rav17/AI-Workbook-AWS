from aria.api.runtime_session import (
    IdempotencyConflict,
    RuntimeSessionBusy,
    RuntimeSessionCoordinator,
)
from aria.framework.agentcore import AgentCoreRuntimeAdapter
from aria.framework.runner import FrameworkRunner
from aria.persistence.store import IdempotencyStore
from aria.session.manager import SessionManager


def test_session_manager_reuses_conversation_session():
    manager = SessionManager()

    first = manager.start_session("tenant-1", "user-1")
    second = manager.start_session("tenant-1", "user-1")

    assert first["session_id"] == second["session_id"]
    assert first["user_id"] == "user-1"


def test_session_manager_rejects_duplicate_write_lock():
    manager = SessionManager()
    session_id = manager.start_session("tenant-2", "user-2")["session_id"]

    manager.lock_session(session_id)
    assert manager.lock_session(session_id) is False


def test_framework_runner_processes_payload_with_state():
    runner = FrameworkRunner()
    result = runner.run({"message": "hello", "name": "Aisha"}, {"risk_appetite": "moderate"})

    assert result["status"] == "processed"
    assert result["state"]["risk_appetite"] == "moderate"
    assert "Aisha" in result["response"]


def test_runtime_session_coordinator_reuses_authenticated_conversation():
    manager = SessionManager()
    coordinator = RuntimeSessionCoordinator(
        AgentCoreRuntimeAdapter(manager),
    )
    event = {"requestContext": {"authorizer": {"tenant_id": "tenant-1", "sub": "user-1"}}}

    first = coordinator.run(event, {"conversation_id": "conversation-1"}, lambda runtime, state: {})
    second = coordinator.run(
        event, {"conversation_id": "conversation-1"}, lambda runtime, state: {}
    )

    assert first["runtime_session_id"] == second["runtime_session_id"]
    assert first["session_id"] == "tenant-1:user-1:conversation-1"


def test_runtime_identity_uses_verified_claims_not_payload_ids():
    coordinator = RuntimeSessionCoordinator(AgentCoreRuntimeAdapter(SessionManager()))

    identity = coordinator._identity(
        {
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "verified-user", "custom:tenant_id": "verified-tenant"}
                }
            }
        },
        {"client_id": "spoofed-user", "conversation_id": "conversation-1"},
    )

    assert identity == ("verified-tenant", "verified-user", "conversation-1")


def test_runtime_identity_rejects_payload_only_identity():
    import pytest

    coordinator = RuntimeSessionCoordinator(AgentCoreRuntimeAdapter(SessionManager()))

    with pytest.raises(ValueError, match="authenticated tenant claim is required"):
        coordinator._identity({}, {"client_id": "client-1", "conversation_id": "conversation-1"})


def test_runtime_session_coordinator_rejects_concurrent_writer():
    manager = SessionManager()
    adapter = AgentCoreRuntimeAdapter(manager)
    coordinator = RuntimeSessionCoordinator(adapter)
    event = {"requestContext": {"authorizer": {"tenant_id": "tenant-1", "sub": "user-1"}}}
    runtime = adapter.resolve("tenant-1", "user-1", "conversation-2")
    assert adapter.acquire(runtime) is True

    try:
        try:
            coordinator.run(
                event,
                {"conversation_id": "conversation-2"},
                lambda runtime_session, state: {},
            )
        except RuntimeSessionBusy as exc:
            assert str(exc) == "runtime_session_busy"
        else:
            raise AssertionError("concurrent runtime writers must be rejected")
    finally:
        adapter.release(runtime)


def test_runtime_session_coordinator_deduplicates_requests_and_releases_failed_claims():
    coordinator = RuntimeSessionCoordinator(
        AgentCoreRuntimeAdapter(SessionManager()), IdempotencyStore()
    )
    event = {"requestContext": {"authorizer": {"tenant_id": "tenant-1", "sub": "user-1"}}}
    calls = 0

    def callback(runtime, state):
        nonlocal calls
        calls += 1
        return {"response": "done"}

    first = coordinator.run(event, {}, callback, idempotency_key="request-1")
    try:
        coordinator.run(event, {}, callback, idempotency_key="request-1")
    except IdempotencyConflict as exc:
        assert str(exc) == "duplicate_request"
    else:
        raise AssertionError("duplicate request keys must not invoke Runtime twice")

    assert first["response"] == "done"
    assert calls == 1

    attempts = 0

    def flaky_callback(runtime, state):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary invocation failure")
        return {"response": "retried"}

    try:
        coordinator.run(event, {}, flaky_callback, idempotency_key="request-2")
    except RuntimeError:
        pass
    else:
        raise AssertionError("the first Runtime failure should propagate")

    retried = coordinator.run(event, {}, flaky_callback, idempotency_key="request-2")
    assert retried["response"] == "retried"
    assert attempts == 2
