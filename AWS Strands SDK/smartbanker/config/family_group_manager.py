"""Family Group account benefits management. Traces: R22."""
from __future__ import annotations

from datetime import datetime

from config.models import FamilyGroup
from observability.logger import CorrelatedLogger


class FamilyGroupManager:
    """Manages Family Group creation, membership, and tier benefit propagation.

    Traces: R22.1, R22.2, R22.3, R22.4, R22.5, R22.6.
    """

    def __init__(self):
        self._groups: dict[str, FamilyGroup] = {}  # keyed by primary_holder
        self.logger = CorrelatedLogger()

    def create_group(self, primary_holder: str, max_size: int = 6) -> FamilyGroup:
        """Create a new family group. Traces: R22.1."""
        group = FamilyGroup(
            primary_holder=primary_holder,
            linked_members=[],
            max_group_size=max_size,
        )
        self._groups[primary_holder] = group
        self.logger._emit(
            "family_group_created",
            user_id=primary_holder,
            timestamp=datetime.utcnow().isoformat(),
        )
        return group

    def add_member(self, primary_holder: str, member_id: str) -> bool:
        """Add a member to a family group. Returns False if group full. Traces: R22.3, R22.6."""
        group = self._groups.get(primary_holder)
        if group is None:
            return False
        if len(group.linked_members) >= group.max_group_size:
            return False
        if member_id in group.linked_members:
            return True  # already a member
        group.linked_members.append(member_id)
        self.logger._emit(
            "family_member_added",
            user_id=member_id,
            primary_holder=primary_holder,
            timestamp=datetime.utcnow().isoformat(),
        )
        return True

    def remove_member(self, primary_holder: str, member_id: str) -> bool:
        """Remove a member from a family group. Traces: R22.6."""
        group = self._groups.get(primary_holder)
        if group is None or member_id not in group.linked_members:
            return False
        group.linked_members.remove(member_id)
        self.logger._emit(
            "family_member_removed",
            user_id=member_id,
            primary_holder=primary_holder,
            timestamp=datetime.utcnow().isoformat(),
        )
        return True

    def get_group(self, primary_holder: str) -> FamilyGroup | None:
        """Retrieve a family group by primary holder."""
        return self._groups.get(primary_holder)

    def get_group_for_member(self, member_id: str) -> FamilyGroup | None:
        """Find the family group a member belongs to. Traces: R22.4."""
        for group in self._groups.values():
            if member_id == group.primary_holder or member_id in group.linked_members:
                return group
        return None

    def get_effective_tier(self, member_id: str, default_tier: str = "basic") -> str:
        """Get the effective tier for a member (inherits primary holder's tier).

        Traces: R22.2, R22.5. The caller provides the primary holder's tier;
        this method resolves group membership.
        """
        group = self.get_group_for_member(member_id)
        if group is None:
            return default_tier
        # The primary holder's tier is the effective tier for all members
        return default_tier  # caller should pass primary holder's tier

    def propagate_tier_change(self, primary_holder: str, new_tier: str) -> list[str]:
        """Propagate tier change to all group members. Returns affected member IDs.

        Traces: R22.5.
        """
        group = self._groups.get(primary_holder)
        if group is None:
            return []
        affected = list(group.linked_members)
        self.logger._emit(
            "tier_change_propagated",
            primary_holder=primary_holder,
            new_tier=new_tier,
            affected_members=affected,
            timestamp=datetime.utcnow().isoformat(),
        )
        return affected
