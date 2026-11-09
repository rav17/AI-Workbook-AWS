# Feature Specification: Profile-Aware Workflow Orchestration

**Feature Branch**: Not requested; preserve the current branch.
**Created**: 2026-11-10
**Status**: Implemented and verified within the evidence boundaries below.
**Input**: Route work requests to an appropriate confirmed profile, wire the
standard workflow and individual stage skills through the conductor, and verify
subagent functionality without bypassing human decisions.

## User Scenarios & Testing

### User Story 1 - Select the right lifecycle (Priority: P1)

As a contributor, I want my request classified before work starts so a new
feature, bug fix, hotfix, infrastructure change, refactor or experiment uses
an appropriate lifecycle rather than the same hard-coded route.

**Independent Test**: Present representative requests and verify the recommendation,
reason, confirmation requirement, and clarification for ambiguous requests.

**Acceptance Scenarios**:

1. **Given** a clearly new feature, **When** routing is requested, **Then**
   full-lifecycle is recommended and the user confirms the route before initialization.
2. **Given** a bug or hotfix, **When** routing is requested, **Then** bugfix is
   recommended without weakening its gates; security fixes recommend security-patch.
3. **Given** an ambiguous or mixed request, **When** routing is requested,
   **Then** the user is asked to select or clarify a profile instead of an
   unannounced default being initialized.
4. **Given** an explicit supported profile, **When** routing is requested,
   **Then** it takes precedence over inference and its stages/gates are presented.
5. **Given** initialized work, **When** routing is entered again, **Then**
   its existing route is preserved; changes require an explicit confirmed switch.

### User Story 2 - Execute through the assigned agents (Priority: P1)

As a contributor, I want the standard entry point and direct lifecycle stage
skills to use the conductor and assigned specialists, with no recursive dispatch
or silent fallback to pretending the parent is a subagent.

**Independent Test**: Drive a non-default route through the entry point, observe
assigned lead/support/reviewer briefs, and verify stage order, pending gates,
failure handling and restart behavior.

**Acceptance Scenarios**:

1. **Given** a confirmed profile, **When** standard workflow execution begins,
   **Then** the selected route drives execution rather than a fixed four-stage list.
2. **Given** a directly requested stage skill, **When** it is entered from outside
   the conductor, **Then** it routes to the conductor, validates stage eligibility
   and delegates once to the assigned lead.
3. **Given** a stage lead executing a conductor brief, **When** it follows the
   stage skill, **Then** it performs the skill body without recursively dispatching.
4. **Given** a pending human gate, parked work or invalid/stale audit state,
   **When** execution is requested, **Then** no downstream agent is dispatched.
5. **Given** unavailable subagent support or an unavailable assigned agent,
   **When** dispatch is attempted, **Then** the limitation is reported and work stops.
6. **Given** a supporting agent, author and reviewer, **When** work is delegated,
   **Then** contributions are returned in allowed form and the reviewer is
   independent; read-only agents are not instructed to write contribution files.

### User Story 3 - Reuse and verify the integration (Priority: P2)

As a toolkit adopter, I want routing and orchestration included in portable
installs without inheriting application policy or fictional execution evidence.

**Independent Test**: Install into a non-banking fixture, inspect/run routing
and dispatch checks, and verify project-owned settings remain preserved.

**Acceptance Scenarios**:

1. **Given** a portable install, **When** a new request enters, **Then** the same
   routing, confirmation and conductor instructions are available.
2. **Given** automated dispatch tests, **When** reporting results, **Then**
   deterministic routing/engine tests are distinguished from actual host subagent
   invocation and from live production/deployment behavior.
3. **Given** disabled optional packs and local settings, **When** the integration
   is installed/updated, **Then** pack enablement and existing project policy
   are not overwritten.

### Edge Cases

- Mixed new-feature and bugfix intent; an investigation with no actionable category.
- Words occurring in a technical description rather than expressing work intent.
- Explicit unknown/disabled profile, omitted stage or stage requested out of order.
- Initial ideation before a specification exists; repeated skill entry after completion.
- Partial failure, pending/rejected gates, stale review/sensor evidence or broken audit chain.
- Missing conductor permissions, undispatchable plugin agents, or an agent
  configuration that disables model invocation.
- Existing static workflow runs and initialized features must not be silently migrated.

## Requirements

### Functional Requirements

- **FR-001**: Routing MUST recommend full-lifecycle for clearly new features,
  bugfix for bugs/hotfixes, security-patch for security fixes, and appropriate
  existing specialized profiles for other recognized work.
- **FR-002**: Recommendations MUST include a reason and require user confirmation
  before initialization; ambiguous/mixed input MUST request clarification.
- **FR-003**: Explicit profile selection MUST override inference; unavailable
  profiles MUST fail explicitly and list valid alternatives.
- **FR-004**: Existing initialized routes MUST be preserved unless explicitly switched.
- **FR-005**: The standard workflow MUST use the profile-aware entry point rather
  than enforcing a fixed feature route.
- **FR-006**: Direct lifecycle stage skills MUST use the same conductor handoff,
  with an explicit recursion-safe path for an already delegated stage lead.
- **FR-007**: Dispatch MUST validate the route, stage, audit integrity, parked
  status and pending gate before invoking downstream agents.
- **FR-008**: Conductor briefs MUST identify the lead, bounded supporting roles,
  independent reviewers, relevant artifacts and allowed actions; read-only
  contributors MUST return text rather than be required to edit files.
- **FR-009**: Missing host dispatch capability or required agent configuration
  MUST stop explicitly, without claiming delegation occurred.
- **FR-010**: Human gates, rule decisions, verification approval, sensors and
  explicit deployment authorization MUST remain intact.
- **FR-011**: Shared routing/instructions MUST be distributed in the portable
  bundle while preserving project-owned settings and disabled pack defaults.
- **FR-012**: Verification MUST cover category selection, explicit override,
  ambiguity, route-driven dispatch, direct-skill handoff, recursion prevention,
  blocking conditions and portability, with honest evidence boundaries.

### Key Entities

- **Routing recommendation**: Work category, candidate profile(s), reason,
  clarification need and user confirmation.
- **Stage dispatch brief**: Profile/stage, assigned lead, supporting specialists,
  independent reviewers, relevant files and bounded permissions.
- **Execution context**: Selected feature, route state, pending decision and
  whether the current invocation is already delegated by the conductor.

## Success Criteria

- **SC-001**: Every supported category in the regression matrix produces the
  expected recommendation; ambiguous cases never initialize a route automatically.
- **SC-002**: Standard and direct-skill entry paths use the same selected route
  and conductor handoff, with zero recursive handoffs in the acceptance scenarios.
- **SC-003**: Every tested pending gate, parked feature, broken audit or invalid
  agent configuration prevents downstream dispatch.
- **SC-004**: Portable acceptance demonstrates the routing integration in an
  unrelated project without application policy or preapproved commands.
- **SC-005**: Validation reporting explicitly separates simulated dispatch,
  real host subagent invocation and untested live integrations.

## Assumptions

- User confirmed: recommend full-lifecycle for new features, always ask before
  initializing a recommended profile, and map hotfix to the existing bugfix profile.
- This changes the reusable workspace toolkit, not personal instructions.
- Optional plugins remain disabled. No blanket full-lifecycle migration,
  production deployment, new harness adapter or parallel-worker scheduler is included.
- Shorter profiles remain available; the receiving project's principles still apply.
