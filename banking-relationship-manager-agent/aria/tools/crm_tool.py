from __future__ import annotations

from typing import Any

from aria.guardrails.processor import GuardrailProcessor
from aria.models.interaction import InteractionSummary
from aria.models.wallet import WalletProfile
from aria.tools.risk_tool import assess_risk_appetite


def get_client_profile(client_id: str, store: dict[str, Any] | None = None) -> dict[str, Any]:
    store = store or {}
    return dict(store.get(client_id, {}))


def update_client_profile(client_id: str, profile_data: dict[str, Any]) -> dict[str, Any]:
    record = {
        "client_id": client_id,
        "name": profile_data.get("name", "Unknown"),
        "segment": profile_data.get("segment", "retail"),
        "risk_appetite": profile_data.get("risk_appetite"),
        "needs": profile_data.get("needs", []),
    }

    for field in (
        "family_members",
        "accounts",
        "wallet_profile",
        "preferences",
        "segment_flags",
        "notes",
    ):
        if field in profile_data:
            record[field] = profile_data[field]

    wallet_profile = profile_data.get("wallet_profile")
    if wallet_profile is not None:
        if isinstance(wallet_profile, WalletProfile):
            record["wallet_profile"] = wallet_profile.to_dict()
        elif isinstance(wallet_profile, dict):
            record["wallet_profile"] = WalletProfile.from_payload(
                client_id,
                wallet_profile,
            ).to_dict()

    if record["risk_appetite"] is None:
        risk_tolerance = profile_data.get("risk_tolerance")
        if risk_tolerance is not None:
            record["risk_appetite"] = assess_risk_appetite(profile_data)

    return record


def log_interaction(entry: dict[str, Any]) -> dict[str, Any]:
    guardrails = GuardrailProcessor()

    def safe_items(values: Any) -> list[str]:
        if isinstance(values, str):
            values = [values]
        safe_values = []
        for value in values or []:
            if not isinstance(value, str):
                continue
            result = guardrails.process_input(value)
            safe_values.append(result.sanitized_message if not result.blocked else "[REDACTED]")
        return safe_values

    topics = entry.get("topics_discussed", entry.get("topics", []))
    preferences = entry.get("client_preferences", entry.get("preferences", []))
    topics = safe_items(topics)
    preferences = safe_items(preferences)

    follow_up_actions = entry.get("follow_up_actions")
    if follow_up_actions is None:
        follow_up = entry.get("follow_up")
        if isinstance(follow_up, str) and follow_up.strip():
            follow_up_actions = [{"action": follow_up}]
        elif isinstance(follow_up, dict):
            follow_up_actions = [follow_up]
        else:
            follow_up_actions = []
    if isinstance(follow_up_actions, list):
        follow_up_actions = [
            {
                **action,
                "action": safe_items(action.get("action", ""))[0],
            }
            for action in follow_up_actions
            if isinstance(action, dict)
        ]

    summary_fields: dict[str, Any] = {
        "client_id": entry.get("client_id", ""),
        "session_id": entry.get("session_id", ""),
        "topics_discussed": topics,
        "client_preferences": preferences,
        "follow_up_actions": follow_up_actions,
        "segment_flags": entry.get("segment_flags", []),
        "escalation_id": entry.get("escalation_id"),
    }
    if entry.get("interaction_date") is not None:
        summary_fields["interaction_date"] = entry["interaction_date"]
    summary = InteractionSummary(**summary_fields).model_dump(mode="json")
    summary["topics"] = summary["topics_discussed"]
    summary["preferences"] = summary["client_preferences"]
    summary["follow_up"] = (
        summary["follow_up_actions"][0]["action"] if summary["follow_up_actions"] else None
    )
    return {"summary": summary}


def create_followup_reminder(client_id: str, message: str) -> dict[str, str]:
    return {
        "client_id": client_id,
        "message": message,
        "reminder_type": "follow_up",
    }
