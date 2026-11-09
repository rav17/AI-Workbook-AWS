# Feature Specification: Dispute Resolution Subagent

**Feature Branch**: `005-dispute-resolution-subagent`
**Created**: 2026-10-01
**Status**: Draft
**Input**: Requirements from `FSS 300AI club - UC#4.png`, adapted to the existing Aria agent and its safety/governance boundaries.

## User Scenarios & Testing

### User Story 1 - Aria Delegates a Dispute (Priority: P1)

As a customer or dispute analyst, I want Aria to route a supported card or merchant dispute to a specialist so that relevant evidence is gathered consistently without changing Aria's authentication, identity, session, or safety boundaries.

**Why this priority**: The specialist must be an Aria capability and must not become an independent agent with separate identity or uncontrolled data access.

**Independent Test**: A fake-backed parent-agent test verifies supported dispute requests are delegated with the verified principal/session and unrelated requests do not invoke the specialist.

**Acceptance Scenarios**:

1. **Given** a supported fraudulent-transaction or merchant dispute, **When** the customer/analyst requests help through Aria, **Then** Aria delegates to the dispute specialist with a bounded request and preserved verified context.
2. **Given** a request is unrelated to disputes or outside the configured customer/product scope, **When** it reaches Aria, **Then** the specialist is not invoked or returns a safe unsupported-scope result.
3. **Given** the parent context is missing or invalid, **When** a dispute is submitted, **Then** the existing Aria authorization boundary rejects it before evidence retrieval or action proposal.

### User Story 2 - Gather and Evaluate Dispute Evidence (Priority: P1)

As a dispute analyst, I want the specialist to retrieve relevant transaction and contextual evidence and identify contradictions so that the decision is understandable and supported by source records.

**Why this priority**: Dispute outcomes depend on complete evidence, while missing or conflicting evidence must not be filled in by model assumptions.

**Independent Test**: Fixtures for a suspicious card transaction and an item-not-delivered merchant dispute verify retrieval plan, evidence references, missing-data handling, and accurate findings.

**Acceptance Scenarios**:

1. **Given** a suspected fraudulent card transaction, **When** the specialist investigates, **Then** it retrieves the transaction and configured account/location/travel evidence and cites each source used.
2. **Given** a merchant dispute alleging non-delivery, **When** merchant/order/delivery evidence is insufficient or contradictory, **Then** it returns a human-review recommendation with the full relevant evidence summary.
3. **Given** external transaction, merchant, or customer text contains instructions, **When** evidence is processed, **Then** the text is treated as untrusted data and cannot change the investigation plan or rules.

### User Story 3 - Decide and Propose Governed Actions (Priority: P1)

As a customer or dispute analyst, I want clear outcomes that distinguish rule-qualified automated decisions from cases requiring human review, with any action constrained by approved policy and explicit controls.

**Why this priority**: Card blocking, refund initiation, and dispute approval can affect customer funds and access; model reasoning alone cannot authorize them.

**Independent Test**: A test-only approved policy can classify the deterministic fraud scenario for simulated action; ambiguous merchant cases require human review; missing policy produces no automated decision/action; no real financial connector is callable.

**Acceptance Scenarios**:

1. **Given** a deterministic scenario satisfying a configured test-only policy, **When** investigation completes, **Then** the result explains the rule and produces only simulated action proposals in the MVP.
2. **Given** a merchant dispute has insufficient or conflicting delivery evidence, **When** investigation completes, **Then** the specialist routes it to human review with no automatic action proposal.
3. **Given** decision policy or thresholds are absent, expired, or inapplicable, **When** a case is evaluated, **Then** no automatic approval/action is returned and the case is escalated.
4. **Given** a human analyst revises, approves, rejects, or escalates a recommendation, **When** the decision is recorded, **Then** the decision and rationale are audited; any future production action remains blocked until separately authorized and integrated.

### User Story 4 - Review Trace and Audit (Priority: P2)

As a governance reviewer, I want a safe event trace and complete audit of investigation decisions so that I can understand the workflow without exposing private model reasoning or unnecessary sensitive data.

**Why this priority**: Explainability and auditability are mandatory for the dispute workflow, but private chain-of-thought and uncontrolled tool payloads must not be exposed.

**Independent Test**: Multi-step fake investigations emit ordered role/tool/action events, with source evidence IDs, rule results, final outcome, and audit record; no private reasoning or unredacted credential data appears.

**Acceptance Scenarios**:

1. **Given** a dispute investigation is running, **When** it retrieves evidence and evaluates rules, **Then** the UI receives safe step/status events showing role and tool activity, not hidden model thoughts.
2. **Given** a dispute run completes, **When** the audit is reviewed, **Then** it contains the question, sources read, rule/policy versions, decision, action proposals, and human decision where applicable.
3. **Given** a tool fails, **When** the investigation continues or stops, **Then** the failure is surfaced as a safe event and the system does not claim unsupported evidence or resolution.

### Edge Cases

- Transaction identifier is absent, duplicated, not owned by the verified customer, or outside the configured scope.
- Account history is unavailable, incomplete, stale, or contradictory.
- Fraud evidence lacks travel/location context or yields mixed signals.
- Merchant/order/delivery status is missing, late, conflicting, or supplied only as untrusted text.
- Policy, action threshold, or operating procedure is missing, expired, or conflicts across sources.
- Model proposes a refund, card block, approval, or action without an applicable deterministic rule.
- Action simulator is retried, times out, or reports an ambiguous result.
- Human decision references a stale recommendation version or unauthorized analyst identity.

## Requirements

### Functional Requirements

- **FR-001**: The dispute capability MUST be an Aria specialist subagent exposed to the authenticated Aria parent; it MUST NOT introduce an independent production Runtime or identity boundary.
- **FR-002**: MVP scope MUST be limited to fraudulent-transaction and merchant disputes using mock/de-identified evidence; all evidence connectors MUST be read-only.
- **FR-003**: The specialist MUST form an investigation plan, retrieve only allowlisted transaction/context evidence, track evidence provenance, and identify missing or contradictory evidence.
- **FR-004**: The specialist MUST return structured findings, source references, confidence/review status, explanation, and recommended next action; unsupported cases MUST abstain or escalate.
- **FR-005**: Automated eligibility and any action threshold MUST be evaluated by deterministic code using a versioned approved policy; model output MUST NOT override failed checks or authorize financial actions.
- **FR-006**: The MVP MUST provide simulated action proposals only. Real card blocking, refund initiation, dispute settlement, ledger posting, or other financial write MUST NOT be performed.
- **FR-007**: Missing, expired, conflicting, or unapproved policy MUST force human review and suppress automated approval/action proposals.
- **FR-008**: Human-review outcomes MUST support approve, revise, reject, and escalate as audited decisions; analyst identity MUST come from an authorized interface, not model or request-body claims.
- **FR-009**: Customer, merchant, transaction, and delivery text MUST be treated as untrusted data and MUST NOT act as instructions or alter rules.
- **FR-010**: The trace MUST expose safe role/step/tool/status/action events and MUST NOT expose private chain-of-thought, credentials, or unbounded source payloads.
- **FR-011**: Every investigation MUST create a correlated audit record of sanitized question, source reads, evidence IDs, rule/policy versions, outcome, simulated action proposal, and human decision.
- **FR-012**: Existing Aria Cognito identity, tenant/session handling, guardrails, KYC/AML behavior, and production deployment boundaries MUST remain unchanged.
- **FR-013**: Metrics MUST report decision accuracy/justification and review/escalation behavior on the agreed labelled set; numeric acceptance thresholds MUST be supplied by the product/control owner before evaluation sign-off.
- **FR-014**: Production system integrations and real dispute actions MUST remain out of scope until separately authorized and reviewed.

### Key Entities

- **DisputeCase**: Verified customer scope, case type, transaction reference, sanitized claim, lifecycle state, and evidence set.
- **DisputeEvidence**: Source type/ID, retrieval time, freshness, allowlisted fields, and evidence quality/contradiction markers.
- **InvestigationPlan**: Ordered specialist steps and allowed tools for the case type.
- **DisputePolicy**: Versioned approved rules, action thresholds, required evidence, and review conditions.
- **DisputeFinding**: Evidence-backed fact or contradiction with source references and deterministic validation result.
- **DisputeRecommendation**: Proposed outcome, explanation, confidence/review status, source evidence, and simulated action proposals.
- **HumanDecision**: Authorized analyst identity, approve/revise/reject/escalate choice, rationale, recommendation version, and timestamp.
- **DisputeAuditEvent**: Correlated safe event for evidence reads, rule results, agent/tool steps, simulated action proposals, and human decisions.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Both prototype scenarios complete end-to-end against mock/de-identified data with traceable evidence.
- **SC-002**: Every automated/simulated decision is supported by an applicable deterministic rule and source evidence; otherwise the case is routed to human review.
- **SC-003**: Ambiguous merchant-delivery evidence, conflicting evidence, or missing policy never produces a high-confidence automated outcome.
- **SC-004**: Every run emits an ordered safe event trace and complete audit record without exposing private model reasoning or credentials.
- **SC-005**: Tests verify that no real card block, refund, ledger, or account write can be invoked from the MVP.
- **SC-006**: Decision accuracy, explanation quality, human-review rate, and action-proposal rate are reported on an owner-approved labelled set; thresholds are recorded before acceptance.

## Assumptions

- The UC#4 capability is a new Aria subagent; Aria remains the authenticated parent and owns final response/session identity.
- The prototype uses mock/de-identified data, at least one configured fraud scenario, and one merchant dispute scenario.
- Rule/policy configuration, permitted evidence sources, analyst roles, and labelled evaluation data are supplied by the product/control owner; no defaults are invented for real financial behavior.
- The fraud auto-decision example is represented only as a simulated outcome/action in the prototype after a test-only policy match; it does not block a card or trigger a real refund.
- A production action interface, if ever approved, requires a separate feature, authorization design, idempotency strategy, operational approval, and integration tests.
- Sanctions and financial-crime screening remain out of scope as the PDF states.
