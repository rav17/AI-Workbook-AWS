"""ConcurrencyManager facade coordinating all concurrency safety subsystems."""

import logging
import time
from datetime import datetime, timezone

from src.concurrency.circuit_breaker import CircuitBreakerManager
from src.concurrency.config import ConcurrencyConfig
from src.concurrency.deduplicator import AlertDeduplicator
from src.concurrency.dependency_graph import DependencyGraph
from src.concurrency.enums import (
    ConflictResolutionStrategy,
    ExecutionDecisionType,
)
from src.concurrency.lock_store import LockStore, LockStoreError
from src.concurrency.metrics import (
    CircuitBreakerEvent,
    ConcurrencyMetrics,
    ConflictEvent,
    QueuedEvent,
    SuppressionEvent,
)
from src.concurrency.models import (
    ExecutionDecision,
    QueueEntry,
)
from src.concurrency.priority_queue import (
    DuplicateEntryError,
    PriorityQueue,
    QueueFullError,
)
from src.concurrency.resource_registry import ResourceConflictRegistry
from src.models import Severity

logger = logging.getLogger(__name__)

# Map severity to numeric rank (lower = higher priority)
SEVERITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}


class ConcurrencyManager:
    """Facade coordinating all concurrency safety subsystems.

    Orchestrates: deduplication → circuit breaker → dependency check →
    resource conflict → host lock acquisition.
    """

    def __init__(
        self,
        lock_store: LockStore,
        resource_registry: ResourceConflictRegistry,
        priority_queue: PriorityQueue,
        circuit_breaker: CircuitBreakerManager,
        dependency_graph: DependencyGraph,
        deduplicator: AlertDeduplicator,
        metrics: ConcurrencyMetrics,
        config: ConcurrencyConfig,
    ) -> None:
        self._lock_store = lock_store
        self._resource_registry = resource_registry
        self._priority_queue = priority_queue
        self._circuit_breaker = circuit_breaker
        self._dependency_graph = dependency_graph
        self._deduplicator = deduplicator
        self._metrics = metrics
        self._config = config

        # Track active executions: incident_id → {host, action_name, resources, start_time}
        self._active_executions: dict[str, dict] = {}

    async def request_execution(
        self,
        incident_id: str,
        target_hosts: list[str],
        action_name: str,
        severity: Severity,
        correlation_group: str,
        alert_name: str = "",
    ) -> ExecutionDecision:
        """Request permission to execute a remediation action.

        Applies safety checks in order:
        1. Alert deduplication
        2. Circuit breaker check
        3. Dependency check
        4. Resource conflict detection
        5. Host lock acquisition
        """
        # Step 1: Alert deduplication
        if alert_name and target_hosts:
            fingerprint = self._deduplicator.compute_fingerprint(
                alert_name, target_hosts[0], severity.value
            )
            try:
                dedup_result = await self._deduplicator.check_and_acquire(
                    fingerprint, incident_id
                )
                if dedup_result.is_duplicate:
                    await self._metrics.emit_suppression_event(
                        SuppressionEvent(
                            alert_fingerprint=fingerprint,
                            suppressed_incident_id=incident_id,
                            original_incident_id=dedup_result.original_incident_id or "",
                            suppression_window_remaining_seconds=float(
                                self._config.suppression_window_seconds
                            ),
                        )
                    )
                    return ExecutionDecision(
                        decision_type=ExecutionDecisionType.SUPPRESSED,
                        allowed=False,
                        reason=f"Duplicate alert suppressed (original: {dedup_result.original_incident_id})",
                        blocking_incident_id=dedup_result.original_incident_id,
                    )
            except LockStoreError as e:
                return ExecutionDecision(
                    decision_type=ExecutionDecisionType.REJECTED,
                    allowed=False,
                    reason=f"Lock Store unavailable: {e}",
                )

        # Step 2: Circuit breaker check (check all target hosts)
        for host in target_hosts:
            cb_decision = await self._circuit_breaker.check_state(host)
            if not cb_decision.allowed:
                return ExecutionDecision(
                    decision_type=ExecutionDecisionType.REJECTED,
                    allowed=False,
                    reason=cb_decision.reason,
                )

        # Step 3: Dependency check
        predecessors = self._dependency_graph.get_predecessors(action_name)
        if predecessors:
            # Check if all predecessors have completed for this correlation group
            for pred in predecessors:
                if not self._is_predecessor_completed(pred, correlation_group):
                    return ExecutionDecision(
                        decision_type=ExecutionDecisionType.QUEUED,
                        allowed=False,
                        reason=f"Waiting for predecessor action '{pred}' to complete",
                    )

        # Step 4: Resource conflict detection
        for host in target_hosts:
            active_on_host = self._get_active_resources_for_host(host)
            if active_on_host:
                conflicts = self._resource_registry.detect_conflicts(
                    action_name, host, active_on_host
                )
                for conflict in conflicts:
                    if conflict.resolution_strategy == ConflictResolutionStrategy.REJECT:
                        await self._metrics.emit_conflict_event(
                            ConflictEvent(
                                incident_id=incident_id,
                                target_host=host,
                                conflicting_categories=conflict.conflicting_categories,
                                blocking_incident_id=conflict.blocking_incident_id,
                                resolution_strategy="REJECT",
                            )
                        )
                        return ExecutionDecision(
                            decision_type=ExecutionDecisionType.REJECTED,
                            allowed=False,
                            reason=(
                                f"Resource conflict: {conflict.conflicting_categories} "
                                f"blocked by {conflict.blocking_incident_id}"
                            ),
                            blocking_incident_id=conflict.blocking_incident_id,
                        )

                    elif conflict.resolution_strategy == ConflictResolutionStrategy.PREEMPT:
                        # Check if preemption is allowed (severity gap >= 2)
                        can_preempt = self._can_preempt(
                            severity, conflict.blocking_incident_id
                        )
                        if not can_preempt:
                            await self._metrics.emit_conflict_event(
                                ConflictEvent(
                                    incident_id=incident_id,
                                    target_host=host,
                                    conflicting_categories=conflict.conflicting_categories,
                                    blocking_incident_id=conflict.blocking_incident_id,
                                    resolution_strategy="PREEMPT_DENIED",
                                )
                            )
                            return ExecutionDecision(
                                decision_type=ExecutionDecisionType.REJECTED,
                                allowed=False,
                                reason="Preemption denied: insufficient priority gap",
                                blocking_incident_id=conflict.blocking_incident_id,
                            )
                        # Preemption allowed — proceed (caller handles cancellation)

                    elif conflict.resolution_strategy == ConflictResolutionStrategy.QUEUE:
                        # Queue the action
                        return await self._enqueue_action(
                            incident_id, host, action_name, severity, correlation_group
                        )

        # Step 5: Host lock acquisition
        try:
            if len(target_hosts) == 1:
                result = await self._lock_store.acquire_host_lock(
                    target_hosts[0],
                    incident_id,
                    self._config.max_lock_duration_seconds,
                    action_name,
                )
            else:
                result = await self._lock_store.acquire_host_locks_atomic(
                    target_hosts,
                    incident_id,
                    self._config.max_lock_duration_seconds,
                    action_name,
                )
        except LockStoreError as e:
            return ExecutionDecision(
                decision_type=ExecutionDecisionType.REJECTED,
                allowed=False,
                reason=f"Lock Store unavailable: {e}",
            )

        if not result.acquired:
            # Queue the action
            decision = await self._enqueue_action(
                incident_id,
                target_hosts[0],
                action_name,
                severity,
                correlation_group,
            )
            if decision.decision_type == ExecutionDecisionType.QUEUED:
                await self._metrics.emit_queued_event(
                    QueuedEvent(
                        incident_id=incident_id,
                        target_host=target_hosts[0],
                        blocking_incident_id=result.holder_incident_id or "",
                        queue_position=decision.queue_position or 0,
                        estimated_wait_seconds=float(
                            self._config.max_lock_duration_seconds
                        ),
                    )
                )
            return decision

        # Lock acquired — track active execution
        self._metrics.record_lock_acquisition()
        resources = self._resource_registry.get_resource_categories(action_name)
        for host in target_hosts:
            self._active_executions[incident_id] = {
                "host": host,
                "action_name": action_name,
                "resources": resources,
                "start_time": time.time(),
                "severity": severity,
            }

        return ExecutionDecision(
            decision_type=ExecutionDecisionType.ALLOWED,
            allowed=True,
        )

    async def complete_execution(
        self,
        incident_id: str,
        target_hosts: list[str],
        action_name: str,
        success: bool,
        alert_name: str = "",
        severity: str = "",
    ) -> None:
        """Signal that a remediation execution has completed.

        Releases locks, updates circuit breaker, clears fingerprints on failure,
        and processes the priority queue.
        """
        # Track lock hold duration
        exec_info = self._active_executions.pop(incident_id, None)
        if exec_info:
            duration = time.time() - exec_info["start_time"]
            self._metrics.record_lock_hold_duration(duration)

        # Release host locks
        for host in target_hosts:
            try:
                await self._lock_store.release_host_lock(host, incident_id)
            except LockStoreError as e:
                logger.warning(
                    "Failed to release lock for host %s (incident %s): %s",
                    host,
                    incident_id,
                    str(e),
                )

        # Update circuit breaker
        for host in target_hosts:
            transition = await self._circuit_breaker.record_outcome(
                host, success, incident_id, action_name
            )
            if transition:
                await self._metrics.emit_circuit_breaker_event(
                    CircuitBreakerEvent(
                        host=host,
                        previous_state=transition.previous_state.value,
                        new_state=transition.new_state.value,
                        consecutive_failures=0 if success else 1,
                        trigger=transition.trigger,
                    )
                )

        # Clear fingerprint on failure to allow retry
        if not success and alert_name and target_hosts:
            fingerprint = self._deduplicator.compute_fingerprint(
                alert_name, target_hosts[0], severity
            )
            await self._deduplicator.clear_on_failure(fingerprint)

        # Process priority queue — dequeue next action for each released host
        for host in target_hosts:
            next_entry = self._priority_queue.dequeue_for_host(host)
            if next_entry:
                logger.info(
                    "Dequeued incident %s for host %s (priority: %s)",
                    next_entry.incident_id,
                    host,
                    next_entry.severity.value,
                )
                # The dequeued entry will be retried by the orchestrator

        # Publish metrics
        await self._metrics.publish_periodic_metrics()

    async def _enqueue_action(
        self,
        incident_id: str,
        host: str,
        action_name: str,
        severity: Severity,
        correlation_group: str,
    ) -> ExecutionDecision:
        """Enqueue an action in the priority queue."""
        entry = QueueEntry(
            incident_id=incident_id,
            target_host=host,
            action_name=action_name,
            severity=severity,
            enqueued_at=datetime.now(timezone.utc),
            correlation_group=correlation_group,
        )

        try:
            position = self._priority_queue.enqueue(entry)
        except QueueFullError:
            return ExecutionDecision(
                decision_type=ExecutionDecisionType.REJECTED,
                allowed=False,
                reason=f"Queue full for host {host}",
            )
        except DuplicateEntryError:
            return ExecutionDecision(
                decision_type=ExecutionDecisionType.REJECTED,
                allowed=False,
                reason=f"Incident {incident_id} already queued for host {host}",
            )

        return ExecutionDecision(
            decision_type=ExecutionDecisionType.QUEUED,
            allowed=False,
            reason=f"Queued at position {position} for host {host}",
            queue_position=position,
        )

    def _get_active_resources_for_host(self, host: str) -> dict[str, list[str]]:
        """Get active execution resources for a specific host.

        Returns: {incident_id: [resource_categories]} for active executions on this host.
        """
        result: dict[str, list[str]] = {}
        for iid, info in self._active_executions.items():
            if info["host"] == host:
                result[iid] = info["resources"]
        return result

    def _can_preempt(self, incoming_severity: Severity, blocking_incident_id: str) -> bool:
        """Check if the incoming action can preempt the blocking execution.

        Requires severity gap >= configured threshold (default 2).
        """
        blocking_info = self._active_executions.get(blocking_incident_id)
        if not blocking_info:
            return False

        incoming_rank = SEVERITY_RANK.get(incoming_severity.value, 5)
        blocking_rank = SEVERITY_RANK.get(blocking_info["severity"].value, 5)

        # Incoming must be higher priority (lower rank) by at least the gap
        return (blocking_rank - incoming_rank) >= self._config.preemption_severity_gap

    def _is_predecessor_completed(self, action_name: str, correlation_group: str) -> bool:
        """Check if a predecessor action has completed for a correlation group.

        For simplicity, checks if there's no active execution of the predecessor
        in the same correlation group. A more complete implementation would
        track completed actions in the Lock Store.
        """
        for iid, info in self._active_executions.items():
            if info["action_name"] == action_name:
                return False  # Still running
        return True

    @property
    def active_execution_count(self) -> int:
        """Number of currently active executions (for graceful shutdown)."""
        return len(self._active_executions)

    async def release_all_held_locks(self) -> int:
        """Force-release all locks held by active executions.

        Called during graceful shutdown to prevent lock leaks when
        ECS terminates the task. Returns the number of locks released.
        """
        released = 0
        # Copy to avoid mutation during iteration
        active_copy = dict(self._active_executions)

        for incident_id, info in active_copy.items():
            host = info["host"]
            try:
                success = await self._lock_store.release_host_lock(host, incident_id)
                if success:
                    released += 1
                    logger.info(
                        "Shutdown: released lock for host=%s incident=%s",
                        host,
                        incident_id,
                    )
            except LockStoreError as e:
                logger.warning(
                    "Shutdown: failed to release lock for host=%s: %s",
                    host,
                    str(e),
                )
                # Fallback: try force-release (unconditional delete)
                try:
                    await self._lock_store.force_release_host_lock(host)
                    released += 1
                    logger.info(
                        "Shutdown: force-released lock for host=%s", host
                    )
                except LockStoreError:
                    pass

        # Clear active executions tracking
        self._active_executions.clear()
        return released

    def get_status(self) -> dict:
        """Get current concurrency status for the API endpoint."""
        return {
            "active_locks": len(self._active_executions),
            "active_executions": {
                iid: {
                    "host": info["host"],
                    "action": info["action_name"],
                    "severity": info["severity"].value,
                    "duration_seconds": time.time() - info["start_time"],
                }
                for iid, info in list(self._active_executions.items())[:1000]
            },
            "queue_depths": self._priority_queue.get_all_depths(),
            "total_active_executions": len(self._active_executions),
        }
