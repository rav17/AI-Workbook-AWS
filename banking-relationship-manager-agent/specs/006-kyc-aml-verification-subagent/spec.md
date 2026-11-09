# Feature Specification: KYC/AML Verification Subagent

**Feature Branch**: `006-kyc-aml-verification-subagent`
**Created**: 2026-10-01
**Status**: Draft
**Input**: UC3 KYC/AML Agentic AI one-page requirements PDF, implemented as a bounded Aria specialist capability.

## User Scenarios & Testing

### User Story 1 - Extract Identity Evidence (Priority: P1)

As a compliance analyst, I want identity attributes extracted from an explicitly supported document reference with field-level confidence and provenance so that I can review evidence without relying on untraceable model claims.

**Why this priority**: Document understanding is the first stage in the source workflow, but extracted values are observations—not verified identity facts.

**Independent Test**: Fake document extractors return typed observations for representative document fixtures; missing, low-confidence, unsupported, and malformed fields produce explicit gaps without persisting raw document content.

**Acceptance Scenarios**:

1. **Given** a supported test document reference, **When** extraction runs, **Then** the result contains normalized field observations, confidence, document type, and evidence reference.
2. **Given** an unsupported document type, missing provider, or low-confidence field, **When** extraction runs, **Then** the specialist marks the field unavailable/uncertain and escalates rather than guessing.
3. **Given** a document contains prompt-like instructions or credentials, **When** it is processed, **Then** content is treated as untrusted data, redacted where needed, and never placed in long-term Memory or ordinary logs.

### User Story 2 - Cross-Verify Identity Evidence (Priority: P1)

As a compliance analyst, I want extracted identity observations compared with multiple authorized verification sources so that mismatches, missing sources, and contradictory records are made explicit.

**Why this priority**: Verification is the core safeguard that distinguishes a KYC decision from simple document parsing.

**Independent Test**: Fake source adapters provide matching, conflicting, missing, stale, and unavailable observations; the deterministic verifier produces reproducible field-level outcomes and source provenance.

**Acceptance Scenarios**:

1. **Given** matching document and source observations, **When** verification runs, **Then** it reports which fields matched and cites each source reference.
2. **Given** a material field conflict, **When** verification runs, **Then** it reports both observations and sources and requires review; it does not choose the preferred source using model judgment.
3. **Given** a verification source is unavailable or no source-priority policy is configured, **When** verification runs, **Then** status is incomplete and the case is escalated.

### User Story 3 - Assess Risk and Escalate Transparently (Priority: P1)

As a compliance officer, I want risk and escalation decisions grounded in approved rules, with reasons and evidence, so that high-risk or ambiguous cases receive human review.

**Why this priority**: UC3 requires context-aware assessment and smart escalation; without approved risk policy, the safe outcome is an explicit unassessed state.

**Independent Test**: An approved test-only policy and fake evidence exercise deterministic risk-rule results, escalation categories, and explanation provenance; absent policy always returns `unassessed` and human review.

**Acceptance Scenarios**:

1. **Given** complete verified evidence and an applicable approved policy, **When** assessment runs, **Then** it returns the policy version, deterministic findings, explainable risk factors, and next step.
2. **Given** contradictory identity evidence, an AML alert, incomplete sources, or an unavailable policy, **When** assessment runs, **Then** it routes to human review with reasons and evidence references.
3. **Given** a case is escalated, **When** the analyst receives it, **Then** the case summary distinguishes verified facts, model hypotheses, missing evidence, and policy-derived findings.

### User Story 4 - Integrate Safely with Aria (Priority: P2)

As an Aria user, I want KYC/AML work routed to a specialist without changing Aria's parent authentication or allowing a model to approve compliance status.

**Why this priority**: The capability must fit Aria's established identity, session, guardrail, and provider-injection boundaries.

**Independent Test**: Parent-agent tests prove only compliance-related requests are delegated, verified identity/session context is preserved, unsupported provider configuration fails closed, and unrelated Aria behavior is unchanged.

**Acceptance Scenarios**:

1. **Given** a supported KYC/AML request, **When** Aria routes it, **Then** the specialist receives only the authenticated subject/tenant context and bounded evidence references.
2. **Given** an ordinary banking query, **When** Aria handles it, **Then** the compliance specialist is not invoked.
3. **Given** document extraction or verification requests a status change, **When** the specialist completes, **Then** it returns a recommendation for authorized human review and does not directly mark KYC current or clear an AML alert.

### Edge Cases

- Document type or jurisdiction is unsupported or not configured.
- Extracted identity fields are missing, malformed, low-confidence, expired, or conflict across sources.
- A source returns stale, duplicate, malformed, or contradictory records.
- Provider timeout, rate limit, authorization failure, or partial multi-source outage.
- Risk policy, source precedence, threshold, or escalation mapping is missing, expired, or conflicts across versions.
- External document text attempts prompt injection or includes credential-like content.
- A duplicate case or concurrent analyst decision references stale evidence/recommendation version.

## Requirements

### Functional Requirements

- **FR-001**: The capability MUST be an Aria specialist subagent exposed to the existing parent; Aria remains authoritative for authentication, tenant/session identity, final response, and output safety.
- **FR-002**: Document extraction MUST use an injectable provider contract and return typed field observations with confidence and source references; raw documents MUST NOT be logged, sent to long-term Memory, or copied into ordinary prompts.
- **FR-003**: Verification MUST use injectable, allowlisted read-only source contracts and return field-level match, mismatch, unavailable, or incomplete results with provenance.
- **FR-004**: Source precedence, accepted document types/jurisdictions, normalization, and material-conflict rules MUST be explicit approved configuration; the model MUST NOT invent or select these rules.
- **FR-005**: Risk assessment MUST be deterministic and policy-versioned; when an approved policy is unavailable or inapplicable, status MUST be `unassessed` and escalation required.
- **FR-006**: AML findings MUST be sourced from configured evidence and approved rules; the standalone threshold helper MUST NOT be treated as an integrated AML monitoring provider.
- **FR-007**: Missing, malformed, unsupported, conflicting, or unavailable provider responses MUST fail closed and MUST NOT produce a current/cleared compliance status.
- **FR-008**: The specialist MUST return structured findings, evidence references, policy version, uncertainty/missing-data reasons, and an explicit human-review recommendation where needed.
- **FR-009**: The specialist MUST NOT autonomously approve KYC, clear AML alerts, block accounts, file regulatory reports, or perform any financial/compliance action.
- **FR-010**: Audit events MUST distinguish source-verified observations, deterministic findings, model-generated hypotheses, and analyst decisions; events MUST exclude raw documents, credentials, and hidden chain-of-thought.
- **FR-011**: Fake-backed tests MUST cover extraction, multi-source conflicts, provider failures, policy absence, escalation, redaction, and Aria parent isolation before any live integration.
- **FR-012**: Existing Aria Cognito, tenant/session, Guardrail, Runtime resource-policy, and fail-closed recommendation boundaries MUST remain unchanged.

### Key Entities

- **IdentityDocumentReference**: Opaque reference, document type, issuing jurisdiction if configured, and source metadata; no raw document bytes in ordinary state.
- **ExtractedIdentityObservation**: Field name, normalized/masked value, confidence, document reference, and extraction timestamp.
- **VerificationObservation**: Field/source pair, normalized/masked value, verification status, freshness, and provenance reference.
- **IdentityConflict**: Field, competing observations, materiality from approved policy, and review reason.
- **CompliancePolicy**: Versioned source precedence, document requirements, conflict rules, risk rules, AML indicators, and escalation mapping supplied by authorized owners.
- **ComplianceAssessment**: Verified matches/conflicts, risk findings, policy version, completion status, missing evidence, and human-review decision.
- **ComplianceAuditEvent**: Correlated source retrieval, extraction, deterministic check, escalation, and analyst-decision metadata.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Supported document fixtures produce typed field observations with source references; unsupported/low-confidence fields are never represented as verified facts.
- **SC-002**: Matching/conflicting multi-source fixtures produce deterministic field-level verification results with full provenance.
- **SC-003**: Missing provider, malformed response, source conflict, or missing policy never results in KYC-current or AML-cleared status.
- **SC-004**: All high-risk, conflicting, or incomplete fixture cases produce an explainable human-review outcome.
- **SC-005**: No test or runtime path logs/persists raw document content, credentials, or hidden reasoning in audit/Memory.
- **SC-006**: Existing Aria authentication, tenant isolation, KYC fail-closed, product-gating, and unrelated route tests remain green.

## Assumptions

- Until owners specify jurisdictions and provider contracts, implementation uses generic typed extraction observations and fake adapters only; no real OCR or external-source vendor is selected.
- The one-page UC3 source does not provide source precedence, supported document field schemas, risk factors, AML thresholds, or retention periods; these remain explicit owner inputs.
- The existing standalone AML threshold function remains a utility only and is not represented as an AML monitoring integration.
- Raw identity documents are never sent to AgentCore Memory; local fake tests use synthetic values and masked audit summaries.
- Human compliance review is required for every conflict, missing source, unsupported document, or policy gap.
