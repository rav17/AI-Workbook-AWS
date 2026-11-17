# Tasks: Explicit Delegation Assurance

**Input**: Human-approved [spec.md](spec.md), independently reviewed [plan.md](plan.md),
[data model](data-model.md), [CLI contract](contracts/assurance-cli.md).
**Route**: Selective; implementation inline with no assigned workers.
**Verification**: Human approved the four exact plan commands, configured sensors,
Python syntax checks and AST-only Graphify update. No live-host certification.

## Phase 1: Setup

- [x] T001 Confirm current practices and preserve existing changes in the affected files listed in `plan.md`; establish the relevant existing-test baseline without altering 039.

## Phase 2: Foundation

- [x] T002 Add the single acceptance audit event to `speckit_flow/models.py` and `specs/009-workflow-profiles-audit/contracts/audit-event.schema.json`, retaining existing event validation and state meanings (FR-003, FR-007).

## Phase 3: User Story 1 - Explicit bounded acceptance (P1)

**Independent test**: No acceptance stops; a current human acceptance permits only
the missing-evidence exception, with an explicitly unverified status.

- [x] T003 [US1] Write failing acceptance/status CLI tests in `tests/unit/speckit_flow/test_flow_assurance.py`, covering absent acceptance, human/agent actors, context, inspectable disclosure and the unchanged stage/route (FR-001--FR-004, FR-008).
- [x] T004 [US1] Implement scoped audit acceptance/status in `speckit_flow/assurance.py`: "host/session identifiers (24/64 characters)", "rationale and observation (60 characters each)", aggregate "500-character event limit", redaction before writing, and current-scope validation (FR-001--FR-004).
- [x] T005 [US1] Add explicit acceptance/status commands and honest text/JSON output in `speckit_flow/cli.py`; expose non-authorizing inspection in `speckit_flow/orchestration.py` without redefining ready as runtime certification (FR-002, FR-008).

## Phase 4: User Story 2 - Preserve boundaries (P1)

**Independent test**: Excluded modes, actual failures and changed scope cannot use
acceptance to override their stops.

- [x] T006 [US2] Add focused strict-mode, stale/malformed-audit, changed-worker/session, redo/reset and gate/call-preservation cases in `tests/unit/speckit_flow/test_flow_assurance.py`; update the changed-policy contract in `tests/unit/speckit_flow/test_flow_orchestration.py` (FR-005, FR-006, FR-007, FR-008, FR-010).
- [x] T007 [US2] Enforce eligible ordinary profiles/core pre-release stages, current configuration and retry boundaries in `speckit_flow/assurance.py`, preserving independent lifecycle/recovery checks and explicit invalid-input errors (FR-003--FR-007).
- [x] T008 [US2] Extend human-decision detection in `scripts/speckit_guard.py` and add a focused regression in `tests/unit/speckit_flow/test_flow_guard.py`, including forged human actors through agent tools (FR-001, FR-007).
- [x] T009 [US2] Update the conditional exception, context source and risk/identity limits in `.github/agents/speckit-conductor.agent.md`, `.github/skills/speckit-workflow/SKILL.md` and `docs/speckit-profiles.md`; retain frontmatter and strict hybrid checks (FR-005--FR-008).

## Phase 5: User Story 3 - Existing-feature compatibility (P2)

**Independent test**: Applying the mechanism to a temporary initialized feature
does not rewrite its earlier audit, assignments, stage state or approvals.

- [x] T010 [US3] Add existing-feature and read-only inspection regressions in `tests/unit/speckit_flow/test_flow_assurance.py`, proving no automatic route/status changes or cross-feature reuse (FR-009, FR-010).
- [x] T011 [US3] Include `assurance.py` in `scripts/speckit-portable-bundle.json` and document the separate human acceptance/resume procedure in `docs/speckit-profiles.md`, without accepting or resuming 039 (FR-009).

## Phase 6: Validation and handoff

- [x] T012 Run the approved focused pytest/lint/format/type commands from `plan.md`, Python syntax checks, configured implement sensors and AST-only Graphify update; record actual results and failures here (FR-010).
- [x] T013 Prepare final status evidence for selective inline accounting and the handoff, including residual uncertainty, known failures, no code-review claim and 039's unchanged state (FR-007--FR-010).

## Dependencies and execution

T001 precedes all edits. T003 precedes T002/T004/T005 so the acceptance reproducer
fails first; T002 then provides the event foundation. T006 precedes T007--T009;
T010 precedes T011. T012 follows all implementation; T013 follows T012.
Shared module/test changes stay serial. Independent file reads and checks may
run in parallel; no implementation worker calls are assigned.

US1 is the smallest functional increment, but ship only with US2 boundary tests
and US3 compatibility. Each story's stated independent tests are distinct from
runtime certification. Do not initialize a new feature or lower another route.

## Verification commands and evidence

Use the four exact commands in [the approved plan](plan.md#project-practices-and-verification-proposal)
from its stated project root. Expected: focused tests, scoped lint and new-module
typing pass; disclose any existing formatting/full-sensor failures rather than
reformatting unrelated edits. Construction assertions map to the FR identifiers
on each task.

### Results recorded before configured implement sensors

- Baseline existing suites: 149 passed, 1 failed, 2 skipped. The failure was a
  Windows access-denied error during temporary `state.md` replacement; no cause
  or general filesystem fix was established.
- Pre-implementation regression: failed collection because the assurance
  module did not yet exist.
- Final approved six-suite command: **185 passed, 2 skipped**, exit 0.
  Skips are optional missing `specify_cli.workflows.steps.prompt`.
- Scoped Ruff lint: exit 0. Assurance-module mypy: exit 0.
- Scoped format check: exit 1; six already-existing mixed-edit files would be
  reformatted. New module/test files pass formatting. No broad formatting or
  cleanup of unrelated existing edits was performed.
- Pylance syntax checks: all nine changed Python files report no syntax errors.
  Initial requests lacked an explicit workspace root; corrected requests passed.
- AST-only Graphify update: exit 0; graph rebuilt. Unsupported-file skips and
  community-label refresh advice remain; no semantic/LLM relabeling was run.
- Tests exposed an introduced repeated-audit-read regression. The tightly
  coupled fix extends `speckit_flow/audit.py`'s existing snapshot to retain the
  latest acceptance per stage during its normal stream, rather than reopening
  the audit. The original quick and added ordinary dispatch read-count checks
  both pass. This additional source surface is a dependency of T005/T010.
- Read-only real 039 status: `not_accepted`, runtime enforcement `unverified`,
  no acceptance event. Its route/state were not changed or resumed.
- Independent plan review: initial block, one revision, follow-up pass with no
  findings. No independent implementation review or live-host certification.
- Configured implement sensors completed: **lint failed (exit 1), unit-tests
  failed (exit 1)**. The sensor runner captures subprocess output but stores
  only exit codes, so their detailed causes/test totals are unavailable here.
  Do not attribute every wider failure to the baseline or infer a broader pass
  from the focused suite. No unchanged full-suite rerun was used to chase green.
- These failures are advisory for this route's non-gated implementation stage,
  not waived or reported as passing. Checked tasks mean the actions were
  performed, not that every check passed.
- This final evidence-only task update follows the sensor run; its stored task
  fingerprint therefore predates this update. No claim of fresh passing wider
  sensors is made. Inline accounting uses the finalized task artifact.
- Remaining limitations: no authenticated caller/host identity, no live tool
  isolation proof, no independent code review, and unresolved scoped formatting
  and wider sensor failures. No acceptance or resume was performed for 039.
