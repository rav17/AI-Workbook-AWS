# GitHub Copilot Project Instructions

## Graphify

Use Graphify first for repository questions and codebase context.

This project may have a knowledge graph at `graphify-out/` with god nodes, community structure, and cross-file relationships.

Rules:

- For any question about this repository, first run `graphify query "<question>"` when `graphify-out/graph.json` exists.
- Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when query, path, or explain do not provide enough context.
- After modifying code, run `graphify update .` to keep the graph current. This is AST-only and has no API cost.

## Agent-Specific Spec Kit Integration

When a request requires the Spec Kit workflow, this is GitHub Copilot's activation rule:

- Before invoking any `/speckit-*` skill, run `specify integration use copilot` from the repository root.
- Continue using the Copilot skills under `.github/skills/`.
- Do not switch to the Claude Code integration from GitHub Copilot.

## Feature Development Process

For every code-change request, use `/speckit-workflow` before editing code.
Classify the request with `python -m speckit_flow workflow recommend "<request>" --json`.
Recommend `full-lifecycle` for a new feature, `bugfix` for a bug/hotfix,
`security-patch` for a security fix, or the appropriate refactor/infra/POC profile.
If intent is unclear or mixed, ask the user what kind of work it is. An explicit
profile takes precedence but still requires confirmation. Present stages/gates
and ask before initializing; never silently select the legacy default.

For explicitly resumed work, preserve the initialized feature/profile. Ask
whether to create new work or resume if the scope is uncertain. Profile changes
require explicit confirmation at a stage boundary.

Use the shared entry skill and `workflow dispatch` preflight to invoke the
`speckit-conductor` custom agent, which delegates to assigned leads/supports and
independent reviewers. Do not silently run stage work in the parent and call it
delegation. If host subagents are unavailable, report the limitation and stop.
Direct stage skills use the same handoff; only a matching delegated lead follows
their bodies, using the conductor's stage marker and feature directory.

Execute only the confirmed route in order, preserving specification, planning
and task artifacts where routed, sensors and human gates. Never approve gates,
verification commands or learned rules without the actual human decision.
Full-lifecycle is not permission to deploy or change live resources.

This repository uses Spec Kit with shared templates and specifications stored in `.specify/` and `specs/`. Copilot skills are installed under `.github/skills/`. The generated artifacts are the source of truth for resuming, reviewing, and handing off work.
