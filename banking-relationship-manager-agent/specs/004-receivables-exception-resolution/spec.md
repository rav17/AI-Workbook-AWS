# Feature Specification: Virtual Account Receivables Exception Resolution

**Feature Branch**: `004-receivables-exception-resolution`  
**Created**: 2026-11-10  
**Status**: Draft  
**Input**: UC8 Virtual Account Receivables Exception Resolution Agent source and the approved ideation brief, adapted for a controlled, human-supervised MVP.

## Clarifications

### Session 2026-11-10

- Human decisions recorded in Q1?Q5: `receivables_operations_analyst` is a synthetic-fixture role; the permitted mock task is create-only in isolated test/demo storage with idempotent retries; the human will review proposed synthetic policy, fixtures, and labelled evaluation at the plan gate; and internal proposals, analyst decisions, confirmation/idempotency bindings, and audit may persist only in isolated synthetic local test/demo storage. These decisions do not approve the plan, policy contents or values, fixture contents or construction commands, evaluation labels or denominators, results, production authorization, or financial writes.
- Supporting design review (not policy approval): analyst approval is distinct from task creation. The analyst must see the exact immutable mock payload and explicitly confirm it; confirmation is required before any mock write, and source and financial records remain unchanged.
- Supporting architecture review (not authorization): the Aria parent retains responsibility for validated identity, tenant/session boundaries, and the final response. Model or specialist/tool visibility alone does not establish analyst authorization.
- Supporting design and architecture review (not a new business-policy decision): confirmation is bound to the current proposal and decision state. If revise, reject, or escalate commits first, the pending confirmation is stale and creates no task; if task creation commits first, a later decision does not mutate or revoke it. An identical retry returns the committed task; reuse with a changed proposal version or immutable payload is rejected without mutation.
- Supporting design review: facts must be distinguishable from inference; controls and status must be accessible; and no-confident outcomes must explain the reason, evidence availability/freshness, and a safe next step. Approval is unavailable for those outcomes.

## User Scenarios & Testing

### User Story 1 - Request an Exception Investigation (Priority: P1)

As a virtual-account or receivables operations analyst, I want Aria to investigate a supported inbound payment exception so I can receive a consistent, evidence-backed proposal without changing Aria’s identity, session, or safety boundaries.

**Why this priority**: Investigation is the central user need, bounded to one synthetic customer, one currency, and the supported exception categories.

**Independent Test**: Using synthetic cases, verify that a supported request is investigated within scope, while missing identifiers, unsupported categories, and unrelated requests do not cause out-of-scope investigation.

**Acceptance Scenarios**:

1. **Given** a supported payment exception with an identifier, **When** the analyst asks Aria to investigate it, **Then** the investigation remains within the approved synthetic scope and preserves Aria’s identity and session boundaries.
2. **Given** a missing payment identifier or unsupported exception, **When** the analyst requests an investigation, **Then** the analyst receives a clear limitation or escalation and no broader investigation is performed.
3. **Given** a request unrelated to receivables exceptions, **When** it reaches Aria, **Then** existing Aria behavior remains unchanged.

### User Story 2 - Review an Evidence-Backed Proposal or Escalation (Priority: P1)

As a receivables operations analyst, I want the investigation to show relevant evidence, candidate allocations, and deterministic variance results—or explain why no confident recommendation is available—so I can decide what to do next.

**Why this priority**: Analysts need an understandable basis for review; insufficient, conflicting, or unapproved evidence must not be turned into a confident allocation.

**Independent Test**: Use synthetic fixtures for each supported category and verify cited evidence, candidate information, signed variance calculations where applicable, and safe no-recommendation outcomes.

**Acceptance Scenarios**:

1. **Given** synthetic evidence supports one eligible invoice and the applicable approved policy, **When** investigation completes, **Then** the proposal identifies the payment and candidate, shows the payment amount, expected amount, signed variance and currency, cites evidence, and identifies the policy version used.
2. **Given** there is a possible payer-name or reference match, **When** the result is presented, **Then** it distinguishes that inference from authoritative facts and does not use it to repair a missing or invalid virtual-account mapping.
3. **Given** the mapping is missing or invalid, a duplicate is suspected or confirmed, candidates conflict, evidence is insufficient, or the applicable policy is unavailable or unapproved, **When** the investigation completes, **Then** it does not offer a confident allocation and explains the safe next step.
4. **Given** evidence is unavailable, stale, malformed, partial, or contradictory, **When** the result is presented, **Then** its availability and freshness limitations are disclosed alongside the evidence identifiers and the analyst is given a safe next step.
5. **Given** payer or remittance text contains instructions or conflicts with authoritative records, **When** it is considered, **Then** it is treated as untrusted evidence, not as instructions or authoritative identity.

### User Story 3 - Decide Whether to Create a Synthetic Mock Case Task (Priority: P1)

As a receivables operations analyst, I want to approve, revise, reject, or escalate a proposal and see the exact synthetic mock task before confirming its creation, so the proposed allocation remains subject to my decision and no financial record is changed.

**Why this priority**: The analyst retains decision authority. The only permitted prototype write is a specifically approved synthetic mock case task.

**Independent Test**: Verify that an analyst can make each decision; revisions create a new proposal requiring review; only explicit approval followed by confirmation of the displayed task can result in an approved mock write; other decisions produce no write.

**Acceptance Scenarios**:

1. **Given** a proposal is presented, **When** the analyst reviews it, **Then** it is clearly identified as a proposal and offers approve, revise, reject, and escalate choices.
2. **Given** a proposal lacks a confident recommendation, **When** the analyst reviews it, **Then** approval and the mock-write path are unavailable.
3. **Given** the analyst revises a proposal, **When** the revision is evaluated, **Then** it becomes a new proposal version that requires fresh analyst review and approval; prior approval does not authorize the revision or any write for it.
4. **Given** the analyst rejects or escalates a proposal, **When** the decision is recorded, **Then** no case-task write occurs.
5. **Given** the analyst approves an eligible proposal, **When** the exact synthetic mock task is displayed, **Then** no write occurs until the analyst explicitly confirms that task.
6. **Given** a create-only mock write fails or its result is uncertain, **When** the analyst is informed, **Then** the result is not described as successful; the analyst sees a safe next step, the investigation context is retained, and a retry with the same approved proposal version and immutable task payload returns the same task without creating a duplicate or mutating a task.
7. **Given** an idempotency key is retried with a different approved proposal version or immutable task payload, **When** the write is checked, **Then** the request is rejected without creating or mutating a task.
8. **Given** a task confirmation is pending and a revise, reject, or escalate decision changes the current decision revision/state, **When** that decision races with task creation, **Then** if the decision commits first, the confirmation is stale and creates no task; if task creation commits first, the later decision does not mutate or revoke the committed task. An identical retry after task creation returns that same task without creating another.

### User Story 4 - Evaluate and Trace the Bounded MVP (Priority: P2)

As a product owner or control reviewer, I want traceable synthetic investigations and an agreed labelled test set so I can evaluate the proposed outcomes without mistaking targets for measured results.

**Why this priority**: Controlled evaluation and traceability are necessary before effectiveness can be claimed.

**Independent Test**: On an owner-approved labelled synthetic test set, verify the defined measures and audit coverage, and verify that no prohibited write occurs.

**Acceptance Scenarios**:

1. **Given** a synthetic investigation, **When** its trace is reviewed, **Then** it records retrievals, evidence references, policy version, proposal versions, analyst decisions, and any permitted mock write without customer data or secrets.
2. **Given** the agreed labelled evaluation set has not been approved or evaluated, **When** results are discussed, **Then** the targets below are described as targets, not measured performance.
3. **Given** an approved evaluation is run, **When** results are reported, **Then** incorrect-allocation rate is reported explicitly alongside confident-recommendation precision.

### Edge Cases

- The virtual account is absent, inactive, expired, outside its effective dates, or mapped to a different customer.
- A source is unavailable, stale, malformed, partial, contradictory, or returns multiple records for an identifier expected to be unique.
- The amount, currency, reference, payer name, or date is malformed or inconsistent with available evidence.
- A duplicate or prior allocation is confirmed, suspected, unverifiable, or supported by conflicting identifiers.
- Several invoices are plausible, or an invoice is closed, partially allocated, or otherwise ineligible under approved policy.
- The operating procedure or matching, confidence, eligibility, or tolerance policy is absent, unapproved, expired, ambiguous, or inapplicable.
- Payer or remittance text contains instructions, attempts to bypass policy, or credential-like data.
- A retrieval fails after earlier evidence was obtained.
- A decision changes concurrently while a confirmation is uncommitted, making that confirmation stale; an identical retry may follow an already committed task.
- A mock write fails or returns an uncertain result.

## Requirements

### Functional Requirements

- **FR-001**: The capability MUST operate as a bounded receivables specialist within Aria. Aria MUST retain authentication, user and tenant identity, session ownership, and final-response responsibility. User, tenant, session, and analyst authorization MUST be validated at a trusted server-side boundary; model or specialist/tool visibility alone MUST NOT authorize access or approval.
- **FR-002**: The MVP MUST cover only one synthetic corporate customer, one currency, and these exception categories: missing or invalid virtual-account mapping, amount or reference mismatch, and suspected duplicate.
- **FR-003**: The MVP MUST use synthetic information only. It MUST NOT use production integrations, real customer data, or de-identified customer data.
- **FR-004**: Payment, virtual-account, customer, and invoice source information MUST be read-only; investigation MUST NOT change source records.
- **FR-005**: An investigation result MUST identify the exception and present relevant evidence, supported candidate allocations, a confidence outcome, and a draft operations note. It MUST distinguish authoritative facts from inferred payer-name or reference matches.
- **FR-006**: Variance MUST be calculated deterministically using decimal amounts. Results MUST show the payment amount, expected amount, signed variance, currency, and the applicable approved policy version where relevant.
- **FR-007**: Matching, confidence, eligibility, tolerance, duplicate and prior-allocation criteria, and procedure decisions MUST use applicable, owner-approved, versioned rules or policy. This specification establishes no rule contents, policy values, or business thresholds.
- **FR-008**: Missing, unapproved, expired, ambiguous, or inapplicable policy MUST prevent a confident recommendation and result in an explicit safe outcome or escalation.
- **FR-009**: Before a confident allocation is offered, duplicate and prior-allocation checks MUST be deterministic and reproducible against authoritative synthetic payment and allocation records using owner-approved criteria. Identical records and criteria MUST produce the same check outcome. A check may clear an allocation only when the required records are available and consistent and the approved checks find no suspected or confirmed duplicate or prior allocation. Suspected or confirmed duplicates, prior allocations, unknown or unavailable check status, and conflicting records MUST fail closed: no confident allocation is permitted and the result MUST explain the limitation and safe next step. A model MUST NOT infer or supply clearance.
- **FR-010**: Missing or invalid mapping, unresolved competing candidates, contradictory evidence, low confidence, or unexplained variance MUST prevent a confident recommendation and provide a safe next step.
- **FR-011**: A proposal MUST cite relevant source identifiers and disclose evidence availability and freshness limitations. It MUST show the basis for the proposal, including relevant payment, mapping, customer, invoice, duplicate-check, procedure, policy, and variance information. No freshness cutoff or detailed rationale format is established by this specification.
- **FR-012**: Analyst choices MUST include approve, revise, reject, and escalate. A revision MUST produce a new proposal version that requires review; reject and escalate MUST NOT cause a write.
- **FR-013**: Approval MUST be unavailable for an outcome without a confident recommendation.
- **FR-014**: The sole permitted business write MUST be a create-only synthetic mock case-task in isolated test/demo storage, after the analyst explicitly approves a confident proposal version and then confirms the exact task payload. Internal proposals, analyst decisions, confirmation/idempotency bindings, and audit records MAY persist only in isolated synthetic local test/demo storage; they MUST NOT be persisted to production or live resources. Approval and confirmation MUST be bound to the current proposal version and analyst-decision revision/state. At task creation, that binding MUST be validated atomically with the create/idempotency reservation. An intervening revise, reject, or escalate decision MUST invalidate an uncommitted confirmation. If such a decision and task creation race, whichever commits first determines the outcome: a decision committed first prevents the stale confirmation from creating a task; a task committed first MUST NOT be mutated or revoked by a later decision. The synthetic fixture role is `receivables_operations_analyst`; it MUST NOT be treated as production authority.
- **FR-015**: The create-only mock case-task write MUST be traceable and idempotent. Its idempotency key MUST be bound to the approved proposal version and immutable task payload. A retry with the same key, proposal version, and payload MUST return the same already-committed task without creating a duplicate or mutating a task, including when a later decision change makes the original confirmation stale. Reuse with a different proposal version or payload MUST be rejected without mutation. A failed or uncertain write MUST NOT be represented as successful.
- **FR-016**: The MVP MUST NOT perform ledger posting, account credit, payment return or repair, virtual-account creation or modification, customer or invoice master changes, collections, or sanctions or financial-crime screening.
- **FR-017**: Payer names, remittance references, and narratives MUST be treated as untrusted data and MUST NOT be followed as instructions or used as authoritative identity.
- **FR-018**: Traces MUST record source retrievals, evidence references, relevant policy versions, proposal versions, analyst decisions, and permitted mock writes using safe synthetic references. Internal traces and audit records MUST persist only in isolated synthetic local test/demo storage and MUST NOT be persisted to production or live resources. Logs, audit records, specifications, and tests MUST contain no customer data or secrets.
- **FR-019**: The analyst experience MUST distinguish fact from inference, make status understandable without color alone, support keyboard operation with visible focus and clear labels and headings, and announce loading, result, and error states to screen-reader users.
- **FR-020**: Missing, conflicting, stale, malformed, or partial evidence and failed or uncertain writes MUST be explained with a safe next step. An uncertain write outcome MUST be reported as unconfirmed, distinct from a verified not-created outcome; a failure MUST NOT imply that an action succeeded. Safe retry MUST retain relevant context.
- **FR-021**: The success targets below MUST NOT be claimed as achieved until an owner-agreed labelled evaluation set is approved and evaluated.

### Key Entities

- **Receivables Exception**: A synthetic payment identifier, supported exception category, currency, amount, date, and investigation state.
- **Evidence Item**: A source identifier, evidence type, availability, freshness information, and whether the content is an authoritative fact or an inference.
- **Candidate Allocation**: A proposed customer and invoice association with supporting evidence and eligibility outcome.
- **Approved Policy**: An owner-approved, versioned procedure and its applicable matching, confidence, eligibility, and tolerance criteria.
- **Investigation Proposal**: A versioned recommendation or explicit no-confident-recommendation outcome, with evidence, exception reason, variance information, and draft note.
- **Analyst Decision**: Approve, revise, reject, or escalate, linked to the proposal version and decision rationale.
- **Synthetic Mock Case Task**: The sole permitted write artifact, linked to an explicitly confirmed analyst decision.
- **Audit Record**: A trace of synthetic evidence retrieval, policy use, proposals, analyst decisions, and permitted mock writes using safe references.

## Success Criteria

### Measurable Outcomes

SC-001–SC-004 are acceptance targets and evaluation conventions, not approved business policy or measured evidence. The calculation conventions below are proposed solely to make evaluation reproducible and require owner agreement under Q4 before results are calculated. The owner must approve the synthetic fixture strata and labels—including expected classifications, acceptable candidate identifiers, and escalation applicability/correctness labels—before evaluation. No policy values, confidence thresholds, or other business decision thresholds are established here. Report targets as targets until an owner-agreed labelled synthetic set is approved and evaluated.

For SC-001–SC-004, count one evaluation case per synthetic payment exception. Report numerators, denominators, counts by outcome, and the complete case disposition. A runtime abstention, missing/no-candidate result, or processing error is not silently removed: treat it as incorrect for any applicable accuracy or escalation numerator, and report it in the disposition counts. Cases lacking an owner-approved ground-truth label are not scored; report their count separately and do not claim results for an incomplete or unapproved set. A zero denominator is **N/A, not success**. Report applicable strata separately as well as any aggregate.

- **SC-001 — Exception classification accuracy:** At least 90%. Proposed calculation: correctly classified cases divided by all evaluation cases with an owner-approved expected classification. A classification is correct only when the result matches the case’s owner-approved expected class (or an owner-approved acceptable label, if the owner defines one). Abstention, no classification, and error count as incorrect in the denominator.
- **SC-002 — Top-candidate accuracy:** At least 85% on cases owner-labeled as supported and allocatable. Proposed calculation: cases whose highest-ranked allocation candidate is one of the owner-approved acceptable invoice identifiers divided by all such cases. No candidate, abstention, error, or a different top candidate counts as incorrect in the denominator. The owner must agree which cases are supported and allocatable and which candidate identifiers are acceptable.
- **SC-003 — Confident precision and incorrect-allocation rate:** Confident-recommendation precision is at least 95%. Proposed confident-precision calculation: correct confident allocation recommendations divided by all confident allocation recommendations. “Confident” means the system explicitly presents an allocation as confident; the evaluation convention does not set or imply a business confidence threshold. An allocation is correct only if it matches the owner-approved expected candidate and does not violate owner-labeled eligibility or duplicate/prior-allocation status. Also report incorrect-allocation rate: incorrect allocation recommendations, whether confident or not, divided by all allocation recommendations, whether confident or not. Report the counts of abstentions, no-candidate outcomes, and errors separately alongside both rates; they are not allocation recommendations and must not be hidden. A zero denominator for either rate is N/A, not success.
- **SC-004 — Correct escalation:** At least 90% of cases labeled by the owner as requiring escalation, including applicable low-confidence, conflicting, or duplicate-suspected cases, are escalated correctly. Proposed calculation: cases with an explicit escalation and no confident allocation divided by all owner-labeled escalation-required cases. Abstention, no candidate, error, or a confident allocation without the required escalation counts as not correctly escalated. Report false escalations of cases labeled as not requiring escalation separately. The owner must define and approve escalation applicability and correctness labels; this criterion does not establish business escalation policy.
- **SC-005 ? Verifiable evidence and reproducible variance:** For each measure, the denominator is every output with outcome `recommend`; do not exclude a recommendation because its evidence or calculation is missing or invalid. The evidence numerator includes a recommendation only when evidence of all seven required types?`payment`, `virtual_account`, `customer`, `invoice`, `payment_history`, `allocation_ledger`, and `policy`?is present, available, fresh, complete, and non-conflicting. Each citation must include a synthetic source-record ID and snapshot/version that resolve read-only to that exact source record; the snapshot/version digest must be available and match. Source facts must be authoritative; inferred evidence (including reference or payer-name matches) must be labeled as inference and cannot satisfy or override an authoritative fact. The policy citation must resolve to the applicable policy ID and version. The variance numerator includes a recommendation only when its resolved payment and invoice evidence supplies the payment amount, invoice outstanding amount, and matching currency, and its cited applicable policy ID/version supplies the calculation rule; independently recompute the signed variance using Decimal at that policy?s precision and verify the resulting value, sign, and currency match the displayed output. The current proposed synthetic-policy rule is `payment_amount - invoice.outstanding_amount`, signed Decimal to 2 dp; it remains pending human review. Missing, partial, stale, malformed, conflicting, unavailable, unresolvable, or digest-mismatched evidence; absent required inputs or policy version; or a recomputation/output mismatch fails the applicable numerator. Target: 100% for each measure. A zero denominator is `N/A`, not a pass. These are targets, not measured or approved claims; report achievement only after the labelled evaluation set and its results are approved and evaluated.
- **SC-006**: Prohibited financial mutations are zero in all test and demo paths.
- **SC-007**: 100% of source retrievals, proposals, analyst decisions, and permitted mock case-task writes are represented in the trace using safe synthetic references.

## Assumptions

- Aria remains responsible for identity, tenant/session boundaries, and the final response.
- The initial scope is one synthetic corporate customer, one currency, and exactly the three listed exception categories.
- The resolved mock approver role is `receivables_operations_analyst` for synthetic fixtures only; it confers no production authority.
- Receivables/control owners must supply and approve the applicable procedure and versioned matching, confidence, eligibility, and tolerance policies. The human has committed to review a proposed synthetic policy at the plan gate; no policy values or policy contents have been supplied or approved, and no production policy is established.
- The human-approved mock-write boundary is create-only in isolated test/demo storage with idempotent retries. Synthetic fixture contents remain to be authored, reviewed, and approved; the fixture role confers no production authority.
- The human has committed to review the proposed synthetic labelled evaluation set at the plan gate. The set, labels, denominators, and evaluation results remain unapproved and unestablished; no performance has been measured or approved for claim.
- The detailed rationale format and freshness presentation are not settled. Results must nevertheless provide evidence identifiers, disclose availability/freshness limitations, and explain the safe next step.
- Any production integration, additional customer or currency, or financial action requires separate review and approval.
