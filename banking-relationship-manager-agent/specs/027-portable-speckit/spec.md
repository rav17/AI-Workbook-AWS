# Feature Specification: Portable Spec Kit Setup

**Feature Branch**: `027-portable-speckit`

**Created**: 2026-11-05

**Status**: Implemented

**Input**: User description: "setup speckit such that I can use it for another project as well not only for banking focused project"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reuse the workflow in another project (Priority: P1)

A developer working in a different repository wants to use the same Spec Kit lifecycle, skills, profiles, gates and validation without inheriting banking application assumptions.

**Why this priority**: Portability is the primary outcome requested; it must work without changing or disrupting the current banking project.

**Independent Test**: Set up a clean non-banking sample repository and run the documented setup and diagnostics; it can initialize a feature using neutral defaults without banking-specific requirements or agent prompts.

**Acceptance Scenarios**:

1. **Given** a supported project with the required Spec Kit/Copilot prerequisites, **When** the user applies the reusable setup, **Then** the workflow files and shared lifecycle behavior are available in that project.
2. **Given** the receiving project has no banking domain configuration, **When** it runs workflow diagnostics and initializes a feature, **Then** it succeeds using general-purpose defaults.

### User Story 2 - Preserve project-specific configuration (Priority: P2)

A developer wants to add their project's own constitution, agents, profiles, sensors and knowledge while keeping the shared workflow updates separate from those customizations.

**Why this priority**: The setup is only reusable if different projects can specialize safely and upgrades do not overwrite local policy.

**Independent Test**: Add a project-specific profile and rules to a sample setup, apply an update, and verify those customizations remain intact and are validated.

**Acceptance Scenarios**:

1. **Given** project-specific workflow configuration exists, **When** shared workflow content is updated, **Then** custom files remain preserved and conflicts are reported rather than silently overwritten.
2. **Given** the project declares its own governance principles, **When** an agent runs a lifecycle stage, **Then** it uses that project's constitution and does not assume the banking constitution applies.

### User Story 3 - Choose optional domain packs (Priority: P3)

A developer wants to opt into domain-specific stages, agents or sensors only when they fit the target project.

**Why this priority**: Optional domain packs make the generic workflow useful across domains without imposing irrelevant ceremony.

**Independent Test**: Compare diagnostics and available profiles with an optional domain pack disabled and enabled; the default setup remains domain-neutral and enabling the pack adds only its documented capabilities.

**Acceptance Scenarios**:

1. **Given** an optional domain pack is disabled, **When** the workflow is initialized, **Then** its domain-specific profiles, agents and gates are not imposed on the project.
2. **Given** a project explicitly enables a domain pack, **When** diagnostics run, **Then** pack prerequisites and dispatch configuration are validated.

### Edge Cases

- The destination repository already contains Spec Kit files with local modifications.
- The destination repository has no constitution or has a constitution for a different domain.
- A project update introduces a conflict with an existing custom profile, agent, sensor or rule.
- The destination project uses a different language, test runner or deployment model.
- A domain pack is enabled but its extra agents are not dispatchable by the conductor.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The setup MUST identify and separate workflow-engine assets from banking-application code, policy and domain content.
- **FR-002**: A developer MUST be able to apply the reusable workflow to a separate repository using a documented, repeatable setup process that is independent of this repository's banking application.
- **FR-003**: The default setup MUST be domain-neutral and MUST NOT require banking-specific terminology, regulations, services, tests or AWS resources.
- **FR-004**: A project MUST be able to author its own constitution and workflow configuration without inheriting another project's governance requirements.
- **FR-005**: The setup MUST preserve existing project files and local customizations, and MUST report conflicting files rather than silently replacing them.
- **FR-006**: Project-specific profiles, stages, agents, rules, sensors and knowledge MUST be configurable through the existing extension mechanisms where supported.
- **FR-007**: Optional domain packs MUST be opt-in, documented, and validated for missing prerequisites such as conductor dispatch entries.
- **FR-008**: The reusable setup MUST include a documented update path that distinguishes shared workflow updates from project-owned configuration.
- **FR-009**: A new project's language-specific checks and verify command MUST be proposed and approved by a human before they are used as construction checkpoints.
- **FR-010**: Automated tests MUST verify installation or setup in an isolated non-banking sample project and verify that the existing banking project behavior remains unchanged.
- **FR-011**: Every adopted AI-DLC-inspired capability MUST be delivered as reusable workflow behavior, project-configurable data, or an explicitly opt-in domain pack; it MUST NOT depend on banking application code or assumptions.

### Key Entities *(include if data involved)*

- **Workflow Core**: Shared lifecycle skills, engine, schemas, templates and neutral defaults.
- **Project Configuration**: The receiving project's constitution, profiles, stages, sensors, rules, agents and verification settings.
- **Domain Pack**: Optional bundle of domain-specific workflow additions, enabled explicitly per project.
- **Setup Manifest**: The record that identifies shared files, project-owned files and the supported update method.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A clean sample repository outside the banking domain can be configured and pass workflow diagnostics in 10 minutes or less using the documented process.
- **SC-002**: The sample repository can initialize a feature and complete its neutral workflow without adding banking-specific files or requirements.
- **SC-003**: Reapplying or updating the shared setup preserves all project-owned customizations in 100% of tested conflict scenarios, or reports the conflict before modifying the file.
- **SC-004**: Tests demonstrate that disabling optional domain packs leaves the neutral workflow usable and that enabling a pack exposes only its documented additions.
- **SC-005**: The existing banking project passes its current workflow validation and focused tests after the portability setup is introduced.

## Assumptions

- The first supported consumer is another Git-based project using GitHub Copilot and this repository's current Spec Kit workflow; other harnesses are out of scope unless separately requested.
- The user wants to reuse the workflow toolkit and its lifecycle, not copy the banking application itself.
- A receiving project supplies its own constitution and project-specific check command; no generic command will be run or approved automatically.
- Shared workflow updates must not overwrite user-owned project files without explicit approval.
