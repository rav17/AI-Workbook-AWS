"""Graceful shutdown handler for ECS SIGTERM signals.

Ensures DynamoDB locks are released before the container is killed,
preventing lock leaks during ECS deployments (rolling updates, canary).

When ECS sends SIGTERM:
1. Stop accepting new request_execution() calls
2. Wait for in-flight executions to complete (max 25s)
3. Force-release all held DynamoDB locks
4. Exit cleanly with code 0

This leaves a 5s buffer within ECS Fargate's 30s stop timeout.
"""

import asyncio
import logging
import signal
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.concurrency.manager import ConcurrencyManager

logger = logging.getLogger(__name__)

# Leave 5s buffer within ECS Fargate 30s stop timeout
MAX_DRAIN_WAIT_SECONDS = 25
DRAIN_POLL_INTERVAL = 0.5


class GracefulShutdownHandler:
    """Handles ECS SIGTERM for clean lock release during deployments."""

    def __init__(self) -> None:
        self._shutting_down: bool = False
        self._concurrency_manager: Optional["ConcurrencyManager"] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_shutting_down(self) -> bool:
        """True if shutdown has been initiated."""
        return self._shutting_down

    def set_concurrency_manager(self, manager: "ConcurrencyManager") -> None:
        """Attach the concurrency manager for lock release on shutdown."""
        self._concurrency_manager = manager

    def register(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Register SIGTERM and SIGINT signal handlers.

        Args:
            loop: The asyncio event loop (required for scheduling async work
                  from a sync signal handler).
        """
        self._loop = loop

        # Use signal.signal for cross-platform compatibility
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        logger.info("Graceful shutdown handler registered (SIGTERM + SIGINT)")

    def _handle_signal(self, signum: int, frame) -> None:
        """Signal handler — schedules async drain on the event loop."""
        if self._shutting_down:
            # Already shutting down — force exit on second signal
            logger.warning("Second signal received, forcing immediate exit")
            sys.exit(1)

        self._shutting_down = True
        sig_name = signal.Signals(signum).name
        logger.info("%s received — initiating graceful shutdown", sig_name)

        if self._loop and self._loop.is_running():
            # Schedule the async drain coroutine on the running loop
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._drain_and_release())
            )
        else:
            # No running loop — exit immediately
            logger.warning("No running event loop — exiting immediately")
            sys.exit(0)

    async def _drain_and_release(self) -> None:
        """Drain in-flight executions and release all locks.

        Steps:
        1. Block new requests (via is_shutting_down flag)
        2. Wait up to 25s for active executions to complete
        3. Force-release any remaining DynamoDB locks
        4. Exit cleanly
        """
        logger.info("Starting graceful drain (max %ds)", MAX_DRAIN_WAIT_SECONDS)

        released_count = 0

        if self._concurrency_manager is not None:
            # Wait for in-flight executions to complete naturally
            elapsed = 0.0
            while elapsed < MAX_DRAIN_WAIT_SECONDS:
                active = self._concurrency_manager.active_execution_count
                if active == 0:
                    logger.info("All in-flight executions completed")
                    break
                logger.info(
                    "Waiting for %d in-flight execution(s) (%.1fs elapsed)",
                    active,
                    elapsed,
                )
                await asyncio.sleep(DRAIN_POLL_INTERVAL)
                elapsed += DRAIN_POLL_INTERVAL

            # Force-release any remaining locks
            try:
                released_count = await self._concurrency_manager.release_all_held_locks()
                if released_count > 0:
                    logger.info(
                        "Released %d lock(s) during graceful shutdown",
                        released_count,
                    )
            except Exception as e:
                logger.error("Error releasing locks during shutdown: %s", e)

        logger.info(
            "Graceful shutdown complete (released %d locks). Exiting.",
            released_count,
        )
        sys.exit(0)
