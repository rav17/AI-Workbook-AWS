"""SmartBanker entry point — AgentCore Runtime compatible.

Wraps the multi-agent system with BedrockAgentCoreApp for deployment
to AgentCore Runtime. Tools are accessed via AgentCore Gateway (MCP).

Local mode:  python main.py (uses local tools, no AWS required)
AgentCore:   agentcore launch (deploys to AgentCore Runtime)

Traces: R16, R17.
"""
from __future__ import annotations

import os
import sys

from config.settings import AgentConfig, MemoryConfig, AppConfig
from config.models import FinalResponse
from agents.coordinator import CoordinatorAgent
from agents.workers.spending_analyzer import create_spending_analyzer
from agents.workers.savings_advisor import create_savings_advisor
from agents.workers.investment_advisor import create_investment_advisor
from agents.workers.query_assistant import create_query_assistant
from agents.workers.risk_compliance import create_risk_compliance
from agents.workers.loan_advisor import create_loan_advisor
from agents.workers.service_request_handler import create_service_request_handler
from agents.workers.value_assessor import create_value_assessor


def create_app(config: AppConfig | None = None) -> CoordinatorAgent:
    """Create and configure the SmartBanker agent system."""
    if config is None:
        config = AppConfig()

    coordinator = CoordinatorAgent(config.agent, config.memory)

    # Register Phase 1 worker agents with the delegator
    coordinator.delegator.register_worker("spending_analysis", create_spending_analyzer(config.agent))
    coordinator.delegator.register_worker("savings_advice", create_savings_advisor(config.agent))
    coordinator.delegator.register_worker("investment_advice", create_investment_advisor(config.agent))
    coordinator.delegator.register_worker("financial_query", create_query_assistant(config.agent))

    # Risk agent is both a worker and used directly by coordinator
    risk_agent = create_risk_compliance(config.agent)
    coordinator.delegator.register_worker("risk_compliance", risk_agent)
    coordinator.risk_agent = risk_agent

    # Register Phase 2 worker agents
    coordinator.delegator.register_worker(
        "loan_advice", create_loan_advisor(config.agent, config.priority)
    )
    coordinator.delegator.register_worker(
        "service_request", create_service_request_handler(config.agent, config.priority)
    )
    coordinator.delegator.register_worker(
        "value_assessment", create_value_assessor(config.agent)
    )

    return coordinator


# ---------------------------------------------------------------------------
# AgentCore Runtime entry point
# ---------------------------------------------------------------------------

try:
    from bedrock_agentcore import BedrockAgentCoreApp

    agentcore_app = BedrockAgentCoreApp()

    @agentcore_app.entrypoint
    def invoke(payload: dict) -> dict:
        """AgentCore Runtime entry point.

        Receives requests routed through AgentCore Gateway.
        Tools are exposed as Lambda targets on the Gateway and
        accessed by worker agents via MCP.
        """
        app = create_app()
        user_id = payload.get("user_id", "anonymous")
        request = payload.get("prompt", payload.get("request", ""))
        response = app.process_request(user_id, request)
        return {"response": response.model_dump()}

except ImportError:
    # bedrock-agentcore not installed — local mode only
    agentcore_app = None


# ---------------------------------------------------------------------------
# Legacy HTTP handler (for direct Lambda / local testing)
# ---------------------------------------------------------------------------

def handler(event: dict) -> dict:
    """Direct invocation handler (non-AgentCore)."""
    app = create_app()
    user_id = event.get("user_id", "anonymous")
    request = event.get("request", event.get("prompt", ""))
    response = app.process_request(user_id, request)
    return response.model_dump()


# ---------------------------------------------------------------------------
# Local CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if agentcore_app is not None and os.environ.get("AGENTCORE_RUNTIME"):
        # Running inside AgentCore Runtime
        agentcore_app.run()
    else:
        # Local CLI mode
        app = create_app()
        user_id = "user_001"
        query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Analyze my spending and suggest ways to save more"
        print(f"\n{'='*60}")
        print(f"SmartBanker AI — Processing request for {user_id}")
        print(f"Query: {query}")
        print(f"{'='*60}\n")
        response = app.process_request(user_id, query)
        print(f"\nStatus: {response.status}")
        print(f"Retries used: {response.retries_used}")
        for i, rec in enumerate(response.recommendations):
            print(f"\n--- Recommendation {i+1} ({rec.worker_domain}) ---")
            print(f"  Confidence: {rec.confidence}")
            print(f"  Risk Level: {rec.risk_level}")
            print(f"  Recommendation: {rec.recommendation[:300]}")
            if rec.explainability_summary:
                print(f"  Explainability: {rec.explainability_summary[:200]}")
            if rec.disclaimer:
                print(f"  Disclaimer: {rec.disclaimer[:200]}")
            if rec.issues:
                print(f"  Issues: {rec.issues}")
        if response.warnings:
            print(f"\nWarnings: {response.warnings}")
