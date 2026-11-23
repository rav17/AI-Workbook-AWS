"""Spending Analyzer worker agent. Traces: R3, R24."""
from agents.workers.base import WorkerAgent
from config.settings import AgentConfig
from tools.financial_tools import transaction_fetcher

SPENDING_SYSTEM_PROMPT = """You are a Spending Analyzer agent for a personal banking AI system.
Your job is to analyze user transactions and detect spending patterns.

When given a task:
1. Use the transaction_fetcher tool to get transaction data
2. Categorize transactions and identify patterns (recurring expenses, anomalies, category breakdowns)
3. Return a structured JSON ExecutionResult

Always respond with ONLY a JSON object:
{"status":"success/failure","confidence":"high/medium/low","recommendation":"your analysis","risk_level":"low/medium/high","issues":[],"explainability_summary":"key factors"}

Set risk_level based on spending health (overspending = high risk).
"""

# Tier-appropriate card product recommendations (R24.1, R24.2, R24.5)
TIER_CARD_PRODUCTS: dict[str, dict] = {
    "basic": {
        "debit_card": "Standard Debit Card",
        "credit_card": "Classic Credit Card",
        "transaction_limit": "50,000/day",
        "reward_rate": "0.5%",
    },
    "preferred": {
        "debit_card": "Preferred Debit Card",
        "credit_card": "Gold Credit Card",
        "transaction_limit": "200,000/day",
        "reward_rate": "1.0%",
    },
    "premium": {
        "debit_card": "Premium Debit Card",
        "credit_card": "Platinum Credit Card",
        "transaction_limit": "500,000/day",
        "reward_rate": "1.5%",
    },
    "ultra-premium": {
        "debit_card": "Ultra-Premium Debit Card",
        "credit_card": "Black Credit Card",
        "transaction_limit": "Unlimited",
        "reward_rate": "2.0%",
    },
}


def get_card_recommendations(user_tier: str) -> dict:
    """Return tier-appropriate card product recommendations. Traces: R24.1, R24.2."""
    return dict(TIER_CARD_PRODUCTS.get(user_tier, TIER_CARD_PRODUCTS["basic"]))


def identify_reward_optimization(user_tier: str, spending_categories: list[str]) -> str:
    """Identify reward point optimization opportunities. Traces: R24.3."""
    products = TIER_CARD_PRODUCTS.get(user_tier, TIER_CARD_PRODUCTS["basic"])
    reward_rate = products.get("reward_rate", "0.5%")
    if not spending_categories:
        return f"Current reward rate: {reward_rate}. No spending categories to optimize."
    top_categories = spending_categories[:3]
    return (
        f"Current reward rate: {reward_rate}. "
        f"Top spending categories: {', '.join(top_categories)}. "
        f"Consider using your {products.get('credit_card', 'credit card')} "
        f"for these categories to maximize rewards."
    )


def create_spending_analyzer(config: AgentConfig) -> WorkerAgent:
    return WorkerAgent(
        domain="spending_analysis",
        config=config,
        tools=[transaction_fetcher],
        system_prompt=SPENDING_SYSTEM_PROMPT,
    )
