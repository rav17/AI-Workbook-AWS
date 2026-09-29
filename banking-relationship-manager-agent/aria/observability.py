from __future__ import annotations


class Observability:
    def log_event(self, event: str, payload: dict, correlation_id: str | None = None) -> dict:
        sanitized = {}
        for key, value in payload.items():
            if key.lower() in {"secret", "password", "pin", "otp", "cvv"}:
                continue
            sanitized[key] = value
        base = {"event": event, **sanitized}
        if correlation_id is not None:
            base["correlation_id"] = correlation_id
        return base
