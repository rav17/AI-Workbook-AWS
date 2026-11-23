"""Investment Advisor worker agent. Traces: R5, R21."""
from agents.workers.base import WorkerAgent
from config.settings import AgentConfig
from tools.financial_tools import investment_data_api

INVESTMENT_SYSTEM_PROMPT = """You are an Investment Advisor agent for a personal banking AI system.
Your job is to provide risk-aware investment recommendations including wealth management guidance.

Capabilities:
- Investment advisory (stocks, bonds, mutual funds, ETFs)
- Demat account management guidance
- Trading support
- Forex advisory with tier-specific preferential rates
- Wealth management recommendations (structured products, portfolio management services, alternative investments)

When given a task:
1. Use investment_data_api to get market data
2. Categorize each recommendation with risk_level (low/medium/high)
3. Include an explainability_summary describing your reasoning
4. If past failures are mentioned, factor them in and AVOID repeating poor advice
5. Tailor product recommendations to the user's tier-eligible product set

Always respond with ONLY a JSON object:
{"status":"success/failure","confidence":"high/medium/low","recommendation":"your investment advice","risk_level":"low/medium/high","issues":[],"explainability_summary":"reasoning behind recommendation"}

IMPORTANT: Always include explainability. Never guarantee returns.
"""

# Tier-eligible product sets (R21.2, R21.3)
TIER_INVESTMENT_PRODUCTS: dict[str, list[str]] = {
    "basic": ["mutual_funds", "fixed_deposits", "recurring_deposits"],
    "preferred": [
        "mutual_funds", "fixed_deposits", "recurring_deposits",
        "demat_account", "equity_trading", "bonds",
    ],
    "premium": [
        "mutual_funds", "fixed_deposits", "recurring_deposits",
        "demat_account", "equity_trading", "bonds",
        "structured_products", "portfolio_management_services", "forex_advisory",
    ],
    "ultra-premium": [
        "mutual_funds", "fixed_deposits", "recurring_deposits",
        "demat_account", "equity_trading", "bonds",
        "structured_products", "portfolio_management_services", "forex_advisory",
        "alternative_investments", "private_equity", "wealth_management",
    ],
}

# Tier-specific forex rate preferences (R21.5)
TIER_FOREX_RATES: dict[str, str] = {
    "basic": "standard rate",
    "preferred": "standard rate - 0.10%",
    "premium": "standard rate - 0.25%",
    "ultra-premium": "standard rate - 0.50%",
}


def get_tier_investment_products(tier: str) -> list[str]:
    """Return tier-eligible investment products. Traces: R21.2."""
    return list(TIER_INVESTMENT_PRODUCTS.get(tier, TIER_INVESTMENT_PRODUCTS["basic"]))


def get_forex_rate_info(tier: str) -> str:
    """Return tier-specific forex rate info. Traces: R21.5."""
    return TIER_FOREX_RATES.get(tier, TIER_FOREX_RATES["basic"])


def create_investment_advisor(config: AgentConfig) -> WorkerAgent:
    return WorkerAgent(
        domain="investment_advice",
        config=config,
        tools=[investment_data_api],
        system_prompt=INVESTMENT_SYSTEM_PROMPT,
    )
