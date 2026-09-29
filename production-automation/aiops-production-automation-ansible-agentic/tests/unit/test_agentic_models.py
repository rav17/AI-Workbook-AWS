"""Unit tests for Agentic AI data models and enums."""

import pytest
from datetime import datetime, timezone

from src.agentic_ai.models import (
    # Enums
    OperatingMode,
    EscalationStatus,
    FallbackReason,
    # Domain models
    RemediationStep,
    RemediationPlan,
    CorrelationGroup,
    IncidentRecord,
    HumanResponse,
    PrerequisiteResult,
    # Configuration
    AgentConfig,
    OrchestratorConfig,
)
from src.models import EnrichedAlert, Severity, AlertStatus


class TestOperatingModeEnum:
    """Tests for OperatingMode enum."""

    def test_ai_only_value(self):
        assert OperatingMode.AI_ONLY.value == "ai_only"

    def test_rules_only_value(self):
        assert OperatingMode.RULES_ONLY.value == "rules_only"

    def test_ai_with_fallback_value(self):
        assert OperatingMode.AI_WITH_FALLBACK.value == "ai_with_fallback"

    def test_has_exactly_three_modes(self):
        assert len(OperatingMode) == 3

    def test_from_string(self):
        assert OperatingMode("ai_only") == OperatingMode.AI_ONLY
        assert OperatingMode("rules_only") == OperatingMode.RULES_ONLY
        assert OperatingMode("ai_with_fallback") == OperatingMode.AI_WITH_FALLBACK


class TestEscalationStatusEnum:
    """Tests for EscalationStatus enum."""

    def test_pending_value(self):
        assert EscalationStatus.PENDING.value == "pending"

    def test_approved_value(self):
        assert EscalationStatus.APPROVED.value == "approved"

    def test_rejected_value(self):
        assert EscalationStatus.REJECTED.value == "rejected"

    def test_timed_out_executed_value(self):
        assert EscalationStatus.TIMED_OUT_EXECUTED.value == "timed_out_executed"

    def test_timed_out_unresolved_value(self):
        assert EscalationStatus.TIMED_OUT_UNRESOLVED.value == "timed_out_unresolved"

    def test_has_exactly_five_statuses(self):
        assert len(EscalationStatus) == 5


class TestFallbackReasonEnum:
    """Tests for FallbackReason enum."""

    def test_throttling_value(self):
        assert FallbackReason.THROTTLING.value == "throttling"

    def test_timeout_value(self):
        assert FallbackReason.TIMEOUT.value == "timeout"

    def test_service_error_value(self):
        assert FallbackReason.SERVICE_ERROR.value == "service_error"

    def test_reasoning_timeout_value(self):
        assert FallbackReason.REASONING_TIMEOUT.value == "reasoning_timeout"

    def test_has_exactly_four_reasons(self):
        assert len(FallbackReason) == 4


class TestRemediationStep:
    """Tests for RemediationStep dataclass."""

    def test_basic_creation(self):
        step = RemediationStep(
            step_number=1,
            action="AWS-RunShellScript",
            target_resource="i-1234567890abcdef0",
        )
        assert step.step_number == 1
        assert step.action == "AWS-RunShellScript"
        assert step.target_resource == "i-1234567890abcdef0"
        assert step.parameters == {}
        assert step.expected_outcome == ""

    def test_with_parameters(self):
        step = RemediationStep(
            step_number=2,
            action="AWS-RestartService",
            target_resource="i-abc123",
            parameters={"serviceName": "nginx"},
            expected_outcome="Service restarted successfully",
        )
        assert step.parameters == {"serviceName": "nginx"}
        assert step.expected_outcome == "Service restarted successfully"


class TestRemediationPlan:
    """Tests for RemediationPlan dataclass."""

    def _make_step(self, n: int = 1) -> RemediationStep:
        return RemediationStep(
            step_number=n,
            action="AWS-RunShellScript",
            target_resource="i-abc123",
        )

    def test_basic_creation(self):
        plan = RemediationPlan(
            incident_ids=["inc-001"],
            steps=[self._make_step()],
            confidence_score=0.85,
            reasoning_explanation="High confidence based on history.",
            selected_action="restart_service",
            target_resource="i-abc123",
        )
        assert plan.confidence_score == 0.85
        assert plan.requires_escalation is False
        assert plan.fallback_used is False
        assert plan.fallback_reason is None
        assert plan.truncation_flag is False

    def test_confidence_score_zero_valid(self):
        plan = RemediationPlan(
            incident_ids=["inc-001"],
            steps=[self._make_step()],
            confidence_score=0.0,
            reasoning_explanation="No confidence.",
            selected_action="noop",
            target_resource="i-abc123",
        )
        assert plan.confidence_score == 0.0

    def test_confidence_score_one_valid(self):
        plan = RemediationPlan(
            incident_ids=["inc-001"],
            steps=[self._make_step()],
            confidence_score=1.0,
            reasoning_explanation="Full confidence.",
            selected_action="restart",
            target_resource="i-abc123",
        )
        assert plan.confidence_score == 1.0

    def test_confidence_score_below_zero_raises(self):
        with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
            RemediationPlan(
                incident_ids=["inc-001"],
                steps=[self._make_step()],
                confidence_score=-0.1,
                reasoning_explanation="Invalid.",
                selected_action="restart",
                target_resource="i-abc123",
            )

    def test_confidence_score_above_one_raises(self):
        with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
            RemediationPlan(
                incident_ids=["inc-001"],
                steps=[self._make_step()],
                confidence_score=1.1,
                reasoning_explanation="Invalid.",
                selected_action="restart",
                target_resource="i-abc123",
            )

    def test_max_20_steps_valid(self):
        steps = [self._make_step(n) for n in range(1, 21)]
        plan = RemediationPlan(
            incident_ids=["inc-001"],
            steps=steps,
            confidence_score=0.9,
            reasoning_explanation="Multi-step plan.",
            selected_action="complex_remediation",
            target_resource="i-abc123",
        )
        assert len(plan.steps) == 20

    def test_more_than_20_steps_raises(self):
        steps = [self._make_step(n) for n in range(1, 22)]
        with pytest.raises(ValueError, match="steps must contain at most 20 items"):
            RemediationPlan(
                incident_ids=["inc-001"],
                steps=steps,
                confidence_score=0.9,
                reasoning_explanation="Too many steps.",
                selected_action="complex",
                target_resource="i-abc123",
            )

    def test_reasoning_explanation_max_2048_valid(self):
        explanation = "x" * 2048
        plan = RemediationPlan(
            incident_ids=["inc-001"],
            steps=[self._make_step()],
            confidence_score=0.7,
            reasoning_explanation=explanation,
            selected_action="restart",
            target_resource="i-abc123",
        )
        assert len(plan.reasoning_explanation) == 2048

    def test_reasoning_explanation_over_2048_raises(self):
        explanation = "x" * 2049
        with pytest.raises(ValueError, match="reasoning_explanation must be at most 2048 characters"):
            RemediationPlan(
                incident_ids=["inc-001"],
                steps=[self._make_step()],
                confidence_score=0.7,
                reasoning_explanation=explanation,
                selected_action="restart",
                target_resource="i-abc123",
            )

    def test_with_fallback(self):
        plan = RemediationPlan(
            incident_ids=["inc-001"],
            steps=[self._make_step()],
            confidence_score=0.5,
            reasoning_explanation="Fallback used.",
            selected_action="restart",
            target_resource="i-abc123",
            fallback_used=True,
            fallback_reason=FallbackReason.THROTTLING,
        )
        assert plan.fallback_used is True
        assert plan.fallback_reason == FallbackReason.THROTTLING


class TestCorrelationGroup:
    """Tests for CorrelationGroup dataclass."""

    def _make_alert(self) -> EnrichedAlert:
        return EnrichedAlert(
            incident_id="inc-001",
            alert_name="HighCPU",
            severity=Severity.P2,
            status=AlertStatus.FIRING,
            labels={"instance": "i-abc123"},
            annotations={"summary": "CPU high"},
            starts_at=datetime.now(timezone.utc),
            ends_at=None,
        )

    def test_basic_creation(self):
        now = datetime.now(timezone.utc)
        group = CorrelationGroup(
            group_id="grp-001",
            alerts=[self._make_alert()],
            common_labels={"instance": "i-abc123"},
            window_start=now,
            window_end=now,
        )
        assert group.group_id == "grp-001"
        assert len(group.alerts) == 1

    def test_max_50_alerts_valid(self):
        now = datetime.now(timezone.utc)
        alerts = [self._make_alert() for _ in range(50)]
        group = CorrelationGroup(
            group_id="grp-002",
            alerts=alerts,
            common_labels={"instance": "i-abc123"},
            window_start=now,
            window_end=now,
        )
        assert len(group.alerts) == 50

    def test_more_than_50_alerts_raises(self):
        now = datetime.now(timezone.utc)
        alerts = [self._make_alert() for _ in range(51)]
        with pytest.raises(ValueError, match="alerts must contain at most 50 items"):
            CorrelationGroup(
                group_id="grp-003",
                alerts=alerts,
                common_labels={"instance": "i-abc123"},
                window_start=now,
                window_end=now,
            )


class TestIncidentRecord:
    """Tests for IncidentRecord dataclass."""

    def test_basic_creation(self):
        now = datetime.now(timezone.utc)
        record = IncidentRecord(
            incident_id="inc-001",
            alert_name="HighCPU",
            severity="P1",
            affected_service="web-api",
            affected_resource="i-abc123",
            remediation_action="restart_service",
            outcome="success",
            execution_duration_seconds=12.5,
            timestamp_completed=now,
            expiry_timestamp=int(now.timestamp()) + 86400 * 90,
        )
        assert record.incident_id == "inc-001"
        assert record.model_id is None
        assert record.fallback_used is False

    def test_confidence_score_validation(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
            IncidentRecord(
                incident_id="inc-001",
                alert_name="HighCPU",
                severity="P1",
                affected_service="web-api",
                affected_resource="i-abc123",
                remediation_action="restart",
                outcome="success",
                execution_duration_seconds=5.0,
                timestamp_completed=now,
                expiry_timestamp=int(now.timestamp()) + 86400,
                confidence_score=1.5,
            )

    def test_reasoning_summary_max_2048(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="reasoning_summary must be at most 2048 characters"):
            IncidentRecord(
                incident_id="inc-001",
                alert_name="HighCPU",
                severity="P1",
                affected_service="web-api",
                affected_resource="i-abc123",
                remediation_action="restart",
                outcome="success",
                execution_duration_seconds=5.0,
                timestamp_completed=now,
                expiry_timestamp=int(now.timestamp()) + 86400,
                reasoning_summary="x" * 2049,
            )

    def test_none_confidence_score_valid(self):
        now = datetime.now(timezone.utc)
        record = IncidentRecord(
            incident_id="inc-001",
            alert_name="HighCPU",
            severity="P1",
            affected_service="web-api",
            affected_resource="i-abc123",
            remediation_action="restart",
            outcome="success",
            execution_duration_seconds=5.0,
            timestamp_completed=now,
            expiry_timestamp=int(now.timestamp()) + 86400,
            confidence_score=None,
        )
        assert record.confidence_score is None


class TestHumanResponse:
    """Tests for HumanResponse dataclass."""

    def test_approve_action(self):
        now = datetime.now(timezone.utc)
        response = HumanResponse(
            action="approve",
            responder_identity="user@example.com",
            timestamp=now,
        )
        assert response.action == "approve"
        assert response.alternative_action is None

    def test_reject_with_alternative(self):
        now = datetime.now(timezone.utc)
        response = HumanResponse(
            action="reject_with_alternative",
            responder_identity="admin@example.com",
            timestamp=now,
            alternative_action="scale_up_instances",
        )
        assert response.action == "reject_with_alternative"
        assert response.alternative_action == "scale_up_instances"

    def test_reject_action(self):
        now = datetime.now(timezone.utc)
        response = HumanResponse(
            action="reject",
            responder_identity="ops@example.com",
            timestamp=now,
        )
        assert response.action == "reject"

    def test_invalid_action_raises(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="action must be one of"):
            HumanResponse(
                action="invalid_action",
                responder_identity="user@example.com",
                timestamp=now,
            )


class TestPrerequisiteResult:
    """Tests for PrerequisiteResult dataclass."""

    def test_all_ready(self):
        result = PrerequisiteResult(
            is_ready=True,
            registration_status=True,
            online_status=True,
            iam_role_attached=True,
        )
        assert result.is_ready is True
        assert result.error_message == ""

    def test_not_registered(self):
        result = PrerequisiteResult(
            is_ready=False,
            registration_status=False,
            online_status=True,
            iam_role_attached=True,
            error_message="instance not registered with SSM",
        )
        assert result.is_ready is False
        assert "not registered" in result.error_message

    def test_offline(self):
        result = PrerequisiteResult(
            is_ready=False,
            registration_status=True,
            online_status=False,
            iam_role_attached=True,
            error_message="instance offline",
        )
        assert result.online_status is False

    def test_missing_iam_role(self):
        result = PrerequisiteResult(
            is_ready=False,
            registration_status=True,
            online_status=True,
            iam_role_attached=False,
            error_message="instance missing required IAM role",
        )
        assert result.iam_role_attached is False


class TestAgentConfig:
    """Tests for AgentConfig dataclass with validation."""

    def test_default_values(self):
        config = AgentConfig(model_id="anthropic.claude-3-sonnet-20240229-v1:0")
        assert config.max_input_tokens == 4000
        assert config.max_output_tokens == 1000
        assert config.reasoning_timeout_seconds == 30
        assert config.retry_count == 2
        assert config.retry_backoff_base_seconds == 1.0
        assert config.escalation_threshold == 0.5
        assert config.p1_minimum_confidence == 0.8
        assert config.correlation_window_seconds == 300
        assert config.history_retention_days == 90

    def test_empty_model_id_raises(self):
        with pytest.raises(ValueError, match="model_id must be a non-empty string"):
            AgentConfig(model_id="")

    def test_max_input_tokens_below_range_raises(self):
        with pytest.raises(ValueError, match="max_input_tokens must be between 1000 and 16000"):
            AgentConfig(model_id="test-model", max_input_tokens=999)

    def test_max_input_tokens_above_range_raises(self):
        with pytest.raises(ValueError, match="max_input_tokens must be between 1000 and 16000"):
            AgentConfig(model_id="test-model", max_input_tokens=16001)

    def test_max_input_tokens_boundary_values(self):
        config_min = AgentConfig(model_id="test-model", max_input_tokens=1000)
        assert config_min.max_input_tokens == 1000
        config_max = AgentConfig(model_id="test-model", max_input_tokens=16000)
        assert config_max.max_input_tokens == 16000

    def test_max_output_tokens_below_range_raises(self):
        with pytest.raises(ValueError, match="max_output_tokens must be between 200 and 4000"):
            AgentConfig(model_id="test-model", max_output_tokens=199)

    def test_max_output_tokens_above_range_raises(self):
        with pytest.raises(ValueError, match="max_output_tokens must be between 200 and 4000"):
            AgentConfig(model_id="test-model", max_output_tokens=4001)

    def test_max_output_tokens_boundary_values(self):
        config_min = AgentConfig(model_id="test-model", max_output_tokens=200)
        assert config_min.max_output_tokens == 200
        config_max = AgentConfig(model_id="test-model", max_output_tokens=4000)
        assert config_max.max_output_tokens == 4000

    def test_escalation_threshold_below_range_raises(self):
        with pytest.raises(ValueError, match="escalation_threshold must be between 0.1 and 0.9"):
            AgentConfig(model_id="test-model", escalation_threshold=0.09)

    def test_escalation_threshold_above_range_raises(self):
        with pytest.raises(ValueError, match="escalation_threshold must be between 0.1 and 0.9"):
            AgentConfig(model_id="test-model", escalation_threshold=0.91)

    def test_escalation_threshold_boundary_values(self):
        config_min = AgentConfig(model_id="test-model", escalation_threshold=0.1)
        assert config_min.escalation_threshold == 0.1
        config_max = AgentConfig(model_id="test-model", escalation_threshold=0.9)
        assert config_max.escalation_threshold == 0.9

    def test_correlation_window_below_range_raises(self):
        with pytest.raises(ValueError, match="correlation_window_seconds must be between 30 and 900"):
            AgentConfig(model_id="test-model", correlation_window_seconds=29)

    def test_correlation_window_above_range_raises(self):
        with pytest.raises(ValueError, match="correlation_window_seconds must be between 30 and 900"):
            AgentConfig(model_id="test-model", correlation_window_seconds=901)

    def test_correlation_window_boundary_values(self):
        config_min = AgentConfig(model_id="test-model", correlation_window_seconds=30)
        assert config_min.correlation_window_seconds == 30
        config_max = AgentConfig(model_id="test-model", correlation_window_seconds=900)
        assert config_max.correlation_window_seconds == 900

    def test_history_retention_below_range_raises(self):
        with pytest.raises(ValueError, match="history_retention_days must be between 7 and 365"):
            AgentConfig(model_id="test-model", history_retention_days=6)

    def test_history_retention_above_range_raises(self):
        with pytest.raises(ValueError, match="history_retention_days must be between 7 and 365"):
            AgentConfig(model_id="test-model", history_retention_days=366)

    def test_history_retention_boundary_values(self):
        config_min = AgentConfig(model_id="test-model", history_retention_days=7)
        assert config_min.history_retention_days == 7
        config_max = AgentConfig(model_id="test-model", history_retention_days=365)
        assert config_max.history_retention_days == 365


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig dataclass with validation."""

    def test_default_values(self):
        config = OrchestratorConfig()
        assert config.operating_mode == OperatingMode.RULES_ONLY
        assert config.sqs_queue_url == ""
        assert config.sqs_visibility_timeout == 60
        assert config.escalation_timeout_minutes == 30
        assert config.health_check_interval_seconds == 30
        assert config.redaction_patterns == ["password", "secret", "token", "key"]

    def test_custom_operating_mode(self):
        config = OrchestratorConfig(operating_mode=OperatingMode.AI_WITH_FALLBACK)
        assert config.operating_mode == OperatingMode.AI_WITH_FALLBACK

    def test_escalation_timeout_below_range_raises(self):
        with pytest.raises(ValueError, match="escalation_timeout_minutes must be between 5 and 120"):
            OrchestratorConfig(escalation_timeout_minutes=4)

    def test_escalation_timeout_above_range_raises(self):
        with pytest.raises(ValueError, match="escalation_timeout_minutes must be between 5 and 120"):
            OrchestratorConfig(escalation_timeout_minutes=121)

    def test_escalation_timeout_boundary_values(self):
        config_min = OrchestratorConfig(escalation_timeout_minutes=5)
        assert config_min.escalation_timeout_minutes == 5
        config_max = OrchestratorConfig(escalation_timeout_minutes=120)
        assert config_max.escalation_timeout_minutes == 120

    def test_custom_redaction_patterns(self):
        config = OrchestratorConfig(
            redaction_patterns=["password", "secret", "token", "key", "credential"]
        )
        assert "credential" in config.redaction_patterns
