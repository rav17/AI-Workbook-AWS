"""Lifestyle and travel perks awareness. Traces: R25."""
from __future__ import annotations


# Configurable tier-to-lifestyle benefits mapping (R25.1, R25.4)
TIER_LIFESTYLE_BENEFITS: dict[str, list[dict[str, str]]] = {
    "basic": [],
    "preferred": [
        {"perk": "dining_offers", "description": "10% off at partner restaurants"},
        {"perk": "cashback_programme", "description": "0.5% cashback on select purchases"},
    ],
    "premium": [
        {"perk": "lounge_access", "description": "4 complimentary airport lounge visits per quarter"},
        {"perk": "dining_offers", "description": "15% off at partner restaurants"},
        {"perk": "cashback_programme", "description": "1% cashback on all purchases"},
        {"perk": "reward_acceleration", "description": "2x reward points on travel and dining"},
    ],
    "ultra-premium": [
        {"perk": "lounge_access", "description": "Unlimited airport lounge access worldwide"},
        {"perk": "dining_offers", "description": "20% off at premium partner restaurants"},
        {"perk": "cashback_programme", "description": "2% cashback on all purchases"},
        {"perk": "reward_acceleration", "description": "3x reward points on travel and dining"},
        {"perk": "concierge_travel", "description": "Dedicated travel concierge service"},
        {"perk": "hotel_upgrades", "description": "Complimentary room upgrades at partner hotels"},
    ],
}

# Keywords indicating travel/lifestyle context (R25.2)
_LIFESTYLE_KEYWORDS = [
    "travel", "lounge", "airport", "dining", "restaurant",
    "cashback", "reward", "hotel", "vacation", "trip",
    "lifestyle", "perk", "benefit",
]


def get_lifestyle_benefits(tier_name: str) -> list[dict[str, str]]:
    """Return lifestyle benefits for a tier. Traces: R25.1."""
    return list(TIER_LIFESTYLE_BENEFITS.get(tier_name, []))


def is_lifestyle_context(interaction_text: str) -> bool:
    """Check if interaction context is relevant to lifestyle/travel. Traces: R25.2."""
    text_lower = interaction_text.lower()
    return any(kw in text_lower for kw in _LIFESTYLE_KEYWORDS)


def build_lifestyle_summary(tier_name: str) -> str:
    """Build a human-readable summary of lifestyle perks. Traces: R25.3."""
    benefits = get_lifestyle_benefits(tier_name)
    if not benefits:
        return "No lifestyle perks available for this tier."
    parts = [f"{b['perk'].replace('_', ' ')}: {b['description']}" for b in benefits]
    return "Lifestyle perks: " + "; ".join(parts) + "."
