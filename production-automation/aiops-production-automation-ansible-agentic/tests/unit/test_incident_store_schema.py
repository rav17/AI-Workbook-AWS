"""Unit tests for IncidentMemoryStore against the real AiopsIncidentMemory key schema."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import EndpointConnectionError

from src.agentic_ai.models.domain import IncidentRecord
from src.agentic_ai.models.incident_store import (
    INCIDENT_SK_PREFIX,
    OUTCOME_PENDING,
    IncidentMemoryStore,
)
from tests.unit.fake_dynamodb import FakeDynamoDBClient

pytestmark = pytest.mark.unit

TABLE = "AiopsIncidentMemory-test"


def _record(
    incident_id: str,
    *,
    alert: str = "NetworkFloodDetected",
    service: str = "web-frontend",
    resource: str = "i-0aaa",
    outcome: str = OUTCOME_PENDING,
    when: datetime | None = None,
) -> IncidentRecord:
    return IncidentRecord(
        incident_id=incident_id,
        alert_name=alert,
        severity="critical",
        affected_service=service,
        affected_resource=resource,
        remediation_action="investigate",
        outcome=outcome,
        execution_duration_seconds=0.0,
        timestamp_completed=when or datetime.now(timezone.utc),
        expiry_timestamp=0,
    )


@pytest.fixture
def fake() -> FakeDynamoDBClient:
    return FakeDynamoDBClient(TABLE)


@pytest.fixture
def store(fake: FakeDynamoDBClient) -> IncidentMemoryStore:
    return IncidentMemoryStore(table_name=TABLE, dynamodb_client=fake)


def test_record_incident_uses_table_key_schema(store, fake) -> None:
    """Items carry the table's sort key and the ServiceIndex key."""
    assert store.record_incident(_record("inc-1"))
    (pk, sk), item = next(iter(fake.items.items()))
    assert pk == "inc-1"
    assert sk.startswith(INCIDENT_SK_PREFIX)
    assert item["service_name"] == {"S": "web-frontend"}
    assert item["outcome"] == {"S": OUTCOME_PENDING}
    assert int(item["expiry_timestamp"]["N"]) > 0


def test_empty_service_name_does_not_break_index_write(store, fake) -> None:
    """An empty GSI key is rejected by DynamoDB; the store substitutes a placeholder."""
    assert store.record_incident(_record("inc-2", service=""))
    item = fake.items[next(iter(fake.items))]
    assert item["service_name"] == {"S": "unknown"}


def test_query_history_by_alert_excludes_approval_items(store, fake) -> None:
    """Approval items share alert_name and the table; they must not count as history."""
    store.record_incident(_record("inc-a"))
    fake.put_item(
        TableName=TABLE,
        Item={
            "incident_id": {"S": "inc-b"},
            "timestamp": {"S": "APPROVAL#tok123"},
            "alert_name": {"S": "NetworkFloodDetected"},
        },
    )
    history = store.query_history(alert_name="NetworkFloodDetected")
    assert [r.incident_id for r in history] == ["inc-a"]


def test_query_history_newest_first_and_by_service(store) -> None:
    now = datetime.now(timezone.utc)
    store.record_incident(_record("old", when=now - timedelta(hours=2)))
    store.record_incident(_record("new", when=now))
    store.record_incident(_record("other", alert="DiskSpaceLow", service="db"))
    assert [
        r.incident_id for r in store.query_history(alert_name="NetworkFloodDetected")
    ] == [
        "new",
        "old",
    ]
    assert [r.incident_id for r in store.query_history(service="db")] == ["other"]


def test_record_outcome_updates_existing_item(store, fake) -> None:
    store.record_incident(_record("inc-3"))
    assert store.record_outcome("inc-3", "success", 1.5, source="human_feedback")
    assert len(fake.items) == 1  # updated in place, no stray item
    record = store.get_incident("inc-3")
    assert record is not None
    assert record.outcome == "success"
    item = fake.items[next(iter(fake.items))]
    assert item["outcome_source"] == {"S": "human_feedback"}


def test_record_outcome_only_if_pending_first_answer_wins(store) -> None:
    store.record_incident(_record("inc-4"))
    assert store.record_outcome("inc-4", "success", 0.0, only_if_pending=True)
    assert not store.record_outcome("inc-4", "failure", 0.0, only_if_pending=True)
    assert store.get_incident("inc-4").outcome == "success"


def test_record_outcome_for_unknown_incident_does_not_create_item(store, fake) -> None:
    assert not store.record_outcome("missing", "success", 0.0)
    assert fake.items == {}


def test_record_resolution_marks_newest_matching_resource_only(store, fake) -> None:
    now = datetime.now(timezone.utc)
    store.record_incident(
        _record("older", resource="i-0aaa", when=now - timedelta(minutes=10))
    )
    store.record_incident(_record("newer", resource="i-0aaa", when=now))
    store.record_incident(_record("elsewhere", resource="i-0bbb", when=now))

    assert (
        store.record_resolution_for_alert("NetworkFloodDetected", "i-0aaa") == "newer"
    )
    assert (
        store.record_resolution_for_alert("NetworkFloodDetected", "i-0aaa") == "older"
    )
    assert store.record_resolution_for_alert("NetworkFloodDetected", "i-0aaa") is None

    by_id = {item["incident_id"]["S"]: item for item in fake.items.values()}
    assert by_id["newer"]["resolution_status"] == {"S": "resolved"}
    assert "resolution_status" not in by_id["elsewhere"]
    # Resolution is informational: the outcome the router counts is untouched.
    assert by_id["newer"]["outcome"] == {"S": OUTCOME_PENDING}


def test_record_resolution_ignores_incidents_older_than_max_age(store) -> None:
    old = datetime.now(timezone.utc) - timedelta(hours=7)
    store.record_incident(_record("stale", when=old))
    assert store.record_resolution_for_alert("NetworkFloodDetected", "i-0aaa") is None


def test_store_degrades_gracefully_when_unreachable() -> None:
    client = MagicMock()
    error = EndpointConnectionError(endpoint_url="https://dynamodb")
    client.query.side_effect = error
    client.put_item.side_effect = error
    store = IncidentMemoryStore(table_name=TABLE, dynamodb_client=client)
    assert store.query_history(alert_name="X") == []
    assert store.record_incident(_record("inc-x")) is False
    assert store.record_outcome("inc-x", "success", 0.0) is False
    assert store.record_resolution_for_alert("X", "i-0") is None
    assert store.get_incident("inc-x") is None
