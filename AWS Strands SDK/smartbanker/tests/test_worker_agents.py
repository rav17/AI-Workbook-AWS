"""Tests for all worker agents (T4.2–T4.6). Traces: R3, R4, R5, R6, R7."""
import json
import pytest
from unittest.mock import patch, MagicMock

from config.models import (
    ExecutionResult, MemoryContext, PlanTask, InteractionRecord,
    SimilarPattern, Status, Confidence, RiskLevel,
)
from config.settings import AgentConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config() -> AgentConfig:
    return AgentConfig(aws_region="us-east-1", llm_model_id="amazon.nova-pro-v1:0")


def _task(intent: str = "Analyze spending", worker: str = "spending_analysis") -> PlanTask:
    return PlanTask(task_id="t1", intent=intent, assigned_worker=worker)


def _context(**kwargs) -> MemoryContext:
    return MemoryContext(**kwargs)


def _json_response(**overrides) -> str:
    data = {
        "status": "success",
        "confidence": "high",
        "recommendation": "Test recommendation",
        "risk_level": "low",
        "issues": [],
        "explainability_summary": "Based on analysis",
    }
    data.update(overrides)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# T4.2: Spending Analyzer (R3)
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
class TestSpendingAnalyzer:
    def test_create_sets_domain(self, mock_bedrock, mock_agent):
        from agents.workers.spending_analyzer import create_spending_analyzer
        worker = create_spending_analyzer(_config())
        assert worker.domain == "spending_analysis"

    def test_has_transaction_fetcher_tool(self, mock_bedrock, mock_agent):
        from agents.workers.spending_analyzer import create_spending_analyzer
        from tools.financial_tools import transaction_fetcher
        worker = create_spending_analyzer(_config())
        # The agent is created with tools list containing transaction_fetcher
        call_kwargs = mock_agent.call_args
        assert transaction_fetcher in call_kwargs.kwargs.get("tools", call_kwargs[1].get("tools", []))

    def test_system_prompt_mentions_spending(self, mock_bedrock, mock_agent):
        from agents.workers.spending_analyzer import SPENDING_SYSTEM_PROMPT
        prompt_lower = SPENDING_SYSTEM_PROMPT.lower()
        assert "spending" in prompt_lower
        assert "transaction" in prompt_lower
        assert "pattern" in prompt_lower
        assert "recurring" in prompt_lower
        assert "anomal" in prompt_lower

    def test_execute_returns_execution_result(self, mock_bedrock, mock_agent_cls):
        from agents.workers.spending_analyzer import create_spending_analyzer
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = _json_response(
            recommendation="High grocery spending detected",
            risk_level="medium",
        )
        mock_agent_cls.return_value = mock_agent_instance

        worker = create_spending_analyzer(_config())
        result = worker.execute(_task(), _context())
        assert isinstance(result, ExecutionResult)
        assert result.status == "success"
        assert result.worker_domain == "spending_analysis"


# ---------------------------------------------------------------------------
# T4.3: Savings Advisor (R4)
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
class TestSavingsAdvisor:
    def test_create_sets_domain(self, mock_bedrock, mock_agent):
        from agents.workers.savings_advisor import create_savings_advisor
        worker = create_savings_advisor(_config())
        assert worker.domain == "savings_advice"

    def test_has_balance_and_budgeting_tools(self, mock_bedrock, mock_agent):
        from agents.workers.savings_advisor import create_savings_advisor
        from tools.financial_tools import balance_checker, budgeting_calculator
        worker = create_savings_advisor(_config())
        call_kwargs = mock_agent.call_args
        tools = call_kwargs.kwargs.get("tools", call_kwargs[1].get("tools", []))
        assert balance_checker in tools
        assert budgeting_calculator in tools

    def test_system_prompt_enforces_low_risk(self, mock_bedrock, mock_agent):
        """R4.3: risk_level ALWAYS 'low' for savings advice."""
        from agents.workers.savings_advisor import SAVINGS_SYSTEM_PROMPT
        assert 'risk_level' in SAVINGS_SYSTEM_PROMPT
        assert '"low"' in SAVINGS_SYSTEM_PROMPT
        assert "ALWAYS" in SAVINGS_SYSTEM_PROMPT

    def test_system_prompt_avoids_failed_strategies(self, mock_bedrock, mock_agent):
        """R4.4: Avoid repeating failed strategies."""
        from agents.workers.savings_advisor import SAVINGS_SYSTEM_PROMPT
        prompt_lower = SAVINGS_SYSTEM_PROMPT.lower()
        assert "avoid" in prompt_lower or "alternative" in prompt_lower

    def test_execute_returns_execution_result(self, mock_bedrock, mock_agent_cls):
        from agents.workers.savings_advisor import create_savings_advisor
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = _json_response(
            recommendation="Set up automatic transfers of 20% to savings",
            risk_level="low",
        )
        mock_agent_cls.return_value = mock_agent_instance

        worker = create_savings_advisor(_config())
        result = worker.execute(
            _task("Suggest savings plan", "savings_advice"),
            _context(),
        )
        assert isinstance(result, ExecutionResult)
        assert result.worker_domain == "savings_advice"


# ---------------------------------------------------------------------------
# T4.4: Investment Advisor (R5)
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
class TestInvestmentAdvisor:
    def test_create_sets_domain(self, mock_bedrock, mock_agent):
        from agents.workers.investment_advisor import create_investment_advisor
        worker = create_investment_advisor(_config())
        assert worker.domain == "investment_advice"

    def test_has_investment_data_api_tool(self, mock_bedrock, mock_agent):
        from agents.workers.investment_advisor import create_investment_advisor
        from tools.financial_tools import investment_data_api
        worker = create_investment_advisor(_config())
        call_kwargs = mock_agent.call_args
        tools = call_kwargs.kwargs.get("tools", call_kwargs[1].get("tools", []))
        assert investment_data_api in tools

    def test_system_prompt_requires_risk_categorization(self, mock_bedrock, mock_agent):
        """R5.2: Categorize with risk_level low/medium/high."""
        from agents.workers.investment_advisor import INVESTMENT_SYSTEM_PROMPT
        assert "risk_level" in INVESTMENT_SYSTEM_PROMPT
        assert "low" in INVESTMENT_SYSTEM_PROMPT
        assert "medium" in INVESTMENT_SYSTEM_PROMPT
        assert "high" in INVESTMENT_SYSTEM_PROMPT

    def test_system_prompt_requires_explainability(self, mock_bedrock, mock_agent):
        """R5.5: Include explainability summary."""
        from agents.workers.investment_advisor import INVESTMENT_SYSTEM_PROMPT
        assert "explainability" in INVESTMENT_SYSTEM_PROMPT.lower()

    def test_system_prompt_factors_past_failures(self, mock_bedrock, mock_agent):
        """R5.4: Factor in past failures."""
        from agents.workers.investment_advisor import INVESTMENT_SYSTEM_PROMPT
        prompt_lower = INVESTMENT_SYSTEM_PROMPT.lower()
        assert "failure" in prompt_lower or "avoid" in prompt_lower

    def test_execute_returns_execution_result(self, mock_bedrock, mock_agent_cls):
        from agents.workers.investment_advisor import create_investment_advisor
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = _json_response(
            recommendation="Consider S&P 500 Index Fund for medium risk tolerance",
            risk_level="medium",
            explainability_summary="Based on risk tolerance and market conditions",
        )
        mock_agent_cls.return_value = mock_agent_instance

        worker = create_investment_advisor(_config())
        result = worker.execute(
            _task("Recommend investments", "investment_advice"),
            _context(),
        )
        assert isinstance(result, ExecutionResult)
        assert result.worker_domain == "investment_advice"


# ---------------------------------------------------------------------------
# T4.5: Query Assistant (R6)
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
class TestQueryAssistant:
    def test_create_sets_domain(self, mock_bedrock, mock_agent):
        from agents.workers.query_assistant import create_query_assistant
        worker = create_query_assistant(_config())
        assert worker.domain == "financial_query"

    def test_no_external_tools(self, mock_bedrock, mock_agent):
        """R6: Memory-based, no external tools."""
        from agents.workers.query_assistant import create_query_assistant
        worker = create_query_assistant(_config())
        call_kwargs = mock_agent.call_args
        tools = call_kwargs.kwargs.get("tools", call_kwargs[1].get("tools", []))
        assert tools == []

    def test_system_prompt_handles_low_confidence(self, mock_bedrock, mock_agent):
        """R6.3: Return confidence 'low' with issues when can't answer."""
        from agents.workers.query_assistant import QUERY_SYSTEM_PROMPT
        prompt_lower = QUERY_SYSTEM_PROMPT.lower()
        assert "confidence" in prompt_lower
        assert "low" in prompt_lower
        assert "knowledge gap" in prompt_lower or "insufficient" in prompt_lower or "lack" in prompt_lower

    def test_execute_returns_execution_result(self, mock_bedrock, mock_agent_cls):
        from agents.workers.query_assistant import create_query_assistant
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = _json_response(
            recommendation="A savings account typically earns 3-5% APY",
            confidence="high",
        )
        mock_agent_cls.return_value = mock_agent_instance

        worker = create_query_assistant(_config())
        result = worker.execute(
            _task("What is a good savings rate?", "financial_query"),
            _context(),
        )
        assert isinstance(result, ExecutionResult)
        assert result.worker_domain == "financial_query"

    def test_execute_with_memory_context(self, mock_bedrock, mock_agent_cls):
        """R6.1: Uses memory context to inform answers."""
        from agents.workers.query_assistant import create_query_assistant
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = _json_response(
            recommendation="Based on your history, you save about 15% monthly",
            confidence="high",
        )
        mock_agent_cls.return_value = mock_agent_instance

        pattern = SimilarPattern(content="User saves 15% monthly", similarity_score=0.95)
        ctx = _context(patterns=[pattern])

        worker = create_query_assistant(_config())
        result = worker.execute(
            _task("How much do I save?", "financial_query"),
            ctx,
        )
        assert isinstance(result, ExecutionResult)
        assert result.status == "success"


# ---------------------------------------------------------------------------
# T4.6: Risk & Compliance (R7)
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
class TestRiskCompliance:
    def test_create_sets_domain(self, mock_bedrock, mock_agent):
        from agents.workers.risk_compliance import create_risk_compliance
        worker = create_risk_compliance(_config())
        assert worker.domain == "risk_compliance"

    def test_no_external_tools(self, mock_bedrock, mock_agent):
        """Risk compliance uses validation logic, no external tools."""
        from agents.workers.risk_compliance import create_risk_compliance
        worker = create_risk_compliance(_config())
        call_kwargs = mock_agent.call_args
        tools = call_kwargs.kwargs.get("tools", call_kwargs[1].get("tools", []))
        assert tools == []

    def test_validate_safe_recommendation_passes(self, mock_bedrock, mock_agent):
        """R7.1: Validate recommendations for safety."""
        from agents.workers.risk_compliance import create_risk_compliance
        worker = create_risk_compliance(_config())
        safe_result = ExecutionResult(
            status="success",
            confidence="high",
            recommendation="Consider diversifying into index funds",
            risk_level="medium",
            issues=[],
        )
        validated = worker.validate_recommendation(safe_result)
        assert validated.status != Status.FAILURE or "unsafe" not in str(validated.issues).lower()

    def test_validate_unsafe_recommendation_rejected(self, mock_bedrock, mock_agent):
        """R7.2: Reject unsafe recommendations with status 'failure'."""
        from agents.workers.risk_compliance import create_risk_compliance
        worker = create_risk_compliance(_config())
        unsafe_result = ExecutionResult(
            status="success",
            confidence="high",
            recommendation="This is a guaranteed returns investment with no risk",
            risk_level="low",
            issues=[],
        )
        validated = worker.validate_recommendation(unsafe_result)
        assert validated.status == Status.FAILURE
        assert any("compliance" in i.lower() or "unsafe" in i.lower() for i in validated.issues)

    def test_validate_missing_risk_label(self, mock_bedrock, mock_agent):
        """R7.3: Enforce risk labeling — empty risk_level triggers issue."""
        from agents.workers.risk_compliance import create_risk_compliance
        worker = create_risk_compliance(_config())
        result = ExecutionResult(
            status="success",
            confidence="high",
            recommendation="Buy some stocks",
            risk_level="low",
            issues=[],
        )
        # Bypass Pydantic to simulate a missing/empty risk_level
        result.__dict__["risk_level"] = ""
        validated = worker.validate_recommendation(result)
        assert any("risk_level" in i.lower() for i in validated.issues)

    def test_system_prompt_mentions_disclaimer(self, mock_bedrock, mock_agent):
        """R7.4: Ensure disclaimers on investment/savings advice."""
        from agents.workers.risk_compliance import RISK_SYSTEM_PROMPT
        prompt_lower = RISK_SYSTEM_PROMPT.lower()
        assert "disclaimer" in prompt_lower

    def test_multiple_unsafe_patterns_detected(self, mock_bedrock, mock_agent):
        """R7.2: Various unsafe patterns should be caught."""
        from agents.workers.risk_compliance import create_risk_compliance, UNSAFE_PATTERNS
        worker = create_risk_compliance(_config())
        for pattern in UNSAFE_PATTERNS:
            result = ExecutionResult(
                status="success",
                confidence="high",
                recommendation=f"This investment offers {pattern}",
                risk_level="low",
                issues=[],
            )
            validated = worker.validate_recommendation(result)
            assert validated.status == Status.FAILURE, f"Pattern '{pattern}' was not caught"

    def test_execute_returns_execution_result(self, mock_bedrock, mock_agent_cls):
        from agents.workers.risk_compliance import create_risk_compliance
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = _json_response(
            recommendation="Recommendation passes compliance checks",
            risk_level="low",
        )
        mock_agent_cls.return_value = mock_agent_instance

        worker = create_risk_compliance(_config())
        result = worker.execute(
            _task("Validate recommendation", "risk_compliance"),
            _context(),
        )
        assert isinstance(result, ExecutionResult)
        assert result.worker_domain == "risk_compliance"
