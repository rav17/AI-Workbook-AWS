"""Human-in-the-loop approval handler.

When an alert triggers remediation, this module:
1. Generates a time-limited approval token
2. Sends an email/Slack notification with root cause analysis + approval link
3. If the link is clicked before expiry → executes the remediation
4. If not clicked → marks as "operator_manual" and skips automation

The approval link hits a GET endpoint on this service:
    GET /approve/{token}

Flow:
    Alert → Pipeline → Match Playbook → Create Approval Token
        → Send Email with RCA + Link
            → Operator clicks link → /approve/{token} → Execute remediation
            → Link expires → No action (operator fixes manually)

Persistence:
    Approval tokens are stored in DynamoDB (AiopsIncidentMemory table) using
    the DynamoApprovalStore. This guarantees tokens survive ECS task restarts,
    rolling deployments, and multi-task scaling. Token consumption uses
    conditional writes for exactly-once semantics.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from src.stores.approval_store import DynamoApprovalStore, StoredApproval

logger = logging.getLogger(__name__)

# Token expiry: 30 minutes by default
DEFAULT_TOKEN_EXPIRY_SECONDS = 1800


def _get_signing_secret() -> str:
    """Retrieve the HMAC signing secret from environment or Secrets Manager.

    Priority:
    1. APPROVAL_SIGNING_SECRET env var (for local dev/testing)
    2. Secrets Manager at /aiops/{env}/approval-signing-secret
    3. Generate a random secret (single-task fallback with warning)
    """
    # Check env var first (local dev)
    env_secret = os.environ.get("APPROVAL_SIGNING_SECRET", "").strip()
    if env_secret:
        return env_secret

    # Try Secrets Manager
    env_name = os.environ.get("ENVIRONMENT", "dev")
    secret_name = f"/aiops/{env_name}/approval-signing-secret"
    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_name)
        logger.info("Loaded approval signing secret from Secrets Manager")
        return response["SecretString"]
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ("ResourceNotFoundException", "AccessDeniedException"):
            logger.warning(
                "Approval signing secret not found in Secrets Manager (%s: %s). "
                "Generating ephemeral secret — approval tokens will NOT survive task restarts.",
                secret_name,
                error_code,
            )
        else:
            logger.warning(
                "Failed to retrieve signing secret from Secrets Manager: %s", e
            )
    except Exception as e:
        logger.warning("Unexpected error loading signing secret: %s", e)

    # Fallback: generate ephemeral secret (works for single-task dev environments)
    return secrets.token_hex(32)


_SIGNING_SECRET = _get_signing_secret()


# Backward-compatible alias for code that references PendingApproval
PendingApproval = StoredApproval


class ApprovalHandler:
    """Manages human-in-the-loop approvals for remediation actions.

    Stores pending approvals in DynamoDB via DynamoApprovalStore for
    persistence across ECS task restarts and multi-task deployments.

    Key guarantees:
    - Tokens survive task restarts, deployments, and OOM kills
    - Any task in the ECS fleet can validate and consume tokens
    - Exactly-once consumption via DynamoDB conditional writes
    - Automatic cleanup via DynamoDB TTL (no manual garbage collection)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        expiry_seconds: int = DEFAULT_TOKEN_EXPIRY_SECONDS,
        dynamodb_table_name: str = "",
    ) -> None:
        """Initialize the approval handler.

        Args:
            base_url: Public API Gateway URL for approval links.
            expiry_seconds: Seconds until approval tokens expire.
            dynamodb_table_name: DynamoDB table name. If empty, reads from
                DYNAMODB_TABLE_NAME env var.
        """
        self._base_url = base_url.rstrip("/")
        self._expiry_seconds = expiry_seconds

        table_name = dynamodb_table_name or os.environ.get("DYNAMODB_TABLE_NAME", "")

        if table_name:
            try:
                self._store = DynamoApprovalStore(table_name=table_name)
                logger.info(
                    "ApprovalHandler using DynamoDB store (table=%s)", table_name
                )
            except Exception as e:
                logger.error(
                    "Failed to initialize DynamoApprovalStore: %s. "
                    "Approval tokens will NOT persist across task restarts.",
                    e,
                )
                self._store = None
        else:
            logger.warning(
                "DYNAMODB_TABLE_NAME not set — ApprovalHandler has no persistent store. "
                "Tokens will be lost on task restart."
            )
            self._store = None

        # Fallback in-memory store (used only when DynamoDB is unavailable)
        self._memory_store: dict[str, StoredApproval] = {}
        # Fallback duplicate-suppression locks: dedup_key -> (owner_token, lock_until)
        self._memory_dedup: dict[str, tuple[str, float]] = {}

    def create_approval(
        self,
        incident_id: str,
        alert_name: str,
        severity: str,
        affected_host: str,
        service_name: str,
        root_cause: str,
        proposed_action: str,
        playbook_path: str,
        extra_vars: dict = None,
    ) -> Optional[StoredApproval]:
        """Create a pending approval with a signed token.

        Persists to DynamoDB for cross-task durability. Falls back to
        in-memory if DynamoDB is unavailable.

        Duplicate suppression: if an approval for the same alert, host and
        playbook is already pending (not expired, not yet used), no new
        approval is created and None is returned, so the caller sends no
        second email. Example: a direct alert and the CloudWatch alarm for the
        same CPU spike. Fails open (creates the approval) if DynamoDB errors.

        Args:
            incident_id: Unique incident identifier.
            alert_name: Name of the triggering alert.
            severity: Alert severity level.
            affected_host: Target host for remediation.
            service_name: Affected service name.
            root_cause: Human-readable root cause description.
            proposed_action: Description of the proposed fix.
            playbook_path: Path to the Ansible playbook.
            extra_vars: Extra variables for playbook execution.

        Returns:
            StoredApproval with the generated token, or None if an equivalent
            approval is already pending.
        """
        token = self._generate_token(incident_id)
        dedup_key = self._dedup_key(alert_name, affected_host, playbook_path)
        lock_until = time.time() + self._expiry_seconds

        if not self._claim_dedup(dedup_key, token, lock_until):
            logger.info(
                "Duplicate approval suppressed: a pending approval already exists for "
                "alert=%s host=%s playbook=%s (incident %s not emailed)",
                alert_name,
                affected_host,
                playbook_path,
                incident_id,
                extra={"incident_id": incident_id},
            )
            return None

        approval = StoredApproval(
            token=token,
            incident_id=incident_id,
            alert_name=alert_name,
            severity=severity,
            affected_host=affected_host,
            service_name=service_name,
            root_cause=root_cause,
            proposed_action=proposed_action,
            playbook_path=playbook_path,
            extra_vars=extra_vars or {},
            expiry_seconds=self._expiry_seconds,
            dedup_key=dedup_key,
        )

        # Persist to DynamoDB (primary) or memory (fallback)
        if self._store is not None:
            try:
                self._store.create(approval)
            except Exception as e:
                logger.error(
                    "DynamoDB store failed, falling back to memory: %s", e
                )
                self._memory_store[token] = approval
        else:
            self._memory_store[token] = approval

        logger.info(
            "Created approval token for incident %s (expires: %s, persistent=%s)",
            incident_id,
            approval.expires_at_iso,
            self._store is not None,
        )
        return approval

    def get_approval_link(self, approval: StoredApproval) -> str:
        """Generate the clickable approval URL.

        Args:
            approval: The approval to generate a link for.

        Returns:
            Full URL for the operator to click.
        """
        return f"{self._base_url}/approve/{approval.token}"

    def validate_and_consume(self, token: str) -> Optional[StoredApproval]:
        """Validate a token and atomically mark it as consumed.

        Uses DynamoDB conditional writes to guarantee exactly-once
        consumption even if multiple tasks or requests race on the
        same token.

        Args:
            token: The approval token to validate and consume.

        Returns:
            StoredApproval if valid and successfully consumed, None otherwise.
        """
        if self._store is not None:
            return self._store.consume(token)

        # Fallback: in-memory validation
        approval = self._memory_store.get(token)
        if approval is None:
            logger.warning("Approval token not found (memory): %s...", token[:8])
            return None

        if approval.is_expired:
            logger.info("Approval token expired: %s...", token[:8])
            return None

        if approval.consumed:
            logger.warning("Approval token already used: %s...", token[:8])
            return None

        approval.consumed = True
        approval.consumed_at = time.time()
        if self._memory_dedup.get(approval.dedup_key, ("", 0.0))[0] == token:
            del self._memory_dedup[approval.dedup_key]
        logger.info(
            "Approval consumed (memory): incident=%s", approval.incident_id
        )
        return approval

    def get_pending(self, incident_id: str) -> Optional[StoredApproval]:
        """Get pending approval by incident ID.

        Args:
            incident_id: The incident identifier.

        Returns:
            StoredApproval if a pending approval exists, None otherwise.
        """
        if self._store is not None:
            return self._store.get_pending_by_incident(incident_id)

        # Fallback: memory scan
        for approval in self._memory_store.values():
            if approval.incident_id == incident_id and not approval.consumed:
                return approval
        return None

    def get_pending_by_token(self, token: str) -> Optional[StoredApproval]:
        """Get pending approval by token without consuming it.

        Used by the GET confirmation page to display approval details
        without marking the token as used.

        Args:
            token: The approval token to look up.

        Returns:
            StoredApproval if found, None otherwise.
        """
        if self._store is not None:
            return self._store.get_by_token(token)

        return self._memory_store.get(token)

    def cleanup_expired(self) -> int:
        """Remove expired approvals from in-memory cache.

        DynamoDB TTL handles cleanup automatically for the persistent
        store, so this only affects the memory fallback.

        Returns:
            Count of expired items removed from memory.
        """
        expired_tokens = [
            t for t, a in self._memory_store.items()
            if a.is_expired and not a.consumed
        ]
        for token in expired_tokens:
            del self._memory_store[token]
        return len(expired_tokens)

    @staticmethod
    def _dedup_key(alert_name: str, affected_host: str, playbook_path: str) -> str:
        """Stable key for 'the same remediation': alert + host + playbook."""
        raw = f"{alert_name}|{affected_host}|{playbook_path}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _claim_dedup(self, dedup_key: str, token: str, lock_until: float) -> bool:
        """Claim the duplicate-suppression lock. Returns False only for a real duplicate.

        Uses DynamoDB (shared by all ECS tasks) when available, otherwise an
        in-process dict. A DynamoDB error fails open (returns True) because a
        duplicate email is safer than a suppressed approval request.
        """
        if self._store is not None:
            claimed = self._store.claim_dedup(dedup_key, token, lock_until)
            return claimed is not False  # None (store error) -> fail open

        now = time.time()
        existing = self._memory_dedup.get(dedup_key)
        if existing is not None and existing[1] > now:
            return False
        self._memory_dedup[dedup_key] = (token, lock_until)
        return True

    @staticmethod
    def _generate_token(incident_id: str) -> str:
        """Generate a signed, unique approval token.

        Combines a random nonce with an HMAC signature to produce
        a token that is both unpredictable and verifiable.

        Args:
            incident_id: The incident ID for token binding.

        Returns:
            32-character hex token string.
        """
        nonce = secrets.token_hex(16)
        payload = f"{incident_id}:{nonce}:{time.time()}"
        signature = hmac.HMAC(
            _SIGNING_SECRET.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        return f"{nonce}{signature}"
