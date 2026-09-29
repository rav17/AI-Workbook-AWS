"""Redis-backed storm detection shared state.

Provides cross-task storm detection by maintaining:
- A shared sliding-window alert counter (all tasks contribute)
- A shared storm-active flag (all tasks read the same state)
- Shared group suppression tracking (prevents duplicate processing across tasks)

Redis key patterns:
    storm:counter:{minute_bucket}  → INCR + EXPIRE (alert rate tracking)
    storm:active                   → SET/DEL (storm mode flag)
    storm:group:{alert}:{service}  → SET + EXPIRE (group suppression)
    storm:metrics:suppressed       → INCR (total suppressed counter)

All operations have sub-millisecond latency and are atomic.
Falls back to in-memory if Redis is unavailable.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RedisStormState:
    """Redis-backed shared state for storm detection.

    Used by StormDetector when Redis is available. All ECS tasks
    share the same alert rate counter and storm state, ensuring
    consistent storm detection regardless of which task receives
    the alert.
    """

    def __init__(self, redis_client, window_seconds: int = 60) -> None:
        """Initialize Redis storm state.

        Args:
            redis_client: A connected redis.Redis instance.
            window_seconds: Sliding window size for rate measurement.
        """
        self._redis = redis_client
        self._window_seconds = window_seconds

    def increment_alert_count(self) -> int:
        """Increment the current minute's alert counter.

        Uses a per-minute bucket key with auto-expiry for natural
        sliding window behavior.

        Returns:
            Current count for this minute bucket.
        """
        bucket = int(time.time() // 60)
        key = f"storm:counter:{bucket}"
        try:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self._window_seconds + 60)  # Extra 60s buffer
            results = pipe.execute()
            return results[0]
        except Exception as e:
            logger.debug("Redis storm INCR failed: %s", e)
            return 0

    def get_current_rate(self) -> int:
        """Get the total alert count across the sliding window.

        Sums all minute-bucket counters within the window.

        Returns:
            Total alerts in the current window across all tasks.
        """
        now = int(time.time() // 60)
        buckets = self._window_seconds // 60 or 1
        keys = [f"storm:counter:{now - i}" for i in range(buckets)]
        try:
            pipe = self._redis.pipeline()
            for key in keys:
                pipe.get(key)
            results = pipe.execute()
            return sum(int(r) for r in results if r is not None)
        except Exception as e:
            logger.debug("Redis storm rate check failed: %s", e)
            return 0

    def set_storm_active(self, active: bool) -> None:
        """Set the global storm-active flag.

        All tasks read this flag to determine storm mode.

        Args:
            active: Whether storm mode should be active.
        """
        try:
            if active:
                self._redis.set("storm:active", "1")
            else:
                self._redis.delete("storm:active")
        except Exception as e:
            logger.debug("Redis storm flag set failed: %s", e)

    def is_storm_active(self) -> bool:
        """Check if storm mode is globally active."""
        try:
            return self._redis.get("storm:active") == "1"
        except Exception:
            return False

    def check_group_suppression(
        self, alert_name: str, service_name: str, suppression_window: int
    ) -> bool:
        """Check if a group is already being processed (suppressed).

        Uses SET NX (set-if-not-exists) for atomic check-and-set.

        Args:
            alert_name: Alert name for the group key.
            service_name: Service name for the group key.
            suppression_window: Seconds to suppress duplicates.

        Returns:
            True if the group was ALREADY suppressed (should not process).
            False if this is the first for this group (should process).
        """
        key = f"storm:group:{alert_name}:{service_name}"
        try:
            # SET NX with expiry: returns True if key was SET (we're first)
            was_set = self._redis.set(key, "1", nx=True, ex=suppression_window)
            return not was_set  # If not set, it already existed → suppressed
        except Exception as e:
            logger.debug("Redis group suppression check failed: %s", e)
            return False  # Fail-open: process the alert

    def increment_suppressed(self) -> int:
        """Increment the global suppressed alert counter.

        Returns:
            Total suppressed alerts across all tasks.
        """
        try:
            return self._redis.incr("storm:metrics:suppressed")
        except Exception:
            return 0

    def get_suppressed_total(self) -> int:
        """Get total suppressed alerts across all tasks."""
        try:
            val = self._redis.get("storm:metrics:suppressed")
            return int(val) if val else 0
        except Exception:
            return 0
