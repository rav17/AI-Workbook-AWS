# Feature Specification: Compliance Plugin Pack (worked example)

**Feature Branch**: `025-compliance-plugin-pack`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Ship an example plugin pack that adds a compliance review agent, a compliance sensor and a compliance profile, so teams can see how plugins and extra agents are used without editing core."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enable the pack and get a compliance profile (Priority: P1)

A team lead enables the compliance pack by switching it on in its manifest. A new `compliance` workflow profile then appears next to the core profiles, and a feature can be started with it.

**Why this priority**: The profile is the visible entry point. Without it the pack adds nothing a team can use.

**Independent Test**: Enable the pack, list profiles, and initialize a feature with `compliance`. Disable the pack and confirm the profile is gone.

**Acceptance Scenarios**:

1. **Given** the pack is enabled, **When** profiles are listed, **Then** `compliance` appears and a feature can be initialized with it.
2. **Given** the pack is disabled, **When** profiles are listed, **Then** `compliance` is absent and core profiles are unchanged.

---

### User Story 2 - A compliance check blocks gate approval (Priority: P2)

A compliance sensor runs at the specify and plan stages. If the stage artifact has no compliance section, the gate cannot be approved until it is added.

**Why this priority**: It proves a plugin can add enforcement, not only labels.

**Independent Test**: Start a `compliance` feature, write a plan without a compliance section, and try to approve the gate. Add the section and approve.

**Acceptance Scenarios**:

1. **Given** a plan with no compliance section, **When** a human approves the plan gate, **Then** approval is refused and the reason names the sensor.
2. **Given** the section is present, **When** the gate is approved, **Then** it succeeds.

---

### User Story 3 - A compliance agent supports the specify and plan stages (Priority: P3)

The pack adds a read-only compliance reviewer agent that supports the specify and plan stages and is listed with source `plugin:compliance`.

**Why this priority**: It shows the extra-agent route, which depends on the earlier stories being useful first.

**Independent Test**: List agents with the pack enabled and confirm the new agent, its source and its stage support. Run doctor and confirm it passes.

**Acceptance Scenarios**:

1. **Given** the pack is enabled, **When** agents are listed, **Then** the compliance reviewer appears with source `plugin:compliance`.
2. **Given** the pack is enabled, **When** doctor runs, **Then** the roster check passes.

### Edge Cases

- The pack adds a stage anchor or profile id that already exists: loading must fail with a clear message.
- The pack is enabled but its agent file is missing: doctor must report it.
- The pack tries to lower a required core sensor: it must be rejected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pack MUST live in its own folder and add no changes to core files.
- **FR-002**: When enabled, the pack MUST add a `compliance` profile.
- **FR-003**: When enabled, the pack MUST add a sensor that requires a compliance section in the specify and plan artifacts.
- **FR-004**: The sensor MUST be required for the `compliance` profile only.
- **FR-005**: When enabled, the pack MUST add one read-only compliance agent supporting specify and plan, with its own agent file.
- **FR-006**: Disabling the pack MUST remove all of the above, leaving core behaviour unchanged.
- **FR-007**: The pack MUST be validated by doctor and by the plugin validate command.
- **FR-008**: The pack MUST ship with a short guide on enabling it and adapting it.

### Key Entities

- **Plugin pack**: A named folder with a manifest and optional profiles, sensors and agents.
- **Compliance profile**: A workflow route that includes the compliance review.
- **Compliance sensor**: A check that blocks gate approval when a compliance section is missing.
- **Compliance agent**: A read-only reviewer that supports the specify and plan stages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A team can enable the pack and start a compliance feature in under 5 minutes using only the guide.
- **SC-002**: With the pack disabled, the existing test suite results are identical to before.
- **SC-003**: 100% of attempts to approve a plan without a compliance section are refused.
- **SC-004**: Doctor reports no failures with the pack enabled or disabled.

## Assumptions

- The pack ships disabled by default, so existing users see no change.
- The compliance section check looks for a heading, not for the quality of its content.
- Regulatory content (for example specific banking rules) is out of scope; the pack is a template teams adapt.
- Existing plugin loading, sensor and extra-agent features are reused unchanged.
