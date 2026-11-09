from aria.session.manager import SessionManager


class FakeConditionalFailure(Exception):
    response = {"Error": {"Code": "ConditionalCheckFailedException"}}


class FakeSessionTable:
    def __init__(self):
        self.items = {}

    def get_item(self, *, Key, **kwargs):
        item = self.items.get(Key["session_id"])
        return {"Item": dict(item)} if item is not None else {}

    def put_item(self, *, Item, **kwargs):
        condition = kwargs.get("ConditionExpression", "")
        values = kwargs.get("ExpressionAttributeValues", {})
        key = Item["session_id"]
        existing = self.items.get(key)
        if condition and existing is not None:
            # attribute_not_exists branch: reject if already present (start_session)
            # revision-match branch: reject if revision doesn't match (save_session)
            expected = values.get(":expected")
            if expected is None or existing.get("revision") != expected:
                raise FakeConditionalFailure()
        self.items[key] = dict(Item)

    def update_item(
        self,
        *,
        Key,
        UpdateExpression,
        ConditionExpression=None,
        ExpressionAttributeNames=None,
        ExpressionAttributeValues=None,
    ):
        item = self.items.get(Key["session_id"])
        if item is None:
            raise FakeConditionalFailure()
        values = ExpressionAttributeValues or {}
        if ConditionExpression and item.get("revision") != values.get(":expected"):
            raise FakeConditionalFailure()
        if ":state" in values:
            item["state"] = values[":state"]
            item["revision"] = values[":revision"]
        if ":status" in values:
            item["status"] = values[":status"]


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


def test_session_manager_recovers_existing_session_state():
    manager = SessionManager()
    session = manager.start_session("tenant-1", "user-42")
    manager.update_session_state(session["session_id"], {"risk_appetite": "moderate"})

    recovered = manager.recover_session(session["session_id"])

    assert recovered["status"] == "recovered"
    assert recovered["state"]["risk_appetite"] == "moderate"


def test_dynamodb_session_manager_recovers_state_and_rejects_stale_revision():
    table = FakeSessionTable()
    first_manager = SessionManager(table=table)
    session = first_manager.start_session("tenant-1", "user-42")
    assert first_manager.update_session_state(
        session["session_id"], {"risk_appetite": "moderate"}, expected_revision=1
    )

    restarted_manager = SessionManager(table=table)
    recovered = restarted_manager.start_session("tenant-1", "user-42")

    assert recovered["state"]["risk_appetite"] == "moderate"
    assert recovered["revision"] == 2
    assert not restarted_manager.update_session_state(
        session["session_id"], {"segment": "premier"}, expected_revision=1
    )


def test_recover_session_concurrent_writers_both_succeed_idempotently():
    """Two concurrent callers racing to recover the same session must not raise;
    both should return a session with status='recovered'."""
    table = FakeSessionTable()
    manager = SessionManager(table=table)
    session = manager.start_session("tenant-1", "user-99")
    session_id = session["session_id"]

    # First writer recovers normally.
    first = manager.recover_session(session_id)
    assert first["status"] == "recovered"

    # Second writer finds the revision has already advanced (status was set by first).
    # The conditional update fails, and recover_session re-reads the winner's state
    # instead of raising.
    second = manager.recover_session(session_id)
    assert second["status"] == "recovered"


def test_save_session_rejects_stale_revision_and_returns_none():
    """save_session must return None when a concurrent writer advanced the revision."""
    table = FakeSessionTable()
    manager = SessionManager(table=table)
    session = manager.start_session("tenant-1", "user-77")
    session_id = session["session_id"]

    # Advance the revision via update_session_state so the table is at revision 2.
    manager.update_session_state(session_id, {"segment": "premier"}, expected_revision=1)

    # A stale snapshot (still at revision 1) must be rejected.
    stale_snapshot = {**session, "status": "active", "revision": 1}
    result = manager.save_session(session_id, stale_snapshot)
    assert result is None

    # A snapshot that matches the current revision must succeed.
    current = manager.get_session(session_id)
    saved = manager.save_session(session_id, current)
    assert saved is not None
    assert saved["revision"] == 2


def test_save_session_succeeds_for_new_session():
    """save_session must succeed when the session does not yet exist in DynamoDB."""
    table = FakeSessionTable()
    manager = SessionManager(table=table)
    new_session = {
        "session_id": "tenant-2:user-new",
        "tenant_id": "tenant-2",
        "user_id": "user-new",
        "state": {},
        "revision": 1,
        "status": "active",
    }
    result = manager.save_session("tenant-2:user-new", new_session)
    assert result is not None
    assert result["session_id"] == "tenant-2:user-new"
