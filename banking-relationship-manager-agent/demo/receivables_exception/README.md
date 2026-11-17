# Local synthetic receivables exception demo

## Scope and data boundary

This is a local, synthetic-only harness. It uses the approved synthetic fixture catalogue and read-only source adapters. There is no Runtime registration, live integration, production authority, financial/source-record mutation, real-model call, or network path. The sole business write is an immutable create-only synthetic mock case task after analyst approval and explicit confirmation. Internal proposals, decisions, bindings, and audit remain isolated in local SQLite.

## Investigation

The deterministic engine evaluates synthetic source evidence and linked-artifact approval provenance. It distinguishes authoritative source facts from reference-token and payer-name inferences; neither inference repairs mapping or supplies identity. Missing, stale, partial, conflicting, or unapproved evidence fails closed with a safe next step.

## Analyst decision and explicit confirmation

Approve, revise, reject, and escalate are application operations, not model tools. Approval is unavailable for non-recommendations. The exact immutable task payload is displayed before explicit confirmation. Retry identities are server-issued and bound to proposal version, decision revision, trusted context, and payload. A failed or uncertain write is reported as unconfirmed, never as success; an identical retry returns the committed task.

## Accessibility

The demo uses semantic headings, explicit labels, keyboard-operable controls, textual status (not color alone), and announced status/error regions. Native buttons retain visible browser focus.

## Evaluation limits

The 57-case catalogue and labels remain unchanged. Targets are not measured claims; only approved, executed tests establish local observed evidence. Coverage gaps and unexercised surfaces are unmeasured, not zero. Linked-artifact approval provenance is separate from pending/draft policy labels in the fixture; mutable fixture status fields are not approval evidence.

## Synthetic clock semantics

The interactive local demo starts a process-local logical clock at the approved fixture `fixed_clock` and advances it by monotonic elapsed time. Restarting the process resets that logical clock to the fixture anchor. The evaluation harness keeps a fixed clock for reproducibility. Neither clock establishes real-time validity for live evidence or production use.

See the exact approved verification commands in [quickstart.md](../../specs/004-receivables-exception-resolution/quickstart.md). Commands are not duplicated here.
