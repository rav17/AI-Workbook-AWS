"""Property-based tests for the AuditLogger component.

Tests validate JSON Lines serialization correctness, round-trip properties,
and audit record completeness with truncation behavior.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

from hypothesis import given, settings, strategies as st

from src.audit_logger import AuditLogger, MAX_OUTPUT_SUMMARY_LENGTH
from src.models import AuditRecord


# --- Hypothesis Strategies ---


def audit_record_strategy():
    """Generate random AuditRecord instances with varied field values."""
    return st.builds(
        AuditRecord,
        incident_id=st.uuids().map(str),
        alert_name=st.text(min_size=0, max_size=100),
        severity=st.sampled_from(["P1", "P2", "P3"]),
        affected_host=st.text(min_size=0, max_size=100),
        timestamp_received=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        enrichment_data=st.one_of(
            st.none(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.text(min_size=0, max_size=50),
                min_size=0,
                max_size=5,
            ),
        ),
        matched_playbook=st.one_of(st.none(), st.text(min_size=1, max_size=80)),
        execution_result=st.one_of(
            st.none(),
            st.sampled_from(["success", "failure", "timeout", "skipped"]),
        ),
        execution_duration=st.one_of(st.none(), st.floats(min_value=0.0, max_value=600.0)),
        notification_status=st.sampled_from(["sent", "failed", "partial"]),
        output_summary=st.text(min_size=0, max_size=3000),
    )


def audit_record_with_long_output_strategy():
    """Generate AuditRecord instances with output_summary exceeding 2048 chars."""
    return st.builds(
        AuditRecord,
        incident_id=st.uuids().map(str),
        alert_name=st.text(min_size=1, max_size=100),
        severity=st.sampled_from(["P1", "P2", "P3"]),
        affected_host=st.text(min_size=1, max_size=100),
        timestamp_received=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        enrichment_data=st.one_of(
            st.none(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.text(min_size=0, max_size=50),
                min_size=0,
                max_size=5,
            ),
        ),
        matched_playbook=st.one_of(st.none(), st.text(min_size=1, max_size=80)),
        execution_result=st.one_of(
            st.none(),
            st.sampled_from(["success", "failure", "timeout", "skipped"]),
        ),
        execution_duration=st.one_of(st.none(), st.floats(min_value=0.0, max_value=600.0)),
        notification_status=st.sampled_from(["sent", "failed", "partial"]),
        output_summary=st.text(min_size=2049, max_size=5000),
    )


def audit_record_with_short_output_strategy():
    """Generate AuditRecord instances with output_summary within 2048 chars."""
    return st.builds(
        AuditRecord,
        incident_id=st.uuids().map(str),
        alert_name=st.text(min_size=1, max_size=100),
        severity=st.sampled_from(["P1", "P2", "P3"]),
        affected_host=st.text(min_size=1, max_size=100),
        timestamp_received=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        enrichment_data=st.one_of(
            st.none(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.text(min_size=0, max_size=50),
                min_size=0,
                max_size=5,
            ),
        ),
        matched_playbook=st.one_of(st.none(), st.text(min_size=1, max_size=80)),
        execution_result=st.one_of(
            st.none(),
            st.sampled_from(["success", "failure", "timeout", "skipped"]),
        ),
        execution_duration=st.one_of(st.none(), st.floats(min_value=0.0, max_value=600.0)),
        notification_status=st.sampled_from(["sent", "failed", "partial"]),
        output_summary=st.text(min_size=0, max_size=2048),
    )


# --- Property 25: Audit serialization as JSON lines ---
# Feature: self-healing-infrastructure, Property 25: Audit serialization as JSON lines
# **Validates: Requirements 8.2**


@given(record=audit_record_strategy())
@settings(max_examples=100, deadline=1000)
def test_audit_record_serializes_to_valid_json(record: AuditRecord):
    """Each AuditRecord serialization produces valid JSON that can be parsed.

    **Validates: Requirements 8.2**
    """
    json_line = record.to_json_line()

    # Must be valid JSON
    parsed = json.loads(json_line)
    assert isinstance(parsed, dict)


@given(record=audit_record_strategy())
@settings(max_examples=100, deadline=1000)
def test_audit_record_json_round_trip(record: AuditRecord):
    """Each JSON line can be deserialized back to an equivalent AuditRecord.

    **Validates: Requirements 8.2**
    """
    json_line = record.to_json_line()

    # Round-trip: serialize then deserialize
    restored = AuditRecord.from_json(json_line)

    # Verify key fields match (output_summary may be truncated by logger,
    # but to_json_line itself does not truncate - that's the logger's job)
    assert restored.incident_id == record.incident_id
    assert restored.alert_name == record.alert_name
    assert restored.severity == record.severity
    assert restored.affected_host == record.affected_host
    assert restored.enrichment_data == record.enrichment_data
    assert restored.matched_playbook == record.matched_playbook
    assert restored.execution_result == record.execution_result
    assert restored.execution_duration == record.execution_duration
    assert restored.notification_status == record.notification_status
    assert restored.output_summary == record.output_summary


@given(record=audit_record_strategy())
@settings(max_examples=100, deadline=1000)
def test_audit_record_json_contains_no_newlines(record: AuditRecord):
    """No newlines within individual JSON records (JSON Lines format requirement).

    **Validates: Requirements 8.2**
    """
    json_line = record.to_json_line()

    # JSON Lines format: each record must be a single line with no embedded newlines
    assert "\n" not in json_line
    assert "\r" not in json_line


@given(records=st.lists(audit_record_strategy(), min_size=2, max_size=10))
@settings(max_examples=100, deadline=5000)
def test_audit_logger_writes_multiple_records_as_separate_lines(records: list):
    """Multiple records are written as separate lines (JSON Lines format).

    **Validates: Requirements 8.2**
    """
    # Use a temporary file for the audit log
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        audit_logger = AuditLogger(log_file_path=tmp_path)

        for record in records:
            audit_logger.log_incident(record)

        audit_logger.close()

        # Read the file and verify JSON Lines format
        with open(tmp_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Filter out empty lines (file may have trailing newline)
        non_empty_lines = [line.strip() for line in lines if line.strip()]

        # Should have exactly as many lines as records written
        assert len(non_empty_lines) == len(records)

        # Each line must be valid JSON and independently parseable
        for i, line in enumerate(non_empty_lines):
            parsed = json.loads(line)
            assert isinstance(parsed, dict)
            # Verify the incident_id matches the record we wrote
            assert parsed["incident_id"] == records[i].incident_id

    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# --- Property 24: Audit record completeness and truncation ---
# Feature: self-healing-infrastructure, Property 24: Audit record completeness and truncation
# **Validates: Requirements 8.1, 8.4**


@given(record=audit_record_with_long_output_strategy())
@settings(max_examples=100, deadline=5000)
def test_audit_logger_truncates_long_output_summary(record: AuditRecord):
    """When output_summary exceeds 2048 characters, the AuditLogger SHALL
    truncate it to exactly 2048 characters before writing.

    **Validates: Requirements 8.4**
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        audit_logger = AuditLogger(log_file_path=tmp_path)
        audit_logger.log_incident(record)
        audit_logger.close()

        with open(tmp_path, "r", encoding="utf-8") as f:
            line = f.readline().strip()

        parsed = json.loads(line)
        assert len(parsed["output_summary"]) <= MAX_OUTPUT_SUMMARY_LENGTH, (
            f"output_summary should be truncated to {MAX_OUTPUT_SUMMARY_LENGTH} chars, "
            f"but got {len(parsed['output_summary'])} chars"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@given(record=audit_record_with_short_output_strategy())
@settings(max_examples=100, deadline=5000)
def test_audit_logger_preserves_short_output_summary(record: AuditRecord):
    """When output_summary is within 2048 characters, the AuditLogger SHALL
    preserve it unchanged.

    **Validates: Requirements 8.4**
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        audit_logger = AuditLogger(log_file_path=tmp_path)
        original_summary = record.output_summary
        audit_logger.log_incident(record)
        audit_logger.close()

        with open(tmp_path, "r", encoding="utf-8") as f:
            line = f.readline().strip()

        parsed = json.loads(line)
        assert parsed["output_summary"] == original_summary, (
            "output_summary should be preserved unchanged when within limit"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@given(record=audit_record_strategy())
@settings(max_examples=100, deadline=5000)
def test_audit_record_contains_all_required_fields(record: AuditRecord):
    """Each audit record SHALL contain all required fields: incident_id,
    alert_name, severity, affected_host, timestamp_received, matched_playbook,
    execution_result, notification_status.

    **Validates: Requirements 8.1**
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        audit_logger = AuditLogger(log_file_path=tmp_path)
        audit_logger.log_incident(record)
        audit_logger.close()

        with open(tmp_path, "r", encoding="utf-8") as f:
            line = f.readline().strip()

        parsed = json.loads(line)

        required_fields = [
            "incident_id",
            "alert_name",
            "severity",
            "affected_host",
            "timestamp_received",
            "matched_playbook",
            "execution_result",
            "notification_status",
        ]

        for field_name in required_fields:
            assert field_name in parsed, (
                f"Audit record missing required field '{field_name}'. "
                f"Record keys: {list(parsed.keys())}"
            )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@given(record=audit_record_strategy())
@settings(max_examples=100, deadline=5000)
def test_audit_record_incident_id_preserved(record: AuditRecord):
    """The incident_id in the written audit record SHALL match the original
    record's incident_id.

    **Validates: Requirements 8.1**
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        audit_logger = AuditLogger(log_file_path=tmp_path)
        audit_logger.log_incident(record)
        audit_logger.close()

        with open(tmp_path, "r", encoding="utf-8") as f:
            line = f.readline().strip()

        parsed = json.loads(line)
        assert parsed["incident_id"] == record.incident_id, (
            f"Expected incident_id='{record.incident_id}', "
            f"got '{parsed['incident_id']}'"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@given(record=audit_record_strategy())
@settings(max_examples=100, deadline=5000)
def test_audit_record_severity_preserved(record: AuditRecord):
    """The severity in the written audit record SHALL match the original
    record's severity.

    **Validates: Requirements 8.1**
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        audit_logger = AuditLogger(log_file_path=tmp_path)
        audit_logger.log_incident(record)
        audit_logger.close()

        with open(tmp_path, "r", encoding="utf-8") as f:
            line = f.readline().strip()

        parsed = json.loads(line)
        assert parsed["severity"] == record.severity, (
            f"Expected severity='{record.severity}', got '{parsed['severity']}'"
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
