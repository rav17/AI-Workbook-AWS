# Spec Kit Workflow Profiles, State and Audit

Inspired by [AI-DLC](https://github.com/awslabs/aidlc-workflows), the Spec Kit workflow supports profiles that tune the stage route, depth and approval gates per kind of work. Each feature also keeps a persistent state file and a tamper-evident audit trail.

## Profiles

Profiles are JSON files in `.specify/profiles/`. Add a team profile by dropping in a new file; the `id` must match the filename.

| Profile | Stages | Depth | Gates |
|---|---|---|---|
| `feature` (default) | specify, plan, tasks, implement | standard | specify, plan |
| `enterprise` | all six stages | comprehensive | every stage |
| `express` | specify, tasks, implement | minimal | specify |
| `bugfix` | specify, tasks, implement | minimal | specify |
| `refactor` | specify, plan, tasks, implement | minimal | plan |
| `infra` | specify, plan, tasks, implement | standard | plan |
| `security-patch` | specify, tasks, implement | minimal | specify |
| `poc` | specify, implement | minimal | none |
| `full-lifecycle` | ideation through operate | standard | ideation, specify, plan, implement, deploy |

Rules enforced by validation: `specify` is first (optionally after `ideation`), stages are in canonical order (`ideation, specify, clarify, plan, tasks, analyze, implement, deploy, operate`), `implement` needs `tasks` unless the profile declares `implement-without-tasks`, `deploy` needs `implement`, `operate` needs `deploy`, and every gate must be a stage in the route. Schema: `specs/009-workflow-profiles-audit/contracts/profile.schema.json`.

## Commands

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

## Standard workflow lifecycle automation (feature 011)

The shipped `.specify/workflows/speckit/workflow.yml` automatically tracks the standard `feature` route. After `/speckit-specify` creates the feature directory, workflow preflight initializes lifecycle state and records `specify`; shell steps wrap `plan`, `tasks` and `implement`. The existing human gates after specify and plan record `gate_approved` or `gate_rejected`. Rejection is audited before the workflow stops.

Preflight verifies the audit chain and requires the selected profile to match the workflow's exact stages and gates. It does not reset existing state. Use the `speckit-profile` skill for non-standard profiles; the static standard workflow reports a mismatch rather than silently switching profiles. To resume an interrupted engine run, use `specify workflow resume`; `python -m speckit_flow resume` verifies persisted lifecycle state but does not resume the engine's step cursor.

For `comprehensive` depth, first save current source-bound review evidence with `/speckit-review <stage>`. A blocked review requires an explicit human `gate approve <stage> --override-reason "<reason>"`; the standard workflow does not inject arbitrary free text into shell commands, so resolve that approval explicitly and continue with the `speckit-profile` skill rather than resuming an already-decided gate step.

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
- **Traceability:** `python -m speckit_flow trace [--require-tests]` maps `FR-###` requirements in `spec.md` to tasks (and test tasks, those mentioning "test") in `tasks.md`; exits 1 on uncovered requirements.
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

Define units in `units.json` with `units add <id> "<title>" --depends-on a,b --tasks T001,T002`. Propose the project's real check with `verify propose --actor agent:developer -- python -m pytest -q`; a human approves it with `verify approve`. Editing the command invalidates approval. `units checkpoint <id>` needs its dependencies checkpointed, runs the approved command, and records a checkpoint only on success. The `implement` gate cannot be approved while any unit is unchecked. Agents are blocked from `verify approve` and from editing `.specify/verify.json`.

## Plugin packs (feature 020)

A pack lives in `.specify/plugins/<name>/` with `plugin.json` (`name` equal to the folder, `version`, optional `enabled: false`) and any of `profiles/*.json`, `sensors.json`, `stages.json`. Plugins only add items; reusing a core profile or sensor id is refused. Precedence is core, plugins by name, then `.specify/custom/`. `plugins list|validate` shows what each pack provides, and `doctor` checks them. Agents cannot be supplied by plugins yet. Agents are blocked from editing `.specify/plugins/`.

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
