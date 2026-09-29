"""Redis client singleton for shared state across ECS tasks.

Provides a lazily-initialized Redis connection pool that all shared-state
components share. Gracefully degrades to None if Redis is unavailable,
allowing callers to fall back to in-memory state.

Configuration:
    REDIS_URL: Redis connection URL (e.g., "redis://aiops-cache.xxxxx.use1.cache.amazonaws.com:6379")
    REDIS_SSL: "true" for TLS connections (ElastiCache in-transit encryption)
    REDIS_CONNECT_TIMEOUT: Connection timeout in seconds (default: 2)
    REDIS_SOCKET_TIMEOUT: Socket timeout in seconds (default: 1)

If redis package is not installed, all operations gracefully return None/defaults.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_initialization_attempted = False


def get_redis_client():
    """Get the shared Redis client (lazily initialized).

    Returns:
        A redis.Redis instance if connected, None if unavailable.
    """
    global _redis_client, _initialization_attempted

    if _initialization_attempted:
        return _redis_client

    _initialization_attempted = True

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        logger.info(
            "REDIS_URL not set — shared state will use in-memory fallback "
            "(single-task mode only)"
        )
        return None

    try:
        import redis

        use_ssl = os.environ.get("REDIS_SSL", "false").lower() in ("true", "1", "yes")
        connect_timeout = float(os.environ.get("REDIS_CONNECT_TIMEOUT", "2"))
        socket_timeout = float(os.environ.get("REDIS_SOCKET_TIMEOUT", "1"))

        _redis_client = redis.Redis.from_url(
            redis_url,
            ssl=use_ssl,
            socket_connect_timeout=connect_timeout,
            socket_timeout=socket_timeout,
            decode_responses=True,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        # Verify connectivity
        _redis_client.ping()
        logger.info("Redis connected: %s (ssl=%s)", redis_url.split("@")[-1], use_ssl)
        return _redis_client

    except ImportError:
        logger.warning(
            "redis package not installed — shared state will use in-memory fallback. "
            "Install with: pip install redis"
        )
        return None
    except Exception as e:
        logger.warning(
            "Redis connection failed (non-fatal, using in-memory fallback): %s", e
        )
        _redis_client = None
        return None


def is_redis_available() -> bool:
    """Check if Redis is available and connected."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.ping()
        return True
    except Exception:
        return False
