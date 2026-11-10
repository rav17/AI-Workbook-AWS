"""Unit tests for the AWS DevOps Agent forwarder (Phase 1 integration)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import io
import json
import urllib.error
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.devops_agent import (
    DevOpsAgentConfig,
    DevOpsAgentForwarder,
    map_priority,
    sign,
)

pytestmark = pytest.mark.unit

URL = "https://event-ai.us-east-1.api.aws/webhook/generic/test-id"
SECRET = "test-webhook-secret"

FIELDS = dict(
    alert_name="NetworkFloodDetected",
    severity="critical",
    host="i-0123456789abcdef0",
    service_name="web-frontend",
    summary="Network packets spike",
)


def _config(**overrides) -> DevOpsAgentConfig:
    values = dict(
        enabled=True,
        webhook_url=URL,
        webhook_secret=SECRET,
        triggers=frozenset({"unmatched", "failed", "critical"}),
        max_per_hour=20,
        environment="dev",
        aws_region="us-east-1",
        web_app_url="",
    )
    values.update(overrides)
    return DevOpsAgentConfig(**values)


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(URL, code, "err", {}, io.BytesIO(b""))


def _forwarder(opener=None, **cfg) -> tuple[DevOpsAgentForwarder, MagicMock, MagicMock]:
    opener = opener or MagicMock(return_value=_Response())
    sleep = MagicMock()
    return DevOpsAgentForwarder(config=_config(**cfg), opener=opener, sleep=sleep), opener, sleep


class TestSignature:
    def test_matches_documented_algorithm(self) -> None:
        """base64(HMAC_SHA256(secret, "{timestamp}:{body}")) per the AWS docs."""
        ts, body = "2026-11-10T03:00:00.000Z", '{"eventType":"incident"}'
        expected = base64.b64encode(
            hmac.new(SECRET.encode(), f"{ts}:{body}".encode(), hashlib.sha256).digest()
        ).decode()
        assert sign(SECRET, ts, body) == expected

    def test_request_carries_signed_headers_over_the_exact_body(self) -> None:
        forwarder, opener, _ = _forwarder()

        forwarder.forward(incident_id="inc-1", trigger="unmatched", **FIELDS)

        request = opener.call_args.args[0]
        headers = {k.lower(): v for k, v in request.header_items()}
        ts = headers["x-amzn-event-timestamp"]
        body = request.data.decode("utf-8")
        assert headers["content-type"] == "application/json"
        assert headers["x-amzn-event-signature"] == sign(SECRET, ts, body)
        assert request.get_method() == "POST"
        assert request.full_url == URL
        assert opener.call_args.kwargs["timeout"] == 5


class TestPayload:
    def test_schema_fields(self) -> None:
        forwarder, _, _ = _forwarder()
        p = forwarder.build_payload(incident_id="inc-1", trigger="unmatched", **FIELDS)

        assert p["eventType"] == "incident"
        assert p["action"] == "created"
        assert p["priority"] == "CRITICAL"
        assert p["incidentId"] == "aiops-inc-1-unmatched"
        assert p["service"] == "web-frontend"
        assert p["timestamp"].endswith(".000Z")
        # DevOps Agent ignores `data`, so context must be in the description
        assert "data" not in p
        for text in ("NetworkFloodDetected", "i-0123456789abcdef0", "inc-1", "us-east-1"):
            assert text in p["description"]

    def test_long_fields_are_truncated(self) -> None:
        forwarder, _, _ = _forwarder()
        p = forwarder.build_payload(
            incident_id="inc-1", trigger="unmatched", **{**FIELDS, "summary": "x" * 10000,
                                                         "alert_name": "A" * 500}
        )
        assert len(p["description"]) <= 4000
        assert len(p["title"]) <= 200

    @pytest.mark.parametrize(
        ("severity", "priority"),
        [("critical", "CRITICAL"), ("P1", "CRITICAL"), ("warning", "HIGH"),
         ("P2", "HIGH"), ("info", "MEDIUM"), ("", "MEDIUM"), ("weird", "MEDIUM")],
    )
    def test_priority_mapping(self, severity, priority) -> None:
        assert map_priority(severity) == priority


class TestActivation:
    def test_disabled_sends_nothing(self) -> None:
        forwarder, opener, _ = _forwarder(enabled=False)
        assert forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS).status == "skipped"
        opener.assert_not_called()

    @pytest.mark.parametrize("missing", ["webhook_url", "webhook_secret"])
    def test_enabled_without_credentials_is_inactive(self, missing) -> None:
        forwarder, opener, _ = _forwarder(**{missing: ""})
        assert forwarder.active is False
        forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS)
        opener.assert_not_called()

    def test_non_https_url_is_rejected(self) -> None:
        forwarder, _, _ = _forwarder(webhook_url="http://insecure.example.com/hook")
        assert forwarder.active is False

    def test_trigger_not_enabled_is_skipped(self) -> None:
        forwarder, opener, _ = _forwarder(triggers=frozenset({"unmatched"}))
        assert forwarder.forward(incident_id="i", trigger="critical", **FIELDS).status == "skipped"
        opener.assert_not_called()

    def test_config_from_env_defaults_off_and_drops_unknown_triggers(self, monkeypatch) -> None:
        for var in ("DEVOPS_AGENT_ENABLED", "DEVOPS_AGENT_WEBHOOK_URL", "DEVOPS_AGENT_WEBHOOK_SECRET"):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("DEVOPS_AGENT_FORWARD_ON", "unmatched,bogus")
        monkeypatch.setenv("DEVOPS_AGENT_MAX_PER_HOUR", "not-a-number")
        cfg = DevOpsAgentConfig.from_env()
        assert cfg.enabled is False
        assert cfg.triggers == frozenset({"unmatched"})
        assert cfg.max_per_hour == 20


class TestCostGuards:
    def test_same_incident_and_trigger_sent_once(self) -> None:
        forwarder, opener, _ = _forwarder()
        assert forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS).status == "sent"
        assert forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS).status == "skipped"
        assert opener.call_count == 1

    def test_hourly_cap(self) -> None:
        forwarder, opener, _ = _forwarder(max_per_hour=2)
        statuses = [
            forwarder.forward(incident_id=f"i{n}", trigger="unmatched", **FIELDS).status
            for n in range(3)
        ]
        assert statuses == ["sent", "sent", "skipped"]
        assert opener.call_count == 2


class TestRetries:
    def test_retries_5xx_then_succeeds_with_backoff(self) -> None:
        opener = MagicMock(side_effect=[_http_error(503), _http_error(500), _Response()])
        forwarder, _, sleep = _forwarder(opener=opener)

        result = forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS)

        assert result.status == "sent"
        assert opener.call_count == 3
        assert [c.args[0] for c in sleep.call_args_list] == [1.0, 2.0]

    def test_gives_up_after_three_attempts(self) -> None:
        opener = MagicMock(side_effect=urllib.error.URLError("unreachable"))
        forwarder, _, _ = _forwarder(opener=opener)
        result = forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS)
        assert result.status == "failed"
        assert opener.call_count == 3

    def test_auth_error_is_not_retried(self) -> None:
        opener = MagicMock(side_effect=_http_error(401))
        forwarder, _, sleep = _forwarder(opener=opener)
        result = forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS)
        assert result.status == "failed" and result.reason == "HTTP 401"
        assert opener.call_count == 1
        sleep.assert_not_called()

    def test_throttling_is_retried(self) -> None:
        opener = MagicMock(side_effect=[_http_error(429), _Response()])
        forwarder, _, _ = _forwarder(opener=opener)
        assert forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS).status == "sent"

    def test_unexpected_error_never_raises(self) -> None:
        opener = MagicMock(side_effect=RuntimeError("boom"))
        forwarder, _, _ = _forwarder(opener=opener)
        assert forwarder.forward(incident_id="i", trigger="unmatched", **FIELDS).status == "failed"

    def test_forward_async_runs_off_the_event_loop(self) -> None:
        forwarder, opener, _ = _forwarder()
        result = asyncio.run(forwarder.forward_async(incident_id="i", trigger="failed", **FIELDS))
        assert result.status == "sent"
        assert json.loads(opener.call_args.args[0].data)["incidentId"] == "aiops-i-failed"


class TestAppWiring:
    """The pipeline forwards unmatched alerts and keeps working if forwarding fails."""

    def _payload(self):
        from src.models import AlertmanagerAlert, AlertmanagerPayload

        alert = AlertmanagerAlert(
            status="firing",
            labels={"alertname": "NetworkFloodDetected", "severity": "critical",
                    "instance": "i-0123456789abcdef0", "service_name": "web-frontend"},
            annotations={"summary": "Network packets spike"},
            starts_at="2026-11-10T00:00:00Z",
            ends_at="0001-01-01T00:00:00Z",
            generator_url="",
            fingerprint="fp-1",
        )
        return AlertmanagerPayload(
            version="4", group_key="g", status="firing", receiver="aiops", alerts=[alert],
            group_labels={}, common_labels={}, common_annotations={}, external_url="",
        )

    def _run(self, forward_result):
        import src.app as app
        from src.devops_agent import ForwardResult

        forwarder = MagicMock()
        forwarder.forward_async = AsyncMock(return_value=ForwardResult(forward_result))
        advisory = AsyncMock()
        with patch.object(app, "devops_forwarder", forwarder), \
             patch.object(app.orchestrator, "process_alert_payload",
                          AsyncMock(return_value=["inc-42"])), \
             patch.object(app, "playbook_mapper", MagicMock(rules=[])), \
             patch.object(app, "_send_ai_advisory_email", advisory), \
             patch.object(app.alert_inhibitor, "evaluate",
                          return_value=MagicMock(should_process=True)), \
             patch.object(app.alert_inhibitor, "register_active_incident"), \
             patch.object(app.resolved_tracker, "register_pending"):
            asyncio.run(app._process_and_notify(self._payload()))
        return forwarder, advisory

    def test_unmatched_alert_is_forwarded_and_email_mentions_it(self) -> None:
        forwarder, advisory = self._run("sent")

        kwargs = forwarder.forward_async.call_args.kwargs
        assert kwargs["trigger"] == "unmatched"
        assert kwargs["incident_id"] == "inc-42"
        assert advisory.call_args.kwargs["devops_agent_forwarded"] is True

    def test_forwarding_failure_still_sends_advisory_email(self) -> None:
        _, advisory = self._run("failed")
        advisory.assert_awaited_once()
        assert advisory.call_args.kwargs["devops_agent_forwarded"] is False
