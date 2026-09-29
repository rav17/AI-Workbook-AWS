"""Unit tests for data models and enums."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from src.models import (
    # Enums
    Severity,
    RemediationStatus,
    AlertStatus,
    # Dataclasses
    AlertmanagerAlert,
    AlertmanagerPayload,
    NormalizedAlert,
    AssetInfo,
    EnrichedAlert,
    MappingRule,
    PlaybookMatch,
    ExecutionResult,
    AuditRecord,
    HealthResponse,
    # Pydantic models
    AlertmanagerAlertModel,
    AlertmanagerPayloadModel,
    HealthResponseModel,
    ErrorResponseModel,
    WebhookResponseModel,
)


class TestEnums:
    """Tests for enum definitions."""

    def test_severity_values(self):
        assert Severity.P1.value == "P1"
        assert Severity.P2.value == "P2"
        assert Severity.P3.value == "P3"

    def test_remediation_status_values(self):
        assert RemediationStatus.SUCCESS.value == "success"
        assert RemediationStatus.FAILURE.value == "failure"
        assert RemediationStatus.TIMEOUT.value == "timeout"

    def test_alert_status_values(self):
        assert AlertStatus.FIRING.value == "firing"
        assert AlertStatus.RESOLVED.value == "resolved"

    def test_severity_has_three_levels(self):
        assert len(Severity) == 3

    def test_remediation_status_has_three_states(self):
        assert len(RemediationStatus) == 3

    def test_alert_status_has_two_states(self):
        assert len(AlertStatus) == 2


class TestAlertmanagerAlert:
    """Tests for AlertmanagerAlert dataclass."""

    def test_creation_with_required_fields(self):
        alert = AlertmanagerAlert(
            status="firing",
            labels={"alertname": "HighCPU", "severity": "critical"},
            annotations={"summary": "CPU high"},
            starts_at="2024-01-01T00:00:00Z",
            ends_at="0001-01-01T00:00:00Z",
        )
        assert alert.status == "firing"
        assert alert.labels["alertname"] == "HighCPU"
        assert alert.generator_url == ""
        assert alert.fingerprint == ""

    def test_creation_with_all_fields(self):
        alert = AlertmanagerAlert(
            status="resolved",
            labels={"alertname": "DiskFull"},
            annotations={},
            starts_at="2024-01-01T00:00:00Z",
            ends_at="2024-01-01T01:00:00Z",
            generator_url="http://prometheus:9090/graph",
            fingerprint="abc123",
        )
        assert alert.generator_url == "http://prometheus:9090/graph"
        assert alert.fingerprint == "abc123"


class TestAlertmanagerPayload:
    """Tests for AlertmanagerPayload dataclass."""

    def test_creation_with_required_fields(self):
        alert = AlertmanagerAlert(
            status="firing",
            labels={"alertname": "Test"},
            annotations={},
            starts_at="2024-01-01T00:00:00Z",
            ends_at="",
        )
        payload = AlertmanagerPayload(
            version="4",
            group_key="test-group",
            status="firing",
            receiver="self-healing",
            alerts=[alert],
        )
        assert payload.version == "4"
        assert len(payload.alerts) == 1
        assert payload.group_labels == {}
        assert payload.common_labels == {}
        assert payload.external_url == ""


class TestNormalizedAlert:
    """Tests for NormalizedAlert dataclass."""

    def test_creation(self):
        now = datetime.now(timezone.utc)
        alert = NormalizedAlert(
            incident_id="uuid-123",
            alert_name="HighCPU",
            severity=Severity.P1,
            status=AlertStatus.FIRING,
            labels={"instance": "web-01:9090"},
            annotations={"summary": "CPU high"},
            starts_at=now,
            ends_at=None,
        )
        assert alert.incident_id == "uuid-123"
        assert alert.severity == Severity.P1
        assert alert.status == AlertStatus.FIRING
        assert alert.ends_at is None
        assert alert.raw_fingerprint == ""


class TestAssetInfo:
    """Tests for AssetInfo dataclass."""

    def test_creation(self):
        asset = AssetInfo(
            hostname="web-01",
            ip_address="10.0.1.1",
            location="us-east-1a",
            service_name="web-frontend",
            service_owner="platform-team",
        )
        assert asset.hostname == "web-01"
        assert asset.ip_address == "10.0.1.1"
        assert asset.service_owner == "platform-team"


class TestEnrichedAlert:
    """Tests for EnrichedAlert dataclass."""

    def test_creation_unenriched(self):
        now = datetime.now(timezone.utc)
        alert = EnrichedAlert(
            incident_id="uuid-123",
            alert_name="HighCPU",
            severity=Severity.P1,
            status=AlertStatus.FIRING,
            labels={},
            annotations={},
            starts_at=now,
            ends_at=None,
        )
        assert alert.asset is None
        assert alert.is_enriched is False

    def test_creation_enriched(self):
        now = datetime.now(timezone.utc)
        asset = AssetInfo(
            hostname="web-01",
            ip_address="10.0.1.1",
            location="us-east-1a",
            service_name="web",
            service_owner="team",
        )
        alert = EnrichedAlert(
            incident_id="uuid-123",
            alert_name="HighCPU",
            severity=Severity.P1,
            status=AlertStatus.FIRING,
            labels={},
            annotations={},
            starts_at=now,
            ends_at=None,
            asset=asset,
            is_enriched=True,
        )
        assert alert.is_enriched is True
        assert alert.asset.hostname == "web-01"


class TestMappingRule:
    """Tests for MappingRule dataclass."""

    def test_creation(self):
        rule = MappingRule(
            name="cpu-restart",
            conditions={"alert_name": "HighCPU", "severity": "P1"},
            playbook_path="playbooks/restart.yml",
        )
        assert rule.name == "cpu-restart"
        assert rule.priority == 0
        assert len(rule.conditions) == 2


class TestPlaybookMatch:
    """Tests for PlaybookMatch dataclass."""

    def test_creation(self):
        match = PlaybookMatch(
            rule_name="cpu-restart",
            playbook_path="playbooks/restart.yml",
            matched_attributes=2,
        )
        assert match.matched_attributes == 2


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_creation_success(self):
        result = ExecutionResult(
            status=RemediationStatus.SUCCESS,
            return_code=0,
            stdout="ok: [web-01]",
            stderr="",
            duration_seconds=5.2,
            playbook_path="playbooks/restart.yml",
            target_host="web-01",
        )
        assert result.status == RemediationStatus.SUCCESS
        assert result.return_code == 0

    def test_creation_failure(self):
        result = ExecutionResult(
            status=RemediationStatus.FAILURE,
            return_code=1,
            stdout="",
            stderr="fatal: [web-01]: FAILED!",
            duration_seconds=3.1,
            playbook_path="playbooks/restart.yml",
            target_host="web-01",
        )
        assert result.status == RemediationStatus.FAILURE
        assert result.return_code == 1

    def test_creation_timeout(self):
        result = ExecutionResult(
            status=RemediationStatus.TIMEOUT,
            return_code=-1,
            stdout="",
            stderr="Execution timed out",
            duration_seconds=300.0,
            playbook_path="playbooks/restart.yml",
            target_host="web-01",
        )
        assert result.status == RemediationStatus.TIMEOUT


class TestAuditRecord:
    """Tests for AuditRecord dataclass."""

    def test_creation(self):
        now = datetime.now(timezone.utc)
        record = AuditRecord(
            incident_id="uuid-123",
            alert_name="HighCPU",
            severity="P1",
            affected_host="web-01",
            timestamp_received=now,
            enrichment_data={"hostname": "web-01"},
            matched_playbook="playbooks/restart.yml",
            execution_result="success",
            execution_duration=5.2,
            notification_status="sent",
            output_summary="ok: [web-01]",
        )
        assert record.incident_id == "uuid-123"
        assert record.output_summary == "ok: [web-01]"

    def test_creation_unmatched(self):
        now = datetime.now(timezone.utc)
        record = AuditRecord(
            incident_id="uuid-456",
            alert_name="UnknownAlert",
            severity="P3",
            affected_host="unknown",
            timestamp_received=now,
            enrichment_data=None,
            matched_playbook=None,
            execution_result=None,
            execution_duration=None,
            notification_status="sent",
        )
        assert record.matched_playbook is None
        assert record.execution_result is None
        assert record.output_summary == ""


class TestHealthResponse:
    """Tests for HealthResponse dataclass."""

    def test_healthy(self):
        resp = HealthResponse(
            status="healthy",
            uptime_seconds=3600.0,
            version="0.1.0",
            dependencies={"ansible": "available", "mapping_config": "available"},
        )
        assert resp.status == "healthy"

    def test_degraded(self):
        resp = HealthResponse(
            status="degraded",
            uptime_seconds=100.0,
            version="0.1.0",
            dependencies={"ansible": "unavailable", "mapping_config": "available"},
        )
        assert resp.status == "degraded"


class TestAlertmanagerAlertModel:
    """Tests for Pydantic AlertmanagerAlertModel validation."""

    def test_valid_alert(self):
        alert = AlertmanagerAlertModel(
            status="firing",
            labels={"alertname": "HighCPU", "severity": "critical"},
            annotations={"summary": "CPU high"},
            startsAt="2024-01-01T00:00:00Z",
            endsAt="0001-01-01T00:00:00Z",
        )
        assert alert.status == "firing"
        assert alert.labels["alertname"] == "HighCPU"

    def test_rejects_missing_alertname(self):
        with pytest.raises(ValidationError) as exc_info:
            AlertmanagerAlertModel(
                status="firing",
                labels={"severity": "critical"},
                annotations={},
            )
        assert "alertname" in str(exc_info.value)

    def test_rejects_empty_alertname(self):
        with pytest.raises(ValidationError) as exc_info:
            AlertmanagerAlertModel(
                status="firing",
                labels={"alertname": "", "severity": "critical"},
                annotations={},
            )
        assert "alertname" in str(exc_info.value)

    def test_rejects_missing_severity(self):
        with pytest.raises(ValidationError) as exc_info:
            AlertmanagerAlertModel(
                status="firing",
                labels={"alertname": "Test"},
                annotations={},
            )
        assert "severity" in str(exc_info.value)

    def test_rejects_empty_status(self):
        with pytest.raises(ValidationError) as exc_info:
            AlertmanagerAlertModel(
                status="",
                labels={"alertname": "Test", "severity": "critical"},
                annotations={},
            )
        assert "status" in str(exc_info.value)


class TestAlertmanagerPayloadModel:
    """Tests for Pydantic AlertmanagerPayloadModel validation."""

    def test_valid_payload(self):
        payload = AlertmanagerPayloadModel(
            version="4",
            groupKey="test",
            status="firing",
            receiver="self-healing",
            alerts=[{
                "status": "firing",
                "labels": {"alertname": "HighCPU", "severity": "critical"},
                "annotations": {},
                "startsAt": "2024-01-01T00:00:00Z",
                "endsAt": "",
                "generatorURL": "",
                "fingerprint": "abc",
            }],
        )
        assert len(payload.alerts) == 1

    def test_rejects_empty_alerts(self):
        with pytest.raises(ValidationError) as exc_info:
            AlertmanagerPayloadModel(alerts=[])
        assert "at least 1 item" in str(exc_info.value).lower() or "min_length" in str(exc_info.value).lower()

    def test_accepts_multiple_alerts(self):
        alerts = [
            {
                "status": "firing",
                "labels": {"alertname": f"Alert{i}", "severity": "warning"},
                "annotations": {},
            }
            for i in range(5)
        ]
        payload = AlertmanagerPayloadModel(alerts=alerts)
        assert len(payload.alerts) == 5


class TestHealthResponseModel:
    """Tests for Pydantic HealthResponseModel."""

    def test_valid_response(self):
        resp = HealthResponseModel(
            status="healthy",
            uptime_seconds=3600.0,
            version="0.1.0",
            dependencies={"ansible": "available"},
        )
        assert resp.status == "healthy"


class TestWebhookResponseModel:
    """Tests for Pydantic WebhookResponseModel."""

    def test_default_status(self):
        resp = WebhookResponseModel(alerts_received=3)
        assert resp.status == "accepted"
        assert resp.alerts_received == 3


class TestErrorResponseModel:
    """Tests for Pydantic ErrorResponseModel."""

    def test_with_detail(self):
        err = ErrorResponseModel(error="Bad request", detail="Missing field")
        assert err.error == "Bad request"
        assert err.detail == "Missing field"

    def test_without_detail(self):
        err = ErrorResponseModel(error="Bad request")
        assert err.detail is None
