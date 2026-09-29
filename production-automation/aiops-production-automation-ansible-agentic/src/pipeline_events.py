"""Structured Pipeline Events — enables replay and analytics.

Emits typed events for each pipeline stage transition, providing:
1. Queryable event history (by type, incident_id, time range, outcome)
2. Replay capability for testing pipeline changes against historical data
3. Real-time dashboarding via event streaming

Events are written to structured JSON log (CloudWatch Logs compatible)
and stored in memory for the last N events (for status API).

Event types:
- alert.received, alert.normalized, alert.enriched, alert.unenriched
- playbook.matched, playbook.unmatched
- guardrail.evaluated
- execution.started, execution.completed, execution.aborted
- baking.result
- notification.sent
- alert.suppressed, alert.auto_resolved, alert.inhibited
"""

import json
import logging
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Keep last N events in memory for status API queries
MAX_IN_MEMORY_EVENTS = 1000
# Schema version for forward compatibility
SCHEMA_VERSION = "1.0"


class EventType(Enum):
    """Pipeline event types."""

    ALERT_RECEIVED = "alert.received"
    ALERT_NORMALIZED = "alert.normalized"
    ALERT_ENRICHED = "alert.enriched"
    ALERT_UNENRICHED = "alert.unenriched"
    ALERT_SUPPRESSED = "alert.suppressed"
    ALERT_INHIBITED = "alert.inhibited"
    ALERT_AUTO_RESOLVED = "alert.auto_resolved"
    PLAYBOOK_MATCHED = "playbook.matched"
    PLAYBOOK_UNMATCHED = "playbook.unmatched"
    GUARDRAIL_EVALUATED = "guardrail.evaluated"
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_ABORTED = "execution.aborted"
    BAKING_RESULT = "baking.result"
    NOTIFICATION_SENT = "notification.sent"
    STORM_ACTIVATED = "storm.activated"
    STORM_DEACTIVATED = "storm.deactivated"
    FLEET_BREAKER_TRIPPED = "fleet_breaker.tripped"
    FLEET_BREAKER_RECOVERED = "fleet_breaker.recovered"


@dataclass
class PipelineEvent:
    """A single structured pipeline event."""

    event_type: str
    incident_id: str
    timestamp: float = field(default_factory=time.time)
    schema_version: str = SCHEMA_VERSION
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize to JSON for CloudWatch Logs / JSON-lines output."""
        return json.dumps({
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            **self.data,
        }, default=str)


class PipelineEventEmitter:
    """Emits structured events for pipeline observability.

    Events are:
    1. Written to structured logger (for CloudWatch Logs Insights queries)
    2. Stored in memory ring buffer (for /events status endpoint)
    3. Available for real-time subscribers (future: EventBridge/DynamoDB stream)

    Thread-safe.
    """

    def __init__(self, max_events: int = MAX_IN_MEMORY_EVENTS) -> None:
        self._lock = Lock()
        self._events: deque = deque(maxlen=max_events)
        self._event_logger = logging.getLogger("pipeline.events")
        self._total_emitted: int = 0

    def emit(
        self,
        event_type: EventType,
        incident_id: str,
        **kwargs: Any,
    ) -> None:
        """Emit a pipeline event.

        Args:
            event_type: The type of event.
            incident_id: The incident this event relates to.
            **kwargs: Additional event-specific data fields.
        """
        event = PipelineEvent(
            event_type=event_type.value,
            incident_id=incident_id,
            data=kwargs,
        )

        # Log as structured JSON
        self._event_logger.info(event.to_json())

        # Store in ring buffer
        with self._lock:
            self._events.append(event)
            self._total_emitted += 1

    # --- Convenience methods for common events ---

    def alert_received(
        self, incident_id: str, alert_name: str, severity: str
    ) -> None:
        self.emit(
            EventType.ALERT_RECEIVED,
            incident_id,
            alert_name=alert_name,
            severity=severity,
        )

    def alert_enriched(
        self, incident_id: str, source: str, hostname: str, service: str
    ) -> None:
        self.emit(
            EventType.ALERT_ENRICHED,
            incident_id,
            source=source,
            hostname=hostname,
            service=service,
        )

    def alert_suppressed(
        self, incident_id: str, reason: str, parent_incident_id: str = ""
    ) -> None:
        self.emit(
            EventType.ALERT_SUPPRESSED,
            incident_id,
            reason=reason,
            parent_incident_id=parent_incident_id,
        )

    def alert_inhibited(
        self, incident_id: str, reason: str, parent_incident_id: str = ""
    ) -> None:
        self.emit(
            EventType.ALERT_INHIBITED,
            incident_id,
            reason=reason,
            parent_incident_id=parent_incident_id,
        )

    def alert_auto_resolved(
        self, incident_id: str, resolution_time_seconds: float = 0
    ) -> None:
        self.emit(
            EventType.ALERT_AUTO_RESOLVED,
            incident_id,
            resolution_time_seconds=resolution_time_seconds,
        )

    def playbook_matched(
        self, incident_id: str, rule_name: str, playbook_path: str, score: float = 0
    ) -> None:
        self.emit(
            EventType.PLAYBOOK_MATCHED,
            incident_id,
            rule_name=rule_name,
            playbook_path=playbook_path,
            effectiveness_score=score,
        )

    def execution_started(
        self, incident_id: str, playbook: str, host: str
    ) -> None:
        self.emit(
            EventType.EXECUTION_STARTED,
            incident_id,
            playbook=playbook,
            host=host,
        )

    def execution_completed(
        self, incident_id: str, status: str, duration: float
    ) -> None:
        self.emit(
            EventType.EXECUTION_COMPLETED,
            incident_id,
            status=status,
            duration_seconds=duration,
        )

    def guardrail_evaluated(
        self, incident_id: str, decision: str, checks_passed: list, duration: float
    ) -> None:
        self.emit(
            EventType.GUARDRAIL_EVALUATED,
            incident_id,
            decision=decision,
            checks_passed=checks_passed,
            duration_seconds=duration,
        )

    # --- Query methods ---

    def get_recent_events(
        self,
        limit: int = 50,
        event_type: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> list[dict]:
        """Get recent events with optional filtering.

        Args:
            limit: Max number of events to return.
            event_type: Filter by event type (e.g., "execution.completed").
            incident_id: Filter by incident ID.

        Returns:
            List of event dicts (most recent first).
        """
        with self._lock:
            results = []
            for event in reversed(self._events):
                if event_type and event.event_type != event_type:
                    continue
                if incident_id and event.incident_id != incident_id:
                    continue
                results.append({
                    "event_type": event.event_type,
                    "incident_id": event.incident_id,
                    "timestamp": event.timestamp,
                    **event.data,
                })
                if len(results) >= limit:
                    break
            return results

    def get_stats(self) -> dict:
        """Get event emitter statistics."""
        with self._lock:
            type_counts: dict[str, int] = {}
            for event in self._events:
                type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1

            return {
                "total_emitted": self._total_emitted,
                "in_memory": len(self._events),
                "max_capacity": self._events.maxlen,
                "by_type": type_counts,
            }
