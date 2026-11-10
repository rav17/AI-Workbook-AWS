# Feature Specification: AI-DLC Agent Roster

**Feature Branch**: `012-ai-dlc-agent-roster`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Add AI-DLC's 14 agents (11 domain experts, 2 reviewers, 1 composer) as Copilot custom agents, map them to workflow stages in profiles, and record agent actors in the audit trail"

## User Scenarios & Testing

### User Story 1 - Use a roster of specialist agents (Priority: P1)

As a contributor, I want a named roster of 14 specialist agents (11 domain experts, 2 reviewers, 1 composer) available in my Copilot environment, so that each lifecycle stage is handled by an agent with the right focus, tools and boundaries.

**Why this priority**: The roster is the requested deliverable; the other stories build on it.

**Independent Test**: List the agent files and confirm exactly 14 exist, each with a unique name, a description, a declared role (domain, reviewer or composer) and a declared tool scope.

**Acceptance Scenarios**:

1. **Given** the repository is set up, **When** a contributor lists the agents, **Then** 11 domain agents, 2 reviewer agents and 1 composer agent are present with unique names.
2. **Given** a reviewer agent, **When** its definition is read, **Then** it is restricted to reviewing and recording evidence and cannot approve gates.
3. **Given** the composer agent, **When** its definition is read, **Then** it proposes a route but states that a human must approve it before use.

### User Story 2 - See which agents own each stage (Priority: P2)

As a contributor, I want each workflow profile to declare a lead agent and supporting agents for every stage, so that I know who is responsible and who assists at each point.

**Why this priority**: Mapping turns a list of agents into an orchestrated lifecycle.

**Independent Test**: Show a profile's stage assignments; verify every stage has exactly one lead and that an unknown agent or stage in a mapping is rejected.

**Acceptance Scenarios**:

1. **Given** any shipped profile, **When** its assignments are displayed, **Then** every stage in its route shows one lead agent and zero or more supporting agents.
2. **Given** a mapping naming an agent that is not in the roster, **When** the profile is validated, **Then** validation fails and names the unknown agent.
3. **Given** a profile created before this feature without assignments, **When** it is loaded, **Then** it remains valid and uses default assignments.

### User Story 3 - Attribute work to agents in the audit trail (Priority: P3)

As an auditor, I want stage and review events to record which agent acted, so that the audit trail shows who did what, while human-only decisions stay human.

**Why this priority**: Attribution completes the audit story but depends on the roster and mapping.

**Independent Test**: Record a stage start as an agent, a review as a reviewer agent, and attempt an agent-made gate approval and rule approval; confirm the first two are recorded and the last two are refused.

**Acceptance Scenarios**:

1. **Given** a known agent name, **When** it starts or completes a stage, **Then** the audit event records that agent as the actor.
2. **Given** an unknown agent name, **When** it is used as an actor for an agent-restricted action, **Then** the action is refused.
3. **Given** an agent actor, **When** it attempts to approve a gate or a learned rule, **Then** the action is refused and the audit chain remains valid.

## Edge Cases

- A profile's route omits a stage that the mapping assigns: validation reports the extra stage.
- A stage has no mapping in a legacy profile: the default assignment applies instead of failing.
- An agent file is removed while a profile references it: validation reports the missing agent.
- Two agents share a name: roster validation fails.
- A reviewer agent is listed as lead for a stage that has no review requirement: allowed, but it still cannot approve.

## Requirements

### Functional Requirements

- **FR-001**: The project MUST provide exactly 14 roster agent definitions plus one conductor: 11 domain experts (product, design, delivery, architect, aws-platform, compliance, devsecops, developer, quality, pipeline-deploy, operations), 2 reviewers (product-lead, architecture-reviewer) and 1 composer.
- **FR-002**: Each agent definition MUST include a unique name, a description, a role, the stages it leads and supports, and a tool scope.
- **FR-003**: Reviewer agents MUST be review-only: they record review evidence and MUST NOT approve gates, approve rules or edit deliverables. This MUST be enforced by their granted tool scope (no edit capability), not only by instructions.
- **FR-004**: The composer agent MUST propose routes only; a route takes effect only after explicit human approval through the existing compose flow.
- **FR-015**: The project MUST provide a conductor agent that is the only agent allowed to delegate. It reads a feature's stage assignments and dispatches each stage's lead and supporting agents as independent sub-agents with self-contained context. Roster agents MUST NOT be able to delegate to each other.
- **FR-016**: Roster agents MUST be hidden from the interactive agent picker except the conductor, and only the conductor may invoke them as sub-agents.
- **FR-017**: A pre-tool-use hook MUST block any agent-initiated command that approves or rejects a gate, approves a rule, or edits the audit log, state or rules files directly, and MUST report the reason. Human-run commands are unaffected.
- **FR-018**: Stage skills MUST name the stage's lead agent so the assignment is visible in the ordinary workflow.
- **FR-005**: Profiles MUST support an optional per-stage assignment of one lead agent and zero or more supporting agents, validated against the roster and the profile's route.
- **FR-006**: Profiles without assignments MUST remain valid and receive default assignments derived from the roster.
- **FR-007**: Every stage of every shipped profile MUST resolve to a lead agent, using the roster's default stage ownership unless the profile declares its own assignment.
- **FR-008**: The lifecycle MUST report the assignments for a profile and for the current stage of a feature.
- **FR-009**: Audit events MUST accept agent actors for stage start, stage done and review recording, and MUST validate the agent name against the roster.
- **FR-010**: Gate approval, gate rejection, and learned-rule approval MUST remain restricted to human actors.
- **FR-011**: Existing profiles, state, audit chains, reviews, rules and workflow automation MUST continue to work unchanged.
- **FR-012**: Agents MUST reuse the existing deterministic review, rules and compose commands rather than duplicating their logic.
- **FR-013**: Roster validation MUST be runnable on demand and fail with clear messages for duplicate, missing or malformed agent definitions.
- **FR-014**: Documentation MUST describe the roster, the stage assignments, and the human-only decision boundary.

### Key Entities

- **Agent**: A named specialist with a role (domain, reviewer or composer), tier, description, led and supported stages, and tool scope.
- **Stage assignment**: For one stage of a profile, one lead agent and any supporting agents.
- **Roster**: The validated set of 14 agents.
- **Agent actor**: An audit actor identity naming an agent rather than a human.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Roster validation passes with exactly 14 agents: 11 domain, 2 reviewer, 1 composer.
- **SC-002**: 100% of shipped profiles show a lead agent for every stage in their route.
- **SC-003**: In 100% of tested cases, agent actors cannot approve gates or learned rules.
- **SC-006**: In 100% of tested cases, the hook blocks an agent-initiated gate approval, rule approval and direct edit of audit or state files, while allowing read-only status commands.
- **SC-004**: All pre-existing automated tests continue to pass without modification of their expectations.
- **SC-005**: A contributor can find a stage's lead and supporting agents with a single command.

## Assumptions

- Agents are delivered as Copilot custom agent files under the repository's agent folder, matching the active Copilot integration.
- AI-DLC's 33 stages are not adopted; AI-DLC agent responsibilities are remapped onto this project's existing nine stages.
- Agents are advisory personas and cannot be spawned by this project's CLI; the CLI records and validates their attribution.
- AI-DLC's reviewer and composer behaviors are rebuilt as agents on top of the existing deterministic review and compose features.
- Human approval, the audit hash chain and human-only rule decisions are unchanged.
