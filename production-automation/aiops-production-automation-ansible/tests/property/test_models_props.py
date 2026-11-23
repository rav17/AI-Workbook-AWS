# Feature: self-healing-infrastructure, Property 25: Audit serialization as JSON lines
"""Property-based tests for data model serialization.

Property 25: Audit serialization as JSON lines
*For any* AuditRecord, serialization SHALL produce a single line of valid JSON
that can be deserialized back to an equivalent record (round-trip property).

**Validates: Requirements 8.2**
"""

import json
from datetime import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import AuditRecord


# --- Hypothesis Strategies ---

# Strategy for generating random enrichment data dictionaries
enrichment_data_strategy = st.one_of(
    st.none(),
    st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))),
        values=st.one_of(
            st.text(max_size=50, alphabet=st.characters(blacklist_categories=("Cs",))),
            st.integers(min_value=-1000, max_value=1000),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.none(),
        ),
        max_size=5,
    ),
)

# Strategy for generating random AuditRecord instances
audit_record_strategy = st.builds(
    AuditRecord,
    incident_id=st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=("Cs",))),
    alert_name=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",))),
    severity=st.sampled_from(["P1", "P2", "P3", "critical", "warning", "info"]),
    affected_host=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",))),
    timestamp_received=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2030, 12, 31),
    ),
    enrichment_data=enrichment_data_strategy,
    matched_playbook=st.one_of(st.none(), st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",)))),
    execution_result=st.one_of(st.none(), st.sampled_from(["success", "failure", "timeout", "skipped"])),
    execution_duration=st.one_of(st.none(), st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False)),
    notification_status=st.sampled_from(["sent", "failed", "partial", "skipped"]),
    output_summary=st.text(min_size=0, max_size=200, alphabet=st.characters(blacklist_categories=("Cs",))),
)


class TestAuditRecordSerialization:
    """Property tests for AuditRecord JSON serialization (Property 25)."""

    @given(record=audit_record_strategy)
    @settings(max_examples=100)
    def test_serialization_produces_valid_json(self, record: AuditRecord) -> None:
        """For any AuditRecord, serialization SHALL produce valid JSON.

        Validates: Requirements 8.2
        """
        json_line = record.to_json_line()

        # The output must be parseable by a standard JSON parser
        parsed = json.loads(json_line)
        assert isinstance(parsed, dict)

    @given(record=audit_record_strategy)
    @settings(max_examples=100)
    def test_serialization_produces_single_line(self, record: AuditRecord) -> None:
        """For any AuditRecord, serialization SHALL produce a single line (no embedded newlines).

        Validates: Requirements 8.2
        """
        json_line = record.to_json_line()

        # The JSON output must not contain newline characters
        assert "\n" not in json_line, f"JSON output contains newline: {json_line!r}"
        assert "\r" not in json_line, f"JSON output contains carriage return: {json_line!r}"

    @given(record=audit_record_strategy)
    @settings(max_examples=100)
    def test_serialization_round_trip(self, record: AuditRecord) -> None:
        """For any AuditRecord, deserialization of serialized output SHALL produce an equivalent record.

        Validates: Requirements 8.2
        """
        json_line = record.to_json_line()

        # Deserialize back to an AuditRecord
        restored = AuditRecord.from_json(json_line)

        # All fields must match the original record
        assert restored.incident_id == record.incident_id
        assert restored.alert_name == record.alert_name
        assert restored.severity == record.severity
        assert restored.affected_host == record.affected_host
        assert restored.timestamp_received == record.timestamp_received
        assert restored.enrichment_data == record.enrichment_data
        assert restored.matched_playbook == record.matched_playbook
        assert restored.execution_result == record.execution_result
        assert restored.execution_duration == record.execution_duration
        assert restored.notification_status == record.notification_status
        assert restored.output_summary == record.output_summary
