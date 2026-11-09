# Data Model: Dispute Resolution

## DisputeCase

- `case_id`: stable case identifier.
- `customer_id`: verified Aria/customer identity scope.
- `dispute_type`: `fraudulent_transaction` or `merchant_dispute` in the MVP.
- `transaction_id`: required reference to the disputed transaction.
- `claim`: sanitized customer/analyst description treated as untrusted text.
- `state`: `received`, `investigating`, `awaiting_review`, `approved_for_simulation`, `revised`, `rejected`, `escalated`, or `closed`.
- `created_at`, `updated_at`: timezone-aware UTC timestamps.

Validation: case scope must match the verified parent context and the configured MVP customer/product constraints.

## DisputeEvidence

- `evidence_id`, `source_type`, `source_record_id`, `retrieved_at`, `source_version`.
- `fields`: allowlisted transaction, account, location, merchant, order, delivery, or customer fields.
- `finding`: concise factual summary, contradiction marker, and freshness status.

Validation: preserve source provenance; external text is data, not instruction; raw payloads are not exposed in UI/audit by default.

## DisputePolicy

- `policy_id`, `version`, `effective_from`, `effective_to`.
- `dispute_type`, `required_evidence`, `rule_conditions`, `human_review_conditions`.
- `action_proposals`: allowlisted simulated action names only.

Validation: policy must be approved, in-date, and applicable. Missing or conflicting policy suppresses auto outcomes and requires review. The MVP policy data is explicitly test-only.

## DisputeFinding

- `finding_id`, `case_id`, `finding_type`, `summary`, `evidence_ids`.
- `deterministic_result`: pass/fail/not_applicable for required checks.
- `confidence_inputs`: evidence completeness and rule outcomes, not a model-authorized permission.

## DisputeRecommendation

- `recommendation_id`, `case_id`, `version`, `outcome` (`propose_resolution`, `human_review`, `no_recommendation`).
- `reason`, `explanation`, `evidence_ids`, `policy_version`.
- `simulated_actions`: empty or allowlisted proposals; never real action requests.
- `created_at`.

Validation: any deterministic failure or required-evidence conflict prevents a confident proposed resolution.

## HumanDecision

- `decision_id`, `recommendation_id`, `recommendation_version`, `analyst_id`.
- `decision`: `approve`, `revise`, `reject`, or `escalate`.
- `rationale`, `revision`, `created_at`.

Validation: analyst identity is established by the approved review interface; revised recommendations are revalidated and require a new decision.

## DisputeAuditEvent

- `event_id`, `correlation_id`, `case_id`, `sequence`, `actor`, `event_type`, `created_at`.
- `source_references`, `rule/policy_version`, `recommendation_version`, `human_decision_id`, `safe_summary`.

Validation: append-oriented, correlated, and free of credentials, hidden reasoning, and unnecessary raw source payloads.
