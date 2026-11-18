# Claude Code project instructions

This file is loaded by Claude Code. Use `specify integration use claude` from
the project root before invoking Spec Kit commands. The provider is identified
by the agent-specific instructions loaded by the current client, not by
parsing the user's prompt. Do not infer a different provider from the request
wording.

## Choosing a process

- For a new project or feature, run `/speckit-constitution` once if the
  project principles have not been established. Then run
  `/speckit-specify`, resolve open questions with `/speckit-clarify` when
  needed, `/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`, and
  `/speckit-implement`. Review each artifact before proceeding. Run
  `/speckit-converge` after implementation and repeat implementation and
  convergence until it reports `Converged`.
- For a bug or hotfix, use the bug workflow instead of creating a feature
  specification: `/speckit-bug-assess`, `/speckit-bug-fix`, then
  `/speckit-bug-test`. A hotfix may be urgent, but still assess the cause and
  verify the original symptom. Report verification as `verified` only when
  the checks were actually run and passed.
- If it is unclear whether a request is a feature or a bug, clarify its
  intended behavior and the observed failure before choosing a workflow.

Use the command spelling exposed by Claude Code. Run the workflow stages in
the agent chat, one at a time; the `specify` CLI is for project setup and
integration management.

## Scenario-specific lifecycle

Read `.specify/memory/constitution.md` before planning or implementation.
Classify the request as greenfield, brownfield, exploratory, or repair;
clarify unclear intent instead of assuming every request is a new feature.

### Greenfield

Define users, outcomes, scope, non-goals, measurable acceptance criteria,
and edge cases in `specs/<NNN>-<name>/spec.md`. Agree on missing project
principles before planning; do not invent stack or compliance requirements.
Follow the feature lifecycle above, delivering a bounded first slice.

### Brownfield and modernization

Inspect existing architecture, APIs, schemas, configuration, conventions,
and relevant tests before specifying a change. Query Graphify first when
its graph exists; confirm missing or stale details against source.
Run relevant baseline checks and record existing failures in `research.md`.
Document preserved behavior, integration boundaries, reuse opportunities,
and regression acceptance criteria. For refactoring, state the behavior
that must remain unchanged. For breaking or data changes, include
compatibility, migration, and rollback in the plan.
Follow the feature lifecycle for the bounded change, not a retrospective
specification or rewrite of the whole application.

### Exploratory work

Agree on the question, timebox, evaluation criteria, and exit decision.
Keep one stable feature `spec.md` while comparing alternative approaches.
Draft candidate plans and evidence under that feature's
`alternatives/<approach>/`, using the installed plan template; do not
overwrite an approved `plan.md` or its research, contracts, and design files.
The installed `/speckit-plan` targets the active feature's canonical
`plan.md`; it has no automatic named-alternative mode.
Do not start production implementation during exploration.
If prototypes are needed, obtain approval for bounded prototype plans,
tasks, verification, and isolated locations before editing code.
Record measured results, limitations, and rejected options. Obtain a
decision to select an approach, clarify, or stop. For a selected approach,
run `/speckit-plan` to reconcile the chosen design into the canonical
artifacts, then tasks, analyze, approval, implement, and converge.

## Artifact continuity and approval gates

- Review and obtain approval of the specification before planning, the plan
  before task generation, and the tasks plus analysis before implementation.
  Use `/speckit-checklist` when additional requirements-quality review is
  useful. Resolve blocking findings before proceeding.
- At each gate, present the decision/scope, artifact links, change summary,
  actual review and validation results, unresolved risks, and what approval
  authorizes. Wait for explicit approval; do not claim checks were run when
  only artifacts were inspected.
- Keep acceptance criteria traceable through the plan, tasks, tests, and
  results. Update the spec first when intent changes, then reconcile
  downstream artifacts without discarding completed work or prior evidence.
- Resume the active feature from its artifacts. This CLI uses
  `.specify/feature.json` or `$env:SPECIFY_FEATURE_DIRECTORY` to resolve its
  directory. For an explicit override, set
  `$env:SPECIFY_FEATURE_DIRECTORY = 'specs\<NNN>-<name>'` in the same shell
  invocation as the dependent scripts. Do not assume a Git branch or
  `SPECIFY_FEATURE` alone selects the artifact directory.
- This folder has no Git repository or application CI yet. Before using it
  for shared delivery, agree on version control and CI, then retain specs,
  plans, tasks, code, and test evidence together. Do not initialize Git,
  publish, or deploy merely to satisfy the course examples.
- Copilot/Claude co-installation is a user-approved exception; Spec Kit
  reports `unsafe-multi-install`. Run one agent at a time in this workspace:
  `integration use` changes shared defaults, templates, and extension
  registration. Use separate workspace copies for concurrent agents.

## Review evidence and handoff

- Use `.github/pull_request_template.md` when preparing a pull request.
  Until a remote repository exists, use the same structure for the final
  review handoff; do not create or publish a PR without a user request.
- For the first real feature, confirm the specification owner and required
  reviewers; record them in `spec.md`. Do not invent people or approvals.
- Maintain a verification table in the feature's `tasks.md`, linking each
  in-scope acceptance criterion (existing ID or story/scenario heading) to
  task IDs, test assertions or manual procedures, actual results, and
  evidence. Include edge cases and preserved behavior. Use the same rows
  in the PR or link to that table rather than maintaining conflicting copies.
- Record significant decisions in existing `research.md` or `plan.md`:
  decision, rationale, rejected alternatives, and actual approval when
  obtained. Record plan deviations before treating the new design as agreed.
- Repairs retain evidence in their existing bug reports; documentation-only
  changes record review results without fabricated runtime tests. Mark
  inapplicable template fields N/A with a reason.
- During final review, compare retained specifications, implementation, and
  user documentation for drift. Report gaps and follow-up work explicitly.
  Do not treat template completion or test-name matching as proof of coverage.
- CI enforcement, automated issue creation, and release/deployment gates
  remain deferred until a repository, application, and delivery requirements
  exist. This template and guidance are not automated enforcement.

## graphify

Graphify is installed for this project. Once built, its knowledge graph is
stored at graphify-out/ with god nodes, community structure, and cross-file
relationships. Fall back to source when the graph is absent, stale, or incomplete.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- Use `graphify extract . --code-only` for an initial local AST-only build.
  Do not enable external LLM extraction, cloud uploads, or remote graph
  publishing. Docs and media semantic extraction are not part of this setup.
- Reuse the installed `graphify` CLI; do not install dependencies unless it
  reports missing dependencies.
