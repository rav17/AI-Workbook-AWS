from __future__ import annotations


def main(payload: dict, state: dict | None = None) -> dict:
    return {
        "status": "ok",
        "response": f"Smoke test completed for {payload.get('name', 'user')}.",
        "state": state or {},
    }
