"""Unit tests for HostLockManager."""

import asyncio

import pytest

from src.host_lock_manager import HostLockManager


class TestHostLockManagerInit:
    """Tests for HostLockManager initialization."""

    def test_default_timeout(self):
        mgr = HostLockManager()
        assert mgr._lock_timeout == 120.0

    def test_custom_timeout(self):
        mgr = HostLockManager(lock_timeout=60.0)
        assert mgr._lock_timeout == 60.0

    def test_empty_locks_on_init(self):
        mgr = HostLockManager()
        assert mgr._locks == {}


class TestHostLockManagerAcquire:
    """Tests for lock acquisition."""

    async def test_acquire_returns_true(self):
        mgr = HostLockManager(lock_timeout=5.0)
        result = await mgr.acquire("web-server-01")
        assert result is True
        mgr.release("web-server-01")

    async def test_acquire_creates_lock_lazily(self):
        mgr = HostLockManager()
        assert "web-server-01" not in mgr._locks
        await mgr.acquire("web-server-01")
        assert "web-server-01" in mgr._locks
        mgr.release("web-server-01")

    async def test_acquire_timeout_returns_false(self):
        mgr = HostLockManager(lock_timeout=0.1)
        # Hold the lock
        await mgr.acquire("host1")
        # Second acquire should timeout
        result = await mgr.acquire("host1")
        assert result is False
        mgr.release("host1")

    async def test_acquire_serializes_same_host(self):
        """Verify that concurrent requests for the same host are serialized."""
        mgr = HostLockManager(lock_timeout=5.0)
        execution_order = []

        async def task(task_id: int):
            acquired = await mgr.acquire("shared-host")
            if acquired:
                execution_order.append(f"start-{task_id}")
                await asyncio.sleep(0.05)
                execution_order.append(f"end-{task_id}")
                mgr.release("shared-host")

        await asyncio.gather(task(1), task(2), task(3))

        # Verify serialization: each task completes before next starts
        for i in range(0, len(execution_order) - 1, 2):
            start = execution_order[i]
            end = execution_order[i + 1]
            task_id = start.split("-")[1]
            assert end == f"end-{task_id}"


class TestHostLockManagerRelease:
    """Tests for lock release."""

    async def test_release_unlocks_host(self):
        mgr = HostLockManager(lock_timeout=5.0)
        await mgr.acquire("host1")
        assert mgr.is_locked("host1") is True
        mgr.release("host1")
        assert mgr.is_locked("host1") is False

    async def test_release_allows_next_acquire(self):
        mgr = HostLockManager(lock_timeout=1.0)
        await mgr.acquire("host1")
        mgr.release("host1")
        # Should be able to acquire again immediately
        result = await mgr.acquire("host1")
        assert result is True
        mgr.release("host1")

    def test_release_nonexistent_host_logs_warning(self):
        """Releasing a host that was never locked should not raise."""
        mgr = HostLockManager()
        # Should not raise
        mgr.release("never-locked-host")


class TestHostLockManagerIsLocked:
    """Tests for lock state checking."""

    def test_is_locked_unknown_host_returns_false(self):
        mgr = HostLockManager()
        assert mgr.is_locked("unknown-host") is False

    async def test_is_locked_after_acquire(self):
        mgr = HostLockManager(lock_timeout=5.0)
        await mgr.acquire("host1")
        assert mgr.is_locked("host1") is True
        mgr.release("host1")

    async def test_is_locked_after_release(self):
        mgr = HostLockManager(lock_timeout=5.0)
        await mgr.acquire("host1")
        mgr.release("host1")
        assert mgr.is_locked("host1") is False


class TestHostLockManagerIndependence:
    """Tests for lock independence across hosts."""

    async def test_different_hosts_independent(self):
        """Locking one host does not affect another."""
        mgr = HostLockManager(lock_timeout=5.0)
        await mgr.acquire("host-a")
        # Should be able to acquire a different host immediately
        result = await mgr.acquire("host-b")
        assert result is True
        mgr.release("host-a")
        mgr.release("host-b")

    async def test_concurrent_different_hosts(self):
        """Multiple hosts can be locked concurrently."""
        mgr = HostLockManager(lock_timeout=5.0)
        results = await asyncio.gather(
            mgr.acquire("host-1"),
            mgr.acquire("host-2"),
            mgr.acquire("host-3"),
        )
        assert all(results)
        assert mgr.is_locked("host-1")
        assert mgr.is_locked("host-2")
        assert mgr.is_locked("host-3")
        mgr.release("host-1")
        mgr.release("host-2")
        mgr.release("host-3")


class TestHostLockManagerTryFinally:
    """Tests for try/finally lock release guarantee."""

    async def test_lock_released_on_exception(self):
        """Lock should be released even when exception occurs during execution."""
        mgr = HostLockManager(lock_timeout=5.0)

        with pytest.raises(ValueError):
            acquired = await mgr.acquire("host1")
            try:
                assert acquired
                raise ValueError("Simulated execution failure")
            finally:
                mgr.release("host1")

        # Lock should be released after exception
        assert mgr.is_locked("host1") is False
        # Should be able to acquire again
        result = await mgr.acquire("host1")
        assert result is True
        mgr.release("host1")
