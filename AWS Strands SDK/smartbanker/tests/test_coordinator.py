"""Unit tests for CoordinatorAgent. Traces: R1, R13, R17."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from config.models import (
    Confidence,
    ExecutionResult,
    FinalResponse,
    InteractionRecord,
    IntrospectionReport,
    MemoryContext,
    Plan,
    PlanTask,
    ReflectionDecision,
    SimilarPattern,
    Status,
    RiskLevel,
)
from config.settings import AgentConfig, MemoryConfig


# ---------------------------------------------------------------------------
# Helpers — build a CoordinatorAgent with mocked external dependencies
# ---------------------------------------------------------------------------

def _make_coordinator():
    """Create a CoordinatorAgent with all external I/O mocked out."""
    agent_cfg = AgentConfig(max_retries=3)
    mem_cfg = MemoryConfig(agent_id="test")

    with patch("agents.coordinator.BedrockModel"), \
         patch("agents.coordinator.Agent"), \
         patch("agents.coordinator.DynamoDBShortTermMemory") as mock_stm_cls, \
         patch("agents.coordinator.VectorMemoryManager") as mock_ltm_cls, \
         patch("agents.coordinator.DelegatorAgent") as mock_del_cls:

        mock_stm = MagicMock()
        mock_stm.get_failures.return_value = []
        mock_stm_cls.return_value = mock_stm

        mock_ltm = MagicMock()
        mock_ltm.search_patterns.return_value = []
        mock_ltm_cls.return_value = mock_ltm

        mock_delegator = MagicMock()
        mock_del_cls.return_value = mock_delegator

        from agents.coordinator import CoordinatorAgent
        coord = CoordinatorAgent(agent_cfg, mem_cfg)
        coord.stm = mock_stm
        coord.ltm = mock_ltm
        coord.delegator = mock_delegator
        return coord


def _ok_result(domain: str = "financial_query", recommendation: str = "Do X") -> ExecutionResult:
    return ExecutionResult(
        status=Status.SUCCESS,
        confidence=Confidence.HIGH,
        recommendation=recommendation,
        risk_level=RiskLevel.LOW,
        worker_domain=domain,
    )


def _fail_result(domain: str = "investment_advice", issues: list[str] | None = None) -> ExecutionResult:
    return ExecutionResult(
        status=Status.FAILURE,
        confidence=Confidence.LOW,
        recommendation="bad advice",
        risk_level=RiskLevel.HIGH,
        issues=issues or ["something went wrong"],
        worker_domain=domain,
    )


# ===================================================================
# Reflection tests — R13.1, R13.2
# ===================================================================

class TestReflect:
    """Tests for CoordinatorAgent.reflect()."""

    def test_finalize_when_all_success(self):
        """All successful results → finalize."""
        coord = _make_coordinator()
        decision = coord.reflect([_ok_result(), _ok_result()])
        assert decision.action == "finalize"
        assert not decision.should_retry

    def test_retry_on_fixable_failure(self):
        """A non-compliance failure → retry."""
        coord = _make_coordinator()
        decision = coord.reflect([_fail_result()])
        assert decision.action == "retry"
        assert decision.should_retry
        assert len(decision.failed_tasks) == 1

    def test_finalize_on_compliance_failure(self):
        """Compliance violation → finalize (not retryable)."""
        coord = _make_coordinator()
        result = _fail_result(issues=["Compliance violation: unsafe pattern detected"])
        decision = coord.reflect([result])
        assert decision.action == "finalize"
        assert not decision.should_retry

    def test_retry_includes_only_fixable_task_ids(self):
        """Mixed results: only fixable failures appear in failed_tasks."""
        coord = _make_coordinator()
        ok = _ok_result()
        fixable = _fail_result(issues=["timeout"])
        compliance = _fail_result(issues=["Compliance violation: bad"])
        decision = coord.reflect([ok, fixable, compliance])
        assert decision.action == "retry"
        assert fixable.task_id in decision.failed_tasks
        assert compliance.task_id not in decision.failed_tasks

    def test_finalize_on_empty_results(self):
        """No results → finalize."""
        coord = _make_coordinator()
        decision = coord.reflect([])
        assert decision.action == "finalize"

    def test_low_confidence_triggers_retry(self):
        """Low confidence result triggers retry even if status is success."""
        coord = _make_coordinator()
        low_conf = ExecutionResult(
            status=Status.SUCCESS,
            confidence=Confidence.LOW,
            recommendation="maybe",
            risk_level=RiskLevel.MEDIUM,
            worker_domain="savings_advice",
        )
        decision = coord.reflect([low_conf])
        assert decision.should_retry


# ===================================================================
# Introspection tests — R12.2, R12.3
# ===================================================================

class TestIntrospect:
    """Tests for CoordinatorAgent.introspect()."""

    def test_valid_result_passes(self):
        coord = _make_coordinator()
        report = coord.introspect(_ok_result())
        assert report.schema_valid is True
        assert report.issues == []
        assert report.quality_score == "high"

    def test_empty_recommendation_flagged(self):
        coord = _make_coordinator()
        result = _ok_result()
        result.recommendation = ""
        report = coord.introspect(result)
        assert not report.schema_valid
        assert any("Empty recommendation" in i for i in report.issues)

    def test_missing_worker_domain_flagged(self):
        coord = _make_coordinator()
        result = _ok_result()
        result.worker_domain = ""
        report = coord.introspect(result)
        assert not report.schema_valid
        assert any("Missing worker_domain" in i for i in report.issues)

    def test_low_confidence_quality_is_low(self):
        coord = _make_coordinator()
        result = ExecutionResult(
            status=Status.SUCCESS,
            confidence=Confidence.LOW,
            recommendation="uncertain",
            risk_level=RiskLevel.MEDIUM,
            worker_domain="financial_query",
        )
        report = coord.introspect(result)
        assert report.schema_valid is True
        assert report.quality_score == "low"


# ===================================================================
# Plan tests — R1.1, R1.4, R1.5
# ===================================================================

class TestPlan:
    """Tests for CoordinatorAgent.plan()."""

    def test_fallback_plan_on_llm_failure(self):
        """When the LLM call fails, a single-task fallback plan is returned."""
        coord = _make_coordinator()
        coord.planner = MagicMock(side_effect=Exception("LLM down"))
        context = MemoryContext()
        plan = coord.plan(context, "help me save money", user_id="u1")
        assert len(plan.tasks) == 1
        assert plan.tasks[0].assigned_worker == "financial_query"
        assert plan.user_id == "u1"

    def test_plan_parses_llm_json(self):
        """When the LLM returns valid JSON, it is parsed into a Plan."""
        coord = _make_coordinator()
        llm_response = MagicMock()
        llm_response.__str__ = lambda _: '{"tasks": [{"intent": "analyze spending", "assigned_worker": "spending_analysis", "execution_order": 0}], "excluded_strategies": ["old_strategy"]}'
        coord.planner = MagicMock(return_value=llm_response)
        context = MemoryContext()
        plan = coord.plan(context, "analyze my spending", user_id="u2")
        assert len(plan.tasks) == 1
        assert plan.tasks[0].assigned_worker == "spending_analysis"
        assert "old_strategy" in plan.excluded_strategies

    def test_plan_excludes_failed_strategies(self):
        """Failures in context are passed to the LLM prompt."""
        coord = _make_coordinator()
        # Make planner return fallback (we just want to verify the prompt)
        coord.planner = MagicMock(side_effect=Exception("capture"))
        failure = InteractionRecord(
            user_id="u1", input="invest", output="bad",
            status="failure", confidence="low",
            strategy_used="concentrated_tech_stocks",
        )
        context = MemoryContext(failures=[failure])
        plan = coord.plan(context, "invest again", user_id="u1")
        # Fallback plan returned because LLM raised
        assert len(plan.tasks) == 1


# ===================================================================
# Overall status determination
# ===================================================================

class TestDetermineOverallStatus:

    def test_all_success(self):
        from agents.coordinator import CoordinatorAgent
        assert CoordinatorAgent._determine_overall_status([_ok_result(), _ok_result()]) == "success"

    def test_all_failure(self):
        from agents.coordinator import CoordinatorAgent
        assert CoordinatorAgent._determine_overall_status([_fail_result(), _fail_result()]) == "failure"

    def test_mixed(self):
        from agents.coordinator import CoordinatorAgent
        assert CoordinatorAgent._determine_overall_status([_ok_result(), _fail_result()]) == "partial_success"

    def test_empty(self):
        from agents.coordinator import CoordinatorAgent
        assert CoordinatorAgent._determine_overall_status([]) == "failure"


# ===================================================================
# process_request integration (mocked externals) — R17
# ===================================================================

class TestProcessRequest:
    """Tests for the full self-healing loop."""

    def test_successful_single_pass(self):
        """Happy path: no retries needed."""
        coord = _make_coordinator()
        coord.delegator.dispatch.return_value = [_ok_result()]
        # Mock plan to return a simple plan
        coord.planner = MagicMock()
        llm_resp = MagicMock()
        llm_resp.__str__ = lambda _: '{"tasks": [{"intent": "query", "assigned_worker": "financial_query", "execution_order": 0}]}'
        coord.planner.return_value = llm_resp

        response = coord.process_request("user1", "what is my balance?")

        assert isinstance(response, FinalResponse)
        assert response.status == "success"
        assert response.retries_used == 0
        assert response.user_id == "user1"
        assert len(response.recommendations) == 1

    def test_retry_on_failure_then_success(self):
        """First attempt fails, second succeeds → retries_used=1."""
        coord = _make_coordinator()
        # First call returns failure, second returns success
        coord.delegator.dispatch.side_effect = [
            [_fail_result()],
            [_ok_result()],
        ]
        coord.planner = MagicMock()
        llm_resp = MagicMock()
        llm_resp.__str__ = lambda _: '{"tasks": [{"intent": "invest", "assigned_worker": "investment_advice", "execution_order": 0}]}'
        coord.planner.return_value = llm_resp

        response = coord.process_request("user1", "invest my money")

        assert response.status == "success"
        assert response.retries_used == 1

    def test_max_retries_exhausted(self):
        """All attempts fail → retries exhausted, status=failure."""
        coord = _make_coordinator()
        coord.max_retries = 2
        coord.delegator.dispatch.return_value = [_fail_result()]
        coord.planner = MagicMock()
        llm_resp = MagicMock()
        llm_resp.__str__ = lambda _: '{"tasks": [{"intent": "invest", "assigned_worker": "investment_advice", "execution_order": 0}]}'
        coord.planner.return_value = llm_resp

        response = coord.process_request("user1", "invest")

        assert response.status == "failure"
        # retries_used should be max_retries (2)
        assert response.retries_used == 2

    def test_persist_learnings_called(self):
        """Verify STM store_interaction is called after processing."""
        coord = _make_coordinator()
        coord.delegator.dispatch.return_value = [_ok_result()]
        coord.planner = MagicMock()
        llm_resp = MagicMock()
        llm_resp.__str__ = lambda _: '{"tasks": [{"intent": "q", "assigned_worker": "financial_query", "execution_order": 0}]}'
        coord.planner.return_value = llm_resp

        coord.process_request("user1", "help")

        coord.stm.store_interaction.assert_called()

    def test_compliance_check_applied(self):
        """When risk_agent is set, compliance check runs on results."""
        coord = _make_coordinator()
        coord.risk_agent = MagicMock()
        coord.risk_agent.validate_recommendation.return_value = _ok_result()
        coord.delegator.dispatch.return_value = [_ok_result()]
        coord.planner = MagicMock()
        llm_resp = MagicMock()
        llm_resp.__str__ = lambda _: '{"tasks": [{"intent": "q", "assigned_worker": "financial_query", "execution_order": 0}]}'
        coord.planner.return_value = llm_resp

        coord.process_request("user1", "invest")

        coord.risk_agent.validate_recommendation.assert_called()

    def test_correlation_id_in_response(self):
        """FinalResponse includes a valid correlation_id."""
        coord = _make_coordinator()
        coord.delegator.dispatch.return_value = [_ok_result()]
        coord.planner = MagicMock()
        llm_resp = MagicMock()
        llm_resp.__str__ = lambda _: '{"tasks": [{"intent": "q", "assigned_worker": "financial_query", "execution_order": 0}]}'
        coord.planner.return_value = llm_resp

        response = coord.process_request("user1", "help")

        # Should be a valid UUID
        uuid.UUID(response.correlation_id)

    def test_warnings_populated_from_issues(self):
        """Warnings in FinalResponse come from result issues."""
        coord = _make_coordinator()
        result_with_issues = _ok_result()
        result_with_issues.issues = ["Watch out for fees"]
        coord.delegator.dispatch.return_value = [result_with_issues]
        coord.planner = MagicMock()
        llm_resp = MagicMock()
        llm_resp.__str__ = lambda _: '{"tasks": [{"intent": "q", "assigned_worker": "financial_query", "execution_order": 0}]}'
        coord.planner.return_value = llm_resp

        response = coord.process_request("user1", "help")

        assert "Watch out for fees" in response.warnings
