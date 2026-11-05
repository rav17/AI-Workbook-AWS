# Tasks: Compliance Plugin Pack

**Input**: Design documents from `/specs/025-compliance-plugin-pack/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/plugin-pack.md

**Tests**: Included. The constitution requires focused unit tests for every change.

## Phase 1: Setup

- [x] T001 Create the pack folder `.specify/plugins/compliance/` with `plugin.json` (name `compliance`, version `1.0.0`, `enabled: false`) per data-model.md (FR-001, FR-006)

## Phase 2: Foundational (blocks US2)

- [x] T002 Add the optional `profiles` scope to sensors in `speckit_flow/sensors.py`: parse a non-empty list of strings, apply it in `run_stage` and `gate_problems` using the feature's state profile (FR-004)
- [x] T003 Add the `section` built-in sensor to `speckit_flow/sensors.py` per contracts/plugin-pack.md: required `heading`, optional `artifact`, fails when the heading is missing or its body is empty (FR-003)
- [x] T004 [P] Unit tests for T002 and T003 in `tests/unit/speckit_flow/test_flow_section_sensor.py`: scoped sensor skipped for other profiles, section pass, missing heading, empty body, invalid options (FR-003, FR-004)

## Phase 3: User Story 1 - Enable the pack and get a compliance profile (P1)

**Goal**: A `compliance` profile appears only when the pack is enabled.

**Independent Test**: Enable the pack in a temp project, list profiles, initialize a feature; disable and confirm it is gone.

- [x] T005 [US1] Create `.specify/plugins/compliance/profiles/compliance.json` per data-model.md: stages specify, clarify, plan, tasks, analyze, implement; gates specify and plan; strict guard policy (FR-002)
- [x] T006 [US1] Tests in `tests/unit/speckit_flow/test_flow_compliance_pack.py`: profile absent when disabled, present when enabled, core profiles unchanged, `plugins validate` passes (FR-002, FR-006, FR-007)

## Phase 4: User Story 2 - A compliance check blocks gate approval (P2)

**Goal**: Plan gate approval is refused without a Compliance section, for the compliance profile only.

**Independent Test**: Initialize a compliance feature, run the sensor on a plan without the section, attempt approval, then add the section and approve.

- [x] T007 [US2] Create `.specify/plugins/compliance/sensors.json` with sensor `compliance-section` (builtin `section`, heading `Compliance`, stages specify and plan, required, profiles `["compliance"]`) (FR-003, FR-004)
- [x] T008 [US2] Tests in `tests/unit/speckit_flow/test_flow_compliance_pack.py`: approval refused without the section, accepted with it, sensor not applied to the `feature` profile, plugin cannot reuse a core sensor id (FR-003, FR-004)

## Phase 5: User Story 3 - A compliance agent supports specify and plan (P3)

**Goal**: A read-only `compliance-reviewer` agent appears with source `plugin:compliance`.

**Independent Test**: List agents with the pack enabled; run doctor.

- [x] T009 [US3] Create `.specify/plugins/compliance/agents.json` (domain, judgment, supports specify and plan, `can_edit` false) (FR-005)
- [x] T010 [US3] Create `.github/agents/speckit-compliance-reviewer.agent.md`: read-only tools, `user-invocable: false`, name `speckit-compliance-reviewer` (FR-005)
- [x] T011 [US3] Tests in `tests/unit/speckit_flow/test_flow_compliance_pack.py`: agent loaded with source `plugin:compliance` when enabled, absent when disabled, roster validation passes both ways, doctor has no failures (FR-005, FR-006, FR-007)

## Phase 6: Polish

- [x] T012 [P] Write `.specify/plugins/compliance/README.md`: how to enable, what it adds, how to adapt, and that enabling means adding the agent to the conductor's `agents` list (FR-008)
- [x] T013 [P] Add a "Compliance pack" section and document `profiles` and `section` sensors in `docs/speckit-profiles.md` (FR-008)
- [x] T014 Run ruff, mypy and the full unit suite; run `graphify update .`; confirm the quickstart steps in `specs/025-compliance-plugin-pack/quickstart.md` (FR-007)
- [x] T015 Test that the pack is self-contained and core config does not mention it, in `tests/unit/speckit_flow/test_flow_compliance_pack.py` (FR-001)
- [x] T016 Test that the pack README documents enabling and adapting, in `tests/unit/speckit_flow/test_flow_compliance_pack.py` (FR-008)

## Dependencies

- T001 first. T002 and T003 before T007. T005 needs T001. T009 needs T001; T010 before T011.
- US1 and US3 are independent of the engine changes; US2 needs T002 and T003.
- Order: T001 â†’ T002, T003 â†’ T004; then US1, US2, US3; then Polish.

## Parallel Opportunities

- T004 with T005 (different files). T012 and T013 together.

## Implementation Strategy

MVP is US1 (profile only). Add US2 after the engine changes for real enforcement, then US3.
