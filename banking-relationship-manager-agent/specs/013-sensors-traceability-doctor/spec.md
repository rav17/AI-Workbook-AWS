# Feature Specification: Sensors, Traceability and Doctor

**Feature Branch**: `013-sensors-traceability-doctor`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Add deterministic sensors that must pass before a gate can be approved, requirement-to-task-to-test traceability checks, and a `doctor` health check, borrowing the ideas from AI-DLC."

## User Scenarios & Testing

### User Story 1 - Gates rely on scripted evidence (Priority: P1)

As a reviewer approving a gate, I want scripted checks (artifact consistency, lint, tests, traceability) to pass before approval, so that the gate rests on evidence instead of an agent's opinion.

**Independent Test**: Configure a required sensor for a stage, try to approve the gate with no result, with a failing result, and with a passing result; only the last succeeds.

**Acceptance Scenarios**:

1. **Given** a stage with a required sensor and no recorded result, **When** a human approves its gate, **Then** approval is refused and the refusal is audited.
2. **Given** a failing sensor, **When** approval is attempted, **Then** it is refused naming the sensor.
3. **Given** a passing result and unchanged artifacts, **When** approval is attempted, **Then** it succeeds and the audit notes the sensor ids relied on.
4. **Given** a passing result and artifacts changed afterwards, **When** approval is attempted, **Then** it is refused as stale.
5. **Given** no sensor configuration file, **When** gates are approved, **Then** behaviour is unchanged.

### User Story 2 - Trace requirements to tasks to tests (Priority: P2)

As a planner, I want every requirement mapped to at least one task, and optionally to a test task, so that gaps are reported before `implement`.

**Independent Test**: Run `trace` on a feature where one requirement is not cited by any task; the gap is listed and the traceability sensor fails.

**Acceptance Scenarios**:

1. **Given** a spec with requirements `FR-001..FR-00N` and a tasks file citing them, **When** `trace` runs, **Then** it prints a requirement to task to test matrix.
2. **Given** a requirement no task cites, **When** `trace` runs, **Then** it is reported as uncovered and the command exits non-zero.
3. **Given** a requirement cited only by non-test tasks and test coverage required, **Then** it is reported as lacking a test.
4. **Given** a task citing an unknown requirement id, **Then** it is reported.

### User Story 3 - One-command health check (Priority: P3)

As a maintainer, I want `doctor` to verify the repo's workflow setup in one command, so that misconfiguration is found early.

**Independent Test**: Run `doctor` on the repo (all checks ok) and on a broken profile or tampered audit chain (fails with the check named).

**Acceptance Scenarios**:

1. **Given** a healthy repo, **When** `doctor` runs, **Then** every check reports ok and the exit code is 0.
2. **Given** a corrupt profile, roster, sensor config, rules file or audit chain, **When** `doctor` runs, **Then** that check fails with a reason and the exit code is 1.
3. **Given** no feature directory, **When** `doctor` runs, **Then** feature-level checks are skipped, not failed.

### Edge Cases

- A sensor command is missing or times out: the run is recorded as `fail` with the reason.
- Sensor output may contain secrets: output is never stored in audit or result files.
- A sensor result file is edited by hand: the guard hook blocks agent edits; the result also records artifact fingerprints so stale results are detected.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST read sensor definitions from `.specify/sensors/sensors.json` with id, description, kind (`builtin` or `command`), stages, required flag, and either a builtin name and options or an argv list and timeout.
- **FR-002**: The system MUST provide builtin sensors `consistency` (stage artifacts exist, are non-empty, carry no template placeholders) and `traceability` (requirements covered by tasks, optionally by tests).
- **FR-003**: Command sensors MUST run without a shell, from the project root, with a timeout, and MUST NOT store their output.
- **FR-004**: `sensors run <stage>` MUST execute the sensors configured for that stage, store results with artifact fingerprints under the feature directory, and audit each run as `sensor_run`.
- **FR-005**: When a sensor configuration exists, `gate approve` MUST refuse unless every required sensor for the stage has a passing, non-stale result; refusals MUST be audited and approvals MUST note the sensor ids.
- **FR-006**: `sensors list` MUST show configured sensors; invalid configuration MUST fail validation with a clear message.
- **FR-007**: `trace` MUST print a requirement to task to test matrix, report uncovered requirements, tasks citing unknown requirements, and exit non-zero when requirements are uncovered.
- **FR-008**: `doctor` MUST check profiles, roster, sensor configuration, rules file, hook files, workflow file and, when a feature directory is available, state loading and audit-chain integrity, and exit non-zero if any check fails.
- **FR-009**: Without a sensor configuration file all existing behaviour MUST be unchanged.
- **FR-010**: The guard hook MUST also block agent edits to sensor result files and the sensor configuration.

### Key Entities

- **Sensor**: id, kind, stages, required, builtin name/options or argv/timeout.
- **Sensor result**: sensor id, stage, status (`pass`/`fail`), timestamp, artifact fingerprints, short reason.
- **Trace matrix**: requirement id to citing tasks and test tasks.

## Success Criteria

- **SC-001**: A gate with a required sensor can never be approved without a current passing result (covered by tests).
- **SC-002**: A coverage gap is reported in one command, naming each uncovered requirement.
- **SC-003**: `doctor` reports a healthy repo in under 2 seconds.
- **SC-004**: All existing tests keep passing.

## Assumptions

- Requirements are written as `FR-###` in `spec.md`; tasks cite them in `tasks.md`; a test task mentions `test` in its text.
- Sensor results are evidence of artifact state, not of code state; code-level sensors (lint, tests) are re-run when needed.
