from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class Observability:
    _SENSITIVE_KEY_FRAGMENTS = (
        "secret",
        "password",
        "passcode",
        "pin",
        "otp",
        "cvv",
        "cvc",
        "token",
        "authorization",
    )
    _SENSITIVE_TEXT_PATTERNS = (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
        re.compile(
            r"(?i)\b(password|passcode|pin|otp|cvv|cvc|secret|access[_ -]?token|refresh[_ -]?token)"
            r"\b\s*(?:is|=|:)?\s*[^\s,;]+"
        ),
    )

    def _sanitize_text(self, value: str) -> str:
        for pattern in self._SENSITIVE_TEXT_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self._sanitize(item)
                for key, item in value.items()
                if not any(fragment in key.lower() for fragment in self._SENSITIVE_KEY_FRAGMENTS)
            }
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, str):
            return self._sanitize_text(value)
        return value

    def log_event(
        self,
        event: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        sanitized = self._sanitize(payload)
        base: dict[str, Any] = {"event": event, **sanitized}
        if correlation_id is not None:
            base["correlation_id"] = correlation_id
        return base

    def log_operation(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
        session_id: str | None = None,
        latency_ms: float | None = None,
        status: str = "success",
        retries: int = 0,
    ) -> dict[str, Any]:
        prefix, _, name = operation.partition(".")
        entry: dict[str, Any] = {
            "event": operation,
            "category": prefix or "request",
            "tool": name if prefix == "tool" else None,
            "status": status,
            "retries": retries,
            **self._sanitize(payload),
        }
        if correlation_id is not None:
            entry["correlation_id"] = correlation_id
        if session_id is not None:
            entry["session_id"] = session_id
        if latency_ms is not None:
            entry["latency_ms"] = latency_ms
        return {key: value for key, value in entry.items() if value is not None}

    def emit_operation(
        self,
        operation: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
        session_id: str | None = None,
        latency_ms: float | None = None,
        status: str = "success",
        retries: int = 0,
    ) -> dict[str, Any]:
        entry = self.log_operation(
            operation,
            payload,
            correlation_id=correlation_id,
            session_id=session_id,
            latency_ms=latency_ms,
            status=status,
            retries=retries,
        )
        logger.info(json.dumps(entry, sort_keys=True, default=str))
        return entry
