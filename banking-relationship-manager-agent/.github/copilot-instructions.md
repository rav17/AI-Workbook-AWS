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

Whenever any code change is requested, including a new feature, bugfix, hotfix, small fix, or tweak, follow the Spec Kit workflow before editing code:

1. `/speckit-specify` - Turn the request into `specs/<NNN>-<name>/spec.md`.
2. `/speckit-plan` - Produce `plan.md`, `research.md`, `data-model.md`, and `quickstart.md`.
3. `/speckit-tasks` - Produce a dependency-ordered `tasks.md` organized by user story.
4. `/speckit-implement` - Execute the tasks.

Apply this workflow uniformly regardless of change size. Do not jump straight to code, even for a small or fully specified fix.

This repository uses Spec Kit with shared templates and specifications stored in `.specify/` and `specs/`. Copilot skills are installed under `.github/skills/`. The generated artifacts are the source of truth for resuming, reviewing, and handing off work.
