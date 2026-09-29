"""Unit tests for the MetricsPublisher class.

Validates: Requirements 9.2, 10.9
"""

import pytest
from unittest.mock import MagicMock, patch

from src.agentic_ai.observability.metrics_publisher import (
    AUTO_SCALING_METRIC,
    METRIC_DEFINITIONS,
    MetricUnit,
    MetricsPublisher,
)


@pytest.fixture
def mock_cloudwatch():
    """Mock boto3 CloudWatch client."""
    with patch("boto3.client") as mock_client:
        cw_mock = MagicMock()
        mock_client.return_value = cw_mock
        yield cw_mock


@pytest.fixture
def publisher(mock_cloudwatch):
    """Create a MetricsPublisher with mocked CloudWatch client."""
    pub = MetricsPublisher(environment="dev", flush_interval_seconds=1.0)
    pub._cloudwatch_client = mock_cloudwatch
    return pub


class TestMetricDefinitions:
    """Verify that all required metrics are defined with correct units."""

    def test_all_required_metrics_present(self):
        """All metrics specified in Requirement 9.2 must be defined."""
        expected_metrics = {
            "AlertsReceived",
            "AIReasoningInvocations",
            "AIReasoningLatency",
            "FallbackToRulesCount",
            "RemediationsExecuted",
            "RemediationSuccessCount",
            "RemediationFailureCount",
            "HumanEscalationsCount",
            "BedrockThrottleCount",
            "DeadLetterQueueDepth",
        }
        assert set(METRIC_DEFINITIONS.keys()) == expected_metrics

    def test_count_metrics_have_count_unit(self):
        """All count-type metrics should use the Count unit."""
        count_metrics = [
            "AlertsReceived",
            "AIReasoningInvocations",
            "FallbackToRulesCount",
            "RemediationsExecuted",
            "RemediationSuccessCount",
            "RemediationFailureCount",
            "HumanEscalationsCount",
            "BedrockThrottleCount",
            "DeadLetterQueueDepth",
        ]
        for name in count_metrics:
            assert METRIC_DEFINITIONS[name].unit == MetricUnit.COUNT, (
                f"{name} should have unit Count"
            )

    def test_latency_metric_has_milliseconds_unit(self):
        """AIReasoningLatency should use Milliseconds unit."""
        assert METRIC_DEFINITIONS["AIReasoningLatency"].unit == MetricUnit.MILLISECONDS

    def test_auto_scaling_metric_defined(self):
        """AutoScalingAboveNominal metric should be defined separately."""
        assert AUTO_SCALING_METRIC.name == "AutoScalingAboveNominal"
        assert AUTO_SCALING_METRIC.unit == MetricUnit.COUNT


class TestMetricsPublisherNamespace:
    """Verify namespace construction."""

    def test_namespace_uses_environment(self, publisher):
        """Namespace should be AIOps/{environment}."""
        assert publisher.namespace == "AIOps/dev"

    def test_namespace_with_prod_environment(self, mock_cloudwatch):
        """Prod environment produces correct namespace."""
        pub = MetricsPublisher(environment="prod")
        pub._cloudwatch_client = mock_cloudwatch
        assert pub.namespace == "AIOps/prod"

    def test_namespace_reads_environment_from_env_var(self, mock_cloudwatch):
        """Should read ENVIRONMENT env var when not explicitly provided."""
        with patch.dict("os.environ", {"ENVIRONMENT": "staging"}):
            pub = MetricsPublisher()
            pub._cloudwatch_client = mock_cloudwatch
            assert pub.namespace == "AIOps/staging"


class TestRecordMetric:
    """Verify metric recording behavior."""

    def test_record_valid_metric(self, publisher):
        """Recording a valid metric adds to the buffer."""
        publisher.record("AlertsReceived", 1.0)
        assert len(publisher._buffer) == 1
        assert publisher._buffer[0]["MetricName"] == "AlertsReceived"
        assert publisher._buffer[0]["Value"] == 1.0
        assert publisher._buffer[0]["Unit"] == "Count"

    def test_record_latency_metric(self, publisher):
        """Recording AIReasoningLatency uses Milliseconds unit."""
        publisher.record("AIReasoningLatency", 1250.5)
        assert publisher._buffer[0]["Unit"] == "Milliseconds"
        assert publisher._buffer[0]["Value"] == 1250.5

    def test_record_includes_environment_dimension(self, publisher):
        """All recorded metrics should include Environment dimension."""
        publisher.record("AlertsReceived", 1.0)
        dimensions = publisher._buffer[0]["Dimensions"]
        env_dims = [d for d in dimensions if d["Name"] == "Environment"]
        assert len(env_dims) == 1
        assert env_dims[0]["Value"] == "dev"

    def test_record_with_extra_dimensions(self, publisher):
        """Extra dimensions should be appended to the metric datum."""
        publisher.record("AlertsReceived", 1.0, dimensions={"AlertName": "HighCPU"})
        dimensions = publisher._buffer[0]["Dimensions"]
        assert len(dimensions) == 2
        alert_dims = [d for d in dimensions if d["Name"] == "AlertName"]
        assert len(alert_dims) == 1
        assert alert_dims[0]["Value"] == "HighCPU"

    def test_record_unknown_metric_raises_value_error(self, publisher):
        """Recording an unknown metric name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown metric 'InvalidMetric'"):
            publisher.record("InvalidMetric", 1.0)

    def test_record_includes_timestamp(self, publisher):
        """Recorded metric should have a Timestamp field."""
        publisher.record("AlertsReceived", 1.0)
        assert "Timestamp" in publisher._buffer[0]
        assert publisher._buffer[0]["Timestamp"] > 0


class TestPublishScalingMetric:
    """Verify AutoScalingAboveNominal metric behavior (Requirement 10.9)."""

    def test_publish_when_task_count_above_5(self, publisher):
        """Should publish metric when task_count > 5."""
        publisher.publish_scaling_metric(task_count=6)
        assert len(publisher._buffer) == 1
        assert publisher._buffer[0]["MetricName"] == "AutoScalingAboveNominal"
        assert publisher._buffer[0]["Value"] == 6.0

    def test_no_publish_when_task_count_at_5(self, publisher):
        """Should NOT publish metric when task_count == 5."""
        publisher.publish_scaling_metric(task_count=5)
        assert len(publisher._buffer) == 0

    def test_no_publish_when_task_count_below_5(self, publisher):
        """Should NOT publish metric when task_count < 5."""
        publisher.publish_scaling_metric(task_count=3)
        assert len(publisher._buffer) == 0

    def test_no_publish_when_task_count_zero(self, publisher):
        """Should NOT publish metric when task_count is 0."""
        publisher.publish_scaling_metric(task_count=0)
        assert len(publisher._buffer) == 0

    def test_publish_includes_task_count_dimension(self, publisher):
        """Published metric should include TaskCount dimension."""
        publisher.publish_scaling_metric(task_count=8)
        dimensions = publisher._buffer[0]["Dimensions"]
        task_dims = [d for d in dimensions if d["Name"] == "TaskCount"]
        assert len(task_dims) == 1
        assert task_dims[0]["Value"] == "8"

    def test_publish_scaling_metric_value_equals_task_count(self, publisher):
        """The metric value should equal the task_count."""
        publisher.publish_scaling_metric(task_count=10)
        assert publisher._buffer[0]["Value"] == 10.0


class TestFlush:
    """Verify metric flushing to CloudWatch."""

    def test_flush_publishes_buffered_metrics(self, publisher, mock_cloudwatch):
        """Flushing should call put_metric_data with buffered metrics."""
        publisher.record("AlertsReceived", 1.0)
        publisher.record("RemediationsExecuted", 3.0)
        publisher._flush()

        mock_cloudwatch.put_metric_data.assert_called_once()
        call_kwargs = mock_cloudwatch.put_metric_data.call_args[1]
        assert call_kwargs["Namespace"] == "AIOps/dev"
        assert len(call_kwargs["MetricData"]) == 2

    def test_flush_clears_buffer(self, publisher, mock_cloudwatch):
        """Buffer should be empty after successful flush."""
        publisher.record("AlertsReceived", 1.0)
        publisher._flush()
        assert len(publisher._buffer) == 0

    def test_flush_empty_buffer_does_nothing(self, publisher, mock_cloudwatch):
        """Flushing an empty buffer should not call CloudWatch."""
        publisher._flush()
        mock_cloudwatch.put_metric_data.assert_not_called()

    def test_flush_retries_on_failure(self, publisher, mock_cloudwatch):
        """Failed metrics should be re-buffered for retry."""
        mock_cloudwatch.put_metric_data.side_effect = Exception("Throttled")
        publisher.record("AlertsReceived", 1.0)
        publisher._flush()
        # Metrics should be re-buffered
        assert len(publisher._buffer) == 1


class TestStartStop:
    """Verify lifecycle management."""

    def test_start_sets_running(self, publisher):
        """Starting the publisher should set _running to True."""
        publisher.start()
        assert publisher._running is True
        publisher.stop()

    def test_stop_flushes_remaining(self, publisher, mock_cloudwatch):
        """Stopping should flush any remaining buffered metrics."""
        publisher.record("AlertsReceived", 1.0)
        publisher.stop()
        mock_cloudwatch.put_metric_data.assert_called_once()

    def test_double_start_is_idempotent(self, publisher):
        """Calling start() twice should not create duplicate threads."""
        publisher.start()
        thread1 = publisher._flush_thread
        publisher.start()
        thread2 = publisher._flush_thread
        assert thread1 is thread2
        publisher.stop()
