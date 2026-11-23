"""Unit tests for DynamoDBShortTermMemory (memory/dynamodb_manager.py).

Tests use an in-memory stub for the DynamoDB table so no real AWS calls are made.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from config.models import InteractionRecord, PruneEvent
from config.settings import MemoryConfig
from memory.dynamodb_manager import DynamoDBShortTermMemory


# ---------------------------------------------------------------------------
# Helpers – lightweight DynamoDB table stub
# ---------------------------------------------------------------------------

class _StubTable:
    """Minimal in-memory replacement for a boto3 DynamoDB Table resource."""

    def __init__(self):
        self._items: list[dict] = []

    def put_item(self, *, Item: dict) -> None:
        self._items.append(Item)

    def delete_item(self, *, Key: dict) -> None:
        self._items = [
            i for i in self._items
            if not (i["user_id"] == Key["user_id"] and i["timestamp"] == Key["timestamp"])
        ]

    def query(self, **kwargs) -> dict:
        # Extract user_id from the KeyConditionExpression
        # The real boto3 Key().eq() produces a ConditionBase; we inspect
        # the expression dict to pull out the value.
        kce = kwargs["KeyConditionExpression"]
        expr = kce.get_expression()
        # expr looks like {'format': '{0} {operator} {1}', 'operator': '=',
        #                   'values': (AttributePath, value)}
        user_id = expr["values"][1]

        forward = kwargs.get("ScanIndexForward", True)
        limit = kwargs.get("Limit", 100)

        matched = [i for i in self._items if i["user_id"] == user_id]
        matched.sort(key=lambda x: x["timestamp"], reverse=not forward)
        return {"Items": matched[:limit]}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_memory(max_interactions: int = 20) -> DynamoDBShortTermMemory:
    """Create a DynamoDBShortTermMemory backed by the in-memory stub."""
    config = MemoryConfig(agent_id="test-agent", max_interactions=max_interactions)
    mem = object.__new__(DynamoDBShortTermMemory)
    mem.max_interactions = config.max_interactions
    mem.table_name = "test_table"
    mem.table = _StubTable()
    mem.dynamodb = None
    return mem


def _record(
    user_id: str = "u1",
    inp: str = "hello",
    out: str = "world",
    status: str = "success",
    confidence: str = "high",
    ts_offset_seconds: int = 0,
) -> InteractionRecord:
    ts = (datetime(2025, 1, 1) + timedelta(seconds=ts_offset_seconds)).isoformat()
    return InteractionRecord(
        user_id=user_id,
        timestamp=ts,
        input=inp,
        output=out,
        status=status,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Tests – store_interaction
# ---------------------------------------------------------------------------

class TestStoreInteraction:
    def test_stores_record(self):
        mem = _make_memory()
        rec = _record()
        mem.store_interaction("u1", rec)
        result = mem.retrieve_interactions("u1")
        assert len(result) == 1
        assert result[0].input == "hello"

    def test_skips_duplicate(self):
        mem = _make_memory()
        rec1 = _record(ts_offset_seconds=-10)
        rec2 = _record(ts_offset_seconds=0)  # same input/output
        mem.store_interaction("u1", rec1)
        mem.store_interaction("u1", rec2)
        # deduplicate removes the old one, new one replaces it
        result = mem.retrieve_interactions("u1")
        assert len(result) == 1
        assert result[0].timestamp == rec2.timestamp


# ---------------------------------------------------------------------------
# Tests – retrieve_interactions
# ---------------------------------------------------------------------------

class TestRetrieveInteractions:
    def test_returns_newest_first(self):
        mem = _make_memory()
        for i in range(5):
            rec = _record(inp=f"q{i}", out=f"a{i}", ts_offset_seconds=i)
            mem.table.put_item(Item=rec.model_dump())
        result = mem.retrieve_interactions("u1")
        timestamps = [r.timestamp for r in result]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_respects_limit(self):
        mem = _make_memory()
        for i in range(10):
            rec = _record(inp=f"q{i}", out=f"a{i}", ts_offset_seconds=i)
            mem.table.put_item(Item=rec.model_dump())
        result = mem.retrieve_interactions("u1", limit=3)
        assert len(result) == 3

    def test_empty_for_unknown_user(self):
        mem = _make_memory()
        assert mem.retrieve_interactions("unknown") == []


# ---------------------------------------------------------------------------
# Tests – get_failures
# ---------------------------------------------------------------------------

class TestGetFailures:
    def test_returns_only_failures(self):
        mem = _make_memory()
        mem.table.put_item(Item=_record(status="success", ts_offset_seconds=0).model_dump())
        mem.table.put_item(Item=_record(status="failure", inp="f1", ts_offset_seconds=1).model_dump())
        mem.table.put_item(Item=_record(status="failure", inp="f2", ts_offset_seconds=2).model_dump())
        failures = mem.get_failures("u1")
        assert len(failures) == 2
        assert all(f.status == "failure" for f in failures)

    def test_limit_caps_results(self):
        mem = _make_memory()
        for i in range(5):
            mem.table.put_item(
                Item=_record(status="failure", inp=f"f{i}", ts_offset_seconds=i).model_dump()
            )
        assert len(mem.get_failures("u1", limit=2)) == 2

    def test_no_limit_returns_all(self):
        mem = _make_memory()
        for i in range(3):
            mem.table.put_item(
                Item=_record(status="failure", inp=f"f{i}", ts_offset_seconds=i).model_dump()
            )
        assert len(mem.get_failures("u1")) == 3


# ---------------------------------------------------------------------------
# Tests – prune
# ---------------------------------------------------------------------------

class TestPrune:
    def test_no_prune_when_under_limit(self):
        mem = _make_memory(max_interactions=5)
        for i in range(3):
            mem.table.put_item(Item=_record(inp=f"q{i}", out=f"a{i}", ts_offset_seconds=i).model_dump())
        events = mem.prune("u1")
        assert events == []
        assert len(mem.retrieve_interactions("u1")) == 3

    def test_prunes_oldest_non_failure_first(self):
        mem = _make_memory(max_interactions=3)
        mem.table.put_item(Item=_record(inp="old_success", out="a", status="success", ts_offset_seconds=0).model_dump())
        mem.table.put_item(Item=_record(inp="failure_rec", out="b", status="failure", ts_offset_seconds=1).model_dump())
        mem.table.put_item(Item=_record(inp="mid_success", out="c", status="success", ts_offset_seconds=2).model_dump())
        mem.table.put_item(Item=_record(inp="new_success", out="d", status="success", ts_offset_seconds=3).model_dump())

        events = mem.prune("u1")
        assert len(events) == 1
        remaining = mem.retrieve_interactions("u1")
        assert len(remaining) == 3
        remaining_inputs = {r.input for r in remaining}
        assert "old_success" not in remaining_inputs
        assert "failure_rec" in remaining_inputs

    def test_prunes_high_confidence_before_low(self):
        """R9.4: low-confidence records are retained longer than high-confidence."""
        mem = _make_memory(max_interactions=2)
        mem.table.put_item(Item=_record(inp="low_conf", out="a", confidence="low", ts_offset_seconds=0).model_dump())
        mem.table.put_item(Item=_record(inp="high_conf", out="b", confidence="high", ts_offset_seconds=1).model_dump())
        mem.table.put_item(Item=_record(inp="newest", out="c", confidence="high", ts_offset_seconds=2).model_dump())

        events = mem.prune("u1")
        assert len(events) == 1
        remaining = mem.retrieve_interactions("u1")
        remaining_inputs = {r.input for r in remaining}
        assert "high_conf" not in remaining_inputs
        assert "low_conf" in remaining_inputs

    def test_prune_returns_prune_events(self):
        mem = _make_memory(max_interactions=1)
        mem.table.put_item(Item=_record(inp="a", out="1", ts_offset_seconds=0).model_dump())
        mem.table.put_item(Item=_record(inp="b", out="2", ts_offset_seconds=1).model_dump())
        events = mem.prune("u1")
        assert len(events) == 1
        assert isinstance(events[0], PruneEvent)
        assert events[0].user_id == "u1"
        assert events[0].reason == "exceeded_max_interactions"

    def test_failures_never_pruned(self):
        """Even when all records are failures, none should be pruned."""
        mem = _make_memory(max_interactions=2)
        for i in range(4):
            mem.table.put_item(
                Item=_record(inp=f"f{i}", out=f"o{i}", status="failure", ts_offset_seconds=i).model_dump()
            )
        events = mem.prune("u1")
        assert events == []
        assert len(mem.retrieve_interactions("u1", limit=10)) == 4


# ---------------------------------------------------------------------------
# Tests – deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def test_detects_duplicate(self):
        mem = _make_memory()
        existing = _record(inp="same", out="same", ts_offset_seconds=-5)
        mem.table.put_item(Item=existing.model_dump())
        new_rec = _record(inp="same", out="same", ts_offset_seconds=0)
        assert mem.deduplicate("u1", new_rec) is True
        assert len(mem.retrieve_interactions("u1")) == 0

    def test_no_duplicate_different_input(self):
        mem = _make_memory()
        existing = _record(inp="a", out="same", ts_offset_seconds=-5)
        mem.table.put_item(Item=existing.model_dump())
        new_rec = _record(inp="b", out="same", ts_offset_seconds=0)
        assert mem.deduplicate("u1", new_rec) is False

    def test_no_duplicate_different_output(self):
        mem = _make_memory()
        existing = _record(inp="same", out="x", ts_offset_seconds=-5)
        mem.table.put_item(Item=existing.model_dump())
        new_rec = _record(inp="same", out="y", ts_offset_seconds=0)
        assert mem.deduplicate("u1", new_rec) is False

    def test_no_duplicate_empty_table(self):
        mem = _make_memory()
        new_rec = _record(inp="hello", out="world")
        assert mem.deduplicate("u1", new_rec) is False
