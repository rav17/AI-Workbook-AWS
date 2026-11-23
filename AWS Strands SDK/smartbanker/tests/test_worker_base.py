"""Tests for WorkerAgent base class. Traces: R12."""
import json
import pytest
from unittest.mock import MagicMock, patch
from config.models import (
    ExecutionResult, MemoryContext, PlanTask, InteractionRecord,
    SimilarPattern, Status, Confidence, RiskLevel,
)
from config.settings import AgentConfig
from agents.workers.base import WorkerAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> AgentConfig:
    return AgentConfig(aws_region="us-east-1", llm_model_id="amazon.nova-pro-v1:0")


def _make_task(intent: str = "Analyze spending") -> PlanTask:
    return PlanTask(task_id="t1", intent=intent, assigned_worker="spending_analysis")


def _make_context(**kwargs) -> MemoryContext:
    return MemoryContext(**kwargs)


def _valid_json(**overrides) -> str:
    data = {
        "status": "success",
        "confidence": "high",
        "recommendation": "Save more",
        "risk_level": "low",
        "issues": [],
        "explainability_summary": "Based on analysis",
    }
    data.update(overrides)
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Tests: __init__
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
def test_init_sets_domain_and_creates_agent(mock_bedrock, mock_agent):
    config = _make_config()
    worker = WorkerAgent("spending_analysis", config, ["tool1"], "You are a helper")
    assert worker.domain == "spending_analysis"
    mock_bedrock.assert_called_once_with(model_id=config.llm_model_id, region_name=config.aws_region)
    mock_agent.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _parse_result  (R12.1, R12.3)
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
class TestParseResult:
    def _worker(self, mock_bedrock, mock_agent) -> WorkerAgent:
        return WorkerAgent("test_domain", _make_config(), [], "prompt")

    def test_valid_json_returns_success(self, mock_bedrock, mock_agent):
        w = self._worker(mock_bedrock, mock_agent)
        task = _make_task()
        result = w._parse_result(_valid_json(), task)
        assert result.status == "success"
        assert result.confidence == "high"
        assert result.recommendation == "Save more"
        assert result.risk_level == "low"
        assert result.issues == []
        assert result.worker_domain == "test_domain"
        assert result.task_id == task.task_id

    def test_invalid_status_returns_failure(self, mock_bedrock, mock_agent):
        """R12.3: invalid field values → failure."""
        w = self._worker(mock_bedrock, mock_agent)
        raw = _valid_json(status="unknown")
        result = w._parse_result(raw, _make_task())
        assert result.status == Status.FAILURE
        assert any("status" in i for i in result.issues)

    def test_invalid_confidence_returns_failure(self, mock_bedrock, mock_agent):
        w = self._worker(mock_bedrock, mock_agent)
        raw = _valid_json(confidence="very_high")
        result = w._parse_result(raw, _make_task())
        assert result.status == Status.FAILURE

    def test_invalid_risk_level_returns_failure(self, mock_bedrock, mock_agent):
        w = self._worker(mock_bedrock, mock_agent)
        raw = _valid_json(risk_level="extreme")
        result = w._parse_result(raw, _make_task())
        assert result.status == Status.FAILURE

    def test_no_json_returns_failure(self, mock_bedrock, mock_agent):
        """R12.3: unparseable output → failure."""
        w = self._worker(mock_bedrock, mock_agent)
        result = w._parse_result("just plain text", _make_task())
        assert result.status == Status.FAILURE
        assert len(result.issues) > 0

    def test_empty_string_returns_failure(self, mock_bedrock, mock_agent):
        w = self._worker(mock_bedrock, mock_agent)
        result = w._parse_result("", _make_task())
        assert result.status == Status.FAILURE

    def test_json_with_extra_text_still_parses(self, mock_bedrock, mock_agent):
        w = self._worker(mock_bedrock, mock_agent)
        raw = "Here is the result: " + _valid_json() + " Hope that helps!"
        result = w._parse_result(raw, _make_task())
        assert result.status == "success"


# ---------------------------------------------------------------------------
# Tests: validate_result  (R12.2)
# ---------------------------------------------------------------------------

class TestValidateResult:
    def test_valid_result_passes(self):
        result = ExecutionResult(
            status="success", confidence="high", recommendation="ok",
            risk_level="low", issues=[],
        )
        valid, errors = WorkerAgent.validate_result(result)
        assert valid is True
        assert errors == []

    def test_invalid_status_fails_validation(self):
        result = ExecutionResult(
            status="success", confidence="high", recommendation="ok",
            risk_level="low", issues=[],
        )
        # Force an invalid value by bypassing Pydantic
        object.__setattr__(result, "status", "bad")
        valid, errors = WorkerAgent.validate_result(result)
        assert valid is False
        assert any("status" in e for e in errors)

    def test_all_enum_combos_valid(self):
        for s in Status:
            for c in Confidence:
                for r in RiskLevel:
                    result = ExecutionResult(
                        status=s.value, confidence=c.value,
                        recommendation="x", risk_level=r.value, issues=[],
                    )
                    valid, errors = WorkerAgent.validate_result(result)
                    assert valid is True, f"Failed for {s}, {c}, {r}: {errors}"


# ---------------------------------------------------------------------------
# Tests: execute  (R12.1)
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
class TestExecute:
    def test_execute_returns_execution_result(self, mock_bedrock, mock_agent_cls):
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = _valid_json()
        mock_agent_cls.return_value = mock_agent_instance

        w = WorkerAgent("test_domain", _make_config(), [], "prompt")
        result = w.execute(_make_task(), _make_context())
        assert isinstance(result, ExecutionResult)
        assert result.status == "success"

    def test_execute_catches_exception(self, mock_bedrock, mock_agent_cls):
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = RuntimeError("boom")
        mock_agent_cls.return_value = mock_agent_instance

        w = WorkerAgent("test_domain", _make_config(), [], "prompt")
        result = w.execute(_make_task(), _make_context())
        assert result.status == Status.FAILURE
        assert any("boom" in i for i in result.issues)


# ---------------------------------------------------------------------------
# Tests: _build_context_prompt
# ---------------------------------------------------------------------------

@patch("agents.workers.base.Agent")
@patch("agents.workers.base.BedrockModel")
class TestBuildContextPrompt:
    def test_includes_task_intent(self, mock_bedrock, mock_agent):
        w = WorkerAgent("d", _make_config(), [], "p")
        prompt = w._build_context_prompt(_make_task("Check balance"), _make_context())
        assert "Check balance" in prompt

    def test_includes_failures(self, mock_bedrock, mock_agent):
        failure = InteractionRecord(
            user_id="u1", input="q", output="bad advice", status="failure",
            confidence="low", strategy_used="old_strategy",
        )
        ctx = _make_context(failures=[failure])
        w = WorkerAgent("d", _make_config(), [], "p")
        prompt = w._build_context_prompt(_make_task(), ctx)
        assert "old_strategy" in prompt

    def test_includes_patterns(self, mock_bedrock, mock_agent):
        pattern = SimilarPattern(content="saves 20% monthly", similarity_score=0.9)
        ctx = _make_context(patterns=[pattern])
        w = WorkerAgent("d", _make_config(), [], "p")
        prompt = w._build_context_prompt(_make_task(), ctx)
        assert "saves 20% monthly" in prompt
