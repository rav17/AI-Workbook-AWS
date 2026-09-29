"""CloudWatch custom metrics publisher for the AIOps system.

Publishes operational metrics to the AIOps/{environment} namespace.
Supports batching with periodic flush to stay within the 60-second
publish latency requirement.

Requirements: 9.2, 10.9
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import boto3

logger = logging.getLogger(__name__)


class MetricUnit(str, Enum):
    """CloudWatch metric units used by the AIOps system."""

    COUNT = "Count"
    MILLISECONDS = "Milliseconds"


@dataclass(frozen=True)
class MetricDefinition:
    """Defines a supported custom metric with its name and unit."""

    name: str
    unit: MetricUnit


# All custom metrics defined in Requirement 9.2
METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "AlertsReceived": MetricDefinition(name="AlertsReceived", unit=MetricUnit.COUNT),
    "AIReasoningInvocations": MetricDefinition(
        name="AIReasoningInvocations", unit=MetricUnit.COUNT
    ),
    "AIReasoningLatency": MetricDefinition(
        name="AIReasoningLatency", unit=MetricUnit.MILLISECONDS
    ),
    "FallbackToRulesCount": MetricDefinition(
        name="FallbackToRulesCount", unit=MetricUnit.COUNT
    ),
    "RemediationsExecuted": MetricDefinition(
        name="RemediationsExecuted", unit=MetricUnit.COUNT
    ),
    "RemediationSuccessCount": MetricDefinition(
        name="RemediationSuccessCount", unit=MetricUnit.COUNT
    ),
    "RemediationFailureCount": MetricDefinition(
        name="RemediationFailureCount", unit=MetricUnit.COUNT
    ),
    "HumanEscalationsCount": MetricDefinition(
        name="HumanEscalationsCount", unit=MetricUnit.COUNT
    ),
    "BedrockThrottleCount": MetricDefinition(
        name="BedrockThrottleCount", unit=MetricUnit.COUNT
    ),
    "DeadLetterQueueDepth": MetricDefinition(
        name="DeadLetterQueueDepth", unit=MetricUnit.COUNT
    ),
}

# The auto-scaling metric defined in Requirement 10.9
AUTO_SCALING_METRIC = MetricDefinition(
    name="AutoScalingAboveNominal", unit=MetricUnit.COUNT
)

# Maximum metric data points per put_metric_data call (AWS limit is 1000)
MAX_BATCH_SIZE = 20

# Default flush interval in seconds (must be < 60s per requirement)
DEFAULT_FLUSH_INTERVAL_SECONDS = 30.0


@dataclass
class MetricsPublisher:
    """Publishes custom CloudWatch metrics for the AIOps system.

    Namespace: AIOps/{environment}
    Publishes within 60s of event occurrence via periodic batch flush.

    Usage:
        publisher = MetricsPublisher()
        publisher.start()  # Start background flush thread

        publisher.record("AlertsReceived", 1.0)
        publisher.record("AIReasoningLatency", 1250.5)
        publisher.publish_scaling_metric(task_count=7)

        publisher.stop()  # Stop and flush remaining metrics
    """

    environment: str = field(default_factory=lambda: os.environ.get("ENVIRONMENT", "dev"))
    flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS
    _cloudwatch_client: Any = field(default=None, init=False, repr=False)
    _buffer: list[dict] = field(default_factory=list, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _flush_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _running: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self._cloudwatch_client = boto3.client("cloudwatch")

    @property
    def namespace(self) -> str:
        """CloudWatch namespace for all AIOps metrics."""
        return f"AIOps/{self.environment}"

    def start(self) -> None:
        """Start the background flush thread."""
        if self._running:
            return
        self._running = True
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="metrics-flush"
        )
        self._flush_thread.start()
        logger.info(
            "MetricsPublisher started (namespace=%s, flush_interval=%.1fs)",
            self.namespace,
            self.flush_interval_seconds,
        )

    def stop(self) -> None:
        """Stop the background flush thread and flush remaining metrics."""
        self._running = False
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5.0)
        # Final flush of any remaining buffered metrics
        self._flush()
        logger.info("MetricsPublisher stopped")

    def record(self, metric_name: str, value: float, dimensions: dict[str, str] | None = None) -> None:
        """Record a metric data point for batched publishing.

        Args:
            metric_name: Must be one of the keys in METRIC_DEFINITIONS.
            value: The metric value.
            dimensions: Optional additional dimensions beyond the defaults.

        Raises:
            ValueError: If metric_name is not a recognized metric.
        """
        if metric_name not in METRIC_DEFINITIONS:
            raise ValueError(
                f"Unknown metric '{metric_name}'. "
                f"Valid metrics: {sorted(METRIC_DEFINITIONS.keys())}"
            )

        definition = METRIC_DEFINITIONS[metric_name]
        metric_datum = self._build_metric_datum(
            definition.name, value, definition.unit.value, dimensions
        )

        with self._lock:
            self._buffer.append(metric_datum)

        # If buffer is getting large, flush immediately
        if len(self._buffer) >= MAX_BATCH_SIZE:
            self._flush()

    def publish_scaling_metric(self, task_count: int) -> None:
        """Publish AutoScalingAboveNominal metric only when task_count > 5.

        Per Requirement 10.9: When the ECS auto-scaling scales the service
        above 5 tasks, publish AutoScalingAboveNominal metric tagged with
        the current task count.

        Args:
            task_count: Current number of ECS tasks running.
        """
        if task_count <= 5:
            return

        metric_datum = self._build_metric_datum(
            AUTO_SCALING_METRIC.name,
            float(task_count),
            AUTO_SCALING_METRIC.unit.value,
            {"TaskCount": str(task_count)},
        )

        with self._lock:
            self._buffer.append(metric_datum)

        logger.info(
            "AutoScalingAboveNominal metric queued (task_count=%d)", task_count
        )

    def _build_metric_datum(
        self,
        metric_name: str,
        value: float,
        unit: str,
        extra_dimensions: dict[str, str] | None = None,
    ) -> dict:
        """Build a CloudWatch MetricDatum dictionary."""
        dimensions = [
            {"Name": "Environment", "Value": self.environment},
        ]
        if extra_dimensions:
            for dim_name, dim_value in extra_dimensions.items():
                dimensions.append({"Name": dim_name, "Value": dim_value})

        return {
            "MetricName": metric_name,
            "Dimensions": dimensions,
            "Timestamp": time.time(),
            "Value": value,
            "Unit": unit,
        }

    def _flush_loop(self) -> None:
        """Background thread that flushes buffered metrics at regular intervals."""
        while self._running:
            time.sleep(self.flush_interval_seconds)
            self._flush()

    def _flush(self) -> None:
        """Flush all buffered metrics to CloudWatch in batches."""
        with self._lock:
            if not self._buffer:
                return
            to_publish = self._buffer[:]
            self._buffer.clear()

        # Publish in batches of MAX_BATCH_SIZE
        for i in range(0, len(to_publish), MAX_BATCH_SIZE):
            batch = to_publish[i : i + MAX_BATCH_SIZE]
            # Convert timestamps from epoch float to datetime-compatible format
            # CloudWatch accepts epoch seconds or datetime objects
            metric_data = []
            for datum in batch:
                from datetime import datetime, timezone

                ts = datum.pop("Timestamp")
                datum["Timestamp"] = datetime.fromtimestamp(ts, tz=timezone.utc)
                metric_data.append(datum)

            try:
                self._cloudwatch_client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=metric_data,
                )
                logger.debug(
                    "Published %d metrics to %s", len(metric_data), self.namespace
                )
            except Exception as exc:
                logger.error(
                    "Failed to publish %d metrics to CloudWatch: %s",
                    len(metric_data),
                    exc,
                )
                # Re-buffer failed metrics for retry on next flush
                with self._lock:
                    self._buffer.extend(metric_data)
