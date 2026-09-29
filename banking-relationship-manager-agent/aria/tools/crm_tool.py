from __future__ import annotations


def update_client_profile(client_id: str, profile_data: dict) -> dict:
    record = {
        "client_id": client_id,
        "name": profile_data.get("name", "Unknown"),
        "segment": profile_data.get("segment", "retail"),
        "risk_appetite": profile_data.get("risk_appetite"),
        "needs": profile_data.get("needs", []),
    }
    return record


def log_interaction(entry: dict) -> dict:
    summary = {
        "client_id": entry.get("client_id", "unknown"),
        "topics": entry.get("topics", []),
        "preferences": entry.get("preferences", []),
        "follow_up": entry.get("follow_up"),
    }
    return {"summary": summary}


def create_followup_reminder(client_id: str, message: str) -> dict:
    return {
        "client_id": client_id,
        "message": message,
        "reminder_type": "follow_up",
    }
