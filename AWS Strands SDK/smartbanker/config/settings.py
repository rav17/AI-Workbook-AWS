"""Configuration for SmartBanker AI Agent. Traces: R16, R18, R23, R29, R34, R36."""
from pydantic import BaseModel


class AgentConfig(BaseModel):
    """Core agent configuration for LLM inference and retry behavior."""
    aws_region: str = "us-east-1"
    llm_model_id: str = "us.amazon.nova-pro-v1:0"
    embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    max_retries: int = 3


class GatewayConfig(BaseModel):
    """AgentCore Gateway configuration for API entry point."""
    gateway_id: str
    stage: str = "prod"
    auth_type: str = "iam"
    rate_limit_rps: int = 100
    burst_limit: int = 200


class MemoryConfig(BaseModel):
    """AgentCore Memory configuration for short-term and long-term memory."""
    agent_id: str
    aws_region: str = "us-east-1"
    stm_namespace: str = "short-term"
    ltm_namespace: str = "long-term"
    max_interactions: int = 20
    max_failures_in_context: int = 10
    max_patterns_in_context: int = 5
    max_context_age_days: int = 90
    default_k: int = 5


class PriorityConfig(BaseModel):
    """Tier-to-priority mapping for banking task processing (Req 29)."""
    tier_priority_map: dict[str, str] = {
        "basic": "standard",
        "preferred": "elevated",
        "premium": "high",
        "ultra-premium": "critical",
    }
    estimated_processing_times: dict[str, str] = {
        "standard": "3-5 business days",
        "elevated": "1-3 business days",
        "high": "same business day",
        "critical": "within 4 hours",
    }


class ComplianceConfig(BaseModel):
    """Compliance rules that cannot be bypassed (Req 34)."""
    mandatory_checks: list[str] = ["kyc_verification", "credit_check", "aml_screening", "sanctions_check"]
    non_waivable_rules: list[str] = ["kyc", "credit_assessment", "regulatory_compliance"]


class ScopeLimitationConfig(BaseModel):
    """Out-of-scope service definitions (Req 36)."""
    out_of_scope_services: list[str] = [
        "active_portfolio_management",
        "daily_wealth_monitoring",
        "retirement_modeling",
        "advanced_tax_optimization",
    ]


class AppConfig(BaseModel):
    """Top-level application configuration."""
    agent: AgentConfig = AgentConfig()
    memory: MemoryConfig = MemoryConfig(agent_id="smartbanker-agent")
    gateway: GatewayConfig = GatewayConfig(gateway_id="smartbanker-gw")
    priority: PriorityConfig = PriorityConfig()
    compliance: ComplianceConfig = ComplianceConfig()
    scope_limitation: ScopeLimitationConfig = ScopeLimitationConfig()
