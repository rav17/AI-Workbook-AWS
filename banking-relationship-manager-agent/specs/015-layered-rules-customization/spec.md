# Feature Specification: Layered Rules and Customization Overlay

**Feature Branch**: `015-layered-rules-customization`

**Created**: 2026-11-05

**Status**: Implemented

**Input**: Borrow AI-DLC's layered rules and "customize without editing core" ideas: rules at org, team and project level, and a project overlay for profiles and sensors.

## User Scenarios & Testing

### User Story 1 - Layered rules (Priority: P1)

As a team lead, I want org, team and project rules merged so that shared standards apply everywhere and a project can narrow them.

**Acceptance Scenarios**:

1. **Given** active rules in `org.json` and `rules.json`, **When** `rules list --effective` runs, **Then** both appear labelled with their layer.
2. **Given** a team rule and a project rule with the same wording but opposite polarity, **Then** the project rule wins and the team rule is reported as overridden.
3. **Given** a pending or discarded rule, **Then** it is never effective.

### User Story 2 - Customization overlay (Priority: P2)

As a team, I want to add or override profiles and sensors from `.specify/custom/` without editing shipped files.

**Acceptance Scenarios**:

1. **Given** `.specify/custom/profiles/<id>.json`, **Then** the profile is available and `custom list` shows add or override.
2. **Given** an invalid overlay file, **Then** loading fails with a clear error (never silently skipped).
3. **Given** an overlay sensor reusing the id of a required core sensor, **Then** loading is refused.

## Requirements

- **FR-001**: Rules MUST merge from org, team and project layers, narrower layer winning on opposite-polarity duplicates.
- **FR-002**: Only active rules MUST be effective; approval stays human-only.
- **FR-003**: Overlay profiles and sensors MUST merge over core by id and validate with the core validators.
- **FR-004**: Overlay MUST NOT replace a required core sensor.
- **FR-005**: `doctor` MUST validate the overlay and effective rules.
- **FR-006**: The guard hook MUST protect `.specify/custom/`, `org.json` and `team.json` from agent edits.

## Out of Scope

Custom roster agents and custom stages (stages are code-defined); phase-level rules reuse the existing stage-origin matching.
