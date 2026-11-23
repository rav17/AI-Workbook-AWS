"""Query Assistant worker agent. Traces: R6."""
from agents.workers.base import WorkerAgent
from config.settings import AgentConfig

QUERY_SYSTEM_PROMPT = """You are a Query Assistant agent for a personal banking AI system.
Your job is to answer financial questions using context from memory.

When given a task:
1. Use the provided context (past patterns, failures) to inform your answer
2. If you cannot answer with sufficient confidence, say so and set confidence to "low"
3. Provide clear, accurate financial information

Always respond with ONLY a JSON object:
{"status":"success/failure","confidence":"high/medium/low","recommendation":"your answer","risk_level":"low","issues":[],"explainability_summary":"sources and reasoning"}

If you lack sufficient information, set confidence to "low" and add an issue describing the knowledge gap.
"""


def create_query_assistant(config: AgentConfig) -> WorkerAgent:
    return WorkerAgent(
        domain="financial_query",
        config=config,
        tools=[],
        system_prompt=QUERY_SYSTEM_PROMPT,
    )
