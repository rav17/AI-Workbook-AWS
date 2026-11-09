# Quickstart

1. As a human, enable `.specify/plugins/codebase-analysis/plugin.json`.
2. Restart the CLI/session so stage definitions reload; run
   `python -m speckit_flow doctor` and `profiles validate`.
3. Use a feature with profile `brownfield`. Complete specify and obtain the
   human specify gate decision normally.
4. Ask the conductor to start `codebase-analysis`. In a recognized existing
   codebase, the architect follows `/speckit-codebase` and writes `codebase.md`.
   In a tooling-only/new project, the stage is skipped with an audited reason.
5. Continue clarify and plan. Plan reads the analysis, checks cited files against
   current source, and records unresolved questions.

`python -m speckit_flow codebase scan` is also available for read-only inventory
without enabling the plugin. It does not generate semantic findings.

Validation uses targeted scanner/stage/bootstrap tests in temporary projects.
No actual project gates or verification commands are approved by these tests.

## Verification evidence

The user approved the focused workflow/bootstrap suite, Ruff/mypy and doctor,
including simulated human decisions only in disposable fixtures.

- `python -m pytest tests\unit\speckit_flow tests\unit\test_speckit_bootstrap.py -q`:
  **302 passed, 2 skipped**.
- Added final boundary/failure/junction checks and ran
  `python -m pytest tests\unit\speckit_flow\test_flow_codebase.py -q`:
  **18 passed, 1 skipped**.
- Ruff and mypy passed on all seven changed Python files.
- Doctor: nine core stages, nine default profiles, all three packs disabled;
  no initialized feature state was present to check.
- `graphify update .` refreshed the AST graph without LLM/API calls.

One skip is unavailable symlink creation on this Windows machine; a real
Windows junction exclusion test passed. The other is the pre-existing missing
`specify_cli.workflows.engine` dependency. Installed-project subprocess tests
verified both source-present and tooling-only paths, architect assignment,
plugin disablement, pending-gate refusal, audited skip and advancing to clarify.
They do not establish live AI-generated semantic analysis or a real second
project's harness integration; those remain untested.
