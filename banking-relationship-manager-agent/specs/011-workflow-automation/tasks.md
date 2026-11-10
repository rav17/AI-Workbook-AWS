# Tasks: Spec Kit Workflow Automation

**Input**: Design documents in `specs/011-workflow-automation/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md
**Tests**: Include focused tests per project constitution.

## Phase 1: Setup

- [x] T001 Confirm `speckit_flow` remains an optional helper and no workflow engine dependency is added in `pyproject.toml`
- [x] T002 [P] Add workflow preflight test module `tests/unit/speckit_flow/test_flow_workflow.py`

## Phase 2: Foundational

- [x] T003 Add workflow route and preflight invariants to `specs/011-workflow-automation/contracts/cli.md` and `contracts/workflow.md`
- [x] T004 Implement typed `workflow begin` route parsing, default initialization, existing state checks, and audit-chain verification in `speckit_flow/cli.py` and `speckit_flow/state.py`

## Phase 3: User Story 1 - Automatically track the standard workflow (P1) 🎯 MVP

**Goal**: Start and complete lifecycle records around the standard feature workflow without manual lifecycle commands.
**Independent test**: Run all four core stages and verify one start/completion pair per stage, in order, and no completion after a failed stage.

- [x] T005 [P] [US1] Test `workflow begin` initializes the feature profile only when state is missing in `tests/unit/speckit_flow/test_flow_workflow.py`
- [x] T006 [P] [US1] Test `workflow begin` leaves existing state unchanged and rejects a non-matching route in `tests/unit/speckit_flow/test_flow_workflow.py`
- [x] T007 [US1] Add `workflow begin --stages --gates` CLI parsing, preflight behavior and JSON/text output in `speckit_flow/cli.py`
- [x] T008 [US1] Add a workflow preflight helper that resolves the profile, verifies stages/gates and checks the audit chain in `speckit_flow/state.py`
- [x] T009 [US1] Add workflow preflight and specify start/done shell steps immediately after `speckit.specify` and before the first gate in `.specify/workflows/speckit/workflow.yml`
- [x] T010 [US1] Add `agent:workflow` stage start/done shell steps around plan, tasks and implement in `.specify/workflows/speckit/workflow.yml`
- [x] T011 [P] [US1] Test lifecycle wrappers preserve specify → plan → tasks → implement order and only complete after successful commands in `tests/unit/speckit_flow/test_flow_workflow.py`

## Phase 4: User Story 2 - Review gated work using recorded evidence (P2)

**Goal**: Persist gate approval/rejection and stop dispatch after rejection.
**Independent test**: Approve each existing gate and verify audit records; reject a gate and verify later workflow commands are not dispatched.

- [x] T012 [P] [US2] Test approve/reject gate branches and rejection-stop behavior from `.specify/workflows/speckit/workflow.yml` in `tests/unit/speckit_flow/test_flow_workflow.py`
- [x] T013 [US2] Configure both workflow gates with `on_reject: skip` and conditional lifecycle approve/reject branches in `.specify/workflows/speckit/workflow.yml`
- [x] T014 [US2] Ensure the rejection branch records `gate_rejected` then exits non-zero before later stages in `.specify/workflows/speckit/workflow.yml`
- [x] T015 [US2] Update both gate messages to instruct comprehensive-profile users to save a current review using `.github/skills/speckit-review/SKILL.md` before approval

## Phase 5: User Story 3 - Resume and verify lifecycle progress (P3)

**Goal**: Resume safely from persisted state and stop on audit or state errors.
**Independent test**: Resume a valid engine run from its interruption point; verify corrupt audit, missing state, and route mismatch each stop with actionable errors and no state rewrite.

- [x] T016 [P] [US3] Test broken audit chain, missing state, malformed state, and route mismatch leave persisted files untouched in `tests/unit/speckit_flow/test_flow_workflow.py`
- [x] T017 [US3] Verify `status` and `resume` validate the audit chain before reporting successful progress in `speckit_flow/cli.py`
- [x] T018 [US3] Document recovery, engine resume, profile mismatch and blocked-review handling in `docs/speckit-profiles.md`
- [x] T019 [P] [US3] Add runnable preflight, approval, rejection and resume scenarios to `specs/011-workflow-automation/quickstart.md`

## Phase 6: Polish

- [x] T020 Validate the YAML with `WorkflowDefinition` and `validate_workflow`, and retain a focused workflow regression in `tests/unit/speckit_flow/test_flow_workflow.py`
- [x] T021 Run `ruff check`, `mypy speckit_flow`, `pytest tests/unit/speckit_flow`, and `pytest tests/unit`; fix regressions
- [x] T022 Run the scenarios in `specs/011-workflow-automation/quickstart.md` in an isolated scratch feature directory
- [x] T023 Run `graphify update .`

## Dependencies

Setup → Foundational → US1 (MVP) → US2 → US3 → Polish. US2 requires the workflow preflight and stage transitions from US1; US3 tests the same state and audit boundaries.

## Parallel examples

- Setup: T001 and T002 may proceed independently.
- US1: T005 and T006 tests can be written before T007/T008; T009/T010 workflow integration follows the preflight implementation.
- US2: T012 can be written before T013/T014; T015 is documentation-only and independent.
- US3: T016 and T019 can proceed independently.

## Implementation Strategy

Deliver US1 first as the MVP: deterministic preflight and stage tracking around the standard workflow. Add audited human gate decisions next (US2), then verify recovery and document resumption (US3). Keep the existing standard workflow sequence and gate positions throughout.
