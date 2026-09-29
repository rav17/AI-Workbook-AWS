from __future__ import annotations


class StateStore:
    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def save(self, session: dict) -> dict:
        self._sessions[session["session_id"]] = session
        return session

    def update_if_unmodified(
        self, session_id: str, updates: dict, expected_revision: int | None
    ) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if expected_revision is not None and session.get("revision") != expected_revision:
            return False
        session["state"] = {**session.get("state", {}), **updates}
        session["revision"] = int(session.get("revision", 0)) + 1
        return True


class IdempotencyStore:
    def __init__(self) -> None:
        self._processed: set[tuple[str, str]] = set()

    def mark_processed(self, tenant_id: str, event_id: str) -> bool:
        key = (tenant_id, event_id)
        if key in self._processed:
            return False
        self._processed.add(key)
        return True
