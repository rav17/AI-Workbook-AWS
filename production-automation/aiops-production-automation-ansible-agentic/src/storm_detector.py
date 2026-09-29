"""Alert Storm Detector — backpressure and rate limiting.

Prevents system overload during infrastructure-wide outages by:
1. Tracking incoming alert rate in a sliding window
2. Grouping alerts by (alertname + service) during storm mode
3. Processing only one representative per group
4. Responding HTTP 429 when queue depth exceeds capacity

Uses a thread-safe sliding window counter with O(1) operations.
"""

import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class StormConfig:
    """Configuration for storm detection behavior."""

    # Alerts per minute threshold to enter storm mode
    rate_threshold: int = 50
    # Window size in seconds for rate measurement
    window_seconds: int = 60
    # Seconds to suppress duplicate groups during storm
    suppression_window_seconds: int = 120
    # Minutes of below-threshold rate before exiting storm mode
    exit_cooldown_minutes: int = 2
    # Maximum internal queue depth before returning 429
    max_queue_depth: int = 100

    @classmethod
    def from_env(cls) -> "StormConfig":
        """Load config from environment variables with defaults."""
        return cls(
            rate_threshold=int(os.environ.get("STORM_RATE_THRESHOLD", "50")),
            window_seconds=int(os.environ.get("STORM_WINDOW_SECONDS", "60")),
            suppression_window_seconds=int(
                os.environ.get("STORM_SUPPRESSION_WINDOW", "120")
            ),
            exit_cooldown_minutes=int(
                os.environ.get("STORM_EXIT_COOLDOWN_MINUTES", "2")
            ),
            max_queue_depth=int(os.environ.get("STORM_MAX_QUEUE_DEPTH", "100")),
        )


@dataclass
class StormGroupKey:
    """Key for grouping alerts during storm mode."""

    alert_name: str
    service_name: str

    def __hash__(self) -> int:
        return hash((self.alert_name, self.service_name))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StormGroupKey):
            return NotImplemented
        return (
            self.alert_name == other.alert_name
            and self.service_name == other.service_name
        )


@dataclass
class StormDecision:
    """Result of evaluating an alert against the storm detector."""

    should_process: bool
    is_storm_active: bool
    reason: str = ""
    group_key: Optional[StormGroupKey] = None
    suppressed_count: int = 0


@dataclass
class StormMetrics:
    """Metrics from the storm detector for observability."""

    is_storm_active: bool
    current_rate: float
    threshold: int
    alerts_suppressed_total: int
    active_groups: int
    storm_activations_total: int


class StormDetector:
    """Sliding-window alert storm detection with grouping.

    Thread-safe implementation using a circular buffer for O(1) rate tracking.
    """

    def __init__(self, config: Optional[StormConfig] = None) -> None:
        self._config = config or StormConfig.from_env()
        self._lock = Lock()

        # Sliding window: list of timestamps for recent alerts
        self._timestamps: list[float] = []

        # Storm mode state
        self._storm_active: bool = False
        self._storm_entered_at: float = 0.0
        self._below_threshold_since: float = 0.0

        # Group tracking: key → last_processed_at
        self._active_groups: dict[StormGroupKey, float] = {}

        # Metrics
        self._total_suppressed: int = 0
        self._storm_activations: int = 0

        # Enabled flag (for feature flag support)
        self._enabled: bool = os.environ.get(
            "STORM_DETECTION_ENABLED", "true"
        ).lower() in ("true", "1", "yes")

    @property
    def is_storm_active(self) -> bool:
        """Whether the system is currently in storm mode."""
        return self._storm_active

    @property
    def enabled(self) -> bool:
        """Whether storm detection is enabled."""
        return self._enabled

    def evaluate(self, alert_name: str, service_name: str) -> StormDecision:
        """Evaluate whether an incoming alert should be processed.

        This is the main entry point called by the webhook handler.

        Args:
            alert_name: The alertname label from the alert.
            service_name: The service_name label (or empty string).

        Returns:
            StormDecision indicating whether to process this alert.
        """
        if not self._enabled:
            return StormDecision(should_process=True, is_storm_active=False)

        now = time.time()
        group_key = StormGroupKey(alert_name=alert_name, service_name=service_name)

        with self._lock:
            # Record this alert in the sliding window
            self._timestamps.append(now)

            # Prune old timestamps outside the window
            cutoff = now - self._config.window_seconds
            self._timestamps = [
                t for t in self._timestamps if t > cutoff
            ]

            current_rate = len(self._timestamps)

            # Check if we should enter or exit storm mode
            self._update_storm_state(current_rate, now)

            if not self._storm_active:
                return StormDecision(
                    should_process=True,
                    is_storm_active=False,
                    group_key=group_key,
                )

            # Storm mode is active — apply grouping
            last_processed = self._active_groups.get(group_key)

            if last_processed is not None:
                # Group has been seen recently
                elapsed = now - last_processed
                if elapsed < self._config.suppression_window_seconds:
                    # Suppress this alert (already processing one for this group)
                    self._total_suppressed += 1
                    return StormDecision(
                        should_process=False,
                        is_storm_active=True,
                        reason=(
                            f"Storm suppression: {alert_name}/{service_name} "
                            f"already processing (group seen {elapsed:.0f}s ago)"
                        ),
                        group_key=group_key,
                        suppressed_count=self._total_suppressed,
                    )

            # This is either a new group or the suppression window expired
            # Process this alert as the representative for its group
            self._active_groups[group_key] = now
            return StormDecision(
                should_process=True,
                is_storm_active=True,
                reason="Storm mode: processing as group representative",
                group_key=group_key,
            )

    def check_backpressure(self, queue_depth: int) -> bool:
        """Check if backpressure should be applied (HTTP 429).

        Args:
            queue_depth: Current internal pipeline queue depth.

        Returns:
            True if the system should respond with HTTP 429.
        """
        return queue_depth > self._config.max_queue_depth

    def get_metrics(self) -> StormMetrics:
        """Get current storm detector metrics for observability."""
        with self._lock:
            now = time.time()
            cutoff = now - self._config.window_seconds
            current_rate = sum(1 for t in self._timestamps if t > cutoff)

            return StormMetrics(
                is_storm_active=self._storm_active,
                current_rate=float(current_rate),
                threshold=self._config.rate_threshold,
                alerts_suppressed_total=self._total_suppressed,
                active_groups=len(self._active_groups),
                storm_activations_total=self._storm_activations,
            )

    def _update_storm_state(self, current_rate: int, now: float) -> None:
        """Update storm mode state based on current rate.

        Must be called while holding self._lock.
        """
        if not self._storm_active:
            # Check if we should ENTER storm mode
            if current_rate > self._config.rate_threshold:
                self._storm_active = True
                self._storm_entered_at = now
                self._below_threshold_since = 0.0
                self._storm_activations += 1
                logger.warning(
                    "STORM MODE ACTIVATED: rate=%d threshold=%d",
                    current_rate,
                    self._config.rate_threshold,
                )
        else:
            # Check if we should EXIT storm mode
            if current_rate <= self._config.rate_threshold:
                if self._below_threshold_since == 0.0:
                    self._below_threshold_since = now
                else:
                    below_duration = now - self._below_threshold_since
                    required = self._config.exit_cooldown_minutes * 60
                    if below_duration >= required:
                        self._storm_active = False
                        self._below_threshold_since = 0.0
                        # Clean up expired groups
                        self._active_groups.clear()
                        logger.info(
                            "STORM MODE DEACTIVATED: rate=%d (below threshold for %ds)",
                            current_rate,
                            int(below_duration),
                        )
            else:
                # Rate back above threshold — reset exit timer
                self._below_threshold_since = 0.0
