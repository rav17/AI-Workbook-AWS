# Research: AI-DLC Agent Roster

## Decision 1: Agents are Copilot custom agents under `.github/agents`
**Rationale**: VS Code docs define `.github/agents/*.agent.md` with frontmatter `name`, `description`, `tools`, `agents`, `user-invocable`, `disable-model-invocation`, and optional `model`.
**Alternatives**: Plain prompt files (no tool scoping); persona text inside skills (no real isolation).

## Decision 2: One conductor dispatches roster agents as sub-agents
**Rationale**: AI-DLC's conductor performs every delegation and agents never call each other. Copilot sub-agents run in their own context and need the `agent` tool plus an `agents: [...]` allow-list on the coordinator. Roster agents omit the `agent` tool, so they cannot delegate.
**Alternatives**: Handoffs (Local harness only, switches the main agent, not suited to parallel support agents); engine `fan_out` (the Spec Kit command step has no per-step agent option).

## Decision 3: Roster agents are `user-invocable: false`
**Rationale**: Keeps the agent picker clean and makes the conductor the single entry point; the conductor's `agents` list overrides model-invocation limits.

## Decision 4: Review-only enforced by tools, not prose
**Rationale**: VS Code docs state a "do not edit" instruction is not a permission boundary. Reviewers get `read`, `search` and `execute` (to run the review CLI) but not `edit`. The hook additionally blocks approval commands.
**Alternatives**: Prose-only restriction (insufficient).

## Decision 5: Hook enforcement with a CLI backstop
**Rationale**: Copilot `preToolUse` hooks in `.github/hooks/*.json` can emit `{"permissionDecision": "deny", ...}`. Hooks are Preview in VS Code, so `decide_gate` and the rule code also refuse non-human actors.
**Alternatives**: Hook only (Preview, not universal); CLI only (cannot stop direct file edits).

## Decision 6: Roster registry as JSON, assignments derived
**Rationale**: AI-DLC's 33 stages are not adopted, so each agent's led/supported stages are remapped onto the nine existing stages in one place. Profiles derive assignments from the roster and may override with an optional `assignments` block. This avoids editing every shipped profile.
**Alternatives**: Duplicate assignments in all 9 profile files (drift risk).

## Decision 7: Reviewers support, never lead
**Rationale**: Reviewers are advisory evidence producers; leading a stage would conflict with their no-edit tool scope. They appear as supporting agents on stages they review.

## Stage ownership (default)
| Stage | Lead | Support |
|-------|------|---------|
| ideation | product | architect, design |
| specify | product | design, compliance, product-lead |
| clarify | product | design, architect |
| plan | architect | aws-platform, devsecops, compliance, architecture-reviewer |
| tasks | delivery | developer, quality |
| analyze | quality | product-lead, architecture-reviewer, devsecops |
| implement | developer | quality, devsecops, architecture-reviewer |
| deploy | pipeline-deploy | devsecops, aws-platform, compliance |
| operate | operations | devsecops, quality |

The composer is not stage-bound; it is used when a custom route is proposed.
