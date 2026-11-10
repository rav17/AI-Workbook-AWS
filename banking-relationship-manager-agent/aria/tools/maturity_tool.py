from __future__ import annotations

from typing import Any

from aria.constants import MATURITY_NOTIFICATION_DAYS, OUTFLOW_THRESHOLD


def _build_reinvestment_options(rate_reference: str = "current bank offer") -> list[dict[str, str]]:
    return [
        {
            "name": "Rollover into a fixed deposit",
            "rate": rate_reference,
            "benefit": "Lock in the current fixed-deposit rate while preserving principal.",
        },
        {
            "name": "Rebalance into a diversified portfolio",
            "rate": rate_reference,
            "benefit": "Align your allocation with your risk profile and short-term goals.",
        },
    ]


def evaluate_maturity_event(event: dict[str, Any]) -> dict[str, Any]:
    days = int(event.get("days_to_maturity", event.get("days_until_maturity", 0)))
    amount = float(event.get("amount", 0))

    if days <= 30:
        return {
            "status": "notify",
            "recommended_action": "review_reinvestment",
            "days_to_maturity": days,
            "amount": amount,
            "reinvestment_options": _build_reinvestment_options(),
            "rate_reference": "Current bank fixed-deposit rates",
        }

    return {
        "status": "monitor",
        "recommended_action": "continue_tracking",
        "days_to_maturity": days,
        "amount": amount,
        "reinvestment_options": _build_reinvestment_options(),
    }


def evaluate_outflow_event(event: dict[str, Any]) -> dict[str, Any]:
    amount = float(event.get("amount", 0))
    threshold = float(event.get("threshold_amount", OUTFLOW_THRESHOLD))
    if amount >= threshold:
        return {
            "status": "alert",
            "recommended_action": "rebalance_portfolio",
            "amount": amount,
            "threshold_amount": threshold,
        }
    return {
        "status": "monitor",
        "recommended_action": "continue_tracking",
        "amount": amount,
        "threshold_amount": threshold,
    }


def check_upcoming_maturities(
    client_id: str,
    days_ahead: int = MATURITY_NOTIFICATION_DAYS,
) -> list[dict[str, Any]]:
    return [
        {
            "client_id": client_id,
            "days_to_maturity": min(days_ahead, MATURITY_NOTIFICATION_DAYS),
            "amount": 150000.0,
            "status": "notify",
            "recommended_action": "review_reinvestment",
        }
    ]


def detect_large_outflows(
    client_id: str,
    threshold_amount: float = OUTFLOW_THRESHOLD,
) -> list[dict[str, Any]]:
    return [
        {
            "client_id": client_id,
            "amount": threshold_amount * 1.5,
            "threshold_amount": threshold_amount,
            "status": "alert",
            "recommended_action": "rebalance_portfolio",
        }
    ]
