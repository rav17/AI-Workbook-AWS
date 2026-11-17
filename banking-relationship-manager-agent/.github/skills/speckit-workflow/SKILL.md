---
name: speckit-workflow
description: "Route code changes to a confirmed Spec Kit profile and run its stages inline or through the conductor. Use for code-change requests, direct stage handoffs and resuming work."
---

# Profile-Aware Lifecycle Entry

Run from the receiving Spec Kit project root. Activate the Copilot integration
before invoking Spec Kit skills. Read its constitution when present.
No application/domain policy from the toolkit source is implied.

## 1. Identify the work and confirm the route

Present execution simply as inline, inline with selected workers, or delegated;
`workflow recommend` exposes these choices alongside existing profile presets.
This is presentation only: profile ids, risk assessment, required workers,
gates and initialized routes do not change. Never silently choose a lighter route.

- Distinguish a new work item from explicitly resuming the active feature.
  If that distinction is unclear, ask the user; do not attach a new request to
  whichever feature pointer happens to be active.
- For an explicitly resumed initialized feature, run `python -m speckit_flow resume`
  and preserve its profile. Do not initialize again, infer a replacement route,
  reset completed work or switch without explicit user confirmation.
- After an interruption or context reset, use
  `python -m speckit_flow context --feature-dir <path> --json` for a fresh,
  read-only summary of the route, gate, core artifacts and first five pending
  tasks. Read the relevant source artifacts, dependencies and current diff
  before acting. Checkbox progress is not test evidence or a ready-to-run queue;
  this command never replaces dispatch preflight or human approval.
- For a new work item, run
  `python -m speckit_flow workflow recommend "<request>" --json`.
  If the user named a profile, pass `--profile <id>`. This read-only heuristic
  returns advice, not a decision. Consider the actual intent, not just keywords.
- Ordinary features: recommend `feature`; ordinary fixes: recommend `bugfix`.
  Both use the existing named-agent route. `quick` is an explicit opt-in inline
  alternative, not the default recommendation.
  Security fix: `security-patch`; refactor: `refactor`; infrastructure: `infra`;
  experiment: `poc`; high-assurance delivery: `enterprise`.
- Keyword advice is not a risk assessment. Check the actual code, uncertainty,
  safety, privacy, authorization, regulatory and deployment impact. Do not
  recommend `quick` when those impacts are significant or unknown, or when
  project/plugin policy requires independent specialists. Use a stronger route
  or ask the user. An explicit profile selection still needs confirmation.
- If `quick` is explicitly selected, explain its gate and lack of independent
  review before confirmation.
- Present stages, gates and the reason. **Always ask the user to confirm the
  profile before initialization**, even for an explicit name. If
  `needs_clarification` is true, ask what kind of work it is / which available
  profile to use. Do not silently use `feature`. Never enable plugins to make
  a requested profile available. Suggest `speckit-compose` for a custom route.

The opt-in `selective` profile keeps specification/plan/tasks/implementation
and the specification/plan gates, with inline stage work and an independent
plan reviewer. Show the recommendation's advisory risk signals, explicit worker
assignments and lighter/stronger alternatives. Inspect actual authorization,
privacy, interface, migration, deployment and uncertainty impacts; this is not
a numerical score or an automatic safety assessment. Never lower project-policy
requirements. Confirm all selected workers and the rationale before init with
`--profile selective --confirm-route --route-rationale "<reason>"`.
The profile must explicitly assign every stage. Customize its assignments in
project configuration before confirmation, not during execution. Initialization
freezes and audit-binds the route. There is no silent switch or automatic risk
reroute; if scope or risk changes materially, stop and obtain a newly confirmed
feature route. The special no-tool reviewer belongs only to `hybrid-plan`.

## 2. Establish the feature context

After confirmation, allocate exactly one feature directory using the receiving
project's numbering/template rules from `speckit-specify` (or its explicit user
path). Persist the feature pointer. Do not create a second directory when the
specify stage later runs. Allocation alone is not stage completion.
This bootstrap allows ideation before a spec exists.

Run `python -m speckit_flow init --profile <confirmed-id> --feature-dir <path> --actor agent:workflow`.
If audit exists without state, or initialization fails, stop and report it;
do not overwrite or rebuild automatically.

For `hybrid-plan`, read the [hybrid host procedure](../../../docs/speckit-profiles.md#profiles)
before initialization or invocation. Confirm the exact eligible reviewer and
rationale with `--reviewer`, `--reviewer-rationale`, and `--confirm-route`.
Stop without substitution if named discovery, no-tool enforcement or actual
input-boundary evidence is unavailable. Actor labels are not authentication.
Source and capability approvals are separate human-terminal decisions:
obtain approval before any log access, use only the audit-bound adapter, and
never directly read raw logs or replace/extend the approved source.
Prepare LF-only UTF-8 plan bytes before reservation; pass `review_prompt`
verbatim and preserve the exact result. Never normalize evidence, retry failed
calls or reset budgets automatically. Use the existing `workflow review-result`
command after actual success, run required sensors, and stop at the plan gate.
Follow the reference's [actual-host accessibility checks](../../../docs/speckit-profiles.md#hybrid-review-status-accessibility-checks);
text and unit tests do not establish keyboard/screen-reader acceptance.

## 3. Execute the confirmed route

Use `python -m speckit_flow workflow next --feature-dir <path> --json` for
between-stage decisions. It returns `execute`, `inspect`, `wait`, `recover`,
`await_human`, `parked`, `blocked` or `complete`, each with a reason and next
action. It never advances state, invokes agents or approves anything. Reuse its
returned dispatch brief for an eligible stage rather than rediscovering the
route. A direct-stage entry still uses the explicit dispatch below.
Use its compact readiness report for artifacts, sensor freshness, open questions
and call accounting; ask unresolved questions in a focused batch, up to the
stage's existing question budget. Read full questions when the preview is
truncated. The approval-package skeleton is not a completed review package or
permission to advance. No summary runs checks or establishes host identity.
`wait` refers to a recorded running call, not proof of host liveness; inspect
that existing call instead of launching another.

For `selective`, read [selected-worker execution](../../../docs/speckit-profiles.md#opt-in-selective-execution-and-engine-directives)
before starting. Perform the stage inline with `SPECKIT_INLINE_STAGE=<stage>`
and `agent:workflow`, without a lead or conductor. Reserve/invoke/finish only
assigned supports before inline work, record `workflow calls inline`, then
reserve assigned reviewers and save their actual reviews without author
commentary. Actual invocation outcomes, verdicts and tests remain distinct.
Keep accounting serial and only independent read-only workers parallel.
Completion needs current inline evidence, successful assigned calls, fresh
reviews and sensors. Allow at most one inline revision and one reviewer
follow-up; do not repeat supports. Failed/running calls stop progress.

For interruptions, inspect `workflow recovery --json` using the
[recovery reference](../../../docs/speckit-profiles.md#fail-closed-recovery-inspection).
It never cancels, transfers ownership or replays side effects. Missing workers,
failed calls, timeout or human approval cannot establish safe exclusion.
No Copilot identity/fencing or recovery executor is installed.
Resume advice applies only to an eligible pending stage with no relevant
blockers; normal preflight remains necessary. Advanced watchdog, inventory,
snapshot comparison and revalidation details stay opt-in via
`--approval-package`; they are review evidence, not an executable queue.

Use the dispatch brief already returned by `workflow next`; do not repeat
dispatch for the same operation. For an external direct-stage handoff, run
`python -m speckit_flow workflow dispatch --stage <requested-stage>
--feature-dir <path> --json`. This checks eligibility, not model invocation.

- If complete, report lifecycle completion without redispatch.
- If blocked (pending human gate, parked feature, damaged audit, omitted or
  out-of-order stage, invalid/unavailable agent), stop and explain the blocker.
- If `execution` is `delegated`, choose exactly one coordinator path:
  - **Already running as `speckit-conductor` (including top-level):** execute
    the conductor's one-stage procedure directly. Do not invoke another
    conductor or hand this stage back to this entry skill.
  - **Another host with named conductor and nested-worker support:** invoke
    `speckit-conductor` once with request, feature directory, exactly one stage
    and preflight output. It invokes only the assigned named workers.
  - **Otherwise:** stop once and explain that this host cannot execute the
    delegated route. In Local with nested subagents disabled, select
    `speckit-conductor` top-level; it calls workers directly without nesting.
    Do not enable recursion, repeatedly re-enter the workflow, or substitute
    generic workers or parent-only work.
  Before each
  lifecycle worker call, the conductor must use `workflow calls reserve`, then
  `workflow calls finish` after actual completion. Inspect `workflow calls
  status` on interruption; failures and exhausted budgets stop work. Only a
  human reset or stage redo starts a fresh attempt; never silently retry or
  treat an existing running reservation as permission for a replacement worker.
- The conductor's lead brief contains `SPECKIT_DELEGATED_STAGE=<stage>` and
  explicit lead identity. This is a recursion marker, not an authorization
  token. Only that matching stage lead executes the stage skill body.
- Pass dispatch's absolute `project_root` and `feature_dir` to the conductor.
  Follow its worker execution contract: explicitly root every shell invocation,
  check test-file existence, and preserve the configured worker's no-agent tool
  restriction. Do not substitute a generic task-runner wrapper for custom
  dispatch or infer no nesting from a worker's final summary.

For ordinary delegated work with missing runtime-restriction evidence, retain
the default stop unless the conductor obtains a current `unverified_accepted`
result from `workflow assurance status`, scoped to the explicit feature/stage
and exact host-supplied current host/session identifiers. Follow the conductor's
ordinary-work assurance procedure and present its operational trust limits.
The human personally records acceptance after a separate review package; an
agent never records it, fabricates context or infers it from a profile/plan
approval. The exception changes neither declared permissions nor actual-failure,
gate, review, accounting or recovery checks. It is unavailable to strict hybrid
review, enterprise/security-patch work, custom profiles or tasks requiring
verified isolation. A dispatch `ready` or context-free summary is not acceptance.

For `execution: inline`, the host performs the stage itself, not as a claimed
specialist invocation. Do not invoke the conductor, supports or reviewers by
default. If the user explicitly requests an independent review, use an actual
independent reviewer and report its result or unavailability; never present
the host's own review as independent. Use `agent:workflow` for lifecycle
transitions and sensors. For each stage:

1. If already in progress, inspect artifacts and ask before resuming. Otherwise
   start it with `stage start <stage> --feature-dir <path> --actor agent:workflow`.
   If skipped, report the reason and stop without running the stage body.
2. Load the matching `speckit-<stage>` skill with the feature directory and
   `SPECKIT_INLINE_STAGE=<stage>` in the brief; execute that skill's body
   directly. The marker is a recursion guard, not approval authority. Reuse
   the allocated feature directory. Load relevant stage knowledge and effective
   rules, report conflicts, and record questions without inventing answers.
   Stop for answers when unresolved questions would materially change the plan
   or implementation; do not infer them from silence.
   Consult relevant existing documents before asking; cite settled answers and
   propose inferred answers for confirmation in the normal interaction.
   Planning/implementation reuse the compact, source-fingerprinted project
   practices summary described in `docs/speckit-profiles.md`, without another
   stage, discovery agent or approval gate.
3. Run `python -m speckit_flow sensors run <stage> --feature-dir <path>
   --actor agent:workflow`; required failures at a gated stage
   stop progress until corrected. Report advisory failures and distinguish
   absent checks from passes. Do not repeatedly rerun unchanged failures.
   Then run `stage done <stage> --feature-dir <path> --actor agent:workflow`.
4. Stop at a pending gate and present the review package below. A gate remains
   human-only. Before implementation, present the task breakdown and actual
   verification scope. Run targeted tests covering acceptance criteria and
   regressions; report failures, missing checks and unverified assumptions.

The conductor returns after one stage; the inline host follows the same stage
boundaries. For a full workflow request, repeat
preflight for the next stage only when there is no blocker or pending gate.
For a direct-stage request, return after that one stage; do not continue the route.
Never redispatch a failed or in-progress stage blindly; inspect actual results
and ask whether to resume the interrupted work.
No-progress stop: if a handoff returns without the expected artifact and
lifecycle progress, or asks the caller to invoke the same workflow/conductor
again, report the failed handoff and stop. Do not spend another worker call
repeating it; require human direction after fixing the brief or host setup.

For a standalone read-only review request, do not initialize or advance a
lifecycle merely to review. Handle a small review directly; delegate only if
independence is required or the evidence needs substantial separate context.
An informal review is not source-bound lifecycle gate evidence.

## 4. Human decisions and resume

Before every human approval request (including profile, stage, verification,
scope-change and learned-rule decisions), present a readable review package in
chat **before** opening the approval form. Do not substitute links only inside
the form, a completion claim, or the conductor/subagent's status message.
The host presenting the gate owns this user-facing handoff.

Each package must include:

- **Decision and scope**: feature, profile/stage where applicable, the exact
  decision requested, and whether work is proposed, implemented or verified.
- **Reviewable work**: plain-language summary of the proposal or changes since
  the last review; direct workspace links to existing artifacts and relevant
  code/diffs. Summarize key contents so the user need not discover the plan or
  deliverables by opening an unexplained list of files.
- **Evidence**: actual independent review verdicts and unresolved findings,
  sensor outcomes, and relevant verification commands/results. Distinguish
  passed, failed, skipped, not run and not configured. Empty sensor results
  prove no checks; synthetic measurements do not prove production accuracy.
- **Risks and boundaries**: open questions, assumptions, deferred requirements,
  deviations, limitations and any proposed exception to a failed check.
- **Authorization**: exactly what approval allows next, what remains excluded,
  and options to approve, request changes or pause. Do not bundle unrelated
  authorization or infer approval from silence.

Tailor the contents to the decision:

| Decision | Required review contents |
|---|---|
| Profile or route | Classification rationale, stages, gates, alternatives and initialization scope. |
| Ideation or specification | Problem, user journeys, requirements, acceptance criteria, exclusions and unresolved questions, with artifact links. |
| Plan | Architecture and design choices, diagrams where applicable, affected interfaces, data/storage and safety boundaries, proposed policy/fixtures, exact verification commands and deferred scope. |
| Before implementation | Task breakdown and dependencies, task-list link, intended code surfaces, acceptance mapping and approved verification scope. Present this even if tasks/analyze have no separate human gate; do not invent a gate or request redundant approval unless the route or a scope change requires it. |
| Implementation or construction checkpoint | Delivered changes linked to tasks/code, actual test counts and failures/skips, review findings, demo evidence, remaining work and limitations. |
| Deploy or operate | Target environment, concrete actions, release/runbook links, readiness evidence, rollback/recovery and operational risks. Local acceptance does not authorize live-resource changes. |
| Verification, scope change or learned rule | Exact commands, changes or rule text, rationale, impact, supporting evidence and the specific authorization requested. |

Inspect the referenced artifacts and ensure review/sensor evidence matches their
current versions before presenting the package. Disclose missing evidence; do
not request approval for missing artifacts or proceed past required failed
checks. Refresh stale reviews/sensors rather than reusing an outdated pass,
subject to the conductor's bounded review policy; stop for user direction when
the automatic review budget is exhausted.
Provide the relevant links again when fixes materially change a reviewed
artifact; show what changed instead of repeating an unexplained approval form.

After presenting the package, ask the human to approve/request changes/pause;
record only the decision they actually made and its disclosed scope.
For a rejected gate, explain `redo` and wait for an explicit human instruction.
Re-run stale sensors/reviews before approval within that budget, or wait for
user direction. Agents never supply `human:` actors
without that actual user decision, or approve verification/learned rules.

Use `/speckit-workflow resume` after a human decision or interruption. An engine
workflow run is a **session**, not proof the feature completed; check lifecycle
status. Do not auto-resume an old static four-stage engine cursor under this new
workflow. No deploy/operate profile authorizes commands against live resources.
