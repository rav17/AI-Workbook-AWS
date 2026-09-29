"""DynamoDB-backed distributed lock store with TTL support.

Provides host locks, alert fingerprints, and circuit breaker state storage
using DynamoDB conditional writes for atomic operations.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from src.concurrency.enums import CircuitBreakerStateEnum
from src.concurrency.models import CircuitBreakerState, FingerprintRecord, HostLock

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5


class LockStoreError(Exception):
    """Raised when the Lock Store is unreachable or returns an error."""

    pass


class LockResult:
    """Result of a lock acquisition attempt."""

    def __init__(self, acquired: bool, holder_incident_id: Optional[str] = None):
        self.acquired = acquired
        self.holder_incident_id = holder_incident_id


class LockStore:
    """DynamoDB-backed distributed lock store with TTL support."""

    def __init__(
        self,
        table_name: str,
        dynamodb_client=None,
        region_name: Optional[str] = None,
        heartbeat_manager=None,
    ) -> None:
        self.table_name = table_name
        self._heartbeat_manager = heartbeat_manager

        if dynamodb_client is not None:
            self._client = dynamodb_client
        else:
            config = Config(
                connect_timeout=_TIMEOUT_SECONDS,
                read_timeout=_TIMEOUT_SECONDS,
                retries={"max_attempts": 1},
            )
            kwargs: dict = {"config": config}
            if region_name:
                kwargs["region_name"] = region_name
            self._client = boto3.client("dynamodb", **kwargs)

    async def acquire_host_lock(
        self, host: str, incident_id: str, ttl_seconds: int, action_name: str = ""
    ) -> LockResult:
        """Acquire a host lock using DynamoDB conditional write.

        Uses attribute_not_exists to ensure atomic acquisition.
        If heartbeat manager is configured, starts a heartbeat for the lock.
        """
        now = time.time()
        ttl_epoch = int(now) + ttl_seconds

        try:
            self._client.put_item(
                TableName=self.table_name,
                Item={
                    "PK": {"S": f"HOST#{host}"},
                    "SK": {"S": "LOCK"},
                    "incident_id": {"S": incident_id},
                    "acquired_at": {"N": str(now)},
                    "ttl": {"N": str(ttl_epoch)},
                    "action_name": {"S": action_name},
                },
                ConditionExpression="attribute_not_exists(PK)",
            )

            # Start heartbeat if manager is available
            if self._heartbeat_manager is not None:
                import asyncio
                try:
                    token = await self._heartbeat_manager.start_heartbeat(
                        host, incident_id, ttl_seconds
                    )
                    logger.debug(
                        "Lock acquired with heartbeat: host=%s token=%d",
                        host, token,
                    )
                except Exception as e:
                    logger.warning("Failed to start heartbeat for %s: %s", host, e)

            return LockResult(acquired=True)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Lock is held by another execution
                holder = self._get_lock_holder(host)
                return LockResult(acquired=False, holder_incident_id=holder)
            raise LockStoreError(f"Failed to acquire lock for {host}: {e}") from e
        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
        ) as e:
            raise LockStoreError(f"Lock Store unreachable: {e}") from e

    async def release_host_lock(self, host: str, incident_id: str) -> bool:
        """Release a host lock, verifying the caller holds it.

        Also stops the heartbeat for this host if running.
        """
        # Stop heartbeat first (before releasing lock)
        if self._heartbeat_manager is not None:
            try:
                await self._heartbeat_manager.stop_heartbeat(host)
            except Exception as e:
                logger.warning("Failed to stop heartbeat for %s: %s", host, e)

        try:
            self._client.delete_item(
                TableName=self.table_name,
                Key={
                    "PK": {"S": f"HOST#{host}"},
                    "SK": {"S": "LOCK"},
                },
                ConditionExpression="incident_id = :iid",
                ExpressionAttributeValues={":iid": {"S": incident_id}},
            )
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    "Lock release failed: incident %s does not hold lock for %s",
                    incident_id,
                    host,
                )
                return False
            raise LockStoreError(f"Failed to release lock for {host}: {e}") from e
        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
        ) as e:
            raise LockStoreError(f"Lock Store unreachable: {e}") from e

    async def force_release_host_lock(self, host: str) -> bool:
        """Force-release a host lock regardless of holder."""
        try:
            self._client.delete_item(
                TableName=self.table_name,
                Key={
                    "PK": {"S": f"HOST#{host}"},
                    "SK": {"S": "LOCK"},
                },
            )
            return True
        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
            ClientError,
        ) as e:
            raise LockStoreError(f"Failed to force-release lock for {host}: {e}") from e

    async def acquire_host_locks_atomic(
        self, hosts: list[str], incident_id: str, ttl_seconds: int, action_name: str = ""
    ) -> LockResult:
        """Acquire locks for all hosts atomically.

        If any lock cannot be acquired, releases all already-acquired locks.
        """
        acquired_hosts: list[str] = []

        try:
            for host in hosts:
                result = await self.acquire_host_lock(host, incident_id, ttl_seconds, action_name)
                if result.acquired:
                    acquired_hosts.append(host)
                else:
                    # Rollback all acquired locks
                    for acquired_host in acquired_hosts:
                        await self.release_host_lock(acquired_host, incident_id)
                    return LockResult(
                        acquired=False, holder_incident_id=result.holder_incident_id
                    )
            return LockResult(acquired=True)

        except LockStoreError:
            # Rollback on error
            for acquired_host in acquired_hosts:
                try:
                    await self.release_host_lock(acquired_host, incident_id)
                except LockStoreError:
                    logger.warning("Failed to rollback lock for %s", acquired_host)
            raise

    async def get_active_lock(self, host: str) -> Optional[HostLock]:
        """Get the currently active lock for a host."""
        try:
            response = self._client.get_item(
                TableName=self.table_name,
                Key={
                    "PK": {"S": f"HOST#{host}"},
                    "SK": {"S": "LOCK"},
                },
            )
            item = response.get("Item")
            if not item:
                return None
            return HostLock(
                host=host,
                incident_id=item["incident_id"]["S"],
                acquired_at=datetime.fromtimestamp(
                    float(item["acquired_at"]["N"]), tz=timezone.utc
                ),
                ttl_seconds=int(item["ttl"]["N"]) - int(float(item["acquired_at"]["N"])),
                action_name=item.get("action_name", {}).get("S", ""),
            )
        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
            ClientError,
        ) as e:
            raise LockStoreError(f"Failed to get lock for {host}: {e}") from e

    # --- Fingerprint operations ---

    async def read_fingerprint(self, fingerprint: str) -> Optional[FingerprintRecord]:
        """Read a fingerprint record from the store."""
        try:
            response = self._client.get_item(
                TableName=self.table_name,
                Key={
                    "PK": {"S": f"FINGERPRINT#{fingerprint}"},
                    "SK": {"S": "RECORD"},
                },
            )
            item = response.get("Item")
            if not item:
                return None
            return FingerprintRecord(
                fingerprint=fingerprint,
                incident_id=item["incident_id"]["S"],
                created_at=datetime.fromtimestamp(
                    float(item["created_at"]["N"]), tz=timezone.utc
                ),
                ttl_seconds=int(item["ttl"]["N"]) - int(float(item["created_at"]["N"])),
            )
        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
            ClientError,
        ) as e:
            raise LockStoreError(f"Failed to read fingerprint: {e}") from e

    async def write_fingerprint_conditional(
        self, fingerprint: str, incident_id: str, ttl_seconds: int
    ) -> bool:
        """Write a fingerprint using conditional create-if-not-exists.

        Returns True if the fingerprint was created, False if it already exists.
        """
        now = time.time()
        ttl_epoch = int(now) + ttl_seconds

        try:
            self._client.put_item(
                TableName=self.table_name,
                Item={
                    "PK": {"S": f"FINGERPRINT#{fingerprint}"},
                    "SK": {"S": "RECORD"},
                    "incident_id": {"S": incident_id},
                    "created_at": {"N": str(now)},
                    "ttl": {"N": str(ttl_epoch)},
                },
                ConditionExpression="attribute_not_exists(PK)",
            )
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise LockStoreError(f"Failed to write fingerprint: {e}") from e
        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
        ) as e:
            raise LockStoreError(f"Lock Store unreachable: {e}") from e

    async def delete_fingerprint(self, fingerprint: str) -> None:
        """Delete a fingerprint record."""
        try:
            self._client.delete_item(
                TableName=self.table_name,
                Key={
                    "PK": {"S": f"FINGERPRINT#{fingerprint}"},
                    "SK": {"S": "RECORD"},
                },
            )
        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
            ClientError,
        ) as e:
            raise LockStoreError(f"Failed to delete fingerprint: {e}") from e

    # --- Circuit breaker state operations ---

    async def get_circuit_breaker_state(self, host: str) -> Optional[CircuitBreakerState]:
        """Get the circuit breaker state for a host."""
        try:
            response = self._client.get_item(
                TableName=self.table_name,
                Key={
                    "PK": {"S": f"CB#{host}"},
                    "SK": {"S": "STATE"},
                },
            )
            item = response.get("Item")
            if not item:
                return None

            data = item.get("data", {}).get("M", {})
            failed_ids_list = data.get("failed_incident_ids", {}).get("L", [])
            failed_ids = [entry["S"] for entry in failed_ids_list]

            last_failure_at = None
            if "last_failure_at" in data:
                last_failure_at = datetime.fromtimestamp(
                    float(data["last_failure_at"]["N"]), tz=timezone.utc
                )

            last_success_at = None
            if "last_success_at" in data:
                last_success_at = datetime.fromtimestamp(
                    float(data["last_success_at"]["N"]), tz=timezone.utc
                )

            return CircuitBreakerState(
                host=host,
                state=CircuitBreakerStateEnum(item["state"]["S"]),
                consecutive_failures=int(item["consecutive_failures"]["N"]),
                last_failure_at=last_failure_at,
                last_success_at=last_success_at,
                failed_incident_ids=failed_ids,
                last_failed_action=data.get("last_failed_action", {}).get("S"),
            )

        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
            ClientError,
        ) as e:
            raise LockStoreError(f"Failed to get circuit breaker state for {host}: {e}") from e

    async def update_circuit_breaker_state(
        self, host: str, state: CircuitBreakerState
    ) -> None:
        """Update the circuit breaker state for a host."""
        data: dict = {
            "failed_incident_ids": {
                "L": [{"S": iid} for iid in state.failed_incident_ids[-5:]]
            },
        }
        if state.last_failure_at:
            data["last_failure_at"] = {"N": str(state.last_failure_at.timestamp())}
        if state.last_success_at:
            data["last_success_at"] = {"N": str(state.last_success_at.timestamp())}
        if state.last_failed_action:
            data["last_failed_action"] = {"S": state.last_failed_action}

        try:
            self._client.put_item(
                TableName=self.table_name,
                Item={
                    "PK": {"S": f"CB#{host}"},
                    "SK": {"S": "STATE"},
                    "state": {"S": state.state.value},
                    "consecutive_failures": {"N": str(state.consecutive_failures)},
                    "data": {"M": data},
                },
            )
        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
            BotoCoreError,
            ClientError,
        ) as e:
            raise LockStoreError(
                f"Failed to update circuit breaker state for {host}: {e}"
            ) from e

    # --- Private helpers ---

    def _get_lock_holder(self, host: str) -> Optional[str]:
        """Get the incident_id of the current lock holder."""
        try:
            response = self._client.get_item(
                TableName=self.table_name,
                Key={
                    "PK": {"S": f"HOST#{host}"},
                    "SK": {"S": "LOCK"},
                },
                ProjectionExpression="incident_id",
            )
            item = response.get("Item")
            if item:
                return item["incident_id"]["S"]
            return None
        except Exception:
            return None
