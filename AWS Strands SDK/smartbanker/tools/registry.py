"""Tool Registry with schema validation. Traces: R8."""
from __future__ import annotations
from dataclasses import dataclass, field
import jsonschema
from config.models import ValidationResult


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict
    compatible_workers: list[str] = field(default_factory=list)


class ToolRegistry:
    """Centralized tool catalog with schema validation. Traces: R8."""

    def __init__(self):
        self._tools: dict[str, ToolSchema] = {}

    def register(self, schema: ToolSchema) -> None:
        self._tools[schema.name] = schema

    def validate_invocation(self, tool_name: str, params: dict) -> ValidationResult:
        schema = self._tools.get(tool_name)
        if not schema:
            return ValidationResult(valid=False, errors=[f"Tool '{tool_name}' not registered"])
        try:
            jsonschema.validate(instance=params, schema=schema.parameters)
            return ValidationResult(valid=True)
        except jsonschema.ValidationError as e:
            return ValidationResult(valid=False, errors=[str(e.message)])

    def lookup(self, tool_name: str) -> ToolSchema | None:
        return self._tools.get(tool_name)

    def get_compatible_tools(self, worker_domain: str) -> list[ToolSchema]:
        return [t for t in self._tools.values() if worker_domain in t.compatible_workers]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


def create_default_registry() -> ToolRegistry:
    """Create registry with all standard financial tools."""
    registry = ToolRegistry()
    registry.register(ToolSchema(
        name="transaction_fetcher",
        description="Retrieves user transaction data for a given period",
        parameters={
            "type": "object",
            "required": ["user_id"],
            "properties": {
                "user_id": {"type": "string"},
                "days": {"type": "integer", "default": 30},
            },
        },
        compatible_workers=["spending_analysis"],
    ))
    registry.register(ToolSchema(
        name="balance_checker",
        description="Checks current account balances",
        parameters={
            "type": "object",
            "required": ["user_id"],
            "properties": {"user_id": {"type": "string"}},
        },
        compatible_workers=["savings_advice"],
    ))
    registry.register(ToolSchema(
        name="investment_data_api",
        description="Retrieves market and investment data",
        parameters={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "risk_tolerance": {"type": "string", "enum": ["low", "medium", "high"]},
            },
        },
        compatible_workers=["investment_advice"],
    ))
    registry.register(ToolSchema(
        name="budgeting_calculator",
        description="Calculates budget allocations and savings potential",
        parameters={
            "type": "object",
            "required": ["user_id", "income"],
            "properties": {
                "user_id": {"type": "string"},
                "income": {"type": "number"},
                "target_savings_pct": {"type": "number", "default": 20},
            },
        },
        compatible_workers=["savings_advice"],
    ))

    # ------------------------------------------------------------------
    # Phase 2 tools (R8.1, R20, R28, R30, R32, R39)
    # ------------------------------------------------------------------

    registry.register(ToolSchema(
        name="service_request_processor",
        description="Processes routine banking service requests",
        parameters={
            "type": "object",
            "required": ["request_type", "description"],
            "properties": {
                "request_type": {"type": "string"},
                "description": {"type": "string"},
                "user_id": {"type": "string"},
            },
        },
        compatible_workers=["service_request"],
    ))
    registry.register(ToolSchema(
        name="escalation_tracker",
        description="Tracks escalation of service requests",
        parameters={
            "type": "object",
            "required": ["request_id"],
            "properties": {
                "request_id": {"type": "string"},
                "reason": {"type": "string"},
            },
        },
        compatible_workers=["service_request"],
    ))
    registry.register(ToolSchema(
        name="document_guidance_tool",
        description="Provides guidance on required documents for banking operations",
        parameters={
            "type": "object",
            "required": ["document_type"],
            "properties": {
                "document_type": {"type": "string"},
                "user_id": {"type": "string"},
            },
        },
        compatible_workers=["service_request"],
    ))
    registry.register(ToolSchema(
        name="loan_product_catalog",
        description="Retrieves available loan products from the bank catalog",
        parameters={
            "type": "object",
            "properties": {
                "loan_type": {"type": "string"},
                "user_tier": {"type": "string"},
            },
        },
        compatible_workers=["loan_advice"],
    ))
    registry.register(ToolSchema(
        name="tier_pricing_engine",
        description="Calculates tier-specific preferential pricing for loans",
        parameters={
            "type": "object",
            "properties": {
                "user_tier": {"type": "string"},
                "base_rate": {"type": "number"},
            },
        },
        compatible_workers=["loan_advice"],
    ))
    registry.register(ToolSchema(
        name="activity_analyzer",
        description="Analyzes user banking activity metrics for value assessment",
        parameters={
            "type": "object",
            "required": ["user_id"],
            "properties": {
                "user_id": {"type": "string"},
                "period_months": {"type": "integer", "default": 6},
            },
        },
        compatible_workers=["value_assessment"],
    ))
    registry.register(ToolSchema(
        name="tier_benefit_mapper",
        description="Maps tier benefits to user activity for value assessment",
        parameters={
            "type": "object",
            "required": ["user_tier"],
            "properties": {
                "user_tier": {"type": "string"},
            },
        },
        compatible_workers=["value_assessment"],
    ))
    registry.register(ToolSchema(
        name="compliance_rule_checker",
        description="Checks compliance rules for banking operations",
        parameters={
            "type": "object",
            "required": ["request_context"],
            "properties": {
                "request_context": {"type": "string"},
                "rule_set": {"type": "string"},
            },
        },
        compatible_workers=["risk_compliance"],
    ))

    return registry
