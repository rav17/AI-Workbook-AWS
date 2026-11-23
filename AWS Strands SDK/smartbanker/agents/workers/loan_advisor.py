"""Loan Advisor worker agent. Traces: R20, R30, R35."""
from __future__ import annotations

from agents.workers.base import WorkerAgent
from config.models import (
    ExecutionResult,
    MemoryContext,
    PlanTask,
    Status,
    Confidence,
    RiskLevel,
)
from config.settings import AgentConfig, PriorityConfig
from compliance.disclosure_manager import LOAN_DISCLAIMER
from tools.financial_tools import loan_product_catalog, tier_pricing_engine

LOAN_SYSTEM_PROMPT = """You are a Loan Advisor agent for a personal banking AI system.
Your job is to advise users on suitable loan products with tier-specific preferential pricing.

Supported loan types:
- Personal loans
- Auto loans
- Property-backed loans
- Working capital facilities

When given a task:
1. Use the loan_product_catalog tool to retrieve available loan products
2. Use the tier_pricing_engine tool to apply tier-specific preferential pricing
3. Evaluate user eligibility and recommend the best loan product
4. Include an explainability_summary describing factors influencing the recommendation
5. ALWAYS include the loan approval limitation disclaimer

MANDATORY DISCLAIMER (must appear in every response):
"Facilitation improves chances but does not guarantee approval. Final approval depends on
credit score, income verification, and risk assessment by the lending institution."

Always respond with ONLY a JSON object:
{"status":"success/failure","confidence":"high/medium/low","recommendation":"loan advice","risk_level":"low/medium/high","issues":[],"explainability_summary":"factors and tier benefits applied","facilitation_summary":"facilitation actions taken"}

If the user does not meet minimum eligibility, return status "failure" with unmet criteria in issues.
"""

# Tier-specific facilitation strategies (R30.1, R30.3)
_TIER_FACILITATION: dict[str, dict[str, object]] = {
    "basic": {
        "benefits": ["standard processing"],
        "rate_discount": "0%",
        "priority_processing": False,
    },
    "preferred": {
        "benefits": ["standard processing", "reduced documentation"],
        "rate_discount": "0.25%",
        "priority_processing": False,
    },
    "premium": {
        "benefits": ["standard processing", "reduced documentation", "priority processing", "relationship manager review"],
        "rate_discount": "0.50%",
        "priority_processing": True,
    },
    "ultra-premium": {
        "benefits": ["standard processing", "reduced documentation", "priority processing", "relationship manager review", "dedicated underwriter"],
        "rate_discount": "0.75%",
        "priority_processing": True,
    },
}

SUPPORTED_LOAN_TYPES = [
    "personal_loan",
    "auto_loan",
    "property_backed_loan",
    "working_capital_facility",
]


class LoanAdvisorAgent(WorkerAgent):
    """Provides loan advisory with tier-specific facilitation strategies.

    Traces: R20.1, R20.2, R20.3, R20.5, R20.6, R30.1–R30.5, R35.1–R35.4.
    """

    def __init__(self, config: AgentConfig, priority_config: PriorityConfig | None = None):
        super().__init__(
            domain="loan_advice",
            config=config,
            tools=[loan_product_catalog, tier_pricing_engine],
            system_prompt=LOAN_SYSTEM_PROMPT,
        )
        self.priority_config = priority_config or PriorityConfig()

    # ------------------------------------------------------------------
    # Loan facilitation (R20, R30, R35)
    # ------------------------------------------------------------------

    def facilitate_loan(
        self,
        task: PlanTask,
        context: MemoryContext,
        user_tier: str = "basic",
    ) -> ExecutionResult:
        """Facilitate a loan application with tier-specific strategies.

        Applies tier-based facilitation benefits, attaches the mandatory
        loan approval limitation disclaimer, and includes a facilitation
        summary in the result.  Traces: R30.1–R30.5, R35.1–R35.4.
        """
        facilitation = _TIER_FACILITATION.get(user_tier, _TIER_FACILITATION["basic"])
        benefits = facilitation["benefits"]
        rate_discount = facilitation["rate_discount"]

        facilitation_summary = (
            f"Tier: {user_tier}. Benefits applied: {', '.join(benefits)}. "
            f"Rate discount: {rate_discount}."
        )

        return ExecutionResult(
            status=Status.SUCCESS,
            confidence=Confidence.HIGH,
            recommendation=(
                f"Loan facilitation initiated for tier '{user_tier}'. "
                f"Applied benefits: {', '.join(benefits)}. "
                f"Preferential rate discount: {rate_discount}."
            ),
            risk_level=RiskLevel.MEDIUM,
            issues=[LOAN_DISCLAIMER],
            explainability_summary=(
                f"Loan recommendation based on programme tier '{user_tier}'. "
                f"Facilitation benefits: {', '.join(benefits)}. "
                f"Rate discount applied: {rate_discount}. "
                f"Task intent: {task.intent}."
            ),
            worker_domain=self.domain,
            facilitation_summary=facilitation_summary,
            disclaimer=LOAN_DISCLAIMER,
        )


def create_loan_advisor(
    config: AgentConfig, priority_config: PriorityConfig | None = None
) -> LoanAdvisorAgent:
    """Factory function for LoanAdvisorAgent."""
    return LoanAdvisorAgent(config, priority_config)
