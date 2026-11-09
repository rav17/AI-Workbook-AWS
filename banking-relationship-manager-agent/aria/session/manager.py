from __future__ import annotations

from typing import Any, cast

Session = dict[str, Any]


def _build_session_id(tenant_id: str, user_id: str) -> str:
    return f"{tenant_id}:{user_id}"


class SessionManager:
    def __init__(
        self,
        initial_sessions: dict[str, Session] | None = None,
        *,
        table: Any = None,
    ) -> None:
        self._sessions: dict[str, Session] = dict(initial_sessions or {})
        self._locks: set[str] = set()
        self._table = table

    @staticmethod
    def _conditional_failure(error: Exception) -> bool:
        response = getattr(error, "response", {})
        return (
            isinstance(response, dict)
            and response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"
        )

    def start_session(self, tenant_id: str, user_id: str) -> Session:
        session_id = _build_session_id(tenant_id, user_id)
        if self._table is not None:
            item = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "state": {},
                "revision": 1,
                "status": "active",
            }
            try:
                self._table.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(session_id)",
                )
            except Exception as exc:
                if not self._conditional_failure(exc):
                    raise
            return self.get_session(session_id)
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "state": {},
                "revision": 1,
                "status": "active",
            }
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> Session:
        if self._table is not None:
            response = self._table.get_item(Key={"session_id": session_id}, ConsistentRead=True)
            item = response.get("Item")
            if item is None:
                raise KeyError(f"session not found: {session_id}")
            return cast(Session, item)
        return self._sessions[session_id]

    def recover_session(self, session_id: str) -> Session:
        if self._table is not None:
            session = self.get_session(session_id)
            current_revision = int(session.get("revision", 0))
            try:
                self._table.update_item(
                    Key={"session_id": session_id},
                    UpdateExpression="SET #status = :status",
                    ConditionExpression="#revision = :expected",
                    ExpressionAttributeNames={"#status": "status", "#revision": "revision"},
                    ExpressionAttributeValues={
                        ":status": "recovered",
                        ":expected": current_revision,
                    },
                )
            except Exception as exc:
                if not self._conditional_failure(exc):
                    raise
                # Another writer already recovered this session — re-read the winner's state.
                return self.get_session(session_id)
            session["status"] = "recovered"
            return session
        if session_id not in self._sessions:
            raise KeyError(f"session not found: {session_id}")
        session = cast(Session, dict(self._sessions[session_id]))
        session["status"] = "recovered"
        self._sessions[session_id] = session
        return session

    def save_session(
        self,
        session_id: str,
        session: Session,
        *,
        expected_revision: int | None = None,
    ) -> Session | None:
        """Persist a full session snapshot.

        Returns the saved session on success, or ``None`` when a concurrent
        writer has already advanced the revision (DynamoDB only).  Callers
        should treat ``None`` as a signal to re-read and retry.
        """
        if self._table is not None:
            current_revision = int(session.get("revision", expected_revision or 0))
            condition = (
                "attribute_not_exists(session_id) OR #revision = :expected"
            )
            try:
                self._table.put_item(
                    Item={**session, "session_id": session_id},
                    ConditionExpression=condition,
                    ExpressionAttributeNames={"#revision": "revision"},
                    ExpressionAttributeValues={":expected": current_revision},
                )
            except Exception as exc:
                if self._conditional_failure(exc):
                    return None
                raise
            return self.get_session(session_id)
        self._sessions[session_id] = dict(session)
        return self._sessions[session_id]

    def lock_session(self, session_id: str) -> bool:
        if session_id in self._locks:
            return False
        self._locks.add(session_id)
        return True

    def release_session(self, session_id: str) -> None:
        self._locks.discard(session_id)

    def update_session_state(
        self, session_id: str, updates: dict[str, Any], expected_revision: int | None = None
    ) -> bool:
        if self._table is not None:
            try:
                session = self.get_session(session_id)
            except KeyError:
                return False
            current_revision = int(session.get("revision", 0))
            if expected_revision is not None and current_revision != expected_revision:
                return False
            try:
                self._table.update_item(
                    Key={"session_id": session_id},
                    UpdateExpression="SET #state = :state, #revision = :revision",
                    ConditionExpression="#revision = :expected",
                    ExpressionAttributeNames={"#state": "state", "#revision": "revision"},
                    ExpressionAttributeValues={
                        ":state": {**session.get("state", {}), **updates},
                        ":revision": current_revision + 1,
                        ":expected": current_revision,
                    },
                )
                return True
            except Exception as exc:
                if self._conditional_failure(exc):
                    return False
                raise
        session = self._sessions[session_id]
        if expected_revision is not None and session.get("revision") != expected_revision:
            return False
        session["state"] = {**session["state"], **updates}
        session["revision"] = int(session.get("revision", 1)) + 1
        return True
