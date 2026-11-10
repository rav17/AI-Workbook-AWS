# Data Model: Receivables Exception Resolution

## ReceivablesException

- `exception_id`: stable test/demo identifier.
- `payment_id`: unique payment source identifier.
- `exception_type`: `invalid_mapping`, `amount_reference_mismatch`, or `suspected_duplicate`.
- `customer_scope`: the single configured corporate customer.
- `currency`: the single MVP currency.
- `received_amount`: non-negative `Decimal` from the payment source.
- `value_date`: timezone-aware or local banking date normalized by the source adapter.
- `payer_name`, `remittance_reference`: untrusted external text.
- `state`: `received`, `investigating`, `awaiting_analyst`, `approved`, `revised`, `rejected`, `escalated`, or `case_task_created`.

Validation: supported category, customer, and currency are enforced before source reads; invalid values fail closed.

## SourceEvidence

- `source_type`: payment, virtual account, customer, invoice, or approved procedure.
- `source_record_id`: opaque source identifier.
- `retrieved_at`: UTC retrieval timestamp.
- `fields`: allowlisted typed evidence fields required by a rule.
- `source_version`: optional source/procedure version.

Validation: read adapters return only allowed fields, never accept arbitrary model-authored queries, and preserve provenance for audit.

## VirtualAccountEvidence

- `virtual_account_id`: payment's virtual account identifier.
- `status`: active, inactive, expired, or unknown.
- `customer_id`: authoritative mapping when present.
- `effective_from`, `effective_to`: validity period.
- `evidence`: source references.

Validation: payer-name inference cannot replace a missing or invalid authoritative mapping.

## InvoiceCandidate

- `invoice_id`, `customer_id`, `currency`, `status`.
- `expected_amount`, `outstanding_amount`: `Decimal`.
- `due_date`: optional banking date.
- `reference`: untrusted source field.
- `evidence`: source references.

Validation: only open/eligible invoices in the configured customer/currency scope are candidates; closed or already fully allocated invoices are excluded deterministically.

## ApprovedPolicy

- `policy_id`, `version`, `effective_from`, `effective_to`.
- `currency`, `exception_types`.
- `tolerance_amount` and/or `tolerance_percent`: owner-approved values.
- `matching_weights`, `confidence_thresholds`: owner-approved, versioned settings.
- `procedure_text` or bounded procedure sections and source references.

Validation: missing, expired, conflicting, or inapplicable policy yields no confident recommendation and escalation. No default tolerance or confidence threshold is invented.

## MatchingDecision

- `candidate_id`: customer/invoice pair or explicit no-candidate result.
- `deterministic_checks`: mapping, active dates, currency, invoice status, amount variance, tolerance, and duplicate result.
- `variance_amount`: `Decimal` computed by code.
- `candidate_score`: explainable score from configured matching policy; never overrides deterministic failures.
- `confidence_band`: configured band or `undetermined`.
- `evidence`: source IDs and policy version.

Validation: a candidate failing any mandatory deterministic check cannot be marked eligible.

## InvestigationRecommendation

- `recommendation_id`, `exception_id`, `version`.
- `outcome`: `recommend`, `no_recommendation`, or `escalate`.
- `customer_id`, `invoice_id`: optional proposed allocation.
- `exception_reason`, `confidence_band`, `variance_amount`.
- `evidence`, `policy_version`, `draft_operations_note`.

Validation: recommendations are proposals only; evidence is required; low-confidence, duplicate, competing, contradictory, or unsupported cases do not produce a confident allocation.

## AnalystDecision

- `decision_id`, `recommendation_id`, `recommendation_version`.
- `analyst_id`: established by the approved analyst interface, never model-generated.
- `decision`: `approve`, `revise`, `reject`, or `escalate`.
- `rationale`, `revision_fields`, `created_at`.

Validation: only an authorized analyst action can advance to approval; revise re-runs deterministic checks and returns for a fresh decision.

## CaseTask

- `case_task_id`, `exception_id`, `recommendation_id`, `decision_id`.
- `status`, `created_at`, `idempotency_key`, `case_payload`.

Validation: the case-task adapter is the sole write interface and rejects requests without an authorized approved decision. It cannot post a ledger entry or mutate source/master records.

## ReceivablesAuditEvent

- `event_id`, `correlation_id`, `exception_id`, `sequence`, `event_type`, `actor`.
- `source_references`, `tool_name`, `rule_results`, `recommendation_version`, `decision_id`, `case_task_id`.
- `safe_summary`, `created_at`.

Validation: audit records are append-oriented and contain evidence references/safe summaries, not unnecessary raw payer/remittance text or hidden model reasoning.
