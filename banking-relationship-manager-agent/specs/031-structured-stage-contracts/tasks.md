# Tasks: Structured Stage Contracts

**Input**: Design documents from `/specs/031-structured-stage-contracts/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because the specification requires deterministic validation, gate behavior and portable fixture acceptance.

## Phase 1: Setup

**Purpose**: Lock down backward-compatible profile behavior before contract support.

- [x] T001 [P] Add profile parsing regression tests for absent and explicit `stage_contracts` values in `tests/unit/speckit_flow/test_flow_profiles.py`.

## Phase 2: Foundational

**Purpose**: Introduce the opt-in profile flag without changing existing profile behavior.

- [x] T002 Implement the `Profile.stage_contracts` boolean with a default of `false` and explicit invalid-value errors in `speckit_flow/models.py`.

**Checkpoint**: Existing profiles still load with contract support disabled.

## Phase 3: User Story 1 - Work from a clear stage agreement (Priority: P1) 🎯 MVP

**Goal**: Load, validate and display the structured contract applicable to a stage.

**Independent Test**: Load contracts for an opted-in profile, display a stage contract, and verify missing, duplicate or invalid declarations are reported explicitly.

### Tests for User Story 1

- [x] T003 [P] [US1] Test contract parsing, duplicate/unknown stages, project overrides and malformed data in `tests/unit/speckit_flow/test_flow_contracts.py`.
- [x] T004 [P] [US1] Test contract list/show CLI output and configuration errors in `tests/unit/speckit_flow/test_flow_cli_contracts.py`.

### Implementation for User Story 1

- [x] T005 [US1] Implement contract loading, validation, project overrides and active-profile completeness checks in `speckit_flow/contracts.py`.
- [x] T006 [US1] Validate all routed stage contracts during initialization when `stage_contracts` is enabled in `speckit_flow/state.py`.
- [x] T007 [US1] Add a read-only `contracts` list/show command with JSON and human-readable output in `speckit_flow/cli.py`.
- [x] T008 [P] [US1] Document contract authoring and inspection in `.github/skills/speckit-contracts/SKILL.md`.

**Checkpoint**: Opted-in users and stage leads can inspect validated contracts; disabled profiles remain unchanged.

## Phase 4: User Story 2 - Review required outputs at human gates (Priority: P1)

**Goal**: Enforce current, path-bound required output evidence only at human gates.

**Independent Test**: Missing, empty, inaccessible, escaping or stale required outputs fail the contract sensor and block gate approval; non-gated completion remains available.

### Tests for User Story 2

- [x] T009 [P] [US2] Test missing/empty outputs, path traversal, symlinks, size limits and fingerprint freshness for the contract sensor in `tests/unit/speckit_flow/test_flow_sensors.py`.
- [x] T010 [P] [US2] Test required sensor gate blocking, stale result rejection and human-only decisions in `tests/unit/speckit_flow/test_flow_state.py`.

### Implementation for User Story 2

- [x] T011 [US2] Add the `stage-contract` builtin sensor, safe output checks and contract/output fingerprints with explicit bounded filesystem errors in `speckit_flow/sensors.py`.

**Checkpoint**: Required outputs block only human gate approval; non-gated stages remain advisory.

## Phase 5: User Story 3 - Adopt contracts without changing defaults (Priority: P2)

**Goal**: Package the feature for portable, project-owned adoption.

**Independent Test**: A non-banking fixture enables the pack, inspects contracts, checks gated output evidence, customizes a stage contract, and confirms disabled behavior is unchanged.

### Tests for User Story 3

- [x] T012 [P] [US3] Add installed non-banking project acceptance coverage for disabled defaults, contract inspection, customization and a gated output check in `tests/unit/test_speckit_bootstrap.py`.

### Implementation for User Story 3

- [x] T013 [US3] Add the disabled plugin manifest, `contract-driven` profile, scoped sensor and contracts for each routed stage in `.specify/plugins/stage-contracts/`.
- [x] T014 [US3] Add the reusable plugin and skill paths to `scripts/speckit-portable-bundle.json`.
- [x] T015 [P] [US3] Document opt-in activation, the human-gates-only policy and limits in `docs/speckit-profiles.md` and `docs/speckit-portability.md`.

**Checkpoint**: An unrelated project can opt in without importing domain policy or changing existing default routes.

## Phase 6: Polish and Validation

**Purpose**: Verify implementation quality, portability and generated workflow metadata.

- [x] T016 Run the human-approved focused pytest command, Ruff, mypy, doctor and plugin validation; record results in `specs/031-structured-stage-contracts/quickstart.md`.
- [x] T017 Refresh the repository graph with `graphify update .` and inspect the final feature diff without staging unrelated work.

## Dependencies and parallel opportunities

- T001 -> T002.
- T002 -> T003, T004, T005, T006, T007, T008.
- T005 -> T006, T007, T008, T009, T011.
- T009 -> T011; T010 validates the existing gate behavior with the new sensor.
- T011 -> T012 -> T013 -> T014, T015.
- T005 + T007 + T013 -> T014 -> T016 -> T017.
- All implementation tasks -> T016 -> T017.
- T003 and T004 can run in parallel; T008 can run in parallel with CLI and sensor implementation; T015 can run in parallel with portable bundle work.

## Implementation Strategy

1. Deliver the MVP contract loader and inspection command (US1) with backward-compatible profile defaults.
2. Add deterministic file checks and stale-evidence gate enforcement (US2).
3. Package an opt-in profile, default contracts and non-banking acceptance coverage (US3).
4. Run only the verification command approved by the human; do not approve gates or verification on the user's behalf.
