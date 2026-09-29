"""Execution-Level Idempotency — prevents duplicate SSM command execution.

When the SSM executor retries a failed API call (network timeout), the
command might execute TWICE on the host. This module provides an
idempotency layer that:
1. Generates a unique key per (incident_id, step_number, attempt_number)
2. Checks if the key has already been executed
3. Returns cached result if already completed
4. Prevents re-execution of the same step

Storage: in-memory with TTL (24h). Can be backed by DynamoDB in production.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 86400  # 24 hours
MAX_RECORDS = 50000  # Prevent unbounded memory growth


class IdempotencyStatus(Enum):
    """Status of an idempotency record."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IdempotencyRecord:
    """A stored execution outcome for idempotency checks."""

    key: str
    status: IdempotencyStatus
    result_payload: Optional[dict] = None
    created_at: float = 0.0
    completed_at: float = 0.0
    ttl: float = 0.0


@dataclass
class IdempotencyCheckResult:
    """Result of an idempotency check before execution."""

    already_executed: bool
    status: Optional[IdempotencyStatus] = None
    cached_result: Optional[dict] = None
    reason: str = ""


class IdempotencyStore:
    """In-memory idempotency store with TTL-based expiry.

    Thread-safe. Provides at-most-once execution semantics for
    SSM commands within a 24-hour window.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._lock = Lock()
        self._records: dict[str, IdempotencyRecord] = {}
        self._ttl = ttl_seconds

    @staticmethod
    def make_key(incident_id: str, step_number: int, attempt: int = 0) -> str:
        """Generate an idempotency key.

        Args:
            incident_id: The incident being remediated.
            step_number: Which step in the multi-step plan.
            attempt: The retry attempt number.

        Returns:
            A composite key string.
        """
        return f"{incident_id}:{step_number}:{attempt}"

    def check_and_acquire(self, key: str) -> IdempotencyCheckResult:
        """Check if a key has already been executed; if not, acquire it.

        This is an atomic check-and-set operation:
        - If key doesn't exist → create IN_PROGRESS record, return not_executed
        - If key exists and COMPLETED → return cached result
        - If key exists and IN_PROGRESS → return already_in_progress
        - If key exists and FAILED → allow re-execution (clear and acquire)

        Args:
            key: The idempotency key to check.

        Returns:
            IdempotencyCheckResult indicating whether to proceed.
        """
        with self._lock:
            self._evict_expired()

            record = self._records.get(key)

            if record is None:
                # Not seen before — acquire
                self._records[key] = IdempotencyRecord(
                    key=key,
                    status=IdempotencyStatus.IN_PROGRESS,
                    created_at=time.time(),
                    ttl=time.time() + self._ttl,
                )
                return IdempotencyCheckResult(
                    already_executed=False,
                    reason="New execution (idempotency key acquired)",
                )

            if record.status == IdempotencyStatus.COMPLETED:
                # Already executed successfully — return cached
                return IdempotencyCheckResult(
                    already_executed=True,
                    status=IdempotencyStatus.COMPLETED,
                    cached_result=record.result_payload,
                    reason="Already executed — returning cached result",
                )

            if record.status == IdempotencyStatus.IN_PROGRESS:
                # Another execution is in progress
                age = time.time() - record.created_at
                if age > 600:  # 10 min timeout for IN_PROGRESS records
                    # Stale IN_PROGRESS — allow re-execution
                    record.status = IdempotencyStatus.IN_PROGRESS
                    record.created_at = time.time()
                    return IdempotencyCheckResult(
                        already_executed=False,
                        reason="Stale in-progress record reset (>10min old)",
                    )
                return IdempotencyCheckResult(
                    already_executed=True,
                    status=IdempotencyStatus.IN_PROGRESS,
                    reason=f"Execution already in progress (started {age:.0f}s ago)",
                )

            if record.status == IdempotencyStatus.FAILED:
                # Previous attempt failed — allow retry
                record.status = IdempotencyStatus.IN_PROGRESS
                record.created_at = time.time()
                record.result_payload = None
                return IdempotencyCheckResult(
                    already_executed=False,
                    reason="Previous attempt failed — allowing retry",
                )

        return IdempotencyCheckResult(already_executed=False)

    def mark_completed(self, key: str, result: Optional[dict] = None) -> None:
        """Mark an execution as completed with optional result payload.

        Args:
            key: The idempotency key.
            result: Optional result dict to cache (exit_code, output, etc.)
        """
        with self._lock:
            record = self._records.get(key)
            if record:
                record.status = IdempotencyStatus.COMPLETED
                record.completed_at = time.time()
                record.result_payload = result
            else:
                # Record directly if not tracked (defensive)
                self._records[key] = IdempotencyRecord(
                    key=key,
                    status=IdempotencyStatus.COMPLETED,
                    result_payload=result,
                    created_at=time.time(),
                    completed_at=time.time(),
                    ttl=time.time() + self._ttl,
                )

    def mark_failed(self, key: str, error: str = "") -> None:
        """Mark an execution as failed (allows future retry).

        Args:
            key: The idempotency key.
            error: Error description.
        """
        with self._lock:
            record = self._records.get(key)
            if record:
                record.status = IdempotencyStatus.FAILED
                record.completed_at = time.time()
                record.result_payload = {"error": error}

    def get_stats(self) -> dict:
        """Get store statistics for observability."""
        with self._lock:
            total = len(self._records)
            completed = sum(
                1 for r in self._records.values()
                if r.status == IdempotencyStatus.COMPLETED
            )
            in_progress = sum(
                1 for r in self._records.values()
                if r.status == IdempotencyStatus.IN_PROGRESS
            )
            failed = sum(
                1 for r in self._records.values()
                if r.status == IdempotencyStatus.FAILED
            )
            return {
                "total_records": total,
                "completed": completed,
                "in_progress": in_progress,
                "failed": failed,
            }

    def _evict_expired(self) -> None:
        """Remove expired records. Must hold self._lock."""
        if len(self._records) < MAX_RECORDS // 2:
            return  # Only evict when store is getting large

        now = time.time()
        expired = [
            k for k, r in self._records.items()
            if r.ttl > 0 and now > r.ttl
        ]
        for k in expired[:5000]:
            del self._records[k]
