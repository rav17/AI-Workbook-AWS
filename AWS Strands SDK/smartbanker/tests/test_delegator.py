"""Tests for DelegatorAgent. Traces: R2."""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from config.models import (
    ExecutionResult, Plan, PlanTask, MemoryContext,
    Status, Confidence, RiskLevel,
)
from config.settings import AgentConfig
from agents.delegator import DelegatorAgent, _compute_relevance_score
from agents.workers.base import WorkerAgent
from tools.registry import ToolSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> AgentConfig:
    return AgentConfig(aws_region="us-east-1", llm_model_id="test-model")


def _make_worker(domain: str) -> WorkerAgent:
    """Create a mock WorkerAgent that returns a success result."""
    worker = MagicMock(spec=WorkerAgent)
    worker.domain = domain
    worker.execute.return_value = ExecutionResult(
        status=Status.SUCCESS,
        confidence=Confidence.HIGH,
        recommendation="test recommendation",
        risk_level=RiskLevel.LOW,
        issues=[],
        worker_domain=domain,
    )
    return worker


def _make_plan(tasks: list[PlanTask], user_id: str = "u1") -> Plan:
    return Plan(user_id=user_id, original_request="test", tasks=tasks)


def _make_context() -> MemoryContext:
    return MemoryContext()


# ---------------------------------------------------------------------------
# R2.1 — Worker domain matching
# ---------------------------------------------------------------------------

class TestWorkerRegistrationAndRouting:
    def test_register_and_route_exact_match(self):
        """R2.1: Delegator selects worker whose domain matches task intent."""
        agent = DelegatorAgent(_make_config())
        worker = _make_worker("spending_analysis")
        agent.register_worker("spending_analysis", worker)

        task = PlanTask(intent="analyze spending", assigned_worker="spending_analysis")
        result = agent.route_task(task)

        assert not isinstance(result, ExecutionResult)
        matched_worker, tools = result
        assert matched_worker is worker

    def test_dispatch_routes_to_correct_worker(self):
        """R2.1: dispatch routes each task to the assigned worker."""
        agent = DelegatorAgent(_make_config())
        w1 = _make_worker("spending_analysis")
        w2 = _make_worker("savings_advice")
        agent.register_worker("spending_analysis", w1)
        agent.register_worker("savings_advice", w2)

        plan = _make_plan([
            PlanTask(intent="analyze spending", assigned_worker="spending_analysis", execution_order=0),
            PlanTask(intent="suggest savings", assigned_worker="savings_advice", execution_order=1),
        ])
        results = agent.dispatch(plan, _make_context())

        assert len(results) == 2
        w1.execute.assert_called_once()
        w2.execute.assert_called_once()


# ---------------------------------------------------------------------------
# R2.2 — Tool validation
# ---------------------------------------------------------------------------

class TestToolValidation:
    def test_tool_compatible_with_worker(self):
        """R2.2: Required tools must be available and compatible."""
        agent = DelegatorAgent(_make_config())
        worker = _make_worker("spending_analysis")
        agent.register_worker("spending_analysis", worker)

        # transaction_fetcher is registered as compatible with spending_analysis
        task = PlanTask(
            intent="analyze spending",
            assigned_worker="spending_analysis",
            required_tools=["transaction_fetcher"],
        )
        result = agent.route_task(task)
        assert not isinstance(result, ExecutionResult)

    def test_tool_not_registered_still_routes_to_worker(self):
        """R2.2: When assigned worker is registered, route to it even if
        plan specifies unknown tool names (LLM may invent tool names)."""
        agent = DelegatorAgent(_make_config())
        worker = _make_worker("spending_analysis")
        agent.register_worker("spending_analysis", worker)

        task = PlanTask(
            intent="analyze spending",
            assigned_worker="spending_analysis",
            required_tools=["nonexistent_tool"],
        )
        result = agent.route_task(task)
        # Should still route to the registered worker
        assert not isinstance(result, ExecutionResult)
        matched_worker, _ = result
        assert matched_worker is worker

    def test_tool_incompatible_still_routes_to_assigned_worker(self):
        """R2.2: When assigned worker is registered, route to it — the worker
        already has its own tools configured via constructor."""
        agent = DelegatorAgent(_make_config())
        worker = _make_worker("spending_analysis")
        agent.register_worker("spending_analysis", worker)

        task = PlanTask(
            intent="analyze spending",
            assigned_worker="spending_analysis",
            required_tools=["investment_data_api"],
        )
        result = agent.route_task(task)
        # Should still route to the registered worker
        assert not isinstance(result, ExecutionResult)
        matched_worker, _ = result
        assert matched_worker is worker


# ---------------------------------------------------------------------------
# R2.3 — No compatible worker → error
# ---------------------------------------------------------------------------

class TestNoCompatibleWorker:
    def test_unregistered_worker_returns_error(self):
        """R2.3: No worker registered for domain → error ExecutionResult."""
        agent = DelegatorAgent(_make_config())

        task = PlanTask(intent="do something", assigned_worker="unknown_domain")
        result = agent.route_task(task)

        assert isinstance(result, ExecutionResult)
        assert result.status == Status.FAILURE
        assert any("No compatible worker" in issue for issue in result.issues)

    def test_dispatch_includes_error_for_missing_worker(self):
        """R2.3: dispatch returns error result for unroutable tasks."""
        agent = DelegatorAgent(_make_config())
        plan = _make_plan([
            PlanTask(intent="unknown task", assigned_worker="nonexistent"),
        ])
        results = agent.dispatch(plan, _make_context())

        assert len(results) == 1
        assert results[0].status == Status.FAILURE


# ---------------------------------------------------------------------------
# R2.4 — Highest domain relevance score
# ---------------------------------------------------------------------------

class TestRelevanceScoring:
    def test_relevance_score_exact_domain_match(self):
        """R2.4: Exact domain name in intent → score 1.0."""
        score = _compute_relevance_score("spending_analysis", "spending_analysis task")
        assert score == 1.0

    def test_relevance_score_keyword_match(self):
        """R2.4: Keyword matches produce a positive score."""
        score = _compute_relevance_score("spending_analysis", "analyze my transactions and expenses")
        assert score > 0.0

    def test_relevance_score_no_match(self):
        """R2.4: No keyword overlap → score 0.0."""
        score = _compute_relevance_score("spending_analysis", "invest in stocks")
        assert score == 0.0

    def test_fallback_selects_highest_relevance_worker(self):
        """R2.4: When assigned worker is missing, pick highest relevance."""
        agent = DelegatorAgent(_make_config())
        w_spend = _make_worker("spending_analysis")
        w_invest = _make_worker("investment_advice")
        agent.register_worker("spending_analysis", w_spend)
        agent.register_worker("investment_advice", w_invest)

        # assigned_worker doesn't exist; intent matches investment keywords
        task = PlanTask(
            intent="invest in stocks and portfolio",
            assigned_worker="nonexistent",
        )
        result = agent.route_task(task)

        assert not isinstance(result, ExecutionResult)
        matched_worker, _ = result
        assert matched_worker is w_invest

    def test_fallback_with_tool_constraint(self):
        """R2.4: Fallback picks highest relevance worker when assigned is missing."""
        agent = DelegatorAgent(_make_config())
        w_spend = _make_worker("spending_analysis")
        w_invest = _make_worker("investment_advice")
        agent.register_worker("spending_analysis", w_spend)
        agent.register_worker("investment_advice", w_invest)

        # assigned_worker doesn't exist; intent matches investment
        task = PlanTask(
            intent="invest in stocks",
            assigned_worker="nonexistent",
            required_tools=["investment_data_api"],
        )
        result = agent.route_task(task)

        assert not isinstance(result, ExecutionResult)
        matched_worker, _ = result
        assert matched_worker is w_invest


# ---------------------------------------------------------------------------
# Priority level propagation
# ---------------------------------------------------------------------------

class TestPriorityLevel:
    def test_priority_level_propagated_to_results(self):
        """dispatch propagates priority_level to each ExecutionResult."""
        agent = DelegatorAgent(_make_config())
        worker = _make_worker("spending_analysis")
        agent.register_worker("spending_analysis", worker)

        plan = _make_plan([
            PlanTask(intent="analyze spending", assigned_worker="spending_analysis"),
        ])
        results = agent.dispatch(plan, _make_context(), priority_level="critical")

        assert results[0].priority_level == "critical"

    def test_no_priority_level_leaves_field_empty(self):
        """dispatch without priority_level leaves the field at default."""
        agent = DelegatorAgent(_make_config())
        worker = _make_worker("spending_analysis")
        agent.register_worker("spending_analysis", worker)

        plan = _make_plan([
            PlanTask(intent="analyze spending", assigned_worker="spending_analysis"),
        ])
        results = agent.dispatch(plan, _make_context())

        assert results[0].priority_level == ""


# ---------------------------------------------------------------------------
# Execution order
# ---------------------------------------------------------------------------

class TestExecutionOrder:
    def test_tasks_dispatched_in_execution_order(self):
        """Tasks are dispatched sorted by execution_order."""
        agent = DelegatorAgent(_make_config())
        call_order = []

        def make_tracking_worker(domain: str):
            w = _make_worker(domain)

            def tracking_execute(task, ctx):
                call_order.append(domain)
                return ExecutionResult(
                    status=Status.SUCCESS, confidence=Confidence.HIGH,
                    recommendation="ok", risk_level=RiskLevel.LOW,
                    worker_domain=domain,
                )

            w.execute = tracking_execute
            return w

        w1 = make_tracking_worker("spending_analysis")
        w2 = make_tracking_worker("savings_advice")
        agent.register_worker("spending_analysis", w1)
        agent.register_worker("savings_advice", w2)

        plan = _make_plan([
            PlanTask(intent="save", assigned_worker="savings_advice", execution_order=2),
            PlanTask(intent="spend", assigned_worker="spending_analysis", execution_order=1),
        ])
        agent.dispatch(plan, _make_context())

        assert call_order == ["spending_analysis", "savings_advice"]
