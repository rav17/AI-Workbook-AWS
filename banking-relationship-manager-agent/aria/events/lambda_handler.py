from __future__ import annotations

from typing import Any

from aria.events.handler import handle_event


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    del context
    return handle_event(event, lambda normalized: {"client_id": normalized["client_id"]})
