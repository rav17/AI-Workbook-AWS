from __future__ import annotations

from typing import Any


def get_risk_questionnaire() -> list[str]:
    return [
        "What is your investment time horizon?",
        "How would you react to a 15% market decline?",
        "Are you comfortable with market-linked products that can move up or down?",
        "How important is liquidity when considering investments?",
    ]


def assess_risk_appetite(profile: dict[str, Any]) -> str:
    if not isinstance(profile, dict):
        raise TypeError("profile must be a dictionary")

    raw_risk_appetite = str(profile.get("risk_appetite", "")).strip().lower()
    normalized = {
        "conservative": "conservative",
        "moderate": "moderate",
        "aggressive": "high",
        "high": "high",
        "low": "conservative",
    }
    if raw_risk_appetite in normalized:
        return normalized[raw_risk_appetite]

    raw_tolerance = profile.get("risk_tolerance", profile.get("risk_score", 5))
    try:
        risk_tolerance = float(raw_tolerance or 0)
    except (TypeError, ValueError):
        risk_tolerance = 5.0

    if risk_tolerance <= 2:
        return "conservative"
    if risk_tolerance >= 7:
        return "high"
    return "moderate"
