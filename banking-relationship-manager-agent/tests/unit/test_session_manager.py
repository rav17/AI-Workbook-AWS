from aria.session.manager import SessionManager


def test_session_manager_tracks_lock_and_release():
    manager = SessionManager()
    session = manager.start_session("tenant-1", "user-42")

    assert manager.lock_session(session["session_id"]) is True
    assert manager.lock_session(session["session_id"]) is False

    manager.release_session(session["session_id"])
    assert manager.lock_session(session["session_id"]) is True


def test_session_manager_updates_state_without_overwriting_history():
    manager = SessionManager()
    session = manager.start_session("tenant-1", "user-42")

    manager.update_session_state(session["session_id"], {"risk_appetite": "moderate"})
    manager.update_session_state(session["session_id"], {"segment": "premier"})

    state = manager.get_session(session["session_id"])
    assert state["state"]["risk_appetite"] == "moderate"
    assert state["state"]["segment"] == "premier"
