# Tasks: Portable Spec Kit Setup

**Input**: Design documents from `/specs/027-portable-speckit/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/bootstrap-cli.md`

## Phase 1: Setup

**Purpose**: Establish the portable bundle and isolated test structure.

- [X] T001 Create portable configuration seed directory and README in `.specify/templates/portable/README.md`
- [X] T002 [P] Create bootstrap CLI test module in `tests/unit/test_speckit_bootstrap.py`

## Phase 2: Foundational

**Purpose**: Define a constrained, auditable source bundle before any user story installation behavior.

- [X] T003 Add the allow-listed portable file manifest in `scripts/speckit-portable-bundle.json`
- [X] T004 Add a neutral base sensor configuration with only repository-independent built-ins in `.specify/templates/portable/sensors.json`
- [X] T005 Add neutral integration defaults in `.specify/templates/portable/integration.json` and generate a target-local active feature pointer in `scripts/speckit_bootstrap.py`
- [X] T006 Add path containment, manifest validation, and SHA-256 helpers in `scripts/speckit_bootstrap.py`

**Checkpoint**: Bundle files are explicit, target-independent and testable without touching the source repository.

## Phase 3: User Story 1 - Reuse the workflow in another project (Priority: P1)

**Goal**: Install the reusable lifecycle into a clean non-banking Copilot project without importing banking-specific assets.

**Independent Test**: Install into a temporary non-banking repository, run `python -m speckit_flow doctor`, list profiles, and verify the target has no Aria code, banking constitution/knowledge, or source-repository test commands.

### Tests for User Story 1

- [X] T007 [US1] Test dry-run and successful install into a temporary target in `tests/unit/test_speckit_bootstrap.py`
- [X] T008 [US1] Test installed-file allowlist excludes banking application, constitution, knowledge, and project-specific command sensors in `tests/unit/test_speckit_bootstrap.py`
- [X] T009 [US1] Test the installed target's `speckit_flow doctor` and profile validation in `tests/unit/test_speckit_bootstrap.py`

### Implementation for User Story 1

- [X] T010 [US1] Implement `install --target --dry-run` using the bundle manifest in `scripts/speckit_bootstrap.py`
- [X] T011 [US1] Include generic profiles, stages, roster and templates in `scripts/speckit-portable-bundle.json`
- [X] T012 [US1] Configure target-independent install defaults without copying `.specify/memory/constitution.md`, `.specify/knowledge/banking-compliance.md`, `pyproject.toml`, or banking tests in `scripts/speckit-portable-bundle.json`
- [X] T013 [US1] Document prerequisites, install, target configuration and validation in `docs/speckit-portability.md`

**Checkpoint**: A clean non-banking project can install and validate the neutral workflow independently.

## Phase 4: User Story 2 - Preserve project-specific configuration (Priority: P2)

**Goal**: Safely update shared files without overwriting locally modified files or removing user-owned configuration.

**Independent Test**: Install, modify an installed file and add project-owned configuration, then run update and verify modified/owned files remain byte-identical while safe shared updates are applied or reported.

### Tests for User Story 2

- [X] T014 [US2] Test identical-file skip, conflict reporting and no-write-on-conflict behavior in `tests/unit/test_speckit_bootstrap.py`
- [X] T015 [US2] Test update ownership hashes and preservation of user-created `.specify/custom/` files in `tests/unit/test_speckit_bootstrap.py`

### Implementation for User Story 2

- [X] T016 [US2] Record installed file hashes and bundle version in `.specify/speckit-portable-manifest.json`
- [X] T017 [US2] Implement conservative `update --target --dry-run` behavior and conflict exit status in `scripts/speckit_bootstrap.py`
- [X] T018 [US2] Document update, conflict resolution and ownership boundaries in `docs/speckit-portability.md`

**Checkpoint**: Local configuration survives updates, and every conflict is visible before a write.

## Phase 5: User Story 3 - Choose optional domain packs (Priority: P3)

**Goal**: Make AI-DLC-inspired capabilities reusable while requiring explicit opt-in for domain-specific additions.

**Independent Test**: Install with optional packs disabled, then enable one in the target and verify its documented additions and dispatch requirements using `doctor`.

### Tests for User Story 3

- [X] T019 [US3] Test optional plugin packs are installed disabled and do not alter the neutral route by default in `tests/unit/test_speckit_bootstrap.py`
- [X] T020 [US3] Test enabling the generic AI-DLC extras plugin produces a valid target in `tests/unit/test_speckit_bootstrap.py`

### Implementation for User Story 3

- [X] T021 [US3] Include only documented, disabled plugin examples in the portable bundle manifest at `scripts/speckit-portable-bundle.json`
- [X] T022 [US3] Document plugin selection and post-enable validation in `docs/speckit-portability.md`

**Checkpoint**: Shared AI-DLC-inspired workflow behavior is portable, while domain-specific additions remain opt-in.

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T023 Verify the receiving project's test command is not pre-approved and document human approval in `tests/unit/test_speckit_bootstrap.py` and `docs/speckit-portability.md`
- [X] T024 Run focused bootstrap and `speckit_flow` tests; run ruff and mypy on `scripts/speckit_bootstrap.py` and update `specs/027-portable-speckit/tasks.md`
- [X] T025 Run `graphify update .` after code changes and verify no unrelated files are staged
- [X] T026 Constrain directory entries to explicit files and use neutral rules/integration seeds in `scripts/speckit-portable-bundle.json` (FR-001, FR-003, FR-011)
- [X] T027 Test bundle exclusions, update dry-runs, missing/modified files, aliases, and path collisions in `tests/unit/test_speckit_bootstrap.py` (FR-005, FR-008)
- [X] T028 Test a complete isolated non-banking CLI lifecycle with sensors, simulated fixture gates, sample code, and a verified unit checkpoint in `tests/unit/test_speckit_bootstrap.py` (FR-002, FR-009, FR-010)
- [X] T029 Document acceptance evidence and limitations in `docs/speckit-portability.md`, then commit only feature 027 files

### Acceptance results (2026-11-09)

- Targeted bootstrap and workflow tests: **284 passed, 1 skipped**.
- The skip is the existing `specify_cli.workflows.engine` integration test,
  because the module is not installed. No claim is made that this integration ran.
- Ruff and mypy passed for the bootstrap and its tests.
- Current-project `doctor` passed; optional packs remain disabled.
- `graphify update .` completed. Generated graphs and unrelated application
  changes are excluded from the feature commit.

## Dependencies & Execution Order

### Phase Dependencies

- Setup has no prerequisites.
- Foundational depends on Setup and blocks all user stories.
- User Story 1 depends on Foundational.
- User Story 2 depends on User Story 1's installed manifest.
- User Story 3 depends on User Story 1's bundle and validates optional plugin behavior.
- Polish depends on all selected stories.

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational; MVP scope.
- **US2 (P2)**: Depends on US1 installation and recorded ownership.
- **US3 (P3)**: Depends on US1 bundle; independent of US2's update implementation.

### Parallel Opportunities

- T001 and T002 can run in parallel.
- T007 and T008 are in one test module and should be added sequentially; T009 depends on install behavior.
- T014 and T015 share one test module and should be added sequentially.
- US2 and US3 implementation share the bundle manifest and documentation, so perform them sequentially.

## Implementation Strategy

Deliver US1 first as the smallest useful setup, then add safe updates in US2 and optional domain packs in US3. Run each isolated acceptance test against a temporary project so validation cannot mutate this banking repository. Do not approve a target project's verify command automatically.
