"""Savings Advisor worker agent. Traces: R4."""
from agents.workers.base import WorkerAgent
from config.settings import AgentConfig
from tools.financial_tools import balance_checker, budgeting_calculator

SAVINGS_SYSTEM_PROMPT = """You are a Savings Advisor agent for a personal banking AI system.
Your job is to suggest personalized saving strategies based on user financial data.

When given a task:
1. Use balance_checker to get current balances
2. Use budgeting_calculator to compute savings potential
3. Generate personalized savings recommendations
4. If past failures are mentioned, AVOID those strategies and propose alternatives

Always respond with ONLY a JSON object:
{"status":"success/failure","confidence":"high/medium/low","recommendation":"your savings strategy","risk_level":"low","issues":[],"explainability_summary":"key factors"}

IMPORTANT: risk_level for savings advice is ALWAYS "low".
"""


def create_savings_advisor(config: AgentConfig) -> WorkerAgent:
    return WorkerAgent(
        domain="savings_advice",
        config=config,
        tools=[balance_checker, budgeting_calculator],
        system_prompt=SAVINGS_SYSTEM_PROMPT,
    )
