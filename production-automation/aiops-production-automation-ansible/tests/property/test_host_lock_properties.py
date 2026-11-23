# Feature: execution-concurrency-safety, Property 3: Lock Acquire/Release Round-Trip
"""Property-based tests for the Host Lock Manager component.

Property 3: Lock Acquire/Release Round-Trip
*For any* hostname and any sequence of (acquire, release) operations, the
HostLockManager SHALL return to a state equivalent to no lock held—the lock
is fully released and available for new acquisitions.

**Validates: Requirements 1.6**
"""

import asyncio

from hypothesis import given, settings
from hypothesis import strategies as st

from src.host_lock_manager import HostLockManager


# --- Hypothesis Strategies ---

# Strategy for generating valid hostnames
hostname_strategy = st.one_of(
    # Simple hostnames
    st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    ).filter(lambda h: len(h.strip()) > 0),
    # FQDN-style hostnames
    st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-"),
    ).map(lambda h: f"{h}.example.com"),
    # IP address format
    st.tuples(
        st.integers(min_value=1, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=1, max_value=255),
    ).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}"),
)

# Strategy for generating number of acquire/release cycles (1-10)
cycle_count_strategy = st.integers(min_value=1, max_value=10)


# --- Property 3: Lock Acquire/Release Round-Trip ---


class TestLockAcquireReleaseRoundTrip:
    """Property tests for lock acquire/release round-trip (Property 3).

    **Validates: Requirements 1.6**

    For any hostname and any sequence of (acquire, release) operations, the
    HostLockManager SHALL return to a state equivalent to no lock held—the
    lock is fully released and available for new acquisitions.
    """

    @given(
        hostname=hostname_strategy,
        num_cycles=cycle_count_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_lock_returns_to_unlocked_after_acquire_release_cycles(
        self,
        hostname: str,
        num_cycles: int,
    ) -> None:
        """After any number of (acquire, release) cycles, the lock SHALL
        return to an unlocked state.

        **Validates: Requirements 1.6**

        Strategy: Generate a hostname and a number of acquire/release cycles
        (1-10). For each cycle, acquire then release. After all cycles, verify
        is_locked() returns False.
        """

        async def run_cycles():
            manager = HostLockManager(lock_timeout=5.0)

            # Perform num_cycles of acquire/release
            for _ in range(num_cycles):
                acquired = await manager.acquire(hostname)
                assert acquired, (
                    f"Lock acquisition should succeed for host '{hostname}'"
                )
                manager.release(hostname)

            # After all cycles, the lock should be fully released
            assert not manager.is_locked(hostname), (
                f"After {num_cycles} acquire/release cycles, host '{hostname}' "
                f"should not be locked, but is_locked() returned True"
            )

        asyncio.run(run_cycles())

    @given(
        hostname=hostname_strategy,
        num_cycles=cycle_count_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_new_acquire_succeeds_after_acquire_release_cycles(
        self,
        hostname: str,
        num_cycles: int,
    ) -> None:
        """After any number of (acquire, release) cycles, a new acquire()
        SHALL succeed immediately.

        **Validates: Requirements 1.6**

        Strategy: Generate a hostname and a number of acquire/release cycles
        (1-10). For each cycle, acquire then release. After all cycles, verify
        a new acquire() succeeds immediately (within a short timeout).
        """

        async def run_cycles_and_reacquire():
            manager = HostLockManager(lock_timeout=5.0)

            # Perform num_cycles of acquire/release
            for _ in range(num_cycles):
                acquired = await manager.acquire(hostname)
                assert acquired, (
                    f"Lock acquisition should succeed for host '{hostname}'"
                )
                manager.release(hostname)

            # A new acquire should succeed immediately
            acquired = await manager.acquire(hostname)
            assert acquired, (
                f"After {num_cycles} acquire/release cycles, a new acquire() "
                f"for host '{hostname}' should succeed immediately, but it failed"
            )

            # Clean up
            manager.release(hostname)

        asyncio.run(run_cycles_and_reacquire())
