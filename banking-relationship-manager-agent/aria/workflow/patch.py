from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PatchOperation:
    field: str
    value: Any = None
    action: str = "set"


@dataclass(frozen=True)
class StatePatch:
    field: str | None = None
    value: Any = None
    reason: str = "manual_update"
    operations: tuple[PatchOperation, ...] = ()

    @classmethod
    def multi(
        cls,
        operations: list[tuple[str, Any]] | tuple[tuple[str, Any], ...],
        *,
        reason: str = "manual_update",
    ) -> StatePatch:
        return cls(
            reason=reason,
            operations=tuple(PatchOperation(field, value) for field, value in operations),
        )

    def normalized_operations(self) -> tuple[PatchOperation, ...]:
        if self.operations:
            return self.operations
        if self.field is None:
            return ()
        return (PatchOperation(self.field, self.value),)
