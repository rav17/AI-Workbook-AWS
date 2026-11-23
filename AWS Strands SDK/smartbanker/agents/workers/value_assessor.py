"""Value Assessor worker agent. Traces: R39."""
from __future__ import annotations

from agents.workers.base import WorkerAgent
from config.models import (
    ExecutionResult,
    ValueAssessmentResult,
    Status,
    Confidence,
    RiskLevel,
)
from config.settings import AgentConfig
from tools.financial_tools import activity_analyzer, tier_benefit_mapper

VALUE_ASSESSOR_SYSTEM_PROMPT = """You are a Value Assessor agent for a personal banking AI system.
Your job is to analyze a user's banking activity against their programme tier benefits
and provide an honest value assessment.

When given a task:
1. Use the activity_analyzer tool to retrieve user banking activity metrics
2. Use the tier_benefit_mapper tool to get the user's tier benefits
3. Compare activity against available benefits to determine utilization
4. Calculate a value score (0.0 to 1.0) based on benefit utilization
5. Recommend tier changes when appropriate — including honest downgrade suggestions

IMPORTANT: Be honest. If a user on a premium tier is only using basic self-service
features, recommend a downgrade to save them money. The user's interest comes first.

Always respond with ONLY a JSON object:
{"status":"success/failure","confidence":"high/medium/low","recommendation":"value assessment",
"risk_level":"low/medium/high","issues":[],"explainability_summary":"assessment rationale"}
"""

# Benefits that map to basic self-service usage
_BASIC_BENEFITS = {"standard_checking", "debit_card", "online_banking"}

# Tier ordering for upgrade/downgrade logic
_TIER_ORDER = ["basic", "preferred", "premium", "ultra-premium"]


class ValueAssessorAgent(WorkerAgent):
    """Analyzes user banking activity against tier benefits for value assessment.

    Traces: R39.1, R39.2, R39.3, R39.4, R39.5.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(
            domain="value_assessment",
            config=config,
            tools=[activity_analyzer, tier_benefit_mapper],
            system_prompt=VALUE_ASSESSOR_SYSTEM_PROMPT,
        )

    def assess_value(
        self,
        user_id: str,
        tier: str,
        activity: dict,
    ) -> ValueAssessmentResult:
        """Generate value assessment comparing activity against tier benefits.

        Compares the user's actual banking activity against the benefits
        available at their current tier. Honestly recommends downgrade when
        basic self-service is sufficient. Traces: R39.1–R39.5.
        """
        import json as _json

        # Get tier benefits
        raw_benefits = _json.loads(tier_benefit_mapper(user_tier=tier))
        all_benefits = [b["benefit"] for b in raw_benefits.get("benefits", [])]

        # Determine which benefits the user actually utilizes
        services_used = set(activity.get("services_used", []))
        utilized = [b for b in all_benefits if b in services_used]
        unused = [b for b in all_benefits if b not in services_used]

        # Calculate value score: ratio of utilized to total benefits
        value_score = len(utilized) / len(all_benefits) if all_benefits else 0.0

        # Determine if basic self-service is sufficient (R39.4)
        self_service_sufficient = services_used.issubset(_BASIC_BENEFITS)

        # Build tier recommendation
        tier_recommendation = self._build_tier_recommendation(
            tier, value_score, self_service_sufficient, utilized, unused
        )

        return ValueAssessmentResult(
            user_id=user_id,
            current_tier=tier,
            activity_summary=activity,
            utilized_benefits=utilized,
            unused_benefits=unused,
            value_score=round(value_score, 2),
            tier_recommendation=tier_recommendation,
            self_service_sufficient=self_service_sufficient,
        )

    def _build_tier_recommendation(
        self,
        current_tier: str,
        value_score: float,
        self_service_sufficient: bool,
        utilized: list[str],
        unused: list[str],
    ) -> dict:
        """Build an honest tier recommendation based on value analysis."""
        current_idx = _TIER_ORDER.index(current_tier) if current_tier in _TIER_ORDER else 0

        # Honest downgrade recommendation when premium services aren't used (R39.4)
        if self_service_sufficient and current_idx > 0:
            return {
                "action": "downgrade",
                "suggested_tier": "basic",
                "rationale": (
                    f"Your current usage ({', '.join(utilized)}) is limited to basic "
                    f"self-service features. A basic tier would provide the same services "
                    f"at lower cost. Unused benefits: {', '.join(unused)}."
                ),
            }

        # Low value score — suggest downgrade one tier
        if value_score < 0.4 and current_idx > 0:
            suggested = _TIER_ORDER[current_idx - 1]
            return {
                "action": "downgrade",
                "suggested_tier": suggested,
                "rationale": (
                    f"Value score {value_score:.0%} indicates low utilization of "
                    f"{current_tier} benefits. Consider {suggested} tier to better "
                    f"match your usage. Unused: {', '.join(unused)}."
                ),
            }

        # High value score — suggest upgrade if not at top
        if value_score > 0.8 and current_idx < len(_TIER_ORDER) - 1:
            suggested = _TIER_ORDER[current_idx + 1]
            return {
                "action": "upgrade",
                "suggested_tier": suggested,
                "rationale": (
                    f"Value score {value_score:.0%} shows strong utilization of "
                    f"{current_tier} benefits. You may benefit from {suggested} tier "
                    f"for additional features."
                ),
            }

        # Good fit — maintain current tier
        return {
            "action": "maintain",
            "suggested_tier": current_tier,
            "rationale": (
                f"Value score {value_score:.0%} indicates good alignment between "
                f"your usage and {current_tier} tier benefits."
            ),
        }


def create_value_assessor(config: AgentConfig) -> ValueAssessorAgent:
    """Factory function for ValueAssessorAgent."""
    return ValueAssessorAgent(config)
