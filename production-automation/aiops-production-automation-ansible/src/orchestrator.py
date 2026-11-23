"""Orchestrator component for coordinating the full self-healing pipeline.

Coordinates the end-to-end alert processing pipeline:
normalize → enrich → match → execute → notify

Handles concurrent alert processing with asyncio, stage failure handling,
unmatched alerts, and failure notification failures.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

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
        """
        self._normalizer = normalizer
        self._enricher = enricher
        self._mapper = mapper
        self._executor = executor
        self._dispatcher = dispatcher
        self._audit_logger = audit_logger
        self._metrics = metrics_collector
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)

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

            # Stage 4: Execute
            execution_result: Optional[ExecutionResult] = None
            try:
                target_host = self._resolve_target_host(enriched_alert)
                extra_vars = self._build_extra_vars(enriched_alert)
                execution_result = await self._executor.execute(
                    playbook_path=playbook_match.playbook_path,
                    target_host=target_host,
                    extra_vars=extra_vars,
                )
            except Exception as e:
                await self._handle_stage_failure(
                    incident_id=incident_id,
                    stage="execute",
                    alert=alert,
                    error=e,
                    enriched_alert=enriched_alert,
                )
                return incident_id

            # Track execution outcome metrics
            self._record_execution_metrics(
                execution_result=execution_result,
                alert_name=alert.alert_name,
                severity=alert.severity.value,
            )

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
