# Data Model: Receivables Exception Resolution (synthetic MVP)

Typed Pydantic v2 models (frozen where stated). Money is `Decimal` with 2 dp (`ROUND_HALF_EVEN`), serialized as string. Timestamps are UTC timezone-aware. All values are **synthetic**. Policy values are proposals pending human review.

## TrustedContext (frozen; not model-visible)
`tenant_id`, `user_id`, `session_id`, `correlation_id`, `analyst_role` (synthetic harness constant `receivables_operations_analyst`), `authority_source` (`trusted_server_provider` | `synthetic_harness`). Construct only from a separately trusted server-side provider or explicit synthetic harness. A payload `_verified_principal` field by itself is not proof and cannot construct this context. Runtime provider wiring is deferred; absent an approved trusted source, refuse context-dependent work. Recheck context at every port, service and writer.

## ReceivablesException
`exception_id` (`EXC-SYN-*`), `payment_id`, `intake_hint` (informational; ignored by classification), `customer_scope`=`CORP-SYN-001`, `currency`=`USD`, `state` (`received|investigating|awaiting_analyst|approved_awaiting_confirmation|revised|rejected|escalated|task_created`).

## EvidenceItem
`evidence_id`, `source_type` (payment|virtual_account|customer|invoice|payment_history|allocation_ledger|policy), `source_record_id`, `as_of`, `age_seconds`, `availability` (`available|partial|unavailable|malformed|conflicting`), `freshness` (`fresh|stale`), `evidence_kind` (including `reference_match` and `payer_name_match`), `kind` (`fact|inference`). A reference match has `evidence_kind=reference_match` and `kind=inference`; payer-name comparison has `evidence_kind=payer_name_match` and `kind=inference`. Neither is an authoritative identity/fact or repairs mapping, establishes eligibility, or independently supports a recommendation. Partial required evidence is disclosed, never used to assert a fact from its missing portion, and fails closed.

## SourceSnapshot (frozen)
Per source: record(s), `as_of`, `tenant_id`. `snapshot_digest` = SHA-256 of canonical JSON of all evidence used.

## Payment / VirtualAccount / Customer / Invoice (read-only fixtures)
- Payment: `payment_id`, `amount` (string -> Decimal; malformed => evidence malformed), `currency`, `value_date`, `va_id`, `remittance_reference`, `payer_name`, `narrative` (untrusted), `bank_reference`.
- VirtualAccount: `va_id`, `status` (active|inactive|expired), `customer_id`, `effective_from`, `effective_to`.
- Customer: `customer_id`, `known_payer_names` (informational).
- Invoice: `invoice_id`, `customer_id`, `currency`, `status` (open|partially_open|closed|disputed), `outstanding_amount`, `reference`, `due_date`.
- AllocationRecord: `allocation_id`, `payment_id`, `invoice_id`, `status` (posted|pending).

## ApprovedPolicy (synthetic, versioned)
`policy_id`, `version`, `tenant_id`, `currency`, `exception_types`, `effective_from`, `effective_to`, `approval_status` (`pending_human_review|proposed_not_approved|approved_synthetic_test_only`), `approval_record_ref` (null until human approval), tolerance, weights, bands, margin, duplicate window, freshness limits, TTLs. Activation to `approved_synthetic_test_only` requires an approval record; without it every case fails closed `POLICY_UNAPPROVED`.

## DuplicateCheckResult / PriorAllocationResult
Status `clear|suspected|confirmed|unknown|conflict`, with matched record IDs. `clear` only when all required sources are available, fresh, consistent and no rule fires.

## CandidateAllocation
`invoice_id`, `eligible`, `exclusion_reason`, `score` (int), `band`, `expected_amount`, `variance` (signed Decimal), `within_tolerance`, `evidence_ids`.

## InvestigationProposal (immutable per version)
`proposal_id`, `exception_id`, `version`, `outcome` (`recommend|no_recommendation|escalate|out_of_scope`), `classification`, `primary_reason`, `secondary_reasons`, `proposed_invoice_id` (only when `recommend`), `variance` (payment, expected, signed variance, currency), `policy_id/version`, `evidence[]`, `source_snapshot_digest`, `created_at`, `expires_at`, `draft_operations_note` (deterministic), `safe_next_step` (required for partial evidence; otherwise nullable), `content_hash`. For partial required evidence, disclose the incomplete source and advise refreshing/completing it, rerunning, and routing for human review if it remains incomplete.

## AnalystDecision
`decision_id`, `proposal_id`, `proposal_version`, `decision` (`approve|revise|reject|escalate`), `analyst_id` (from TrustedContext), `decision_revision` (monotonic per exception), `rationale` (bounded safe text), `created_at`. `approve` is unavailable unless outcome is `recommend`. Confirmation is not a decision value and does not increment decision revision.

## ConfirmationBinding, ConfirmationEvent, MockCaseTaskPayload and CaseTask
`ConfirmationBinding` (proposed persistent record; Q5 permits isolated synthetic local persistence, but does not approve this design or its implementation): immutable `confirmation_id` (opaque, server-issued at approval; never model/caller-selected), `tenant_id`, `session_id`, `exception_id`, `proposal_id`, `proposal_version`, `decision_revision`, `payload_hash`, and trusted-context binding. Create atomically with the approval state/event. Proposed store constraints: unique `(tenant_id, session_id, confirmation_id)` and one binding per approval tuple. Same scoped identity with changed exception/proposal/version/revision/payload/context is `conflict`; cross-scope access fails closed.
`ConfirmationEvent`: distinct persisted confirmation/audit event carrying the confirmation ID, binding reference, outcome and timestamp; not an AnalystDecision.
Payload: `exception_id`, `proposal_id`, `proposal_version`, `payment_id`, `invoice_id`, `customer_id`, `currency`, `payment_amount`, `expected_amount`, `variance`, `policy_id`, `policy_version`, `evidence_ids`, `decision_revision`, `summary` (safe template). No raw payer/remittance text. `payload_hash` is SHA-256 of canonical payload and is not an identity.
`CaseTask`: `case_task_id`, `confirmation_id` (proposed UNIQUE constraint), `payload_hash`, `payload_json`, `tenant_id`, `session_id`, `created_at`. Create-only: the proposed DB design uses triggers to abort UPDATE/DELETE. Q5 permits the isolated synthetic local persistence scope, but these constraints and their enforcement are unapproved, unimplemented and unverified.

## DecisionState (per tenant/session/exception)
`current_proposal_version`, `decision_revision`, `state`, `approved_at`, bound `confirmation_id` reference. The proposed design updates this only inside a persistence transaction with its audit event; implementation and transaction behavior are not approved or verified.

## AuditEvent (append-only, same transaction as state change; retrieval events appended by the engine)
`event_id`, `correlation_id`, `sequence`, `event_type` (retrieval|check|proposal|decision|confirmation_binding|confirmation|task_result|replay|rejection), `actor`, `source_refs`, `policy_version`, `reason_codes`, `proposal_version`, `confirmation_id?`, binding reference/hash, `case_task_id?`, `safe_summary`, `created_at`. The proposed design excludes prompts, credentials, hidden reasoning and raw narrative/payer/remittance text. Confirmation is a distinct event carrying its immutable binding; audit failure means the operation is not successful. Q5 permits this isolated synthetic local persistence scope; audit behavior remains a proposal, not implemented or verified.

## Retry identity
No content-derived idempotency key. A stable opaque `confirmation_id` is issued by server-side code at approval and bound atomically to trusted tenant/session/exception, proposal/version, decision revision and canonical payload hash. Revised approval receives a new ID. Under the same scoped ID, changed binding is a conflict. An exact committed retry returns the existing task even if the decision state later changes.

## State transitions
`received -> investigating -> awaiting_analyst` (outcome recommend) -> `approved_awaiting_confirmation` (server issues and binds confirmation ID) -> `task_created` after a separate confirmation operation. From `awaiting_analyst|approved_awaiting_confirmation`: analyst `revise` -> new proposal version (back to `awaiting_analyst`, fresh approval and new confirmation ID), `reject -> rejected`, `escalate -> escalated`. Outcomes `no_recommendation|escalate` allow only reject/escalate/revise; never approve. Confirmation is not an analyst decision. After `task_created`, later decisions are recorded but do not alter the task. These state and audit persistence transitions are proposed, not implemented or verified; Q5 approves only their isolated synthetic local storage scope.
