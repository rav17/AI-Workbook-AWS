"""Structured observability logger. Traces: R14."""
from __future__ import annotations
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(message)s")


class CorrelatedLogger:
    """Structured logger with correlation ID for end-to-end tracing. Traces: R14.4."""

    def __init__(self, correlation_id: str = ""):
        self._correlation_id = correlation_id
        self._logger = logging.getLogger("smartbanker")

    def with_correlation(self, correlation_id: str) -> CorrelatedLogger:
        new = CorrelatedLogger(correlation_id)
        return new

    def _emit(self, event_type: str, **kwargs):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": self._correlation_id,
            "event": event_type,
            **kwargs,
        }
        self._logger.info(json.dumps(entry))

    def log_memory_prune(self, user_id: str, record_timestamp: str, reason: str) -> None:
        """Traces: R14.1."""
        self._emit("memory_prune", user_id=user_id, record_timestamp=record_timestamp, reason=reason)

    def log_pattern_reuse(self, pattern_id: str, similarity_score: float) -> None:
        """Traces: R14.2."""
        self._emit("pattern_reuse", pattern_id=pattern_id, similarity_score=similarity_score)

    def log_avoided_mistake(self, failure_id: str, request_context: str) -> None:
        """Traces: R14.3."""
        self._emit("avoided_mistake", failure_id=failure_id, request_context=request_context)

    def log_plan_generated(self, plan_id: str, task_count: int) -> None:
        self._emit("plan_generated", plan_id=plan_id, task_count=task_count)

    def log_reflection(self, should_retry: bool, reason: str) -> None:
        self._emit("reflection", should_retry=should_retry, reason=reason)

    def log_worker_execution(self, worker_domain: str, status: str, confidence: str) -> None:
        self._emit("worker_execution", worker_domain=worker_domain, status=status, confidence=confidence)

    def log_risk_decision(self, recommendation_id: str, risk_level: str, approved: bool) -> None:
        self._emit("risk_decision", recommendation_id=recommendation_id, risk_level=risk_level, approved=approved)

    # ------------------------------------------------------------------
    # Phase 2 log events (R14, R28.3, R29.3, R34.2, R36.2, R37.4)
    # ------------------------------------------------------------------

    def log_escalation(
        self, user_id: str, service_request_id: str, tracking_ref: str, estimated_timeline: str
    ) -> None:
        """Log service escalation event. Traces: R28.3."""
        self._emit(
            "service_escalation",
            user_id=user_id,
            service_request_id=service_request_id,
            tracking_ref=tracking_ref,
            estimated_timeline=estimated_timeline,
        )

    def log_priority_assignment(
        self, user_id: str, task_id: str, priority_level: str, tier: str
    ) -> None:
        """Log priority assignment for tier-based processing. Traces: R29.3."""
        self._emit(
            "priority_assignment",
            user_id=user_id,
            task_id=task_id,
            priority_level=priority_level,
            tier=tier,
        )

    def log_compliance_block(
        self, user_id: str, request_context: str, compliance_rule: str
    ) -> None:
        """Log compliance enforcement event. Traces: R34.2."""
        self._emit(
            "compliance_block",
            user_id=user_id,
            request_context=request_context,
            compliance_rule=compliance_rule,
        )

    def log_scope_limitation(
        self, user_id: str, request_context: str, scope_boundary: str
    ) -> None:
        """Log scope limitation response. Traces: R36.2."""
        self._emit(
            "scope_limitation",
            user_id=user_id,
            request_context=request_context,
            scope_boundary=scope_boundary,
        )

    def log_proactive_engagement(
        self, user_id: str, opportunity_type: str, notification_id: str
    ) -> None:
        """Log proactive engagement notification. Traces: R37.4."""
        self._emit(
            "proactive_engagement",
            user_id=user_id,
            opportunity_type=opportunity_type,
            notification_id=notification_id,
        )
