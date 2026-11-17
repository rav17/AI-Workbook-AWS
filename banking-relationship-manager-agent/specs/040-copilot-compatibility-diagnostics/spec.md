# Feature Specification: Copilot Compatibility Diagnostics

**Feature Branch**: Not created; feature 040 is separate from feature 039.
**Created**: 2026-11-17
**Status**: Draft
**Input**: Confirmed narrow quick inline correction to misleading worker-tool
compatibility diagnostics. No enforcement changes or runtime certification.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive an accurate compatibility diagnosis (Priority: P1)

As a maintainer, I want the conductor to distinguish unavailable diagnostics from
an observed host limitation so I do not repeatedly change hosts or reset work
based on an unsupported explanation.

**Why this priority**: An inaccurate diagnosis prevented continued work without
establishing whether the host actually violated the configured restrictions.

**Independent Test**: Review the instruction contract against examples of missing
invocation parameters, failed named-worker selection, observed forbidden
delegation, and unavailable runtime evidence.

**Acceptance Scenarios**:

1. **Given** a named-worker invocation interface has no per-call tool override,
   **When** compatibility is diagnosed, **Then** that absence alone is not
   reported as proof that the worker's configured restrictions are unsupported.
2. **Given** named-worker selection fails or forbidden delegation is observed,
   **When** compatibility is diagnosed, **Then** execution stops with that
   specific limitation and does not substitute a generic worker.
3. **Given** enforcement cannot be established from available evidence,
   **When** compatibility is diagnosed, **Then** the report says it is
   unverified, identifies the missing evidence, and retains the existing stop.

### User Story 2 - Understand what the correction does not prove (Priority: P2)

As a receiving developer, I want host guidance to separate configuration,
invocation and runtime enforcement so a documentation correction is not mistaken
for permission enforcement or a passed live-host test.

**Why this priority**: The portable workflow must not inherit overstated claims.

**Independent Test**: Read the conductor guidance and its linked profile guide;
confirm that both describe the same limits and retain existing safeguards.

**Acceptance Scenarios**:

1. **Given** a worker definition omits delegation tools, **When** guidance explains
   its effect, **Then** it distinguishes declared restrictions from verified
   runtime behavior.
2. **Given** a static regression test passes, **When** results are reported,
   **Then** they are not described as live enforcement evidence or permission
   to resume feature 039 automatically.

### Edge Cases

- Successful named-worker discovery alone does not establish restricted tools.
- No observed nested call does not prove that nesting was unavailable.
- A host may enforce configured restrictions without exposing a per-call override.
- A generic worker's behavior does not establish a named worker's behavior.
- Existing user edits and feature 039's route, state and artifacts remain intact.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Guidance MUST distinguish configured restrictions, observed
  capability failures and unavailable runtime evidence.
- **FR-002**: Guidance MUST NOT infer unsupported enforcement solely from a
  missing per-call tool override or absent invocation parameter.
- **FR-003**: The existing stop for unavailable or unverified required enforcement,
  failed named-worker selection and observed forbidden delegation MUST remain.
  Reports MUST identify the failed check or missing evidence without claiming an
  unsupported root cause.
- **FR-004**: Worker tool declarations, guard behavior, human gates, call budgets
  and initialized routes MUST NOT change. Generic substitution and prompt-only
  permission claims MUST remain prohibited.
- **FR-005**: Directly related host documentation and focused regression checks
  MUST cover the diagnosis distinction and existing stop conditions.
- **FR-006**: Results MUST disclose that no live host enforcement was verified
  and that this correction does not unblock feature 039 by itself.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four diagnosis scenarios in Story 1 and the edge cases are
  addressed consistently in the conductor guidance and profile guide.
- **SC-002**: Focused regression checks pass for both the new diagnosis guidance
  and the preserved no-substitution/rooted-command/restriction contract.
- **SC-003**: No enforcement configuration or feature 039 artifact is changed.
- **SC-004**: The final report makes zero claims of live runtime enforcement
  validation without actual host evidence.

## Assumptions

- The user confirmed the quick inline route for this narrow correction only.
- Independent review is not provided by quick; its human gate is at tasks.
- Host enforcement integration, new hooks, platform changes and automatic
  resumption of feature 039 are excluded.
- Existing unrelated worktree edits are preserved.
