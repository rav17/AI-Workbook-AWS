# Specification Quality Checklist: KYC/AML Verification Subagent

**Purpose**: Validate UC3 scope, safety boundaries, and testability before planning
**Created**: 2026-10-01
**Feature**: [spec.md](../spec.md)

## Aria Integration and Scope

- [x] Capability is a bounded Aria subagent and retains parent authentication/session ownership
- [x] Document extraction and cross-source verification are explicit, separate workflow stages
- [x] Live provider/vendor/jurisdiction choices are not invented
- [x] The existing KYC status helper is distinguished from full document-based KYC/AML investigation

## Safety and Governance

- [x] Source adapters are read-only and injectable
- [x] Missing, malformed, conflicting, or unavailable evidence fails closed
- [x] Risk policy, source priority, AML thresholds, and escalation rules require owner approval
- [x] Model output cannot mark KYC current, clear AML, or authorize financial/compliance actions
- [x] Raw documents and credentials are excluded from logs, prompts, and long-term Memory
- [x] Human review is required for conflicts, incomplete evidence, unsupported documents, and policy gaps

## Requirements and Testing

- [x] User stories have independent test criteria and acceptance scenarios
- [x] Fake-backed tests cover providers, conflicts, failures, escalation, and parent isolation
- [x] Audit events separate verified observations, deterministic findings, hypotheses, and analyst decisions
- [x] Success criteria are measurable without claiming production integration
- [x] No unresolved clarification markers or template placeholders remain

## Notes

- Checklist completion indicates requirements quality only, not implementation completion.
- Live provider contracts, jurisdiction-specific document rules, and retention policy remain external decisions.
