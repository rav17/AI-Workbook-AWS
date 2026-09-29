"""Property-based tests for the Concurrent Execution Safety module.

Validates correctness properties for deduplication, priority queue,
circuit breaker, and concurrency management.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.concurrency.config import ConcurrencyConfig
from src.concurrency.models import (
    QueueEntry,
)
from src.concurrency.priority_queue import PriorityQueue
from src.concurrency.deduplicator import AlertDeduplicator
from src.guardrails.models import RiskLevel
from src.models import Severity

pytestmark = pytest.mark.property


# --- Property: Priority queue severity ordering ---


@given(
    severities=st.lists(
        st.sampled_from(["P1", "P2", "P3", "P4", "P5"]),
        min_size=2,
        max_size=15,
    )
)
@settings(max_examples=100)
def test_priority_queue_severity_ordering(severities):
    """Priority queue dequeues in severity order (P1 first)."""
    queue = PriorityQueue()
    host = "test-host"

    for i, sev in enumerate(severities):
        entry = QueueEntry(
            incident_id=f"inc-{i}",
            target_host=host,
            action_name="restart",
            severity=Severity(sev),
            enqueued_at=datetime.now(timezone.utc),
            correlation_group="group-1",
        )
        try:
            queue.enqueue(entry)
        except Exception:
            pass  # Queue full or duplicate

    # Dequeue all and verify ordering
    previous_priority = (0, 0.0)  # (severity_rank, timestamp)
    while True:
        entry = queue.dequeue_for_host(host)
        if entry is None:
            break
        current_priority = entry.priority_key()
        assert current_priority >= previous_priority
        previous_priority = current_priority


# --- Property: Deduplicator fingerprint is deterministic ---


@given(
    alert_name=st.text(min_size=1, max_size=50),
    target_host=st.text(min_size=1, max_size=50),
    severity=st.sampled_from(["P1", "P2", "P3"]),
)
@settings(max_examples=100)
def test_deduplicator_fingerprint_deterministic(alert_name, target_host, severity):
    """Deduplicator fingerprint is deterministic for same inputs."""
    config = ConcurrencyConfig()
    lock_store = MagicMock()
    dedup = AlertDeduplicator(lock_store=lock_store, config=config)

    fp1 = dedup.compute_fingerprint(alert_name, target_host, severity)
    fp2 = dedup.compute_fingerprint(alert_name, target_host, severity)

    assert fp1 == fp2
    assert len(fp1) > 0


# --- Property: Priority queue max depth enforcement ---


@given(
    num_entries=st.integers(min_value=1, max_value=30),
)
@settings(max_examples=100)
def test_priority_queue_max_depth(num_entries):
    """Priority queue enforces max depth per host (default 20)."""
    queue = PriorityQueue(max_depth_per_host=20)
    host = "test-host"
    enqueued = 0

    for i in range(num_entries):
        entry = QueueEntry(
            incident_id=f"inc-{i}",
            target_host=host,
            action_name="restart",
            severity=Severity.P2,
            enqueued_at=datetime.now(timezone.utc),
            correlation_group=f"group-{i}",
        )
        try:
            queue.enqueue(entry)
            enqueued += 1
        except Exception:
            break

    assert queue.get_depth(host) <= 20
    assert enqueued <= 20


# --- Property: RiskLevel.elevate() is capped at CRITICAL ---


@given(level=st.sampled_from(list(RiskLevel)))
@settings(max_examples=100)
def test_risk_level_elevate_capped():
    """RiskLevel.elevate() never goes above CRITICAL."""
    for level in RiskLevel:
        elevated = level.elevate()
        assert elevated in list(RiskLevel)
        # Verify CRITICAL stays CRITICAL
        assert RiskLevel.CRITICAL.elevate() == RiskLevel.CRITICAL
