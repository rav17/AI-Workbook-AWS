"""FastAPI application for the self-healing infrastructure webhook receiver.

Provides endpoints for:
- POST /webhook: Receives Alertmanager webhook payloads
- GET /health: Health check with dependency status
- GET /metrics: Prometheus metrics exposition
"""

import asyncio
import logging
import os
import shutil
import time
from typing import Any

from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import ValidationError

from src.models import (
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

logger = logging.getLogger(__name__)

# --- Service startup time and version ---
_SERVICE_START_TIME = time.time()
SERVICE_VERSION = os.environ.get("SERVICE_VERSION", "1.0.0")

# --- Configuration from environment variables ---
ASSET_INVENTORY_PATH = os.environ.get("ASSET_INVENTORY_PATH", "config/asset_inventory.yml")
MAPPING_CONFIG_PATH = os.environ.get("MAPPING_CONFIG_PATH", "config/mapping_config.yml")
AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "audit.log")

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
dispatcher = NotificationDispatcher(channels=[])
audit_logger = AuditLogger(log_file_path=AUDIT_LOG_PATH)

orchestrator = Orchestrator(
    normalizer=normalizer,
    enricher=enricher,
    mapper=playbook_mapper,
    executor=executor,
    dispatcher=dispatcher,
    audit_logger=audit_logger,
    metrics_collector=metrics_collector,
)

# --- FastAPI application ---
app = FastAPI(
    title="AIOps Self-Healing Infrastructure",
    description="Webhook receiver for Alertmanager with automated remediation",
    version="1.0.0",
)


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
async def webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """Receive Alertmanager webhook payloads.

    Validates Content-Type, payload size, and payload structure before
    dispatching to the orchestrator as a background task.

    Returns:
        200 with accepted status for valid payloads
        400 for invalid payloads or size exceeded
        415 for wrong Content-Type
    """
    # Check Content-Type header
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return JSONResponse(
            status_code=415,
            content={"error": "Unsupported Media Type", "detail": "Content-Type must be application/json"},
        )

    # Read body and check size
    body = await request.body()
    if len(body) > MAX_PAYLOAD_SIZE:
        return JSONResponse(
            status_code=400,
            content={"error": "Payload too large", "detail": f"Payload size exceeds {MAX_PAYLOAD_SIZE} bytes limit"},
        )

    # Parse and validate payload
    try:
        payload_model = AlertmanagerPayloadModel.model_validate_json(body)
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid payload", "detail": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON", "detail": str(e)},
        )

    # Convert to internal dataclass
    payload = _pydantic_model_to_dataclass(payload_model)

    # Dispatch processing as a background task (fire-and-forget)
    background_tasks.add_task(orchestrator.process_alert_payload, payload)

    return JSONResponse(
        status_code=200,
        content={"status": "accepted", "alerts_received": len(payload.alerts)},
    )


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint with dependency status.

    Checks:
    - ansible-playbook binary availability via shutil.which
    - Mapping config file existence
    - Asset inventory file existence

    Returns:
        200 with healthy status when all dependencies are available
        503 with degraded status when any dependency is missing
    """
    dependencies: dict[str, str] = {}

    # Check ansible-playbook binary
    ansible_path = shutil.which("ansible-playbook")
    dependencies["ansible_binary"] = "ok" if ansible_path else "missing"

    # Check mapping config file
    mapping_exists = os.path.isfile(MAPPING_CONFIG_PATH)
    dependencies["mapping_config"] = "ok" if mapping_exists else "missing"

    # Check asset inventory file
    inventory_exists = os.path.isfile(ASSET_INVENTORY_PATH)
    dependencies["asset_inventory"] = "ok" if inventory_exists else "missing"

    # Determine overall status
    all_ok = all(v == "ok" for v in dependencies.values())

    # Calculate uptime
    uptime_seconds = round(time.time() - _SERVICE_START_TIME, 2)

    if all_ok:
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "uptime_seconds": uptime_seconds,
                "version": SERVICE_VERSION,
                "dependencies": dependencies,
            },
        )
    else:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "uptime_seconds": uptime_seconds,
                "version": SERVICE_VERSION,
                "dependencies": dependencies,
            },
        )


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Expose Prometheus metrics in text exposition format.

    Returns:
        Prometheus metrics as text/plain
    """
    metrics_output = metrics_collector.render_metrics()
    return PlainTextResponse(content=metrics_output, media_type="text/plain")
