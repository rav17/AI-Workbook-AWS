"""DynamoDB-backed deferred actions store.

Persists guardrail-deferred remediation actions to DynamoDB so they
survive ECS task restarts, deployments, and spot interruptions.

Actions are deferred when guardrail engine returns DEFER (e.g.,
maintenance window active, concurrency slot full). They are
re-evaluated periodically by any task in the fleet.

Storage pattern:
- PK: incident_id
- SK: "DEFERRED#{incident_id}" (one deferred action per incident)
- TTL: auto-expires after max deferral window (1 hour)
- GSI (OutcomeIndex): outcome="DEFERRED" enables listing all pending items

Design decisions:
- Uses the existing AiopsIncidentMemory table
- Serializes alert/playbook data as JSON strings (DynamoDB-safe)
- Conditional writes prevent duplicate deferrals
- Re-evaluation uses query on outcome="DEFERRED" via OutcomeIndex GSI
- Atomic state transitions: DEFERRED → ALLOWED / DENIED / EXPIRED
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# Maximum deferral time before auto-expiry (seconds)
MAX_DEFER_AGE_SECONDS = 3600  # 1 hour

# Maximum items to process per re-evaluation cycle
MAX_REEVALUATE_BATCH = 25


@dataclass
class DeferredAction:
    """A guardrail-deferred remediation action persisted in DynamoDB.

    Attributes:
        incident_id: Unique incident identifier.
        alert_name: Name of the triggering alert.
        severity: Alert severity value.
        target_host: Target host for remediation.
        service_name: Affected service name.
        playbook_path: Path to matched playbook.
        rule_name: Name of the matched mapping rule.
        alert_data: Serialized NormalizedAlert for re-execution.
        enriched_alert_data: Serialized EnrichedAlert for re-execution.
        playbook_match_data: Serialized PlaybookMatch for re-execution.
        deferred_at: Unix timestamp when deferred.
        reason: Human-readable reason for deferral.
        re_evaluate_on: Event type that should trigger re-evaluation.
        status: Current status (DEFERRED, ALLOWED, DENIED, EXPIRED).
    """

    incident_id: str
    alert_name: str
    severity: str
    target_host: str
    service_name: str
    playbook_path: str
    rule_name: str
    alert_data: str  # JSON-serialized NormalizedAlert
    enriched_alert_data: str  # JSON-serialized EnrichedAlert
    playbook_match_data: str  # JSON-serialized PlaybookMatch
    deferred_at: float = field(default_factory=time.time)
    reason: str = ""
    re_evaluate_on: str = "slot_release"  # slot_release, window_end
    status: str = "DEFERRED"

    @property
    def age_seconds(self) -> float:
        """How long this action has been deferred."""
        return time.time() - self.deferred_at

    @property
    def is_expired(self) -> bool:
        """Whether this deferred action has exceeded max deferral time."""
        return self.age_seconds > MAX_DEFER_AGE_SECONDS


class DynamoDeferredActionsStore:
    """DynamoDB-backed store for guardrail-deferred remediation actions.

    This store replaces the in-memory list in Orchestrator, enabling:
    - Survival across ECS task restarts and deployments
    - Any task in the fleet can re-evaluate deferred actions
    - Automatic expiry via DynamoDB TTL
    - Atomic state transitions prevent duplicate execution

    Storage pattern uses the existing AiopsIncidentMemory table:
        PK: incident_id
        SK: "DEFERRED#{incident_id}"
        outcome: "DEFERRED" (enables query via OutcomeIndex GSI)
    """

    def __init__(
        self,
        table_name: str,
        dynamodb_resource=None,
    ) -> None:
        """Initialize the deferred actions store.

        Args:
            table_name: Name of the DynamoDB table.
            dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        """
        self._table_name = table_name
        if dynamodb_resource:
            self._table = dynamodb_resource.Table(table_name)
        else:
            self._table = boto3.resource("dynamodb").Table(table_name)

    def defer(self, action: DeferredAction) -> bool:
        """Store a deferred action in DynamoDB.

        Uses conditional write to prevent duplicate deferrals for the
        same incident (idempotent).

        Args:
            action: The deferred action to persist.

        Returns:
            True if stored successfully, False on failure.
        """
        item = {
            "incident_id": action.incident_id,
            "timestamp": f"DEFERRED#{action.incident_id}",
            "alert_name": action.alert_name,
            "severity": action.severity,
            "target_host": action.target_host,
            "service_name": action.service_name,
            "playbook_path": action.playbook_path,
            "rule_name": action.rule_name,
            "alert_data": action.alert_data,
            "enriched_alert_data": action.enriched_alert_data,
            "playbook_match_data": action.playbook_match_data,
            "deferred_at": str(action.deferred_at),
            "reason": action.reason,
            "re_evaluate_on": action.re_evaluate_on,
            "status": "DEFERRED",
            # Use "outcome" field for GSI query (OutcomeIndex PK = outcome)
            "outcome": "DEFERRED",
            # DynamoDB TTL: auto-expire after max deferral window + 30min buffer
            "expiry_timestamp": int(action.deferred_at + MAX_DEFER_AGE_SECONDS + 1800),
            "record_type": "DEFERRED_ACTION",
        }

        try:
            self._table.put_item(
                Item=item,
                # Prevent overwriting if already deferred (idempotent)
                ConditionExpression=(
                    "attribute_not_exists(#ts) OR #status <> :deferred"
                ),
                ExpressionAttributeNames={
                    "#ts": "timestamp",
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":deferred": "DEFERRED",
                },
            )
            logger.info(
                "Deferred action stored: incident=%s reason=%s re_evaluate_on=%s",
                action.incident_id,
                action.reason,
                action.re_evaluate_on,
            )
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info(
                    "Deferred action already exists for incident %s (idempotent)",
                    action.incident_id,
                )
                return True  # Idempotent success
            logger.error("Failed to store deferred action: %s", e)
            return False

    def list_pending(self) -> list[DeferredAction]:
        """List all currently deferred actions (status=DEFERRED).

        Uses the OutcomeIndex GSI (PK: outcome) to efficiently query
        all deferred items without scanning the full table.

        Returns:
            List of DeferredAction items that are still pending.
        """
        try:
            response = self._table.query(
                IndexName="OutcomeIndex",
                KeyConditionExpression="outcome = :deferred",
                FilterExpression="record_type = :rt",
                ExpressionAttributeValues={
                    ":deferred": "DEFERRED",
                    ":rt": "DEFERRED_ACTION",
                },
                Limit=MAX_REEVALUATE_BATCH,
            )
            items = response.get("Items", [])
            return [self._item_to_action(item) for item in items]

        except ClientError as e:
            logger.error("Failed to list deferred actions: %s", e)
            return []

    def mark_allowed(self, incident_id: str) -> bool:
        """Atomically transition a deferred action to ALLOWED status.

        Uses conditional update to prevent double-execution:
        only succeeds if current status is still DEFERRED.

        Args:
            incident_id: The incident to mark as allowed.

        Returns:
            True if transition succeeded, False if already transitioned.
        """
        return self._transition_status(incident_id, "ALLOWED")

    def mark_denied(self, incident_id: str, reason: str = "") -> bool:
        """Atomically transition a deferred action to DENIED status.

        Args:
            incident_id: The incident to mark as denied.
            reason: Reason for denial.

        Returns:
            True if transition succeeded, False if already transitioned.
        """
        return self._transition_status(incident_id, "DENIED", reason)

    def mark_expired(self, incident_id: str) -> bool:
        """Atomically transition a deferred action to EXPIRED status.

        Args:
            incident_id: The incident to mark as expired.

        Returns:
            True if transition succeeded, False if already transitioned.
        """
        return self._transition_status(incident_id, "EXPIRED")

    def get(self, incident_id: str) -> Optional[DeferredAction]:
        """Get a specific deferred action by incident_id.

        Args:
            incident_id: The incident identifier.

        Returns:
            DeferredAction if found, None otherwise.
        """
        try:
            response = self._table.get_item(
                Key={
                    "incident_id": incident_id,
                    "timestamp": f"DEFERRED#{incident_id}",
                },
            )
            item = response.get("Item")
            if item is None:
                return None
            return self._item_to_action(item)
        except ClientError as e:
            logger.error(
                "Failed to get deferred action for incident %s: %s",
                incident_id,
                e,
            )
            return None

    def count_pending(self) -> int:
        """Count currently deferred actions (approximate).

        Uses Select=COUNT on the OutcomeIndex GSI for efficiency.

        Returns:
            Approximate count of pending deferred actions.
        """
        try:
            response = self._table.query(
                IndexName="OutcomeIndex",
                KeyConditionExpression="outcome = :deferred",
                FilterExpression="record_type = :rt",
                ExpressionAttributeValues={
                    ":deferred": "DEFERRED",
                    ":rt": "DEFERRED_ACTION",
                },
                Select="COUNT",
            )
            return response.get("Count", 0)
        except ClientError as e:
            logger.error("Failed to count deferred actions: %s", e)
            return 0

    def _transition_status(
        self, incident_id: str, new_status: str, reason: str = ""
    ) -> bool:
        """Atomically transition status from DEFERRED to new_status.

        Args:
            incident_id: The incident to transition.
            new_status: Target status (ALLOWED, DENIED, EXPIRED).
            reason: Optional reason for the transition.

        Returns:
            True if transition succeeded, False otherwise.
        """
        update_expr = "SET #status = :new_status, outcome = :new_status"
        expr_values = {
            ":deferred": "DEFERRED",
            ":new_status": new_status,
        }

        if reason:
            update_expr += ", reason = :reason"
            expr_values[":reason"] = reason

        try:
            self._table.update_item(
                Key={
                    "incident_id": incident_id,
                    "timestamp": f"DEFERRED#{incident_id}",
                },
                UpdateExpression=update_expr,
                ConditionExpression="#status = :deferred",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues=expr_values,
            )
            logger.info(
                "Deferred action transitioned: incident=%s status=%s",
                incident_id,
                new_status,
            )
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info(
                    "Deferred action already transitioned for incident %s",
                    incident_id,
                )
                return False
            logger.error(
                "Failed to transition deferred action %s to %s: %s",
                incident_id,
                new_status,
                e,
            )
            return False

    def _item_to_action(self, item: dict) -> DeferredAction:
        """Convert a DynamoDB item to a DeferredAction dataclass."""
        return DeferredAction(
            incident_id=item["incident_id"],
            alert_name=item.get("alert_name", ""),
            severity=item.get("severity", ""),
            target_host=item.get("target_host", ""),
            service_name=item.get("service_name", ""),
            playbook_path=item.get("playbook_path", ""),
            rule_name=item.get("rule_name", ""),
            alert_data=item.get("alert_data", "{}"),
            enriched_alert_data=item.get("enriched_alert_data", "{}"),
            playbook_match_data=item.get("playbook_match_data", "{}"),
            deferred_at=float(item.get("deferred_at", 0)),
            reason=item.get("reason", ""),
            re_evaluate_on=item.get("re_evaluate_on", "slot_release"),
            status=item.get("status", "DEFERRED"),
        )
