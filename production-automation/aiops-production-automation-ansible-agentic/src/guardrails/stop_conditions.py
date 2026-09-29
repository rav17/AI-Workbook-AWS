"""Stop Conditions Monitor — Abort execution if system degrades.

Monitors CloudWatch alarms during playbook execution and triggers
immediate abort if any configured stop condition alarm fires.

Inspired by AWS FIS Stop Conditions and SageMaker Deployment Guardrails.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

STOP_CONDITIONS_CONFIG_PATH = os.environ.get(
    "STOP_CONDITIONS_CONFIG_PATH", "config/stop_conditions.yml"
)


@dataclass
class StopCondition:
    """A single stop condition alarm definition."""

    name: str
    metric: str
    threshold: str
    description: str = ""


@dataclass
class ServiceStopConditions:
    """Stop conditions for a specific service group."""

    service_group: str
    conditions: list[StopCondition] = field(default_factory=list)


@dataclass
class StopConditionResult:
    """Result of stop condition monitoring."""

    triggered: bool
    condition_name: str = ""
    reason: str = ""


class StopConditionsMonitor:
    """Monitors stop conditions during remediation execution.

    Polls CloudWatch alarms at a configurable interval and signals
    abort if any stop condition enters ALARM state.
    """

    DEFAULT_POLL_INTERVAL = 10  # seconds
    MIN_POLL_INTERVAL = 5
    MAX_POLL_INTERVAL = 30
    DEFAULT_GRACE_PERIOD = 15  # seconds before monitoring starts

    def __init__(
        self,
        config_path: str = STOP_CONDITIONS_CONFIG_PATH,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        grace_period: int = DEFAULT_GRACE_PERIOD,
        cloudwatch_client=None,
    ) -> None:
        self._config_path = config_path
        self._poll_interval = max(
            self.MIN_POLL_INTERVAL, min(poll_interval, self.MAX_POLL_INTERVAL)
        )
        self._grace_period = grace_period
        self._cloudwatch = cloudwatch_client
        self._service_conditions: dict[str, list[StopCondition]] = {}
        self._global_conditions: list[StopCondition] = []
        self._abort_event: Optional[asyncio.Event] = None
        self._triggered_condition: Optional[StopConditionResult] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load stop conditions from YAML config."""
        if not os.path.isfile(self._config_path):
            logger.info("No stop conditions config at %s — monitoring disabled", self._config_path)
            return

        try:
            with open(self._config_path, "r") as f:
                data = yaml.safe_load(f) or {}

            # Load service-specific conditions
            for entry in data.get("stop_conditions", []):
                sg = entry.get("service_group", "")
                conditions = [
                    StopCondition(
                        name=a.get("name", ""),
                        metric=a.get("metric", ""),
                        threshold=a.get("threshold", ""),
                        description=a.get("description", ""),
                    )
                    for a in entry.get("alarms", [])
                ]
                if sg:
                    self._service_conditions[sg] = conditions

            # Load global conditions
            for g in data.get("global", []):
                self._global_conditions.append(
                    StopCondition(
                        name=g.get("name", ""),
                        metric=g.get("metric", ""),
                        threshold=g.get("threshold", ""),
                        description=g.get("description", ""),
                    )
                )

            # Load defaults
            defaults = data.get("defaults", {})
            if "polling_interval_seconds" in defaults:
                self._poll_interval = max(
                    self.MIN_POLL_INTERVAL,
                    min(int(defaults["polling_interval_seconds"]), self.MAX_POLL_INTERVAL),
                )
            if "grace_period_before_monitoring_seconds" in defaults:
                self._grace_period = int(defaults["grace_period_before_monitoring_seconds"])

            logger.info(
                "Loaded stop conditions: %d service groups, %d global",
                len(self._service_conditions),
                len(self._global_conditions),
            )
        except Exception as e:
            logger.warning("Failed to load stop conditions config: %s", e)

    def get_conditions_for_service(self, service_group: str) -> list[StopCondition]:
        """Get all applicable stop conditions for a service group."""
        conditions = list(self._global_conditions)
        conditions.extend(self._service_conditions.get(service_group, []))
        return conditions

    def has_conditions(self, service_group: str) -> bool:
        """Check if any stop conditions are configured for this service."""
        return bool(self._global_conditions) or service_group in self._service_conditions

    async def start_monitoring(self, service_group: str) -> asyncio.Event:
        """Start monitoring stop conditions in a background task.

        Returns an asyncio.Event that gets set when a stop condition triggers.
        The caller should check this event periodically or await it.
        """
        self._abort_event = asyncio.Event()
        self._triggered_condition = None

        conditions = self.get_conditions_for_service(service_group)
        if not conditions:
            return self._abort_event

        asyncio.create_task(
            self._monitor_loop(conditions, self._abort_event)
        )
        return self._abort_event

    async def _monitor_loop(
        self, conditions: list[StopCondition], abort_event: asyncio.Event
    ) -> None:
        """Background polling loop that checks CloudWatch alarms."""
        # Grace period — allow remediation to start before monitoring
        await asyncio.sleep(self._grace_period)

        while not abort_event.is_set():
            for condition in conditions:
                if await self._check_alarm_state(condition):
                    self._triggered_condition = StopConditionResult(
                        triggered=True,
                        condition_name=condition.name,
                        reason=f"Stop condition '{condition.name}' triggered: {condition.description}",
                    )
                    logger.warning(
                        "STOP CONDITION TRIGGERED: %s — %s",
                        condition.name,
                        condition.description,
                    )
                    abort_event.set()
                    return

            await asyncio.sleep(self._poll_interval)

    async def _check_alarm_state(self, condition: StopCondition) -> bool:
        """Check if a CloudWatch alarm is in ALARM state.

        Returns True if the alarm is triggered and execution should abort.
        """
        if self._cloudwatch is None:
            # No CloudWatch client — cannot monitor (graceful degradation)
            return False

        try:
            response = self._cloudwatch.describe_alarms(
                AlarmNames=[condition.name],
                AlarmTypes=["MetricAlarm"],
            )
            alarms = response.get("MetricAlarms", [])
            if alarms and alarms[0].get("StateValue") == "ALARM":
                return True
            return False
        except Exception as e:
            logger.warning("Failed to check stop condition alarm '%s': %s", condition.name, e)
            return False

    def get_triggered_condition(self) -> Optional[StopConditionResult]:
        """Return the stop condition that triggered, or None."""
        return self._triggered_condition

    def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        if self._abort_event:
            self._abort_event.set()
