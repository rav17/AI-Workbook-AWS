"""Unit tests for the Normalizer component."""

import uuid
from datetime import datetime, timezone

import pytest

from src.models import (
    AlertmanagerAlert,
    AlertmanagerPayload,
    AlertStatus,
    Severity,
)
from src.normalizer import Normalizer


@pytest.fixture
def normalizer():
    """Create a Normalizer instance."""
    return Normalizer()


@pytest.fixture
def valid_alert():
    """Create a valid AlertmanagerAlert."""
    return AlertmanagerAlert(
        status="firing",
        labels={"alertname": "HighCPUUsage", "severity": "critical", "instance": "web-01:9090"},
        annotations={"summary": "CPU is high"},
        starts_at="2024-01-15T10:30:00Z",
        ends_at="0001-01-01T00:00:00Z",
        generator_url="http://prometheus:9090/graph",
        fingerprint="abc123",
    )


@pytest.fixture
def valid_payload(valid_alert):
    """Create a valid AlertmanagerPayload."""
    return AlertmanagerPayload(
        version="4",
        group_key="test-group",
        status="firing",
        receiver="self-healing",
        alerts=[valid_alert],
    )


class TestNormalizerSeverityMapping:
    """Tests for severity mapping: critical→P1, warning→P2, info→P3."""

    def test_critical_maps_to_p1(self, normalizer, valid_payload):
        valid_payload.alerts[0].labels["severity"] = "critical"
        result = normalizer.normalize(valid_payload)
        assert result[0].severity == Severity.P1

    def test_warning_maps_to_p2(self, normalizer, valid_payload):
        valid_payload.alerts[0].labels["severity"] = "warning"
        result = normalizer.normalize(valid_payload)
        assert result[0].severity == Severity.P2

    def test_info_maps_to_p3(self, normalizer, valid_payload):
        valid_payload.alerts[0].labels["severity"] = "info"
        result = normalizer.normalize(valid_payload)
        assert result[0].severity == Severity.P3

    def test_unknown_severity_defaults_to_p3(self, normalizer, valid_payload):
        valid_payload.alerts[0].labels["severity"] = "unknown_value"
        result = normalizer.normalize(valid_payload)
        assert result[0].severity == Severity.P3

    def test_empty_severity_defaults_to_p3(self, normalizer, valid_payload):
        valid_payload.alerts[0].labels["severity"] = ""
        result = normalizer.normalize(valid_payload)
        assert result[0].severity == Severity.P3

    def test_missing_severity_key_defaults_to_p3(self, normalizer, valid_payload):
        del valid_payload.alerts[0].labels["severity"]
        result = normalizer.normalize(valid_payload)
        assert result[0].severity == Severity.P3


class TestNormalizerFieldExtraction:
    """Tests for field extraction from alerts."""

    def test_extracts_alert_name(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        assert result[0].alert_name == "HighCPUUsage"

    def test_extracts_labels(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        assert result[0].labels == valid_payload.alerts[0].labels

    def test_extracts_annotations(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        assert result[0].annotations == valid_payload.alerts[0].annotations

    def test_extracts_status_firing(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        assert result[0].status == AlertStatus.FIRING

    def test_extracts_status_resolved(self, normalizer, valid_payload):
        valid_payload.alerts[0].status = "resolved"
        result = normalizer.normalize(valid_payload)
        assert result[0].status == AlertStatus.RESOLVED

    def test_extracts_starts_at(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        expected = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert result[0].starts_at == expected

    def test_ends_at_zero_value_returns_none(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        assert result[0].ends_at is None

    def test_ends_at_valid_timestamp(self, normalizer, valid_payload):
        valid_payload.alerts[0].ends_at = "2024-01-15T11:00:00Z"
        result = normalizer.normalize(valid_payload)
        expected = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        assert result[0].ends_at == expected

    def test_extracts_fingerprint(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        assert result[0].raw_fingerprint == "abc123"


class TestNormalizerDefaults:
    """Tests for default value assignment when fields are missing."""

    def test_missing_alert_name_defaults_to_empty_string(self, normalizer, valid_payload):
        del valid_payload.alerts[0].labels["alertname"]
        result = normalizer.normalize(valid_payload)
        assert result[0].alert_name == ""

    def test_missing_status_defaults_to_firing(self, normalizer, valid_payload):
        valid_payload.alerts[0].status = ""
        result = normalizer.normalize(valid_payload)
        assert result[0].status == AlertStatus.FIRING

    def test_missing_starts_at_defaults_to_current_time(self, normalizer, valid_payload):
        valid_payload.alerts[0].starts_at = ""
        before = datetime.now(timezone.utc)
        result = normalizer.normalize(valid_payload)
        after = datetime.now(timezone.utc)
        assert before <= result[0].starts_at <= after

    def test_invalid_starts_at_defaults_to_current_time(self, normalizer, valid_payload):
        valid_payload.alerts[0].starts_at = "not-a-timestamp"
        before = datetime.now(timezone.utc)
        result = normalizer.normalize(valid_payload)
        after = datetime.now(timezone.utc)
        assert before <= result[0].starts_at <= after


class TestNormalizerAlertCount:
    """Tests for alert count preservation."""

    def test_single_alert_produces_one_normalized(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        assert len(result) == 1

    def test_multiple_alerts_produce_same_count(self, normalizer, valid_alert):
        payload = AlertmanagerPayload(
            version="4",
            group_key="test-group",
            status="firing",
            receiver="self-healing",
            alerts=[valid_alert, valid_alert, valid_alert],
        )
        result = normalizer.normalize(payload)
        assert len(result) == 3


class TestNormalizerIncidentId:
    """Tests for UUID-based incident ID generation."""

    def test_generates_valid_uuid(self, normalizer, valid_payload):
        result = normalizer.normalize(valid_payload)
        # Should not raise ValueError
        uuid.UUID(result[0].incident_id)

    def test_generates_unique_ids_per_alert(self, normalizer, valid_alert):
        payload = AlertmanagerPayload(
            version="4",
            group_key="test-group",
            status="firing",
            receiver="self-healing",
            alerts=[valid_alert, valid_alert],
        )
        result = normalizer.normalize(payload)
        assert result[0].incident_id != result[1].incident_id
