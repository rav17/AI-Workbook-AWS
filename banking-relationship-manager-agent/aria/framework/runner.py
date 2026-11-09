from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aria.framework.config import FrameworkConfig, load_framework_config


class FrameworkRunner:
    def __init__(
        self,
        handler: Callable[[dict[str, Any], dict[str, Any]], Any] | None = None,
        config: FrameworkConfig | None = None,
    ) -> None:
        self.handler = handler
        self.config = config or load_framework_config()

    def _bounded_context(self, payload: dict[str, Any]) -> str | None:
        context = payload.get("context")
        if not isinstance(context, str):
            return None
        return context[: self.config.max_context_tokens * 4]

    def _stop_result(self, status: str, reason: str) -> dict[str, Any]:
        return {"status": status, "reason": reason}

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
        if payload.get("cancelled"):
            return self._stop_result("cancelled", "cancelled")
        guardrail_reason = payload.get("guardrail_stop_reason")
        if guardrail_reason:
            return self._stop_result("blocked", str(guardrail_reason))

        session_state = dict(state or {})
        self._apply_patch(session_state, payload.get("state_patch"))
        bounded_context = self._bounded_context(payload)
        turn_count = int(payload.get("turn_count", session_state.get("turn_count", 0)))
        tool_calls = payload.get("tool_calls", [])
        if isinstance(tool_calls, list) and len(tool_calls) > self.config.max_tool_calls:
            result = self._stop_result("limit_exceeded", "max_tool_calls")
            if bounded_context is not None:
                result["context"] = bounded_context
            return result
        if turn_count >= self.config.max_turns:
            result = self._stop_result("limit_exceeded", "max_turns")
            if bounded_context is not None:
                result["context"] = bounded_context
            return result

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

            response = {
                "status": "processed",
                "mode": mode,
                "response": result.get("response", "processed"),
                "state": result.get("state", session_state),
            }
            if bounded_context is not None:
                response["context"] = bounded_context
            return response
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
