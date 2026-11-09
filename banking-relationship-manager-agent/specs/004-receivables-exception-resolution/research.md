# Research: Receivables Exception Resolution Subagent

**Date**: 2026-10-01
**Source**: UC8 Virtual Account Receivables Exception Resolution Agent requirements summary, 13-page PDF.

## Decisions

### Aria integration

- **Decision**: Implement one receivables specialist as a child Strands `Agent`, exposed through the existing Aria parent with `Agent.as_tool`. Aria remains responsible for validated caller identity, tenant/session context, input/output guardrails, and final response.
- **Rationale**: The use case is a capability of Aria, not a new independently deployed banking agent. This reuses the pinned Strands SDK and the existing Runtime boundary.
- **Alternative rejected**: Six independently autonomous agents. Triage, virtual-account verification, matching, policy retrieval, validation, and case preparation are responsibilities inside one controlled specialist workflow; model autonomy does not replace deterministic checks or the analyst.

### Evidence sources and adapters

- **Decision**: Provide narrow read-only interfaces for payment records, virtual-account master, customer master, open invoices, and the approved procedure/tolerance source. The MVP uses fakes, synthetic fixtures, or approved de-identified data.
- **Rationale**: The PDF requires these sources and explicitly excludes production integration from the MVP. Adapter boundaries make evidence provenance and permission review testable.
- **Alternative rejected**: Direct database access or unrestricted source clients inside the model. The child receives only bounded tool results and cannot choose arbitrary queries or writes.

### Deterministic rules and confidence

- **Decision**: Implement matching eligibility, amount variance, tolerance, effective-date, invoice status, currency, and duplicate/prior-allocation checks in a deterministic rules module before any model recommendation is accepted.
- **Rationale**: A mistaken confident allocation can misstate a customer's ledger. The model may form and compare hypotheses, but it cannot override failed rules or provide authoritative arithmetic.
- **External inputs**: Approved tolerance values, matching weights, confidence thresholds, operating procedure/version, and labelled test set must come from the operations/control owner. The implementation does not invent production values.

### Analyst approval and permitted write

- **Decision**: Represent approve, revise, reject, and escalate as explicit state transitions. The sole write adapter is a case-management task writer; it requires an approved decision, analyst identity, recommendation version, and idempotency key.
- **Rationale**: The PDF permits only a case-management task write after analyst approval and prohibits ledger, account, payment, virtual-account, and master-data changes.
- **Alternative rejected**: Allowing the LLM to call a generic write-capable connector or interpreting a conversational “looks good” as an approval without a validated analyst decision event.

### Audit and evaluation

- **Decision**: Record source identifiers, ordered reads/tool calls, deterministic rule results, recommendation evidence, analyst revisions/decisions, and case-task write outcome. Keep raw source data out of logs; store bounded references/summaries in MVP audit records.
- **Decision**: Evaluate on an agreed labelled set against the PDF's thresholds: classification >=90%, top candidate >=85%, confident allocation precision >=95%, correct escalation >=90%, evidence coverage 100%, variance verification 100%, and zero prohibited financial writes.
- **Rationale**: The PDF prioritizes precision and escalation over forced automation.

## Current Aria Integration Points

- Parent and tools: `aria/agent.py`, `aria/agents/aria/agentcore_entrypoint.py`, and `aria/agents/aria/agent.yaml`.
- Existing child-agent pattern: pinned Strands `Agent.as_tool` is available in `strands-agents==1.34.1`.
- Identity/session: reuse the authenticated parent session and verified principal; do not create a separate Runtime or identity system.
- Safety: apply existing `GuardrailProcessor` to request text, payer/remittance narratives, model output, and analyst notes; treat external text as data.
- Existing workflow models and persistence: use typed results, explicit state transitions, conditional writes, and idempotency where applicable; do not put receivables evidence in long-term Memory.

## Risks and External Dependencies

- No approved procedure, tolerance table, matching policy, confidence thresholds, customer/source access, analyst authorization mapping, or labelled evaluation data is included in the repository; these are explicit owner inputs.
- Source integrations and case-task write are mocked in the MVP. Production access requires separate least-privilege IAM/API design and operations sign-off.
- The MVP excludes sanctions/AML screening; any future requirement must be separately specified and reviewed.
