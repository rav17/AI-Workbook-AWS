from __future__ import annotations

from dataclasses import dataclass, field

from aria.workflow.patch import StatePatch


@dataclass
class WorkflowState:
    client_id: str
    workflow_version: int = 1
    revision: int | None = None
    status: str = "not_started"
    current_step: str | None = None
    risk_appetite: str | None = None
    needs: list[str] = field(default_factory=list)
    segment: str | None = None
    family_status: str | None = None

    def __post_init__(self) -> None:
        if self.revision is None:
            self.revision = self.workflow_version
        else:
            self.workflow_version = self.revision

    def apply_patch(
        self,
        patch: StatePatch,
        *,
        expected_revision: int | None = None,
        locked_fields: set[str] | None = None,
    ) -> WorkflowState:
        current_revision = self.revision or self.workflow_version
        if expected_revision is not None and expected_revision != current_revision:
            raise RuntimeError("stale_revision")

        allowed_fields = {
            "client_id",
            "status",
            "current_step",
            "risk_appetite",
            "needs",
            "segment",
            "family_status",
        }
        locked_fields = locked_fields or set()
        operations = patch.normalized_operations()
        for operation in operations:
            if operation.field not in allowed_fields:
                raise ValueError("unknown_field")
            if operation.field in locked_fields:
                raise ValueError("locked_field")
            if operation.action not in {"set", "clear"}:
                raise ValueError("invalid_operation")

        for operation in operations:
            setattr(self, operation.field, None if operation.action == "clear" else operation.value)

        self.revision = current_revision + 1
        self.workflow_version = self.revision
        return self
