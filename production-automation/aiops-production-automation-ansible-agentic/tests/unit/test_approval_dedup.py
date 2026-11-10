"""Unit tests for duplicate approval suppression.

Regression test for the dev end-to-end finding: a direct HighCPUUsage alert and
the CloudWatch alarm for the same CPU spike produced two approval emails.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from src.approval_handler import ApprovalHandler
from src.stores.approval_store import DynamoApprovalStore

pytestmark = pytest.mark.unit


def _create(handler: ApprovalHandler, incident_id: str, host: str = "i-0abc", alert="HighCPUUsage"):
    return handler.create_approval(
        incident_id=incident_id,
        alert_name=alert,
        severity="critical",
        affected_host=host,
        service_name="web-frontend",
        root_cause="CPU above 80%",
        proposed_action=f"Execute playbooks/fix_high_cpu.yml on {host}",
        playbook_path="playbooks/fix_high_cpu.yml",
    )


def _conditional_failed() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
        "PutItem",
    )


@pytest.fixture
def memory_handler(monkeypatch) -> ApprovalHandler:
    """Handler with no DynamoDB table (in-memory fallback path)."""
    monkeypatch.delenv("DYNAMODB_TABLE_NAME", raising=False)
    return ApprovalHandler(base_url="http://test", dynamodb_table_name="")


class TestInMemoryDedup:
    def test_second_identical_approval_is_suppressed(self, memory_handler) -> None:
        first = _create(memory_handler, "inc-1")
        second = _create(memory_handler, "inc-2")

        assert first is not None
        assert second is None

    def test_different_host_is_not_a_duplicate(self, memory_handler) -> None:
        assert _create(memory_handler, "inc-1", host="i-0abc") is not None
        assert _create(memory_handler, "inc-2", host="i-0def") is not None

    def test_different_alert_is_not_a_duplicate(self, memory_handler) -> None:
        assert _create(memory_handler, "inc-1", alert="HighCPUUsage") is not None
        assert _create(memory_handler, "inc-2", alert="DiskSpaceLow") is not None

    def test_consuming_releases_lock_for_a_new_occurrence(self, memory_handler) -> None:
        first = _create(memory_handler, "inc-1")
        assert memory_handler.validate_and_consume(first.token) is not None

        # The problem recurs after the fix: it must be able to ask again.
        assert _create(memory_handler, "inc-2") is not None

    def test_expired_lock_allows_new_approval(self, memory_handler) -> None:
        first = _create(memory_handler, "inc-1")
        key = first.dedup_key
        token, _ = memory_handler._memory_dedup[key]
        memory_handler._memory_dedup[key] = (token, time.time() - 1)  # force expiry

        assert _create(memory_handler, "inc-2") is not None


class TestDynamoDedup:
    def _handler_with_table(self, monkeypatch, table: MagicMock) -> ApprovalHandler:
        monkeypatch.delenv("DYNAMODB_TABLE_NAME", raising=False)
        handler = ApprovalHandler(base_url="http://test", dynamodb_table_name="")
        resource = MagicMock()
        resource.Table.return_value = table
        handler._store = DynamoApprovalStore(table_name="t", dynamodb_resource=resource)
        return handler

    def test_conditional_failure_suppresses_and_sends_nothing(self, monkeypatch) -> None:
        table = MagicMock()
        # 1st put = dedup lock claim (conditional failure => duplicate)
        table.put_item.side_effect = [_conditional_failed()]
        handler = self._handler_with_table(monkeypatch, table)

        assert _create(handler, "inc-2") is None
        # Only the lock claim was attempted; no approval item was written.
        assert table.put_item.call_count == 1
        lock_item = table.put_item.call_args.kwargs["Item"]
        assert lock_item["incident_id"].startswith("APPROVAL_DEDUP#")
        assert "attribute_not_exists" in table.put_item.call_args.kwargs["ConditionExpression"]

    def test_successful_claim_writes_lock_then_approval(self, monkeypatch) -> None:
        table = MagicMock()
        handler = self._handler_with_table(monkeypatch, table)

        approval = _create(handler, "inc-1")

        assert approval is not None
        assert table.put_item.call_count == 2
        approval_item = table.put_item.call_args_list[1].kwargs["Item"]
        assert approval_item["dedup_key"] == approval.dedup_key

    def test_dynamodb_error_fails_open(self, monkeypatch) -> None:
        """A DynamoDB outage must not suppress approval requests."""
        table = MagicMock()
        throttled = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "x"}},
            "PutItem",
        )
        table.put_item.side_effect = [throttled, None]
        handler = self._handler_with_table(monkeypatch, table)

        assert _create(handler, "inc-1") is not None

    def test_consume_releases_lock_owned_by_token(self, monkeypatch) -> None:
        table = MagicMock()
        handler = self._handler_with_table(monkeypatch, table)
        approval = _create(handler, "inc-1")

        assert handler.validate_and_consume(approval.token) is not None

        table.delete_item.assert_called_once()
        kwargs = table.delete_item.call_args.kwargs
        assert kwargs["Key"]["incident_id"] == f"APPROVAL_DEDUP#{approval.dedup_key}"
        assert kwargs["ExpressionAttributeValues"][":token"] == approval.token
