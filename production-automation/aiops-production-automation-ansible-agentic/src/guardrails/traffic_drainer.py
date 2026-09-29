"""Traffic Drainer — removes instances from load balancer before remediation.

Implements drain/restore lifecycle with health check polling
and re-registration retry logic.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
"""

import asyncio
import logging

from src.guardrails.interfaces import LoadBalancerClient

logger = logging.getLogger(__name__)

DEFAULT_DRAIN_SECONDS = 30
MIN_DRAIN_SECONDS = 5
MAX_DRAIN_SECONDS = 300

DEFAULT_HEALTH_CHECK_TIMEOUT = 60
MIN_HEALTH_CHECK_TIMEOUT = 10
MAX_HEALTH_CHECK_TIMEOUT = 300

HEALTH_CHECK_INTERVAL = 5  # seconds
MAX_REGISTRATION_RETRIES = 3
INITIAL_BACKOFF = 2.0  # seconds

LB_REMOVAL_TIMEOUT = 30  # seconds
LB_RESTORE_TIMEOUT = 60  # seconds


class TrafficDrainer:
    """Manages traffic drain/restore lifecycle for remediation actions.

    - drain(): Remove instance from LB within 30s, wait drain period.
    - restore(): Health-check instance, re-register with LB within 60s.
    - Always attempts re-registration after execution regardless of removal.
    """

    def __init__(
        self,
        lb_client: LoadBalancerClient,
        target_group: str = "",
        drain_seconds: int = DEFAULT_DRAIN_SECONDS,
        health_check_timeout: int = DEFAULT_HEALTH_CHECK_TIMEOUT,
    ) -> None:
        self._lb_client = lb_client
        self._target_group = target_group

        # Clamp drain seconds
        if drain_seconds < MIN_DRAIN_SECONDS or drain_seconds > MAX_DRAIN_SECONDS:
            self._drain_seconds = DEFAULT_DRAIN_SECONDS
        else:
            self._drain_seconds = drain_seconds

        # Clamp health check timeout
        if (
            health_check_timeout < MIN_HEALTH_CHECK_TIMEOUT
            or health_check_timeout > MAX_HEALTH_CHECK_TIMEOUT
        ):
            self._health_check_timeout = DEFAULT_HEALTH_CHECK_TIMEOUT
        else:
            self._health_check_timeout = health_check_timeout

    async def drain(self, instance_id: str) -> bool:
        """Remove instance from load balancer and wait for drain.

        Args:
            instance_id: The instance to drain.

        Returns:
            True if successfully drained, False if still present.
        """
        try:
            removed = await asyncio.wait_for(
                self._lb_client.deregister_target(self._target_group, instance_id),
                timeout=LB_REMOVAL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(
                "LB deregistration timed out for %s after %ds",
                instance_id,
                LB_REMOVAL_TIMEOUT,
            )
            removed = False
        except Exception as e:
            logger.error("LB deregistration failed for %s: %s", instance_id, e)
            removed = False

        if not removed:
            # Verify absence from active target list
            try:
                still_active = await self._lb_client.is_target_active(
                    self._target_group, instance_id
                )
                if still_active:
                    logger.error(
                        "Instance %s still in active target list after removal failure",
                        instance_id,
                    )
                    return False
            except Exception:
                return False

        # Wait for drain period
        await asyncio.sleep(self._drain_seconds)
        return True

    async def restore(self, instance_id: str) -> bool:
        """Health-check instance and re-register with load balancer.

        Polls health at 5-second intervals. Re-registers even if health
        check fails (with warning logged). Retries registration up to 3 times.

        Args:
            instance_id: The instance to restore.

        Returns:
            True if re-registered successfully, False otherwise.
        """
        # Health check polling
        health_ok = await self._poll_health(instance_id)
        if not health_ok:
            logger.warning(
                "Health check failed/timed out for %s, "
                "proceeding with re-registration anyway",
                instance_id,
            )

        # Re-registration with retry
        registered = await self._register_with_retry(instance_id)
        if not registered:
            logger.error(
                "Failed to re-register %s after %d retries",
                instance_id,
                MAX_REGISTRATION_RETRIES,
            )
        return registered

    async def _poll_health(self, instance_id: str) -> bool:
        """Poll health endpoint at 5-second intervals until timeout."""
        elapsed = 0.0
        while elapsed < self._health_check_timeout:
            try:
                await self._lb_client.is_target_active(
                    self._target_group, instance_id
                )
                # If it can respond, consider healthy enough
                return True
            except Exception:
                pass
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            elapsed += HEALTH_CHECK_INTERVAL
        return False

    async def _register_with_retry(self, instance_id: str) -> bool:
        """Re-register with exponential backoff retry."""
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_REGISTRATION_RETRIES):
            try:
                success = await asyncio.wait_for(
                    self._lb_client.register_target(
                        self._target_group, instance_id
                    ),
                    timeout=LB_RESTORE_TIMEOUT,
                )
                if success:
                    return True
            except asyncio.TimeoutError:
                logger.warning(
                    "Registration attempt %d timed out for %s",
                    attempt + 1,
                    instance_id,
                )
            except Exception as e:
                logger.warning(
                    "Registration attempt %d failed for %s: %s",
                    attempt + 1,
                    instance_id,
                    e,
                )

            if attempt < MAX_REGISTRATION_RETRIES - 1:
                await asyncio.sleep(backoff)
                backoff *= 2

        return False
