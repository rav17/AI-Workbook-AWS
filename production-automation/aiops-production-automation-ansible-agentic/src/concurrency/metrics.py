"""CloudWatch metric publishing and structured log emission for concurrency events."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class QueuedEvent:
    """Event data for a queued remediation action."""

    incident_id: str
    target_host: str
    blocking_incident_id: str
    queue_position: int
    estimated_wait_seconds: float


@dataclass
class ConflictEvent:
    """Event data for a resource conflict."""

    incident_id: str
    target_host: str
    conflicting_categories: list[str]
    blocking_incident_id: str
    resolution_strategy: str


@dataclass
class SuppressionEvent:
    """Event data for a duplicate alert suppression."""

    alert_fingerprint: str
    suppressed_incident_id: str
    original_incident_id: str
    suppression_window_remaining_seconds: float


@dataclass
class CircuitBreakerEvent:
    """Event data for a circuit breaker state transition."""

    host: str
    previous_state: str
    new_state: str
    consecutive_failures: int
    trigger: str


@dataclass
class PreemptionEvent:
    """Event data for a preemption."""

    preempted_incident_id: str
    preempting_incident_id: str
    preempted_severity: str
    preempting_severity: str
    target_host: str
    reason: str


class ConcurrencyMetrics:
    """CloudWatch metric publishing and structured log emission."""

    def __init__(self, cloudwatch_client=None, namespace: str = "AIOps/Concurrency") -> None:
        self._cloudwatch = cloudwatch_client
        self._namespace = namespace
        self._dropped_logs_counter = 0

        # Metric counters (reset each publish interval)
        self._lock_acquisitions = 0
        self._lock_contentions = 0
        self._suppressed_alerts = 0
        self._circuit_breaker_trips = 0
        self._preemptions = 0
        self._lock_hold_durations: list[float] = []
        self._last_metric_publish: float = time.time()
        self._consecutive_publish_failures = 0

    async def emit_queued_event(self, event: QueuedEvent) -> None:
        """Emit structured log for a queued remediation action."""
        await self._emit_log("concurrency.queued", {
            "incident_id": event.incident_id,
            "target_host": event.target_host,
            "blocking_incident_id": event.blocking_incident_id,
            "queue_position": event.queue_position,
            "estimated_wait_seconds": event.estimated_wait_seconds,
        })
        self._lock_contentions += 1

    async def emit_conflict_event(self, event: ConflictEvent) -> None:
        """Emit structured log for a resource conflict."""
        await self._emit_log("concurrency.conflict", {
            "incident_id": event.incident_id,
            "target_host": event.target_host,
            "conflicting_categories": event.conflicting_categories,
            "blocking_incident_id": event.blocking_incident_id,
            "resolution_strategy": event.resolution_strategy,
        })

    async def emit_suppression_event(self, event: SuppressionEvent) -> None:
        """Emit structured log for a duplicate alert suppression."""
        await self._emit_log("concurrency.suppression", {
            "alert_fingerprint": event.alert_fingerprint,
            "suppressed_incident_id": event.suppressed_incident_id,
            "original_incident_id": event.original_incident_id,
            "suppression_window_remaining_seconds": event.suppression_window_remaining_seconds,
        })
        self._suppressed_alerts += 1

    async def emit_circuit_breaker_event(self, event: CircuitBreakerEvent) -> None:
        """Emit structured log for a circuit breaker state transition."""
        await self._emit_log("concurrency.circuit_breaker", {
            "host": event.host,
            "previous_state": event.previous_state,
            "new_state": event.new_state,
            "consecutive_failures": event.consecutive_failures,
            "trigger": event.trigger,
        })
        if event.new_state == "OPEN":
            self._circuit_breaker_trips += 1

    async def emit_preemption_event(self, event: PreemptionEvent) -> None:
        """Emit structured log for a preemption."""
        await self._emit_log("concurrency.preemption", {
            "preempted_incident_id": event.preempted_incident_id,
            "preempting_incident_id": event.preempting_incident_id,
            "preempted_severity": event.preempted_severity,
            "preempting_severity": event.preempting_severity,
            "target_host": event.target_host,
            "reason": event.reason,
        })
        self._preemptions += 1

    def record_lock_acquisition(self) -> None:
        """Record a successful lock acquisition."""
        self._lock_acquisitions += 1

    def record_lock_hold_duration(self, duration_seconds: float) -> None:
        """Record a lock hold duration."""
        self._lock_hold_durations.append(duration_seconds)

    async def publish_periodic_metrics(self) -> None:
        """Publish accumulated metrics to CloudWatch (60-second intervals)."""
        if self._cloudwatch is None:
            return

        now = time.time()
        if now - self._last_metric_publish < 60:
            return

        metric_data = [
            {
                "MetricName": "LockAcquisitions",
                "Value": self._lock_acquisitions,
                "Unit": "Count",
            },
            {
                "MetricName": "LockContentions",
                "Value": self._lock_contentions,
                "Unit": "Count",
            },
            {
                "MetricName": "SuppressedAlerts",
                "Value": self._suppressed_alerts,
                "Unit": "Count",
            },
            {
                "MetricName": "CircuitBreakerTrips",
                "Value": self._circuit_breaker_trips,
                "Unit": "Count",
            },
            {
                "MetricName": "Preemptions",
                "Value": self._preemptions,
                "Unit": "Count",
            },
        ]

        if self._lock_hold_durations:
            avg_duration = sum(self._lock_hold_durations) / len(self._lock_hold_durations)
            metric_data.append({
                "MetricName": "AvgLockHoldDuration",
                "Value": avg_duration,
                "Unit": "Seconds",
            })

        try:
            self._cloudwatch.put_metric_data(
                Namespace=self._namespace,
                MetricData=metric_data,
            )
            self._consecutive_publish_failures = 0
        except Exception as e:
            self._consecutive_publish_failures += 1
            if self._consecutive_publish_failures >= 3:
                logger.error(
                    "CloudWatch metric publishing failed for 3 consecutive intervals",
                    extra={
                        "last_successful_publish": self._last_metric_publish,
                        "error": str(e),
                    },
                )

        # Reset counters
        self._last_metric_publish = now
        self._lock_acquisitions = 0
        self._lock_contentions = 0
        self._suppressed_alerts = 0
        self._circuit_breaker_trips = 0
        self._preemptions = 0
        self._lock_hold_durations = []

    @property
    def dropped_logs_count(self) -> int:
        """Get the number of dropped log emissions."""
        return self._dropped_logs_counter

    async def _emit_log(self, event_type: str, data: dict) -> None:
        """Emit a structured JSON log entry with retry."""
        log_entry = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }

        try:
            logger.info(json.dumps(log_entry))
        except Exception:
            # Retry once within 5 seconds
            try:
                await asyncio.sleep(0.1)
                logger.info(json.dumps(log_entry))
            except Exception:
                self._dropped_logs_counter += 1
