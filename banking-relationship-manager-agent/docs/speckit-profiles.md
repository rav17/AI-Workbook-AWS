# Spec Kit Workflow Profiles, State and Audit

Inspired by [AI-DLC](https://github.com/awslabs/aidlc-workflows), the Spec Kit workflow supports profiles that tune the stage route, depth and approval gates per kind of work. Each feature also keeps a persistent state file and a tamper-evident audit trail.

To reuse the toolkit outside this application, follow the
[portable setup guide](./speckit-portability.md). It installs neutral defaults
without copying this project's constitution, banking knowledge or test commands.

## Everyday workflow

Start with `/speckit-workflow <request>`. The
[canonical entry skill](../.github/skills/speckit-workflow/SKILL.md) owns the
procedure; this guide explains capabilities and advanced commands.

1. **Confirm the route.** Review stages, gates and selected workers. Inline,
   selected-worker and delegated are execution presentations, not risk rankings.
   Existing profile defaults and initialized routes remain unchanged.
2. **Follow `workflow next --json`.** Read the current stage, next action,
   required artifacts, outstanding questions/checks and worker assignments.
   Reuse its dispatch brief; do not run a second discovery for the same handoff.
3. **Do one stage and validate it.** Use the confirmed execution path and
   actual tests/sensors. Invocation success, review verdict, freshness and human
   approval are different evidence. Missing checks never mean passed checks.
4. **Present the review package and stop at gates.** Show scope, artifact links,
   actual results, unresolved risks and exactly what a decision permits.
   Before implementation, show tasks and verification scope even without a
   separate tasks gate. Only actual human decisions authorize advancement.
5. **On interruption, inspect first.** Context restores the work summary;
   recovery inspects evidence. Neither starts workers, approves gates or
   establishes ownership. Never blindly redispatch an in-progress stage.

Requirement-linked tasks are normal; units, diagrams and extra artifacts are
conditional on real coordination needs or confirmed policy. Load relevant
rules/knowledge and batch unresolved questions within existing budgets.
Do not activate plugins, introduce specialist calls or create duplicate unit
records just to follow this walkthrough.

Advanced references:
[named-worker accounting](#named-agent-host-setup-and-bounded-execution),
[selected-worker execution](#opt-in-selective-execution-and-engine-directives),
[recovery inspection](#fail-closed-recovery-inspection), and
[portable setup](./speckit-portability.md).
Hybrid source/capability procedures are in [Profiles](#profiles); read them
before choosing that route. Actual host capability cannot be inferred from
editor settings or a roster entry.

## Consolidation scope and capability status

This inventory describes existing AI-DLC-inspired mechanisms, not a promise
of parity with every upstream stage or harness.

| Capability | Current status and simplified use |
| --- | --- |
| Profiles, depth, ceremonies and custom routes | Implemented; existing presets and confirmation preserved, no new default or automatic reroute |
| Stages, optional research/clarification/deploy/operate | Implemented; show only the confirmed route, not every available stage |
| Named roster, conductor and selective workers | Engine implemented; verify actual discovery/tool enforcement, or use the explicitly human-accepted ordinary missing-proof exception below; never claim certification from acceptance |
| Navigation, context and dispatch | Implemented; next for navigation, context for interruption, dispatch for eligibility |
| Reviews, bounded accounting and exact hybrid results | Implemented; actual invocation and source-bound review remain separate |
| Human gates and approval packages | Implemented; one presentation contract, distinct lifecycle/source/verification decisions |
| Sensors, stage contracts and freshness | Implemented; one checklist, separate safety/domain validators |
| Questions and interaction modes | Implemented; ask unresolved questions in bounded batches |
| Tasks, traceability and construction units | Implemented; units only when checkpoint/dependency coordination or policy warrants them |
| Rules, knowledge, learning and project practices | Implemented; relevant guidance only, existing precedence and approvals |
| Codebase analysis, diagrams and optional artifacts | Implemented as conditional guidance/packs; structure is not semantic correctness |
| Plugins and operational readiness | Implemented; all six packs remain disabled here; installation grants no deployment authority |
| Durable state, audit and session controls | Implemented; summaries remain projections, not another authoritative store |
| Recovery inventory, watchdog, snapshots and review plan | Inspection foundation implemented; details remain opt-in and never authorize execution |
| Host identity/fencing and safe recovery continuation | Not implemented; portable observation contracts are not enforceable exclusion |
| Human-confirmed in-place risk rerouting | Deferred; confirmed frozen-route restrictions remain in force |
| Clean live-host and keyboard/screen-reader acceptance | Validation pending; synthetic tests do not establish these results |
| Portability and documentation | Implemented; neutral exports, one canonical procedure and advanced references |

Consolidation is restricted to shorter ordinary guidance and reuse of
operation-local inspection results. No new profiles, commands, dashboards,
report types or route migrations are added. Independent source/gate checks
and beginning/end snapshot fingerprints remain separate; there is no persistent
inspection cache. Validate inline, selected, delegated, pending-gate,
failed/running-call, invalid-evidence and receiving-project scenarios before
claiming compatibility. Clean live acceptance remains a separately approved
activity, not part of this code consolidation.

## Profiles

Profiles are JSON files in `.specify/profiles/`. Add a team profile by dropping in a new file; the `id` must match the filename.

| Profile | Stages | Depth | Gates |
|---|---|---|---|
| `feature` (legacy CLI default) | specify, plan, tasks, implement | standard | specify, plan |
| `quick` (explicit inline opt-in) | specify, plan, tasks, implement | minimal | tasks |
| `enterprise` | all six stages | comprehensive | every stage |
| `express` | specify, tasks, implement | minimal | specify |
| `bugfix` | specify, tasks, implement | minimal | specify |
| `refactor` | specify, plan, tasks, implement | minimal | plan |
| `infra` | specify, plan, tasks, implement | standard | plan |
| `security-patch` | specify, tasks, implement | minimal | specify |
| `poc` | specify, implement | minimal | none |
| `full-lifecycle` | ideation through operate | standard | ideation, specify, plan, implement, deploy |
| `hybrid-plan` | specify, plan, tasks, implement | standard | specify, plan |
| `selective` | specify, plan, tasks, implement | standard | specify, plan |

`hybrid-plan` is opt-in and does not change any existing profile. Initialize it
only after presenting and confirming the selected eligible plan reviewer and
the selection rationale:

```powershell
python -m speckit_flow init --profile hybrid-plan --reviewer hybrid-plan-reviewer `
  --reviewer-rationale "Independent review of the plan" --confirm-route `
  --feature-dir <feature-dir> --actor agent:workflow
```

The confirmed selection is stored in the feature-local route file and bound to
the profile-selection audit event. Dispatch exposes only that reviewer for the
plan stage; there is no invented inline-lead call. Actor labels and call records
are audit evidence, not authentication.

Without a selected host evidence source, hybrid plan dispatch returns
`status: blocked` (CLI exit code 1), and call reservation refuses the stage
without consuming a call budget. Stop once; do not retry or invoke workers.

The opt-in `copilot-events-v1` adapter reads the actual local Copilot session
log. After a human approves that source, register it once for the feature:

```powershell
python -m speckit_flow workflow host-evidence --events-file <events.jsonl> `
  --feature-dir <feature-dir> --actor human:<operator>
```

The actor label records an actual human decision; it does not authenticate it.
Before opening the log, identify its absolute path and session identity from
host metadata, present the scope and retention limits, and obtain actual human
approval. To persist this decision without reading the source, the human runs:

```powershell
python -m speckit_flow workflow host-consent --events-file <absolute-events.jsonl> `
  --session-id <current-session-id> --feature-dir <feature-dir> --actor human:<operator>
```

Then run `host-evidence` for the same path. If the consent includes a session id,
the adapter validates it against `session.start` and rechecks it before reuse.
For compatible older callers, a human `host-evidence` invocation records consent
before its first source read; existing configured sources are not migrated.
New configuration requires its current audit-bound consent; removal or mismatch
fails closed. Header matching is operational provenance, not host authentication.
The guard refuses source/capability decisions through agent tools and direct
agent reads of recognizable raw Copilot session-log paths. Humans run decisions
in their terminal. The hook is a backstop, not a shell sandbox or proof against
arbitrary concealed reads; host guidance and approval discipline still matter.

Registration is audit-bound, cannot silently replace an existing source, and
does not copy conversation contents into the feature. Retain the source under
existing approved access/retention policy: deleting or rotating away required
events makes verification fail rather than extending retention automatically.

The hybrid-only `speckit-hybrid-plan-reviewer` declares `tools: []`. The
existing architecture reviewer retains its tools and is blocked for hybrid
planning; the engine never substitutes it or alters a confirmed selection.
An empty declaration alone is not proof of enforcement. The host must discover
the new named agent and a human must separately approve one synthetic capability
test. Invoke that agent synchronously with the exact prompt
`Reply exactly: hybrid no-tool capability check`, and inspect the host event log
for the actual call ID. The host must record the selected named worker with an
empty tool list, zero worker tool calls, and successful completion. After an
actual human decision to accept that evidence, record it for the feature:

```powershell
python -m speckit_flow workflow host-capability --call-id <host-call-id> `
  --feature-dir <feature-dir> --actor human:<operator>
```

Dispatch remains blocked without that evidence, with a reviewer that declares
any tools, or when the recorded capability source cannot be revalidated.
The host's tool list and call records are operational evidence, not proof
against a compromised host or a guarantee that future enforcement cannot change.
Each actual review invocation is also checked for an empty host-selected tool
list and zero observed worker tool calls. Do not retry an unsafe worker
automatically. Discovery, empty-list semantics and host enforcement must be
tested in the intended host before enabling this route in practice.

For an in-progress plan, reserve the selected reviewer once. Invoke its named
agent synchronously using the returned `review_prompt` verbatim, without
additional user context. The prompt contains only a correlation reference,
fixed review instructions and the exact plan. Do not edit the plan while the
review runs. Record the actual call outcome with `workflow calls finish`, then
save the returned review JSON using `review save plan --file <result.json>
--host-call-id <actual-host-tool-call-id>`. These commands also need the feature
directory and appropriate actor.

Before reservation, `plan.md` must be nonempty UTF-8, at most 1 MiB, with LF-only
line endings and the existing contract file safeguards (regular, feature-local,
no symlink/reparse point). CR/CRLF input fails before a reservation event is appended; the
engine does not rewrite it. Explicitly correct a new plan before trying again.
Existing reservations retain their original byte fingerprint and prompt.

For a successful actual invocation, the host can replace separate finish,
result extraction and save commands with:

```powershell
python -m speckit_flow workflow review-result --reservation-id <reservation-id> `
  --call-id <actual-host-call-id> --feature-dir <feature-dir> --actor agent:workflow --json
```

It correlates the approved source with the selected current reservation,
records actual success if still running, and saves the exact observed JSON.
It never invokes a model, retries, normalizes evidence, runs sensors or advances
a stage. Invalid output can leave a successful call with a missing review;
that is explicitly blocked, not rolled back or given another call budget.
If interrupted after finishing, the same command may save an existing unsaved
result; already saved results are refused rather than duplicated.

New reservations include a versioned output contract in the generated prompt:
finding severities are `info`, `warning`, `major`, or `blocker`; verdicts are
`pass`, `concerns`, or `block`. A blocker requires `block`, `pass` cannot contain
major/blocker findings, and only `pass` permits empty findings. Every finding
must cite `plan.md` and a nonblank section, with a nonblank note of at most 500
characters. Existing reservations retain their original prompt for exact input
revalidation; do not rewrite them to adopt the new contract.

Invalid output, including severity `medium`, remains rejected. Preserve the
exact returned result and failed feature; do not translate severities, reset the
call budget, or reuse its evidence for a replacement acceptance test. A fresh
disposable test needs separate human confirmation of its route, capability test,
and exact current-session event source. Its plan must state how source provenance
and relevance will be checked: approved absolute path and session identity,
current-session call/worker correlation, and revalidation at completion and gate.
These checks do not authenticate the host or extend approved log retention.

The adapter verifies the recorded named-worker invocation, matching child user
input, host-expanded input, zero observed worker tool calls, worker completion,
successful host call, and actual returned JSON. The only allowed user-input
expansion is the observed Copilot `<current_datetime>` timestamp wrapper;
missing expansion records or any other additional user text fail closed.
It binds the reservation to the plan's byte fingerprint and re-reads the source
at stage completion and again at the human gate. Missing, stale, inconsistent,
failed or malformed evidence cannot satisfy review. A successful call alone
is not a passing verdict. Existing human block-override and sensor policies
remain in force.

After reservation, running/failed calls or a missing saved result return
`blocked`; the next action is to wait, recover under human direction, or save
the existing result, never automatically invoke another reviewer. Source
verification errors stop explicitly. A human-directed reset is not evidence
and cannot substitute for a fresh invocation and current plan review.

These are local operational records, not tamper-proof authentication or proof
of the host's tool permissions, private reasoning, or entire internal model
context. The adapter verifies the exposed invocation/child-user-input boundary;
normal host and named-agent system instructions remain host-managed. A real
named-reviewer smoke test established the available event shapes and timestamp
wrapper. This does not claim an end-to-end live plan-gate acceptance test or
keyboard/screen-reader acceptance; those remain separate checks.

### Hybrid review status accessibility checks

Plain-text dispatch includes the review state, invocation outcome, verdict,
freshness, reason, next action, and any verified finding severity, plan location,
and note. A stale review displays its recorded verdict and findings without
revalidating them; they do not apply to the current plan. During quick-profile
planning, dispatch reports `no_review` when no saved plan review file is
available; this is not evidence about past or unrecorded activity and does not
block the route. A blocked hybrid status exits with code 1. Errors before
initialization and host-evidence verification also report a reason rather than
implying success.

The ten text status identifiers are `review_current` (successful review),
`no_review`, `reviewer_unavailable`, `stale_review`,
`invalid_incomplete_review`, `missing_reviewer_selection`,
`invalid_reviewer_selection`, `missing_input_evidence`,
`unverified_input_evidence`, and `inconsistent_input_evidence`.
Selection failures are shown during hybrid initialization; review and boundary
states are shown by workflow dispatch. Each state includes a reason and a next
action. Invocation outcome, verdict, and freshness are separate fields; when
no invocation or valid verdict exists, output explicitly says
`not_recorded` or `not_available`. Status output and audit details must not
include raw prompts, plans, or sensitive customer data.
Plain-text output includes both the stable status identifier and a descriptive
label, so the state remains understandable without color or internal-code
knowledge.

For each state below, exercise it in the actual host using synthetic data.
Record text distinguishability without color; perception of applicable outcome,
verdict, reason, action, severity, location and freshness; keyboard-only reading
and operation in logical order; and screen-reader announcement of status and
actions. Mark the state passed only if every applicable check passes. A unit
test or printed text is not proof of keyboard or screen-reader behavior.

| State | Actual-host accessibility result |
|---|---|
| Successful review | Not verified |
| No review | Not verified |
| Reviewer unavailable | Not verified |
| Stale review | Not verified |
| Invalid/incomplete review | Not verified |
| Missing reviewer selection | Not verified |
| Invalid reviewer selection | Not verified |
| Missing input-boundary evidence | Not verified |
| Unverified input boundary | Not verified |
| Inconsistent input boundary | Not verified |

Rules enforced by validation: `specify` is first (optionally after `ideation`), stages are in canonical order (`ideation, specify, clarify, plan, tasks, analyze, implement, deploy, operate`), `implement` needs `tasks` unless the profile declares `implement-without-tasks`, `deploy` needs `implement`, `operate` needs `deploy`, and every gate must be a stage in the route. Schema: `specs/009-workflow-profiles-audit/contracts/profile.schema.json`.

On `full-lifecycle`, the stage leads use `.github/skills/speckit-diagrams/` to
create applicable, feature-local draw.io views under
`<feature-dir>/architecture/diagrams/`. The skill maps context, overview,
component, interaction, deployment, and operations views to lifecycle stages
and maintains an `index.md` with applicability and source references. Named
cloud services use the matching provider/service icon and readable service
label; unselected services remain neutral shapes. It does not require every
view for every feature. After creating or changing diagrams, run
`python -m speckit_flow diagrams validate --feature-dir <feature-dir>`; this
checks XML and graph references, not icon identity or architecture correctness.

## Named-agent host setup and bounded execution

The outer AI-Workbook-AWS workspace points `chat.agentFilesLocations` at this
project's `.github/agents` directory. This is an editor discovery setting, not
proof that a running session can invoke those agents. Copilot CLI does not
inherit editor search-location settings.

For the Local VS Code harness, open
`banking-relationship-manager-agent.code-workspace`, start a new Local session,
and select `speckit-conductor` as the **top-level** agent. That workspace disables
subagent-to-subagent invocation. The conductor can call its allowed workers
directly without an extra host -> conductor -> worker nesting layer.
Do not invoke the conductor as a subagent in this configuration.

There is one delegated routing decision: an already active conductor runs its
one-stage procedure directly; another host invokes the named conductor once only
when nested-worker invocation is available. Otherwise stop and explain the host
limitation. A worker executes its stage body only with the matching active brief;
a missing/conflicting marker stops the worker instead of handing back to workflow.
The always-on instructions, workflow prompt and stage skills follow this same
rule. This retains the existing AI-DLC-inspired named roles, supports, independent
reviews and profile gates; it does not introduce a built-in-agent adapter.

Before feature work, request one read-only smoke test: invoke
`speckit-product` once to read `.specify/profiles/feature.json` and report its
stages and gates. It must not edit files, run lifecycle transitions, call other
agents, or retry. Inspect tool activity for the actual named worker invocation
and its restricted tools. Profile recommendation and dispatch eligibility are
not invocation evidence. If discovery, invocation, or tool restrictions fail,
stop and report the host limitation; do not substitute a generic worker.

### Worker tool compatibility diagnostics

Separate declared configuration, observed capability failures and unavailable
runtime evidence. Custom-agent `tools` lists declare available tools; the host
may apply the profile without exposing a per-call override parameter.
Missing per-call tool overrides alone do not prove unsupported restrictions.
An unavailable diagnostic is not an observed enforcement failure.

If named-worker selection fails or forbidden delegation is observed, stop and
describe the actual failure without generic substitution.
If required enforcement remains unverified, stop unless the scoped ordinary-work
exception below returns `unverified_accepted`; otherwise identify the missing
evidence, the host/harness and the configured worker. Report **unverified**, not
**unsupported** or **verified**; absence of a known failure is not permission
to continue. Retain the smoke test and existing enforcement requirements.

No observed nested calls does not prove that nesting was unavailable.
Static contract tests are not live-host enforcement evidence.
A declared allowlist, successful discovery, final worker summary or passing
dispatch check alone does not establish runtime permissions. This guidance
neither certifies this session nor automatically unblocks another feature.

#### Explicit ordinary-work assurance acceptance

The default missing-evidence stop remains. For ordinary work on `feature`,
`bugfix`, `refactor` or `selective`, a human may separately accept this limitation
for one current stage, host/session and configured named-worker scope.
Hybrid no-tool review, enterprise/security-patch, unknown/custom profiles,
deployment/operations and tasks requiring verified isolation are ineligible.
Profile names alone do not establish that work is ordinary.

Before asking, show the feature/stage, assigned workers and declared restrictions,
host/session metadata source, actual observations, missing evidence and residual
risk. The human personally runs this decision in the project terminal:

```powershell
python -m speckit_flow workflow assurance accept --feature-dir <feature> --stage <stage> `
  --host <host-label> --session-id <current-session> --reason "<short rationale>" `
  --observation "<sanitized observation>" --confirm-ordinary-work --actor human:<operator>
```

Host/session identifiers are limited to 24/64 characters, rationale/observation
to 60 each, and the complete redacted audit detail to 500 characters. Sensitive,
missing or oversized inputs are rejected rather than truncated. The event
retains the disclosed missing evidence and risk, not raw logs or tool output.

Before worker reservation, the host checks:

```powershell
python -m speckit_flow workflow assurance status --feature-dir <feature> --stage <stage> `
  --host <host-label> --session-id <current-session> --json
```

Only a current `unverified_accepted` result permits passing the missing-proof
condition; report `unverified: human accepted`, never verified isolation. Other
statuses exit 1 with a reason; invalid input/evidence fails explicitly.
Dispatch/next summaries without current context are non-authorizing and report
context checking required, not a valid current exception.

Use the exact current session identity supplied by host metadata (the SDK
conversation identity for Copilot SDK), not a guessed/newest log directory or a
different protocol/history id. Missing current metadata remains a stop.
Identifier equality checks only disclosed/attested context, not authenticated
identity or independently detected host changes. Actor labels and the hook are
operational controls; they do not authenticate a human against arbitrary local
processes or a compromised host.

Changed stage, host/session, worker definitions or a redo/reset invalidates the
acceptance. A normal pending-to-started transition does not. No acceptance
changes routes, approves a gate, excludes a worker, resets calls, starts/resumes
work, grants source consent or overrides a known capability failure. Actual
selection failures, forbidden delegation, failed/running calls, review and
verification requirements remain stops. Generic substitution is never allowed.
Existing features such as 039 require their own decision after this mechanism
is delivered; completing feature 041 does not accept or resume them.

See the [GitHub tool configuration reference](https://docs.github.com/en/copilot/reference/custom-agents-configuration#tools)
and [VS Code harness-specific tool guidance](https://code.visualstudio.com/docs/agents/reference/custom-agent-file-reference#tools).
Those references describe supported configuration, not this session's effective
tools. Do not assume adding `strict-tools-list` fixes VS Code agent conversion;
review its [documented conversion limits](https://code.visualstudio.com/docs/agents/reference/custom-agent-file-reference#copilot-specific-configuration).

For a confirmed feature route, keep one stage in flight, parallelize only
independent assigned supports/reviewers, keep writable outputs disjoint, and
return concise evidence instead of repeating discovery. Preserve the conductor's
existing limit of one automatic revision and one follow-up review per reviewer
per stage attempt. Stop on failure, stale evidence after that budget, missing
host capabilities, or a pending human gate. Do not retry by starting another
conductor or resetting the stage.

The Local harness setting prevents nested subagents. Other harnesses can behave
differently. Persisted lifecycle call accounting adds the following commands
(include `--stage <stage> --feature-dir <path>` on each):

| Command | Purpose |
|---|---|
| `workflow calls reserve <agent-id> --actor agent:conductor --json` | Reserve before an actual worker call; returns its numeric audit event id |
| `workflow calls finish <id> --outcome succeeded\|failed --actor agent:conductor` | Record the actual invocation outcome, not the review verdict |
| `workflow calls status` | Inspect the current attempt without consuming a call |
| `workflow calls reset --reason "<reason>" --actor human:<name>` | Human-only fresh attempt, preserving all earlier audit events |

Per stage attempt, each assigned domain support gets one call, the lead gets
two (initial plus one revision), and each assigned reviewer gets two (initial
plus one follow-up after the revision). Only assigned agents on an in-progress
delegated stage may reserve. Supports precede the lead; reviews follow successful
lead work; revision waits for the initial reviews. Independent supports/reviewers
may run in parallel, but reserve and finish serially. Never run other
audit-writing lifecycle commands concurrently with accounting commands.

Reservations and results persist in the existing hash-chained audit; restarts
and repeated preflight do not reset budgets. An exclusive `.calls.lock` rejects
concurrent accounting mutations without waiting/retrying. Do not automatically
remove an abandoned lock: a human must inspect concurrent processes first.
Failures block further reservations. A running reservation cannot be reused or
reset: stop the actual worker and record it failed before a human resets the
attempt. Human-directed stage redo also starts a fresh attempt.
For stages using reservations, completion rejects running/failed calls or
missing assigned worker results. After a lead revision, assigned follow-up
reviews must complete before stage completion. A handoff that returns to the
same workflow without expected output/progress is a failed invocation: stop,
do not relaunch the conductor or worker. Legacy stages without any reservations retain
their previous completion behavior.

These are enforced bounds on **recorded lifecycle calls**, not a host tool
interceptor, authentication system, timeout, or process watchdog. Actor labels
are workflow attribution, not proof of identity. The guard blocks agent reset
commands where installed; workers and the conductor must still respect their
tool restrictions. A host that bypasses reservations can still launch agents;
the engine neither launches nor cancels them. A completed review with findings
is a successful call; its independent verdict remains separate gate evidence.
Do not claim universal loop prevention, named-agent execution, or faster delivery
from ledger tests. Benchmark completed feature elapsed time and actual call
counts before making performance claims.

## Commands

### Optional walking-skeleton checkpoint

The disabled `walking-skeleton` plugin adds an optional developer-led stage
before implement, after tasks/analyze. Profile `skeleton-first` runs specify ->
plan -> tasks -> walking-skeleton -> implement, with human gates after specify,
plan and walking-skeleton. Quality supports the skeleton stage. A human enables
the pack, restarts the session/CLI, validates plugins and selects that profile.
Default profiles and the nine core stages remain unchanged; use the profile-aware
workflow entry to confirm this route and invoke the conductor.

Follow `speckit-skeleton`: define a thin journey with exact input/output, real
entry/application/output boundaries, task references and explicit mocks/limits.
Create feature-local `skeleton.md` and actual source/acceptance tests. Define
reserved unit `walking-skeleton` with `units add ... --tasks T001,T002 --files
<source>,<test>,<feature>/skeleton.md,...`. The human must approve the receiving
project's actual verification command; the pack/installer grants no approval.

`units add --files` is optional for any construction unit. Paths are root-relative
and normalized from Windows separators to `/` in metadata. At most 100 unique
files, <=1 MiB each; traversal, drive paths, aliases, symlink/reparse ancestors,
non-regular/missing files and access errors fail explicitly. Checkpoints for
tracked units snapshot hashes before/after approved verification. File, unit
definition or command changes during verification fail. Failed rechecks invalidate
prior success before attempting validation, including policy/access errors, for
tracked and untracked units. Adding later units preserves unrelated checkpoints.
Untracked units remain supported with explicitly command-only coverage; their
evidence is now bound to definitions, approved commands and dependency revisions.

The profile-scoped `skeleton` builtin requires actual task references, at least
three tracked files including the feature's report, and current passing evidence
for the reserved unit against default `.specify/verify.json`. Custom unit CLI
verify paths do not satisfy this sensor. File/definition/command changes need
a fresh checkpoint. Run stage sensors after checkpointing; gate freshness covers
units metadata, verify policy, tracked files and existing lifecycle artifacts.
The sensor and gate do not execute verification commands.

**Humans judge whether the slice is genuinely end-to-end.** File count, a passing
command and a report do not prove architecture, full-feature coverage or live
integrations. Only declared files are source-bound: include fixtures/dependencies/
configuration as needed. Later full implementation may intentionally change the
slice; recheckpoint when relying on that evidence again. No deployment, live
services, domain policy or application generator is included.

### Optional operational readiness

The disabled `operational-readiness` plugin adds profile `release-ready`:
specify -> plan -> tasks -> implement -> deploy -> operate. It reuses existing
stages and agents; human gates apply after specify, plan, implement, deploy and
operate. A human enables its manifest, restarts the session/CLI, validates the
plugin and chooses the profile through the profile-aware entry.

At deploy, pipeline-deploy follows `speckit-readiness` to prepare feature-local
`release.md` and `runbook.md` from the pack's templates. Operations updates both
for the operate handoff. Preserve existing records; never overwrite completed
evidence with templates. The conductor passes the skill/records to the leads,
collects sensor results and stops for human review.

Release sections: **Ownership and target**, **Configuration**, **Verification**,
**Rollout**, **Rollback**. Runbook sections: **Ownership**, **Health signals**,
**Alerts**, **Incidents**, **Rollback**, **Feedback**. Each needs an exact
level-two heading, substantive content and a standalone `- Evidence: ...` line.
Keep planned/executed/failed/untested work distinct; non-applicability needs a
reason and human reviewer/reference. No test or operational outcome is invented.

`python -m speckit_flow sensors run deploy` (or `operate`) runs the required
profile-scoped readiness builtin. Missing content/evidence, common placeholders,
unchecked tasks, duplicate sections and comment/code-only evidence fail.
Records must be regular non-symlink/reparse-point UTF-8 files of at most 256 KiB.
Access errors are surfaced. No referenced command, URL or file is executed/read.

Passing readiness results fingerprint both records plus the existing
spec/plan/tasks artifacts; edits/deletion require rerunning checks before a human
gate can be approved. Other sensors keep their existing fingerprint scope.
External evidence is not fingerprinted: prefer immutable/versioned references
and revalidate it manually when it changes.

**A pass validates record structure, not truth, live health or deployment
authorization.** Human reviewers decide evidence quality and acceptable risks.
The pack deploys nothing, runs no live probes and grants no verification approval.
It is provider/domain neutral and ships disabled in the portable toolkit.

### Optional existing-codebase analysis

The disabled `codebase-analysis` plugin adds an architect-led analysis stage
between specify and clarify/plan and a `brownfield` profile. A human enables its
`plugin.json`; restart the CLI/session and validate plugins/profiles before
selecting the route. Default profiles and the nine core stages are unchanged.
Use the profile-aware entry and conductor flow for this route.

`python -m speckit_flow codebase scan [--json]` provides a read-only path inventory,
even when the pack is disabled. The conductor passes it to the architect, who
follows `speckit-codebase` and writes feature-local `codebase.md` covering
architecture, dependencies, interfaces, tests, impact and unknowns. Planning
consumes that evidence and rechecks it against changed code. No test/build
command is executed by scanning; discovered tests are not passing-test evidence.

Applicability is deliberately heuristic: recognized source extensions include
Python, JavaScript/TypeScript, Java/Kotlin, Go, Rust, .NET, C/C++, Ruby/PHP,
Swift, Scala, functional languages, Dart, Vue/Svelte, SQL, Terraform and shell.
Other extensions (including YAML-only infrastructure) may yield a false
greenfield result; perform manual scoped analysis when needed. Manifests alone
do not establish existing application source; recognized test files do.
The exact extension and manifest lists live in `speckit_flow/codebase.py`.

The scanner excludes dependency/build/cache directories, virtual environments,
toolkit metadata (`.specify`, `.github`, `.claude`, `.kiro`, `.agents`), root
`speckit_flow`, `specs`, `graphify-out`, and the three installed Spec Kit Python
scripts; other application scripts remain visible. Exclusion names apply at
any depth except the three explicitly root-only directories. Symlinks and
Windows reparse points/junctions are not traversed. File contents are never
opened. Listing/stat failures and more than 10,000 examined filesystem entries
produce errors, not a greenfield result. This checks inventory access, not
whether every source file's contents are readable.

With no recognized sources, `stage start codebase-analysis` records
`stage_skipped`, saves its reason and advances. Ordering, parked state and
pending human gates are checked first. Conditional stages must be optional and
cannot be approval gates. The conductor must not dispatch agents or call done
for a skipped stage. No general-purpose skip command is introduced.

Run from the repository root with `python -m speckit_flow <command>`; `--feature-dir` defaults to the directory in `.specify/feature.json`.

| Command | Purpose |
|---|---|
| `profiles list / validate [id] / suggest "<text>"` | Inspect profiles; suggestion is advisory |
| `init --profile <id>` | Create state, mark omitted stages skipped |
| `workflow begin --stages <csv> --gates <csv>` | Initialize the default profile if needed; verify state, audit chain and the standard workflow route |
| `stage start|done <stage>` | Record stage progress (order enforced) |
| `gate approve|reject <stage> [--reason R]` | Record a gate decision |
| `switch --profile <id> --confirm` | Change profile at a stage boundary |
| `status` / `resume` | Show progress and verify the audit chain |
| `rebuild` | Reconstruct state from `spec.md`, `plan.md`, `tasks.md` |

In an agent session, use the `speckit-profile` skill, which drives these commands and asks for confirmation.

## Profile-aware workflow entry (feature 032)

### One navigation surface

`workflow recommend` presents inline, inline-with-selected-workers and delegated
execution choices, with existing named profiles as presets. This neither changes
the default recommendation nor removes profiles, workers, policies or gates.

`workflow next --json` is the normal navigation surface. It retains its existing
action/reason/next-action fields and adds the confirmed route, execution choice,
artifact presence, sensor freshness, open-question preview (five items, 160
characters each), recorded calls and stored review freshness. CLI text shows
the same stage checks and distinguishes missing configuration from passing tests.
Sensor inspection and gate decisions share one freshness evaluator; neither
inspection nor a cached file substitutes for actual required checks.

At a gate, `approval_package` lists the required review sections and the
authorization limits. It is a skeleton, not proof that the human has seen a
completed package or approved anything. The host must still present actual
artifacts, checks, findings and unresolved risks before asking.

Existing context/dispatch/inspection commands remain available. Normal work
keeps spec, plan and requirement-linked tasks; use construction units only when
checkpoint/dependency coordination adds value or policy requires them. Relevant
knowledge/practices and existing answers are reused with freshness checks;
questions are batched within existing budgets, not silently answered.
Plugins, deployment, specialist review and learning remain opt-in or
policy-driven. Required domain-specific validators remain separate.

### Opt-in selective execution and engine directives

`selective` uses an inline host for stage work, with explicitly assigned named
supports/reviewers instead of default lead delegation. Its shipped assignments
select only the independent architecture reviewer at plan. There is no default
change to `feature`, `bugfix`, `quick`, `hybrid-plan` or initialized routes.
Project-owned profile/overlay configuration can select additional stage-capable
supports before confirmation; every stage needs an explicit assignment.
Select workers based on actual authorization/privacy, interfaces, migration,
deployment and uncertainty evidence, not a numerical risk score.
Recommendation JSON adds advisory request signals, assignments, review-coverage
notes and lighter/stronger alternatives. The host must inspect roster defaults
where assignments are omitted and present the actual worker set before approval.

After reviewing stages, gates, named workers, rationale and host limitations:

```text
python -m speckit_flow init --profile selective --confirm-route --route-rationale "Independent plan review" --feature-dir <feature>
python -m speckit_flow workflow next --feature-dir <feature> --json
```

Initialization snapshots the complete profile in feature-local
`selective-route.json`, bound to the profile-selection audit event. Changed or
missing snapshots block execution; profile edits do not silently alter existing
work. This increment only supports profile id `selective`; customize that
project-owned profile before init rather than multiplying profiles. Switching
into/out of it and rebuilding completion from artifacts are refused. A material
scope/policy change needs a newly confirmed feature; existing records remain
untouched. The no-tool hybrid reviewer cannot be selected through this route.

`workflow next` is read-only and returns action, reason and next action for
`execute`, `inspect`, `wait`, `recover`, `await_human`, `parked`, `blocked` and
`complete`. Eligible execution includes the existing dispatch brief and required
evidence. Reuse it; do not repeatedly run discovery. `blocked` exits 1.
No directive executes commands, starts stages, grants approval or cancels work.

For selective work, start the stage with `agent:workflow`. Reserve/invoke/finish
only declared domain supports, then perform the stage inline. Run
`workflow calls inline --stage <stage>` after actual work and before reserving
selected reviewers. Include feature directory and actor on every accounting
command. Supports precede inline work; reviews follow it. Do not reserve a
delegated lead. The host must discover/invoke named workers with their actual
declared tools; unavailability is a stop, not permission for substitution.

Inline accounting fingerprints current core artifacts plus declared unit files
at implement. It does not cover undeclared source/dependencies or certify work
quality. Required reviewer calls must succeed; save actual results via the review
CLI as the selected reviewer actor, with `author: agent:workflow`. Completion
and gates require current inline hashes and selected fresh review records.
All selected block verdicts need an explicit audited human override at a gate.
Call outcome, review verdict, sensor result and human approval are separate.
The route permits two inline recordings (initial/revision), one call per support
and two per reviewer (initial/follow-up); failure/running calls freeze progress.
Only a human reset starts a fresh attempt, never an automatic retry.

These are operational evidence bounds, not authentication, process exclusion,
host input-boundary verification or a guarantee of named-agent tool enforcement.
For strict input-boundary checks use `hybrid-plan` and its actual-host adapter.
No tests or deployment permissions are waived by selective execution.

### Fail-closed recovery inspection

```text
python -m speckit_flow workflow recovery --feature-dir <feature> --json
```

This read-only local query reports recorded calls, verified tracked-source units,
uncertain units, ready-unit advice, reason and next action. It reuses current
unit/dependency/approved-command freshness; there is no stale-success cache or
selection of one arbitrary global "latest" unit. Unrelated valid units remain
verified. Command-only checkpoints are not source-verified resume evidence.

Without a host adapter, a recorded running call or accounting lock reports
`unavailable`; unrecorded in-progress execution, failed calls or uncertain
checkpoints report `unknown`; gates/parked work report `delayed`. A host adapter
may supply the core API's typed `WorkerObservation` for a matching current call,
distinguishing `running`, `delayed`, `unavailable`, and `unknown`. This is a
correlated observation, not authenticated identity, safe exclusion or an
ownership lease. No CLI host adapter is installed by this increment.

`resume_allowed` is advisory only for a pending stage with no relevant blockers.
It does not resume, skip tasks or approve anything; re-enter normal preflight.
`ownership_transfer_allowed` is always false, even with an observation.
An expired heartbeat, absent worker listing or failed call never authorizes
takeover. Inspect actual execution and uncertain side effects under human
direction. No cancellation, ownership transfer, lock removal or side-effect
replay is implemented.

The query has no retry/poll loop, model call or external probe. It is bounded
in execution scope, not a hard wall-clock deadline on filesystem I/O. A real
host identity/exclusion adapter and end-to-end recovery acceptance remain separate
work; the opt-in local watchdog below does not complete the broader feature 033 proposal.

Opt into a bounded watchdog with:

```text
python -m speckit_flow workflow recovery --timeout-seconds 10 --feature-dir <feature> --json
```

The watchdog runs local inspection in an owned child process. On deadline it
terminates only that inspection process, returns `unknown`, disables resume and
transfer, and preserves any owner/call metadata observed before timeout. Empty
checkpoint lists mean unobserved evidence, not no progress. OS scheduling and
bounded process cleanup can add latency; this is not a real-time guarantee.
No old task worker is cancelled and no work is replayed.
The deadline starts inside the recovery inspector, after parent Python/CLI
initialization. It includes inspection-process startup, not an end-to-end CLI
startup guarantee; native smoke validation allows parent startup separately.

The core `RecoveryAdapter` protocol accepts trusted integration code returning
a correlated `HostObservation`. Missing identity becomes `unknown`; mismatched
reservation or invalid identity/exclusion metadata fails explicitly. Even
adapter-reported exclusion never grants ownership transfer. Adapters used with
the watchdog must be spawn-picklable. No arbitrary command or user JSON can
register an adapter, and no actual Copilot identity/single-writer adapter is
installed. Actual safe continuation and authenticated host enforcement remain
unimplemented until the receiving host provides enforceable APIs.

### Recovery review packages and synthetic scenarios

Use the same inspection command with an optional review package:

```text
python -m speckit_flow workflow recovery --approval-package --feature-dir <feature>
python -m speckit_flow workflow recovery --approval-package --timeout-seconds 10 --feature-dir <feature> --json
```

Without the flag, the existing output shape and exit status are unchanged.
With it, JSON adds `approval_package`; plain text adds labeled decision/scope,
inspection evidence, verification, provenance, risks, allow/exclude boundaries
and next action. `unknown`/`unavailable` still return exit code 1, with the report
available for review. Corrupt or unreadable evidence remains an explicit error,
not a success-shaped package.

The core `decision_package` formatter accepts an engine-produced recovery
report, not user JSON as host proof. It does not invoke commands, workers or
models, persist an approval, change checkpoints, reset budgets or select a
global latest resume boundary. Neither viewing nor approving a package grants
continuation or transfer. Normal route preflight and any separate human/host
authorization remain mandatory. The report is a non-atomic local inspection;
it must not be reused as a later execution grant.

Scope includes stage, recorded call IDs and current/uncertain unit IDs. Evidence
distinguishes complete inspection from timeout and marks timeout checkpoint
coverage as unobserved. Tracked-current units mean declared-input freshness
only, not that every completion criterion was substantiated. No verification
or independent review runs during inspection; semantic completion and prior
external side-effect outcomes remain not verified. Host identity/exclusion is
at most adapter-reported, never authenticated by the formatter.

The package omits raw file contents, prompts, command arguments, unit titles,
audit details, actor labels, host worker identifiers and absolute source paths.
Workflow IDs remain local metadata; receiving projects must keep those IDs
non-sensitive. Display the actual feature/artifact links separately in the
human approval conversation. Text uses explicit labels rather than color or
link-only meaning, but this does **not** establish keyboard/screen-reader
acceptance; that field remains `not_verified`.

#### Complete checkpoint inventory and evidence comparison

The opt-in package now includes `checkpoint_inventory` for every declared unit:
`current`, `stale`, `missing`, `blocked`, `command_only`, or `unverified`, plus
counts and checkpoint presence. No unit is silently omitted because it lacks
a checkpoint or approved verification policy. In a bound inventory, package
scope marks only `current` tracked units as current; all other units remain
uncertain for recovery review. This does not change the default recovery
report's advisory fields or grant a resume boundary.

Each entry separates:

- **Freshness**: the shared unit assessor compares declared files, definition,
  dependencies and approved verification-command digest.
- **Recorded verification**: the latest unit-checkpoint audit event records
  a pass, failure, or unverified/missing outcome. `checkpoint_record_matches`
  separately checks the saved revision, timestamp and attribution against the
  latest passing event. A pass record is not authenticated proof of test
  semantics; a fresh checkpoint with a mismatched record is `unverified`.
- **Semantic completion**: always `not_verified` in this read-only inspection.

Safe reason codes distinguish missing checkpoints, unavailable/unapproved
verification policy, unavailable/changed tracked inputs, incomplete metadata,
changed definitions/commands/dependency evidence and unmatched/failed
verification records. `changed_files` names changed **declared root-relative**
paths when their current fingerprints were observable. `fingerprints` contains
hashes, not file contents, command arguments, unit titles or audit details.
Keep workflow IDs and declared path labels non-sensitive in receiving projects.
Only declared dependencies are covered; undeclared instruction changes or
semantic verification sufficiency cannot be inferred from these hashes.

`evidence_snapshot` hashes state, audit, units, verification policy, frozen
route files, effective profile and declared tracked inputs at the beginning
and end of inspection. Missing optional inputs are represented as absent.
Unrelated untracked files do not invalidate the snapshot or independent units.
The existing regular-file/reparse-point guards and 1 MiB per-file fingerprint
limit apply; inaccessible or oversized inputs produce explicitly unbound
snapshot evidence, not a usable digest.

Matching endpoints produce `stable_at_read_boundaries`, a fingerprint and
observed audit revision. Changes during inspection produce
`changed_during_inspection`; unavailable or timed-out evidence has no usable
fingerprint. Unit observations may remain visible, but unbound inventory has
no current-unit claims in package scope. Matching endpoints are **not** an
atomic snapshot, continuous stability guarantee, authenticated evidence or
single-writer fence. Ordinary preflight remains mandatory.

Compare a new inspection with an earlier package's lowercase SHA-256 digest:

```text
python -m speckit_flow workflow recovery --approval-package --expected-fingerprint <previous-digest> --feature-dir <feature> --json
```

Comparison is `unchanged`, `changed`, or `not_verified`; without a requested
digest it is `not_requested`. An invalid digest or use without
`--approval-package` is an explicit error. A requested comparison that is
changed or cannot be verified returns exit code 1 with the report available.
Existing unknown/unavailable worker outcomes still return 1 even when hashes
match. Comparing a digest never approves, resumes, cancels, migrates or replays
anything. Core callers opt in with `status(..., include_evidence=True)` or
`bounded_status(..., include_evidence=True)` before formatting a package.

#### Advisory revalidation plan

The same opt-in recovery package includes `revalidation_plan` in JSON and a
numbered review plan in text. No additional command or executor is installed.
The shared validated unit graph supplies dependency order, even when unit
declaration order differs. Each affected unit lists all declared dependencies,
affected prerequisite units, reason codes, changed declared files and review
actions. Review order is not a dispatch queue or permission to run in parallel.

Actions distinguish changed/unavailable inputs, changed unit scope or command,
missing/incomplete checkpoints, changed dependency evidence, failed or unmatched
verification records and human review of unapproved verification policy.
Command-only units require source-coverage review even when their command
record is current. Every affected unit still needs completion-criteria review
and separately authorized verification after prerequisites are resolved.
The plan does not run checks, repair evidence, reset checkpoints, or replay work.

`preserve_units` lists independent current tracked units; there is no blanket
reset. It does not establish semantic completeness. A stable bound inventory
produces `status: advisory`, always with `executable: false`. Unobserved,
unavailable, mid-inspection changes, or a mismatched requested snapshot
comparison produce `status: blocked` with no ordered steps or preserve claims.
Re-inspect before trusting review order.

All plans explicitly retain execution blockers for actual host execution/
ownership safety, unknown prior external side effects, and normal route
preflight/human gates. These remain blockers even if no units require review.
An empty plan means no affected declared units were observed, not permission
to resume or proof that external effects are safe. Existing CLI exit behavior
is unchanged; plan blockers are advisory boundaries, not a new approval path.

The feature 033 inventory maps to these existing and focused model-free cases
in `tests/unit/speckit_flow/test_flow_session.py`. These are test mappings, not
claims of full feature 033 or live-host acceptance. Unsupported continuation
is tested as blocked, not simulated as operationally successful.

| Class | Synthetic case / manual check | Expected boundary |
| --- | --- | --- |
| 1. Running | `test_correlated_host_observation_never_authorizes_takeover[running]` | Running observation; no grant |
| 2. Delayed | Same test, `delayed`; package CLI pending-stage case | Delayed, not stopped |
| 3. Unavailable | Same test, `unavailable` | Missing host evidence, not death |
| 4. Unknown | Same test, `unknown`; package CLI in-progress case | Unknown, no continuation |
| 5. Worker identity | `test_recovery_adapter_requires_identity_and_never_grants_transfer` | Missing identity unknown; mismatched reservation rejected |
| 6. Duplicate dispatch | `test_recovery_package_concurrent_inspection_and_duplicate_dispatch_are_read_only` | Duplicate rejected; one existing reservation preserved |
| 7. Concurrent recovery | Same test, parallel package inspections | No writers or recovery grants created; live fencing not tested |
| 8. Valid/latest checkpoint | `test_recovery_checkpoint_freshness_preserves_unrelated_units` | Current declared units shown; global resume boundary not selected |
| 9. Incomplete checkpoint | `test_recovery_package_excludes_invalidated_declared_progress[incomplete]` | Missing metadata excluded |
| 10. Stale checkpoint | `test_recovery_checkpoint_freshness_preserves_unrelated_units` | Changed tracked input excluded |
| 11. Relevant changes | Package invalidation cases `definition`, `command`, `dependency` | Dependent completion invalidated within declared coverage |
| 12. Unrelated edits | Checkpoint freshness case and package privacy/governance case | Independent current units and unrelated files preserved |
| 13. Uncertain side effects | `test_recovery_package_omits_payloads_and_preserves_governance_and_side_effects` | Existing synthetic effect unchanged; replay never performed |
| 14. Missing host capability | Adapter cases with absent identity/exclusion | No transfer, even if adapter reports exclusion |
| 15. Uncertain liveness | Concurrent-inspection case with synthetic expired/absent-host hints | Hints ignored as authority; no takeover |
| 16. Approval evidence | `test_recovery_package_cli_preserves_default_shape_and_blocked_exit_status` | Scope/evidence/risks/provenance/boundaries visible; no decision recorded |
| 17. Approval accessibility | Actual keyboard and screen-reader procedure | **Not verified**; automated labels are not assistive-technology acceptance |
| 18. Receiving governance | Package privacy/governance case | Receiving instructions, verification policy and disabled plugin preserved |
| 19. Synthetic privacy | Same case | Synthetic markers/raw payloads omitted; no model/live-resource invocation |

The watchdog tests additionally cover timeout evidence and native spawned CLI
output. Process scheduling/cleanup allowance remains explicit; these tests do
not satisfy feature 033's strict real-time deadline criterion. Actual
single-writer recovery, latest semantic checkpoint continuation, authenticated
host integration and manual accessibility acceptance remain outstanding.

Use `/speckit-workflow <request>` for any code-change request. The entry skill
distinguishes new work from explicitly resumed work and invokes
`python -m speckit_flow workflow recommend "<request>" --json`.
Ordinary features recommend `feature` and ordinary fixes recommend `bugfix`,
both using the named-agent route. `quick` remains an explicit opt-in inline
alternative; existing initialized quick work stays inline. Security fixes
recommend `security-patch`, while refactor, infrastructure and experiments use
their existing profiles. The
heuristic is advisory, not a risk assessment: vague/mixed requests ask the user.
An explicit `--profile <id>` overrides inference but still needs confirmation.
The host always presents stages/gates and asks before initializing.

The legacy `feature` profile and `init` default remain unchanged for explicit
CLI clients. Initialized features retain their routes, even if a fresh request
would receive a different recommendation. Switch only with explicit confirmation.

The standard `.specify/workflows/speckit/workflow.yml` now starts a profile-aware
host session instead of hard-coding four stages. It invokes the shared skill
through the Copilot integration; it does not add other harness adapters.
A session stops at human gates or failures. A successful engine prompt/session
does **not** mean the feature is complete; inspect `python -m speckit_flow status`.
If CLI interaction or required delegated subagents are unavailable, execution
stops explicitly; the inline `quick` route does not require nested subagents.

Direct specify/clarify/plan/tasks/analyze/implement skill calls hand off through
the same entry skill. The assigned lead uses `SPECKIT_DELEGATED_STAGE=<stage>`
for delegated work; the host uses `SPECKIT_INLINE_STAGE=<stage>` for inline
work. These markers prevent recursive handoffs; they are not gate/verification
authority. Feature allocation happens once so ideation can precede specification.

The `quick` profile is for well-understood, lower-risk changes: specify,
plan, tasks and implement, with one human gate after tasks and inline execution.
It turns off optional learning and independent reviews, not tests or sensors.
The host must assess actual scope and risk rather than rely on keyword matching;
use a stronger route when safety, privacy, authorization, regulatory, deployment
or plugin requirements warrant it. The user confirms the profile before init.
`quick` is not a claim of independent review or guaranteed correctness.
An explicitly requested independent review must actually be performed by a
different reviewer; if unavailable, report it rather than inventing evidence.

| AI-DLC-inspired capability | Streamlined behavior |
|---|---|
| Profiles and gates | `quick` keeps the core Spec Kit artifacts and one pre-implementation gate; existing routes remain unchanged. |
| Agents and reviews | Inline work uses no default subagent or independent reviewer; delegated and strict routes keep assigned reviews. |
| Sensors and traceability | Keep configured checks and report actual results; focused acceptance and regression tests remain necessary. |
| State, audit and resume | Keep existing lifecycle state, audit integrity and human-only decisions. |
| Rules, knowledge and learning | Load relevant rules and knowledge; `quick` disables optional learned-rule proposals. |
| Plugins and contracts | Remain opt-in; use a stronger route when project or plugin policy requires specialists or additional gates. |
| Deployment and recovery | Remain separate, explicitly authorized workflows; the fast path does not deploy or transfer worker ownership. |

These are workflow and configuration changes, not a measured runtime or accuracy
guarantee. Checks, risks and the absence of independent review must be disclosed.

### Low-overhead implementation and resume

`python -m speckit_flow context --feature-dir <path> --json` gives a read-only
snapshot: lifecycle state, execution mode, pending gate, parked status, core
artifact presence and task checkbox progress. The preview is capped at five
pending tasks with 160 description characters each and source line numbers;
long descriptions are flagged as truncated. Missing/empty task files are
explicit, fenced examples are ignored, and duplicate task IDs fail explicitly.
The output does not include full specifications or completed task descriptions.
It does not choose ready tasks, verify code, grant approval, cache test results
or replace dispatch preflight. Read the actual artifacts and dependencies.

Context and dispatch inspect one fresh audit stream per invocation, checking
the hash chain while counting events and finding the latest park/resume state.
The snapshot retains constant-size summary metadata, not event bodies or a
persistent cache. Missing/empty histories still block context/dispatch; damaged
or unreadable histories fail explicitly. The next invocation rereads the file,
so a later park/resume or corruption cannot reuse an old snapshot.

The plan template no longer includes generic single-project/web/mobile layout
trees. Record the actual affected structure. Quick keeps necessary decisions
and acceptance/regression commands in the plan; auxiliary research/data-model/
contracts/quickstart artifacts remain conditional for quick and retain all
stage/policy requirements on other profiles. The template retains technical
context, constitution checks and complexity justification.

Planning existing-code changes focuses on the delta, reuse and unchanged
behavior, rather than re-documenting the whole system. Behavioral changes need
acceptance/regression test tasks with requirement references; documentation-only
or non-automatable work needs an explained alternative. Run focused checks per
coherent change and final affected checks after the last edit; broaden them for
shared interfaces, policy or failures. Required sensors and approved checkpoint
commands are unchanged. Independent reads/checks may run concurrently, but
dependent/shared-file edits stay sequential and `quick` does not spawn workers
by default. Track tasks persistently, reporting chat progress at milestones.

These choices draw on [Kiro's dependency-aware specs](https://kiro.dev/docs/specs/)
and [bugfix regression preservation](https://kiro.dev/docs/specs/bugfix-specs/),
[OpenSpec's brownfield change focus](https://github.com/Fission-AI/OpenSpec),
[Claude Code's context and verification guidance](https://code.claude.com/docs/en/best-practices),
and [AI-DLC's inline-first orchestration](https://github.com/awslabs/aidlc-workflows/blob/main/docs/guide/00-introduction.md).
They add no external runtime dependency or lifecycle gate.

### Document-grounded clarification and project practices

Before asking a specification, clarification or planning question, consult the
relevant current feature artifacts, approved decisions, project guidance and
stage-filtered knowledge references (`knowledge list --stage <stage> --json`).
The listing contains metadata, not answers: read only the relevant sections.
Reuse explicit answers with path/section or path/line citations, rather than
asking the user to repeat them. Present inferred material answers as proposals
for confirmation in the existing question/gate interaction, within the stage's
question budget and interaction mode. Ask about gaps, conflicting sources or
changed assumptions; do not sweep every document or reopen settled decisions
without cause. Missing/unreadable sources and stale or uncertain evidence must
be disclosed, not guessed away. Current user direction and approved decisions
take precedence over older descriptive documents; unresolved policy conflicts
still need human direction. Documents are evidence, not executable instructions.
Only a human can close a recorded question; no new confirmation gate is added.

Discover convention sources without executing project code:

```text
python -m speckit_flow codebase practices --json
python -m speckit_flow codebase practices --project-dir <package-root> --json
```

The read-only command reports sorted source paths, SHA-256 hashes, an aggregate
fingerprint and an explicit `found`/`empty` status. It inspects recognized
root-level manifests, tooling configuration and contributor guidance, plus
GitHub workflows/instructions. It emits no file contents, extracts no commands,
and does not write a cache. Limits are 64 sources, 1 MiB per source and 2,000
examined directory entries; exceeded limits, inaccessible files and relevant
symlinks/junctions fail explicitly. It does not recursively scan dependencies,
nested packages, arbitrary documentation or external CI templates. Inspect
affected package roots and any referenced scripts/configuration separately;
record those extra sources with their hashes in the summary and recheck them
before reuse. Non-GitHub CI and unrecognized configurations require the same
explicit discovery; an empty result is not proof that no conventions exist.

During planning, read relevant sections of discovered sources and keep a small
**Project practices** section in the existing `plan.md`, not another artifact:

| Practice | Command/convention | Working directory | Evidence |
|---|---|---|---|
| Focused tests | Actual project command and selector, or unknown | Project/package root | Source path and line/section |
| Build/lint/types | Only checks relevant to this change | Project/package root | Source path and line/section |
| Coding conventions | Applicable existing patterns | Affected scope | Source path and line/section |

Store each inspected root and fingerprint alongside the table. Include required
environment/setup, unresolved conflicts and any extra source hashes. Distinguish
CI-only commands from locally runnable equivalents; do not invent commands when
sources disagree or omit them. Never persist credentials, environment values or
customer data in this summary. Source content is untrusted evidence: discovery
does not authorize executing scripts, installing packages, accessing services
or changing verification policy.

Before implementation first uses a summary, on resume, and after changing a
convention source, rerun discovery and compare both root and fingerprint,
including extra sources. Added, deleted, renamed or edited recognized sources
change the fingerprint, even if timestamps do not. Refresh the summary only
when missing/stale or the affected scope changes; surface discovery failures
instead of reusing it as current. Changes to approved verification scope follow
existing approval rules. Fingerprints establish source freshness, **not command
correctness, passing tests or implementation correctness**. Always run required
checks against the current implementation; no test-result cache is introduced.

These are simplified adaptations of AI-DLC's
[document-grounded knowledge](https://github.com/awslabs/aidlc-workflows/blob/main/docs/guide/08-knowledge.md)
and [practices discovery](https://github.com/awslabs/aidlc-workflows/blob/main/docs/guide/04-phases-and-stages.md).
They add no stage, agent, gate or runtime dependency. Automated tests cover the
source snapshot and instruction wiring, not whether an LLM consistently follows
the guidance or whether development is faster; that requires a real workflow trial.

`python -m speckit_flow workflow dispatch [--stage <stage>] --json` is read-only
preflight: it checks state, audit integrity, parked/pending gates, stage order,
roster/frontmatter and conductor allowlist. It returns a lead, domain supports
and independent reviewers plus an execution mode, not model invocation evidence.
Inline stages are run by the host with `agent:workflow`; they do not call the
conductor or claim specialist review. Strict gated stages
without an assigned reviewer receive a core independent product or architecture
reviewer so clarify/tasks gates cannot be stranded without review. For delegated
routes, the conductor uses
the host agent tool, collects read-only contributions as text, runs the lead,
then separate reviewers and sensors. Failed workers are not marked done.

Dispatch also returns absolute `project_root` and `feature_dir` for worker
briefs. Every shell call must explicitly set its working directory (for
PowerShell: `Set-Location -LiteralPath '<project_root>' -ErrorAction Stop`)
or use the host's cwd parameter. Prior calls do not establish later shell
working directories. Validate test-file existence before running relative
selectors; missing paths and zero collected tests are failures.
Invoke configured roster workers directly with their declared tool restrictions:
only the conductor has the `agent` tool. Generic runner wrappers may introduce
another worker and are not an equivalent substitute. If custom selection/tool
restriction is unavailable, stop delegated lifecycle work explicitly. In a
separately requested generic-worker experiment, use a direct executor and inspect
actual tool calls for nesting; prompt instructions and final summaries alone
are not enforcement or evidence that no nested calls happened.
Use the [compatibility diagnostic distinctions](#worker-tool-compatibility-diagnostics)
when explaining unavailable evidence; a missing invocation parameter is not
itself proof of an unsupported host.

Standalone read-only reviews do not start or advance a lifecycle; small reviews
can be handled directly, but do not count as independent, source-bound gate
evidence. In lifecycle work, only assigned agents are used by default. Per
stage attempt, each assigned reviewer runs once plus at most one automatic
follow-up after batched revisions. A current `pass` or `concerns` is reported
without chasing a perfect pass. If further review is needed, including for
stale evidence, the conductor stops and waits for explicit user direction.
Failed sensors are not repeatedly run without a relevant change or a
user-directed retry. These limits are agent instructions, not a CLI-enforced
quota; they do not waive required reviews, sensors or human gates.

Use `/speckit-workflow resume` after an actual human decision or interruption;
in-progress workers require inspection and explicit resume confirmation.
`python -m speckit_flow resume` verifies lifecycle state, not an engine cursor.
Do not silently migrate an old static workflow cursor; finish it with its old
definition or re-enter from verified lifecycle state after review.
Legacy `workflow begin --stages ... --gates ...` remains for explicit clients.

For `comprehensive`/strict profiles, source-bound review evidence and existing
sensors remain required at human gates. Human overrides must be explicit and
audited. A deployment stage never authorizes changing live resources.

## Reviews, rules, knowledge, composer and extended stages (feature 010)

| Command | Purpose |
|---|---|
| `review save <stage> --file f.json` / `review list [stage]` | Record or list source-bound reviews (`reviews/<stage>-<n>.json`); a changed reviewed file makes a review STALE |
| `gate approve <stage> --override-reason R` | Human override of a `block` review; audited as `gate_overridden` |
| `rules propose --text T (--from-gate S / --from-finding ID:N / --manual)` | Store a pending rule |
| `rules approve|discard <R-nnn>` | Human-only decision |
| `rules list [--status S] [--stage X]` | `--stage` shows active rules for that stage (max 10, conflicts flagged) |
| `knowledge list [--stage X]` | Titles and paths of `.specify/knowledge/*.md` (optional `title:` and `stages:` header lines) |
| `compose validate|save --file route.json [--confirm]` / `init --route-file` | Validate and save a custom route with a reason per stage |

- **Review gating:** a current (non-stale) review is used when approving a gate. `comprehensive` depth (for example the `enterprise` profile) **refuses approval without a current review**. A `block` verdict refuses approval unless a human passes `--override-reason`. Reviewer and author must differ.
- **Rules:** agents only propose; a `human:` actor must approve. Stored in `.specify/rules/rules.json`.
- **Extended stages:** `ideation, specify, clarify, plan, tasks, analyze, implement, deploy, operate`. `deploy` needs `implement`; `operate` needs `deploy`. The `full-lifecycle` profile uses all of them. Features on older profiles keep working and do not record the optional stages.
- **Skills:** `speckit-review`, `speckit-learn`, `speckit-compose`. Schemas: `specs/010-reviewers-rules-knowledge/contracts/`.

## Agent roster (feature 012)

- **Roster:** `.specify/agents/roster.json` lists 14 agents (11 domain, 2 reviewers, 1 composer) plus the `speckit-conductor`. Each has `.github/agents/speckit-<id>.agent.md`. Reviewers have no `edit` tool.
- **Orchestration:** only the conductor delegates (`agent` tool). Roster agents are non-user-invocable sub-agents. Each stage has a default lead; a profile may override via `assignments`.
- **Commands:** `python -m speckit_flow agents list|validate|assign [--profile <id>]`. `status`/`resume` show `lead_agent`.
- **Actors:** `agent:<id>` must be a roster id. Gates can only be approved or rejected by `human:` actors.
- **Enforcement:** `.github/hooks/speckit-guard.json` runs `scripts/speckit_guard.py` as a `preToolUse` hook, denying agent gate/rule decisions and writes to audit, state, review and rules files. Hooks are a Copilot preview feature; the CLI checks remain the backstop.
- Specs: `specs/012-ai-dlc-agent-roster/`.

## Sensors, traceability and doctor (feature 013)

- **Sensors:** `.specify/sensors/sensors.json` defines builtin (`consistency`, `traceability`) and command sensors (argv list, no shell, timeout; output is never stored). `python -m speckit_flow sensors list|run <stage>` records results with artifact fingerprints under `<feature>/sensors/<stage>.json` and audits `sensor_run`.
- **Gate enforcement:** when the config exists, `gate approve` is refused unless every required sensor for the stage has a passing, non-stale result. Use `--sensors-file` to point elsewhere. The shipped workflow runs `sensors run` for specify and plan before each gate.
- **Traceability:** `python -m speckit_flow trace [--require-tests]` maps `FR-###`
  requirements in `spec.md` to tasks and test tasks (those mentioning "test") in
  `tasks.md`. Empty requirement/task sets and duplicate task IDs fail explicitly.
  Unknown requirement references now fail alongside uncovered requirements;
  `--require-tests` also rejects requirements lacking a planned test task.
  Sensors and required-test gates report the offending references. Tasks without
  a requirement citation remain advisory (for example setup tasks). These
  stricter checks intentionally reject formerly accepted invalid inputs; they
  prove planned coverage only, never actual test execution or correctness.
- **Doctor:** `python -m speckit_flow doctor` checks profiles, roster, sensors, rules, hook, workflow and (when available) feature state and audit chain.
- Specs: `specs/013-sensors-traceability-doctor/`.

## Intents and session control (feature 014)

- `python -m speckit_flow intents list|switch <name>|park [--reason]|unpark`: list initialized features (active marked `*`), change the active feature (`.specify/feature.json`), park or resume work. Parked status comes from the latest `intent_parked`/`intent_resumed` audit event; `stage start` is refused while parked.
- `redo <stage> --reason R` (alias `jump`): human-only; resets that stage and all later stages to pending, clears a pending gate and audits `stage_redone`. Forward targets are refused so gates stay meaningful.
- `.github/hooks/speckit-session.json` runs `scripts/speckit_session.py` at session start to print the active feature, stage and lead agent. It is best-effort and always exits 0.
- Specs: `specs/014-intents-session-control/`.

## Layered rules and customization (feature 015)

- **Layered rules:** `.specify/rules/org.json` and `team.json` (human-authored) plus the project `rules.json`. `python -m speckit_flow rules list --effective [--stage S]` merges active rules, labelled by layer; a narrower layer overrides a broader rule with the same wording and opposite polarity.
- **Overlay:** `.specify/custom/profiles/<id>.json` and `.specify/custom/sensors.json` add to or override shipped items. Invalid overlays are errors, and an overlay cannot replace a required core sensor. `python -m speckit_flow custom list|validate`; `doctor` checks it.
- The guard hook protects `.specify/custom/`, `org.json` and `team.json` from agent edits.
- Specs: `specs/015-layered-rules-customization/`.

## Questions file and policies (features 016-017)

- **Questions:** `python -m speckit_flow questions add "<text>" --role <agent-id>|answer Q1 "<text>"|list [--open] [--role R]|check`. Questions live in `<feature>/questions.md` as `## Q1 [role: product]`; answer via the CLI (human-only), or type after `**Answer:**` in the file. `check` exits 1 while any are open, and the required `no-open-questions` sensor blocks the plan gate. Agents ask through the conductor and never answer.
- **Guard policy:** profile field `guard_policy: strict|standard`. Strict needs a current review and no open questions before any gate approval. Unset, `depth: comprehensive` implies strict.
- **Test strategy:** profile field `test_strategy: standard|required`. Required refuses tasks/analyze/implement gate approval while a requirement has no test task.
- Specs: `specs/016-questions-interaction-modes/`, `specs/017-test-strategy-guard-policy/`.

## Stages as data (feature 018)

Stage order, optionality, `requires` and `lead` live in `.specify/stages/stages.json`. A project can add optional stages in `.specify/custom/stages.json`, each with `after` naming an existing stage, for example `{"id": "nfr-design", "phase": "design", "optional": true, "after": "plan", "lead": "architect"}`. Custom stages must be optional, use a new id, and have one lead (roster `leads` or the stage `lead`). Profiles opt in by listing the stage in canonical order. `speckit-flow stages` lists the effective stages and `doctor` validates them. Stages load at process start.

## Construction units and verification command (feature 019)

Define units in `units.json` with `units add <id> "<title>" --depends-on a,b --tasks T001,T002`.
Optionally declare implementation, test, fixture and configuration inputs with
`--files <root-relative-paths>`. Propose the project's real check with
`verify propose --actor agent:developer -- python -m pytest -q`; a human approves
it with `verify approve`. Editing the command invalidates approval.
`units checkpoint <id>` needs currently verified dependencies, runs the approved
command, and records evidence only on success. Agents cannot approve verification
commands or edit `.specify/verify.json` through the guarded workflow.

### Freshness-aware checkpoints and ready work

```text
python -m speckit_flow units list --feature-dir <feature> --json
python -m speckit_flow units list --feature-dir <feature> --verify-file <policy>
```

Listing is read-only and never runs verification or dispatches workers. The
existing `units` array gains `status`, `reasons`, `blocked_by`, `coverage` and
`checkpoint_present`; `checkpointed` now means **currently verified**, not merely
present in storage. The top-level `ready` array contains ready unit IDs.

| Status | Meaning |
|---|---|
| `ready` | No checkpoint; dependencies verified, declared files readable, command approved. |
| `blocked` | No checkpoint and an unmet dependency, input or verification-policy requirement. |
| `stale` | Stored evidence exists but no longer matches current inputs or lacks freshness metadata. |
| `verified` | Stored evidence matches declared files, definition, approved command and current dependency evidence. |

`stale` takes precedence for existing evidence, while `blocked_by` still names
direct unverified dependencies. Transitive problems propagate through the DAG.
Reasons explicitly disclose missing/unreadable files and absent/unapproved policy.
Invalid unit/checkpoint containers, unknown dependencies and cycles fail explicitly.
Ready is advisory: normal lifecycle gates, shared-file coordination and required
checks still apply. This is not a scheduler or automatic parallelization feature.

Each successful checkpoint records its unit definition, declared file hashes,
approved-command digest, direct dependency-evidence digests and an audit-sequence
revision. Recheckpointing an ancestor invalidates downstream evidence even within
the same timestamp second. After refreshing an ancestor, recheckpoint dependent
units in dependency order; unrelated valid units stay verified.

Every recheck first removes that unit's previous pass. Failed checks, invalid
policy and access failures cannot retain an earlier success. Source, definition,
command or dependency changes during a successful command also reject the
checkpoint. The implementation gate and walking-skeleton check use the same
freshness evaluator and refuse stale evidence, without executing commands.
The implementation gate uses the feature project's `.specify/verify.json`;
explicit unit CLI operations honor `--verify-file`, but a custom policy does not
silently replace the gate/skeleton policy.

Legacy checkpoints without the new freshness metadata report `stale` and need
an explicit `units checkpoint <id>` refresh; they are not silently upgraded or
deleted by listing. Units without `--files` retain support but report
`coverage: command-only`: current code is **not** fingerprinted. Tracked units
report `coverage: tracked-files`, covering only declared inputs. Include relevant
scripts, tests, configuration and fixtures explicitly; unchanged command text
does not prove an undeclared script or external service is unchanged.

Freshness is not a test-result cache or a substitute for required final/integration
checks, human approval or independent review. There is no new stage, agent,
runtime dependency or approval gate.

## Plugin packs (feature 020)

A pack lives in `.specify/plugins/<name>/` with `plugin.json` (`name` equal to the folder, `version`, optional `enabled: false`) and any of `profiles/*.json`, `sensors.json`, `stages.json`, `agents.json` or `contracts/stages.json`. Plugins only add items; reusing a core profile or sensor id is refused. Precedence is core, plugins by name, then `.specify/custom/`. `plugins list|validate` shows what each pack provides, and `doctor` checks them. Agents are blocked from editing `.specify/plugins/`.

## Structured stage contracts (feature 031)

Project profiles with `"stage_contracts": true` may additionally opt into
`"contract_inputs": true`. The existing stage-contract sensor then requires
declared path-bound inputs to be regular, non-empty, non-link feature-local
files within the same size/count limits as outputs. Their hashes join the
contract/output fingerprints, so input edits, removal or contract changes make
previous passing evidence stale. Invalid or inaccessible inputs fail explicitly.
Pathless inputs remain descriptive and require human review. Legacy profiles
retain output-only checking; no plugin is enabled implicitly. This checks
declared source freshness, not upstream semantic validity or evidence truth.

The disabled `stage-contracts` pack adds the `contract-driven` profile. A
contract records stage purpose, inputs, required/optional outputs, acceptance
criteria and reviewer focus. Enable the pack only after review, then initialize
with that profile or opt a project-owned profile in with
`"stage_contracts": true`. Every routed stage must have a contract; custom
contracts may be added or override pack contracts in
`.specify/custom/stage-contracts.json`.

Use `python -m speckit_flow contracts list` or
`python -m speckit_flow contracts show <stage>` to inspect contracts. Required
outputs on gated stages need feature-relative paths and must exist, be regular
non-empty files, with no more than 100 distinct paths and 1 MiB per file. Run
the stage-contract sensor before gate approval. Missing/failed/stale evidence
blocks the human gate; on non-gated stages it is advisory. The check proves
only presence and freshness, never content quality. No source code or commands
are executed, and file contents are not written to the audit trail.

The pack's sensor uses the `["*"]` stage selector so it also covers custom
stages in an opted-in profile. The profile's `stage_contracts` flag keeps that
sensor inactive for existing profiles.

## Clarify interaction modes (feature 021)

`speckit-clarify` offers three modes: guided (default), file (answer by editing `questions.md`) and discussion (free conversation). Every question is recorded with a role tag, agents cannot answer, and `questions check` confirms none remain.

## Ceremony toggles (feature 022)

A profile can set `"ceremony": {"learning": false, "reviews": false}`; both default to on. With `learning` off, `rules propose` is refused for that feature (`bugfix` uses this). `reviews` off makes the conductor's reviewer dispatch optional and is rejected together with a strict guard policy. Sensors, gates and the guard are never switchable. The session summary shows `skips=`.

## Phase rules

Rules have a fourth, narrowest layer: `phase`. Put rules for one stage in
`.specify/rules/phase/<stage>.json` (for example `plan.json`). They apply only
when that stage is requested and override opposite rules from org, team and
project. Like the other rule files, they are human-managed and protected by the
guard hook.

## Custom and plugin agents

Add agents without editing the core roster: list them in
`.specify/custom/agents.json` or in a plugin's `agents.json` (same format as
`.specify/agents/roster.json`). Extra agents are add-only and must be `domain`
agents that only `supports` stages. They cannot lead a stage, reuse a core id,
or change the fixed core counts. Each needs its own `.agent.md` file; list it in
the conductor's `agents` to let the conductor dispatch it. `agents list` shows
each agent's `source` (`core`, `custom` or `plugin:<name>`).

## Compliance pack (example plugin)

`.specify/plugins/compliance/` is a worked example, shipped disabled. Enabled, it
adds a `compliance` profile, a required `compliance-section` sensor and a
read-only `compliance-reviewer` agent. See its `README.md` to enable and adapt it.

Two generic sensor features support it:

- `section` built-in sensor: `options.heading` (required) and optional
  `options.artifact` (`spec.md`, `plan.md` or `tasks.md`). It fails when the
  heading is missing or its body is empty.
- `profiles` on any sensor: a non-empty list of profile ids. The sensor then
  runs and is required only for features on those profiles.

`doctor` warns (not fails) when an enabled extra agent is missing from the
conductor's `agents` list, because the conductor could not dispatch it.

## AI-DLC extras pack (example plugin)

`.specify/plugins/aidlc-extras/` ships disabled. Enabled, it adds the optional
stages `market-research`, `nfr-design` and `perf-validation`, the profiles
`discovery` and `nfr-hardening`, and a required `nfr-section` sensor for
`nfr-hardening`. Its `templates/` give each stage a starting layout (not read by
the tool). Stages load at start-up, so enabling takes effect on the next command.

## Audit trail

`audit.jsonl` holds one event per line with `seq`, `ts`, `type`, `stage`, `actor`, `detail` and `prev_hash` (SHA-256 of the previous line). The file is only appended to. Editing or deleting an earlier line breaks the chain and `status` reports it. Modifying only the very last line cannot be detected until another event is appended, so rely on version control for that case. Event text containing secret-like or account-number-like values is rejected.
