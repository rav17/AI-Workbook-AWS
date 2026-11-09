# CLI and Host Handoff Contract

## Recommendation

`python -m speckit_flow workflow recommend "<request>" [--profile <id>] [--json]`

Returns an explicit or inferred recommendation; ambiguous input has null profile,
candidate list and `needs_clarification=true`. Always requires human confirmation.
Unknown/unavailable explicit profile: error and nonzero exit; no state writes.

## Dispatch preflight

`python -m speckit_flow workflow dispatch [--stage <stage>] [--feature-dir <path>] [--json]`

Read-only readiness brief for the current route. Errors block dispatch. Completion
has no lead; ready has separated lead/domain supports/reviewers and agent details.
Preflight does not execute tools/models or record stage completion.

## Host entry

`/speckit-workflow <request>` handles classification, confirmation and conductor
dispatch. Direct stage skills use the same path before executing their bodies.
The conductor delegates with `SPECKIT_DELEGATED_STAGE=<stage>`, an explicit
feature directory and lead identity. Only that matching stage lead skips the
handoff. Never approve a gate or invoke another agent from a stage worker.
