"""Concurrency Guard — prevents duplicate and excessive concurrent remediations.

Implements duplicate detection, rolling restart threshold enforcement,
and slot management for remediation actions.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

import logging
import math

from src.guardrails.interfaces import LockStore, ServiceRegistry
from src.guardrails.models import CheckResult, CheckResultType, RemediationAction

logger = logging.getLogger(__name__)

DEFAULT_ROLLING_RESTART_PCT = 25
MIN_ROLLING_RESTART_PCT = 5
MAX_ROLLING_RESTART_PCT = 50

DEFAULT_MAX_DEFER_SECONDS = 600
MIN_DEFER_SECONDS = 60
MAX_DEFER_SECONDS = 3600


class ConcurrencyGuard:
    """Prevents duplicate and excessive concurrent remediations.

    - Detects duplicate remediations via lock store (DENY).
    - Enforces rolling restart threshold: max(floor(group_size * pct / 100), 1).
    - DEFERs when threshold reached, re-evaluates on slot release.
    - Handles lock store unavailability with DENY.
    """

    def __init__(
        self,
        lock_store: LockStore,
        service_registry: ServiceRegistry,
        rolling_restart_pct: int = DEFAULT_ROLLING_RESTART_PCT,
        executor_timeout: int = 300,
        max_defer_seconds: int = DEFAULT_MAX_DEFER_SECONDS,
    ) -> None:
        self._lock_store = lock_store
        self._service_registry = service_registry
        self._executor_timeout = executor_timeout

        # Validate and clamp rolling restart percentage
        if rolling_restart_pct < MIN_ROLLING_RESTART_PCT or rolling_restart_pct > MAX_ROLLING_RESTART_PCT:
            self._rolling_restart_pct = DEFAULT_ROLLING_RESTART_PCT
        else:
            self._rolling_restart_pct = rolling_restart_pct

        # Validate and clamp max defer duration
        if max_defer_seconds < MIN_DEFER_SECONDS or max_defer_seconds > MAX_DEFER_SECONDS:
            self._max_defer_seconds = DEFAULT_MAX_DEFER_SECONDS
        else:
            self._max_defer_seconds = max_defer_seconds

        # Track active slots per service group
        self._active_slots: dict[str, set[str]] = {}  # service -> set of incident_ids

    @property
    def name(self) -> str:
        return "concurrency_guard"

    async def check(self, action: RemediationAction) -> CheckResult:
        """Check concurrency constraints for the action.

        1. Duplicate detection via lock store.
        2. Rolling restart threshold enforcement.

        Args:
            action: The remediation action to evaluate.

        Returns:
            DENY for duplicates or lock store failure,
            DEFER if threshold reached, ALLOW otherwise.
        """
        lock_key = f"remediation:{action.target_host}:{action.action_name}"

        # Step 1: Duplicate detection
        try:
            is_locked = await self._lock_store.is_locked(lock_key)
        except Exception as e:
            logger.warning("Lock store unavailable: %s", e)
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason="lock_store_unavailable",
                metadata={"error": str(e)},
            )

        if is_locked:
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason="duplicate_remediation",
                metadata={
                    "target_host": action.target_host,
                    "action_name": action.action_name,
                },
            )

        # Step 2: Rolling restart threshold
        if action.service_name:
            try:
                group_size = await self._service_registry.get_instance_count(
                    action.service_name
                )
            except Exception:
                group_size = 1

            threshold = max(
                math.floor(group_size * self._rolling_restart_pct / 100), 1
            )
            active = self._active_slots.get(action.service_name, set())

            if len(active) >= threshold:
                return CheckResult(
                    result_type=CheckResultType.DEFER,
                    check_name=self.name,
                    reason=(
                        f"Rolling restart threshold reached "
                        f"({len(active)}/{threshold} slots used)"
                    ),
                    metadata={
                        "service_name": action.service_name,
                        "active_count": str(len(active)),
                        "threshold": str(threshold),
                    },
                )

        return CheckResult(
            result_type=CheckResultType.ALLOW,
            check_name=self.name,
            reason="Concurrency constraints satisfied",
        )

    async def acquire(self, action: RemediationAction) -> bool:
        """Acquire a concurrency slot for the action.

        Lock auto-expires after executor_timeout + 60 seconds.

        Returns:
            True if slot acquired, False otherwise.
        """
        lock_key = f"remediation:{action.target_host}:{action.action_name}"
        ttl = self._executor_timeout + 60

        try:
            acquired = await self._lock_store.acquire_lock(
                lock_key, action.incident_id, ttl
            )
        except Exception as e:
            logger.warning("Failed to acquire lock: %s", e)
            return False

        if acquired and action.service_name:
            if action.service_name not in self._active_slots:
                self._active_slots[action.service_name] = set()
            self._active_slots[action.service_name].add(action.incident_id)

        return acquired

    async def release(self, action: RemediationAction) -> bool:
        """Release a concurrency slot for the action.

        Returns:
            True if slot released, False otherwise.
        """
        lock_key = f"remediation:{action.target_host}:{action.action_name}"

        try:
            released = await self._lock_store.release_lock(
                lock_key, action.incident_id
            )
        except Exception as e:
            logger.warning("Failed to release lock: %s", e)
            released = False

        if action.service_name and action.service_name in self._active_slots:
            self._active_slots[action.service_name].discard(action.incident_id)

        return released
