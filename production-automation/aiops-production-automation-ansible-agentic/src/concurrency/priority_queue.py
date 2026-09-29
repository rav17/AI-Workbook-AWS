"""In-memory priority queue with severity + timestamp ordering."""

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from src.concurrency.config import ConcurrencyConfig
from src.concurrency.models import QueueEntry

logger = logging.getLogger(__name__)


class QueueFullError(Exception):
    """Raised when the queue for a host has reached maximum depth."""

    pass


class DuplicateEntryError(Exception):
    """Raised when a duplicate incident_id is submitted for the same host."""

    pass


class PriorityQueue:
    """In-memory priority queue with severity + timestamp ordering.

    Entries are ordered by severity (P1 highest) then by arrival timestamp
    (earliest first within same severity). Thread-safe via lock.
    """

    def __init__(self, config: ConcurrencyConfig) -> None:
        self._config = config
        self._queues: dict[str, list[QueueEntry]] = defaultdict(list)
        self._lock = threading.Lock()

    def enqueue(self, entry: QueueEntry) -> int:
        """Add an entry to the queue for its target host.

        Returns the queue position (1-based).
        Raises QueueFullError if max depth is reached.
        Raises DuplicateEntryError if incident already queued for this host.
        """
        with self._lock:
            host = entry.target_host
            queue = self._queues[host]

            # Check max depth
            if len(queue) >= self._config.max_queue_depth_per_host:
                logger.warning(
                    "Queue full for host %s (depth=%d)", host, len(queue)
                )
                raise QueueFullError(
                    f"Queue full for host {host}: "
                    f"depth {len(queue)} >= max {self._config.max_queue_depth_per_host}"
                )

            # Check for duplicate
            if any(e.incident_id == entry.incident_id for e in queue):
                raise DuplicateEntryError(
                    f"Incident {entry.incident_id} already queued for host {host}"
                )

            queue.append(entry)
            queue.sort(key=lambda e: e.priority_key())

            position = queue.index(entry) + 1
            return position

    def dequeue_for_host(self, host: str) -> Optional[QueueEntry]:
        """Remove and return the highest-priority entry for a host.

        Returns None if no entries are queued for the host.
        """
        with self._lock:
            queue = self._queues.get(host)
            if not queue:
                return None
            # Queue is already sorted — first entry is highest priority
            return queue.pop(0)

    def get_depth(self, host: str) -> int:
        """Get the current queue depth for a host."""
        with self._lock:
            return len(self._queues.get(host, []))

    def get_all_depths(self) -> dict[str, int]:
        """Get queue depths for all hosts."""
        with self._lock:
            return {host: len(q) for host, q in self._queues.items() if q}

    def remove_by_incident(self, incident_id: str, host: str) -> bool:
        """Remove a specific incident from the queue.

        Returns True if the entry was found and removed.
        """
        with self._lock:
            queue = self._queues.get(host)
            if not queue:
                return False

            for i, entry in enumerate(queue):
                if entry.incident_id == incident_id:
                    queue.pop(i)
                    return True
            return False

    def contains_incident(self, incident_id: str, host: str) -> bool:
        """Check if an incident is already in the queue for a host."""
        with self._lock:
            queue = self._queues.get(host, [])
            return any(e.incident_id == incident_id for e in queue)

    def expire_stale_entries(self, max_wait_seconds: int) -> list[QueueEntry]:
        """Remove and return entries that have exceeded max wait time."""
        now = datetime.now(timezone.utc)
        expired: list[QueueEntry] = []

        with self._lock:
            for host, queue in self._queues.items():
                remaining: list[QueueEntry] = []
                for entry in queue:
                    age = (now - entry.enqueued_at).total_seconds()
                    if age > max_wait_seconds:
                        expired.append(entry)
                    else:
                        remaining.append(entry)
                self._queues[host] = remaining

        return expired

    def peek_for_host(self, host: str) -> Optional[QueueEntry]:
        """Peek at the highest-priority entry without removing it."""
        with self._lock:
            queue = self._queues.get(host)
            if not queue:
                return None
            return queue[0]

    def get_entries_for_host(self, host: str) -> list[QueueEntry]:
        """Get all entries for a host (read-only copy)."""
        with self._lock:
            return list(self._queues.get(host, []))
