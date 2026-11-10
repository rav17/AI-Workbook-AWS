# Feature Specification: Structured Stage Contracts

**Feature Branch**: `031-structured-stage-contracts`

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "Structured stage contracts"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Work from a clear stage agreement (Priority: P1)

A project contributor needs to know what a workflow stage consumes, what it is
expected to produce, and how a reviewer will assess completion before work
begins.

**Why this priority**: Consistent, explicit expectations keep requirements,
decisions, implementation and review connected as projects grow.

**Independent Test**: Select a workflow with contracts enabled and inspect
several stages; each displays its purpose, expected inputs and outputs, and
acceptance criteria in a consistent structure.

**Acceptance Scenarios**:

1. **Given** a stage in the active workflow, **When** its contract is displayed,
   **Then** the stage purpose, inputs, required outputs and acceptance criteria
   are clear to its lead and reviewer.
2. **Given** a project-specific or optional stage, **When** it is included in a
   contract-enabled workflow, **Then** its project-owned contract can be used
   without changing unrelated projects or default routes.

### User Story 2 - Review required outputs at human gates (Priority: P1)

A human reviewer needs reliable evidence that a gated stage produced its
required deliverables before approving the workflow to continue.

**Why this priority**: Human approval is meaningful only when the expected
outputs are visible and present.

**Independent Test**: In a gated stage, attempt approval with a required output
missing or empty and confirm approval is blocked; provide all required outputs
and confirm the human can make the approval decision.

**Acceptance Scenarios**:

1. **Given** a gated stage with a missing or empty required output, **When** a
   human attempts approval, **Then** the gate is blocked with the specific
   missing output identified.
2. **Given** all required outputs are present and non-empty, **When** a human
   reviews the stage, **Then** the human—not an automated content judgment—
   decides whether the acceptance criteria are satisfied.
3. **Given** a non-gated stage with an incomplete contract, **When** the
   workflow is inspected, **Then** the gaps are reported as advisory and do not
   block stage completion.

### User Story 3 - Adopt contracts without changing defaults (Priority: P2)

A team wants to enable structured contracts in any project, including a project
with custom stages, without inheriting domain-specific rules or changing
existing routes.

**Why this priority**: Workflow improvements must remain portable and
incrementally adoptable.

**Independent Test**: Install the toolkit into a non-banking fixture, enable the
contract capability, customize a stage contract, and verify default behavior
remains unchanged when the capability is disabled.

**Acceptance Scenarios**:

1. **Given** contracts are disabled, **When** a project uses an existing
   profile, **Then** stage order, completion behavior and gates remain
   unchanged.
2. **Given** contracts are enabled, **When** a project supplies a valid
   contract for a custom stage, **Then** the contract is displayed and applies
   only to that project's workflow.

### Edge Cases

- A contract refers to an unknown stage or duplicates a stage contract.
- A required output path is missing, empty, outside the feature directory or
  otherwise inaccessible.
- A contract contains malformed or unsupported fields.
- A stage has optional outputs that are not produced.
- A profile includes a stage without a contract while contract enforcement is
  enabled.
- An output changes between contract inspection and gate approval.
- A human rejects a gate even though required outputs exist.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workflow MUST support a consistent, structured contract for a
  stage that describes its purpose, expected inputs, required and optional
  outputs, and acceptance criteria.
- **FR-002**: Contributors and reviewers MUST be able to inspect the contract
  applicable to a stage in the active workflow before or during that stage.
- **FR-003**: The contract capability MUST be opt-in; disabling it MUST preserve
  existing profile routes, stage-completion behavior, and gates.
- **FR-004**: A contract-enabled workflow MUST identify missing contract
  definitions for stages it activates and report the configuration problem
  explicitly.
- **FR-005**: For gated stages, approval MUST be blocked when a required output
  declared by the applicable contract is missing, empty or inaccessible.
- **FR-006**: Output checks MUST be bounded to the feature's declared outputs
  and MUST reject paths that escape the feature directory.
- **FR-007**: Contract checks MUST use the current output state at approval time
  and record an auditable result without copying artifact contents into the
  audit trail.
- **FR-008**: Presence checks MUST NOT claim that an output is substantively
  correct. Acceptance criteria and output quality remain subject to human
  review; agents MUST NOT approve human gates.
- **FR-009**: For non-gated stages, missing required outputs MUST be reported
  as advisory and MUST NOT block stage completion.
- **FR-010**: Projects MUST be able to define or override contracts for their
  own custom stages without introducing banking-specific requirements into the
  portable capability.

### Key Entities *(include if feature involves data)*

- **Stage contract**: The project-owned description of a stage's purpose,
  inputs, expected outputs, and acceptance criteria.
- **Required output**: A feature-local deliverable whose presence is checked at
  a human approval gate.
- **Contract check result**: An auditable summary of required-output checks
  performed against current artifacts, without their contents.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every stage in a contract-enabled workflow has a valid contract
  that exposes its purpose, inputs, outputs and acceptance criteria.
- **SC-002**: All tested missing, empty, inaccessible and escaping required
  output cases block human gate approval and identify the problem.
- **SC-003**: Non-gated stages complete without contract-output enforcement,
  while their missing outputs remain visible as advisory information.
- **SC-004**: Disabling the capability leaves existing profiles and their
  completion behavior unchanged.
- **SC-005**: A non-banking project can customize a stage contract without
  importing domain-specific rules or artifact contents into audit records.

## Assumptions

- Contracts are enabled explicitly and do not silently alter existing profile
  behavior.
- Required-output validation checks safe path, accessibility and non-empty
  presence only; humans assess meaning and quality.
- Optional outputs do not block stage completion or gate approval.
- Existing human approval, audit and review mechanisms remain authoritative.
- Contract definitions and guidance are part of the portable toolkit, while
  project-specific contracts remain owned by the receiving project.
