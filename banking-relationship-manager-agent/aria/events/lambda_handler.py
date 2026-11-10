from __future__ import annotations

from typing import Any

from aria.events.handler import process_event


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    del context
    return {"status": "processed", "result": process_event(event)}
