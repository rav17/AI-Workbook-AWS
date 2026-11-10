from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal

from aria.agents.aria.kyc_aml.models import (
    AMLAssessment,
    AMLFinding,
    ComplianceAssessment,
    CompliancePolicy,
    DocumentReference,
    ExtractedFieldObservation,
    FieldVerificationResult,
    VerificationObservation,
)
from aria.agents.aria.kyc_aml.providers import (
    AMLFindingProvider,
    CompliancePolicyProvider,
    DocumentExtractor,
    IdentityVerificationProvider,
)
from aria.observability import Observability


class ComplianceVerifier:
    """Coordinates injected providers without issuing a compliance approval."""

    def __init__(
        self,
        *,
        document_extractor: DocumentExtractor | None,
        identity_verifier: IdentityVerificationProvider | None,
        policy_provider: CompliancePolicyProvider | None,
        aml_provider: AMLFindingProvider | None,
    ) -> None:
        self.document_extractor = document_extractor
        self.identity_verifier = identity_verifier
        self.policy_provider = policy_provider
        self.aml_provider = aml_provider
        self._observability = Observability()

    def _result(
        self,
        *,
        subject_id: str,
        status: Literal["evidence_consistent", "review_required", "unassessed"],
        correlation_id: str | None,
        reason_codes: list[str],
        field_results: list[FieldVerificationResult] | None = None,
        aml_findings: list[AMLFinding] | None = None,
        aml_status: Literal["clear", "findings", "unassessed"] = "unassessed",
        policy_version: str | None = None,
    ) -> ComplianceAssessment:
        self._observability.emit_operation(
            "compliance.assessment",
            {
                "subject_hash": hashlib.sha256(subject_id.encode("utf-8")).hexdigest()[:16],
                "status": status,
                "reason_codes": reason_codes,
                "field_result_count": len(field_results or []),
                "aml_finding_count": len(aml_findings or []),
                "policy_version": policy_version,
            },
            correlation_id=correlation_id,
            status="review_required" if status != "evidence_consistent" else "success",
        )
        return ComplianceAssessment(
            assessment_id=uuid.uuid4().hex,
            correlation_id=correlation_id,
            status=status,
            field_results=field_results or [],
            aml_findings=aml_findings or [],
            aml_status=aml_status,
            policy_version=policy_version,
            reason_codes=reason_codes,
            requires_human_review=True,
            recommended_kyc_status=None,
        )

    def assess(
        self,
        subject_id: str,
        documents: Sequence[DocumentReference],
        *,
        request_reason: str = "kyc_review",
        correlation_id: str | None = None,
    ) -> ComplianceAssessment:
        if not subject_id.strip() or not documents:
            return self._result(
                subject_id=subject_id or "unknown",
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=["missing_subject_or_document"],
            )
        if self.document_extractor is None or self.identity_verifier is None:
            return self._result(
                subject_id=subject_id,
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=["verification_provider_unavailable"],
            )

        jurisdictions = {document.jurisdiction for document in documents}
        if len(jurisdictions) != 1:
            return self._result(
                subject_id=subject_id,
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=["mixed_document_jurisdictions"],
            )
        jurisdiction = next(iter(jurisdictions))

        try:
            raw_policy = (
                self.policy_provider.get_policy(jurisdiction, request_reason)
                if self.policy_provider is not None
                else None
            )
            policy = CompliancePolicy.model_validate(raw_policy) if raw_policy is not None else None
        except Exception:
            policy = None
        if policy is None:
            return self._result(
                subject_id=subject_id,
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=["policy_unavailable"],
            )
        now = datetime.now(UTC)
        if now < policy.effective_from or now > policy.effective_to:
            return self._result(
                subject_id=subject_id,
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=["policy_not_current"],
                policy_version=policy.version,
            )
        if self.aml_provider is None:
            return self._result(
                subject_id=subject_id,
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=["aml_provider_unavailable"],
                policy_version=policy.version,
            )
        if policy.jurisdiction != jurisdiction or any(
            document.document_type not in policy.supported_document_types for document in documents
        ):
            return self._result(
                subject_id=subject_id,
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=["document_or_jurisdiction_unsupported"],
                policy_version=policy.version,
            )

        try:
            document_extractor = self.document_extractor
            identity_verifier = self.identity_verifier
            aml_provider = self.aml_provider
            raw_extracted = [
                observation
                for document in documents
                for observation in document_extractor.extract(document)
            ]
            extracted = [
                ExtractedFieldObservation.model_validate(observation)
                for observation in raw_extracted
            ]
            raw_source_observations = identity_verifier.verify(subject_id, extracted)
            source_observations = [
                VerificationObservation.model_validate(observation)
                for observation in raw_source_observations
            ]
            aml_result = AMLAssessment.model_validate(aml_provider.assess(subject_id))
        except Exception:
            return self._result(
                subject_id=subject_id,
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=["provider_error"],
                policy_version=policy.version,
            )

        field_results = self._compare_fields(policy, extracted, source_observations)
        reasons = [result.reason_code for result in field_results if result.status != "verified"]
        if aml_result.status == "incomplete":
            return self._result(
                subject_id=subject_id,
                status="unassessed",
                correlation_id=correlation_id,
                reason_codes=[*reasons, "aml_assessment_incomplete"],
                field_results=field_results,
                aml_findings=aml_result.findings,
                aml_status="unassessed",
                policy_version=policy.version,
            )
        if aml_result.findings:
            reasons.append("aml_findings_require_review")
        status: Literal["evidence_consistent", "review_required"] = (
            "review_required" if reasons else "evidence_consistent"
        )
        return self._result(
            subject_id=subject_id,
            status=status,
            correlation_id=correlation_id,
            reason_codes=reasons or ["evidence_consistent_policy_review_required"],
            field_results=field_results,
            aml_findings=aml_result.findings,
            aml_status=aml_result.status,
            policy_version=policy.version,
        )

    @staticmethod
    def _compare_fields(
        policy: CompliancePolicy,
        extracted: Sequence[ExtractedFieldObservation],
        sources: Sequence[VerificationObservation],
    ) -> list[FieldVerificationResult]:
        results: list[FieldVerificationResult] = []
        for field_name in policy.required_fields:
            field_observations = [item for item in extracted if item.field_name == field_name]
            expected_sources = policy.required_sources_by_field.get(field_name, [])
            if not expected_sources:
                results.append(
                    FieldVerificationResult(
                        field_name=field_name,
                        status="unconfigured",
                        reason_code="required_sources_unconfigured",
                    )
                )
                continue
            if not field_observations:
                results.append(
                    FieldVerificationResult(
                        field_name=field_name,
                        status="missing",
                        reason_code="document_field_missing",
                    )
                )
                continue
            if any(
                item.confidence < policy.minimum_extraction_confidence or not item.comparison_token
                for item in field_observations
            ):
                results.append(
                    FieldVerificationResult(
                        field_name=field_name,
                        status="low_confidence",
                        evidence_refs=[item.document_ref for item in field_observations],
                        reason_code="extraction_confidence_insufficient",
                    )
                )
                continue
            if len({item.comparison_token for item in field_observations}) != 1:
                results.append(
                    FieldVerificationResult(
                        field_name=field_name,
                        status="conflict",
                        evidence_refs=[item.document_ref for item in field_observations],
                        reason_code="documents_conflict",
                    )
                )
                continue

            field_sources = [item for item in sources if item.field_name == field_name]
            by_source = {item.source_id: item for item in field_sources}
            evidence_refs = [item.document_ref for item in field_observations]
            evidence_refs.extend(item.source_id for item in field_sources)
            missing_source = False
            conflict = False
            for source_id in expected_sources:
                observation = by_source.get(source_id)
                if observation is None or observation.status in {"missing", "unavailable"}:
                    missing_source = True
                    continue
                if observation.status in {"stale", "invalid"}:
                    conflict = True
                    continue
                if any(
                    observation.comparison_token != item.comparison_token
                    for item in field_observations
                ):
                    conflict = True
            if conflict:
                result_status: Literal["conflict", "source_unavailable", "verified"] = "conflict"
                reason_code = "source_conflict_or_invalid"
            elif missing_source:
                result_status = "source_unavailable"
                reason_code = "required_source_missing"
            else:
                result_status = "verified"
                reason_code = "configured_sources_match"
            results.append(
                FieldVerificationResult(
                    field_name=field_name,
                    status=result_status,
                    evidence_refs=evidence_refs,
                    reason_code=reason_code,
                )
            )
        return results
