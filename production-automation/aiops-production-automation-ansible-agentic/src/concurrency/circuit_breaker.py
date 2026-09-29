"""Per-host circuit breaker with CLOSED/OPEN/HALF_OPEN state machine."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.concurrency.config import ConcurrencyConfig
from src.concurrency.enums import CircuitBreakerStateEnum
from src.concurrency.lock_store import LockStore, LockStoreError
from src.concurrency.models import CircuitBreakerState, StateTransition

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerDecision:
    """Decision from a circuit breaker check."""

    allowed: bool
    state: CircuitBreakerStateEnum
    reason: Optional[str] = None
    cooldown_remaining_seconds: Optional[float] = None


@dataclass
class ResetResult:
    """Result of a manual circuit breaker reset."""

    success: bool
    previous_state: Optional[CircuitBreakerStateEnum] = None
    message: str = ""


class CircuitBreakerManager:
    """Per-host circuit breaker with CLOSED/OPEN/HALF_OPEN states."""

    def __init__(self, lock_store: LockStore, config: ConcurrencyConfig) -> None:
        self._lock_store = lock_store
        self._config = config

    async def check_state(self, host: str) -> CircuitBreakerDecision:
        """Check if execution is allowed for a host based on circuit breaker state.

        Handles state transitions:
        - OPEN → HALF_OPEN after cooldown elapsed
        """
        try:
            state = await self._lock_store.get_circuit_breaker_state(host)
        except LockStoreError as e:
            logger.warning(
                "Lock Store unreachable checking circuit breaker for %s: %s",
                host,
                str(e),
            )
            # Fail-open for circuit breaker reads — allow execution
            # but log warning
            return CircuitBreakerDecision(
                allowed=True,
                state=CircuitBreakerStateEnum.CLOSED,
                reason="Lock Store unreachable, allowing execution",
            )

        if state is None:
            # No state recorded — treat as CLOSED
            return CircuitBreakerDecision(
                allowed=True, state=CircuitBreakerStateEnum.CLOSED
            )

        if state.state == CircuitBreakerStateEnum.CLOSED:
            return CircuitBreakerDecision(
                allowed=True, state=CircuitBreakerStateEnum.CLOSED
            )

        if state.state == CircuitBreakerStateEnum.OPEN:
            # Check if cooldown has elapsed
            if state.last_failure_at:
                now = datetime.now(timezone.utc)
                elapsed = (now - state.last_failure_at).total_seconds()
                cooldown = self._config.circuit_breaker_cooldown_seconds

                if elapsed >= cooldown:
                    # Transition to HALF_OPEN
                    state.state = CircuitBreakerStateEnum.HALF_OPEN
                    try:
                        await self._lock_store.update_circuit_breaker_state(host, state)
                    except LockStoreError:
                        pass  # Best effort

                    return CircuitBreakerDecision(
                        allowed=True,
                        state=CircuitBreakerStateEnum.HALF_OPEN,
                        reason="Cooldown elapsed, allowing probe execution",
                    )
                else:
                    remaining = cooldown - elapsed
                    return CircuitBreakerDecision(
                        allowed=False,
                        state=CircuitBreakerStateEnum.OPEN,
                        reason=(
                            f"Circuit breaker OPEN for {host}: "
                            f"{state.consecutive_failures} consecutive failures, "
                            f"cooldown remaining {remaining:.0f}s"
                        ),
                        cooldown_remaining_seconds=remaining,
                    )
            else:
                # No last_failure_at — shouldn't happen, but transition to HALF_OPEN
                state.state = CircuitBreakerStateEnum.HALF_OPEN
                try:
                    await self._lock_store.update_circuit_breaker_state(host, state)
                except LockStoreError:
                    pass
                return CircuitBreakerDecision(
                    allowed=True, state=CircuitBreakerStateEnum.HALF_OPEN
                )

        if state.state == CircuitBreakerStateEnum.HALF_OPEN:
            # Allow one probe execution
            return CircuitBreakerDecision(
                allowed=True,
                state=CircuitBreakerStateEnum.HALF_OPEN,
                reason="HALF_OPEN: allowing probe execution",
            )

        return CircuitBreakerDecision(
            allowed=True, state=CircuitBreakerStateEnum.CLOSED
        )

    async def record_outcome(
        self, host: str, success: bool, incident_id: str = "", action_name: str = ""
    ) -> Optional[StateTransition]:
        """Record a success or failure outcome and update state.

        Returns a StateTransition if the state changed, None otherwise.
        """
        try:
            state = await self._lock_store.get_circuit_breaker_state(host)
        except LockStoreError as e:
            logger.warning(
                "Lock Store unreachable recording outcome for %s: %s", host, str(e)
            )
            return None

        if state is None:
            state = CircuitBreakerState(
                host=host,
                state=CircuitBreakerStateEnum.CLOSED,
                consecutive_failures=0,
            )

        previous_state = state.state
        now = datetime.now(timezone.utc)

        if success:
            state.consecutive_failures = 0
            state.last_success_at = now

            if previous_state in (
                CircuitBreakerStateEnum.HALF_OPEN,
                CircuitBreakerStateEnum.OPEN,
            ):
                state.state = CircuitBreakerStateEnum.CLOSED
                state.failed_incident_ids = []
                state.last_failed_action = None
        else:
            state.consecutive_failures += 1
            state.last_failure_at = now
            state.last_failed_action = action_name

            # Track last 5 failed incident IDs
            if incident_id:
                state.failed_incident_ids.append(incident_id)
                state.failed_incident_ids = state.failed_incident_ids[-5:]

            if previous_state == CircuitBreakerStateEnum.HALF_OPEN:
                # Probe failed — back to OPEN
                state.state = CircuitBreakerStateEnum.OPEN
            elif previous_state == CircuitBreakerStateEnum.CLOSED:
                # Check threshold
                if state.consecutive_failures >= self._config.circuit_breaker_failure_threshold:
                    state.state = CircuitBreakerStateEnum.OPEN

        try:
            await self._lock_store.update_circuit_breaker_state(host, state)
        except LockStoreError as e:
            logger.warning(
                "Failed to persist circuit breaker state for %s: %s", host, str(e)
            )

        if state.state != previous_state:
            trigger = "test_success" if success else "failure"
            if previous_state == CircuitBreakerStateEnum.HALF_OPEN:
                trigger = "test_success" if success else "test_failure"

            return StateTransition(
                host=host,
                previous_state=previous_state,
                new_state=state.state,
                trigger=trigger,
            )

        return None

    async def manual_reset(self, host: str) -> ResetResult:
        """Manually reset the circuit breaker for a host to CLOSED."""
        try:
            state = await self._lock_store.get_circuit_breaker_state(host)
        except LockStoreError as e:
            return ResetResult(
                success=False,
                message=f"Lock Store unreachable: {e}",
            )

        if state is None:
            return ResetResult(
                success=False,
                message=f"No circuit breaker state found for host {host}",
            )

        if state.state == CircuitBreakerStateEnum.CLOSED:
            return ResetResult(
                success=True,
                previous_state=CircuitBreakerStateEnum.CLOSED,
                message=f"Host {host} already in CLOSED state",
            )

        previous = state.state
        state.state = CircuitBreakerStateEnum.CLOSED
        state.consecutive_failures = 0
        state.failed_incident_ids = []
        state.last_failed_action = None

        try:
            await self._lock_store.update_circuit_breaker_state(host, state)
        except LockStoreError as e:
            return ResetResult(
                success=False,
                message=f"Failed to reset circuit breaker: {e}",
            )

        return ResetResult(
            success=True,
            previous_state=previous,
            message=f"Circuit breaker for {host} reset from {previous.value} to CLOSED",
        )

    async def get_state(self, host: str) -> Optional[CircuitBreakerState]:
        """Get the current circuit breaker state for a host."""
        try:
            return await self._lock_store.get_circuit_breaker_state(host)
        except LockStoreError:
            return None
