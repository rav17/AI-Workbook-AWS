# Data Model: KYC/AML Verification

## DocumentReference

- `document_id`: opaque reference, not a raw identity number.
- `document_type`: configured document type or `unsupported`.
- `jurisdiction`: configured jurisdiction or `unknown`.
- `content_ref`: ephemeral provider/demo reference; never raw bytes in prompt or Memory.
- `received_at`: timezone-aware timestamp.

## ExtractedFieldObservation

- `field_name`: normalized schema field defined by the configured jurisdiction.
- `masked_value`: masked display value; any comparison token is transient and protected.
- `confidence`: provider confidence in `[0,1]`, if supplied; not an authorization decision.
- `document_id`, `provider_id`, `extracted_at`.
- `status`: `extracted`, `low_confidence`, `missing`, `invalid`, or `unsupported`.

Validation: unapproved document/field schemas return `unsupported`; values are masked before logs, audit, UI, or prompts.

## VerificationObservation

- `subject_id`: verified customer reference from Aria's authenticated context.
- `field_name`, `masked_value`, `source_id`, `source_type`, `retrieved_at`.
- `freshness`: `current`, `stale`, or `unknown`.
- `status`: `match`, `mismatch`, `missing`, `unavailable`, or `invalid`.

Validation: sources are read-only, allowlisted, and parent-scoped; unavailable sources are not treated as matches.

## VerificationResult

- `field_name`, `outcome`: `verified`, `conflict`, `incomplete`, or `unverified`.
- `observations`: provenance references and masked values.
- `policy_version`, `reason_code`, `requires_human_review`.

Validation: source precedence and mismatch materiality come from an approved policy; absent policy results in `incomplete`.

## CompliancePolicy

- `policy_id`, `version`, `jurisdiction`, `effective_from`, `effective_to`.
- `supported_documents`, `required_fields`, `source_precedence`.
- `risk_factors`, `thresholds`, `escalation_rules`.

Validation: `effective_from` and `effective_to` MUST be timezone-aware; policy is owner-approved, versioned, current, and explicit. Expired or not-yet-effective policy produces `unassessed`. No code default can assert a compliant risk result.

## AMLAssessment

- `status`: `clear`, `findings`, or `incomplete`.
- `findings`: typed AML signals with severity and evidence reference.
- `evidence_refs`: source evidence references supporting the AML result.

Validation: `clear` requires at least one evidence reference; `findings` requires at least one finding; provider absence, malformed output, or `incomplete` never means clear.

## ComplianceAssessment

- `assessment_id`, `correlation_id`, `status` (`evidence_consistent`, `review_required`, `unassessed`).
- `field_results`, `aml_findings`, `aml_status` (`clear`, `findings`, `unassessed`), `policy_version`, and `reason_codes`.
- `requires_human_review`, `recommended_kyc_status`, which remains null in this implementation.

Validation: provider failures, conflicts, policy gaps, and incomplete AML results never yield KYC approval; every result requires human review.

## ComplianceAuditEvent

- `event_id`, `correlation_id`, `subject_id`, `event_type`, `source_reference`, `policy_version`, `reason_code`, `created_at`.
- `safe_summary`: masked, bounded event details.

Validation: no raw document bytes, full identity numbers, credentials, raw prompt, or private model reasoning.
