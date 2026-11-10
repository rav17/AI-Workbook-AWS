from __future__ import annotations


class WorkflowDependencyGraph:
    _dependencies = {
        "client_profile": {"risk_appetite"},
        "risk_appetite": {"risk_questionnaire"},
        "kyc_status": {"product_recommendation"},
        "risk_questionnaire": {"product_recommendation"},
        "product_recommendation": set(),
    }
    _reasons = {
        "client_profile": "client_profile_changed",
        "risk_appetite": "risk_profile_changed",
        "kyc_status": "kyc_status_changed",
        "risk_questionnaire": "risk_questionnaire_changed",
    }

    def invalidates_for(self, field: str) -> set[str]:
        affected: set[str] = set()
        pending = list(self._dependencies.get(field, set()))
        while pending:
            dependent = pending.pop()
            if dependent in affected:
                continue
            affected.add(dependent)
            pending.extend(self._dependencies.get(dependent, set()))
        return affected

    def reason_for(self, field: str) -> str:
        return self._reasons.get(field, "workflow_dependency_changed")
