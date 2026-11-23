"""Priority Manager for tier-based task processing. Traces: R29."""
from __future__ import annotations

from config.models import ExecutionResult
from config.settings import PriorityConfig

# Canonical ordering of priority levels from lowest to highest.
_PRIORITY_ORDER = ["standard", "elevated", "high", "critical"]


class PriorityManager:
    """Assigns processing priority based on user Programme_Tier.

    Uses PriorityConfig for the tier-to-priority mapping and estimated
    processing times.  Traces: R29.1, R29.2, R29.4, R29.5.
    """

    def __init__(self, config: PriorityConfig | None = None):
        self.config = config or PriorityConfig()
        self.tier_priority_map = self.config.tier_priority_map
        self.estimated_times = self.config.estimated_processing_times

    # ------------------------------------------------------------------
    # R29.1 – Map tier to priority
    # ------------------------------------------------------------------

    def assign_priority(self, user_tier: str) -> str:
        """Map a user Programme_Tier to a processing priority level.

        Returns the mapped priority or ``"standard"`` for unknown tiers.
        """
        return self.tier_priority_map.get(user_tier, "standard")

    # ------------------------------------------------------------------
    # R29.4 – Estimated processing time
    # ------------------------------------------------------------------

    def get_estimated_time(self, priority_level: str) -> str:
        """Return the estimated processing time for *priority_level*.

        Falls back to the ``"standard"`` estimate when the level is
        unrecognised.
        """
        return self.estimated_times.get(
            priority_level,
            self.estimated_times.get("standard", "3-5 business days"),
        )

    # ------------------------------------------------------------------
    # R29.2 – Enrich ExecutionResult with priority metadata
    # ------------------------------------------------------------------

    def enrich_result(self, result: ExecutionResult, user_tier: str) -> ExecutionResult:
        """Add ``priority_level`` and ``estimated_processing_time`` to *result*.

        Mutates and returns the same ExecutionResult instance for
        convenience.
        """
        priority = self.assign_priority(user_tier)
        result.priority_level = priority
        result.estimated_processing_time = self.get_estimated_time(priority)
        return result

    # ------------------------------------------------------------------
    # R29.5 – Validate priority ordering invariant
    # ------------------------------------------------------------------

    def validate_priority_ordering(self, tier_a: str, tier_b: str) -> bool:
        """Return ``True`` if *tier_a* maps to an equal or higher priority than *tier_b*.

        Uses the canonical ordering: standard < elevated < high < critical.
        Unknown priority levels are treated as the lowest (index -1).
        """
        priority_a = self.assign_priority(tier_a)
        priority_b = self.assign_priority(tier_b)

        def _rank(p: str) -> int:
            try:
                return _PRIORITY_ORDER.index(p)
            except ValueError:
                return -1

        return _rank(priority_a) >= _rank(priority_b)
