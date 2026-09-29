from __future__ import annotations

from dataclasses import dataclass, field

from aria.workflow.patch import StatePatch


@dataclass
class WorkflowState:
    client_id: str
    workflow_version: int = 1
    risk_appetite: str | None = None
    needs: list[str] = field(default_factory=list)
    segment: str | None = None
    family_status: str | None = None

    def apply_patch(self, patch: StatePatch) -> WorkflowState:
        if patch.field == "workflow_version":
            self.workflow_version = int(patch.value)
        else:
            setattr(self, patch.field, patch.value)
        self.workflow_version += 1
        return self
