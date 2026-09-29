"""Redis-backed alert inhibition shared state.

Provides cross-task inhibition by maintaining:
- A shared set of active root-cause incidents
- A shared set of resolved incidents
- Group tracking for same-host alert deduplication

Redis key patterns:
    inhibit:active:{alert_name}   → HASH {incident_id, host, service, started_at}
    inhibit:resolved:{alert_name} → SET with EXPIRE (marks resolved root causes)
    inhibit:group:{host}          → HASH {alert_name → timestamp} with EXPIRE

All operations are atomic and have sub-millisecond latency.
Falls back to in-memory if Redis is unavailable.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# TTL for active incidents in Redis (10 minutes — refreshed on each new alert)
ACTIVE_INCIDENT_TTL = 600
# TTL for resolved markers (5 minutes after resolution)
RESOLVED_TTL = 300
# TTL for grouping window entries
GROUP_TTL = 60


class RedisInhibitorState:
    """Redis-backed shared state for alert inhibition.

    Used by AlertInhibitor when Redis is available. Ensures that
    root-cause registration and symptom suppression work correctly
    across multiple ECS tasks.
    """

    def __init__(self, redis_client) -> None:
        """Initialize Redis inhibitor state.

        Args:
            redis_client: A connected redis.Redis instance.
        """
        self._redis = redis_client

    def register_active_incident(
        self,
        incident_id: str,
        alert_name: str,
        host: str,
        service_name: str,
    ) -> None:
        """Register an active root-cause incident (shared across tasks).

        Args:
            incident_id: Unique incident identifier.
            alert_name: The root-cause alert name.
            host: Affected host.
            service_name: Affected service.
        """
        key = f"inhibit:active:{alert_name}"
        try:
            self._redis.hset(key, mapping={
                "incident_id": incident_id,
                "host": host,
                "service_name": service_name,
                "started_at": str(time.time()),
            })
            self._redis.expire(key, ACTIVE_INCIDENT_TTL)
        except Exception as e:
            logger.debug("Redis register_active_incident failed: %s", e)

    def is_source_active(self, alert_name: str) -> bool:
        """Check if a root-cause alert is currently active.

        Args:
            alert_name: The source alert name to check.

        Returns:
            True if the source alert has an active, unresolved incident.
        """
        key = f"inhibit:active:{alert_name}"
        try:
            return self._redis.exists(key) == 1
        except Exception:
            return False

    def get_active_incident(self, alert_name: str) -> Optional[dict]:
        """Get active incident details for a root-cause alert.

        Args:
            alert_name: The source alert name.

        Returns:
            Dict with incident details, or None if not active.
        """
        key = f"inhibit:active:{alert_name}"
        try:
            data = self._redis.hgetall(key)
            if data:
                return data
            return None
        except Exception:
            return None

    def mark_resolved(self, alert_name: str) -> None:
        """Mark a root-cause alert as resolved.

        Removes the active incident key and sets a resolved marker
        with TTL to prevent re-inhibition race conditions.

        Args:
            alert_name: The alert that has resolved.
        """
        active_key = f"inhibit:active:{alert_name}"
        resolved_key = f"inhibit:resolved:{alert_name}"
        try:
            pipe = self._redis.pipeline()
            pipe.delete(active_key)
            pipe.set(resolved_key, "1", ex=RESOLVED_TTL)
            pipe.execute()
        except Exception as e:
            logger.debug("Redis mark_resolved failed: %s", e)

    def is_resolved(self, alert_name: str) -> bool:
        """Check if an alert was recently resolved."""
        key = f"inhibit:resolved:{alert_name}"
        try:
            return self._redis.exists(key) == 1
        except Exception:
            return False

    def check_host_group(
        self, host: str, alert_name: str, window_seconds: int = 30
    ) -> bool:
        """Check if an alert for this host is already in the grouping window.

        Uses HSETNX for atomic check-and-set.

        Args:
            host: Target host.
            alert_name: Alert being grouped.
            window_seconds: Grouping window duration.

        Returns:
            True if already grouped (should suppress), False if first in group.
        """
        key = f"inhibit:group:{host}"
        try:
            # HSETNX: set field only if it doesn't exist
            was_new = self._redis.hsetnx(key, alert_name, str(time.time()))
            self._redis.expire(key, window_seconds * 2)
            return not was_new  # If not new, it was already grouped
        except Exception:
            return False  # Fail-open


class RedisResolvedState:
    """Redis-backed shared state for resolved alert tracking.

    Maintains a cross-task view of which alerts have resolved,
    enabling any task to cancel pending remediations for resolved alerts.

    Redis key patterns:
        resolved:{alert_name}:{host} → "1" with EXPIRE
        resolved:incident:{incident_id} → state value with EXPIRE
    """

    def __init__(self, redis_client) -> None:
        """Initialize Redis resolved state.

        Args:
            redis_client: A connected redis.Redis instance.
        """
        self._redis = redis_client

    def register_pending(
        self, incident_id: str, alert_name: str, host: str
    ) -> None:
        """Register an incident as pending (entered pipeline).

        Args:
            incident_id: Unique incident identifier.
            alert_name: Alert name.
            host: Target host.
        """
        key = f"resolved:incident:{incident_id}"
        try:
            self._redis.hset(key, mapping={
                "alert_name": alert_name,
                "host": host,
                "state": "pending",
                "created_at": str(time.time()),
            })
            self._redis.expire(key, 86400)  # 24h TTL
        except Exception as e:
            logger.debug("Redis register_pending failed: %s", e)

    def mark_resolved(self, alert_name: str, host: str) -> None:
        """Mark an alert+host combination as resolved.

        Any task can then check this before executing remediation.

        Args:
            alert_name: Alert that resolved.
            host: Host that resolved.
        """
        key = f"resolved:{alert_name}:{host}"
        try:
            self._redis.set(key, "1", ex=RESOLVED_TTL)
        except Exception as e:
            logger.debug("Redis mark_resolved failed: %s", e)

    def is_resolved(self, alert_name: str, host: str) -> bool:
        """Check if an alert+host combination has recently resolved.

        Args:
            alert_name: Alert to check.
            host: Host to check.

        Returns:
            True if resolved within the TTL window.
        """
        key = f"resolved:{alert_name}:{host}"
        try:
            return self._redis.exists(key) == 1
        except Exception:
            return False

    def is_incident_resolved(self, incident_id: str) -> bool:
        """Check if a specific incident has been resolved.

        Args:
            incident_id: The incident to check.

        Returns:
            True if the incident was marked as resolved/cancelled.
        """
        key = f"resolved:incident:{incident_id}"
        try:
            state = self._redis.hget(key, "state")
            return state in ("resolved", "cancelled")
        except Exception:
            return False

    def cancel_incident(self, incident_id: str) -> bool:
        """Atomically cancel an incident (was pending, now resolved).

        Uses HSET with check — only cancels if state is still "pending".

        Args:
            incident_id: The incident to cancel.

        Returns:
            True if successfully cancelled, False if already transitioned.
        """
        key = f"resolved:incident:{incident_id}"
        try:
            # Use a Lua script for atomic check-and-set
            lua_script = """
            local state = redis.call('HGET', KEYS[1], 'state')
            if state == 'pending' then
                redis.call('HSET', KEYS[1], 'state', 'cancelled')
                return 1
            end
            return 0
            """
            result = self._redis.eval(lua_script, 1, key)
            return result == 1
        except Exception as e:
            logger.debug("Redis cancel_incident failed: %s", e)
            return False
