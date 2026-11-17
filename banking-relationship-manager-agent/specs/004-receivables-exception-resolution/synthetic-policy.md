# Proposed Synthetic Policy v1 (DRAFT, SYNTHETIC ONLY)

**Every value here is `PENDING_HUMAN_REVIEW`.** It is not approved, not a business policy, not production-derived. Policy id `POLICY-SYN-RX-V1`, version `1.0.0-draft`. Authored by the architect under Q2 for review at the plan gate. Changing any value changes labels and denominators and requires re-review of `synthetic-fixtures.json`.

## 1. Scope
Tenant `TENANT-SYN-001`, customer `CORP-SYN-001`, currency `USD`, categories `invalid_mapping`, `amount_reference_mismatch`, `suspected_duplicate`. Anything else is `out_of_scope`: no investigation, no source reads.

## 2. Deterministic definitions
- **Variance** = `payment_amount - invoice.outstanding_amount` (Decimal, 2 dp, signed; positive = overpayment).
- **Tolerance**: within tolerance iff `|variance| <= 100.00` AND `|variance| <= 0.50% of outstanding_amount` (both inclusive).
- **Reference tokens**: only the payment `remittance_reference` field is parsed, using `(?i)\bINV[-\s]?(\d{4})\b`, normalized to `INV<digits>`. A token matching an invoice reference is evidence with `evidence_kind=reference_match` and `kind=inference`: it is a candidate hypothesis, not authoritative invoice/customer identity or fact. It cannot establish customer scope, eligibility or mapping, nor repair a mapping. Eligibility and customer identity come from their separate source records. Narrative and payer name are never parsed for reference matching or instructions.
- **Eligible invoice**: status `open` or `partially_open`, outstanding > 0, customer `CORP-SYN-001`, currency `USD`. Ineligible invoices matched by reference are reported as excluded (`INVOICE_INELIGIBLE_CLOSED|DISPUTED`), never ranked.
- **Mapping valid**: VA record exists once, status `active`, `customer_id == CORP-SYN-001`, payment `value_date` within `[effective_from, effective_to]` inclusive. Payer-name or reference inference never repairs mapping.
- **Score (integers)**: inferred reference-token candidate match `+50`; amount within tolerance `+30`; `variance == 0` additional `+10`. The reference-match evidence remains `evidence_kind=reference_match`, `kind=inference`; it only ranks a candidate supported by independently sourced eligibility/customer facts. Payer-name agreement `+0` (`kind=inference`, display only). Neither inference establishes identity or repairs mapping. Only candidates with score > 0 are listed.
- **Bands**: high `>= 80`, medium `50-79`, low `< 50`.
- **Competing**: second-best score `>= top - 20` (margin 20).
- **Duplicate**: another payment (different `payment_id`, same VA customer, same amount, same non-empty reference token set, `|value_date difference| <= 3` days inclusive) => `suspected`; identical `bank_reference` => `confirmed`. History source unavailable/stale/conflicting => `unknown`/`conflict`.
- **Prior allocation**: any allocation record for this `payment_id` => payment prior allocation (`suspected_duplicate` class); any `pending`/`posted` allocation by another payment on the candidate invoice => `PRIOR_ALLOC_INVOICE_PENDING`; ledger unavailable => `unknown`. All block confidence.
- **Classification (independent of policy and of intake hint)**: mapping not valid or conflicting -> `invalid_mapping`; else duplicate suspected/confirmed or payment-level prior allocation -> `suspected_duplicate`; else `amount_reference_mismatch` (residual; weak discriminator, flagged for human review). If mapping or payment evidence is unavailable, partial or malformed, classification is *not determinable* (abstain). A reference-match inference does not change classification or establish identity.

## 3. Disposition decision table (first match wins)
1. Scope guard failure -> `out_of_scope`.
2. Policy missing / unapproved / expired / tenant or source mismatch / inapplicable -> `escalate`.
3. Any required source partial -> `escalate` with primary reason `EVIDENCE_PARTIAL`; disclose which source is incomplete and provide safe next step: refresh or complete it, rerun, and route for human review if still incomplete. Do not infer facts from the missing portion.
4. Any required source unavailable, malformed, stale or conflicting -> `escalate` with the corresponding evidence reason.
5. Duplicate suspected/confirmed/unknown or prior allocation present/unknown -> `escalate`.
6. No eligible candidate (including reference to ineligible invoice) -> `escalate` (`NO_CANDIDATE`).
7. Competing candidates -> `escalate`.
8. Top band low -> `escalate` (`LOW_CONFIDENCE`).
9. Top band medium (single candidate, e.g. variance out of tolerance) -> `no_recommendation`, **no escalation required** (analyst may revise/reject).
10. Top band high, unique, all checks clear -> `recommend`.
Primary reason is the first matching rule's reason; later reasons are listed as secondary.

## 4. Reason codes
`MAPPING_ABSENT, MAPPING_EXPIRED, MAPPING_INACTIVE, MAPPING_CUSTOMER_MISMATCH, MAPPING_MISSING_ID, MAPPING_OUTSIDE_EFFECTIVE_DATES, DUP_SUSPECTED, DUP_CONFIRMED, DUP_UNKNOWN, PRIOR_ALLOC_PAYMENT, PRIOR_ALLOC_INVOICE_PENDING, PRIOR_ALLOC_UNKNOWN, INVOICE_INELIGIBLE_CLOSED, INVOICE_INELIGIBLE_DISPUTED, NO_CANDIDATE, COMPETING_CANDIDATES, LOW_CONFIDENCE, MEDIUM_CONFIDENCE_VARIANCE_OUT_OF_TOLERANCE, EVIDENCE_STALE, EVIDENCE_UNAVAILABLE, EVIDENCE_MALFORMED, EVIDENCE_CONFLICT, POLICY_MISSING, POLICY_UNAPPROVED, POLICY_EXPIRED, POLICY_SOURCE_MISMATCH, POLICY_INAPPLICABLE, EVIDENCE_PARTIAL, UNTRUSTED_TEXT_IGNORED` (informational flag), `NONE`. `EVIDENCE_PARTIAL` includes a safe next step to refresh/complete the named source, rerun, and route for human review if still incomplete.

## 5. Freshness and expiry (proposed values)
- Fixed clock `2026-03-16T12:00:00Z`; each source record has `as_of`. `age = now - as_of`; fresh iff `0 <= age <= max_age` inclusive; `as_of` in the future => malformed.
- `max_age`: payment, invoice, payment_history, allocation_ledger `4h` (14400 s); virtual_account, customer `24h`. Boundary checks: age exactly 4h fresh; 4h+1s stale.
- Policy effective on the clock date, both ends inclusive; tenant must equal context tenant; policy digest must equal fixture-declared digest.
- Proposal TTL `30 min` from creation. Confirmation window `10 min` from approval. At confirmation, evidence age is recomputed on the confirmation clock and the evidence digest recomputed; changed or stale => stale confirmation. The freshness presentation shows `as_of` and age per evidence item.

## 6. Evaluation conventions (proposed; owner agreement required before calculation)
- One evaluation case per synthetic payment exception; run denominators are fixed by the catalogue labels, never by runtime output.
- Abstention, no candidate, and error stay in denominators and count as incorrect for any applicable accuracy or escalation numerator; they are also reported as disposition counts. Cases without an owner label are not scored; their count is reported.
- Zero denominator => `N/A`, never pass.
- SC-001: scored cases = 50; correct if class equals expected. Cases `S03`, `S07` are labelled `classification_scored=false` (not determinable); reported as `unscored_by_label`.
- SC-002: 13 allocatable cases; correct if top-ranked eligible candidate in `acceptable_invoice_ids`; abstain/no-candidate/error incorrect.
- SC-003: precision = correct confident `recommend` / all `recommend` outputs; incorrect-allocation rate = incorrect allocation recommendations / all allocation recommendations (a ranked candidate inside a non-confident outcome is "candidate information", not a recommendation); abstentions, no-candidate and errors listed separately. Also report confident outputs on non-allocatable cases.
- SC-004: correct escalation = explicit `escalate` and no confident allocation over 36 escalation-required cases; false escalations over 16 not-required cases reported separately.
- SC-005: for each `recommend`, all 7 evidence types present and variance recomputation equal; `N/A` when no recommendation.
- Report per-stratum counts for S1..S8, and per expected class.
- Circularity warning: labels were derived from this same proposed policy; the set measures conformance, not real-world accuracy. Independent human label review is required.

## 7. Pre-approval behaviour
Fixture policy block carries `approval_status_current="pending_human_review"`. The harness activates `approved_synthetic_test_only` only via a recorded human approval reference. Before that, expected behaviour is every case escalating with `POLICY_UNAPPROVED`.
