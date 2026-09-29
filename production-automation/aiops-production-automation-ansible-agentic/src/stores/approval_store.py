"""DynamoDB-backed approval token store.

Provides atomic, single-use approval token management that survives
ECS task restarts, deployments, and multi-task scaling.

Tokens are stored with:
- Partition key: incident_id
- Sort key: "APPROVAL#{token}" (enables lookup by incident_id)
- GSI (TokenIndex): token → item (enables O(1) lookup by token)
- TTL: auto-expires after approval window closes (DynamoDB handles cleanup)
- Conditional writes: guarantees exactly-once consumption even under concurrency

Design decisions:
- Uses the existing AiopsIncidentMemory table (same PK/SK schema)
- Adds a GSI named "TokenIndex" on the "token" attribute
- Conditional updates prevent double-consumption (race-safe)
- In-memory LRU cache (max 100 items) for hot-path reads within a single task
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# Maximum approvals cached in-memory per task (LRU eviction)
MAX_CACHE_SIZE = 100

# Default token expiry: 30 minutes
DEFAULT_EXPIRY_SECONDS = 1800


@dataclass
class StoredApproval:
    """A remediation approval persisted in DynamoDB.

    Attributes:
        token: Unique HMAC-signed approval token.
        incident_id: Associated incident identifier.
        alert_name: Name of the triggering alert.
        severity: Alert severity level.
        affected_host: Target host for remediation.
        service_name: Affected service name.
        root_cause: Human-readable root cause description.
        proposed_action: Description of the proposed fix.
        playbook_path: Path to the Ansible playbook.
        extra_vars: Extra variables for playbook execution.
        created_at: Unix timestamp when the approval was created.
        expiry_seconds: Seconds until expiry from created_at.
        consumed: Whether the token has been used (atomic flag).
        consumed_at: Unix timestamp when consumed (0 if not consumed).
    """

    token: str
    incident_id: str
    alert_name: str
    severity: str
    affected_host: str
    service_name: str
    root_cause: str
    proposed_action: str
    playbook_path: str
    extra_vars: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    expiry_seconds: int = DEFAULT_EXPIRY_SECONDS
    consumed: bool = False
    consumed_at: float = 0.0

    @property
    def is_expired(self) -> bool:
        """Check if the approval has exceeded its time window."""
        return time.time() > (self.created_at + self.expiry_seconds)

    @property
    def expires_at_iso(self) -> str:
        """Human-readable expiry timestamp."""
        ts = self.created_at + self.expiry_seconds
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )

    # Alias for backward compatibility with PendingApproval interface
    @property
    def approved(self) -> bool:
        """Whether this approval has been consumed."""
        return self.consumed

    @property
    def expires_at(self) -> str:
        """Backward-compatible alias for expires_at_iso."""
        return self.expires_at_iso


class DynamoApprovalStore:
    """DynamoDB-backed approval store with atomic consumption guarantees.

    This store replaces the in-memory dict approach, enabling:
    - Multi-task ECS deployments (all tasks share the same DynamoDB table)
    - Survival across task restarts, rolling updates, and spot interruptions
    - Exactly-once token consumption via conditional writes
    - Automatic cleanup via DynamoDB TTL

    The store uses the existing AiopsIncidentMemory table with the pattern:
        PK: incident_id
        SK: "APPROVAL#{token}"

    A GSI named "TokenIndex" (PK: token) enables efficient lookup by token
    without requiring the caller to know the incident_id.
    """

    def __init__(
        self,
        table_name: str,
        dynamodb_resource=None,
    ) -> None:
        """Initialize the DynamoDB approval store.

        Args:
            table_name: Name of the DynamoDB table (AiopsIncidentMemory-{env}).
            dynamodb_resource: Optional boto3 DynamoDB resource (for testing).
        """
        self._table_name = table_name
        if dynamodb_resource:
            self._table = dynamodb_resource.Table(table_name)
        else:
            self._table = boto3.resource("dynamodb").Table(table_name)

        # LRU cache for hot-path reads (reduces DynamoDB read costs)
        self._cache: OrderedDict[str, StoredApproval] = OrderedDict()

    def create(self, approval: StoredApproval) -> None:
        """Persist a new approval token to DynamoDB.

        Uses a conditional write to prevent duplicate tokens (idempotent).

        Args:
            approval: The approval to persist.

        Raises:
            ClientError: If DynamoDB write fails (non-duplicate reasons).
        """
        item = {
            "incident_id": approval.incident_id,
            "timestamp": f"APPROVAL#{approval.token}",
            "token": approval.token,
            "alert_name": approval.alert_name,
            "severity": approval.severity,
            "affected_host": approval.affected_host,
            "service_name": approval.service_name,
            "root_cause": approval.root_cause,
            "proposed_action": approval.proposed_action,
            "playbook_path": approval.playbook_path,
            "extra_vars": approval.extra_vars or {},
            "created_at": str(approval.created_at),
            "expiry_seconds": approval.expiry_seconds,
            "consumed": False,
            "consumed_at": 0,
            # DynamoDB TTL: auto-delete 1 hour after expiry (buffer for audit)
            "expiry_timestamp": int(
                approval.created_at + approval.expiry_seconds + 3600
            ),
            # Record type marker for queries
            "record_type": "APPROVAL",
        }

        try:
            self._table.put_item(
                Item=item,
                # Prevent overwriting an existing approval with the same token
                ConditionExpression="attribute_not_exists(#ts)",
                ExpressionAttributeNames={"#ts": "timestamp"},
            )
            # Cache locally
            self._cache_put(approval.token, approval)
            logger.info(
                "Approval stored: incident=%s token=%s... expires=%s",
                approval.incident_id,
                approval.token[:8],
                approval.expires_at_iso,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    "Duplicate approval token (idempotent): %s...",
                    approval.token[:8],
                )
            else:
                logger.error("Failed to store approval in DynamoDB: %s", e)
                raise

    def get_by_token(self, token: str) -> Optional[StoredApproval]:
        """Retrieve an approval by its token (non-consuming read).

        Checks local cache first, falls back to DynamoDB query using
        the TokenIndex GSI.

        Args:
            token: The approval token to look up.

        Returns:
            StoredApproval if found, None otherwise.
        """
        # Check cache
        cached = self._cache.get(token)
        if cached is not None:
            return cached

        # Query DynamoDB via TokenIndex GSI
        try:
            response = self._table.query(
                IndexName="TokenIndex",
                KeyConditionExpression="#tk = :token_val",
                ExpressionAttributeNames={"#tk": "token"},
                ExpressionAttributeValues={":token_val": token},
                Limit=1,
            )
            items = response.get("Items", [])
            if not items:
                return None

            approval = self._item_to_approval(items[0])
            self._cache_put(token, approval)
            return approval

        except ClientError as e:
            logger.error("Failed to query approval by token: %s", e)
            return None

    def consume(self, token: str) -> Optional[StoredApproval]:
        """Atomically consume an approval token (single-use guarantee).

        Uses a DynamoDB conditional update to ensure exactly-once semantics:
        - Only succeeds if consumed=False AND expiry not exceeded
        - Race-safe: if two requests hit simultaneously, only one wins

        Args:
            token: The approval token to consume.

        Returns:
            StoredApproval if successfully consumed, None if invalid/expired/already-used.
        """
        # First, look up the item to get PK/SK for the conditional update
        approval = self.get_by_token(token)
        if approval is None:
            logger.warning("Approval token not found: %s...", token[:8])
            return None

        if approval.is_expired:
            logger.info(
                "Approval token expired: %s... (incident=%s)",
                token[:8],
                approval.incident_id,
            )
            return None

        if approval.consumed:
            logger.warning(
                "Approval token already consumed: %s... (incident=%s)",
                token[:8],
                approval.incident_id,
            )
            return None

        # Atomic conditional update: SET consumed=true WHERE consumed=false
        now = time.time()
        try:
            self._table.update_item(
                Key={
                    "incident_id": approval.incident_id,
                    "timestamp": f"APPROVAL#{token}",
                },
                UpdateExpression="SET #consumed_attr = :true_val, #consumed_at_attr = :now_val",
                ConditionExpression="#consumed_attr = :false_val",
                ExpressionAttributeNames={
                    "#consumed_attr": "consumed",
                    "#consumed_at_attr": "consumed_at",
                },
                ExpressionAttributeValues={
                    ":true_val": True,
                    ":false_val": False,
                    ":now_val": str(now),
                },
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Another task consumed it first (race condition handled)
                logger.warning(
                    "Approval token consumed by another task: %s... (incident=%s)",
                    token[:8],
                    approval.incident_id,
                )
                return None
            else:
                logger.error("Failed to consume approval token: %s", e)
                return None

        # Update local state
        approval.consumed = True
        approval.consumed_at = now
        self._cache_put(token, approval)

        logger.info(
            "Approval consumed: incident=%s token=%s...",
            approval.incident_id,
            token[:8],
        )
        return approval

    def get_pending_by_incident(self, incident_id: str) -> Optional[StoredApproval]:
        """Get the pending (unconsumed) approval for an incident.

        Args:
            incident_id: The incident identifier.

        Returns:
            StoredApproval if a pending approval exists, None otherwise.
        """
        try:
            response = self._table.query(
                KeyConditionExpression=(
                    "incident_id = :iid AND begins_with(#ts, :prefix)"
                ),
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExpressionAttributeValues={
                    ":iid": incident_id,
                    ":prefix": "APPROVAL#",
                },
                Limit=5,  # At most a few approvals per incident
            )
            for item in response.get("Items", []):
                approval = self._item_to_approval(item)
                if not approval.consumed and not approval.is_expired:
                    return approval
            return None
        except ClientError as e:
            logger.error(
                "Failed to query approvals for incident %s: %s",
                incident_id,
                e,
            )
            return None

    def _item_to_approval(self, item: dict) -> StoredApproval:
        """Convert a DynamoDB item to a StoredApproval dataclass."""
        return StoredApproval(
            token=item["token"],
            incident_id=item["incident_id"],
            alert_name=item.get("alert_name", ""),
            severity=item.get("severity", ""),
            affected_host=item.get("affected_host", ""),
            service_name=item.get("service_name", ""),
            root_cause=item.get("root_cause", ""),
            proposed_action=item.get("proposed_action", ""),
            playbook_path=item.get("playbook_path", ""),
            extra_vars=item.get("extra_vars", {}),
            created_at=float(item.get("created_at", 0)),
            expiry_seconds=int(item.get("expiry_seconds", DEFAULT_EXPIRY_SECONDS)),
            consumed=bool(item.get("consumed", False)),
            consumed_at=float(item.get("consumed_at", 0)),
        )

    def _cache_put(self, token: str, approval: StoredApproval) -> None:
        """Add to LRU cache, evicting oldest if at capacity."""
        if token in self._cache:
            self._cache.move_to_end(token)
        else:
            if len(self._cache) >= MAX_CACHE_SIZE:
                self._cache.popitem(last=False)
            self._cache[token] = approval
