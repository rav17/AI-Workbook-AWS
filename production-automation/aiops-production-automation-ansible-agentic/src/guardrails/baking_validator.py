"""Post-Execution Baking Period Validator.

After a remediation completes with SUCCESS, monitors the original
alert condition and target host health to determine if the fix
was actually effective.

Inspired by SageMaker Deployment Guardrails baking period.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from src.guardrails.models import RemediationAction, RemediationOutcome, RiskLevel

logger = logging.getLogger(__name__)


# Baking period durations by risk level (seconds)
BAKING_PERIODS = {
    RiskLevel.LOW: 60,
    RiskLevel.MEDIUM: 120,
    RiskLevel.HIGH: 180,
    RiskLevel.CRITICAL: 300,
}

DEFAULT_BAKING_PERIOD = 120
MIN_BAKING_PERIOD = 30
MAX_BAKING_PERIOD = 600
HEALTH_CHECK_INTERVAL = 15  # seconds between health polls


@dataclass
class BakingResult:
    """Result of the post-execution baking period validation."""

    outcome: RemediationOutcome
    baking_duration_seconds: float
    alarm_resolved: bool = False
    host_healthy: bool = False
    reason: str = ""


class BakingValidator:
    """Validates remediation effectiveness after a baking period.

    After playbook execution succeeds, waits for a configurable period
    then checks whether the original issue is actually resolved.
    """

    def __init__(
        self,
        cloudwatch_client=None,
        health_check_func=None,
    ) -> None:
        """Initialize BakingValidator.

        Args:
            cloudwatch_client: boto3 CloudWatch client for alarm state queries.
            health_check_func: Async callable(host) -> bool for host health.
        """
        self._cloudwatch = cloudwatch_client
        self._health_check_func = health_check_func

    def get_baking_period(self, action: RemediationAction) -> int:
        """Get the baking period duration based on risk level."""
        if action.risk_level:
            return BAKING_PERIODS.get(action.risk_level, DEFAULT_BAKING_PERIOD)
        return DEFAULT_BAKING_PERIOD

    async def validate(
        self,
        action: RemediationAction,
        alarm_name: Optional[str] = None,
        baking_period: Optional[int] = None,
    ) -> BakingResult:
        """Run the post-execution baking period validation.

        Args:
            action: The remediation action that was executed.
            alarm_name: CloudWatch alarm name to check for resolution.
            baking_period: Override baking period in seconds. If None, uses
                risk-level-based default.

        Returns:
            BakingResult with the validation outcome.
        """
        period = baking_period or self.get_baking_period(action)
        period = max(MIN_BAKING_PERIOD, min(period, MAX_BAKING_PERIOD))

        start_time = time.time()

        logger.info(
            "Starting baking period for incident %s: %ds (risk=%s)",
            action.incident_id,
            period,
            action.risk_level.value if action.risk_level else "unknown",
        )

        # Wait for the baking period
        await asyncio.sleep(period)

        # Check alarm state
        alarm_resolved = await self._check_alarm_resolved(alarm_name)

        # Check host health
        host_healthy = await self._check_host_health(action.target_host)

        duration = time.time() - start_time

        # Determine outcome
        outcome = self._determine_outcome(alarm_resolved, host_healthy, alarm_name)

        result = BakingResult(
            outcome=outcome,
            baking_duration_seconds=duration,
            alarm_resolved=alarm_resolved,
            host_healthy=host_healthy,
            reason=self._build_reason(outcome, alarm_resolved, host_healthy),
        )

        logger.info(
            "Baking period complete for incident %s: outcome=%s duration=%.1fs",
            action.incident_id,
            outcome.value,
            duration,
        )

        return result

    def _determine_outcome(
        self,
        alarm_resolved: bool,
        host_healthy: bool,
        alarm_name: Optional[str],
    ) -> RemediationOutcome:
        """Determine the baking outcome from check results."""
        if not host_healthy:
            return RemediationOutcome.DEGRADED

        if alarm_name is None:
            # No alarm to check — rely on host health only
            return RemediationOutcome.EFFECTIVE if host_healthy else RemediationOutcome.INCONCLUSIVE

        if alarm_resolved and host_healthy:
            return RemediationOutcome.EFFECTIVE
        elif not alarm_resolved:
            return RemediationOutcome.INEFFECTIVE
        else:
            return RemediationOutcome.INCONCLUSIVE

    def _build_reason(
        self, outcome: RemediationOutcome, alarm_resolved: bool, host_healthy: bool
    ) -> str:
        """Build a human-readable reason string."""
        if outcome == RemediationOutcome.EFFECTIVE:
            return "Alarm resolved and host is healthy after baking period"
        elif outcome == RemediationOutcome.INEFFECTIVE:
            return "Alarm still in ALARM state after baking period — fix may not have worked"
        elif outcome == RemediationOutcome.DEGRADED:
            return "Host health check failed after baking period — service may be degraded"
        else:
            return "Unable to conclusively determine remediation effectiveness"

    async def _check_alarm_resolved(self, alarm_name: Optional[str]) -> bool:
        """Check if the triggering CloudWatch alarm has resolved."""
        if alarm_name is None or self._cloudwatch is None:
            return True  # No alarm to check = assume OK

        try:
            response = self._cloudwatch.describe_alarms(
                AlarmNames=[alarm_name],
                AlarmTypes=["MetricAlarm"],
            )
            alarms = response.get("MetricAlarms", [])
            if not alarms:
                return True  # Alarm not found = assume OK
            return alarms[0].get("StateValue") != "ALARM"
        except Exception as e:
            logger.warning("Failed to check alarm state for '%s': %s", alarm_name, e)
            return True  # Fail-open for alarm check

    async def _check_host_health(self, target_host: str) -> bool:
        """Check if the target host is healthy after remediation."""
        if self._health_check_func is None:
            return True  # No health check configured = assume OK

        try:
            return await self._health_check_func(target_host)
        except Exception as e:
            logger.warning("Host health check failed for '%s': %s", target_host, e)
            return False
