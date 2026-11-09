# Feature Specification: Virtual Account Receivables Exception Resolution Subagent

**Feature Branch**: `004-receivables-exception-resolution`
**Created**: 2026-10-01
**Status**: Draft
**Input**: Requirements from `UC8_Virtual_Account_Receivables_Exception_Resolution_Agent.pdf`, adapted as an Aria specialist subagent for a controlled, human-supervised MVP.

## User Scenarios & Testing

### User Story 1 - Aria Delegates a Receivables Exception (Priority: P1)

As a virtual-account or receivables operations analyst, I want Aria to hand an inbound payment exception to a specialist so that the required evidence is gathered consistently without changing Aria's authentication, session, or safety boundaries.

**Why this priority**: The specialist must be reachable from the existing parent while keeping investigation scoped to a single customer, currency, payment, and supported exception category.

**Independent Test**: A fake-backed parent-agent test verifies supported receivables requests hand off with the authenticated context and a bounded payment reference; unrelated questions do not invoke the specialist.

**Acceptance Scenarios**:

1. **Given** a payment exception in the supported MVP scope, **When** the analyst requests investigation through Aria, **Then** Aria delegates to one receivables specialist and retains parent-owned identity/session context.
2. **Given** an unsupported exception category or missing payment identifier, **When** the request is received, **Then** Aria returns a safe limitation or manual escalation without broadening data access.
3. **Given** a request outside receivables exception handling, **When** it reaches Aria, **Then** existing Aria behavior remains unchanged.

### User Story 2 - Investigate and Recommend from Evidence (Priority: P1)

As an operations analyst, I want the specialist to verify the virtual account, retrieve invoices and customer context, apply deterministic matching rules, and present an evidence-backed recommendation so that I can resolve exceptions without manually correlating every source.

**Why this priority**: The main value is reducing manual investigation while keeping financial decisions reproducible and grounded in approved data and procedures.

**Independent Test**: Fixed source fixtures cover each supported exception and verify source reads, deterministic variance/duplicate rules, candidate ranking, confidence band, evidence citations, and no recommendation when evidence is insufficient.

**Acceptance Scenarios**:

1. **Given** a payment with a valid active virtual-account mapping and one matching open invoice, **When** investigation runs, **Then** the result names the verified customer/invoice, cites source evidence, explains the match, and records the deterministic variance calculation.
2. **Given** an amount mismatch, **When** investigation runs, **Then** the rules engine compares the variance only to the configured approved tolerance and reports the exact values and rule; an unexplained variance is escalated.
3. **Given** a missing/inactive mapping, suspected duplicate, or multiple competing invoices, **When** investigation runs, **Then** the specialist presents evidence and returns no confident allocation unless deterministic verification and policy criteria are met.
4. **Given** payer or remittance text contains instructions or conflicts with master data, **When** the specialist processes it, **Then** the text is treated as untrusted data, not as instructions or authoritative identity.

### User Story 3 - Analyst Controls the Case Action (Priority: P1)

As an operations analyst, I want to approve, revise, reject, or escalate the recommendation before any case task is written so that model output cannot directly change financial records or case outcomes.

**Why this priority**: The source requires a human decision and permits only an approved case-management task write; financial posting and account changes are prohibited.

**Independent Test**: Workflow tests prove no write occurs before approval, only a case-task adapter is callable after approval, revisions rerun validation, and reject/escalate decisions are recorded without ledger mutations.

**Acceptance Scenarios**:

1. **Given** a recommendation is ready, **When** it is displayed, **Then** it is explicitly marked as a proposal and requires analyst decision.
2. **Given** the analyst approves, **When** the workflow commits, **Then** only one case-management task is created or updated through the approved adapter and the decision is audited.
3. **Given** the analyst revises, rejects, or escalates, **When** the workflow records the decision, **Then** revised evidence is re-evaluated or manual handling is requested and no ledger, account, payment, or virtual-account mutation occurs.

### User Story 4 - Audit and Evaluate the MVP (Priority: P2)

As a product owner and control reviewer, I want every retrieval, recommendation, analyst revision, and decision traceable, and I want the bounded MVP evaluated against agreed labels before demo sign-off.

**Why this priority**: In a receivables workflow, an incorrect confident allocation is materially worse than an analyst escalation.

**Independent Test**: Replay a labelled evaluation set and verify audit completeness, classification/top-candidate/precision/escalation measures, deterministic variance calculations, and zero prohibited financial writes.

**Acceptance Scenarios**:

1. **Given** an investigation completes, **When** the audit is reviewed, **Then** it contains source identifiers, ordered reads/tools, rule/procedure references, recommendation, confidence, and analyst decision without unnecessary raw sensitive data.
2. **Given** a low-confidence, duplicate-suspected, or conflicting case, **When** evaluation runs, **Then** it is escalated and never presented as a confident allocation.
3. **Given** the agreed test set, **When** MVP acceptance is measured, **Then** classification accuracy is at least 90%, top-candidate accuracy at least 85% for supported cases, confident recommendation precision at least 95%, correct escalation at least 90% of applicable cases, evidence coverage is 100%, and variance verification is 100%.

### Edge Cases

- Virtual account is absent, inactive, expired, outside effective dates, or maps to a different customer.
- Customer or invoice source is unavailable, stale, contradictory, or returns multiple records for a supposedly unique identifier.
- Amount, currency, reference, payer name, or value date is malformed or inconsistent with source records.
- A duplicate payment or prior allocation is found, cannot be verified, or has conflicting identifiers.
- Several invoices match within tolerance, or an invoice is already closed/partially allocated.
- The approved tolerance table or operating procedure is missing, ambiguous, expired, or not applicable to the payment.
- Payer/remittance text contains prompt injection, credential-like data, or instructions to bypass policy.
- A tool times out, returns malformed evidence, or fails after prior reads succeeded.
- The analyst changes a decision concurrently or retries an approved case-task write.

## Requirements

### Functional Requirements

- **FR-001**: The capability MUST be a specialist subagent of the existing Aria parent, exposed through one bounded handoff; it MUST NOT create a separate production AgentCore Runtime or independent identity boundary.
- **FR-002**: MVP operation MUST be limited to one corporate customer, one currency, and exactly these exception categories: invalid/missing virtual-account mapping, amount/reference mismatch, and suspected duplicate.
- **FR-003**: The specialist MUST use read-only adapters for payment records, virtual-account master, customer master, and open invoices; no source adapter may mutate financial records.
- **FR-004**: The investigation MUST return a structured plan, source evidence, supported candidates, exception reason, confidence, and draft operations note; inferred payer/reference matches MUST be labelled as inference and MUST NOT be treated as authoritative mapping.
- **FR-005**: Candidate retrieval, name/reference similarity, and ranking MUST be explainable and MUST NOT override deterministic eligibility, mapping, duplicate, date, or tolerance checks.
- **FR-006**: Amount variance, currency checks, tolerance evaluation, effective-date checks, invoice eligibility, and duplicate/prior-allocation detection MUST run in deterministic code with independently testable results.
- **FR-007**: Tolerance values, confidence thresholds, matching weights, and operating-procedure content MUST come from an approved versioned configuration; missing or inapplicable configuration MUST produce no recommendation and a safe escalation.
- **FR-008**: Duplicate/prior-allocation checks MUST be completed deterministically before a recommendation can be presented; a confirmed duplicate MUST return no allocation recommendation.
- **FR-009**: Missing/invalid mappings, multiple competing candidates, contradictory evidence, low confidence, and unexplained variance MUST return an explicit no-recommendation/escalation outcome.
- **FR-010**: Every confident recommendation MUST cite source identifiers and evidence for customer, virtual-account status/ownership/effective dates, invoice status/amount, payment, duplicate check, procedure, tolerance, and calculated variance as applicable.
- **FR-011**: Analyst approve, revise, reject, and escalate decisions MUST be explicit workflow states and MUST be audited; a revision MUST rerun deterministic validation before returning for decision.
- **FR-012**: The only permitted write MUST be creating/updating a case-management task after authenticated analyst approval; this action MUST be idempotent and auditable.
- **FR-013**: The system MUST NOT autonomously post to a ledger, credit an account, return/repair a payment, create/modify a virtual account, mutate customer/invoice/payment masters, initiate collections, or perform sanctions/financial-crime screening.
- **FR-014**: Payer names, remittance references, and narratives MUST be treated as untrusted data, checked by Aria guardrails, and never used as instructions.
- **FR-015**: Every source retrieval, tool call, model recommendation, validation result, analyst revision, and decision MUST have a correlated audit entry containing safe metadata and evidence references.
- **FR-016**: The MVP MUST use mocks, approved de-identified data, or test connectors only; production integration and multi-customer/multi-currency operation are out of scope.
- **FR-017**: Existing Aria Cognito authentication, tenant isolation, session ownership, KYC/AML policy, and production Runtime resource boundaries MUST remain unchanged.

### Key Entities

- **ReceivablesException**: Payment identifier, exception category, currency, received amount/date, payer/remittance reference, and investigation state.
- **VirtualAccountEvidence**: Account status, owner/customer mapping, effective dates, source ID, and retrieval timestamp.
- **CustomerCandidate**: Candidate customer ID, source evidence, match features, and whether the match is authoritative or inferred.
- **InvoiceCandidate**: Invoice ID, customer, status, expected/outstanding amount, currency, due date, and source evidence.
- **ToleranceRule**: Approved amount/currency/exception criteria, effective dates, version, and source procedure.
- **MatchingDecision**: Candidate scores and deterministic eligibility/variance/duplicate results; model scores cannot override failed rules.
- **InvestigationRecommendation**: Proposed customer/invoice allocation, confidence band, evidence references, exception reason, and draft operations note; may explicitly contain no recommendation.
- **AnalystDecision**: Approve/revise/reject/escalate action, analyst identity, rationale, timestamp, and linked recommendation version.
- **CaseTask**: The sole permitted write artifact, created/updated only after approval with an idempotency reference.
- **ReceivablesAuditEvent**: Correlated record of retrieval, tool/rule result, recommendation, revision, decision, and allowed case-task write.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Classification accuracy is at least 90% on an agreed labelled MVP test set.
- **SC-002**: Top-candidate accuracy is at least 85% for supported exception types.
- **SC-003**: Precision of recommendations presented as confident is at least 95%; the incorrect-allocation rate is also reported explicitly.
- **SC-004**: At least 90% of applicable low-confidence, conflicting, and duplicate-suspected cases are escalated correctly.
- **SC-005**: 100% of recommendations contain verifiable source evidence and 100% of recommended allocations have a reproducible variance calculation.
- **SC-006**: No test or demo path performs autonomous ledger posting, account credit, payment return/repair, or virtual-account/master-data changes.
- **SC-007**: Every source retrieval, recommendation, analyst revision/decision, and approved case-task write is represented in the audit log.

## Assumptions

- The specialist is a child of the current Aria agent. The Aria parent retains authentication, tenant/user identity, session, and final-response ownership.
- MVP uses one corporate customer, one currency, synthetic/de-identified payment, virtual-account, customer, and invoice data, and only the three listed exception categories.
- Tolerance tables, approved procedures, matching weights, confidence thresholds, and the labelled evaluation set are supplied and approved by the receivables operations/control owner; the implementation will not invent them.
- The rules engine is implemented and tested before the subagent is allowed to produce recommendations.
- Any customer/payer/reference inference is labelled as non-authoritative evidence and cannot repair a missing virtual-account mapping.
- Case-task create/update is mocked for the prototype and remains approval-gated, idempotent, and the only permitted write.
- Production integrations, autonomous financial action, multi-customer/multi-currency support, collections, sanctions, and financial-crime screening require a separate reviewed feature and are excluded here.
