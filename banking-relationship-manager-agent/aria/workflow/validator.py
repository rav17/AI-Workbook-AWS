from __future__ import annotations


class WorkflowValidator:
    def validate(self, state: dict) -> dict:
        errors: list[str] = []

        if not state.get("client_id"):
            errors.append("client_id is required")

        if state.get("name") is not None and not str(state.get("name")).strip():
            errors.append("name cannot be blank")

        if state.get("risk_appetite") not in {None, "conservative", "moderate", "high"}:
            errors.append("invalid risk_appetite")

        if state.get("segment") is not None and not str(state.get("segment")).strip():
            errors.append("segment cannot be blank")

        return {"valid": not errors, "errors": errors}

    def validate_patch(
        self, current_state: dict, proposed_update: dict, locked_fields: set[str] | None = None
    ) -> dict:
        errors: list[str] = []
        locked_fields = locked_fields or set()

        for field in locked_fields:
            if field in proposed_update and current_state.get(field) != proposed_update.get(field):
                errors.append(f"{field} is locked and cannot be changed")

        if "client_id" in proposed_update and not str(proposed_update.get("client_id", "")).strip():
            errors.append("client_id is required")

        if "risk_appetite" in proposed_update and proposed_update.get("risk_appetite") not in {
            "conservative",
            "moderate",
            "high",
        }:
            errors.append("invalid risk_appetite")

        return {"valid": not errors, "errors": errors}
