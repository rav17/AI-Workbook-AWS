"""FastAPI application for the self-healing infrastructure webhook receiver.

Provides endpoints for:
- POST /webhook: Receives Alertmanager webhook payloads (with storm protection)
- GET /health: Health check with dependency status + operating mode
- GET /metrics: Prometheus metrics exposition

Improvements integrated:
- Storm Detection: rate limiting + grouping during alert storms
- Fleet Breaker: fleet-wide circuit breaker status in /health
- Graceful Shutdown: draining flag checked before accepting new work
"""

import asyncio
import dataclasses
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from html import escape as _html_escape
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.storm_detector import StormDetector
from src.inhibitor import AlertInhibitor
from src.resolved_tracker import ResolvedAlertTracker
from src.degradation_manager import DegradationManager
from src.effectiveness_scorer import EffectivenessScorer
from src.pipeline_events import PipelineEventEmitter
from src.escalation_fatigue import EscalationFatigueManager
from src.error_codes import ApiErrorCode, error_response, success_response

from src.models import (
    Severity,
    AlertmanagerPayloadModel,
    AlertmanagerPayload,
    AlertmanagerAlert,
)
from src.orchestrator import Orchestrator
from src.normalizer import Normalizer
from src.enricher import Enricher, AssetInventory
from src.playbook_mapper import PlaybookMapper
from src.executor import RemediationExecutor
from src.notification import NotificationDispatcher
from src.audit_logger import AuditLogger
from src.metrics import MetricsCollector
from src.approval_handler import ApprovalHandler, get_signing_secret
from src.agentic_ai.models.domain import IncidentRecord, RemediationPlan
from src.agentic_ai.models.incident_store import OUTCOME_PENDING, IncidentMemoryStore
from src.feedback_tokens import (
    VERDICT_FAILURE,
    VERDICT_SUCCESS,
    create_feedback_token,
    verify_feedback_token,
)
from src.devops_agent import DevOpsAgentForwarder

logger = logging.getLogger(__name__)

# --- Configuration from environment variables ---
ASSET_INVENTORY_PATH = os.environ.get("ASSET_INVENTORY_PATH", "config/asset_inventory.yml")
MAPPING_CONFIG_PATH = os.environ.get("MAPPING_CONFIG_PATH", "config/mapping_config.yml")
AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.log")

# --- AWS dependency configuration (injected by ECS task definition) ---
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "")

# --- Email / Approval configuration ---
SES_FROM_ADDRESS = os.environ.get("SES_FROM_ADDRESS", "aiops@example.com")
OPERATOR_EMAIL = os.environ.get("OPERATOR_EMAIL", "ops-team@example.com")

# SERVICE_BASE_URL: lazily evaluated at email-send time to avoid cold-start failures
def _get_service_base_url() -> str:
    """Get the public API Gateway URL from SSM Parameter Store.

    Called lazily at email-send time, not at module import time, to avoid
    failures when SSM is not yet reachable during cold start.
    """
    env = os.environ.get("ENVIRONMENT", "dev")
    static_url = os.environ.get("SERVICE_BASE_URL", "").strip()
    if static_url and static_url.startswith("http"):
        return static_url
    try:
        client = boto3.client("ssm")
        resp = client.get_parameter(Name=f"/aiops/{env}/service-base-url")
        url = resp["Parameter"]["Value"]
        # Fix double-https if present
        if url.startswith("https://https://"):
            url = url.replace("https://https://", "https://")
        return url
    except Exception:
        return "http://localhost:8080"


class _LazyServiceUrl:
    """Lazily resolves SERVICE_BASE_URL on first access.

    Avoids SSM calls during module import (cold start) where VPC endpoints
    may not yet be propagated. Caches after first successful resolution.
    """

    def __init__(self) -> None:
        self._resolved: str = ""

    def __str__(self) -> str:
        if not self._resolved:
            self._resolved = _get_service_base_url()
        return self._resolved

    @property
    def value(self) -> str:
        return str(self)


_service_base_url = _LazyServiceUrl()

# --- Payload size limit (1 MB) ---
MAX_PAYLOAD_SIZE = 1 * 1024 * 1024  # 1 MB

# --- Module-level singletons ---
metrics_collector = MetricsCollector()
normalizer = Normalizer()
asset_inventory = AssetInventory(inventory_path=ASSET_INVENTORY_PATH)
enricher = Enricher(asset_inventory=asset_inventory)

# PlaybookMapper requires a config file; handle gracefully if missing
try:
    playbook_mapper = PlaybookMapper(mapping_config_path=MAPPING_CONFIG_PATH)
except Exception:
    playbook_mapper = PlaybookMapper(mapping_config_path=MAPPING_CONFIG_PATH)

executor = RemediationExecutor()
dispatcher = NotificationDispatcher(channels=[])  # Email replaces Slack; kept for pipeline compatibility
audit_logger = AuditLogger(log_file_path=AUDIT_LOG_PATH)

# --- Approval handler for human-in-the-loop (email-based) ---
approval_handler = ApprovalHandler(base_url=_service_base_url.value)

# --- Incident memory (DynamoDB): history for AI model routing, plus outcomes ---
incident_store: Optional[IncidentMemoryStore] = None
if DYNAMODB_TABLE_NAME:
    try:
        incident_store = IncidentMemoryStore(
            table_name=DYNAMODB_TABLE_NAME,
            region_name=os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION"),
        )
        logger.info("Incident memory store initialized (table=%s)", DYNAMODB_TABLE_NAME)
    except (BotoCoreError, ValueError) as e:
        logger.warning(
            "Incident memory store unavailable (non-fatal, AI history disabled): %s", e
        )
else:
    logger.warning("DYNAMODB_TABLE_NAME not set - AI incident history is disabled")

def _require_human_approval() -> bool:
    """Return whether rule-matched remediations must wait for human approval.

    Fail-safe: approval is required unless REQUIRE_HUMAN_APPROVAL is explicitly
    set to a false value. Any typo or unexpected value keeps the gate ON.
    """
    raw = os.environ.get("REQUIRE_HUMAN_APPROVAL", "true").strip().lower()
    return raw not in ("false", "0", "no", "off")


REQUIRE_HUMAN_APPROVAL = _require_human_approval()

# --- AWS DevOps Agent forwarder (Phase 1: investigation only, never executes) ---
devops_forwarder = DevOpsAgentForwarder()
logger.info("Human approval required before remediation: %s", REQUIRE_HUMAN_APPROVAL)

orchestrator = Orchestrator(
    normalizer=normalizer,
    enricher=enricher,
    mapper=playbook_mapper,
    executor=executor,
    dispatcher=dispatcher,
    audit_logger=audit_logger,
    metrics_collector=metrics_collector,
    # Without this, the pipeline executed the playbook immediately AND sent an
    # "approval" email afterwards — the approval was meaningless.
    require_human_approval=REQUIRE_HUMAN_APPROVAL,
)

# --- Initialize DynamoDB-backed Deferred Actions Store ---
try:
    from src.stores.deferred_actions_store import DynamoDeferredActionsStore
    if DYNAMODB_TABLE_NAME:
        _deferred_store = DynamoDeferredActionsStore(table_name=DYNAMODB_TABLE_NAME)
        orchestrator._deferred_store = _deferred_store
        logger.info("Deferred actions store initialized (DynamoDB-backed, table=%s)", DYNAMODB_TABLE_NAME)
    else:
        logger.warning("DYNAMODB_TABLE_NAME not set — deferred actions will use in-memory fallback")
except Exception as e:
    logger.warning("Deferred actions store initialization failed (non-fatal, using memory): %s", e)

# --- Storm Detector for alert storm protection ---
storm_detector = StormDetector()
if storm_detector.enabled:
    logger.info("Storm detector enabled (threshold=%d/min)", storm_detector._config.rate_threshold)
else:
    logger.info("Storm detector disabled via STORM_DETECTION_ENABLED=false")

# --- Fleet-Wide Circuit Breaker ---
try:
    from src.concurrency.fleet_breaker import FleetCircuitBreaker
    fleet_breaker = FleetCircuitBreaker()
    if fleet_breaker.enabled:
        logger.info("Fleet circuit breaker enabled (threshold=%d)", fleet_breaker._config.failure_threshold)
        # Wire fleet breaker into orchestrator for outcome recording
        orchestrator._fleet_breaker = fleet_breaker
    else:
        logger.info("Fleet circuit breaker disabled via FLEET_BREAKER_ENABLED=false")
except Exception as e:
    fleet_breaker = None
    logger.warning("Fleet circuit breaker initialization failed (non-fatal): %s", e)

# --- Alert Inhibitor (suppresses symptom alerts when root cause is active) ---
alert_inhibitor = AlertInhibitor()
logger.info("Alert inhibitor initialized (%d rules loaded)", alert_inhibitor.rule_count)

# --- Resolved Alert Tracker (prevents unnecessary remediations) ---
resolved_tracker = ResolvedAlertTracker()
logger.info("Resolved alert tracker initialized")

# --- Degradation Manager (auto-adjusts behavior on dependency failures) ---
degradation_manager = DegradationManager()
logger.info("Degradation manager initialized (mode: %s)", degradation_manager.current_mode.value)

# --- Effectiveness Scorer (playbook success/failure tracking + tie-breaking) ---
effectiveness_scorer = EffectivenessScorer()
logger.info("Effectiveness scorer initialized")

# --- Pipeline Event Emitter (structured observability events) ---
pipeline_events = PipelineEventEmitter()
logger.info("Pipeline event emitter initialized")

# --- Escalation Fatigue Manager (auto-approve trusted patterns) ---
fatigue_manager = EscalationFatigueManager()
logger.info("Escalation fatigue manager initialized")

# --- Initialize Guardrail Engine with all safety checks ---
# The engine is attached to the orchestrator for use by both the
# pipeline path and the approval path (Improvement 1: Unified Execution Path).
try:
    from src.guardrails.engine import GuardrailEngine
    from src.guardrails.self_protection import SelfProtectionGuard
    from src.guardrails.maintenance_window import MaintenanceWindowManager
    from src.guardrails.circuit_breaker import CircuitBreaker
    from src.guardrails.classifier import BlastRadiusClassifier
    from src.guardrails.approval import ApprovalGate
    from src.guardrails.plan_validator import PlanValidator

    # Order matters: the classifier sets risk_level, which ApprovalGate reads.
    guardrail_checks = [
        SelfProtectionGuard(),
        MaintenanceWindowManager(),
        CircuitBreaker(),
        BlastRadiusClassifier(),
        ApprovalGate(),
        PlanValidator(),  # Improvement 5: AI plan safety validation
    ]

    _guardrail_engine = GuardrailEngine(checks=guardrail_checks)
    orchestrator._guardrail_engine = _guardrail_engine
    logger.info(
        "Guardrail engine initialized with %d checks: %s",
        len(guardrail_checks),
        ", ".join(c.name for c in guardrail_checks),
    )
    # Not wired (no implementation of their dependencies exists yet):
    # - ConcurrencyGuard needs a guardrails LockStore; concurrency.LockStore uses a
    #   PK/SK schema that does not match AiopsIncidentMemory (incident_id/timestamp),
    #   and nothing calls acquire()/release(). Duplicate approvals are suppressed by
    #   ApprovalHandler instead.
    # - HealthChecker needs a ServiceRegistry; without one it treats every host as a
    #   single instance and denies all HIGH-risk actions.
    logger.warning(
        "Guardrails NOT active: concurrency_guard, health_checker "
        "(no LockStore/ServiceRegistry implementation)"
    )
except Exception as e:
    # Fail CLOSED: never run remediation with the safety checks silently missing.
    # Previously this was logged as "non-fatal" and the service ran with NO guardrails.
    logger.critical("Guardrail engine initialization failed — refusing to start: %s", e)
    raise

# --- Initialize Stop Conditions Monitor (Improvement 2) ---
try:
    from src.guardrails.stop_conditions import StopConditionsMonitor
    _stop_monitor = StopConditionsMonitor()
    orchestrator._stop_monitor = _stop_monitor
    logger.info("Stop conditions monitor initialized")
except Exception as e:
    logger.warning("Stop conditions monitor initialization failed (non-fatal): %s", e)

# --- Initialize Baking Validator (Improvement 3) ---
try:
    from src.guardrails.baking_validator import BakingValidator
    _baking_validator = BakingValidator()
    orchestrator._baking_validator = _baking_validator
    logger.info("Baking validator initialized")
except Exception as e:
    logger.warning("Baking validator initialization failed (non-fatal): %s", e)

# --- Wire Effectiveness Scorer into Orchestrator (feedback loop) ---
orchestrator._effectiveness_scorer = effectiveness_scorer
logger.info("Effectiveness scorer wired into orchestrator pipeline")

# --- FastAPI application ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="AIOps Self-Healing Infrastructure",
    description="Webhook receiver for Alertmanager with automated remediation",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _pydantic_model_to_dataclass(model: AlertmanagerPayloadModel) -> AlertmanagerPayload:
    """Convert a validated Pydantic model to the internal dataclass representation."""
    alerts = [
        AlertmanagerAlert(
            status=alert.status,
            labels=alert.labels,
            annotations=alert.annotations,
            starts_at=alert.startsAt,
            ends_at=alert.endsAt,
            generator_url=alert.generatorURL,
            fingerprint=alert.fingerprint,
        )
        for alert in model.alerts
    ]
    return AlertmanagerPayload(
        version=model.version,
        group_key=model.groupKey,
        status=model.status,
        receiver=model.receiver,
        alerts=alerts,
        group_labels=model.groupLabels,
        common_labels=model.commonLabels,
        common_annotations=model.commonAnnotations,
        external_url=model.externalURL,
    )


@app.post("/webhook")
@limiter.limit("60/minute")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """Receive Alertmanager webhook payloads.

    Validates Content-Type, payload size, and payload structure before
    dispatching to the orchestrator as a background task.

    Storm Protection:
    - Checks backpressure (returns 429 if queue full)
    - Groups alerts during storm mode (suppresses duplicates)
    - Tracks alert rate in sliding window

    Returns:
        200 with accepted status for valid payloads
        400 for invalid payloads or size exceeded
        415 for wrong Content-Type
        429 when system is under backpressure (Alertmanager will retry)
    """
    # Check if system is shutting down (graceful drain)
    from src.main import get_graceful_handler
    if get_graceful_handler().is_shutting_down:
        return error_response(
            code=ApiErrorCode.SERVICE_DRAINING,
            status_code=503,
            detail="Draining in progress — retry after task replacement",
            retry_after_seconds=30,
        )

    # Check Content-Type header
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return error_response(
            code=ApiErrorCode.UNSUPPORTED_MEDIA_TYPE,
            status_code=415,
            detail="Content-Type must be application/json",
        )

    # Read body and check size
    body = await request.body()
    if len(body) > MAX_PAYLOAD_SIZE:
        return error_response(
            code=ApiErrorCode.PAYLOAD_TOO_LARGE,
            status_code=400,
            detail=f"Payload size ({len(body)} bytes) exceeds {MAX_PAYLOAD_SIZE} bytes limit",
        )

    # Parse and validate payload
    try:
        payload_model = AlertmanagerPayloadModel.model_validate_json(body)
    except ValidationError as e:
        return error_response(
            code=ApiErrorCode.PAYLOAD_VALIDATION_FAILED,
            status_code=400,
            detail=str(e),
        )
    except Exception as e:
        return error_response(
            code=ApiErrorCode.PAYLOAD_INVALID_JSON,
            status_code=400,
            detail=str(e),
        )

    # --- Storm Protection: Backpressure Check ---
    # Check if fleet breaker is OPEN (reject all work)
    if fleet_breaker is not None:
        fb_decision = fleet_breaker.check()
        if not fb_decision.allowed:
            return error_response(
                code=ApiErrorCode.FLEET_BREAKER_OPEN,
                status_code=429,
                detail=fb_decision.reason,
                retry_after_seconds=int(fb_decision.cooldown_remaining_seconds),
            )

    # --- Storm Protection: Rate Limiting & Grouping ---
    alerts_to_process = []
    suppressed_count = 0

    for alert in payload_model.alerts:
        alert_name = alert.labels.get("alertname", "Unknown")
        service_name = alert.labels.get("service_name", "")

        storm_decision = storm_detector.evaluate(alert_name, service_name)

        if storm_decision.should_process:
            alerts_to_process.append(alert)
        else:
            suppressed_count += 1
            logger.debug(
                "Storm suppressed: %s/%s (%s)",
                alert_name,
                service_name,
                storm_decision.reason,
            )

    if not alerts_to_process and suppressed_count > 0:
        # All alerts in this payload were suppressed by storm grouping
        return success_response(
            status="storm_suppressed",
            code=ApiErrorCode.STORM_SUPPRESSED.value,
            alerts_received=len(payload_model.alerts),
            alerts_suppressed=suppressed_count,
            storm_active=True,
            retry=False,
        )

    # Convert to internal dataclass (only non-suppressed alerts)
    payload = _pydantic_model_to_dataclass(payload_model)

    # Dispatch processing + email notification as background task
    background_tasks.add_task(_process_and_notify, payload)

    return success_response(
        status="accepted",
        alerts_received=len(payload.alerts),
        alerts_suppressed=suppressed_count,
        storm_active=storm_detector.is_storm_active,
    )


async def _process_and_notify(payload: AlertmanagerPayload) -> None:
    """Process alert through pipeline with smart routing.

    Flow:
    1. Check inhibition rules (suppress symptom alerts)
    2. Check resolved status (skip already-resolved alerts)
    3. Try rule-based matching (PlaybookMapper)
    4. If match found → send approval email with "Approve Auto-Remediation" button
    5. If no match → invoke AI agent to analyze → send advisory email with suggested steps
    """
    from src.email_notifier import EmailNotifier

    # Resolved alerts never go through the remediation pipeline: they only cancel
    # pending work and record that the condition cleared.
    resolved_alerts = [a for a in payload.alerts if a.status == "resolved"]
    if resolved_alerts:
        for resolved_alert in resolved_alerts:
            await _handle_resolved_alert(resolved_alert)
        payload = dataclasses.replace(
            payload,
            alerts=[a for a in payload.alerts if a.status != "resolved"],
        )
        if not payload.alerts:
            return

    # Run the pipeline (normalize → enrich → match → execute)
    incident_ids = await orchestrator.process_alert_payload(payload)

    for index, alert in enumerate(payload.alerts):
        alert_name = alert.labels.get("alertname", "Unknown")
        severity = alert.labels.get("severity", "warning")
        instance = alert.labels.get("instance", "unknown-host")
        service_name = alert.labels.get("service_name", "unknown")
        annotations = alert.annotations
        # The orchestrator returns one incident id per alert, in payload order.
        # (Previously every alert in a batch used incident_ids[0], so batched
        # alerts shared one id and the DevOps Agent de-duplication skipped them.)
        if index < len(incident_ids):
            incident_id = incident_ids[index]
        else:
            incident_id = f"unknown-{uuid.uuid4().hex[:12]}"
        root_cause = annotations.get("summary", f"{alert_name} detected on {instance}")

        # --- Alert Inhibition Check ---
        inhibition = alert_inhibitor.evaluate(
            alert_name=alert_name,
            host=instance,
            severity=severity,
            status=alert.status,
            incident_id=incident_id,
            service_name=service_name,
        )
        if not inhibition.should_process:
            logger.info(
                "Inhibited: %s on %s — %s",
                alert_name, instance, inhibition.reason,
            )
            continue  # Skip suppressed alerts

        # Register as active incident (for future inhibition lookups)
        alert_inhibitor.register_active_incident(
            incident_id=incident_id,
            alert_name=alert_name,
            host=instance,
            service_name=service_name,
        )

        # Register in resolved tracker (for auto-cancellation if resolved later)
        resolved_tracker.register_pending(incident_id, alert_name, instance)

        # --- Check Degradation Manager for AI availability ---
        use_ai = degradation_manager.is_ai_available

        # --- Path 1: Try rule-based matching ---
        matched_rule = None
        playbook_path = None
        for rule in playbook_mapper.rules:
            match = True
            alert_attrs = {"alert_name": alert_name, "severity": severity,
                           "service_name": service_name, **alert.labels}
            for k, v in rule.conditions.items():
                if alert_attrs.get(k) != v:
                    match = False
                    break
            if match:
                matched_rule = rule
                playbook_path = rule.playbook_path
                break

        if matched_rule and playbook_path:
            # --- RULE MODE: Send approval email with auto-remediation button ---
            logger.info(
                "Rule matched: %s → %s (sending approval email)",
                matched_rule.name, playbook_path,
            )
            approval = approval_handler.create_approval(
                incident_id=incident_id,
                alert_name=alert_name,
                severity=severity,
                affected_host=instance,
                service_name=service_name,
                root_cause=root_cause,
                proposed_action=f"Execute {playbook_path} on {instance}",
                playbook_path=playbook_path,
                extra_vars={"service_name": service_name, "incident_id": incident_id},
            )
            if approval is None:
                # Same alert/host/playbook already has a pending approval
                # (e.g. direct trigger + CloudWatch alarm for one CPU spike).
                continue
            try:
                notifier = EmailNotifier(
                    approval_handler=approval_handler,
                    from_address=SES_FROM_ADDRESS,
                    operator_email=OPERATOR_EMAIL,
                )
                notifier.send_approval_email(approval)
            except Exception as e:
                logger.error("Failed to send approval email: %s", str(e))

            # Critical alerts: also ask AWS DevOps Agent to investigate in parallel.
            # Placed after duplicate suppression so one problem = one investigation.
            if severity.lower() == "critical":
                await devops_forwarder.forward_async(
                    incident_id=incident_id,
                    trigger="critical",
                    alert_name=alert_name,
                    severity=severity,
                    host=instance,
                    service_name=service_name,
                    summary=root_cause,
                    detail=f"Matched playbook {playbook_path}; awaiting human approval.",
                    labels=alert.labels,
                    runbook_url=annotations.get("runbook_url", ""),
                )

        else:
            # --- No playbook match: hand the investigation to AWS DevOps Agent ---
            # Forward regardless of local AI availability (that is when it helps most).
            devops_result = await devops_forwarder.forward_async(
                incident_id=incident_id,
                trigger="unmatched",
                alert_name=alert_name,
                severity=severity,
                host=instance,
                service_name=service_name,
                summary=root_cause,
                labels=alert.labels,
                runbook_url=annotations.get("runbook_url", ""),
            )

            # --- ADVISORY MODE: DevOps Agent investigates, the findings Lambda advises ---
            # The Lambda reads the investigation and mitigation plan, asks Bedrock which
            # playbook fits, and sends the one advisory email. Skip our own Bedrock call.
            # If forwarding did not happen (off, capped, failed) fall through to the local
            # AI advisory below so the operator always gets advice.
            if devops_forwarder.defers_advisory(devops_result):
                logger.info(
                    "No playbook match for '%s': DevOps Agent investigation drives the "
                    "advisory email (incident %s)",
                    alert_name,
                    incident_id,
                )
                continue

            # --- AI AGENT MODE: No playbook match, invoke AI for analysis ---
            if not use_ai:
                logger.info(
                    "No playbook match for '%s' and AI unavailable (mode: %s) — skipping",
                    alert_name,
                    degradation_manager.current_mode.value,
                )
                continue

            logger.info(
                "No playbook match for '%s' — switching to AI agent mode",
                alert_name,
            )
            await _send_ai_advisory_email(
                incident_id=incident_id,
                alert_name=alert_name,
                severity=severity,
                instance=instance,
                service_name=service_name,
                root_cause=root_cause,
                labels=alert.labels,
                annotations=annotations,
                devops_agent_forwarded=(devops_result.status == "sent"),
            )


async def _handle_resolved_alert(alert: AlertmanagerAlert) -> None:
    """Handle one "resolved" alert.

    Cancels a pending action for the same alert and host, tells DevOps Agent (opt-in),
    and marks the matching AI advisory incident in DynamoDB as resolved. The advisory
    outcome is not touched: an alert clearing does not prove the advice worked.
    """
    alert_name = alert.labels.get("alertname", "Unknown")
    severity = alert.labels.get("severity", "warning")
    instance = alert.labels.get("instance", "unknown-host")
    service_name = alert.labels.get("service_name", "unknown")
    root_cause = alert.annotations.get("summary", f"{alert_name} detected on {instance}")

    decision = resolved_tracker.handle_resolved(alert_name, instance)
    if decision.should_cancel:
        logger.info(
            "Auto-cancelled: %s on %s resolved before execution",
            alert_name, instance,
        )
        # The cancelled approval can no longer be used, so free its duplicate lock:
        # otherwise a real recurrence within the approval expiry window is dropped.
        if decision.incident_id:
            await asyncio.to_thread(
                approval_handler.release_dedup_for_incident, decision.incident_id
            )
        metrics_collector.increment_storm_suppressed(alert_name, severity)

    # Opt-in (DEVOPS_AGENT_FORWARD_ON includes "resolved"): tell DevOps
    # Agent the alert recovered. No-op unless we forwarded it earlier.
    await devops_forwarder.forward_resolved_async(
        alert_name=alert_name,
        host=instance,
        severity=severity,
        service_name=service_name,
        summary=root_cause,
    )

    if incident_store is not None:
        try:
            resolved_id = await asyncio.to_thread(
                incident_store.record_resolution_for_alert, alert_name, instance
            )
        except Exception as e:  # background task boundary: never fail the webhook flow
            logger.warning("Could not record resolution for %s on %s: %s", alert_name, instance, e)
            return
        if resolved_id:
            logger.info(
                "AI advisory incident %s marked resolved",
                resolved_id,
                extra={"incident_id": resolved_id},
            )


async def _record_advisory_incident(
    *,
    incident_id: str,
    alert_name: str,
    severity: str,
    service_name: str,
    instance: str,
    plan: RemediationPlan,
    model_id: Optional[str],
) -> bool:
    """Store the AI advisory as a pending incident so feedback and history can attach to it.

    Returns:
        True if the record was written, False if there is no store or the write failed.
    """
    if incident_store is None:
        return False
    fallback_reason = plan.fallback_reason
    record = IncidentRecord(
        incident_id=incident_id,
        alert_name=alert_name,
        severity=severity,
        affected_service=service_name,
        affected_resource=instance,
        remediation_action=plan.selected_action or "advisory",
        outcome=OUTCOME_PENDING,
        execution_duration_seconds=0.0,
        timestamp_completed=datetime.now(timezone.utc),
        expiry_timestamp=0,
        model_id=model_id,
        confidence_score=plan.confidence_score,
        reasoning_summary=plan.reasoning_explanation[:2048],
        fallback_used=plan.fallback_used,
        fallback_reason=fallback_reason.value if fallback_reason is not None else None,
    )
    try:
        return await asyncio.to_thread(incident_store.record_incident, record)
    except Exception as e:  # background task boundary
        logger.warning(
            "Could not store advisory incident %s: %s",
            incident_id,
            e,
            extra={"incident_id": incident_id},
        )
        return False


def _build_feedback_blocks(incident_id: str) -> tuple[str, str]:
    """Build the "did this advice help?" section (HTML, text) for the advisory email."""
    try:
        secret = get_signing_secret()
        base = _service_base_url.value.rstrip("/")
        yes = f"{base}/feedback/{create_feedback_token(incident_id, VERDICT_SUCCESS, secret)}"
        no = f"{base}/feedback/{create_feedback_token(incident_id, VERDICT_FAILURE, secret)}"
    except ValueError as e:
        logger.warning(
            "Could not build feedback links for %s: %s",
            incident_id,
            e,
            extra={"incident_id": incident_id},
        )
        return "", ""
    button = (
        "display: inline-block; padding: 10px 18px; border-radius: 4px; color: #fff;"
        " text-decoration: none; font-weight: bold; margin-right: 8px; background: "
    )
    html_block = (
        '<h3>Did this advice help?</h3><p style="font-size: 13px; color: #495057;">'
        "Your answer is stored with the incident and improves model selection for similar "
        "alerts. Each incident accepts one answer.</p>"
        f'<p><a href="{_html_escape(yes, quote=True)}" style="{button}#28a745;">Yes, it helped</a>'
        f'<a href="{_html_escape(no, quote=True)}" style="{button}#dc3545;">No, it did not</a></p>'
    )
    text_block = f"\nDID THIS ADVICE HELP?\n  Yes: {yes}\n  No:  {no}\n"
    return html_block, text_block


def _routing_severity(severity_label: str) -> str:
    """Map an Alertmanager severity label to the P1-P5 value the model router uses.

    Uses the pipeline's own mapping (critical->P1, warning->P2, info->P3). Labels that
    are already P-values pass through; anything else defaults to P3, as in the
    normalizer.
    """
    label = (severity_label or "").strip()
    if label.upper() in {"P1", "P2", "P3", "P4", "P5"}:  # router's full P-range
        return label.upper()
    return Normalizer.SEVERITY_MAP.get(label.lower(), Severity.P3).value


async def _send_ai_advisory_email(
    incident_id: str,
    alert_name: str,
    severity: str,
    instance: str,
    service_name: str,
    root_cause: str,
    labels: dict,
    annotations: dict,
    devops_agent_forwarded: bool = False,
) -> None:
    """Invoke AI agent to analyze the alert and send advisory email with suggested steps."""
    from src.agentic_ai.agents.reasoning_agent import AIReasoningAgent, AgentConfig

    # Invoke AI reasoning agent
    suggested_steps = ""
    ai_reasoning = ""
    plan = None
    agent = None
    try:
        agent = AIReasoningAgent(config=AgentConfig(), incident_store=incident_store)
        # The router and confidence thresholds expect P1-P5, not the raw label.
        plan = await agent.reason(
            alert_name=alert_name,
            severity=_routing_severity(severity),
            service_name=service_name,
            target_resource=instance,
            labels=labels,
            incident_id=incident_id,
        )
        ai_reasoning = plan.reasoning_explanation
        if plan.steps:
            suggested_steps = "\n".join(
                f"  {s.step_number}. {s.action} on {s.target_resource}"
                + (f" — Expected: {s.expected_outcome}" if s.expected_outcome else "")
                for s in plan.steps
            )
        else:
            suggested_steps = f"  1. {plan.selected_action} on {instance}"
    except Exception as e:
        logger.warning("AI agent failed, providing generic advice: %s", e)
        ai_reasoning = f"AI analysis unavailable ({e}). Manual investigation required."
        suggested_steps = (
            f"  1. SSH/SSM into {instance}\n"
            f"  2. Check system resources: top, df -h, journalctl\n"
            f"  3. Investigate alert: {alert_name}\n"
            f"  4. Apply appropriate fix based on findings"
        )

    # Record the advisory as a pending incident and offer one-click feedback links.
    feedback_html, feedback_text = "", ""
    if plan is not None and await _record_advisory_incident(
        incident_id=incident_id,
        alert_name=alert_name,
        severity=_routing_severity(severity),
        service_name=service_name,
        instance=instance,
        plan=plan,
        model_id=agent.last_model_id if agent is not None else None,
    ):
        feedback_html, feedback_text = _build_feedback_blocks(incident_id)

    # Note about the parallel AWS DevOps Agent investigation (Phase 1 integration)
    devops_html = ""
    devops_text = ""
    if devops_agent_forwarded:
        ref = f"aiops-{incident_id}-unmatched"
        link = devops_forwarder.web_app_url
        link_html = f' <a href="{link}">Open the DevOps Agent web app</a>.' if link else ""
        devops_html = (
            '<div style="background: #e7f1ff; border: 1px solid #0d6efd; border-radius: 4px;'
            ' padding: 12px; margin-top: 20px;"><p style="margin: 0; font-size: 13px;">'
            "<strong>AWS DevOps Agent is investigating this incident.</strong> "
            f"Look for incident reference <code>{ref}</code> in the Agent Space."
            f"{link_html}</p></div>"
        )
        devops_text = (
            f"\nAWS DEVOPS AGENT: investigation requested (reference: {ref})"
            + (f"\nOpen: {link}" if link else "")
            + "\n"
        )

    # Build advisory email (no approval button — operator executes manually)
    subject = (
        f"[{severity.upper()}] {alert_name} on {instance} "
        f"— AI Analysis & Suggested Steps"
    )
    html_body = f"""\
<html>
<body style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">

<div style="border-left: 4px solid #fd7e14; padding: 12px 16px; background: #f8f9fa;">
    <h2 style="margin: 0 0 8px 0;">Alert: {alert_name}</h2>
    <p style="margin: 0; color: #495057;">
        Severity: <strong>{severity.upper()}</strong> |
        Host: <strong>{instance}</strong> |
        Service: <strong>{service_name}</strong>
    </p>
</div>

<h3>Root Cause</h3>
<div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px; padding: 12px;">
    <p style="margin: 0;">{root_cause}</p>
</div>

<h3>AI Analysis</h3>
<div style="background: #e8f4f8; border: 1px solid #17a2b8; border-radius: 4px; padding: 12px;">
    <p style="margin: 0; white-space: pre-wrap;">{ai_reasoning}</p>
</div>

<h3>Suggested Remediation Steps</h3>
<div style="background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 12px;">
    <pre style="margin: 0; font-family: monospace; font-size: 13px;">{suggested_steps}</pre>
</div>

<div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 4px; padding: 12px; margin-top: 20px;">
    <p style="margin: 0; color: #721c24; font-size: 13px;">
        <strong>No automated playbook available for this alert.</strong><br>
        Please execute the suggested steps manually or create a playbook for future automation.
    </p>
</div>
{devops_html}
{feedback_html}

<hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
<p style="color: #6c757d; font-size: 12px;">
    Incident: {incident_id} | Mode: AI Advisory (no auto-execute)
</p>

</body>
</html>"""

    text_body = f"""\
ALERT: {alert_name} [{severity.upper()}]
Host: {instance} | Service: {service_name}

ROOT CAUSE: {root_cause}

AI ANALYSIS:
{ai_reasoning}

SUGGESTED STEPS:
{suggested_steps}

NOTE: No automated playbook available. Please execute manually.
{devops_text}{feedback_text}Incident: {incident_id}
"""

    # Send via SES
    try:
        ses = _get_ses_client()
        ses.send_email(
            Source=SES_FROM_ADDRESS,
            Destination={"ToAddresses": [OPERATOR_EMAIL]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(
            "AI advisory email sent for incident %s (no playbook match)",
            incident_id,
        )
    except Exception as e:
        logger.error("Failed to send AI advisory email: %s", str(e))


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint with dependency status and operating mode.

    Checks:
    - SQS connectivity via GetQueueAttributes
    - DynamoDB connectivity via DescribeTable
    - ansible-playbook binary availability via shutil.which
    - Mapping config file existence
    - Asset inventory file existence
    - Storm detector status
    - Fleet circuit breaker status

    Returns:
        200 with healthy status when all dependencies are available
        503 with degraded/unhealthy status when any dependency is unhealthy
    """
    dependencies: dict[str, str] = {}

    # Check SQS connectivity
    dependencies["sqs"] = _check_sqs_health()

    # Check DynamoDB connectivity
    dependencies["dynamodb"] = _check_dynamodb_health()

    # Check ansible-playbook binary
    ansible_path = shutil.which("ansible-playbook")
    dependencies["ansible_binary"] = "ok" if ansible_path else "missing"

    # Check mapping config file
    mapping_exists = os.path.isfile(MAPPING_CONFIG_PATH)
    dependencies["mapping_config"] = "ok" if mapping_exists else "missing"

    # Check asset inventory file
    inventory_exists = os.path.isfile(ASSET_INVENTORY_PATH)
    dependencies["asset_inventory"] = "ok" if inventory_exists else "missing"

    # Determine overall status based on AWS dependencies (sqs and dynamodb)
    aws_healthy = (
        dependencies["sqs"] == "healthy" and dependencies["dynamodb"] == "healthy"
    )

    # Build operating mode info
    operating_mode = "full"
    storm_info = {}
    fleet_info = {}

    # Storm detector status
    if storm_detector.enabled:
        metrics = storm_detector.get_metrics()
        storm_info = {
            "active": metrics.is_storm_active,
            "current_rate": metrics.current_rate,
            "threshold": metrics.threshold,
            "suppressed_total": metrics.alerts_suppressed_total,
        }
        if metrics.is_storm_active:
            operating_mode = "storm_mode"

    # Fleet breaker status
    if fleet_breaker is not None and fleet_breaker.enabled:
        fleet_info = fleet_breaker.get_status()
        if fleet_info.get("state") == "open":
            operating_mode = "fleet_breaker_open"
        elif fleet_info.get("state") == "recovering":
            operating_mode = "fleet_recovering"

    # Check graceful shutdown
    from src.main import get_graceful_handler
    if get_graceful_handler().is_shutting_down:
        operating_mode = "draining"

    response_body = {
        "status": "healthy" if aws_healthy else "unhealthy",
        "mode": operating_mode,
        "dependencies": dependencies,
    }

    if storm_info:
        response_body["storm_detector"] = storm_info
    if fleet_info:
        response_body["fleet_breaker"] = fleet_info

    status_code = 200 if aws_healthy else 503
    return JSONResponse(status_code=status_code, content=response_body)


# --- Module-level AWS clients for health checks (reused across calls) ---
_sqs_health_client = None
_dynamodb_health_client = None
_ses_client = None


def _get_ses_client():
    """Get or create the SES client used for advisory emails (reused across alerts)."""
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses")
    return _ses_client


def _get_sqs_client():
    """Get or create the SQS client for health checks."""
    global _sqs_health_client
    if _sqs_health_client is None:
        _sqs_health_client = boto3.client("sqs")
    return _sqs_health_client


def _get_dynamodb_client():
    """Get or create the DynamoDB client for health checks."""
    global _dynamodb_health_client
    if _dynamodb_health_client is None:
        _dynamodb_health_client = boto3.client("dynamodb")
    return _dynamodb_health_client


def _check_sqs_health() -> str:
    """Check SQS queue connectivity using GetQueueAttributes.

    Returns:
        "healthy" if the queue is reachable, "unhealthy" otherwise.
    """
    if not SQS_QUEUE_URL:
        return "unhealthy"
    try:
        client = _get_sqs_client()
        client.get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=["QueueArn"],
        )
        return "healthy"
    except (BotoCoreError, ClientError) as e:
        logger.warning("SQS health check failed: %s", e)
        return "unhealthy"
    except Exception as e:
        logger.warning("SQS health check unexpected error: %s", e)
        return "unhealthy"


def _check_dynamodb_health() -> str:
    """Check DynamoDB table connectivity using DescribeTable.

    Returns:
        "healthy" if the table is reachable, "unhealthy" otherwise.
    """
    if not DYNAMODB_TABLE_NAME:
        return "unhealthy"
    try:
        client = _get_dynamodb_client()
        client.describe_table(TableName=DYNAMODB_TABLE_NAME)
        return "healthy"
    except (BotoCoreError, ClientError) as e:
        logger.warning("DynamoDB health check failed: %s", e)
        return "unhealthy"
    except Exception as e:
        logger.warning("DynamoDB health check unexpected error: %s", e)
        return "unhealthy"


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Expose Prometheus metrics in text exposition format.

    Returns:
        Prometheus metrics as text/plain
    """
    metrics_output = metrics_collector.render_metrics()
    return PlainTextResponse(content=metrics_output, media_type="text/plain")


# ===========================================================================
# Approval Endpoint — Human-in-the-loop remediation trigger
# ===========================================================================


def _feedback_page(
    heading: str,
    message: str,
    *,
    status_code: int = 200,
    form_action: str = "",
    button: str = "",
) -> Response:
    """Render a small HTML page for the feedback links (all dynamic text is escaped)."""
    form = ""
    if form_action:
        form = (
            f'<form method="POST" action="{_html_escape(form_action, quote=True)}">'
            '<button type="submit" style="background: #0d6efd; color: white; padding: 14px 32px;'
            " border: none; border-radius: 6px; font-size: 16px; font-weight: bold;"
            f' cursor: pointer;">{_html_escape(button)}</button></form>'
        )
    body = (
        '<html><body style="font-family: sans-serif; text-align: center; padding: 60px;">'
        f"<h1>{_html_escape(heading)}</h1>"
        f'<p style="color: #333; font-size: 18px;">{_html_escape(message)}</p>{form}'
        "</body></html>"
    )
    return Response(
        content=body,
        media_type="text/html",
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


# ===========================================================================
# Advisory feedback: "did this AI advice help?" (GET shows, POST records)
# ===========================================================================


@app.get("/feedback/{token}")
async def feedback_confirmation(token: str) -> Response:
    """Show a confirmation page for an advisory feedback link (no side effects).

    Recording happens only on the POST below, so email link scanners that open the
    link cannot record feedback by accident.
    """
    claims = verify_feedback_token(token, get_signing_secret())
    if claims is None:
        return _feedback_page(
            "Link expired or invalid",
            "This feedback link is no longer valid.",
            status_code=410,
        )
    if incident_store is None:
        return _feedback_page(
            "Feedback unavailable", "The incident store is not configured.", status_code=503
        )
    record = await asyncio.to_thread(incident_store.get_incident, claims.incident_id)
    if record is None:
        return _feedback_page(
            "Incident not found", "No record exists for this incident.", status_code=404
        )
    if record.outcome != OUTCOME_PENDING:
        return _feedback_page(
            "Feedback already recorded",
            f"This incident was already marked: {record.outcome}.",
        )
    verdict_text = "helped" if claims.verdict == VERDICT_SUCCESS else "did not help"
    return _feedback_page(
        "Confirm your feedback",
        f"Record that the AI advice for {record.alert_name} on "
        f"{record.affected_resource} {verdict_text}?",
        form_action=f"/feedback/{token}/confirm",
        button="Confirm",
    )


@app.post("/feedback/{token}/confirm")
async def feedback_confirm(token: str) -> Response:
    """Record the operator's feedback as the incident outcome (first answer wins)."""
    claims = verify_feedback_token(token, get_signing_secret())
    if claims is None:
        return _feedback_page(
            "Link expired or invalid",
            "This feedback link is no longer valid.",
            status_code=410,
        )
    if incident_store is None:
        return _feedback_page(
            "Feedback unavailable", "The incident store is not configured.", status_code=503
        )
    recorded = await asyncio.to_thread(
        incident_store.record_outcome,
        claims.incident_id,
        claims.verdict,
        0.0,
        None,
        source="human_feedback",
        only_if_pending=True,
    )
    if recorded:
        logger.info(
            "Advisory feedback recorded: %s",
            claims.verdict,
            extra={"incident_id": claims.incident_id},
        )
        return _feedback_page("Thank you", "Your feedback was recorded.")
    record = await asyncio.to_thread(incident_store.get_incident, claims.incident_id)
    if record is not None and record.outcome != OUTCOME_PENDING:
        return _feedback_page(
            "Feedback already recorded",
            f"This incident was already marked: {record.outcome}.",
        )
    return _feedback_page(
        "Could not record feedback", "Please try the link again in a moment.", status_code=503
    )


@app.get("/approve/{token}")
async def approve_remediation(token: str, background_tasks: BackgroundTasks) -> Response:
    """Show confirmation page for remediation approval.

    This endpoint is called when an operator clicks the approval link
    in the RCA email. It shows a confirmation page with a POST form
    to prevent email link scanners from triggering remediations.

    The actual execution is triggered by the POST endpoint below.
    """
    approval = approval_handler.get_pending_by_token(token)

    if approval is None or approval.is_expired or approval.approved:
        html = """\
<html>
<body style="font-family: sans-serif; text-align: center; padding: 60px;">
    <h1 style="color: #dc3545;">⏰ Link Expired or Already Used</h1>
    <p style="color: #666; font-size: 18px;">
        This approval link is no longer valid.<br>
        The operator must resolve this issue manually.
    </p>
    <p style="color: #999; font-size: 14px;">
        Check your runbooks or contact the on-call engineer.
    </p>
</body>
</html>"""
        return Response(content=html, media_type="text/html", status_code=410)

    # Check if alert has already resolved before showing confirmation
    if resolved_tracker.is_resolved(approval.incident_id):
        html = """\
<html>
<body style="font-family: sans-serif; text-align: center; padding: 60px;">
    <h1 style="color: #17a2b8;">ℹ️ Alert Already Resolved</h1>
    <p style="color: #333; font-size: 18px;">
        This alert has already resolved on its own.<br>
        No remediation action is needed.
    </p>
</body>
</html>"""
        return Response(content=html, media_type="text/html", status_code=200)

    # Show confirmation page with POST form (prevents email scanner auto-approval)
    html = f"""\
<html>
<body style="font-family: sans-serif; text-align: center; padding: 60px;">
    <h1 style="color: #fd7e14;">⚠️ Confirm Remediation</h1>
    <p style="color: #333; font-size: 18px;">
        You are about to approve the following automated remediation:
    </p>
    <table style="margin: 20px auto; text-align: left; border-collapse: collapse;">
        <tr><td style="padding: 8px; font-weight: bold;">Alert:</td>
            <td style="padding: 8px;">{approval.alert_name}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Host:</td>
            <td style="padding: 8px;">{approval.affected_host}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Action:</td>
            <td style="padding: 8px;">{approval.proposed_action}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Playbook:</td>
            <td style="padding: 8px;"><code>{approval.playbook_path}</code></td></tr>
    </table>
    <form method="POST" action="/approve/{token}/confirm">
        <button type="submit"
            style="background: #28a745; color: white; padding: 14px 32px;
                   border: none; border-radius: 6px; font-size: 16px;
                   font-weight: bold; cursor: pointer;">
            ✅ Confirm & Execute Remediation
        </button>
    </form>
    <p style="color: #999; font-size: 13px; margin-top: 20px;">
        Click the button above to trigger the automated fix.<br>
        If you did not intend to approve this, simply close this page.
    </p>
</body>
</html>"""
    return Response(content=html, media_type="text/html", status_code=200)


@app.post("/approve/{token}/confirm")
async def confirm_remediation(token: str, background_tasks: BackgroundTasks) -> Response:
    """Execute remediation after explicit human confirmation via POST.

    This endpoint is called when the operator clicks the "Confirm" button
    on the approval confirmation page. Using POST prevents email link
    scanners (Outlook Safe Links, Gmail) from auto-triggering.
    """
    approval = approval_handler.validate_and_consume(token)

    if approval is None:
        html = """\
<html>
<body style="font-family: sans-serif; text-align: center; padding: 60px;">
    <h1 style="color: #dc3545;">⏰ Link Expired or Already Used</h1>
    <p style="color: #666; font-size: 18px;">
        This approval link is no longer valid.<br>
        The operator must resolve this issue manually.
    </p>
</body>
</html>"""
        return Response(content=html, media_type="text/html", status_code=410)

    # Token valid — execute remediation in background
    background_tasks.add_task(
        _execute_approved_remediation, approval
    )

    html = f"""\
<html>
<body style="font-family: sans-serif; text-align: center; padding: 60px;">
    <h1 style="color: #28a745;">✅ Remediation Approved & Triggered</h1>
    <p style="color: #333; font-size: 18px;">
        The following action is now executing:
    </p>
    <table style="margin: 20px auto; text-align: left; border-collapse: collapse;">
        <tr><td style="padding: 8px; font-weight: bold;">Alert:</td>
            <td style="padding: 8px;">{approval.alert_name}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Host:</td>
            <td style="padding: 8px;">{approval.affected_host}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Action:</td>
            <td style="padding: 8px;">{approval.proposed_action}</td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Playbook:</td>
            <td style="padding: 8px;"><code>{approval.playbook_path}</code></td></tr>
        <tr><td style="padding: 8px; font-weight: bold;">Incident:</td>
            <td style="padding: 8px;"><code>{approval.incident_id}</code></td></tr>
    </table>
    <p style="color: #666; font-size: 14px;">
        You will receive a follow-up notification with the execution result.
    </p>
</body>
</html>"""
    return Response(content=html, media_type="text/html", status_code=200)


async def _execute_approved_remediation(approval) -> None:
    """Execute the remediation after approval, routing through guardrails.

    All 6 safety checks (except Approval Gate) are still evaluated even
    after human approval. This prevents execution during maintenance windows,
    against protected hosts, or when the circuit breaker is open.

    Improvement 1: Unified Execution Path — fixes the approval bypass bug.
    """
    from src.guardrails.models import RemediationAction, GuardrailDecisionType

    logger.info(
        "Executing approved remediation: incident=%s action=%s target=%s",
        approval.incident_id,
        approval.proposed_action,
        approval.affected_host,
    )

    # --- Guardrail evaluation (skip Approval Gate since human already approved) ---
    guardrail_engine = getattr(orchestrator, "_guardrail_engine", None)
    if guardrail_engine is not None:
        action = RemediationAction(
            incident_id=approval.incident_id,
            action_name=os.path.basename(approval.playbook_path),
            target_host=approval.affected_host,
            service_name=approval.service_name,
            playbook_path=approval.playbook_path,
            severity=approval.severity,
            pre_approved=True,
        )

        decision = await guardrail_engine.evaluate(action, skip_approval=True)

        if decision.decision_type == GuardrailDecisionType.DENY:
            logger.warning(
                "Post-approval guardrail DENY: incident=%s check=%s reason=%s",
                approval.incident_id,
                decision.denying_check,
                decision.reason,
            )
            # TODO: Send notification to operator explaining why execution was blocked
            return

        if decision.decision_type == GuardrailDecisionType.DEFER:
            logger.info(
                "Post-approval guardrail DEFER: incident=%s reason=%s",
                approval.incident_id,
                decision.reason,
            )
            # Action will be re-evaluated when the deferral condition clears
            return

    # --- Execute the remediation ---
    # Keep the resolved tracker in step, so a later "resolved" alert is reported as
    # resolved after remediation instead of "resolved before execution".
    resolved_tracker.mark_executing(approval.incident_id)
    try:
        result = await executor.execute(
            playbook_path=approval.playbook_path,
            target_host=approval.affected_host,
            extra_vars=approval.extra_vars,
        )
        resolved_tracker.mark_completed(approval.incident_id)
        logger.info(
            "Approved remediation completed: incident=%s status=%s duration=%.1fs",
            approval.incident_id,
            result.status.value,
            result.duration_seconds,
        )

        # Record metrics
        if result.status.value == "success":
            metrics_collector.increment_remediation_success(
                alert_name=approval.alert_name,
                severity=approval.severity,
            )
        else:
            metrics_collector.increment_remediation_failure(
                alert_name=approval.alert_name,
                severity=approval.severity,
            )
            # The approved fix did not work: ask AWS DevOps Agent to investigate.
            await devops_forwarder.forward_async(
                incident_id=approval.incident_id,
                trigger="failed",
                alert_name=approval.alert_name,
                severity=approval.severity,
                host=approval.affected_host,
                service_name=approval.service_name,
                summary=approval.root_cause,
                detail=(
                    f"Playbook {approval.playbook_path} finished with status "
                    f"{result.status.value} (rc={result.return_code})."
                ),
                excluded_playbook=approval.playbook_path,
            )

        # --- Record outcome for guardrail engine (circuit breaker tracking) ---
        if guardrail_engine is not None:
            await guardrail_engine.record_outcome(
                action, success=(result.status.value == "success")
            )

    except Exception as e:
        resolved_tracker.mark_completed(approval.incident_id)
        logger.error(
            "Approved remediation failed: incident=%s error=%s",
            approval.incident_id,
            str(e),
        )
        await devops_forwarder.forward_async(
            incident_id=approval.incident_id,
            trigger="failed",
            alert_name=approval.alert_name,
            severity=approval.severity,
            host=approval.affected_host,
            service_name=approval.service_name,
            summary=approval.root_cause,
            detail=f"Playbook {approval.playbook_path} raised {type(e).__name__}.",
            excluded_playbook=approval.playbook_path,
        )
        # Record failure for circuit breaker
        if guardrail_engine is not None:
            action = RemediationAction(
                incident_id=approval.incident_id,
                action_name=os.path.basename(approval.playbook_path),
                target_host=approval.affected_host,
                service_name=approval.service_name,
            )
            await guardrail_engine.record_outcome(action, success=False)
