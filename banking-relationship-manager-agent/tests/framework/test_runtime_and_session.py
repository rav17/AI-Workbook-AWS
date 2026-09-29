from aria.framework.runner import FrameworkRunner
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
