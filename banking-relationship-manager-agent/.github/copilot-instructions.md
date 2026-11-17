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

Use `/speckit-workflow` for code changes. The canonical entry, confirmation,
execution, review and resume procedure is
`.github/skills/speckit-workflow/SKILL.md`; do not duplicate or reinterpret it.
Preserve initialized routes and use `workflow next --json` for navigation.
An assigned worker executes only its matching stage body, never re-enters entry.
Only confirmed named workers supply independent lifecycle evidence; unavailable
capabilities stop work, not trigger generic substitutes or repeated handoffs.
Standalone read-only reviews do not initialize a lifecycle.
Human gates, source consent and verification approvals remain actual human
decisions; actor labels or a full-lifecycle request never authorize them.

## Approval Review Packages

Before every approval request, present a readable review package in chat, not
only links inside an approval form or a subagent completion message. Include
the decision and scope, work/change summary, direct artifact links, actual
verification/review/sensor results, unresolved findings and limitations, and
exactly what approval authorizes next and excludes. Follow the stage-specific
requirements in `.github/skills/speckit-workflow/SKILL.md`, section 4.
Show the plan before plan approval and the task breakdown before implementation,
even when tasks has no separate gate. Missing or stale evidence must be disclosed
and resolved where required; an empty sensor result is not validation evidence.
Ask only after presenting the package and record only the actual human decision.

This repository uses Spec Kit with shared templates and specifications stored in `.specify/` and `specs/`. Copilot skills are installed under `.github/skills/`. The generated artifacts are the source of truth for resuming, reviewing, and handing off work.
