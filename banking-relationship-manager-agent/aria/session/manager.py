from __future__ import annotations


def _build_session_id(tenant_id: str, user_id: str) -> str:
    return f"{tenant_id}:{user_id}"


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}
        self._locks: set[str] = set()

    def start_session(self, tenant_id: str, user_id: str) -> dict:
        session_id = _build_session_id(tenant_id, user_id)
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "session_id": session_id,
                "state": {},
                "revision": 1,
            }
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> dict:
        return self._sessions[session_id]

    def lock_session(self, session_id: str) -> bool:
        if session_id in self._locks:
            return False
        self._locks.add(session_id)
        return True

    def release_session(self, session_id: str) -> None:
        self._locks.discard(session_id)

    def update_session_state(
        self, session_id: str, updates: dict, expected_revision: int | None = None
    ) -> bool:
        session = self._sessions[session_id]
        if expected_revision is not None and session.get("revision") != expected_revision:
            return False
        session["state"] = {**session["state"], **updates}
        session["revision"] = int(session.get("revision", 1)) + 1
        return True
