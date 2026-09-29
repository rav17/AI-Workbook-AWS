from __future__ import annotations


def evaluate_maturity_event(event: dict) -> dict:
    days = int(event.get("days_to_maturity", 0))
    amount = float(event.get("amount", 0))

    if days <= 30:
        return {
            "status": "notify",
            "recommended_action": "review_reinvestment",
            "days_to_maturity": days,
            "amount": amount,
        }

    return {
        "status": "monitor",
        "recommended_action": "continue_tracking",
        "days_to_maturity": days,
        "amount": amount,
    }
