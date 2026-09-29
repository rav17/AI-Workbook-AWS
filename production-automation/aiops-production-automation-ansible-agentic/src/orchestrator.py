"""Orchestrator component for coordinating the full self-healing pipeline.

Coordinates the end-to-end alert processing pipeline:
normalize → enrich → match → [guardrail] → execute → [baking] → notify

Handles concurrent alert processing with asyncio, stage failure handling,
unmatched alerts, and failure notification failures.

Improvements integrated:
- Stop Conditions: monitors CloudWatch alarms during execution (Improvement 2)
- Baking Period: validates fix effectiveness post-execution (Improvement 3)
- Plan Validator: blocks dangerous AI commands (wired into guardrail engine) (Improvement 5)
"""

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Optional

from src.audit_logger import AuditLogger
from src.enricher import Enricher
from src.executor import RemediationExecutor
from src.metrics import MetricsCollector
from src.models import (
    AlertmanagerPayload,
    AuditRecord,
    EnrichedAlert,
    ExecutionResult,
    NormalizedAlert,
    PlaybookMatch,
    RemediationStatus,
)
from src.normalizer import Normalizer
from src.notification import NotificationDispatcher
from src.playbook_mapper import PlaybookMapper
from src.stores.deferred_actions_store import DeferredAction, DynamoDeferredActionsStore

if TYPE_CHECKING:
    from src.concurrency.manager import ConcurrencyManager
    from src.guardrails.engine import GuardrailEngine
    from src.guardrails.stop_conditions import StopConditionsMonitor
    from src.guardrails.baking_validator import BakingValidator

logger = logging.getLogger(__name__)

MAX_CONCURRENT_PIPELINES = 50


class Orchestrator:
    """Coordinates the full self-healing pipeline for alert processing.

    Processes alert payloads through sequential stages:
    1. Normalize - Extract and standardize alerts from the payload
    2. Enrich - Augment alerts with asset inventory context
    3. Match - Find a matching remediation playbook
    4. Execute - Run the matched playbook against the target host
    5. Notify - Dispatch notifications about the outcome

    Supports up to 50 concurrent pipeline executions via asyncio.Semaphore.
    Each alert gets a unique UUID incident_id and independent pipeline processing.
    """

    def __init__(
        self,
        normalizer: Normalizer,
        enricher: Enricher,
        mapper: PlaybookMapper,
        executor: RemediationExecutor,
        dispatcher: NotificationDispatcher,
        audit_logger: AuditLogger,
        metrics_collector: MetricsCollector,
        concurrency_manager: Optional["ConcurrencyManager"] = None,
        guardrail_engine: Optional["GuardrailEngine"] = None,
        stop_conditions_monitor: Optional["StopConditionsMonitor"] = None,
        baking_validator: Optional["BakingValidator"] = None,
        fleet_breaker=None,
        deferred_store: Optional[DynamoDeferredActionsStore] = None,
    ) -> None:
        """Initialize the Orchestrator with all pipeline components.

        Args:
            normalizer: Transforms raw payloads into normalized alerts.
            enricher: Augments alerts with asset inventory data.
            mapper: Matches alerts to remediation playbooks.
            executor: Executes Ansible playbooks.
            dispatcher: Dispatches notifications to configured channels.
            audit_logger: Persists audit trail records.
            metrics_collector: Collects operational metrics.
            concurrency_manager: Optional concurrency safety manager. When
                provided, enforces host-level locking, deduplication, circuit
                breaker, and priority queuing between match and execute stages.
            guardrail_engine: Optional guardrail engine. When provided,
                evaluates remediation actions through safety checks between
                match and execute stages.
            stop_conditions_monitor: Optional stop conditions monitor. When
                provided, monitors CloudWatch alarms during execution and
                triggers abort if system degrades.
            baking_validator: Optional post-execution validator. When provided,
                monitors alarm resolution and host health after execution to
                determine if the fix was effective.
            fleet_breaker: Optional fleet-wide circuit breaker. When provided,
                records execution outcomes to detect fleet-wide failures.
            deferred_store: Optional DynamoDB-backed deferred actions store.
                When provided, deferred actions survive task restarts and can
                be re-evaluated by any task in the fleet. Falls back to
                in-memory list if not provided.
        """
        self._normalizer = normalizer
        self._enricher = enricher
        self._mapper = mapper
        self._executor = executor
        self._dispatcher = dispatcher
        self._audit_logger = audit_logger
        self._metrics = metrics_collector
        self._concurrency_manager = concurrency_manager
        self._guardrail_engine = guardrail_engine
        self._stop_monitor = stop_conditions_monitor
        self._baking_validator = baking_validator
        self._fleet_breaker = fleet_breaker
        self._deferred_store = deferred_store
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)
        # Legacy in-memory fallback (used only when deferred_store is None)
        self._deferred_actions: list[dict] = []
        self._effectiveness_scorer = None
        self._effectiveness_scorer_counter: int = 0

    async def process_alert_payload(self, payload: AlertmanagerPayload) -> list[str]:
        """Process a full Alertmanager payload through the self-healing pipeline.

        Normalizes the payload into individual alerts, then processes each alert
        concurrently (up to 50 simultaneous pipelines). Each alert gets a unique
        incident_id and runs through: enrich → match → execute → notify.

        Args:
            payload: The Alertmanager webhook payload containing one or more alerts.

        Returns:
            A list of incident_ids for all alerts processed.
        """
        # Stage 1: Normalize the payload into individual alerts
        try:
            normalized_alerts = self._normalizer.normalize(payload)
        except Exception as e:
            logger.error(
                "Normalization failed for payload",
                extra={"error": str(e)},
            )
            return []

        if not normalized_alerts:
            logger.warning("Normalization produced no alerts from payload")
            return []

        # Process each alert concurrently with semaphore limiting
        tasks = [
            self._run_pipeline(alert) for alert in normalized_alerts
        ]
        incident_ids = await asyncio.gather(*tasks, return_exceptions=False)

        return list(incident_ids)

    async def _run_pipeline(self, alert: NormalizedAlert) -> str:
        """Run the full pipeline for a single normalized alert.

        Executes stages sequentially: enrich → match → execute → notify.
        On stage failure, logs the failure, skips remaining stages, and
        dispatches a failure notification.

        Args:
            alert: The normalized alert to process.

        Returns:
            The incident_id for this alert.
        """
        async with self._semaphore:
            incident_id = alert.incident_id

            logger.info(
                "Pipeline started",
                extra={
                    "incident_id": incident_id,
                    "alert_name": alert.alert_name,
                    "severity": alert.severity.value,
                },
            )

            # Track alert received
            self._metrics.increment_alerts_received(
                alert_name=alert.alert_name,
                severity=alert.severity.value,
            )

            # Stage 2: Enrich
            enriched_alert: Optional[EnrichedAlert] = None
            try:
                enriched_alert = self._enricher.enrich(alert)
            except Exception as e:
                await self._handle_stage_failure(
                    incident_id=incident_id,
                    stage="enrich",
                    alert=alert,
                    error=e,
                )
                return incident_id

            # Stage 3: Match
            playbook_match: Optional[PlaybookMatch] = None
            try:
                playbook_match = self._mapper.match(enriched_alert)
            except Exception as e:
                await self._handle_stage_failure(
                    incident_id=incident_id,
                    stage="match",
                    alert=alert,
                    error=e,
                    enriched_alert=enriched_alert,
                )
                return incident_id

            # Handle unmatched alert (no playbook found)
            if playbook_match is None:
                await self._handle_unmatched_alert(
                    incident_id=incident_id,
                    alert=alert,
                    enriched_alert=enriched_alert,
                )
                return incident_id

            # Stage 3.5: Concurrency Safety Check (between match and execute)
            target_host = self._resolve_target_host(enriched_alert)

            # Stage 3.6: Guardrail Engine Evaluation (between match and execute)
            if self._guardrail_engine is not None:
                from src.guardrails.models import GuardrailDecisionType, RemediationAction

                guardrail_action = RemediationAction(
                    incident_id=incident_id,
                    action_name=playbook_match.rule_name,
                    target_host=target_host,
                    service_name=(
                        enriched_alert.asset.service_name
                        if enriched_alert.asset
                        else ""
                    ),
                    playbook_path=playbook_match.playbook_path,
                    severity=alert.severity.value,
                )

                decision = await self._guardrail_engine.evaluate(guardrail_action)

                if decision.decision_type == GuardrailDecisionType.DENY:
                    logger.info(
                        "Guardrail DENY for incident %s: %s",
                        incident_id,
                        decision.reason,
                    )
                    self._write_audit_record(
                        incident_id=incident_id,
                        alert=alert,
                        enriched_alert=enriched_alert,
                        playbook_match=playbook_match,
                        execution_result=None,
                        notification_status=f"guardrail_deny:{decision.denying_check}",
                    )
                    return incident_id

                elif decision.decision_type == GuardrailDecisionType.DEFER:
                    logger.info(
                        "Guardrail DEFER for incident %s: %s",
                        incident_id,
                        decision.reason,
                    )
                    # Persist deferred action to DynamoDB (survives task restarts)
                    if self._deferred_store is not None:
                        import json as _json

                        deferred = DeferredAction(
                            incident_id=incident_id,
                            alert_name=alert.alert_name,
                            severity=alert.severity.value,
                            target_host=target_host,
                            service_name=(
                                enriched_alert.asset.service_name
                                if enriched_alert.asset
                                else ""
                            ),
                            playbook_path=playbook_match.playbook_path,
                            rule_name=playbook_match.rule_name,
                            alert_data=_json.dumps({
                                "incident_id": alert.incident_id,
                                "alert_name": alert.alert_name,
                                "severity": alert.severity.value,
                                "status": alert.status.value,
                                "labels": alert.labels,
                                "annotations": alert.annotations,
                                "starts_at": alert.starts_at.isoformat(),
                            }),
                            enriched_alert_data=_json.dumps({
                                "incident_id": enriched_alert.incident_id,
                                "alert_name": enriched_alert.alert_name,
                                "severity": enriched_alert.severity.value,
                                "labels": enriched_alert.labels,
                            }),
                            playbook_match_data=_json.dumps({
                                "rule_name": playbook_match.rule_name,
                                "playbook_path": playbook_match.playbook_path,
                                "matched_attributes": playbook_match.matched_attributes,
                            }),
                            reason=decision.reason,
                            re_evaluate_on=(
                                "window_end" if "maintenance" in decision.reason.lower()
                                else "slot_release"
                            ),
                        )
                        self._deferred_store.defer(deferred)
                    else:
                        # Legacy in-memory fallback
                        self._deferred_actions.append({
                            "incident_id": incident_id,
                            "alert": alert,
                            "enriched_alert": enriched_alert,
                            "playbook_match": playbook_match,
                            "deferred_at": time.time(),
                            "reason": decision.reason,
                        })

                    self._write_audit_record(
                        incident_id=incident_id,
                        alert=alert,
                        enriched_alert=enriched_alert,
                        playbook_match=playbook_match,
                        execution_result=None,
                        notification_status=f"guardrail_defer:{decision.denying_check}",
                    )
                    return incident_id

            if self._concurrency_manager is not None:

                execution_decision = await self._concurrency_manager.request_execution(
                    incident_id=incident_id,
                    target_hosts=[target_host],
                    action_name=playbook_match.rule_name,
                    severity=alert.severity,
                    correlation_group=incident_id,
                    alert_name=alert.alert_name,
                )
                if not execution_decision.allowed:
                    logger.info(
                        "Execution not allowed by concurrency manager",
                        extra={
                            "incident_id": incident_id,
                            "decision": execution_decision.decision_type.value,
                            "reason": execution_decision.reason,
                        },
                    )
                    # Write audit record for concurrency rejection
                    self._write_audit_record(
                        incident_id=incident_id,
                        alert=alert,
                        enriched_alert=enriched_alert,
                        playbook_match=playbook_match,
                        execution_result=None,
                        notification_status=f"concurrency_{execution_decision.decision_type.value.lower()}",
                    )
                    return incident_id

            # Stage 4: Execute (with stop condition monitoring)
            execution_result: Optional[ExecutionResult] = None
            abort_event = None
            service_name = (
                enriched_alert.asset.service_name if enriched_alert.asset else ""
            )

            try:
                # Start stop condition monitoring if configured
                if self._stop_monitor and self._stop_monitor.has_conditions(service_name):
                    abort_event = await self._stop_monitor.start_monitoring(service_name)

                extra_vars = self._build_extra_vars(enriched_alert)
                execution_result = await self._executor.execute(
                    playbook_path=playbook_match.playbook_path,
                    target_host=target_host,
                    extra_vars=extra_vars,
                )

                # Check if stop condition triggered during execution
                if abort_event and abort_event.is_set():
                    triggered = self._stop_monitor.get_triggered_condition()
                    logger.warning(
                        "Execution completed but stop condition was triggered: %s",
                        triggered.reason if triggered else "unknown",
                    )
                    # Override execution result to ABORTED if stop condition fired
                    # (the process may have completed before we could kill it)

            except Exception as e:
                # Stop monitoring on failure
                if self._stop_monitor:
                    self._stop_monitor.stop_monitoring()

                # Signal completion to concurrency manager on failure
                if self._concurrency_manager is not None:
                    await self._concurrency_manager.complete_execution(
                        incident_id=incident_id,
                        target_hosts=[target_host],
                        action_name=playbook_match.rule_name,
                        success=False,
                        alert_name=alert.alert_name,
                        severity=alert.severity.value,
                    )

                # Record failure in fleet-wide circuit breaker
                if self._fleet_breaker is not None:
                    self._fleet_breaker.record_failure(
                        host=target_host, incident_id=incident_id
                    )

                await self._handle_stage_failure(
                    incident_id=incident_id,
                    stage="execute",
                    alert=alert,
                    error=e,
                    enriched_alert=enriched_alert,
                )
                return incident_id
            finally:
                # Always stop monitoring after execution
                if self._stop_monitor:
                    self._stop_monitor.stop_monitoring()

            # Signal completion to concurrency manager
            if self._concurrency_manager is not None:
                await self._concurrency_manager.complete_execution(
                    incident_id=incident_id,
                    target_hosts=[target_host],
                    action_name=playbook_match.rule_name,
                    success=(execution_result.status == RemediationStatus.SUCCESS),
                    alert_name=alert.alert_name,
                    severity=alert.severity.value,
                )

            # Record outcome in fleet-wide circuit breaker
            if self._fleet_breaker is not None:
                if execution_result.status == RemediationStatus.SUCCESS:
                    self._fleet_breaker.record_success()
                else:
                    self._fleet_breaker.record_failure(
                        host=target_host, incident_id=incident_id
                    )

            # Track execution outcome metrics
            self._record_execution_metrics(
                execution_result=execution_result,
                alert_name=alert.alert_name,
                severity=alert.severity.value,
            )

            # Record outcome in effectiveness scorer (feedback loop)
            if self._effectiveness_scorer is not None:
                if execution_result.status == RemediationStatus.SUCCESS:
                    self._effectiveness_scorer.record_success(
                        alert_name=alert.alert_name,
                        playbook_path=playbook_match.playbook_path,
                    )
                else:
                    self._effectiveness_scorer.record_failure(
                        alert_name=alert.alert_name,
                        playbook_path=playbook_match.playbook_path,
                    )
                # Periodically persist scores (every 10 executions)
                if self._effectiveness_scorer_counter % 10 == 0:
                    self._effectiveness_scorer.persist()
                self._effectiveness_scorer_counter += 1

            # Stage 4.5: Post-Execution Baking Period (Improvement 3)
            # Validates whether the remediation actually fixed the underlying issue.
            if (
                self._baking_validator
                and execution_result.status == RemediationStatus.SUCCESS
            ):
                from src.guardrails.models import RemediationAction as GAction

                baking_action = GAction(
                    incident_id=incident_id,
                    action_name=playbook_match.rule_name,
                    target_host=target_host,
                    service_name=service_name,
                    risk_level=None,  # Would be set by classifier if available
                )

                # Extract alarm name from alert labels if available
                alarm_name = alert.labels.get("alarm_name") or alert.labels.get(
                    "alertname_cloudwatch"
                )

                baking_result = await self._baking_validator.validate(
                    action=baking_action,
                    alarm_name=alarm_name,
                )

                logger.info(
                    "Baking period result: incident=%s outcome=%s",
                    incident_id,
                    baking_result.outcome.value,
                )

                # Record baking outcome in guardrail engine (feeds circuit breaker)
                if self._guardrail_engine and baking_result.outcome.value == "ineffective":
                    await self._guardrail_engine.record_outcome(baking_action, success=False)

            # Stage 5: Notify
            try:
                await self._dispatcher.notify_remediation(
                    result=execution_result,
                    alert=enriched_alert,
                )
            except Exception as e:
                logger.error(
                    "Notification failed after remediation",
                    extra={
                        "incident_id": incident_id,
                        "stage": "notify",
                        "error": str(e),
                    },
                )

            # Audit logging
            self._write_audit_record(
                incident_id=incident_id,
                alert=alert,
                enriched_alert=enriched_alert,
                playbook_match=playbook_match,
                execution_result=execution_result,
                notification_status="sent",
            )

            logger.info(
                "Pipeline completed",
                extra={
                    "incident_id": incident_id,
                    "alert_name": alert.alert_name,
                    "result": execution_result.status.value,
                },
            )

            return incident_id

    async def _handle_stage_failure(
        self,
        incident_id: str,
        stage: str,
        alert: NormalizedAlert,
        error: Exception,
        enriched_alert: Optional[EnrichedAlert] = None,
    ) -> None:
        """Handle a pipeline stage failure.

        Logs the failure, skips remaining stages, and dispatches a failure
        notification. If the failure notification itself fails, logs the
        meta-failure and terminates the pipeline.

        Args:
            incident_id: The unique incident identifier.
            stage: The name of the failed stage.
            alert: The normalized alert being processed.
            error: The exception that caused the failure.
            enriched_alert: The enriched alert if available.
        """
        logger.error(
            "Pipeline stage failed",
            extra={
                "incident_id": incident_id,
                "stage": stage,
                "alert_name": alert.alert_name,
                "error": str(error),
            },
        )

        # Attempt to send failure notification
        try:
            if enriched_alert is not None:
                await self._dispatcher.notify_incident(enriched_alert)
            else:
                # Build a minimal enriched alert for notification
                minimal_enriched = EnrichedAlert(
                    incident_id=incident_id,
                    alert_name=alert.alert_name,
                    severity=alert.severity,
                    status=alert.status,
                    labels=alert.labels,
                    annotations=alert.annotations,
                    starts_at=alert.starts_at,
                    ends_at=alert.ends_at,
                    asset=None,
                    is_enriched=False,
                )
                await self._dispatcher.notify_incident(minimal_enriched)
        except Exception as notify_error:
            # Failure notification itself failed - log and terminate
            logger.error(
                "Failure notification failed (meta-failure), terminating pipeline",
                extra={
                    "incident_id": incident_id,
                    "stage": stage,
                    "original_error": str(error),
                    "notification_error": str(notify_error),
                },
            )
            self._metrics.increment_notification_failure(
                alert_name=alert.alert_name,
                severity=alert.severity.value,
            )

        # Write audit record for the failure
        self._write_audit_record(
            incident_id=incident_id,
            alert=alert,
            enriched_alert=enriched_alert,
            playbook_match=None,
            execution_result=None,
            notification_status=f"stage_failure:{stage}",
        )

    async def _handle_unmatched_alert(
        self,
        incident_id: str,
        alert: NormalizedAlert,
        enriched_alert: EnrichedAlert,
    ) -> None:
        """Handle an alert with no matching playbook.

        Skips execution stage, dispatches a manual triage notification,
        and records metrics.

        Args:
            incident_id: The unique incident identifier.
            alert: The normalized alert.
            enriched_alert: The enriched alert.
        """
        logger.warning(
            "No playbook match found, dispatching manual triage",
            extra={
                "incident_id": incident_id,
                "alert_name": alert.alert_name,
                "severity": alert.severity.value,
            },
        )

        # Track no-match metric
        self._metrics.increment_no_playbook_match(
            alert_name=alert.alert_name,
            severity=alert.severity.value,
        )

        # Dispatch manual triage notification
        try:
            await self._dispatcher.notify_manual_triage(enriched_alert)
        except Exception as e:
            # Failure notification itself failed - log and terminate
            logger.error(
                "Manual triage notification failed, terminating pipeline",
                extra={
                    "incident_id": incident_id,
                    "alert_name": alert.alert_name,
                    "error": str(e),
                },
            )
            self._metrics.increment_notification_failure(
                alert_name=alert.alert_name,
                severity=alert.severity.value,
            )

        # Write audit record
        self._write_audit_record(
            incident_id=incident_id,
            alert=alert,
            enriched_alert=enriched_alert,
            playbook_match=None,
            execution_result=None,
            notification_status="manual_triage",
        )

    def _resolve_target_host(self, enriched_alert: EnrichedAlert) -> str:
        """Resolve the target host for playbook execution.

        Priority order:
        1. Asset hostname from enrichment
        2. 'instance' label
        3. 'hostname' label
        4. 'job' label
        5. Fallback to 'localhost'

        Args:
            enriched_alert: The enriched alert with asset context.

        Returns:
            The target host string for Ansible execution.
        """
        if enriched_alert.asset and enriched_alert.asset.hostname:
            return enriched_alert.asset.hostname

        for label_key in ("instance", "hostname", "job"):
            value = enriched_alert.labels.get(label_key, "")
            if value and value.strip():
                return value.strip()

        return "localhost"

    def _build_extra_vars(self, enriched_alert: EnrichedAlert) -> dict:
        """Build extra variables to pass to the Ansible playbook.

        Includes alert context that the playbook may need for remediation.

        Args:
            enriched_alert: The enriched alert with full context.

        Returns:
            A dictionary of extra variables for the playbook.
        """
        extra_vars: dict = {
            "incident_id": enriched_alert.incident_id,
            "alert_name": enriched_alert.alert_name,
            "severity": enriched_alert.severity.value,
            "labels": json.dumps(enriched_alert.labels),
        }

        if enriched_alert.asset:
            extra_vars["service_name"] = enriched_alert.asset.service_name
            extra_vars["service_owner"] = enriched_alert.asset.service_owner

        return extra_vars

    def _record_execution_metrics(
        self,
        execution_result: ExecutionResult,
        alert_name: str,
        severity: str,
    ) -> None:
        """Record metrics based on execution result status.

        Args:
            execution_result: The result of playbook execution.
            alert_name: The alert name for metric labels.
            severity: The severity for metric labels.
        """
        if execution_result.status == RemediationStatus.SUCCESS:
            self._metrics.increment_remediation_success(
                alert_name=alert_name,
                severity=severity,
            )
        elif execution_result.status == RemediationStatus.TIMEOUT:
            self._metrics.increment_remediation_timeout(
                alert_name=alert_name,
                severity=severity,
            )
        else:
            self._metrics.increment_remediation_failure(
                alert_name=alert_name,
                severity=severity,
            )

    def _write_audit_record(
        self,
        incident_id: str,
        alert: NormalizedAlert,
        enriched_alert: Optional[EnrichedAlert],
        playbook_match: Optional[PlaybookMatch],
        execution_result: Optional[ExecutionResult],
        notification_status: str,
    ) -> None:
        """Write an audit record for the pipeline run.

        Args:
            incident_id: The unique incident identifier.
            alert: The normalized alert.
            enriched_alert: The enriched alert (if available).
            playbook_match: The matched playbook (if any).
            execution_result: The execution result (if any).
            notification_status: The notification outcome status.
        """
        affected_host = ""
        if enriched_alert and enriched_alert.asset and enriched_alert.asset.hostname:
            affected_host = enriched_alert.asset.hostname
        elif alert.labels.get("instance"):
            affected_host = alert.labels["instance"]
        elif alert.labels.get("hostname"):
            affected_host = alert.labels["hostname"]

        enrichment_data = None
        if enriched_alert and enriched_alert.is_enriched and enriched_alert.asset:
            enrichment_data = {
                "hostname": enriched_alert.asset.hostname,
                "ip_address": enriched_alert.asset.ip_address,
                "service_name": enriched_alert.asset.service_name,
                "service_owner": enriched_alert.asset.service_owner,
                "location": enriched_alert.asset.location,
            }

        matched_playbook = playbook_match.playbook_path if playbook_match else None

        exec_result_str = None
        exec_duration = None
        output_summary = ""
        if execution_result:
            exec_result_str = execution_result.status.value
            exec_duration = execution_result.duration_seconds
            output_summary = execution_result.stdout[:2048] if execution_result.stdout else ""

        record = AuditRecord(
            incident_id=incident_id,
            alert_name=alert.alert_name,
            severity=alert.severity.value,
            affected_host=affected_host,
            timestamp_received=alert.starts_at,
            enrichment_data=enrichment_data,
            matched_playbook=matched_playbook,
            execution_result=exec_result_str,
            execution_duration=exec_duration,
            notification_status=notification_status,
            output_summary=output_summary,
        )

        try:
            self._audit_logger.log_incident(record)
        except Exception as e:
            logger.error(
                "Failed to write audit record",
                extra={
                    "incident_id": incident_id,
                    "error": str(e),
                },
            )

    async def re_evaluate_deferred(self) -> list[str]:
        """Re-evaluate deferred actions.

        Called on slot release (within 30s) or maintenance window end (within 60s).
        Uses DynamoDB-backed store when available, otherwise falls back to in-memory.

        For DynamoDB-backed mode:
        - Queries all items with status=DEFERRED via OutcomeIndex GSI
        - Re-evaluates each through the guardrail engine
        - Atomically transitions status (DEFERRED → ALLOWED/DENIED/EXPIRED)
        - Prevents duplicate execution via conditional writes

        Returns:
            List of incident_ids that were re-evaluated and allowed.
        """
        if self._deferred_store is not None:
            return await self._re_evaluate_deferred_dynamo()
        return await self._re_evaluate_deferred_memory()

    async def _re_evaluate_deferred_dynamo(self) -> list[str]:
        """Re-evaluate deferred actions from DynamoDB store."""
        allowed_ids: list[str] = []

        pending = self._deferred_store.list_pending()
        if not pending:
            return allowed_ids

        for action in pending:
            # Expire stale actions
            if action.is_expired:
                self._deferred_store.mark_expired(action.incident_id)
                logger.info(
                    "Deferred action expired: incident=%s age=%.0fs",
                    action.incident_id,
                    action.age_seconds,
                )
                continue

            # Re-evaluate via guardrail engine
            if self._guardrail_engine is not None:
                from src.guardrails.models import GuardrailDecisionType, RemediationAction

                guardrail_action = RemediationAction(
                    incident_id=action.incident_id,
                    action_name=action.rule_name,
                    target_host=action.target_host,
                    service_name=action.service_name,
                    playbook_path=action.playbook_path,
                    severity=action.severity,
                )

                decision = await self._guardrail_engine.evaluate(guardrail_action)

                if decision.decision_type == GuardrailDecisionType.ALLOW:
                    # Atomically mark as allowed (prevents double-execution)
                    if self._deferred_store.mark_allowed(action.incident_id):
                        allowed_ids.append(action.incident_id)
                        logger.info(
                            "Deferred action now allowed: incident=%s",
                            action.incident_id,
                        )
                elif decision.decision_type == GuardrailDecisionType.DENY:
                    self._deferred_store.mark_denied(
                        action.incident_id, decision.reason
                    )
                    logger.info(
                        "Deferred action now denied: incident=%s reason=%s",
                        action.incident_id,
                        decision.reason,
                    )
                # DEFER again: leave in DynamoDB (no state change needed)

        return allowed_ids

    async def _re_evaluate_deferred_memory(self) -> list[str]:
        """Re-evaluate deferred actions from in-memory list (legacy fallback)."""
        MAX_DEFER_AGE_SECONDS = 3600  # 60 minutes
        now = time.time()
        allowed_ids: list[str] = []
        remaining: list[dict] = []

        for entry in self._deferred_actions:
            age = now - entry["deferred_at"]

            # Expire stale actions
            if age > MAX_DEFER_AGE_SECONDS:
                logger.info(
                    "Deferred action expired for incident %s (age: %.0fs)",
                    entry["incident_id"],
                    age,
                )
                continue

            # Re-evaluate via guardrail engine
            if self._guardrail_engine is not None:
                from src.guardrails.models import GuardrailDecisionType, RemediationAction

                target_host = self._resolve_target_host(entry["enriched_alert"])
                action = RemediationAction(
                    incident_id=entry["incident_id"],
                    action_name=entry["playbook_match"].rule_name,
                    target_host=target_host,
                    service_name=(
                        entry["enriched_alert"].asset.service_name
                        if entry["enriched_alert"].asset
                        else ""
                    ),
                    playbook_path=entry["playbook_match"].playbook_path,
                    severity=entry["alert"].severity.value,
                )

                decision = await self._guardrail_engine.evaluate(action)

                if decision.decision_type == GuardrailDecisionType.ALLOW:
                    allowed_ids.append(entry["incident_id"])
                    logger.info(
                        "Deferred action now allowed for incident %s",
                        entry["incident_id"],
                    )
                elif decision.decision_type == GuardrailDecisionType.DEFER:
                    # Still deferred — keep in queue
                    remaining.append(entry)
                else:
                    # Now denied — drop from queue
                    logger.info(
                        "Deferred action now denied for incident %s: %s",
                        entry["incident_id"],
                        decision.reason,
                    )
            else:
                remaining.append(entry)

        self._deferred_actions = remaining
        return allowed_ids

    @property
    def deferred_count(self) -> int:
        """Number of currently deferred actions.

        Queries DynamoDB store when available, falls back to in-memory count.
        """
        if self._deferred_store is not None:
            return self._deferred_store.count_pending()
        return len(self._deferred_actions)
