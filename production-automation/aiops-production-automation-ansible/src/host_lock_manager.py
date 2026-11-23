"""Host Lock Manager for per-host asyncio lock management.

Provides exclusive per-host locking to ensure only one playbook executes
against a given host at any time. Locks are lazily created and managed
with configurable acquisition timeouts.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class HostLockManager:
    """Manages per-host asyncio locks with configurable acquisition timeout.

    Each unique hostname gets its own asyncio.Lock, lazily created on first
    access. This ensures mutual exclusion per host while allowing concurrent
    executions across different hosts.

    Attributes:
        lock_timeout: Maximum seconds to wait for lock acquisition before
            returning failure (default 120.0).
    """

    def __init__(self, lock_timeout: float = 120.0) -> None:
        """Initialize the HostLockManager.

        Args:
            lock_timeout: Maximum seconds to wait when acquiring a host lock.
                If acquisition takes longer, acquire() returns False.
        """
        self._lock_timeout = lock_timeout
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, hostname: str) -> asyncio.Lock:
        """Get or create the lock for a hostname (lazy population).

        Args:
            hostname: The target host identifier.

        Returns:
            The asyncio.Lock associated with the hostname.
        """
        if hostname not in self._locks:
            self._locks[hostname] = asyncio.Lock()
        return self._locks[hostname]

    async def acquire(self, hostname: str) -> bool:
        """Acquire exclusive lock for a hostname.

        Attempts to acquire the per-host lock within the configured timeout.
        If the lock cannot be acquired before the timeout expires, returns
        False without raising an exception.

        Args:
            hostname: The target host to lock.

        Returns:
            True if the lock was successfully acquired, False on timeout.
        """
        lock = self._get_lock(hostname)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=self._lock_timeout)
            logger.debug("Lock acquired for host: %s", hostname)
            return True
        except asyncio.TimeoutError:
            logger.warning(
                "Lock acquisition timed out for host: %s (timeout=%.1fs)",
                hostname,
                self._lock_timeout,
            )
            return False

    def release(self, hostname: str) -> None:
        """Release the lock for a hostname.

        Should be called in a finally block to guarantee lock release
        after execution completes (success, failure, or exception).

        Args:
            hostname: The target host whose lock should be released.

        Raises:
            RuntimeError: If the lock is not currently held (from asyncio.Lock).
        """
        lock = self._locks.get(hostname)
        if lock is not None and lock.locked():
            lock.release()
            logger.debug("Lock released for host: %s", hostname)
        else:
            logger.warning(
                "Attempted to release lock for host %s but no lock is held",
                hostname,
            )

    def is_locked(self, hostname: str) -> bool:
        """Check if a host currently has a lock held.

        Args:
            hostname: The target host to check.

        Returns:
            True if the host's lock is currently held, False otherwise.
        """
        lock = self._locks.get(hostname)
        if lock is None:
            return False
        return lock.locked()
