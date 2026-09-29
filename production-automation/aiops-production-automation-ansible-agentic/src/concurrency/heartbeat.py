"""Heartbeat-based lock renewal with fencing tokens.

Prevents split-brain execution by:
1. Sending periodic heartbeats to extend lock TTL
2. Using fencing tokens to detect stale lock holders
3. Gracefully stopping on shutdown signal

The heartbeat interval is TTL/3 (standard lease renewal pattern).
If heartbeats stop (process died), the lock expires after one TTL period.
"""

import asyncio
import logging
import time
from typing import Optional

from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# Maximum consecutive heartbeat failures before marking unhealthy
MAX_HEARTBEAT_FAILURES = 3


class HeartbeatManager:
    """Manages background heartbeat tasks for active locks.

    Each active lock gets a heartbeat coroutine that extends its TTL
    at regular intervals (ttl_seconds / 3). The heartbeat uses a
    DynamoDB conditional update to ensure only the current holder
    can extend the lock.
    """

    def __init__(self, dynamodb_client, table_name: str) -> None:
        """Initialize the heartbeat manager.

        Args:
            dynamodb_client: boto3 DynamoDB client instance.
            table_name: DynamoDB table name for lock storage.
        """
        self._client = dynamodb_client
        self._table_name = table_name
        # Active heartbeat tasks: host → asyncio.Task
        self._tasks: dict[str, asyncio.Task] = {}
        # Track fencing tokens: host → current_token
        self._fencing_tokens: dict[str, int] = {}
        # Stop flag for graceful shutdown
        self._stopping = False

    @property
    def active_heartbeats(self) -> int:
        """Number of active heartbeat tasks."""
        return len(self._tasks)

    def get_fencing_token(self, host: str) -> Optional[int]:
        """Get the current fencing token for a host lock.

        Returns None if no active heartbeat exists for this host.
        """
        return self._fencing_tokens.get(host)

    async def start_heartbeat(
        self, host: str, incident_id: str, ttl_seconds: int
    ) -> int:
        """Start a heartbeat task for a newly acquired lock.

        Args:
            host: The hostname the lock is held for.
            incident_id: The incident holding the lock.
            ttl_seconds: The lock's TTL in seconds.

        Returns:
            The fencing token assigned to this lock acquisition.
        """
        # Generate fencing token (monotonically increasing per host)
        token = self._fencing_tokens.get(host, 0) + 1
        self._fencing_tokens[host] = token

        # Cancel any existing heartbeat for this host (shouldn't happen, but safety)
        await self.stop_heartbeat(host)

        # Calculate heartbeat interval (TTL / 3)
        interval = max(ttl_seconds / 3, 5.0)  # minimum 5 seconds

        # Start background heartbeat task
        task = asyncio.create_task(
            self._heartbeat_loop(host, incident_id, ttl_seconds, interval, token)
        )
        self._tasks[host] = task

        logger.debug(
            "Heartbeat started: host=%s incident=%s ttl=%ds interval=%.1fs token=%d",
            host,
            incident_id,
            ttl_seconds,
            interval,
            token,
        )
        return token

    async def stop_heartbeat(self, host: str) -> None:
        """Stop the heartbeat task for a host (called on lock release).

        Args:
            host: The hostname whose heartbeat should stop.
        """
        task = self._tasks.pop(host, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.debug("Heartbeat stopped: host=%s", host)

    async def stop_all(self) -> None:
        """Stop all heartbeat tasks (called during graceful shutdown).

        After stopping heartbeats, locks will expire naturally at their
        current TTL, providing a safety net if explicit release fails.
        """
        self._stopping = True
        hosts = list(self._tasks.keys())
        for host in hosts:
            await self.stop_heartbeat(host)
        logger.info("All heartbeats stopped (%d tasks cancelled)", len(hosts))

    async def _heartbeat_loop(
        self,
        host: str,
        incident_id: str,
        ttl_seconds: int,
        interval: float,
        fencing_token: int,
    ) -> None:
        """Background loop that periodically extends the lock TTL.

        Uses a conditional update to ensure only the current holder
        (matching incident_id) can extend the lock.

        Args:
            host: The locked hostname.
            incident_id: The incident holding the lock.
            ttl_seconds: The original TTL to extend by.
            interval: Seconds between heartbeat attempts.
            fencing_token: The fencing token for this acquisition.
        """
        consecutive_failures = 0

        try:
            while not self._stopping:
                await asyncio.sleep(interval)

                if self._stopping:
                    break

                success = await self._send_heartbeat(
                    host, incident_id, ttl_seconds, fencing_token
                )

                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= MAX_HEARTBEAT_FAILURES:
                        logger.warning(
                            "Heartbeat unhealthy: host=%s (%d consecutive failures). "
                            "Lock will expire naturally.",
                            host,
                            consecutive_failures,
                        )
                        # Don't release the lock — let it expire naturally
                        # This is safer than releasing and risking another holder
                        break

        except asyncio.CancelledError:
            # Normal cancellation on stop_heartbeat()
            pass
        except Exception as e:
            logger.error("Heartbeat loop unexpected error for host=%s: %s", host, e)
        finally:
            # Clean up task reference
            self._tasks.pop(host, None)

    async def _send_heartbeat(
        self,
        host: str,
        incident_id: str,
        ttl_seconds: int,
        fencing_token: int,
    ) -> bool:
        """Send a single heartbeat (extend lock TTL).

        Uses conditional update: only succeeds if incident_id still matches.
        This detects if another process stole the lock (shouldn't happen
        with correct TTL management, but provides defense-in-depth).

        Returns True on success, False on failure.
        """
        new_ttl = int(time.time()) + ttl_seconds

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._client.update_item(
                    TableName=self._table_name,
                    Key={
                        "PK": {"S": f"HOST#{host}"},
                        "SK": {"S": "LOCK"},
                    },
                    UpdateExpression="SET #ttl = :new_ttl, fencing_token = :token",
                    ConditionExpression="incident_id = :iid",
                    ExpressionAttributeNames={"#ttl": "ttl"},
                    ExpressionAttributeValues={
                        ":new_ttl": {"N": str(new_ttl)},
                        ":iid": {"S": incident_id},
                        ":token": {"N": str(fencing_token)},
                    },
                ),
            )
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ConditionalCheckFailedException":
                # Lock was stolen or expired — another process holds it
                logger.warning(
                    "Heartbeat: lock no longer held by us (host=%s incident=%s). "
                    "Another process may have acquired it.",
                    host,
                    incident_id,
                )
                return False
            logger.warning("Heartbeat DynamoDB error for host=%s: %s", host, e)
            return False

        except (BotoCoreError, Exception) as e:
            logger.warning("Heartbeat network error for host=%s: %s", host, e)
            return False
