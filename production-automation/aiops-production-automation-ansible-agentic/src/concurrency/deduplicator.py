"""Alert deduplication using fingerprint-based suppression windows."""

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

from src.concurrency.config import ConcurrencyConfig
from src.concurrency.lock_store import LockStore, LockStoreError

logger = logging.getLogger(__name__)


@dataclass
class DeduplicationResult:
    """Result of a deduplication check."""

    is_duplicate: bool
    original_incident_id: Optional[str] = None
    fingerprint: str = ""


class AlertDeduplicator:
    """Fingerprint-based alert deduplication with suppression windows."""

    def __init__(self, lock_store: LockStore, config: ConcurrencyConfig) -> None:
        self._lock_store = lock_store
        self._config = config
        # Local cache for fallback when Lock Store is unreachable
        self._local_cache: dict[str, str] = {}

    def compute_fingerprint(
        self, alert_name: str, target_host: str, severity: str
    ) -> str:
        """Compute a deterministic fingerprint from alert attributes.

        Combines alert_name, target_host, and severity into a SHA-256 hash.
        """
        content = f"{alert_name}|{target_host}|{severity}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def check_and_acquire(
        self, fingerprint: str, incident_id: str
    ) -> DeduplicationResult:
        """Check if alert is a duplicate and acquire the fingerprint if not.

        Uses conditional write to ensure atomicity. If Lock Store is
        unreachable, falls back to local cache for obvious duplicates.
        """
        try:
            # Attempt conditional write (create-if-not-exists)
            acquired = await self._lock_store.write_fingerprint_conditional(
                fingerprint=fingerprint,
                incident_id=incident_id,
                ttl_seconds=self._config.suppression_window_seconds,
            )

            if acquired:
                # Successfully acquired — not a duplicate
                self._local_cache[fingerprint] = incident_id
                return DeduplicationResult(
                    is_duplicate=False, fingerprint=fingerprint
                )
            else:
                # Fingerprint already exists — duplicate
                existing = await self._lock_store.read_fingerprint(fingerprint)
                original_id = existing.incident_id if existing else None
                return DeduplicationResult(
                    is_duplicate=True,
                    original_incident_id=original_id,
                    fingerprint=fingerprint,
                )

        except LockStoreError as e:
            logger.error(
                "Lock Store unavailable during deduplication: %s", str(e)
            )
            # Fallback to local cache for obvious duplicates
            if fingerprint in self._local_cache:
                return DeduplicationResult(
                    is_duplicate=True,
                    original_incident_id=self._local_cache[fingerprint],
                    fingerprint=fingerprint,
                )
            # Cannot determine — reject to be safe
            raise

    async def clear_on_failure(self, fingerprint: str) -> None:
        """Clear a fingerprint after remediation failure to allow retry."""
        try:
            await self._lock_store.delete_fingerprint(fingerprint)
            self._local_cache.pop(fingerprint, None)
        except LockStoreError as e:
            logger.warning(
                "Failed to clear fingerprint on failure: %s", str(e)
            )
