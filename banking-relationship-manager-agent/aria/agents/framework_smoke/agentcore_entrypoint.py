from __future__ import annotations

from typing import Any


def main(payload: dict[str, Any], state: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "ok",
        "response": f"Smoke test completed for {payload.get('name', 'user')}.",
        "state": state or {},
    }
