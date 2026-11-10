# Research: KYC/AML Verification Subagent

**Date**: 2026-10-01
**Source**: UC3 KYC/AML Agentic AI requirements PDF.

## Decisions

### Aria integration

- **Decision**: Implement one KYC/AML specialist as a child Strands Agent exposed to the authenticated Aria parent with a bounded tool handoff.
- **Rationale**: Aria retains identity/session, tool authorization, guardrails, and final response. The compliance specialist cannot establish its own identity or approve its own result.
- **Alternative rejected**: A second Runtime, independent unauthenticated endpoint, or model-only agent swarm; these duplicate boundaries and make compliance ownership ambiguous.

### Document extraction

- **Decision**: Define an injectable extraction protocol that returns typed field observations with confidence and evidence references; local implementation uses fakes until a document provider and jurisdiction are approved.
- **Rationale**: UC3 lists PAN/passport/driver-license examples but does not specify a country, supported fields, OCR vendor, validation rules, or retention.
- **Constraint**: Raw document bytes and full identity numbers are not logged, put in prompts/Memory, or retained in workflow state. Tests use synthetic values and masked summaries.

### Multi-source verification

- **Decision**: Use read-only provider protocols and deterministic field normalization/comparison; record each source observation and produce match/mismatch/missing/stale outcomes.
- **Rationale**: Conflict resolution must be reproducible and evidence-backed. Source priority and what constitutes a material mismatch require a compliance owner.
- **Alternative rejected**: Letting the LLM choose which source is authoritative or treating a single extraction as verified identity.

### Risk and AML decisioning

- **Decision**: Add a versioned policy interface and deterministic assessment rules, but no default score, thresholds, or jurisdiction-specific requirements. Missing policy returns `unassessed` and human review.
- **Rationale**: The PDF names context-aware risk and AML escalation but supplies no risk factors, thresholds, or approved decisions. Inventing them would create false compliance assurance.
- **Existing code**: The standalone AML helper now validates inputs and thresholds, but it is not connected to transaction/source evidence. The existing KYC status provider remains injectable and fail-closed.

### Audit and escalation

- **Decision**: Emit correlated safe audit events for extraction, source reads, comparisons, policy version, escalation reason, and analyst decision. Store masked values/evidence references only.
- **Rationale**: Investigators need explainability and data minimization; chain-of-thought and raw documents are not audit evidence.

## Aria Integration Points

- `aria/tools/compliance_tool.py`: existing `KYCStatusProvider` and `check_kyc_status` fail-closed contract.
- `aria/agent.py`: parent currently accepts an injectable KYC status provider; product gating blocks when it is absent or invalid.
- `aria/agents/aria/agentcore_entrypoint.py`: current Runtime does not configure a live compliance provider and must remain fail-closed.
- `aria/guardrails/processor.py`, `aria/observability.py`, and `aria/api/runtime_session.py`: reuse input safety, redaction-safe metadata, and parent session identity.

## External Decisions Required

- Supported countries/document types and required identity fields.
- Authoritative KYC/document and verification sources, source precedence, credentials, and least-privilege access.
- AML/risk indicators, thresholds, scoring weights, escalation categories, and who can override a review.
- Raw-document retention, masked-value handling, audit retention, and evidence deletion requirements.
- Labelled test/evaluation cases and minimum accuracy/false-positive/false-negative acceptance criteria.
