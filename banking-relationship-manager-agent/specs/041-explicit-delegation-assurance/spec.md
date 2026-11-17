# Feature Specification: Explicit Delegation Assurance

**Feature Directory**: `041-explicit-delegation-assurance`

**Created**: 2026-11-17

**Status**: Draft for human specification approval

**Input**: Allow explicitly human-accepted lower-assurance delegation for ordinary
work when runtime worker restrictions cannot be independently verified. Keep
strict review boundaries and all unrelated safeguards. Implement inline with
selected independent plan review.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explicitly accept a bounded assurance limitation (Priority: P1)

As an operator of an ordinary development workflow, I can knowingly accept that
the host's enforcement of declared worker restrictions is unverified, instead of
being permanently blocked by missing diagnostic capabilities.

**Why this priority**: Missing evidence is currently a stop even when the named
worker is available and no enforcement failure has been established.

**Independent Test**: Exercise an eligible pending stage with and without a
valid human acceptance. Only the accepted case may proceed past the missing
runtime-enforcement-evidence condition; all other prerequisites still apply.

**Acceptance Scenarios**:

1. **Given** eligible ordinary work with no observed worker-boundary failure,
   **When** no explicit acceptance exists, **Then** missing required runtime
   evidence remains a stop and the operator receives an actionable explanation.
2. **Given** the same work, **When** a human accepts the disclosed limitation for
   its named workers and stage, **Then** delegation may proceed using those
   workers and their declared restrictions, with assurance reported as
   `unverified: human accepted`, never as verified.
3. **Given** a recorded acceptance, **When** work is inspected after a restart,
   **Then** its scope, rationale and limitations remain visible without granting
   acceptance to another feature, stage or worker configuration.

### User Story 2 - Preserve failures and strict boundaries (Priority: P1)

As a maintainer, I retain fail-closed handling for actual capability failures,
strict review modes and authorization requirements.

**Why this priority**: A missing diagnostic must not become an excuse to ignore
an observed violation or weaken a higher-assurance workflow.

**Independent Test**: Apply the acceptance to ineligible work and to ordinary
work with a known failure. Every case remains blocked with its actual reason.

**Acceptance Scenarios**:

1. **Given** accepted ordinary work, **When** named-agent selection fails or
   forbidden delegation is observed, **Then** execution stops without generic
   substitution, automatic retries or a claim that the acceptance overrides it.
2. **Given** hybrid no-tool review, enterprise work, a security-patch workflow,
   or work whose risk requires verified isolation, **When** lower assurance is
   requested, **Then** it cannot replace the existing requirements.
3. **Given** accepted ordinary work, **When** a human gate, source consent,
   audit-integrity check, worker-call budget, review requirement or required
   verification blocks progress, **Then** that condition remains authoritative.

### User Story 3 - Resume existing work without rewriting history (Priority: P2)

As the operator of feature 039, I can separately accept this limitation for its
pending implementation after the policy change is delivered, without replacing
its confirmed route or rewriting earlier evidence.

**Why this priority**: The portable-package work should benefit from the change,
but approval of a policy change is not permission to resume every old feature.

**Independent Test**: Inspect an existing initialized feature before and after a
separate scoped acceptance; its route and prior audit history remain intact.

**Acceptance Scenarios**:

1. **Given** feature 039 is pending, **When** feature 041 is approved or completed,
   **Then** 039 is not automatically accepted, started, reset or marked complete.
2. **Given** the new policy is delivered, **When** the operator separately accepts
   lower assurance for 039's eligible pending stage, **Then** the ordinary resume
   path can recognize the acceptance without changing its confirmed assignments.

### Edge Cases

- Missing, malformed, tampered, declined or out-of-scope acceptance remains a stop.
- A changed worker set, declared tool configuration, stage or host/session context
  requires fresh acceptance; old evidence is not silently broadened.
- Unknown/custom profiles are ineligible by default, rather than inheriting an
  exception because their names appear ordinary.
- An interruption or a failed worker call still requires the existing recovery
  procedure; acceptance cannot exclude a live worker or reset its call budget.
- Worker self-reports, absence of nested calls and static tests are not proof of
  runtime isolation, even when the human accepts proceeding without that proof.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Lower assurance MUST be an explicit, recorded human decision, never
  an agent default, implicit profile choice or consequence of approving this
  specification. Without it, existing missing-evidence stops remain.
- **FR-002**: Before requesting acceptance, the operator MUST see the feature,
  stage, host/session context, assigned named workers, declared restrictions,
  missing evidence, actual observations, rationale and residual risk. Acceptance
  MUST NOT be described as proof that the host enforces those restrictions.
- **FR-003**: Acceptance MUST be scoped to that feature, stage, host/session and
  declared worker configuration. It MUST remain inspectable and auditable, and
  MUST NOT be reused after a scope or configuration change.
- **FR-004**: Only ordinary work on the existing `feature`, `bugfix`, `refactor`
  and `selective` profiles MAY be eligible. These profile names alone MUST NOT
  waive risk assessment or permit work that requires verified isolation.
- **FR-005**: The exception MUST NOT apply to hybrid no-tool review, enterprise,
  security-patch or unrecognized/custom profiles, or override an explicitly
  required higher-assurance boundary.
- **FR-006**: Eligible execution MUST retain actual named-worker selection,
  declared restrictions, bounded invocation accounting, independent reviews and
  observed-failure stops. It MUST NOT substitute generic workers or enable
  recursive delegation.
- **FR-007**: Human gates, lifecycle ownership, raw-source consent, audit
  integrity, recovery exclusions, verification approval and existing required
  checks MUST remain unchanged. No application authorization or data handling
  boundary may rely on this lower-assurance decision.
- **FR-008**: User guidance, conductor decisions and workflow inspection MUST
  consistently distinguish verified evidence, an accepted lack of evidence and
  an observed failure. Accepted execution MUST visibly retain its unverified
  status rather than silently presenting ordinary verified readiness.
- **FR-009**: Existing features MUST retain their routes, task state and prior
  evidence. Applying this exception to an eligible pending stage MUST require
  its own acceptance, without automatically starting work or resetting calls.
- **FR-010**: Focused checks MUST cover the accepted ordinary case, the default
  stop, invalidated acceptance, excluded strict modes, observed failures and
  preservation of existing gates/accounting. Static checks MUST NOT be presented
  as live-host certification.

### Key Entities

- **Assurance acceptance**: The human's bounded decision, scope, rationale,
  disclosed missing evidence and residual risk, linked to the feature history.
- **Assurance status**: Verified, unverified without acceptance, unverified with
  explicit acceptance, or observed failure; acceptance never transforms missing
  evidence into verified evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An otherwise eligible ordinary stage with valid human acceptance
  proceeds past the missing-runtime-evidence condition, while the same stage
  without acceptance remains stopped.
- **SC-002**: Every tested strict-mode, observed-failure and invalidated-scope
  case remains blocked despite the proposed exception.
- **SC-003**: Every accepted execution report identifies both the acceptance and
  the remaining unverified isolation; none claims host certification.
- **SC-004**: Completing this change makes zero automatic changes to feature
  039's route, call accounting, approval decisions or implementation status.

## Assumptions

- This feature uses the human-confirmed selective route: inline stage work,
  independent architecture plan review, and specification/plan human gates.
  The preset does not assign independent implementation review.
- The affected requirement is development-workflow assurance, not permission to
  weaken application authorization, tenant isolation or credential handling.
- Declared tool restrictions remain required configuration but are not treated
  as authenticated runtime evidence or a security boundary.
- Feature 039 remains a separate work item; packaging, publication, snapshot
  consent, unrelated formatting and pre-existing wider test failures are outside
  this feature.
