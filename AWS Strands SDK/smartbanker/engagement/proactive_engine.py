"""Proactive Engagement Engine. Traces: R37."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from config.models import (
    InteractionRecord,
    ProactiveNotification,
    SimilarPattern,
)


@dataclass
class DetectedOpportunity:
    """An actionable opportunity detected from user interaction/pattern data."""

    opportunity_type: str  # matches ProactiveNotification.opportunity_type literals
    description: str
    priority: str = "medium"  # low, medium, high
    tier_specific: bool = False
    metadata: dict | None = None


# Pattern keywords used to detect opportunities from interaction/pattern data
_OPPORTUNITY_KEYWORDS: dict[str, list[str]] = {
    "fee_waiver_expiry": ["fee waiver", "waiver expir", "fee renewal", "annual fee"],
    "investment_maturity": ["maturity", "investment matur", "bond matur", "fixed deposit"],
    "tier_upgrade_eligibility": ["tier upgrade", "upgrade eligib", "higher tier", "balance increase"],
    "promotional_offer": ["promotion", "offer", "discount", "cashback", "reward"],
    "tier_downgrade_risk": ["downgrade", "balance drop", "below minimum", "tier risk"],
    "savings_opportunity": ["savings", "save more", "high interest", "deposit opportunity"],
}


class ProactiveEngagementEngine:
    """Detects and surfaces proactive financial opportunities, alerts, and recommendations.

    Scans user memory patterns and detects opportunities for proactive
    notifications. Traces: R37.1, R37.2, R37.3, R37.4.
    """

    def scan_for_opportunities(
        self, user_id: str, tier: str
    ) -> list[ProactiveNotification]:
        """Scan user history and patterns for proactive engagement opportunities.

        Returns notifications for fee waiver expiry, investment maturity,
        tier upgrade eligibility, promotional offers, tier downgrade risk,
        and savings opportunities. Traces: R37.1.
        """
        # In production, this would retrieve interactions and patterns from memory.
        # Here we provide the interface; callers pass data via detect_patterns.
        return []

    def generate_notification(
        self, opportunity: DetectedOpportunity, user_id: str
    ) -> ProactiveNotification:
        """Generate a user-facing proactive notification from a detected opportunity.

        Traces: R37.2.
        """
        return ProactiveNotification(
            user_id=user_id,
            opportunity_type=opportunity.opportunity_type,
            message=opportunity.description,
            priority=opportunity.priority,
            tier_specific=opportunity.tier_specific,
        )

    def detect_patterns(
        self,
        interactions: list[InteractionRecord],
        patterns: list[SimilarPattern],
    ) -> list[DetectedOpportunity]:
        """Analyze STM+LTM data to detect actionable opportunities.

        Scans interaction records and similar patterns for keywords that
        indicate fee waiver expiry, investment maturity, tier upgrade
        eligibility, promotional offers, tier downgrade risk, and savings
        opportunities. Traces: R37.3.
        """
        detected: list[DetectedOpportunity] = []
        seen_types: set[str] = set()

        # Build a combined text corpus from interactions and patterns
        texts: list[str] = []
        for interaction in interactions:
            texts.append(interaction.input.lower())
            texts.append(interaction.output.lower())
        for pattern in patterns:
            texts.append(pattern.content.lower())

        combined = " ".join(texts)

        for opp_type, keywords in _OPPORTUNITY_KEYWORDS.items():
            if opp_type in seen_types:
                continue
            for kw in keywords:
                if kw in combined:
                    detected.append(
                        DetectedOpportunity(
                            opportunity_type=opp_type,
                            description=self._build_description(opp_type, kw),
                            priority=self._assess_priority(opp_type),
                            tier_specific=opp_type in {
                                "tier_upgrade_eligibility",
                                "tier_downgrade_risk",
                            },
                        )
                    )
                    seen_types.add(opp_type)
                    break

        return detected

    @staticmethod
    def _build_description(opportunity_type: str, matched_keyword: str) -> str:
        """Build a human-readable description for a detected opportunity."""
        descriptions = {
            "fee_waiver_expiry": (
                "Your fee waiver may be expiring soon. Review your account to "
                "ensure continued waiver eligibility."
            ),
            "investment_maturity": (
                "One or more of your investments are approaching maturity. "
                "Consider reinvestment options to maintain returns."
            ),
            "tier_upgrade_eligibility": (
                "Based on your recent activity, you may be eligible for a "
                "programme tier upgrade with additional benefits."
            ),
            "promotional_offer": (
                "There are promotional offers available that may benefit you "
                "based on your banking activity."
            ),
            "tier_downgrade_risk": (
                "Your account activity indicates a risk of tier downgrade. "
                "Review the minimum requirements to maintain your current tier."
            ),
            "savings_opportunity": (
                "We've identified potential savings opportunities based on "
                "your transaction patterns."
            ),
        }
        return descriptions.get(
            opportunity_type,
            f"Opportunity detected related to: {matched_keyword}",
        )

    @staticmethod
    def _assess_priority(opportunity_type: str) -> str:
        """Assess priority level for an opportunity type."""
        high_priority = {"fee_waiver_expiry", "tier_downgrade_risk"}
        low_priority = {"promotional_offer"}
        if opportunity_type in high_priority:
            return "high"
        if opportunity_type in low_priority:
            return "low"
        return "medium"
