# Ideation Brief: Virtual Account Receivables Exception Resolution

**Date**: 2026-11-10

## Problem
Receivables operations analysts manually correlate inbound payment records, virtual-account mappings, customer and invoice details, and operating procedures when a payment cannot be allocated automatically. This can delay investigation and produce inconsistent case documentation. Exceptions include missing or invalid mappings, amount or reference mismatches, competing invoice candidates, and suspected duplicates.

The intended users are virtual-account and receivables operations analysts who investigate exceptions, and product/control reviewers who evaluate whether the process is safe and effective. The capability should help analysts reach an evidence-backed decision without transferring financial decision authority to an agent.

## Desired outcome
For the approved UC8 use case, an analyst can ask Aria to investigate a supported payment exception and receive a clear, evidence-backed proposal—or an explicit no-confident-recommendation outcome. The analyst can approve, revise, reject, or escalate the proposal. Evidence and decisions are traceable, while financial records remain unchanged.

The initial scope is one corporate customer, one currency, and three exception categories: invalid or missing virtual-account mapping, amount/reference mismatch, and suspected duplicate. Source records are read-only. The only permitted write in the controlled prototype is an owner-approved, synthetic mock case-task after analyst approval. The mock approver role is `receivables_operations_analyst`; this represents synthetic fixture behavior only, not production authorization.

### Proposed success measures
These are acceptance targets, not measured results. Metrics must not be claimed until an owner-agreed labelled test set is available and evaluated.

| Measure | Target |
|---|---:|
| Exception classification accuracy | At least 90% |
| Top-candidate accuracy for supported cases | At least 85% |
| Precision of recommendations presented as confident | At least 95% |
| Correct escalation of applicable low-confidence, conflicting, or duplicate-suspected cases | At least 90% |
| Recommendations with verifiable evidence | 100% |
| Recommended allocations with reproducible variance calculations | 100% |
| Prohibited financial mutations in test/demo paths | Zero |
| Audit coverage of retrievals, recommendations, analyst decisions, and permitted mock case-task writes | 100% |

Report incorrect-allocation rate explicitly alongside confident-recommendation precision.

## Options considered
| Option | Pros | Cons |
|--------|------|------|
| Continue manual investigation | Preserves current decision process; no agent-related risk | Retains manual evidence gathering and potential variation in case documentation |
| Deterministic matching workflow only | Predictable checks and outcomes; straightforward to test | Less adaptable when evidence is incomplete or conflicting; may not help analysts navigate investigation |
| Human-supervised, evidence-grounded Aria specialist | Can assist with investigation and explanation while keeping decisions with analysts; supports explicit escalation | Requires agreed policy, labelled evaluation data, evidence handling, and accessible review experience |
| Autonomous allocation or financial action | Could reduce analyst handling for straightforward cases | Exceeds the requested control boundary and risks unauthorized or incorrect financial changes |

## Recommendation
Proceed with the human-supervised Aria specialist for the bounded UC8 scope. It should gather and explain evidence, present supported candidates and deterministic variance results, and provide an explicit no-recommendation/escalation state where evidence or policy is insufficient. Every recommendation remains a proposal for analyst review; no autonomous allocation or financial mutation is in scope.

The investigation must rely on owner-approved, versioned operating procedures and matching/tolerance policy. Missing or inapplicable policy, unresolved conflicts, invalid mappings, suspected duplicates, or insufficient evidence should prevent a confident recommendation. Payer names, remittance references, and narratives are untrusted data, not instructions or authoritative identity.

Supporting review found no receivables implementation in the inspected paths. It recommended reusing the existing parent identity/session boundary and statement-specialist pattern. Design input also calls for accessible analyst choices and clear no-confident-recommendation states. These findings inform the direction; they do not establish implementation readiness or approve a lifecycle gate.

## Open questions and risks
- The receivables operations/control owner must supply or approve the applicable procedure, tolerance values, matching/confidence policy, and labelled test set. Their specific contents are not established here.
- The evaluation set and labels must be agreed before reporting results against the proposed targets.
- Synthetic data and mock case-task fixtures require owner approval. The mock approver role does not grant production authorization.
- Source availability, freshness, and contradictory records may prevent a recommendation; the user experience must make those limitations understandable and support escalation.
- Any future production integration, expanded customer or currency coverage, or financial action requires separate review and approval.
- Approval of UC8 as the requested use case and selection of the full-lifecycle profile do not constitute approval of any stage gate.
