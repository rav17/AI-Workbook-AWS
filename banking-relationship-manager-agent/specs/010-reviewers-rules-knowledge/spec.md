# Feature Specification: Reviewers, Learned Rules, Team Knowledge and Extended Stages

**Feature Branch**: `010-reviewers-rules-knowledge`

**Created**: 2026-11-05

**Status**: Draft

**Input**: User description: "Phase 2 of incorporating AI-DLC concepts into our Spec Kit workflow: independent reviewer agents with source-bound review evidence, learned rules, a team knowledge base, an adaptive composer that proposes a custom route, and optional extra lifecycle stages (ideation, deploy, operate). Builds on 009 workflow profiles and audit trail."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Independent review with evidence (Priority: P1)

At a gated stage, a reviewer (spec, plan or code reviewer) checks the stage's output against the requirements and project principles and produces a review record. Every finding cites the exact file and section it applies to. The human sees the findings at the approval gate, and the gate decision is linked to the review in the audit trail.

**Why this priority**: Approval gates today rely on a human reading everything. Source-bound findings make approvals faster and defensible, which matters in a banking context.

**Independent Test**: Run the spec reviewer on a spec containing a known gap; the review lists the gap with a citation to the spec section, and approving the gate records a link to that review.

**Acceptance Scenarios**:

1. **Given** a completed gated stage, **When** the reviewer runs, **Then** a review record is saved with the reviewer role, the stage, a verdict (pass, concerns, block) and findings.
2. **Given** a finding without a file and section citation, **When** the review is saved, **Then** it is rejected as invalid.
3. **Given** a review with a `block` verdict, **When** the human tries to approve, **Then** approval requires an explicit override with a reason, which is audited.
4. **Given** a profile whose depth is minimal, **When** a stage completes, **Then** review is optional; at comprehensive depth it is required before approval.

---

### User Story 2 - Team knowledge and learned rules (Priority: P2)

Teams keep standards and domain knowledge (for example banking compliance guidance) in a knowledge folder that stages and reviewers consult. After a run, the workflow proposes short behavioural rules learned from rejected gates and review findings. A human approves or discards each proposed rule; approved rules are applied in later runs.

**Why this priority**: This is how context and lessons survive across features instead of being lost.

**Independent Test**: Reject a gate with a reason, run the learning step, approve the proposed rule, then start a new feature and confirm the rule is listed as active and shown to the reviewer.

**Acceptance Scenarios**:

1. **Given** documents in the knowledge folder, **When** a stage starts, **Then** the relevant document titles are listed as consulted context.
2. **Given** a rejected gate with a reason, **When** the learning step runs, **Then** a proposed rule is stored as pending and is not applied.
3. **Given** a pending rule, **When** the human approves it, **Then** it becomes active and appears in later runs; if discarded, it is never applied.
4. **Given** a rule proposal containing secrets or customer data, **When** it is saved, **Then** it is rejected.

---

### User Story 3 - Adaptive composer for custom routes (Priority: P3)

When no profile fits, the composer proposes a custom stage route (with depth and gates) from the request, explaining each choice. The human confirms or edits it, and it is saved as a profile for that feature.

**Why this priority**: Useful but optional; the fixed profiles cover most work.

**Independent Test**: Describe mixed work (a bug fix plus an infrastructure change); the composer proposes a valid route; once confirmed, the feature runs on it.

**Acceptance Scenarios**:

1. **Given** a request that fits no profile well, **When** the composer runs, **Then** it proposes a route that passes profile validation, with a reason per stage.
2. **Given** an invalid proposal, **When** it is validated, **Then** it is rejected with the specific rule broken.
3. **Given** the human confirms, **When** the workflow starts, **Then** the route is stored with the feature and the choice is audited.

---

### User Story 4 - Optional lifecycle stages: ideation, deploy, operate (Priority: P3)

Profiles can include an `ideation` stage before specify (problem framing and feasibility), and `deploy` and `operate` stages after implement (release checklist, rollback plan, run-book and monitoring expectations). These follow the same state, gate and audit rules as other stages.

**Why this priority**: Connects requirements to operational work, but depends on the other stories being stable.

**Independent Test**: Create a profile including all three stages and run it; each stage appears in state and audit, and existing profiles behave unchanged.

**Acceptance Scenarios**:

1. **Given** a profile with `deploy`, **When** the stage runs, **Then** a release checklist with rollback plan is produced and gated.
2. **Given** an existing 009 profile, **When** it runs, **Then** behaviour is identical to before.

---

### Edge Cases

- Reviewer unavailable or review fails to save: the gate stays pending and the failure is audited; no silent approval.
- Knowledge folder empty or missing: stages run normally and note that no knowledge was found.
- Conflicting active rules: the stricter rule wins and the conflict is flagged to the human.
- Rule store grows large: only active rules relevant to the stage are shown, capped to a readable count.
- Review evidence refers to a file that later changes: the review records a content fingerprint so staleness is visible.
- Reviewer and author must be different roles; a stage's own agent cannot approve its own output.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workflow MUST provide reviewer roles for spec, plan and code, each producing a saved review record per stage.
- **FR-002**: Every review finding MUST cite a file and section and MUST have a severity; findings without a citation MUST be rejected.
- **FR-003**: A review MUST carry a verdict (`pass`, `concerns`, `block`) and a content fingerprint of the reviewed files.
- **FR-004**: Approving a gate whose latest review is `block` MUST require an explicit override reason; the override MUST be audited.
- **FR-005**: Review MUST be required before approval at comprehensive depth and optional at minimal and standard depth.
- **FR-006**: Gate approval events MUST reference the review record they relied on.
- **FR-007**: The workflow MUST support a team knowledge folder and list consulted documents for each stage.
- **FR-008**: The workflow MUST propose rules from rejected gates and review findings as pending, never active, until a human approves them.
- **FR-009**: Rules MUST be individually approvable, discardable and listable, with status and origin; active rules MUST be shown to stages and reviewers.
- **FR-010**: Rules and knowledge MUST NOT contain secrets or customer data.
- **FR-011**: The composer MUST propose a route that satisfies the same validation as profiles and explain each stage choice.
- **FR-012**: Confirmed composer routes MUST be saved with the feature and audited.
- **FR-013**: The workflow MUST support optional `ideation`, `deploy` and `operate` stages with their own artifacts, gates and audit events, without changing existing profile behaviour.
- **FR-014**: A stage's author role MUST NOT be accepted as the reviewer of its own output.
- **FR-015**: All review, rule and composer actions MUST be recorded in the audit trail.

### Key Entities

- **Review Record**: Reviewer role, stage, verdict, findings (severity, file, section, note), content fingerprint, timestamp.
- **Rule**: Short behavioural statement with origin (gate or finding), status (pending, active, discarded) and approver.
- **Knowledge Document**: Team standard or domain note in the knowledge folder, with a title and scope.
- **Composed Route**: Custom stage list with depth, gates and per-stage reasons, stored with the feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of review findings link to a specific file and section.
- **SC-002**: A reviewer can read a stage's review and make a gate decision in under 5 minutes for a typical feature.
- **SC-003**: 0 rules become active without explicit human approval.
- **SC-004**: A lesson from one feature is visible in the next feature's run without manual copying, in 100% of approved rules.
- **SC-005**: 100% of overrides of blocking reviews carry a recorded reason.
- **SC-006**: All existing profiles from the previous phase run unchanged.
- **SC-007**: A composed route is proposed and validated in under 1 minute of the user's time.

## Assumptions

- Builds on feature 009: profiles, state and audit trail are available and extended, not replaced.
- Reviewers are agent roles (skills) that assist the human; the human always makes the final gate decision.
- Review records, rules and knowledge are stored as readable, version-controlled files with the feature or the project.
- Rule proposal and composer suggestions are advisory and use simple deterministic checks plus agent judgement; no new external services.
- Deploy and operate stages produce planning artifacts only; they do not perform real deployments.
- The domain-expert agent roster from AI-DLC (11 agents) is out of scope; only reviewers and the composer are added.
