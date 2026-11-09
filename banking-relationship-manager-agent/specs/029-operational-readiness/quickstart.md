# Quickstart

1. Human: review and enable `.specify/plugins/operational-readiness/plugin.json`.
2. Restart CLI/session, run `python -m speckit_flow plugins validate` and doctor.
3. Select `release-ready` for the intended feature through the profile workflow;
   the static default feature workflow is unchanged.
4. Follow specify/plan/tasks/implement and normal human gates. For deploy,
   pipeline-deploy follows `speckit-readiness`, copying plugin templates to
   feature-local `release.md` and `runbook.md` only if absent.
5. Fill actual procedures and evidence, not invented execution results. Run
   `python -m speckit_flow sensors run deploy --actor agent:pipeline-deploy`.
6. Human reviews evidence then approves deploy if appropriate. This records a
   lifecycle decision, not an actual deployment. Do not execute production work.
7. Operations follows the same skill for operate, updates the handoff/feedback,
   reruns sensors, and stops at the human operate gate.

Changes to either record stale readiness results. Immutable external evidence
references are recommended; linked evidence changes are not automatically
detected. Live checks still need the receiving project's normal authorization.

## Approved validation

`python -m pytest tests\unit\speckit_flow tests\unit\test_speckit_bootstrap.py -q`,
Ruff/mypy on changed Python, and read-only doctor. Simulated approvals are
authorized only in disposable fixtures. No real project approval is generated.

## Verification results

- Approved workflow/bootstrap suite: **345 passed, 3 skipped**.
- Ruff and mypy: clean on all four changed Python files.
- Doctor: nine profiles, nine core stages, 15 agents, six default sensors;
  all four optional packs remain disabled. No initialized feature state exists.
- Plugins validation: all four packs valid and disabled.
- `graphify update .`: AST-only graph refreshed, no LLM/API calls.
- No extension hooks configured (`.specify/extensions.yml` absent).

Installed non-banking fixture completed the release-ready route, including both
deploy and operate gates. Missing evidence, changed records and agent approvals
were refused; human fixture decisions cited the readiness sensor in audit.
No verify command was approved or generated and no deployment/live check ran.
The tests also cover both record size boundaries, placeholders, comments/code,
duplicate headings, missing sections/evidence, invalid UTF-8, access failure,
reparse metadata, record deletion and changes during validation. Other sensors'
fingerprint scope is unchanged.

Two skips are unavailable symlink creation on this Windows machine (codebase
analysis and readiness). A reparse-metadata rejection test and existing Windows
junction traversal test passed. The third is the pre-existing missing
`specify_cli.workflows.engine` dependency. These are deterministic CLI/unit
checks, not live LLM-generated records or a real second project's harness test.
