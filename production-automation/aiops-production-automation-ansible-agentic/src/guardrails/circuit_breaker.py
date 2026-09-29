"""Circuit Breaker for the guardrails module.

Implements CLOSED -> OPEN -> HALF_OPEN -> CLOSED state machine.
Tracks failures in a sliding time window and opens the circuit
when the threshold is breached.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10
"""

import logging
import time
from enum import Enum
from typing import Callable, Optional

from src.guardrails.models import CheckResult, CheckResultType, RemediationAction

logger = logging.getLogger(__name__)

DEFAULT_FAILURE_THRESHOLD = 5
MIN_FAILURE_THRESHOLD = 1
MAX_FAILURE_THRESHOLD = 50

DEFAULT_WINDOW_SECONDS = 300
MIN_WINDOW_SECONDS = 30
MAX_WINDOW_SECONDS = 3600

DEFAULT_COOLDOWN_SECONDS = 120
MIN_COOLDOWN_SECONDS = 10
MAX_COOLDOWN_SECONDS = 1800


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerConfig:
    """Configuration for the circuit breaker. Clamps to valid ranges."""

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self.failure_threshold = self._clamp(
            failure_threshold, MIN_FAILURE_THRESHOLD,
            MAX_FAILURE_THRESHOLD, DEFAULT_FAILURE_THRESHOLD,
        )
        self.window_seconds = self._clamp(
            window_seconds, MIN_WINDOW_SECONDS,
            MAX_WINDOW_SECONDS, DEFAULT_WINDOW_SECONDS,
        )
        self.cooldown_seconds = self._clamp(
            cooldown_seconds, MIN_COOLDOWN_SECONDS,
            MAX_COOLDOWN_SECONDS, DEFAULT_COOLDOWN_SECONDS,
        )

    @staticmethod
    def _clamp(value: int, min_val: int, max_val: int, default: int) -> int:
        if not isinstance(value, int) or value < min_val or value > max_val:
            return default
        return value


class CircuitBreaker:
    """Circuit breaker with CLOSED/OPEN/HALF_OPEN state machine.

    - CLOSED: Normal operation, tracking failures in a sliding window.
    - OPEN: All actions denied. Transitions to HALF_OPEN after cooldown.
    - HALF_OPEN: Allows one probe action. Success->CLOSED, Failure->OPEN.
    """

    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        on_open_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self._config = config or CircuitBreakerConfig()
        self._on_open = on_open_callback
        self._state = CircuitState.CLOSED
        self._failures: list[float] = []
        self._last_opened_at: float = 0.0
        self._half_open_probe_allowed = True

    @property
    def name(self) -> str:
        return "circuit_breaker"

    @property
    def state(self) -> CircuitState:
        return self._state

    async def check(self, action: RemediationAction) -> CheckResult:
        """Check if the circuit breaker allows this action."""
        now = time.time()

        if self._state == CircuitState.CLOSED:
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason="Circuit breaker CLOSED",
            )

        if self._state == CircuitState.OPEN:
            elapsed = now - self._last_opened_at
            if elapsed >= self._config.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_probe_allowed = True
                return CheckResult(
                    result_type=CheckResultType.ALLOW,
                    check_name=self.name,
                    reason="Circuit breaker HALF_OPEN: probe allowed",
                )
            remaining = self._config.cooldown_seconds - elapsed
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason=f"Circuit breaker OPEN: cooldown {remaining:.0f}s",
                metadata={"cooldown_remaining": f"{remaining:.0f}"},
            )

        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_probe_allowed:
                self._half_open_probe_allowed = False
                return CheckResult(
                    result_type=CheckResultType.ALLOW,
                    check_name=self.name,
                    reason="HALF_OPEN: probe action allowed",
                )
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason="HALF_OPEN: probe already in progress",
            )

        return CheckResult(
            result_type=CheckResultType.ALLOW, check_name=self.name
        )

    def record_failure(self) -> None:
        """Record a failure. Opens the circuit if threshold is breached."""
        now = time.time()
        self._failures.append(now)

        window_start = now - self._config.window_seconds
        self._failures = [t for t in self._failures if t >= window_start]

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._last_opened_at = now
            logger.warning("Circuit breaker probe failed: HALF_OPEN -> OPEN")
            if self._on_open:
                self._on_open()
            return

        if self._state == CircuitState.CLOSED:
            if len(self._failures) >= self._config.failure_threshold:
                self._state = CircuitState.OPEN
                self._last_opened_at = now
                logger.warning(
                    "Circuit breaker opened: %d failures in %ds",
                    len(self._failures), self._config.window_seconds,
                )
                if self._on_open:
                    self._on_open()

    def record_success(self) -> None:
        """Record success. Closes the circuit if in HALF_OPEN."""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failures.clear()
            logger.info("Circuit breaker: HALF_OPEN -> CLOSED")

    def manual_reset(self) -> None:
        """Manually reset to CLOSED."""
        self._state = CircuitState.CLOSED
        self._failures.clear()
        self._half_open_probe_allowed = True
