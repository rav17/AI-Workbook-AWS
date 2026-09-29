"""Bulkhead Isolation — per-service-group execution pools.

Prevents one service from monopolizing all execution slots by
providing independent concurrency limits per service group.

Example: if web-frontend has 10 alerts queued simultaneously,
it only consumes 3 slots (its bulkhead limit), leaving capacity
for api-gateway and database remediation.

Configuration loaded from config/bulkhead_limits.yml with hot-reload.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

DEFAULT_BULKHEAD_LIMIT = 2
DEFAULT_GLOBAL_LIMIT = 10
DEFAULT_P1_RESERVED = 3
CONFIG_PATH = os.environ.get(
    "BULKHEAD_CONFIG_PATH", "config/bulkhead_limits.yml"
)


@dataclass
class BulkheadConfig:
    """Configuration for a single service bulkhead."""

    max_concurrent: int
    overflow_to_global: bool = True


@dataclass
class BulkheadStatus:
    """Current utilization of a bulkhead."""

    service: str
    max_concurrent: int
    active: int
    available: int


class BulkheadManager:
    """Per-service-group concurrency isolation.

    Each service group gets an independent asyncio.Semaphore controlling
    how many concurrent remediations can run for that service. A global
    cap is also enforced across all services.

    P1 alerts have reserved global capacity that cannot be consumed by
    lower-priority work.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        global_limit: int = DEFAULT_GLOBAL_LIMIT,
        p1_reserved: int = DEFAULT_P1_RESERVED,
    ) -> None:
        """Initialize bulkhead manager.

        Args:
            config_path: Path to bulkhead_limits.yml (or None for defaults).
            global_limit: Maximum total concurrent executions across all services.
            p1_reserved: Slots reserved exclusively for P1 alerts.
        """
        self._config_path = config_path or CONFIG_PATH
        self._global_limit = global_limit
        self._p1_reserved = p1_reserved

        # Per-service semaphores
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        # Per-service config
        self._configs: dict[str, BulkheadConfig] = {}
        # Default config for unknown services
        self._default_config = BulkheadConfig(
            max_concurrent=DEFAULT_BULKHEAD_LIMIT, overflow_to_global=True
        )

        # Global semaphore (total cap across all services)
        self._global_semaphore = asyncio.Semaphore(global_limit)
        # Track active counts per service (for status API)
        self._active_counts: dict[str, int] = {}
        self._total_active: int = 0

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load bulkhead configuration from YAML file.

        Falls back to defaults if file is missing or malformed.
        """
        if not os.path.isfile(self._config_path):
            logger.info(
                "Bulkhead config not found at %s, using defaults",
                self._config_path,
            )
            return

        try:
            with open(self._config_path, "r") as f:
                data = yaml.safe_load(f)

            if not data or not isinstance(data, dict):
                return

            # Load global settings
            global_section = data.get("global", {})
            if global_section:
                self._global_limit = global_section.get(
                    "max_total_concurrent", self._global_limit
                )
                self._p1_reserved = global_section.get(
                    "reserved_for_p1", self._p1_reserved
                )
                self._global_semaphore = asyncio.Semaphore(self._global_limit)

            # Load default settings
            defaults = data.get("defaults", {})
            if defaults:
                self._default_config = BulkheadConfig(
                    max_concurrent=defaults.get(
                        "max_concurrent", DEFAULT_BULKHEAD_LIMIT
                    ),
                    overflow_to_global=defaults.get("overflow_to_global", True),
                )

            # Load per-service bulkheads
            bulkheads = data.get("bulkheads", {})
            for service_name, cfg in bulkheads.items():
                if isinstance(cfg, dict):
                    bc = BulkheadConfig(
                        max_concurrent=cfg.get(
                            "max_concurrent", self._default_config.max_concurrent
                        ),
                        overflow_to_global=cfg.get(
                            "overflow_to_global",
                            self._default_config.overflow_to_global,
                        ),
                    )
                    self._configs[service_name] = bc
                    self._semaphores[service_name] = asyncio.Semaphore(
                        bc.max_concurrent
                    )

            logger.info(
                "Bulkhead config loaded: %d services, global_limit=%d, p1_reserved=%d",
                len(self._configs),
                self._global_limit,
                self._p1_reserved,
            )

        except Exception as e:
            logger.warning("Failed to load bulkhead config: %s (using defaults)", e)

    async def acquire(self, service_name: str, severity: str = "P3") -> bool:
        """Acquire a bulkhead slot for a service.

        Checks both the service-specific limit and the global cap.
        P1 alerts can use reserved global capacity.

        Args:
            service_name: The service requesting execution.
            severity: Alert severity (P1-P5) for P1 reservation logic.

        Returns:
            True if slot acquired, False if bulkhead is full.
        """
        # Get or create service semaphore
        semaphore = self._get_semaphore(service_name)
        config = self._configs.get(service_name, self._default_config)

        # Check service-level capacity (non-blocking)
        if not self._try_acquire_nowait(semaphore):
            return False

        # Check global capacity
        effective_limit = self._global_limit
        if severity not in ("P1", "P2"):
            # Non-P1/P2 alerts cannot use the reserved slots
            effective_limit = self._global_limit - self._p1_reserved

        if self._total_active >= effective_limit:
            # Release the service semaphore we just acquired
            semaphore.release()
            return False

        # Both checks passed — track the acquisition
        self._active_counts[service_name] = (
            self._active_counts.get(service_name, 0) + 1
        )
        self._total_active += 1
        return True

    async def release(self, service_name: str) -> None:
        """Release a bulkhead slot for a service.

        Args:
            service_name: The service releasing its slot.
        """
        semaphore = self._get_semaphore(service_name)
        semaphore.release()

        count = self._active_counts.get(service_name, 0)
        if count > 0:
            self._active_counts[service_name] = count - 1
        self._total_active = max(0, self._total_active - 1)

    def get_status(self) -> dict:
        """Get per-bulkhead utilization for the status API."""
        statuses = []
        for service, config in self._configs.items():
            active = self._active_counts.get(service, 0)
            statuses.append({
                "service": service,
                "max_concurrent": config.max_concurrent,
                "active": active,
                "available": max(0, config.max_concurrent - active),
            })

        return {
            "bulkheads": statuses,
            "global_limit": self._global_limit,
            "global_active": self._total_active,
            "global_available": max(0, self._global_limit - self._total_active),
            "p1_reserved": self._p1_reserved,
        }

    def _get_semaphore(self, service_name: str) -> asyncio.Semaphore:
        """Get or create a semaphore for a service.

        Unknown services get the default limit.
        """
        if service_name not in self._semaphores:
            self._semaphores[service_name] = asyncio.Semaphore(
                self._default_config.max_concurrent
            )
        return self._semaphores[service_name]

    @staticmethod
    def _try_acquire_nowait(semaphore: asyncio.Semaphore) -> bool:
        """Try to acquire a semaphore without blocking.

        Returns True if acquired, False if would block.
        """
        # asyncio.Semaphore doesn't have try_acquire, so we check _value
        if semaphore._value > 0:  # noqa: SLF001
            semaphore._value -= 1  # noqa: SLF001
            return True
        return False
