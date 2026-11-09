# Research

## Optional plugin instead of a mandatory core stage
- Decision: Add `codebase-analysis` after specify, before clarify/plan, in an opt-in brownfield route.
- Rationale: Profile validation requires specify first; the user's need is grounded planning, not changing specification ordering.
- Alternatives: A new first core stage would invalidate established profiles and core-count tests.

## Deterministic applicability, semantic interpretation by architect
- Decision: Reuse one bounded source-extension scanner for inventory and condition checks.
- Rationale: No application execution or provider dependency; explicitly documents heuristic limitations.
- Alternatives: Treat Graphify as mandatory (not installed everywhere); infer architecture automatically from filenames (misleading).

## Safe conditional skips
- Decision: Allow `existing-codebase` only on optional stages, disallow gating conditional stages.
- Rationale: Greenfield skips cannot bypass mandatory work or human approval.
- Alternatives: Prompt-only skipping is unaudited; unrestricted `stage skip` invites approval bypass.

## Portable distribution
- Decision: Explicitly list new engine, skill and plugin files in the portable allowlist.
- Rationale: Changes must work in a non-banking target; no live policy copied.
- Alternatives: Recursive directory exports would reintroduce unrelated project content.
