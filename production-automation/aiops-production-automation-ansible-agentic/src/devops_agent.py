"""Forward selected incidents to AWS DevOps Agent for autonomous investigation.

Phase 1 of the AWS DevOps Agent integration (see docs/devops-agent-integration.md).

Sends an incident to an Agent Space *generic webhook* (HMAC authentication) when:
- ``unmatched``  – no playbook matched (the slow, "unknown problem" path)
- ``failed``     – an approved remediation failed or raised an error
- ``critical``   – any critical/P1 alert, even if a playbook matched
- ``resolved``   – opt-in: the alert recovered (sent against the original ids)

DevOps Agent only investigates and proposes mitigations; it never executes
anything in our pipeline. Execution still goes through PlanValidator and the
human approval gate.

Context sent with each incident (all inside ``description``, which is the only
free-text field the agent reads): redacted alert labels, runbook URL, and what
was already tried (a failed playbook and its outcome). All alert-derived text
is sanitised first. A spike against a real Agent Space showed the agent
ignores output-format instructions placed in the description, so none are sent.

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
import re
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# "resolved" is opt-in: DevOps Agent's handling of a follow-up update on an
# existing incident id is not yet verified, so it is not in DEFAULT_TRIGGERS.
VALID_TRIGGERS = frozenset({"unmatched", "failed", "critical", "resolved"})
DEFAULT_TRIGGERS = "unmatched,failed,critical"

REQUEST_TIMEOUT_SECONDS = 5
MAX_RETRIES = 2
BACKOFF_SECONDS = (1.0, 2.0)
MAX_DESCRIPTION_CHARS = 4000
MAX_TITLE_CHARS = 200
DEDUP_CACHE_SIZE = 1000

# Context sent to DevOps Agent is bounded and sanitised: it is read by an LLM,
# and alert labels are attacker-influenceable text.
MAX_LABELS = 12
MAX_LABEL_VALUE_CHARS = 120
MAX_LABELS_CHARS = 700
MAX_FIELD_CHARS = 600
MAX_ACTIVE_INCIDENTS = 1000
MAX_TRIGGERS_PER_ALERT = 5

# Labels already shown elsewhere in the description, or pure noise.
_SKIPPED_LABELS = frozenset(
    {"alertname", "severity", "instance", "service_name", "job"}
)
_SENSITIVE_LABEL = re.compile(
    r"(pass|secret|token|key|credential|auth|cookie|session|bearer|private|signature)",
    re.IGNORECASE,
)
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

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


# ForwardResult.reason when the same incident and trigger were already sent by this task.
REASON_ALREADY_FORWARDED = "already forwarded"


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
    # Phase 2b: for no-playbook alerts the findings Lambda (DevOps Agent + Bedrock) sends the
    # advisory email, so this task must not call Bedrock when forwarding succeeded.
    advisory_mode: bool = False

    @classmethod
    def from_env(cls) -> "DevOpsAgentConfig":
        """Load configuration; invalid values fall back to safe defaults."""
        enabled = (
            os.environ.get("DEVOPS_AGENT_ENABLED", "false").strip().lower() == "true"
        )
        raw_triggers = os.environ.get("DEVOPS_AGENT_FORWARD_ON", DEFAULT_TRIGGERS)
        triggers = frozenset(
            t.strip().lower() for t in raw_triggers.split(",") if t.strip()
        )
        unknown = triggers - VALID_TRIGGERS
        if unknown:
            logger.warning(
                "Ignoring unknown DEVOPS_AGENT_FORWARD_ON values: %s", sorted(unknown)
            )
            triggers = triggers & VALID_TRIGGERS
        try:
            max_per_hour = max(
                0, int(os.environ.get("DEVOPS_AGENT_MAX_PER_HOUR", "20"))
            )
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
            aws_region=os.environ.get(
                "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "")
            ),
            web_app_url=os.environ.get("DEVOPS_AGENT_WEB_APP_URL", "").strip(),
            advisory_mode=(
                os.environ.get("DEVOPS_AGENT_ADVISORY_MODE", "false").strip().lower()
                == "true"
            ),
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


def sanitize_text(value: object, limit: int) -> str:
    """Make untrusted text safe to embed in the description.

    Strips control characters and collapses whitespace (so a value cannot start
    a forged line in the description), and truncates.
    """
    text = _CONTROL_CHARS.sub(" ", str(value))
    text = " ".join(text.split())
    return _truncate(text, limit)


def redact_labels(labels: Optional[dict]) -> dict[str, str]:
    """Return a bounded, redacted copy of alert labels (never raises).

    Sensitive-looking keys are dropped entirely (not masked), noise labels are
    skipped, and values are sanitised and truncated.
    """
    if not isinstance(labels, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key in sorted(labels, key=str):
        name = sanitize_text(key, 60)
        if not name or name in _SKIPPED_LABELS or _SENSITIVE_LABEL.search(name):
            continue
        cleaned[name] = sanitize_text(labels[key], MAX_LABEL_VALUE_CHARS)
        if len(cleaned) >= MAX_LABELS:
            break
    return cleaned


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
        # "alert|host" -> [(incident_id, trigger), ...] successfully forwarded by
        # THIS task; used to send `resolved` updates against the original ids.
        self._forwarded: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()

        cfg = self._config
        self._active = (
            cfg.enabled and bool(cfg.webhook_url) and bool(cfg.webhook_secret)
        )
        if cfg.enabled and not self._active:
            logger.warning(
                "DEVOPS_AGENT_ENABLED=true but the webhook URL or secret is empty "
                "(secret /aiops/%s/devops-agent-webhook) — forwarding DISABLED",
                cfg.environment,
            )
        elif self._active and not cfg.webhook_url.startswith("https://"):
            logger.error(
                "DevOps Agent webhook URL must use https — forwarding DISABLED"
            )
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

    @property
    def advisory_mode(self) -> bool:
        """Whether DevOps Agent (not this task) produces the advisory for unmatched alerts."""
        return self._config.advisory_mode

    def defers_advisory(self, result: "ForwardResult") -> bool:
        """True when the findings Lambda will send the advisory, so this task must not.

        That holds only in advisory mode and only when an investigation exists for this
        incident: it was just sent, or an earlier alert already forwarded it. Any other
        outcome (disabled, capped, failed) returns False so the caller falls back to its
        own Bedrock advisory and the operator is never left without advice.
        """
        if not self._config.advisory_mode:
            return False
        return result.status == "sent" or (
            result.status == "skipped" and result.reason == REASON_ALREADY_FORWARDED
        )

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
        labels: Optional[dict] = None,
        runbook_url: str = "",
        excluded_playbook: str = "",
        action: str = "created",
    ) -> dict:
        """Build the webhook body (schema from the AWS DevOps Agent docs).

        Only ``title``, ``description``, ``priority`` and the incident reference
        reach the agent, so all context goes into ``description``. Every
        free-text value is sanitised because the agent is an LLM.

        Args:
            excluded_playbook: A playbook that already failed for this incident;
                it is stated as context so the agent does not suggest it again.
            action: ``created`` (default) or ``resolved``.
        """
        resolved = action == "resolved"
        reasons = {
            "unmatched": "No automated playbook matched this alert.",
            "failed": "An approved automated remediation failed.",
            "critical": "Critical alert; investigation requested in parallel.",
        }
        alert = sanitize_text(alert_name, 200)
        host_text = sanitize_text(host, 200)
        lines = [
            f"Alert: {alert}",
            f"Severity: {sanitize_text(severity, 40)}",
            f"Host: {host_text}",
            f"Service: {sanitize_text(service_name, 120)}",
            f"Environment: {self._config.environment}",
            f"Region: {self._config.aws_region}",
        ]
        if resolved:
            lines.append(
                "Update: the alert has RESOLVED (recovered). No further action is needed."
            )
        else:
            lines.append(
                f"Why forwarded: {reasons.get(trigger, sanitize_text(trigger, 40))}"
            )
        lines.append(f"Summary: {sanitize_text(summary, MAX_FIELD_CHARS)}")
        if not resolved:
            label_text = "; ".join(f"{k}={v}" for k, v in redact_labels(labels).items())
            if label_text:
                lines.append(f"Labels: {_truncate(label_text, MAX_LABELS_CHARS)}")
            runbook = sanitize_text(runbook_url, 300)
            if runbook.startswith(("https://", "http://")):
                lines.append(f"Runbook: {runbook}")
        if detail:
            lines.append(f"Detail: {sanitize_text(detail, MAX_FIELD_CHARS)}")
        if excluded_playbook and not resolved:
            lines.append(
                f"Already tried and FAILED for this incident: "
                f"{sanitize_text(excluded_playbook, 80)}"
            )
        lines.append(f"AIOps incident reference: {sanitize_text(incident_id, 100)}")

        description = _truncate("\n".join(lines), MAX_DESCRIPTION_CHARS)
        return {
            "eventType": "incident",
            # Stable per (incident, trigger) so retries are de-duplicated upstream
            "incidentId": _truncate(f"aiops-{incident_id}-{trigger}", 200),
            "action": "resolved" if resolved else "created",
            "priority": map_priority(severity),
            "title": _truncate(
                f"[AIOps/{self._config.environment}] {alert} on {host_text}",
                MAX_TITLE_CHARS,
            ),
            "description": description,
            "timestamp": _utc_timestamp(),
            "service": sanitize_text(service_name, 120) or "unknown",
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
                "x-amzn-event-signature": sign(
                    self._config.webhook_secret, timestamp, body
                ),
            },
        )
        with self._opener(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return int(getattr(response, "status", 200))

    def _reserve(self, dedup_key: str, incident_id: str) -> Optional[ForwardResult]:
        """Claim a de-duplication + rate-limit slot. Returns a skip result, or None if reserved."""
        with self._lock:
            if dedup_key in self._seen:
                return ForwardResult("skipped", REASON_ALREADY_FORWARDED)
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
        return None

    @staticmethod
    def _alert_key(alert_name: object, host: object) -> str:
        return f"{alert_name}|{host}"

    def _remember(self, incident_id: str, trigger: str, fields: dict) -> None:
        """Record a successful forward so a later `resolved` can reference it."""
        key = self._alert_key(fields.get("alert_name", ""), fields.get("host", ""))
        with self._lock:
            entries = self._forwarded.setdefault(key, [])
            entries.append((incident_id, trigger))
            del entries[:-MAX_TRIGGERS_PER_ALERT]
            self._forwarded.move_to_end(key)
            while len(self._forwarded) > MAX_ACTIVE_INCIDENTS:
                self._forwarded.popitem(last=False)

    def forward(
        self, *, incident_id: str, trigger: str, **fields: object
    ) -> ForwardResult:
        """Send one incident. Synchronous; never raises."""
        if trigger == "resolved":
            return ForwardResult("skipped", "use forward_resolved for resolved updates")
        if not self.should_forward(trigger):
            return ForwardResult(
                "skipped", f"trigger '{trigger}' not enabled or forwarding off"
            )

        skipped = self._reserve(f"{incident_id}:{trigger}", incident_id)
        if skipped is not None:
            return skipped

        try:
            body = json.dumps(
                self.build_payload(incident_id=incident_id, trigger=trigger, **fields),
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as e:
            logger.error(
                "DevOps Agent payload build failed: %s",
                e,
                extra={"incident_id": incident_id},
            )
            return ForwardResult("failed", f"payload error: {e}")

        result = self._deliver(body, incident_id, trigger)
        if result.status == "sent":
            self._remember(incident_id, trigger, fields)
        return result

    def forward_resolved(
        self,
        *,
        alert_name: str,
        host: str,
        severity: str = "",
        service_name: str = "",
        summary: str = "",
    ) -> ForwardResult:
        """Tell DevOps Agent an alert recovered, against the incidents we forwarded.

        Opt-in (``resolved`` trigger). Only acts on incidents forwarded by THIS
        task for the same alert and host; otherwise it is skipped. Synchronous;
        never raises.
        """
        if not (self._active and "resolved" in self._config.triggers):
            return ForwardResult("skipped", "resolved updates not enabled")

        with self._lock:
            entries = self._forwarded.pop(self._alert_key(alert_name, host), [])
        if not entries:
            return ForwardResult(
                "skipped", "nothing forwarded for this alert on this task"
            )

        sent_any = False
        last = ForwardResult("skipped", "already updated or capped")
        for incident_id, trigger in entries:
            skipped = self._reserve(f"{incident_id}:{trigger}:resolved", incident_id)
            if skipped is not None:
                last = skipped
                continue
            try:
                body = json.dumps(
                    self.build_payload(
                        incident_id=incident_id,
                        trigger=trigger,
                        action="resolved",
                        alert_name=alert_name,
                        severity=severity,
                        host=host,
                        service_name=service_name,
                        summary=summary or f"{alert_name} resolved on {host}",
                    ),
                    separators=(",", ":"),
                )
            except (TypeError, ValueError) as e:
                logger.error(
                    "DevOps Agent resolved payload build failed: %s",
                    e,
                    extra={"incident_id": incident_id},
                )
                last = ForwardResult("failed", f"payload error: {e}")
                continue
            last = self._deliver(body, incident_id, f"{trigger}/resolved")
            sent_any = sent_any or last.status == "sent"
        return ForwardResult("sent") if sent_any else last

    def _deliver(self, body: str, incident_id: str, trigger: str) -> ForwardResult:
        """POST the body with bounded retries. Never raises."""
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

    async def forward_async(
        self, *, incident_id: str, trigger: str, **fields: object
    ) -> ForwardResult:
        """Forward from async code without blocking the event loop. Never raises."""
        if not self.should_forward(trigger):
            return ForwardResult("skipped", "not enabled")
        try:
            return await asyncio.to_thread(
                self.forward, incident_id=incident_id, trigger=trigger, **fields
            )
        except Exception as e:  # noqa: BLE001 - forwarding must never break the pipeline
            logger.warning(
                "DevOps Agent forwarding error: %s",
                e,
                extra={"incident_id": incident_id},
            )
            return ForwardResult("failed", str(e))

    async def forward_resolved_async(self, **fields: str) -> ForwardResult:
        """Async wrapper for forward_resolved. Never raises."""
        if not (self._active and "resolved" in self._config.triggers):
            return ForwardResult("skipped", "resolved updates not enabled")
        try:
            return await asyncio.to_thread(self.forward_resolved, **fields)
        except Exception as e:  # noqa: BLE001 - forwarding must never break the pipeline
            logger.warning("DevOps Agent resolved update error: %s", e)
            return ForwardResult("failed", str(e))
