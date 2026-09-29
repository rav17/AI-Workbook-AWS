"""Fleet-Wide Circuit Breaker — prevents cascading fleet damage.

Unlike the per-host circuit breaker (which tracks failures per individual host),
the fleet breaker tracks failures GLOBALLY across all hosts. When multiple hosts
fail simultaneously (e.g., SSM service degradation, bad playbook deployed to all),
it halts all automation fleet-wide until the issue is resolved.

After cooldown, uses adaptive ramp-up (1→2→4→8→max) to prevent thundering herd.
"""

import logging
import os
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


class FleetBreakerState(Enum):
    """Fleet-wide circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # All automation paused
    RECOVERING = "recovering"  # Adaptive ramp-up in progress


@dataclass
class FleetBreakerConfig:
    """Configuration for the fleet-wide circuit breaker."""

    # Total failures across any hosts within time window to trip
    failure_threshold: int = 5
    # Sliding window for counting failures (seconds)
    time_window_seconds: int = 300
    # Pause all automation for this long after tripping (seconds)
    cooldown_seconds: int = 600
    # Whether to auto-reset after cooldown (vs manual only)
    auto_reset: bool = True
    # Maximum concurrent during ramp-up (resets to this after full recovery)
    max_concurrent: int = 10

    @classmethod
    def from_env(cls) -> "FleetBreakerConfig":
        """Load from environment variables."""
        return cls(
            failure_threshold=int(os.environ.get("FLEET_BREAKER_THRESHOLD", "5")),
            time_window_seconds=int(os.environ.get("FLEET_BREAKER_WINDOW", "300")),
            cooldown_seconds=int(os.environ.get("FLEET_BREAKER_COOLDOWN", "600")),
            auto_reset=os.environ.get("FLEET_BREAKER_AUTO_RESET", "true").lower()
            in ("true", "1"),
            max_concurrent=int(os.environ.get("FLEET_BREAKER_MAX_CONCURRENT", "10")),
        )


@dataclass
class FleetBreakerDecision:
    """Result of a fleet breaker check."""

    allowed: bool
    state: FleetBreakerState
    reason: str = ""
    cooldown_remaining_seconds: float = 0.0
    current_ramp_limit: int = 0


class FleetCircuitBreaker:
    """Fleet-wide error threshold with adaptive ramp-up recovery.

    Thread-safe. Uses a sliding window deque for O(1) failure tracking.
    """

    def __init__(self, config: Optional[FleetBreakerConfig] = None) -> None:
        self._config = config or FleetBreakerConfig.from_env()
        self._lock = Lock()

        # Sliding window of failure timestamps
        self._failures: deque = deque()

        # State
        self._state = FleetBreakerState.CLOSED
        self._tripped_at: float = 0.0

        # Adaptive ramp-up tracking
        self._ramp_level: int = 0  # Current concurrent limit during recovery
        self._ramp_successes: int = 0  # Successes at current ramp level
        self._active_during_ramp: int = 0  # Currently executing during recovery

        # Feature flag
        self._enabled = os.environ.get(
            "FLEET_BREAKER_ENABLED", "true"
        ).lower() in ("true", "1", "yes")

    @property
    def state(self) -> FleetBreakerState:
        """Current fleet breaker state."""
        return self._state

    @property
    def enabled(self) -> bool:
        """Whether the fleet breaker is enabled."""
        return self._enabled

    def check(self) -> FleetBreakerDecision:
        """Check if a new execution is allowed by the fleet breaker.

        Returns:
            FleetBreakerDecision indicating whether to proceed.
        """
        if not self._enabled:
            return FleetBreakerDecision(
                allowed=True,
                state=FleetBreakerState.CLOSED,
            )

        with self._lock:
            now = time.time()

            if self._state == FleetBreakerState.CLOSED:
                return FleetBreakerDecision(
                    allowed=True,
                    state=FleetBreakerState.CLOSED,
                )

            if self._state == FleetBreakerState.OPEN:
                # Check if cooldown has elapsed
                elapsed = now - self._tripped_at
                if elapsed >= self._config.cooldown_seconds:
                    if self._config.auto_reset:
                        # Transition to RECOVERING (ramp-up)
                        self._state = FleetBreakerState.RECOVERING
                        self._ramp_level = 1  # Start with 1 concurrent
                        self._ramp_successes = 0
                        self._active_during_ramp = 0
                        logger.info(
                            "Fleet breaker: cooldown elapsed, entering RECOVERING "
                            "(ramp-up starting at 1 concurrent)"
                        )
                        return FleetBreakerDecision(
                            allowed=True,
                            state=FleetBreakerState.RECOVERING,
                            current_ramp_limit=1,
                        )
                    else:
                        # Manual reset required
                        remaining = 0.0
                        return FleetBreakerDecision(
                            allowed=False,
                            state=FleetBreakerState.OPEN,
                            reason="Fleet breaker OPEN — manual reset required",
                        )
                else:
                    remaining = self._config.cooldown_seconds - elapsed
                    return FleetBreakerDecision(
                        allowed=False,
                        state=FleetBreakerState.OPEN,
                        reason=(
                            f"Fleet breaker OPEN: {len(self._failures)} failures "
                            f"in window, cooldown remaining {remaining:.0f}s"
                        ),
                        cooldown_remaining_seconds=remaining,
                    )

            if self._state == FleetBreakerState.RECOVERING:
                # Allow up to ramp_level concurrent executions
                if self._active_during_ramp < self._ramp_level:
                    self._active_during_ramp += 1
                    return FleetBreakerDecision(
                        allowed=True,
                        state=FleetBreakerState.RECOVERING,
                        current_ramp_limit=self._ramp_level,
                    )
                else:
                    return FleetBreakerDecision(
                        allowed=False,
                        state=FleetBreakerState.RECOVERING,
                        reason=(
                            f"Ramp-up limit reached "
                            f"({self._active_during_ramp}/{self._ramp_level})"
                        ),
                        current_ramp_limit=self._ramp_level,
                    )

            # Shouldn't reach here
            return FleetBreakerDecision(
                allowed=True, state=FleetBreakerState.CLOSED
            )

    def record_failure(self, host: str = "", incident_id: str = "") -> None:
        """Record a failure from any host.

        If the failure threshold is breached within the time window,
        trips the fleet breaker to OPEN state.
        """
        if not self._enabled:
            return

        with self._lock:
            now = time.time()
            self._failures.append(now)

            # Prune failures outside the window
            cutoff = now - self._config.time_window_seconds
            while self._failures and self._failures[0] < cutoff:
                self._failures.popleft()

            # Check threshold
            if self._state == FleetBreakerState.CLOSED:
                if len(self._failures) >= self._config.failure_threshold:
                    self._state = FleetBreakerState.OPEN
                    self._tripped_at = now
                    logger.warning(
                        "FLEET BREAKER TRIPPED: %d failures in %ds window "
                        "(threshold=%d). All automation PAUSED for %ds.",
                        len(self._failures),
                        self._config.time_window_seconds,
                        self._config.failure_threshold,
                        self._config.cooldown_seconds,
                    )

            elif self._state == FleetBreakerState.RECOVERING:
                # Failure during ramp-up — go back to OPEN
                self._state = FleetBreakerState.OPEN
                self._tripped_at = now
                self._active_during_ramp = 0
                logger.warning(
                    "Fleet breaker: failure during ramp-up (host=%s), "
                    "re-entering OPEN state for another cooldown",
                    host,
                )

    def record_success(self) -> None:
        """Record a successful execution (used during ramp-up recovery).

        Doubles the ramp limit after enough successes at the current level.
        """
        if not self._enabled:
            return

        with self._lock:
            if self._state == FleetBreakerState.RECOVERING:
                self._active_during_ramp = max(0, self._active_during_ramp - 1)
                self._ramp_successes += 1

                # Double ramp limit when all current-level slots succeeded
                if self._ramp_successes >= self._ramp_level:
                    new_level = min(
                        self._ramp_level * 2, self._config.max_concurrent
                    )
                    if new_level >= self._config.max_concurrent:
                        # Full recovery — back to CLOSED
                        self._state = FleetBreakerState.CLOSED
                        self._failures.clear()
                        logger.info(
                            "Fleet breaker: ramp-up complete, returning to CLOSED"
                        )
                    else:
                        self._ramp_level = new_level
                        self._ramp_successes = 0
                        logger.info(
                            "Fleet breaker: ramp-up level increased to %d",
                            new_level,
                        )

            elif self._state == FleetBreakerState.CLOSED:
                # Normal operation — nothing to track
                pass

    def manual_reset(self) -> str:
        """Manually reset the fleet breaker to CLOSED.

        Returns a status message.
        """
        with self._lock:
            previous = self._state
            self._state = FleetBreakerState.CLOSED
            self._failures.clear()
            self._ramp_level = 0
            self._ramp_successes = 0
            self._active_during_ramp = 0
            return f"Fleet breaker reset from {previous.value} to CLOSED"

    def get_status(self) -> dict:
        """Get current fleet breaker status for observability."""
        with self._lock:
            now = time.time()
            cutoff = now - self._config.time_window_seconds
            active_failures = sum(1 for t in self._failures if t > cutoff)

            result = {
                "state": self._state.value,
                "enabled": self._enabled,
                "failures_in_window": active_failures,
                "threshold": self._config.failure_threshold,
                "window_seconds": self._config.time_window_seconds,
                "cooldown_seconds": self._config.cooldown_seconds,
            }

            if self._state == FleetBreakerState.OPEN:
                elapsed = now - self._tripped_at
                result["cooldown_remaining"] = max(
                    0, self._config.cooldown_seconds - elapsed
                )
            elif self._state == FleetBreakerState.RECOVERING:
                result["ramp_level"] = self._ramp_level
                result["ramp_successes"] = self._ramp_successes
                result["active_during_ramp"] = self._active_during_ramp

            return result
