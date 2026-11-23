"""Fee Waiver Matrix and preferential pricing management. Traces: R23."""
from __future__ import annotations

from config.models import FeeWaiverMatrix


# Default fee waiver matrix — configurable without code changes (R23.4)
DEFAULT_FEE_WAIVER_MATRIX = FeeWaiverMatrix(
    tier_waivers={
        "basic": [],
        "preferred": ["annual_maintenance_fee"],
        "premium": [
            "annual_maintenance_fee",
            "transaction_fees",
            "demand_draft_charges",
        ],
        "ultra-premium": [
            "annual_maintenance_fee",
            "transaction_fees",
            "demand_draft_charges",
            "locker_charges",
            "forex_markup",
        ],
    },
    tier_pricing={
        "basic": {"forex_rate": "standard", "loan_rate_discount": "0%"},
        "preferred": {"forex_rate": "standard - 0.10%", "loan_rate_discount": "0.25%"},
        "premium": {"forex_rate": "standard - 0.25%", "loan_rate_discount": "0.50%"},
        "ultra-premium": {"forex_rate": "standard - 0.50%", "loan_rate_discount": "0.75%"},
    },
)

# Keywords that indicate fee-related context for proactive surfacing (R23.3)
_FEE_CONTEXT_KEYWORDS = [
    "fee", "charge", "waiver", "annual", "maintenance",
    "transaction fee", "forex", "locker", "demand draft",
]


class FeeWaiverManager:
    """Looks up tier-based fee waivers and preferential pricing.

    Traces: R23.1, R23.2, R23.3, R23.4, R23.5.
    """

    def __init__(self, matrix: FeeWaiverMatrix | None = None):
        self.matrix = matrix or DEFAULT_FEE_WAIVER_MATRIX

    def get_waivers(self, tier_name: str) -> list[str]:
        """Return applicable fee waivers for a tier. Traces: R23.2."""
        return list(self.matrix.tier_waivers.get(tier_name, []))

    def get_preferential_pricing(self, tier_name: str) -> dict[str, str]:
        """Return preferential pricing for a tier. Traces: R23.2."""
        return dict(self.matrix.tier_pricing.get(tier_name, {}))

    def is_fee_context_relevant(self, interaction_text: str) -> bool:
        """Check if interaction context is relevant to fee waivers. Traces: R23.3."""
        text_lower = interaction_text.lower()
        return any(kw in text_lower for kw in _FEE_CONTEXT_KEYWORDS)

    def build_waiver_summary(self, tier_name: str) -> str:
        """Build a human-readable summary of waivers and pricing for explainability.

        Traces: R23.5.
        """
        waivers = self.get_waivers(tier_name)
        pricing = self.get_preferential_pricing(tier_name)
        parts: list[str] = []
        if waivers:
            parts.append(f"Fee waivers: {', '.join(w.replace('_', ' ') for w in waivers)}.")
        if pricing:
            pricing_str = "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in pricing.items())
            parts.append(f"Preferential pricing: {pricing_str}.")
        return " ".join(parts) if parts else "No special waivers or pricing for this tier."

    def enrich_explainability(
        self, tier_name: str, existing_summary: str, interaction_text: str
    ) -> str:
        """Append waiver/pricing info to explainability summary when context is relevant.

        Traces: R23.3, R23.5.
        """
        if not self.is_fee_context_relevant(interaction_text):
            return existing_summary
        waiver_info = self.build_waiver_summary(tier_name)
        if existing_summary:
            return f"{existing_summary} {waiver_info}"
        return waiver_info
