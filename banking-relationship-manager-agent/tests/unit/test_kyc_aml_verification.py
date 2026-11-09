from datetime import UTC, datetime

from aria.agents.aria.kyc_aml.models import (
    AMLAssessment,
    AMLFinding,
    CompliancePolicy,
    DocumentReference,
    ExtractedFieldObservation,
    VerificationObservation,
)
from aria.agents.aria.kyc_aml.verification import ComplianceVerifier


class FakeExtractor:
    def __init__(self, observations):
        self.observations = observations

    def extract(self, document):
        return self.observations


class FakeIdentityVerifier:
    def __init__(self, observations):
        self.observations = observations

    def verify(self, subject_id, fields):
        return self.observations


class FakePolicyProvider:
    def __init__(self, policy):
        self.policy = policy

    def get_policy(self, jurisdiction, request_reason):
        return self.policy


class FakeAMLProvider:
    def __init__(self, findings=()):
        self.findings = list(findings)

    def assess(self, subject_id):
        return AMLAssessment(
            status="findings" if self.findings else "clear",
            findings=self.findings,
            evidence_refs=["AML-SOURCE-1"],
        )


_DEFAULT_POLICY = object()


def _document():
    return DocumentReference(
        document_ref="DOC-REF-1",
        document_type="identity_document",
        jurisdiction="test-jurisdiction",
    )


def _policy():
    return CompliancePolicy(
        policy_id="TEST-POLICY",
        version="test-v1",
        jurisdiction="test-jurisdiction",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
        effective_to=datetime(2027, 1, 1, tzinfo=UTC),
        supported_document_types=["identity_document"],
        required_fields=["legal_name", "date_of_birth"],
        required_sources_by_field={
            "legal_name": ["customer_source"],
            "date_of_birth": ["customer_source"],
        },
        minimum_extraction_confidence=0.9,
    )


def _extracted():
    return [
        ExtractedFieldObservation(
            field_name="legal_name",
            masked_value="J*** D**",
            comparison_token="name-hash-1",
            confidence=0.99,
            document_ref="DOC-REF-1",
        ),
        ExtractedFieldObservation(
            field_name="date_of_birth",
            masked_value="****-**-14",
            comparison_token="dob-hash-1",
            confidence=0.98,
            document_ref="DOC-REF-1",
        ),
    ]


def _verified_sources(*, name_token="name-hash-1", dob_token="dob-hash-1"):
    return [
        VerificationObservation(
            field_name="legal_name",
            source_id="customer_source",
            masked_value="J*** D**",
            comparison_token=name_token,
            status="verified",
        ),
        VerificationObservation(
            field_name="date_of_birth",
            source_id="customer_source",
            masked_value="****-**-14",
            comparison_token=dob_token,
            status="verified",
        ),
    ]


def _verifier(*, policy=_DEFAULT_POLICY, extracted=None, sources=None, aml_findings=()):
    return ComplianceVerifier(
        document_extractor=FakeExtractor(_extracted() if extracted is None else extracted),
        identity_verifier=FakeIdentityVerifier(_verified_sources() if sources is None else sources),
        policy_provider=FakePolicyProvider(_policy() if policy is _DEFAULT_POLICY else policy),
        aml_provider=FakeAMLProvider(aml_findings),
    )


def test_missing_policy_returns_unassessed_and_requires_human_review():
    verifier = _verifier(policy=None)

    result = verifier.assess("verified-subject", [_document()])

    assert result.status == "unassessed"
    assert result.requires_human_review is True
    assert "policy_unavailable" in result.reason_codes
    assert result.recommended_kyc_status is None


def test_expired_policy_returns_unassessed():
    expired_policy = _policy().model_copy(update={"effective_to": datetime(2025, 1, 1, tzinfo=UTC)})
    result = _verifier(policy=expired_policy).assess("verified-subject", [_document()])

    assert result.status == "unassessed"
    assert "policy_not_current" in result.reason_codes


def test_missing_aml_provider_returns_unassessed_not_clear():
    verifier = ComplianceVerifier(
        document_extractor=FakeExtractor(_extracted()),
        identity_verifier=FakeIdentityVerifier(_verified_sources()),
        policy_provider=FakePolicyProvider(_policy()),
        aml_provider=None,
    )

    result = verifier.assess("verified-subject", [_document()])

    assert result.status == "unassessed"
    assert result.requires_human_review is True
    assert "aml_provider_unavailable" in result.reason_codes
    assert result.recommended_kyc_status is None


def test_matching_document_and_source_evidence_still_requires_human_decision():
    result = _verifier().assess("verified-subject", [_document()])

    assert result.status == "evidence_consistent"
    assert result.requires_human_review is True
    assert {field.status for field in result.field_results} == {"verified"}
    assert result.recommended_kyc_status is None
    assert result.aml_status == "clear"


def test_aml_clear_without_evidence_reference_is_rejected():
    class EvidenceFreeAMLProvider:
        def assess(self, subject_id):
            return AMLAssessment(status="clear", findings=[], evidence_refs=[])

    verifier = ComplianceVerifier(
        document_extractor=FakeExtractor(_extracted()),
        identity_verifier=FakeIdentityVerifier(_verified_sources()),
        policy_provider=FakePolicyProvider(_policy()),
        aml_provider=EvidenceFreeAMLProvider(),
    )
    result = verifier.assess("verified-subject", [_document()])

    assert result.status == "unassessed"
    assert "provider_error" in result.reason_codes


def test_incomplete_aml_assessment_returns_unassessed():
    class IncompleteAMLProvider:
        def assess(self, subject_id):
            return AMLAssessment(status="incomplete", evidence_refs=[])

    verifier = ComplianceVerifier(
        document_extractor=FakeExtractor(_extracted()),
        identity_verifier=FakeIdentityVerifier(_verified_sources()),
        policy_provider=FakePolicyProvider(_policy()),
        aml_provider=IncompleteAMLProvider(),
    )

    result = verifier.assess("verified-subject", [_document()])

    assert result.status == "unassessed"
    assert result.aml_status == "unassessed"
    assert "aml_assessment_incomplete" in result.reason_codes


def test_conflicting_source_observation_requires_review():
    result = _verifier(sources=_verified_sources(name_token="different-name-hash")).assess(
        "verified-subject", [_document()]
    )

    assert result.status == "review_required"
    assert result.requires_human_review is True
    assert any(field.status == "conflict" for field in result.field_results)
    assert result.recommended_kyc_status is None


def test_low_confidence_extraction_is_not_verified():
    observations = _extracted()
    observations[0] = observations[0].model_copy(update={"confidence": 0.2})

    result = _verifier(extracted=observations).assess("verified-subject", [_document()])

    assert result.status == "review_required"
    assert any(field.status == "low_confidence" for field in result.field_results)


def test_aml_finding_forces_human_review_without_clearing_kyc():
    finding = AMLFinding(
        finding_code="TEST_AML_SIGNAL",
        severity="high",
        evidence_ref="AML-SOURCE-1",
        summary="Synthetic test finding",
    )

    result = _verifier(aml_findings=[finding]).assess("verified-subject", [_document()])

    assert result.status == "review_required"
    assert result.requires_human_review is True
    assert result.aml_findings[0].finding_code == "TEST_AML_SIGNAL"
    assert result.recommended_kyc_status is None


def test_provider_failure_returns_unassessed_without_leaking_subject_or_document(caplog):
    class FailedExtractor:
        def extract(self, document):
            raise TimeoutError("source unavailable")

    verifier = ComplianceVerifier(
        document_extractor=FailedExtractor(),
        identity_verifier=FakeIdentityVerifier([]),
        policy_provider=FakePolicyProvider(_policy()),
        aml_provider=FakeAMLProvider(),
    )

    with caplog.at_level("INFO", logger="aria.observability"):
        result = verifier.assess("raw-customer-id", [_document()], correlation_id="corr-test")

    assert result.status == "unassessed"
    assert result.requires_human_review is True
    rendered = caplog.text
    assert "raw-customer-id" not in rendered
    assert "DOC-REF-1" not in rendered


def test_malformed_provider_payload_returns_unassessed():
    class MalformedExtractor:
        def extract(self, document):
            return [{"field_name": "legal_name"}]

    verifier = ComplianceVerifier(
        document_extractor=MalformedExtractor(),
        identity_verifier=FakeIdentityVerifier(_verified_sources()),
        policy_provider=FakePolicyProvider(_policy()),
        aml_provider=FakeAMLProvider(),
    )

    result = verifier.assess("verified-subject", [_document()])

    assert result.status == "unassessed"
    assert result.requires_human_review is True
    assert "provider_error" in result.reason_codes
