from __future__ import annotations

import re


class ContextBuilder:
    def _redact_sensitive_text(self, text: str) -> str:
        redacted = re.sub(
            r"(?i)\b(password|pin|otp|cvv|secret)\b\s*(?:is|=)?\s*[A-Za-z0-9\-]+",
            r"\1=[REDACTED]",
            text,
        )
        return redacted

    def build_context(
        self, tenant_id: str, workflow_state: dict, memory_store: object, user_message: str
    ) -> dict:
        current = dict(workflow_state)
        for key in ["password", "pin", "otp", "cvv", "secret"]:
            current.pop(key, None)

        memory_items = []
        if hasattr(memory_store, "retrieve"):
            memory_items = memory_store.retrieve(tenant_id, limit=5)

        safe_message = self._redact_sensitive_text(user_message)
        history = [item.value for item in memory_items]
        return {
            "tenant_id": tenant_id,
            "current_workflow_state": current,
            "history": history,
            "user_message": safe_message,
            "fallback_text": (
                "No memory entries available; continue with the current workflow "
                "state and ask for the next needed fact."
            ),
        }
