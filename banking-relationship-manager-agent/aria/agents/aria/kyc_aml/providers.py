from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from aria.agents.aria.kyc_aml.models import (
    AMLAssessment,
    CompliancePolicy,
    DocumentReference,
    ExtractedFieldObservation,
    VerificationObservation,
)


class DocumentExtractor(Protocol):
    def extract(self, document: DocumentReference) -> Sequence[ExtractedFieldObservation]: ...


class IdentityVerificationProvider(Protocol):
    def verify(
        self,
        subject_id: str,
        fields: Sequence[ExtractedFieldObservation],
    ) -> Sequence[VerificationObservation]: ...


class CompliancePolicyProvider(Protocol):
    def get_policy(self, jurisdiction: str, request_reason: str) -> CompliancePolicy | None: ...


class AMLFindingProvider(Protocol):
    def assess(self, subject_id: str) -> AMLAssessment: ...
