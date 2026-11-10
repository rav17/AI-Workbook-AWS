"""Forward selected incidents to AWS DevOps Agent for autonomous investigation.

Phase 1 of the AWS DevOps Agent integration (see docs/devops-agent-integration.md).

Sends an incident to an Agent Space *generic webhook* (HMAC authentication) when:
- ``unmatched``  – no playbook matched (the slow, "unknown problem" path)
- ``failed``     – an approved remediation failed or raised an error
- ``critical``   – any critical/P1 alert, even if a playbook matched

DevOps Agent only investigates and proposes mitigations; it never executes
anything in our pipeline. Execution still goes through PlanValidator and the
human approval gate.

Safety properties:
- Disabled unless DEVOPS_AGENT_ENABLED=true AND a webhook URL + secret are set.
- Never raises and never blocks the pipeline (5s timeout, 2 retries, runs in a
  worker thread). Failures are logged with incident_id.
- Cost guard: per-task hourly cap (DEVOPS_AGENT_MAX_PER_HOUR, default 20) and
  per-incident de-duplication. DevOps Agent bills per active agent-second.
- Only selected, non-sensitive fields are sent. DevOps Agent ignores the
  ``data`` field, so all context goes into ``description``.

Webhook contract (AWS docs, "Invoking DevOps Agent through Webhook"):
    signature = base64(HMAC_SHA256(secret, f"{timestamp}:{body}"))
    headers:   x-amzn-event-timestamp, x-amzn-event-signature
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)

VALID_TRIGGERS = frozenset({"unmatched", "failed", "critical"})
DEFAULT_TRIGGERS = "unmatched,failed,critical"

REQUEST_TIMEOUT_SECONDS = 5
MAX_RETRIES = 2
BACKOFF_SECONDS = (1.0, 2.0)
MAX_DESCRIPTION_CHARS = 4000
MAX_TITLE_CHARS = 200
DEDUP_CACHE_SIZE = 1000

# Our alert severity label (or internal P-level) -> DevOps Agent priority
_PRIORITY_MAP = {
    "critical": "CRITICAL",
    "p1": "CRITICAL",
    "high": "HIGH",
    "warning": "HIGH",
    "p2": "HIGH",
    "info": "MEDIUM",
    "p3": "MEDIUM",
    "low": "LOW",
}


@dataclass
class ForwardResult:
    """Outcome of a forward attempt (never an exception)."""

    status: str  # "sent" | "skipped" | "failed"
    reason: str = ""
    http_status: int = 0


@dataclass
class DevOpsAgentConfig:
    """Runtime configuration, read from environment variables."""

    enabled: bool
    webhook_url: str
    webhook_secret: str
    triggers: frozenset[str]
    max_per_hour: int
    environment: str
    aws_region: str
    web_app_url: str

    @classmethod
    def from_env(cls) -> "DevOpsAgentConfig":
        """Load configuration; invalid values fall back to safe defaults."""
        enabled = os.environ.get("DEVOPS_AGENT_ENABLED", "false").strip().lower() == "true"
        raw_triggers = os.environ.get("DEVOPS_AGENT_FORWARD_ON", DEFAULT_TRIGGERS)
        triggers = frozenset(
            t.strip().lower() for t in raw_triggers.split(",") if t.strip()
        )
        unknown = triggers - VALID_TRIGGERS
        if unknown:
            logger.warning("Ignoring unknown DEVOPS_AGENT_FORWARD_ON values: %s", sorted(unknown))
            triggers = triggers & VALID_TRIGGERS
        try:
            max_per_hour = max(0, int(os.environ.get("DEVOPS_AGENT_MAX_PER_HOUR", "20")))
        except ValueError:
            logger.warning("Invalid DEVOPS_AGENT_MAX_PER_HOUR; using 20")
            max_per_hour = 20
        return cls(
            enabled=enabled,
            webhook_url=os.environ.get("DEVOPS_AGENT_WEBHOOK_URL", "").strip(),
            webhook_secret=os.environ.get("DEVOPS_AGENT_WEBHOOK_SECRET", "").strip(),
            triggers=triggers,
            max_per_hour=max_per_hour,
            environment=os.environ.get("ENVIRONMENT", "dev"),
            aws_region=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "")),
            web_app_url=os.environ.get("DEVOPS_AGENT_WEB_APP_URL", "").strip(),
        )


def map_priority(severity: str) -> str:
    """Map our severity label to a DevOps Agent priority (unknown -> MEDIUM)."""
    return _PRIORITY_MAP.get((severity or "").strip().lower(), "MEDIUM")


def sign(secret: str, timestamp: str, body: str) -> str:
    """Compute the DevOps Agent HMAC signature for a request body."""
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:{body}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _utc_timestamp() -> str:
    """Timestamp in the format DevOps Agent expects: 2026-11-10T03:00:00.000Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


class DevOpsAgentForwarder:
    """Sends incident events to an AWS DevOps Agent generic webhook."""

    def __init__(
        self,
        config: Optional[DevOpsAgentConfig] = None,
        opener: Optional[Callable] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create the forwarder.

        Args:
            config: Configuration (defaults to DevOpsAgentConfig.from_env()).
            opener: urlopen-compatible callable (injectable for tests).
            sleep: Sleep function used for retry backoff (injectable for tests).
        """
        self._config = config or DevOpsAgentConfig.from_env()
        self._opener = opener or urllib.request.urlopen
        self._sleep = sleep
        self._lock = threading.Lock()
        self._sent_at: deque[float] = deque()
        self._seen: OrderedDict[str, None] = OrderedDict()

        cfg = self._config
        self._active = cfg.enabled and bool(cfg.webhook_url) and bool(cfg.webhook_secret)
        if cfg.enabled and not self._active:
            logger.warning(
                "DEVOPS_AGENT_ENABLED=true but the webhook URL or secret is empty "
                "(secret /aiops/%s/devops-agent-webhook) — forwarding DISABLED",
                cfg.environment,
            )
        elif self._active and not cfg.webhook_url.startswith("https://"):
            logger.error("DevOps Agent webhook URL must use https — forwarding DISABLED")
            self._active = False
        logger.info(
            "DevOps Agent forwarding: active=%s triggers=%s max_per_hour=%d",
            self._active,
            sorted(cfg.triggers),
            cfg.max_per_hour,
        )

    @property
    def active(self) -> bool:
        """Whether incidents will actually be forwarded."""
        return self._active

    @property
    def web_app_url(self) -> str:
        """Optional DevOps Agent web app URL to include in our emails."""
        return self._config.web_app_url

    def should_forward(self, trigger: str) -> bool:
        """Whether this trigger type is enabled."""
        return self._active and trigger in self._config.triggers

    def build_payload(
        self,
        *,
        incident_id: str,
        trigger: str,
        alert_name: str,
        severity: str,
        host: str,
        service_name: str,
        summary: str,
        detail: str = "",
    ) -> dict:
        """Build the webhook body (schema from the AWS DevOps Agent docs)."""
        reasons = {
            "unmatched": "No automated playbook matched this alert.",
            "failed": "An approved automated remediation failed.",
            "critical": "Critical alert; investigation requested in parallel.",
        }
        lines = [
            f"Alert: {alert_name}",
            f"Severity: {severity}",
            f"Host: {host}",
            f"Service: {service_name}",
            f"Environment: {self._config.environment}",
            f"Region: {self._config.aws_region}",
            f"Why forwarded: {reasons.get(trigger, trigger)}",
            f"Summary: {summary}",
        ]
        if detail:
            lines.append(f"Detail: {detail}")
        lines.append(f"AIOps incident reference: {incident_id}")
        return {
            "eventType": "incident",
            # Stable per (incident, trigger) so retries are de-duplicated upstream
            "incidentId": _truncate(f"aiops-{incident_id}-{trigger}", 200),
            "action": "created",
            "priority": map_priority(severity),
            "title": _truncate(f"[AIOps/{self._config.environment}] {alert_name} on {host}",
                               MAX_TITLE_CHARS),
            "description": _truncate("\n".join(lines), MAX_DESCRIPTION_CHARS),
            "timestamp": _utc_timestamp(),
            "service": service_name or "unknown",
        }

    def _within_rate_limit(self) -> bool:
        now = time.monotonic()
        while self._sent_at and now - self._sent_at[0] > 3600:
            self._sent_at.popleft()
        return len(self._sent_at) < self._config.max_per_hour

    def _post(self, body: str) -> int:
        timestamp = _utc_timestamp()
        request = urllib.request.Request(
            self._config.webhook_url,
            data=body.encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-amzn-event-timestamp": timestamp,
                "x-amzn-event-signature": sign(self._config.webhook_secret, timestamp, body),
            },
        )
        with self._opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return int(getattr(response, "status", 200))

    def forward(self, *, incident_id: str, trigger: str, **fields: str) -> ForwardResult:
        """Send one incident. Synchronous; never raises."""
        if not self.should_forward(trigger):
            return ForwardResult("skipped", f"trigger '{trigger}' not enabled or forwarding off")

        dedup_key = f"{incident_id}:{trigger}"
        with self._lock:
            if dedup_key in self._seen:
                return ForwardResult("skipped", "already forwarded")
            if not self._within_rate_limit():
                logger.warning(
                    "DevOps Agent hourly cap reached (%d) — not forwarding",
                    self._config.max_per_hour,
                    extra={"incident_id": incident_id},
                )
                return ForwardResult("skipped", "hourly cap reached")
            # Reserve the slot before sending so concurrent callers can't overshoot.
            self._seen[dedup_key] = None
            if len(self._seen) > DEDUP_CACHE_SIZE:
                self._seen.popitem(last=False)
            self._sent_at.append(time.monotonic())

        try:
            body = json.dumps(
                self.build_payload(incident_id=incident_id, trigger=trigger, **fields),
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as e:
            logger.error("DevOps Agent payload build failed: %s", e,
                         extra={"incident_id": incident_id})
            return ForwardResult("failed", f"payload error: {e}")

        last_error = ""
        for attempt in range(MAX_RETRIES + 1):
            try:
                status = self._post(body)
                logger.info(
                    "Incident forwarded to AWS DevOps Agent (trigger=%s, http=%d)",
                    trigger,
                    status,
                    extra={"incident_id": incident_id},
                )
                return ForwardResult("sent", http_status=status)
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}"
                if 400 <= e.code < 500 and e.code != 429:
                    break  # auth/format problem: retrying will not help
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_error = f"{type(e).__name__}: {e}"
            except Exception as e:  # noqa: BLE001 - must never break the pipeline
                last_error = f"unexpected {type(e).__name__}: {e}"
                break
            if attempt < MAX_RETRIES:
                self._sleep(BACKOFF_SECONDS[attempt])

        logger.warning(
            "Failed to forward incident to AWS DevOps Agent (trigger=%s): %s",
            trigger,
            last_error,
            extra={"incident_id": incident_id},
        )
        return ForwardResult("failed", last_error)

    async def forward_async(self, *, incident_id: str, trigger: str, **fields: str) -> ForwardResult:
        """Forward from async code without blocking the event loop. Never raises."""
        if not self.should_forward(trigger):
            return ForwardResult("skipped", "not enabled")
        try:
            return await asyncio.to_thread(
                self.forward, incident_id=incident_id, trigger=trigger, **fields
            )
        except Exception as e:  # noqa: BLE001 - forwarding must never break the pipeline
            logger.warning("DevOps Agent forwarding error: %s", e,
                           extra={"incident_id": incident_id})
            return ForwardResult("failed", str(e))
