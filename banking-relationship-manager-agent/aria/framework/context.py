from __future__ import annotations

import re
from typing import Any

from aria.framework.contracts import MemoryRetriever


class ContextBuilder:
    def _redact_sensitive_text(self, text: str) -> str:
        redacted = re.sub(
            r"(?i)\b(password|pin|otp|cvv|secret)\b\s*(?:is|=)?\s*[A-Za-z0-9\-]+",
            r"\1=[REDACTED]",
            text,
        )
        return redacted

    def build_context(
        self,
        tenant_id: str,
        workflow_state: dict[str, Any],
        memory_store: MemoryRetriever | None,
        user_message: str,
    ) -> dict[str, Any]:
        current = dict(workflow_state)
        for key in ["password", "pin", "otp", "cvv", "secret"]:
            current.pop(key, None)

        memory_items = memory_store.retrieve(tenant_id, limit=5) if memory_store is not None else []

        safe_message = self._redact_sensitive_text(user_message)
        history = [item.value for item in memory_items]
        memory = {item.key: item.value for item in memory_items if item.key not in current}
        memory.update(current)
        return {
            "tenant_id": tenant_id,
            "current_workflow_state": current,
            "memory": memory,
            "history": history,
            "user_message": safe_message,
            "fallback_text": (
                "No memory entries available; continue with the current workflow "
                "state and ask for the next needed fact."
            ),
        }
