from __future__ import annotations


def escalate_request(category: str, context: dict) -> dict:
    category_lower = category.lower()

    if "legal" in category_lower or "fraud" in category_lower or "freeze" in category_lower:
        team = "legal-and-risk"
        priority = "high"
    elif "estate" in category_lower or "treasury" in category_lower:
        team = "private-wealth"
        priority = "medium"
    elif "credit" in category_lower:
        team = "credit-underwriting"
        priority = "high"
    else:
        team = "relationship-team"
        priority = "medium"

    return {
        "client_id": context.get("client_id", "unknown"),
        "name": context.get("name", "Unknown"),
        "category": category,
        "team": team,
        "priority": priority,
        "status": "escalated",
    }
