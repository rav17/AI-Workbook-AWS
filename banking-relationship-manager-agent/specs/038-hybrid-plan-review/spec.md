# Feature Specification: Hybrid Plan Review

**Feature Branch**: `[038-hybrid-plan-review]`

**Created**: 2026-11-14

**Status**: Draft

**Input**: User description: "First increment only: opt-in hybrid plan stage where the main assistant plans inline and a selected, genuinely independent reviewer reviews the produced plan. Preserve existing profiles, gates and required sensors. Fail explicitly if a required reviewer is unavailable or the review is stale. Keep real call accounting and distinguish invocation result from review verdict. Automated risk-based selection, broader adaptive routing, other harness adapters, changing existing defaults, and deployment/live actions are out of scope."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Opt in to independent plan review (Priority: P1)

A workflow operator opts a run into hybrid plan review and supplies the reviewer selection from the configured review-eligible roster/assignment for that review. The plan author is not eligible. The main assistant produces the plan inline, after which the selected reviewer reviews the produced plan. The operator can tell whether the review invocation ran successfully and what verdict and findings it returned.

**Why this priority**: This is the core value of the first increment: independent scrutiny of a produced plan without changing the existing default workflow.

**Independent Test**: Exercise an opted-in run with a valid reviewer selected from the configured review-eligible roster/assignment. Verify the plan is produced before review; safe evidence identifies the plan revision and actual review input set, excludes author notes and verdict, and agrees with the recorded invocation inputs; and invocation outcome and review verdict are separately visible.

**Acceptance Scenarios**:

1. **Given** an operator opts in and supplies a valid reviewer from the configured review-eligible roster/assignment other than the plan author, **When** the main assistant completes its plan, **Then** that reviewer reviews the produced plan and the operator can see the invocation outcome separately from the review verdict and findings.
2. **Given** review findings are returned, **When** the review is presented, **Then** each finding communicates its severity, relevant plan file or section, freshness (`current` or `stale`), and an actionable next step in plain text.
3. **Given** a reviewer invocation completes but returns a non-approving verdict or findings, **When** the invocation is accounted for, **Then** its actual invocation outcome remains distinct from the review verdict; findings do not make a successfully completed invocation a failed invocation.
4. **Given** the operator omits the reviewer selection or supplies a reviewer not in the configured review-eligible roster/assignment or who authored the plan, **When** required review is due, **Then** the run reports an explicit invalid/missing selection failure and does not invoke a substitute reviewer or continue as though review occurred.

### User Story 2 - Preserve the existing path when not opted in (Priority: P2)

A workflow operator who does not opt in continues to use the existing workflow, with no plan review implied or represented as having occurred.

**Why this priority**: The hybrid path is opt-in only; preserving established workflow behavior and profile defaults is necessary to avoid unintended changes.

**Independent Test**: Exercise a run without opt-in and verify that it follows the existing path and clearly reports that no hybrid review occurred.

**Acceptance Scenarios**:

1. **Given** a run is not opted in, **When** its planning proceeds, **Then** no hybrid reviewer is invoked, the status says that no review occurred, and existing profile, gate, and required-sensor behavior is unchanged.
2. **Given** a run uses an existing profile without hybrid opt-in, **When** its workflow completes, **Then** its existing defaults and human approval requirements remain in effect.

### User Story 3 - Stop safely when required review cannot be trusted (Priority: P3)

A workflow operator receives an explicit failure instead of an apparent completed review when the selected reviewer is unavailable, reviewer independence cannot be established, or the plan changes after review.

**Why this priority**: A required independent review must not be bypassed or represented as current when it did not occur or no longer applies.

**Independent Test**: Independently exercise reviewer unavailability, unestablished independence, and plan revision after review; confirm each case produces an explicit status and prevents continuation through the required-review path.

**Acceptance Scenarios**:

1. **Given** hybrid review is required and the selected reviewer is unavailable, **When** the review is attempted, **Then** the run reports failure and does not substitute a reviewer or continue silently.
2. **Given** the selected reviewer is the plan producer or the separate reviewer assignment/invocation cannot be established, **When** the required review is due, **Then** the run reports failure and does not present the result as independent review.
3. **Given** evidence of the review input boundary is missing, inconsistent with the recorded invocation inputs, or shows author notes or the author's verdict in the supplied review input, **When** required review is due, **Then** the run reports an explicit boundary failure and does not represent the plan as validly reviewed.
4. **Given** the plan changes after a review, **When** the result is considered for the changed plan, **Then** the review is identified as stale and the required-review path does not continue as though the changed plan had been reviewed.
5. **Given** the reviewer invocation succeeds but its result has a missing or malformed verdict or is incomplete, **When** the result is evaluated, **Then** it is identified as an invalid or incomplete review result, does not satisfy required review, and cannot permit silent continuation.

### Edge Cases

- The reviewer invocation fails before returning a verdict: show the invocation failure distinctly; do not imply a verdict was issued or that review passed.
- The reviewer returns findings but no approving verdict: show the actual verdict and findings; do not recast invocation success as review approval.
- The reviewer invocation succeeds but its verdict is missing or malformed, or its result is incomplete: identify the invocation as successful and the review result as invalid or incomplete; do not treat it as a verdict, satisfy required review, or continue silently.
- The plan is revised during or after review: treat a result for a different plan revision as stale.
- The operator omits a selection, selects outside the configured review-eligible roster/assignment, selects the plan author, or no valid selection is available: fail the required path explicitly before review; do not self-review or silently substitute. This increment uses the supplied selection and configured eligible source only; it adds no adaptive or risk-based routing.
- The separately assigned reviewer worker/invocation cannot be verified: fail the required path explicitly.
- Evidence of the review input boundary is missing, inconsistent with the recorded invocation inputs, or shows author notes or verdict were supplied: fail the required path explicitly. Do not infer or claim what the reviewer privately reasoned.
- Review boundary evidence must identify the reviewed plan revision and actual supplied input set using safe artifact/revision references or fingerprints; show author notes and verdict were excluded; and agree with the recorded invocation inputs. Do not record raw plans, prompts, or sensitive content.
- The operator has not opted in: report that no review occurred, rather than a missing or failed required review.
- Review content contains or could contain sensitive customer information: use only minimum necessary context, keep customer data out of logs, audit details, this specification and tests, and use synthetic test data.
- Existing human approval, required sensors, or profile-specific gates apply: hybrid review does not bypass, replace, or weaken them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The hybrid plan-review path MUST be opt-in. A run without opt-in MUST retain its existing workflow behavior and MUST clearly distinguish “no review occurred” from a review result.
- **FR-002**: For an opted-in run, the workflow operator MUST supply the reviewer selection from the configured review-eligible roster/assignment for this review. The plan author is ineligible. Only the supplied selection is used; this increment MUST NOT add adaptive or risk-based selection. If selection is missing or is not in the configured eligible source, the required-review path MUST fail explicitly without invoking a substitute or continuing as though review occurred. The main assistant MUST produce the plan inline before the selected reviewer reviews it.
- **FR-003**: The selected reviewer MUST be a separately assigned worker whose identity differs from the plan-producing assistant, and MUST use a separate invocation to review the produced plan. A safe, observable input-boundary record MUST identify the reviewed plan revision and the actual supplied input set (for example, through safe artifact/revision references or fingerprints), MUST show that author notes and the author's verdict were excluded from the review input package, and MUST be checked against the recorded invocation inputs. If the record is missing, cannot establish the revision or actual supplied inputs, conflicts with the recorded invocation inputs, or shows author notes or verdict were included, the required-review path MUST fail explicitly with a distinct missing, unverified, or inconsistent input-boundary status, without silent continuation. Do not log raw plan/prompt or sensitive content. This observable assignment, identity, invocation, and input-boundary evidence defines the review boundary for this increment; it does not observe or prove the reviewer's private/internal reasoning and does not assert personal, organizational, or model-level separation. If reviewer availability or any required part of this boundary cannot be established, the required-review path MUST fail explicitly without self-review or silent substitution.
- **FR-004**: A review result MUST identify the exact plan revision reference it covers and expose a user-facing `freshness` field. The field MUST be `current` if and only if the covered revision reference exactly matches the revision being considered; it MUST be `stale` when the references differ. No age- or expiry-based threshold applies. A result without a covered revision reference is invalid/incomplete under FR-005. A stale result MUST NOT satisfy the required review or permit silent continuation as though the current plan had been reviewed.
- **FR-005**: The operator-facing result MUST distinguish whether the reviewer invocation succeeded or failed from the review-result status, verdict, and findings. A successful invocation with a missing or malformed verdict, or an incomplete result, MUST be identified as an invalid or incomplete review result; it MUST NOT satisfy required review or permit silent continuation. An invocation that completes with findings MUST be accounted for as a successful invocation even when the verdict is non-approving.
- **FR-006**: For each of these ten status states—successful review, no review, unavailable reviewer, stale review, invalid/incomplete review, missing reviewer selection, invalid reviewer selection, missing review-input-boundary evidence, unverified review-input boundary, and inconsistent review-input boundary—the displayed status MUST have text that distinguishes the state without relying on color. All applicable information MUST be perceivable, including invocation outcome separately from verdict, the failure reason and next step where applicable, and severity, plan location, or freshness where applicable. A keyboard-only user MUST be able to reach and read the status in the normal logical sequence and operate any associated actions in a logical sequence. A screen reader MUST convey the state, applicable information, and available actions. Each state passes only if every applicable text, perceivability, keyboard, and screen-reader check passes; failure of any applicable check fails that state. These checks do not mandate a particular product or assistive-technology brand.
- **FR-007**: Actual assistant and reviewer invocations MUST be counted according to the existing call-accounting rules; counts MUST represent actual invocations and MUST NOT treat a review verdict as an invocation outcome.
- **FR-008**: The hybrid path MUST preserve existing profiles, defaults, gates, required sensors, and human approval requirements. It MUST NOT authorize money movement, customer-record changes, deployment, or live actions.
- **FR-009**: Customer names, account numbers, balances, and other sensitive customer data MUST NOT appear in logs, audit details, this specification, or tests. Tests MUST use synthetic customer data. Plan and review context MUST be limited to what is necessary for the review.
- **FR-010**: Traceability MUST use safe metadata, such as a correlation reference, plan/revision reference, reviewer invocation result, and review verdict as distinct information. Raw plans, prompts, and sensitive reviewer rationale MUST NOT be included in logs or audit details.
- **FR-011**: The first increment MUST NOT define or change retention or access policy for review information; applicable existing approved controls remain in force. Any new or changed retention/access policy is outside this increment.

### Key Entities *(include if feature involves data)*

- **Plan revision**: The particular version of the plan produced inline and submitted for review; identifies which plan content a review result covers.
- **Reviewer invocation**: An actual attempt by the selected reviewer to review a plan revision, with an invocation outcome distinct from any verdict.
- **Review result**: The verdict and any findings for a plan revision, including severity, relevant location, a user-facing freshness field (`current` or `stale`) determined by exact revision-reference equality, and next step where applicable.
- **Correlation reference**: Safe metadata used to associate related plan and review events without including raw plan, prompt, or sensitive customer content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

The evaluation set for this increment is the 21 named acceptance cases below. Cases are evaluated against their stated observable outcomes; A-12 is evaluated as ten separate status-state checks, one for each state it names. For each criterion, the denominator is the count of its referenced cases or state checks, and the numerator is the count that meet the outcome. These are conformance targets for the enumerated acceptance set, not claims about empirical user or production performance.

1. **A-01 — Complete approving review**: An opted-in run produces the plan before a separately assigned reviewer evaluates it; the invocation outcome, verdict, and findings/status are distinct. When the covered plan revision reference exactly matches the revision being considered, the user-facing freshness field is `current`.
2. **A-02 — Complete non-approving review**: A successful invocation with a non-approving verdict and findings remains an invocation success, with verdict and findings separately reported.
3. **A-03 — No opt-in**: No reviewer is invoked or represented as having reviewed a plan; the existing path and profile behavior remain unchanged.
4. **A-04 — Reviewer unavailable**: The required-review path reports failure and does not substitute a reviewer or continue silently.
5. **A-05 — Reviewer is author**: The required-review path reports failure and does not represent self-review as independent.
6. **A-06 — Assignment or invocation boundary unverified**: The required-review path reports failure if a separate reviewer assignment, different identity, or separate review invocation cannot be established.
7. **A-07 — Review input boundary evidence**: Safe evidence identifies the reviewed plan revision and actual supplied input set, shows that author notes and the author's verdict were excluded, and agrees with the recorded invocation inputs. This tests the observable supplied-input boundary, not the reviewer's private/internal reasoning.
8. **A-08 — Stale plan**: When the covered plan revision reference differs from the revision being considered, the user-facing freshness field is `stale`; the review does not satisfy required review for the changed plan. No age/expiry threshold is used.
9. **A-09 — Missing verdict**: A successful invocation with no verdict is identified as an invalid/incomplete review result and does not satisfy required review.
10. **A-10 — Malformed verdict**: A successful invocation with an unusable verdict is identified as an invalid/incomplete review result and does not satisfy required review.
11. **A-11 — Incomplete result**: A successful invocation with an incomplete required review result is identified as invalid/incomplete and does not satisfy required review.
12. **A-12 — Accessible status**: Evaluate each of these ten states separately: successful review, no review, unavailable reviewer, stale review, invalid/incomplete review, missing reviewer selection, invalid reviewer selection, missing review-input-boundary evidence, unverified review-input boundary, and inconsistent review-input boundary. For each state, pass only if (a) text distinguishes it without color, (b) all applicable information is perceivable, including invocation outcome versus verdict, failure reason/next step, and applicable severity/location/freshness, (c) keyboard-only use reaches and reads the status in normal logical sequence and operates associated actions in logical sequence, and (d) a screen reader conveys the state, applicable information, and available actions. Failure of any applicable check fails that state. An evaluation is required for every listed state; none is presumed to pass.
13. **A-13 — Safe records**: Synthetic customer data is used; prohibited records contain no sensitive customer data, raw plan, prompt, or sensitive reviewer rationale, and traceability uses safe metadata.
14. **A-14 — Invocation accounting**: Actual assistant and reviewer invocations are counted under existing rules; a verdict does not alter or stand in for invocation outcome.
15. **A-15 — Review input boundary evidence missing**: If no safe input-boundary record is present, the required-review path reports a distinct missing-boundary status, fails explicitly, and does not continue as though the plan had a valid review.
16. **A-16 — Review input boundary inconsistent**: If the record conflicts with the recorded invocation inputs or shows that author notes or the author's verdict were supplied, the required-review path reports a distinct inconsistent-boundary status, fails explicitly, and does not continue as though the plan had a valid review.
17. **A-17 — Review input boundary unverified**: If a record is present but cannot establish the reviewed revision or actual supplied input set, the required-review path reports a distinct unverified-boundary status, fails explicitly, and does not continue as though the plan had a valid review.
18. **A-18 — Reviewer selection missing**: If the operator supplies no reviewer selection, the required-review path reports a distinct missing-selection status and invokes no substitute reviewer.
19. **A-19 — Reviewer selection invalid**: If the operator selects outside the configured review-eligible roster/assignment or selects the plan author, the required-review path reports a distinct invalid-selection status and invokes no substitute reviewer.
20. **A-20 — Prohibited actions remain unauthorized**: Conformance evaluation confirms the hybrid path does not authorize or initiate money movement, customer-record changes, deployment, or any live action; existing profiles, defaults, gates, required sensors, and human approval requirements remain in force.
21. **A-21 — No new access/retention policy**: Conformance evaluation confirms this increment defines or changes no access or retention policy for review information, and that any applicable existing approved controls remain in force.

- **SC-001**: At least 3/3 cases (A-01, A-02, A-14) distinguish actual invocation outcome from review verdict/result; findings do not turn a successful invocation into a failed invocation.
- **SC-002**: At least 12/12 required-review failure cases (A-04, A-05, A-06, A-08, A-09, A-10, A-11, A-15, A-16, A-17, A-18, A-19) explicitly identify the unavailable, unestablished, stale, invalid, incomplete, missing/unverified/inconsistent-boundary, or missing/invalid-selection condition and do not continue as though a current valid review occurred.
- **SC-003**: 1/1 case (A-03) preserves the non-opt-in path and does not represent review as having occurred.
- **SC-004**: 10/10 state checks in A-12 (successful review, no review, unavailable reviewer, stale review, invalid/incomplete review, missing selection, invalid selection, missing input-boundary evidence, unverified input boundary, inconsistent input boundary) pass each applicable text-without-color, perceivability, keyboard-only access/operation, and screen-reader check. Every state requires its own evaluation; any applicable failed check fails that state, and no state is presumed to have passed without evaluation.
- **SC-005**: 1/1 case (A-13) meets the safe-records outcome using synthetic customer data.
- **SC-006**: 1/1 case (A-07) passes only when safe evidence identifies the reviewed plan revision and actual supplied input set, demonstrates author notes and verdict were excluded, and is consistent with the recorded invocation inputs; it makes no claim about private/internal reviewer reasoning.
- **SC-007**: 1/1 case (A-20) confirms the hybrid path does not authorize or initiate the prohibited money movement, customer-record changes, deployment, or live actions, and preserves existing controls and approval requirements.
- **SC-008**: 1/1 case (A-21) confirms no new or changed review-information access/retention policy is introduced and any applicable existing approved controls remain in force.

## Assumptions

- The workflow operator supplies the reviewer selection from the configured review-eligible roster/assignment for this review; the plan author is excluded. No adaptive or risk-based routing is introduced. “Independent reviewer” here means a separately assigned worker with a different identity and a separate invocation, with safe evidence of the actual supplied review input set and the reviewed revision. It does not assert or prove private/internal reviewer reasoning or organizational, personal, or model-level separation.
- Existing workflow policy continues to govern profile-specific review verdict handling and human approval. This increment reports review verdicts and findings without changing approval authority or existing gates.
- Existing approved access and retention controls, if applicable to equivalent workflow records, continue to govern review information. This increment does not establish a new retention period or access policy.
- The selected reviewer is expected to receive only the minimum context needed to review the plan; no new use of customer-sensitive information is authorized.
- Scope is limited to the first opt-in hybrid plan-review increment. Other harness adapters, changed defaults, live/deployment actions, and new adaptive routing are excluded.
