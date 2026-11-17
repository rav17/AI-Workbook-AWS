# Tasks: Copilot Compatibility Diagnostics

**Input**: [spec.md](spec.md), [plan.md](plan.md).
**Profile**: Confirmed quick inline; tasks gate before implementation.
**Scope**: Diagnostic accuracy only; no enforcement changes or runtime proof.

## Phase 1: User Story 1 - Accurate Diagnosis (P1 / MVP)

**Independent test**: Written contract distinguishes a missing invocation
parameter, failed named-worker selection, observed forbidden delegation and
unknown enforcement evidence without changing the existing stop.

- [x] T001 [US1] Extend the existing instruction-contract tests in `tests/unit/speckit_flow/test_flow_orchestration.py` for FR-001, FR-002 and FR-003: absence of a per-call override alone is not unsupported enforcement; unknown enforcement remains unverified; record the focused failing result before instruction changes.
- [x] T002 [US1] Clarify `.github/agents/speckit-conductor.agent.md` body for FR-001 through FR-004: preserve the original stop/frontmatter, distinguish configured tools from runtime evidence, and require a precise failure or missing-evidence explanation without generic substitution.

## Phase 2: User Story 2 - Honest Guidance (P2)

**Independent test**: Read conductor and profile guidance side by side; neither
claims static tests establish live-host permissions or unblock feature 039.

- [x] T003 [US2] Update the named-agent host setup section in `docs/speckit-profiles.md` and cross-reference it from worker execution guidance for FR-001, FR-002, FR-003, FR-005 and FR-006; preserve smoke-test/stop requirements and disclose the limits of absence-of-nesting observations.
- [x] T004 [US2] Add or extend focused checks in `tests/unit/speckit_flow/test_flow_orchestration.py` for FR-004 through FR-006: retain no-substitution/stops and consistent documentation evidence limits; reuse existing frontmatter parsing and worker-tool checks rather than inventing runtime attestation.

## Phase 3: Verification and Closure

- [x] T005 Run the commands below for FR-005 and SC-002; inspect the scoped delta for FR-004/SC-003, preserve user edits and record actual results in `tasks.md`.
- [x] T006 Run required implement sensors and `graphify update .`, report wider failures separately, and record FR-006/SC-004 limits in `tasks.md` and the final handoff; do not claim feature 039 was unblocked.

## Dependencies and Execution Order

T001 -> T002 -> T003 -> T004 -> T005 -> T006.
No parallel authoring is proposed: the test edits share a file and documentation
must align with the completed diagnostic wording. US1 is the smallest useful
increment; US2 makes its meaning clear to receiving developers.

## Verification Scope for Human Approval

From `banking-relationship-manager-agent`:

```powershell
python -m pytest tests\unit\speckit_flow\test_flow_orchestration.py -q
python -m ruff check tests\unit\speckit_flow\test_flow_orchestration.py
python -m ruff format --check tests\unit\speckit_flow\test_flow_orchestration.py
```

Expected: targeted tests and scoped Ruff pass; the new diagnosis check fails
before the instruction correction. Existing worker tool/rooted-command checks
continue to pass. Manually compare the two instruction locations, frontmatter,
and protected-scope delta. These are instruction-contract checks, not permission
enforcement tests. No live host, raw log access or new worker invocation is
authorized by this task list.

Run configured implement sensors as `agent:workflow`; their wider checks remain
separate evidence, with failures disclosed rather than silently waived. Run
`graphify update .` after code/test changes.

## Requirement and Outcome Coverage

| Requirement | Tasks | Success criteria |
|-------------|-------|------------------|
| FR-001 | T001, T002, T003 | SC-001 |
| FR-002 | T001, T002, T003 | SC-001 |
| FR-003 | T001, T002, T003 | SC-001, SC-003 |
| FR-004 | T002, T004, T005 | SC-002, SC-003 |
| FR-005 | T001, T003, T004, T005 | SC-002 |
| FR-006 | T003, T004, T006 | SC-004 |

## Evidence

The human ran the tasks approval command and approved the displayed verification
scope before implementation. No independent reviewer is assigned to quick.

- New diagnosis checks failed before instruction changes: 2 failed, 76 deselected.
- User-provided pre-change baseline: 1 failed, 73 passed, 2 skipped; the failure
  was Windows `os.replace` access denied in a temporary state file. Scoped Ruff
  lint passed; format check failed on existing lines. These are not new failures
  caused by this diagnostic correction.
- Final affected-file pytest: **76 passed, 2 skipped**, exit 0. Both skips are
  optional `specify_cli.workflows.steps.prompt` imports; the new checks ran.
  The user's earlier temporary-state Windows replacement failure did not recur
  in this run; its cause has not been established or fixed by this feature.
- Final scoped Ruff lint: **pass**, exit 0. An initially introduced 101-character
  test signature was wrapped; the final lint check ran after that correction.
- Final scoped Ruff format check: **fail**, exit 1. The file already failed the
  user's pre-change format check. Existing formatting is deliberately preserved;
  no whole-file formatting or unrelated cleanup was performed.
- Pylance file syntax validation: **no syntax errors**.
- `graphify update .`: **pass**, exit 0. AST graph updated; 34 unsupported files
  skipped and community labels need refreshing. No LLM label refresh was run.
- Configured implement `lint` and `unit-tests` sensors: **fail / fail**, both
  exit 1. Their runner captures subprocess output but records only the exit
  code, so final wider-suite counts and failure attribution are unavailable.
  This feature does not claim either wider check passed or that all such
  failures are pre-existing. They were run once, without retrying unchanged
  failures or changing sensor configuration. The sensor task fingerprint
  predates this evidence-only task update; no fresh passing sensor is claimed.
- All six checkboxes mean the listed actions were performed, not that every
  validation command passed. The wider failures and existing formatting failure
  remain outstanding outside this narrow diagnosis correction.
- No live runtime enforcement has been tested. Worker frontmatter, guards,
  permissions, human decisions and feature 039 were not modified by the change.
  Feature 039 remains explicitly blocked on its own host-capability requirement;
  this correction does not authorize or certify its resumption.
