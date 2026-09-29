from __future__ import annotations

from typing import Any


def get_risk_questionnaire() -> list[str]:
    return [
        "What is your investment time horizon?",
        "How would you react to a 15% market decline?",
        "Are you comfortable with market-linked products that can move up or down?",
    ]


def assess_risk_appetite(profile: dict[str, Any]) -> str:
    risk_tolerance = int(profile.get("risk_tolerance", 5))

    if risk_tolerance <= 2:
        return "conservative"
    if risk_tolerance >= 7:
        return "high"
    return "moderate"
