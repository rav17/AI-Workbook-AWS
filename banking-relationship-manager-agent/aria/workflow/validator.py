from __future__ import annotations

from typing import Any


class WorkflowValidator:
    _allowed_patch_fields = {
        "client_id",
        "name",
        "risk_appetite",
        "segment",
        "needs",
        "family_status",
    }

    def validate(self, state: dict[str, Any]) -> dict[str, Any]:
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
        self,
        current_state: dict[str, Any],
        proposed_update: dict[str, Any],
        locked_fields: set[str] | None = None,
    ) -> dict[str, Any]:
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

    def validate_authorized_patch(
        self,
        current_state: dict[str, Any],
        proposed_update: dict[str, Any],
        *,
        authorized_fields: set[str] | None = None,
        immutable_fields: set[str] | None = None,
        locked_fields: set[str] | None = None,
        requires_confirmation: bool = False,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        authorized_fields = authorized_fields or self._allowed_patch_fields
        immutable_fields = immutable_fields or {"client_id"}

        unauthorized = set(proposed_update) - authorized_fields
        if unauthorized:
            return {
                "valid": False,
                "errors": ["unauthorized field update"],
                "reason_code": "unauthorized_field",
            }

        for field in immutable_fields:
            if field in proposed_update and proposed_update[field] != current_state.get(field):
                return {
                    "valid": False,
                    "errors": [f"{field} is immutable"],
                    "reason_code": "immutable_field",
                }

        if requires_confirmation and not confirmed:
            return {
                "valid": False,
                "errors": ["explicit confirmation is required"],
                "reason_code": "confirmation_required",
            }

        if str(current_state.get("kyc_status", "current")).lower() != "current":
            return {
                "valid": False,
                "errors": ["current KYC is required"],
                "reason_code": "kyc_required",
            }

        if str(current_state.get("aml_status", "clear")).lower() in {"flagged", "blocked"}:
            return {
                "valid": False,
                "errors": ["AML review is required"],
                "reason_code": "aml_review_required",
            }

        validation = self.validate_patch(current_state, proposed_update, locked_fields)
        if not validation["valid"]:
            validation["reason_code"] = "domain_rule_violation"
            return validation

        return {"valid": True, "errors": [], "reason_code": "accepted"}
