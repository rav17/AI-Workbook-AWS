# Feature Specification: Workflow Profiles and Audit Trail

**Feature Branch**: `009-workflow-profiles-audit`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Phase 1 of incorporating AI-DLC (awslabs/aidlc-workflows) concepts into our Spec Kit workflow: workflow profiles that tune the stage route and depth per kind of work, plus a persistent per-feature state file and an append-only audit trail."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose a workflow profile per kind of work (Priority: P1)

A developer starting work picks a profile (for example `bugfix`, `refactor`, `infra`, `security-patch`, `express`, `feature`, `enterprise`) or lets the workflow suggest one from their description. The profile determines which Spec Kit stages run, how deep the artifacts are, and which approval gates are required, so a small bug fix is not forced through the same ceremony as a regulated feature.

**Why this priority**: Today every change runs the identical specify → plan → tasks → implement path. Right-sizing ceremony is the largest single value and the foundation for later phases.

**Independent Test**: Start a workflow with the `bugfix` profile and then with `enterprise`; confirm the bugfix run skips the stages its profile omits and the enterprise run includes every stage and gate.

**Acceptance Scenarios**:

1. **Given** a request describing a known defect, **When** the developer does not name a profile, **Then** the workflow proposes `bugfix` with its stage list and asks for confirmation before starting.
2. **Given** the developer names `enterprise`, **When** the workflow starts, **Then** all stages run at comprehensive depth with a gate after every stage.
3. **Given** the developer names an unknown profile, **When** the workflow starts, **Then** it lists the valid profiles and does not start.
4. **Given** no profile is named or proposed, **When** the workflow starts, **Then** `feature` (today's behaviour) is used, so existing usage is unchanged.

---

### User Story 2 - Persistent feature state (Priority: P2)

Each feature keeps a state file recording its profile, current stage, completed stages and pending gates, so work can be resumed or handed off by someone else without re-reading everything.

**Why this priority**: Resumability and handoff are core weaknesses of ad-hoc AI coding; state is required before the audit trail is useful.

**Independent Test**: Run part of a workflow, stop, then resume in a new session; the workflow continues from the recorded stage.

**Acceptance Scenarios**:

1. **Given** a feature whose plan stage is complete, **When** a new session resumes it, **Then** the workflow reports the profile and next stage from the state file.
2. **Given** a stage is skipped by the profile, **When** state is viewed, **Then** it shows the stage as skipped with the reason.

---

### User Story 3 - Append-only audit trail (Priority: P2)

Every stage start/finish, gate decision, profile selection and override is appended as a timestamped event to the feature's audit trail, giving reviewers a complete record of what was decided, by whom, and why.

**Why this priority**: Auditability is vital for a banking project and is the basis for later review-evidence and learned-rules phases.

**Independent Test**: Run a workflow with one approve and one reject gate; the audit trail lists each event in order with timestamp, stage, actor and decision.

**Acceptance Scenarios**:

1. **Given** a gate is approved, **When** the workflow advances, **Then** an event with decision, actor and timestamp is appended.
2. **Given** an existing audit trail, **When** new events occur, **Then** earlier entries are never modified or removed.

---

### Edge Cases

- The developer changes profile mid-run: the change is allowed only at a stage boundary, requires confirmation, and is audited; completed stages are kept.
- State file is missing or corrupt on resume: the workflow reports it and offers to rebuild state from existing spec artifacts instead of failing silently.
- A profile omits a stage that a later stage depends on: the profile definition is rejected as invalid.
- Audit trail write fails: the stage does not advance silently; the failure is surfaced to the developer.
- Concurrent features: each feature has its own state and audit trail with no cross-contamination.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workflow MUST provide at least these profiles: `express`, `feature`, `enterprise`, `bugfix`, `refactor`, `infra`, `security-patch`, `poc`.
- **FR-002**: Each profile MUST declare its stage route, artifact depth (minimal, standard, comprehensive) and required approval gates.
- **FR-003**: The workflow MUST accept an explicit profile choice and otherwise propose one from the request description, requiring confirmation before starting.
- **FR-004**: The default profile MUST reproduce the current specify → plan → tasks → implement behaviour with its existing gates.
- **FR-005**: Profiles MUST be defined as editable configuration so teams can add or adjust profiles without changing workflow logic, and invalid definitions MUST be rejected with a clear message.
- **FR-006**: Each feature MUST have a state record containing profile, current stage, completed and skipped stages (with reasons) and pending gates.
- **FR-007**: The workflow MUST resume from the state record when a feature is continued.
- **FR-008**: The workflow MUST append an audit event for profile selection or change, stage start, stage completion, stage skip, gate decision and failure.
- **FR-009**: Each audit event MUST include timestamp, event type, stage, actor (human or agent) and relevant decision or reason.
- **FR-010**: The audit trail MUST be append-only; existing events MUST never be altered by the workflow.
- **FR-011**: Profile changes mid-run MUST occur only at stage boundaries with confirmation.
- **FR-012**: Audit and state files MUST be human-readable and stored with the feature's spec artifacts so they are version-controlled.
- **FR-013**: Audit events MUST NOT record secrets or customer data.

### Key Entities

- **Workflow Profile**: Named definition of stages, depth and gates for a kind of work.
- **Feature State**: Per-feature record of profile, progress and pending gates.
- **Audit Event**: Timestamped, immutable record of one workflow occurrence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can start a bugfix workflow that runs fewer stages than the full route and complete setup in under 1 minute.
- **SC-002**: 100% of existing default-profile runs behave identically to today.
- **SC-003**: A new person can determine a feature's current stage and next step from its state record in under 2 minutes without reading other artifacts.
- **SC-004**: 100% of gate decisions and stage transitions in a run appear in the audit trail, in order.
- **SC-005**: A new profile can be added by a team member in under 10 minutes without code changes.

## Assumptions

- Phase 1 covers profiles, state and audit only; reviewer agents, composer, learned rules, knowledge and extra lifecycle stages (ideation, deploy, operate) are later phases.
- Profiles reuse the existing Spec Kit stages and gates; no new stages are added in this phase.
- The existing Spec Kit workflow engine and skills are the integration point, and profile and audit data live in the feature's spec directory and `.specify/`.
- Profile proposal from a description is advisory; the human always confirms.
- Actors are identified by a simple label (for example the git user or "agent"), not an authentication system.
