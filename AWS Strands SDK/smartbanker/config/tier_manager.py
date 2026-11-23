"""Programme Tier management logic. Traces: R18."""
from __future__ import annotations

from config.models import ProgrammeTier


# Default tier definitions — configurable without code changes (R18.4)
DEFAULT_TIERS: list[ProgrammeTier] = [
    ProgrammeTier(name="basic", min_balance=0.0, salary_credit=0.0, benefits=[
        "standard_checking", "debit_card", "online_banking",
    ]),
    ProgrammeTier(name="preferred", min_balance=25_000.0, salary_credit=50_000.0, benefits=[
        "standard_checking", "debit_card", "online_banking",
        "reduced_fees", "priority_support",
    ]),
    ProgrammeTier(name="premium", min_balance=100_000.0, salary_credit=150_000.0, benefits=[
        "standard_checking", "debit_card", "online_banking",
        "reduced_fees", "priority_support", "lounge_access",
        "wealth_advisory", "preferential_rates",
    ]),
    ProgrammeTier(name="ultra-premium", min_balance=500_000.0, salary_credit=500_000.0, benefits=[
        "standard_checking", "debit_card", "online_banking",
        "reduced_fees", "priority_support", "lounge_access",
        "wealth_advisory", "preferential_rates", "concierge", "insurance_coverage",
    ]),
]

# Canonical tier ordering from lowest to highest
_TIER_ORDER = ["basic", "preferred", "premium", "ultra-premium"]


class TierManager:
    """Manages Programme Tier retrieval, eligibility evaluation, and product filtering.

    Traces: R18.1, R18.2, R18.3, R18.4, R18.5.
    """

    def __init__(self, tiers: list[ProgrammeTier] | None = None):
        self.tiers = {t.name: t for t in (tiers or DEFAULT_TIERS)}

    def get_tier(self, tier_name: str) -> ProgrammeTier | None:
        """Retrieve a tier definition by name. Traces: R18.2."""
        return self.tiers.get(tier_name)

    def get_tier_benefits(self, tier_name: str) -> list[str]:
        """Return benefits for a given tier. Traces: R18.5."""
        tier = self.tiers.get(tier_name)
        return list(tier.benefits) if tier else []

    def evaluate_eligibility(
        self, current_tier: str, balance: float, salary_credit: float
    ) -> str | None:
        """Evaluate if user qualifies for a higher tier. Returns upgrade tier name or None.

        Traces: R18.3.
        """
        current_idx = _TIER_ORDER.index(current_tier) if current_tier in _TIER_ORDER else 0
        for tier_name in reversed(_TIER_ORDER):
            tier = self.tiers.get(tier_name)
            if tier is None:
                continue
            tier_idx = _TIER_ORDER.index(tier_name)
            if tier_idx <= current_idx:
                continue
            if balance >= tier.min_balance and salary_credit >= tier.salary_credit:
                return tier_name
        return None

    def check_downgrade_risk(
        self, current_tier: str, balance: float, salary_credit: float
    ) -> bool:
        """Check if user is at risk of tier downgrade. Traces: R18.3."""
        tier = self.tiers.get(current_tier)
        if tier is None or current_tier == "basic":
            return False
        return balance < tier.min_balance or salary_credit < tier.salary_credit

    def filter_products_by_tier(
        self, tier_name: str, all_products: list[str]
    ) -> list[str]:
        """Filter products/benefits available for a given tier. Traces: R18.5."""
        benefits = set(self.get_tier_benefits(tier_name))
        return [p for p in all_products if p in benefits]
