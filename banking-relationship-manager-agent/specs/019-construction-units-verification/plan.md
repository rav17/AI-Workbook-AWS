# Plan: Construction Units and Verification Command (019)

- New `speckit_flow/units.py` holds verify-file handling and unit graph/checkpoints (FR-001 to FR-007).
- `cli.py` adds `units add|list|checkpoint` and `verify propose|approve|show|run`, plus `--verify-file`.
- `state.decide_gate` refuses the `implement` approval while units are unchecked (FR-008).
- Guard regexes extended for `verify approve` and `.specify/verify.json` (FR-004).
- Decision: the command is an argv list run without a shell, bound to a digest so edits invalidate approval. Propose args are passed after `--`.
- Alternative rejected: free-form shell string (injection risk, harder to approve precisely).
