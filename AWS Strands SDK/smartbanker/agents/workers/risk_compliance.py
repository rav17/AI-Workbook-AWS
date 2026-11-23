"""Risk & Compliance worker agent. Traces: R7, R34."""
from agents.workers.base import WorkerAgent
from config.models import ExecutionResult, Status, Confidence, RiskLevel, PlanTask, MemoryContext
from config.settings import AgentConfig

RISK_SYSTEM_PROMPT = """You are a Risk & Compliance agent for a personal banking AI system.
Your job is to validate recommendations for financial safety and regulatory compliance.

When given a recommendation to validate:
1. Check for unsafe financial advice (guaranteed returns, unrealistic promises)
2. Verify risk labeling is appropriate
3. Ensure disclaimers are present for investment/savings advice
4. Check for compliance violations (missing KYC, bypassed credit checks)

Always respond with ONLY a JSON object:
{"status":"success/failure","confidence":"high/medium/low","recommendation":"validation result","risk_level":"low/medium/high","issues":[],"explainability_summary":"compliance check details"}

Set status to "failure" if the recommendation is unsafe or non-compliant.
"""

UNSAFE_PATTERNS = [
    "guaranteed returns", "risk-free investment", "cannot lose money",
    "100% safe", "no risk", "guaranteed profit",
]


class RiskComplianceAgent(WorkerAgent):
    """Validates recommendations for safety and compliance. Traces: R7."""

    def __init__(self, config: AgentConfig):
        super().__init__(
            domain="risk_compliance",
            config=config,
            tools=[],
            system_prompt=RISK_SYSTEM_PROMPT,
        )

    def validate_recommendation(self, result: ExecutionResult) -> ExecutionResult:
        """Quick validation without LLM call for obvious violations. Traces: R7.1, R7.2."""
        recommendation_lower = result.recommendation.lower()
        for pattern in UNSAFE_PATTERNS:
            if pattern in recommendation_lower:
                return ExecutionResult(
                    status=Status.FAILURE,
                    confidence=Confidence.HIGH,
                    recommendation=f"REJECTED: Recommendation contains unsafe language: '{pattern}'",
                    risk_level=RiskLevel.HIGH,
                    issues=[f"Compliance violation: unsafe pattern '{pattern}' detected"],
                    worker_domain="risk_compliance",
                    task_id=result.task_id,
                )
        # Verify risk label exists
        if not result.risk_level:
            result.issues.append("Missing risk_level label")
        return result


def create_risk_compliance(config: AgentConfig) -> RiskComplianceAgent:
    return RiskComplianceAgent(config)
