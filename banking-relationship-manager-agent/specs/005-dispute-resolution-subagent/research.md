# Research: Dispute Resolution Subagent

**Date**: 2026-10-01
**Source**: UC#4 dispute resolution PNG supplied by the user.

## Decisions

### Aria subagent shape

- **Decision**: Add one dispute specialist as a child Strands `Agent` exposed to the existing Aria parent using the pinned `Agent.as_tool` pattern.
- **Rationale**: Aria owns authentication, tenant/session, and output boundaries. A specialist capability can investigate disputes without a second Runtime or identity system.
- **Alternative rejected**: Six autonomous agents or an autonomous swarm. Role labels in the source (triage, evidence, policy, validation, case) become explicit workflow stages/tool responsibilities under one specialist; deterministic controls and the analyst remain authoritative.

### Evidence and source access

- **Decision**: Define narrow protocols for payment, account/customer, merchant/order/delivery, and policy evidence. MVP implementations use fake/mock or approved de-identified datasets and allowlisted fields.
- **Rationale**: The source asks for transaction and contextual data but explicitly targets a prototype. Evidence provenance and field-level permissions must be testable.
- **Alternative rejected**: Arbitrary model-authored queries or unrestricted database access; they undermine source control and auditability.

### Decisioning and actions

- **Decision**: Deterministic, versioned policy code owns fraud/merchant eligibility, thresholds, and action gating. The subagent may organize evidence, compare hypotheses, and explain outcomes; it cannot set policy or authorize a financial action.
- **Decision**: In the MVP, outputs that resemble automated approval/block/refund are simulated proposals only. Ambiguous, low-confidence, conflicting, missing-policy, or unsupported cases route to human review.
- **Rationale**: The current Aria constitution requires deterministic authorization and safe side-effect boundaries. UC#4 itself emphasizes human-in-loop, explainability, audit, and compliance.
- **External inputs**: Product/control owner supplies approved policies, evidence sources/fields, analyst roles, thresholds, and a labelled evaluation set. No threshold is invented.

### Human approval and audit

- **Decision**: Analyst approve/revise/reject/escalate is represented as explicit state with recommendation versioning. Audit covers each source read, rule result, proposal, revision, decision, and simulated action.
- **Rationale**: A model-generated “approve” is not an authorization. A future live action adapter requires a separate review and cannot be smuggled into this prototype.

### Evaluation

- **Decision**: Report accuracy and justification, governance/audit coverage, human-review rate, and practical workflow outcomes on an owner-approved labelled set. The source provides no numeric thresholds; acceptance targets must be agreed by the owner.

## Current Aria Integration Points

- Parent/tool routing: `aria/agent.py`, `aria/agents/aria/agentcore_entrypoint.py`, and `aria/agents/aria/agent.yaml`.
- Child handoff: pinned Strands `Agent.as_tool` capability.
- Safety: `GuardrailProcessor` for user input, external text, and model output; parent identity/session remains authoritative.
- Existing escalation and observability modules can be reused for human review and safe audit metadata.
- Existing Runtime and Cognito/Gateway/CDK boundaries remain unchanged.

## Risks and Open Boundaries

- No authorized transaction, merchant, delivery, or account data source is supplied in the repository.
- Fraud and merchant dispute policies, analyst authorization, and threshold decisions are owner inputs.
- The UC#4 image's “auto approve / block / refund” examples are not safe production permissions; the MVP only simulates policy outcomes and action proposals.
- Production source connectors, actual financial actions, sanctions/AML, and broader dispute categories are excluded.
