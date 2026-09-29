from __future__ import annotations


class WorkflowDependencyGraph:
    _dependencies = {
        "client_profile": {"client_profile"},
        "risk_appetite": {"risk_questionnaire", "product_recommendation"},
        "kyc_status": {"product_recommendation"},
        "risk_questionnaire": {"product_recommendation"},
        "product_recommendation": set(),
    }

    def invalidates_for(self, field: str) -> set[str]:
        return set(self._dependencies.get(field, set()))
