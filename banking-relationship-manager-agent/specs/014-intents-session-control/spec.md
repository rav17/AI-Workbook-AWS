# Feature Specification: Intents and Session Control

**Feature Branch**: `014-intents-session-control`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Add AI-DLC-style intents (several pieces of work side by side with an active-work view, switch, park, resume) and richer session control (redo, jump back) recorded in the audit, plus a session-start hook."

## User Scenarios & Testing

### User Story 1 - See and switch between active work (Priority: P1)

As a contributor with several features in flight, I want one command listing every initialized feature with its profile, stage, gate and parked status, and a command to make one active.

**Independent Test**: Create two initialized features, list them, switch to the other, and confirm the active pointer changed.

**Acceptance Scenarios**:

1. **Given** two initialized feature directories, **When** `intents list` runs, **Then** both appear with profile, current stage, pending gate, parked flag, and the active one is marked.
2. **Given** a feature name, **When** `intents switch <name>` runs, **Then** the active-feature pointer changes and an audit event is recorded in that feature.
3. **Given** an unknown or uninitialized name, **Then** switching fails with a clear error and the pointer is unchanged.

### User Story 2 - Park and resume work (Priority: P2)

As a contributor, I want to park a feature with a reason and resume it later, so that paused work is not advanced by accident.

**Acceptance Scenarios**:

1. **Given** an active feature, **When** it is parked, **Then** an audit event records the reason and `stage start` is refused until it is resumed.
2. **Given** a parked feature, **When** it is resumed, **Then** an audit event is recorded and stages can start again.
3. **Given** the audit trail, **Then** parked status is derived from the latest park or resume event, with no extra state file.

### User Story 3 - Redo a stage (Priority: P3)

As a human reviewer, I want to send a feature back to an earlier stage with a reason, so that rework is explicit and audited.

**Acceptance Scenarios**:

1. **Given** a completed stage, **When** a human redoes it with a reason, **Then** that stage and every later stage return to pending, any pending gate is cleared, and `stage_redone` is audited.
2. **Given** a stage not yet reached, **When** redo or jump is requested, **Then** it is refused (forward movement stays under the normal stage and gate rules).
3. **Given** an agent actor, **Then** redo is refused.

### User Story 4 - Session start context (Priority: P3)

As a contributor starting a Copilot session, I want the active feature, stage, lead agent and parked status shown at session start.

**Acceptance Scenarios**:

1. **Given** an active initialized feature, **When** the session-start hook runs, **Then** it prints a one-line summary and exits 0.
2. **Given** no active feature or any error, **Then** it prints nothing harmful and exits 0.

### Edge Cases

- Feature directories without `state.json` are ignored by `intents list`.
- Redo while a stage is in progress resets it too.
- Redo does not delete artifacts or earlier audit events; the trail is append-only.

## Requirements

### Functional Requirements

- **FR-001**: `intents list` MUST list every `specs/*/state.json` feature with profile, current stage, pending gate, parked flag and active marker.
- **FR-002**: `intents switch <name>` MUST set the active-feature pointer to an initialized feature and audit `intent_switched` there.
- **FR-003**: `intents park [--reason]` MUST audit `intent_parked`; `intents unpark` MUST audit `intent_resumed`.
- **FR-004**: Parked status MUST be derived from the most recent park or resume audit event.
- **FR-005**: `stage start` MUST be refused for a parked feature, with the refusal audited.
- **FR-006**: `redo <stage> --reason` MUST require a human actor, reset the stage and all later route stages to pending, clear any pending gate and audit `stage_redone`; it MUST refuse stages not yet reached.
- **FR-007**: `jump <stage> --reason` MUST behave as `redo` for earlier stages and refuse forward targets.
- **FR-008**: A `sessionStart` hook script MUST print an active-feature summary and always exit 0.
- **FR-009**: `doctor` MUST report parked features as a note, not a failure.

### Key Entities

- **Intent**: a feature directory with state, plus derived parked flag and active marker.
- **Session event**: `intent_switched`, `intent_parked`, `intent_resumed`, `stage_redone`.

## Success Criteria

- **SC-001**: Active work across features is visible in one command.
- **SC-002**: A parked feature cannot start a stage until resumed.
- **SC-003**: Every redo, park, resume and switch is in the audit trail.
- **SC-004**: All existing tests keep passing.

## Assumptions

- The `sessionStart` hook output handling is best-effort; the hook never blocks.
- Forward skipping of stages is intentionally unsupported to keep gates meaningful.
