# Feature Specification: Reliable Worker Recovery

**Feature Branch**: `033-reliable-worker-recovery`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User-selected increment: reliable worker recovery with portable, model-free scenarios and reviewable approval evidence. The current feature profile is authoritative; the historical full-lifecycle route recorded in ideation is provenance only, not an approved gate or current route.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect ownership and progress (Priority: P1)

A workflow operator needs a trustworthy, bounded account of who owns a task, what verified progress exists, and whether execution is running, delayed, unavailable, or unknown. The operator must not mistake a status report or timeout for proof that a worker has stopped.

**Why this priority**: Without an accurate owner and progress view, an operator cannot make a safe recovery decision or tell useful delay from missing evidence.

**Independent Test**: Present a model-free recovery scenario in each of the four status conditions. The operator can identify the reported owner and verified progress, distinguish all four outcomes, and receive a useful report no later than the configured wait deadline.

**Acceptance Scenarios**:

1. **Given** a task with durable ownership and progress and evidence that execution is active, **When** an operator requests status, **Then** the report identifies the owner and verified progress and labels the outcome running.
2. **Given** a task whose work is scheduled or waiting, **When** an operator requests status, **Then** the report labels the outcome delayed and does not describe that outcome as stopped or safe to take over.
3. **Given** required host evidence is inaccessible, **When** an operator requests status, **Then** the report labels the outcome unavailable, identifies the missing evidence, and does not infer that the worker is dead.
4. **Given** evidence is incomplete, ambiguous, or conflicting, **When** an operator requests status, **Then** the report labels the outcome unknown, states the limitation, and does not infer an owner change or safe takeover.
5. **Given** no decisive status arrives before the configured wait deadline, **When** the wait ends, **Then** the operator receives the latest owner/progress information, evidence status, uncertainty, and safe next options by that deadline.

### User Story 2 - Recover without losing verified progress or creating concurrent work (Priority: P1)

A worker or operator needs to continue after interruption from the latest checkpoint whose completion and supporting evidence remain valid, while preserving single-writer safety and unrelated work.

**Why this priority**: Recovery is valuable only if it avoids lost verified work and does not turn uncertainty into conflicting execution or repeated external effects.

**Independent Test**: Replay model-free interruption, restart, duplicate-dispatch, and simultaneous-recovery scenarios using valid, stale, and invalid checkpoint evidence. Verify identity, the selected progress boundary, preserved unrelated edits, and the absence of concurrent effective writers.

**Acceptance Scenarios**:

1. **Given** a worker starts or resumes a task, **When** it reports its identity, **Then** it is not classified as a different owner merely because of a mistaken or missing self-identity value; if identity cannot be established, the path is blocked and reported as unknown.
2. **Given** a dispatch or recovery request duplicates work already effectively owned, **When** the request is evaluated, **Then** it does not create a second effective writer.
3. **Given** a worker is interrupted and the latest checkpoint and its completion evidence remain valid, **When** recovery is approved and safe exclusion of prior execution is established, **Then** continuation starts from that verified checkpoint without treating later unverified work as complete.
4. **Given** a checkpoint is incomplete, stale, inconsistent, or invalidated by a relevant change to its inputs, dependencies, instructions, or verification evidence, **When** recovery is evaluated, **Then** that checkpoint is not reported as verified or used as the resume boundary.
5. **Given** the host cannot establish worker identity or prevent overlapping effective writers, **When** recovery is requested, **Then** the operator receives an explicit blocked limitation and no ownership transfer or continuation that could create a concurrent writer occurs.
6. **Given** a heartbeat expires, a worker is absent from a host listing, or liveness is otherwise uncertain, **When** recovery is requested, **Then** the uncertainty alone never authorizes automatic ownership theft.
7. **Given** the outcome of an earlier external side effect is uncertain, **When** recovery is evaluated, **Then** the task is not automatically replayed on the assumption that the side effect did not occur.
8. **Given** recovery changes a task ownership or verified progress, **When** the resulting record is reviewed, **Then** unrelated user edits remain unchanged.

### User Story 3 - Review and authorize a bounded recovery decision (Priority: P2)

A human approver needs the decision and its evidence before deciding whether to authorize a recovery action, with the allowed scope and limits easy to understand.

**Why this priority**: Approval is meaningful only when the person can inspect what is known, what remains uncertain, and exactly what their decision permits.

**Independent Test**: Review a model-free approval package using keyboard and screen-reader access, without relying on color or link text alone. Confirm that the decision, scope, evidence status, uncertainty, authorization provenance, and allow/exclude boundaries are all available before the approval choice.

**Acceptance Scenarios**:

1. **Given** a recovery decision requires human approval, **When** the approval is presented, **Then** the reviewer first sees the decision and scope, relevant evidence or its readable content, the actual review/verification status, unknowns and limitations, and exactly what approval allows and excludes.
2. **Given** the reviewer inspects the package, **When** the reviewer uses keyboard or screen-reader navigation, **Then** all required decision information and controls are available without relying on color or link-only meaning.
3. **Given** approval is recorded, **When** the decision record is reviewed, **Then** it contains safe metadata sufficient to trace decision, scope, authorization provenance, outcome, and evidence status; an actor label alone is not represented as proof that a human saw or authorized the decision.
4. **Given** identity, safe exclusion, or required evidence cannot be established, **When** a human reviews the package, **Then** approval does not bypass the missing safety boundary and the recovery remains blocked.
5. **Given** the capability is evaluated in a receiving project with its own governance, **When** portable model-free scenarios are run, **Then** no model or live resource is invoked, no optional pack is activated implicitly, project governance is unchanged, and fixtures contain synthetic data only.
6. **Given** a requested action would move money or change customer records, **When** the request is evaluated, **Then** the action is out of scope and is not performed.

## Edge Cases

- A heartbeat expires while the worker is still running, delayed, or temporarily unobservable; expiry is not evidence of death.
- A host listing omits a worker, or the host evidence source is unavailable; absence and unavailability do not authorize takeover.
- Available observations disagree about owner, worker identity, liveness, or progress; classify the result as unknown and block unsafe continuation.
- Two operators request recovery at the same time, or duplicate dispatches overlap; no path may permit more than one effective writer.
- A checkpoint write or its supporting evidence is interrupted, partially available, or no longer matches relevant inputs or verification; it is not treated as verified.
- A previously verified checkpoint is followed by changed relevant files, dependencies, instructions, or reviews; invalidate dependent completion claims while preserving unrelated edits.
- A host adapter lacks identity or safe-exclusion capability; report the limitation and block the unsafe path rather than claiming universal host recovery.
- An external side effect may have occurred before interruption; do not promise exactly-once replay or absence of duplicate side effects beyond boundaries that can actually be enforced, and do not replay automatically when the outcome is uncertain.
- A status wait reaches its configured deadline without a definitive result; return a bounded report instead of waiting indefinitely.
- Evidence contains customer information, raw prompts, credentials, or other sensitive payloads; exclude it from logs, audit records, checkpoints, approval summaries, specifications, and test fixtures.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The recovery capability MUST provide an operator with durable task ownership and progress information that distinguishes verified progress from merely saved or unverified work.
- **FR-002**: The recovery capability MUST report running, delayed, unavailable, and unknown as distinct outcomes and state the evidence status and limits relevant to each report.
- **FR-003**: The recovery capability MUST end each status wait by its configured deadline and provide the latest available owner, progress, evidence status, uncertainty, and safe next options.
- **FR-004**: A worker MUST be identified as the current worker correctly; if its identity cannot be established, the capability MUST report the limitation and block any ownership-sensitive action.
- **FR-005**: Duplicate dispatch or simultaneous recovery MUST NOT result in more than one effective writer for a task.
- **FR-006**: The capability MUST NOT treat heartbeat expiry, absence from a host listing, delayed execution, host unavailability, or unknown liveness as proof of worker death or authorization for automatic ownership transfer.
- **FR-007**: A recovery continuation MUST use the latest checkpoint in the task's recorded, unambiguous progression order for which the work scope, completion criteria, completion claim, and applicable verification and its result are identified; accessible and interpretable evidence demonstrates each completion criterion and the verification result; and the checkpoint remains applicable to the current state of that work. If the ordering of otherwise eligible checkpoints cannot be established unambiguously, the capability MUST report unknown or blocked and MUST NOT choose an ambiguous resume boundary.
- **FR-008**: A checkpoint MUST NOT be represented as verified or resumable when it is incomplete, stale, inconsistent, or its supporting evidence is missing, inaccessible, ambiguous, contradictory, or insufficient to substantiate each recorded completion criterion, completion claim, or applicable verification result. A relevant change to the work's inputs, dependencies, instructions, completion claims, or verification evidence invalidates the dependent completion claim; unrelated edits MUST NOT invalidate unrelated progress. When evidence cannot be verified against the current relevant state, the checkpoint MUST be classified as not verified and not resumable.
- **FR-009**: If a host cannot establish identity or a safe boundary against overlapping effective writers, the capability MUST report the blocked path and MUST NOT continue or transfer ownership in a way that permits concurrent effective writers.
- **FR-010**: Recovery ownership changes MUST require an explicit human decision; an autonomy grant for recovery actions is not in scope. Human approval MUST NOT substitute for the safe-exclusion condition in FR-009.
- **FR-011**: Before a human makes an approval decision, the review package MUST present the decision and scope, relevant evidence or readable evidence content, actual review/verification status, unknowns and limitations, authorization provenance, and exactly what the decision permits and excludes.
- **FR-012**: Approval information MUST be perceivable and operable with keyboard and screen-reader access and MUST NOT rely on color or link-only meaning to convey required information.
- **FR-013**: Decision traceability MUST include safe metadata for the decision, scope, authorization provenance, outcome, and evidence status. An unverified actor label MUST NOT be described as proof of human identity, review, or authorization.
- **FR-014**: The recovery capability MUST NOT automatically replay work when the outcome of a prior external side effect is uncertain, and MUST NOT claim exactly-once task replay or elimination of duplicate external side effects beyond enforceable boundaries.
- **FR-015**: The recovery capability MUST have a host-neutral contract with a bounded host-adapter boundary and portable, model-free scenarios. The scenario inventory and minimum coverage defined under Success Criteria MUST be represented by at least one explicitly mapped case per named class, with an expected outcome for each case. It MUST NOT invoke models. Host limitations MUST be reported rather than hidden; broad multi-harness or swarm rollout is out of scope.
- **FR-016**: Receiving projects MUST retain their own policies, constitutions, commands, and governance; optional packs MUST remain disabled unless separately chosen by that project.
- **FR-017**: Logs, audit records, checkpoints, approval summaries, specifications, and test fixtures MUST NOT contain customer names, account numbers, balances, raw prompts, secrets, or unnecessary sensitive payloads. Test scenarios MUST use synthetic data.
- **FR-018**: This increment MUST NOT perform actions that move money or change customer records. Any future expansion to such actions requires explicit human approval and applicable receiving-project authorization before it is in scope.

### Key Entities *(include if feature involves data)*

- **Task ownership and progress**: The current accountable worker, its task, and the level of progress supported by verified evidence.
- **Worker status observation**: A reported running, delayed, unavailable, or unknown outcome and the evidence and limitations behind it.
- **Checkpoint evidence**: Information establishing what work is complete, what inputs and dependencies it applies to, and whether it remains valid for continuation.
- **Recovery decision**: A proposed or approved continuation or ownership change, its bounded scope, human authorization provenance, outcome, and evidence status.
- **Host capability boundary**: What a host can and cannot establish about worker identity, liveness, and safe exclusion of overlapping execution.

## Success Criteria *(mandatory)*

### Required Portable Scenario Inventory

The bounded inventory has 19 named scenario classes. Each class MUST have at least one explicitly mapped, model-free scenario with an expected outcome; a scenario may map to more than one class, but each class remains a separate coverage denominator. The required classes are:

1. Running status.
2. Delayed status.
3. Unavailable status.
4. Unknown status.
5. Self-identity is not misclassified as a different owner because of a mistaken or missing value; identity that cannot be established fails closed.
6. Duplicate dispatch.
7. Concurrent recovery requests.
8. Resume from a valid, latest eligible checkpoint.
9. Incomplete checkpoint evidence.
10. Stale checkpoint evidence.
11. Changed relevant inputs, dependencies, instructions, completion claims, or verification evidence.
12. Preservation of unrelated edits when dependent progress is invalidated or ownership changes.
13. Uncertain outcome of an external side effect.
14. Host lacking identity or safe-exclusion capability.
15. Expired heartbeat, host-listing absence, or otherwise uncertain liveness without proof of death or automatic takeover.
16. Approval review of decision scope, evidence, status, limitations, provenance, and allowed/excluded actions.
17. Approval accessibility by keyboard and screen reader without color- or link-only meaning.
18. Preservation of receiving-project governance and disabled optional packs.
19. Synthetic-only privacy coverage, with no customer data, secrets, or unnecessary sensitive payloads.

### Measurable Outcomes

- **SC-001**: The status denominator is all cases mapped to inventory classes 1, 2, 3, and 4. In 100% of those cases, the report identifies available owner and verified progress, gives the expected distinct outcome, and terminates no later than the configured wait deadline.
- **SC-002**: The concurrency denominator is all cases mapped to classes 6 and 7. The number of cases in which more than one effective writer exists MUST be zero. Separately, no case mapped to class 15 may produce automatic ownership transfer.
- **SC-003**: The checkpoint denominator is all cases mapped to classes 8, 9, 10, 11, and 12. In 100% of those cases, only an eligible verified checkpoint is used or continuation is blocked if none exists; incomplete/stale/invalidated evidence is not reported as resumable. In every class 12 case, unrelated edits remain unchanged.
- **SC-004**: The approval denominator is all cases mapped to classes 16 and 17. In 100% of those cases, the required decision, scope, evidence/status, limitations, provenance, and allow/exclude information is available before the choice and accessible without color- or link-only dependence.
- **SC-005**: The governance/privacy denominator is all cases mapped to classes 18 and 19. In 100% of those cases, there is no model invocation, customer banking data, raw prompt, secret, credential, unnecessary sensitive payload, live-resource dependency, implicit governance change, or implicit optional-pack activation.
- **SC-006**: The safety-boundary denominator is all cases mapped to classes 5, 13, 14, and 15. In 100% of cases where identity, safe exclusion, or side-effect outcome is not established, the result is explicitly unknown or blocked as applicable; no case claims universal host recovery, automatic takeover from liveness uncertainty, or exactly-once external side effects.
- **SC-007**: Required inventory coverage is 19 of 19 named classes (100%); each class has at least one explicitly mapped model-free case and an expected outcome. These are acceptance criteria for the scenario set, not claims that scenarios have already been run.

## Assumptions

- The operator or receiving project can supply a configured finite deadline for status waiting; this specification does not prescribe one universal duration.
- A host may not be able to establish identity, liveness, or safe exclusion. In that case the safe default is an explicit unknown or blocked result, not automatic ownership theft.
- Recovery authorization remains a per-decision human choice in this increment; no autonomy grant is assumed. The receiving project remains responsible for recognizing its authorized human through its own governance.
- A checkpoint is resumable only when its work scope, completion criteria, completion claim, and applicable verification and its result are identified; accessible/interpretable evidence demonstrates each criterion and verification result; its recorded applicability matches current relevant inputs, dependencies, instructions, completion claims, and verification evidence; and no relevant change invalidates the claim. Missing, inaccessible, ambiguous, contradictory, or insufficient evidence is not verified and is not resumable. Relevant changes invalidate dependent claims only; unrelated edits do not invalidate unrelated progress. Among eligible checkpoints, the latest is determined by unambiguous recorded task progression order; if that order cannot be established, the resume boundary is unknown or blocked. These are product-level evidence criteria; implementation choices remain for planning.
- The intended deliverable is a host-neutral recovery contract with a bounded, tested adapter seam and portable model-free scenarios, not a broad multi-harness or swarm rollout.
- Existing session, state, orchestration, and checkpoint facilities are contextual provenance only; their presence does not establish worker ownership, liveness, safe exclusion, or the guarantees in this specification. No tests are claimed to have passed.
- The historical ideation artifact records a full-lifecycle route. The current feature profile is authoritative for this specification; ideation is not an approved gate, and no system-context diagram is required for this route.
- No source banking data is needed. Synthetic data is sufficient for all portable scenarios.
- Money movement and customer-record changes remain outside this increment and require explicit approval and receiving-project authorization before any future scope expansion.
