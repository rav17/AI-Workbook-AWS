from __future__ import annotations

from collections.abc import Callable
from typing import Any


class FrameworkRunner:
    def __init__(
        self,
        handler: Callable[[dict[str, Any], dict[str, Any]], Any] | None = None,
    ) -> None:
        self.handler = handler

    def _apply_patch(self, session_state: dict[str, Any], patch: dict[str, Any] | None) -> None:
        if not isinstance(patch, dict):
            return
        session_state.update(patch)

    def run(
        self,
        payload: dict[str, Any],
        state: dict[str, Any] | None = None,
        *,
        mode: str = "sync",
        cleanup: Callable[[], Any] | None = None,
    ) -> dict[str, Any]:
        session_state = dict(state or {})
        self._apply_patch(session_state, payload.get("state_patch"))

        try:
            if self.handler is not None:
                result = self.handler(payload, session_state)
            else:
                name = payload.get("name", "there")
                result = {
                    "response": f"Hello {name}, I have processed your request.",
                    "state": session_state,
                }

            if not isinstance(result, dict):
                result = {"response": str(result), "state": session_state}

            return {
                "status": "processed",
                "mode": mode,
                "response": result.get("response", "processed"),
                "state": result.get("state", session_state),
            }
        except Exception as exc:  # pragma: no cover - guard against unexpected runtime failures
            return {
                "status": "error",
                "mode": mode,
                "error": str(exc),
                "state": session_state,
            }
        finally:
            if cleanup is not None:
                cleanup()

    async def run_async(
        self,
        payload: dict[str, Any],
        state: dict[str, Any] | None = None,
        *,
        cleanup: Callable[[], Any] | None = None,
    ) -> dict[str, Any]:
        return self.run(payload, state, mode="async", cleanup=cleanup)

    def run_stream(
        self,
        payload: dict[str, Any],
        state: dict[str, Any] | None = None,
        *,
        cleanup: Callable[[], Any] | None = None,
    ) -> dict[str, Any]:
        return self.run(payload, state, mode="stream", cleanup=cleanup)
