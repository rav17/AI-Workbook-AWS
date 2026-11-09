# Quickstart

1. Human enables `.specify/plugins/walking-skeleton/plugin.json`, restarts CLI
   and validates plugins/doctor. Select `skeleton-first` via profile workflow.
2. Complete specify/plan/tasks and their normal human gates.
3. Developer follows `speckit-skeleton`: choose one journey; create feature-local
   `skeleton.md` from plugin template and actual implementation + executable test.
4. Define unit `walking-skeleton`, linked to actual task IDs and tracked files
   (including report, source and test). Propose the project's actual verify
   command and stop for human approval. Do not copy this project's command.
5. Run the unit checkpoint. Failed, changed or unapproved checks cannot pass.
   Run skeleton sensors; stop at its human gate with exact observable results.
6. Human reviews scope/mocks/evidence and approves if appropriate. Only then
   start full implement. Add later units without losing earlier checkpoints.

Only declared files are source-bound. Include dependencies, fixtures and test
configuration needed for the slice. Humans must review coverage; the toolkit
cannot infer that a command or three files prove a real end-to-end journey.

## Approved validation

Workflow/bootstrap pytest suite, Ruff/mypy and doctor. Simulated gates and verify
approvals are authorized only in disposable fixtures. No real approval or live
application/service is involved.

## Verification results

- `python -m pytest tests\unit\speckit_flow tests\unit\test_speckit_bootstrap.py -q --tb=short`:
  **378 passed, 4 skipped**.
- Ruff/mypy: clean on all five changed Python files. Whitespace checks clean.
- Doctor: nine core stages, nine default profiles, 15 agents and six default
  sensors; all five optional packs remain disabled. No initialized feature
  lifecycle state exists to check.
- Plugin validation: all five packs valid/disabled.
- `graphify update .`: AST graph refreshed without LLM/API calls.
- No extension hooks configured (`.specify/extensions.yml` absent).

Installed non-banking fixture verified real JSON stdin -> entry -> filtering ->
exact JSON stdout (`["B", "C"]`), excluding read title A and preserving order.
It refused the gate before checkpointing, after report edits and for agent
approval attempts. Fixture-only human decisions allowed implement to start;
adding its next unit retained the earlier checkpoint.

Tests cover exact 100-file/1-MiB limits, unsafe paths/aliases, missing/access/
non-file errors, reparse metadata and a real Windows junction, source/test/
report edits, definition/command changes, timeout/failing rechecks and changes
during verification. Only declared files are source-bound; human scope review
is still necessary.

Three skips are unavailable symlink creation on this Windows machine (codebase,
readiness and skeleton). The fourth is the pre-existing missing
`specify_cli.workflows.engine` dependency. These are deterministic CLI/unit
tests, not live LLM-generated slices or real second-project harness validation.
Parallel PowerShell checks initially failed from host resource exhaustion
(paging-file/stack errors); serial retries completed successfully. No machine
configuration or unrelated processes were changed.
