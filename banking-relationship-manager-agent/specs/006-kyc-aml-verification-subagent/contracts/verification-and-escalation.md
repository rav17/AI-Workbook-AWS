# Contract: KYC/AML Verification and Escalation

## Parent-to-specialist handoff

The authenticated Aria parent may call one bounded specialist tool with:

```json
{
  "subject_id": "CUSTOMER-REFERENCE",
  "document_refs": ["DOC-REF-1"],
  "request_reason": "kyc_refresh",
  "session_context": "Customer submitted updated identity evidence."
}
```

- `subject_id` and tenant/session context come from verified parent identity, not caller-provided identity fields.
- `document_refs` are opaque references resolved by an injected provider; raw document content is not included in the tool request.
- The child is not an authentication or authorization boundary and cannot change parent claims.

## Provider contracts

`DocumentExtractor.extract(document_ref, allowed_schema, correlation_id)` returns typed masked `ExtractedFieldObservation` records plus provider reference/status. `IdentityVerificationProvider.verify(subject_id, fields, source_allowlist, correlation_id)` returns source observations. `CompliancePolicyProvider.get_policy(jurisdiction, request_reason)` returns an owner-approved, effective-dated policy or an explicit unavailable result. `AMLFindingProvider.assess(subject_id)` returns an explicit `clear`, `findings`, or `incomplete` `AMLAssessment` with evidence references; an empty response is not an implicit clear.

Provider errors, unsupported schemas, missing policy, stale sources, and invalid responses return incomplete/unassessed results and require human review. No default provider or policy is assumed.

## Specialist result

```json
{
  "status": "evidence_consistent | review_required | unassessed",
  "assessment_id": "ASSESSMENT-ID",
  "verification_results": [],
  "risk_findings": [],
  "aml_findings": [],
  "aml_status": "clear | findings | unassessed",
  "policy_version": "APPROVED-VERSION-OR-NULL",
  "missing_evidence": [],
  "explanation": "...",
  "recommended_next_step": "...",
  "requires_human_review": true
}
```

The child cannot return a `verified` status if provider/policy prerequisites are absent, and cannot autonomously clear or approve a product request.

## Audit events

Allowed event types include `document.extract`, `source.verify`, `field.match`, `field.conflict`, `risk.assess`, `aml.assess`, `compliance.escalate`, and `analyst.decision`. Events carry correlation, source reference, policy version, and safe reason metadata only. Raw documents, full identity numbers, secrets, and hidden reasoning are excluded.
