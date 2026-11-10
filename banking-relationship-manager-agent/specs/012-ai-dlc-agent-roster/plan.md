# Implementation Plan: AI-DLC Agent Roster

**Branch**: `012-ai-dlc-agent-roster` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-ai-dlc-agent-roster/spec.md`

## Summary

Add AI-DLC's 14 agents as Copilot custom agents (`.github/agents/*.agent.md`) plus one conductor agent that is the only delegator. A machine-readable roster (`.specify/agents/roster.json`) records each agent's role, tier, led and supported stages. A new `speckit_flow/agents.py` loads and validates the roster against the agent files, resolves per-stage lead/support assignments for any profile (roster defaults, optionally overridden by a profile `assignments` block), and validates `agent:<name>` actors. New CLI commands `agents list|validate|assign` expose this. `decide_gate` now refuses non-human actors. A Copilot `preToolUse` hook script blocks agent-initiated approval commands and direct edits of audit/state/rules files. Reviewer agents get no edit tools, and domain agents are hidden from the picker so only the conductor dispatches them.

## Technical Context

**Language/Version**: Python 3.11+ (stdlib only for `speckit_flow`); Markdown agent files; JSON hook config

**Primary Dependencies**: None new. Copilot custom agents, sub-agents and hooks are consumed, not imported.

**Storage**: `.specify/agents/roster.json`; agent files under `.github/agents/`; hook config under `.github/hooks/`; hook script under `scripts/`

**Testing**: pytest; the hook script is tested by piping JSON payloads to it

**Target Platform**: Windows and POSIX; VS Code Copilot and Copilot CLI

**Project Type**: Local Python CLI plus Copilot customization files

**Performance Goals**: Roster validation and assignment resolution under 1 second

**Constraints**: Existing profiles, state, audit chains and tests keep working; no secrets in audit events; hook must fail safe (allow on unparseable input, since the CLI is the backstop)

**Scale/Scope**: 14 roster agents + 1 conductor, 9 stages, 9 profiles

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Structured state authoritative | PASS: roster is structured JSON validated in code; agents never write state directly. |
| II. Deterministic safety | PASS: human-only gate and rule decisions are enforced in code and again by the hook. |
| III. Patch, validate, invalidate | PASS: no new transactional values. |
| IV. Bounded context and tool use | PASS: each agent has a minimal tool scope; sub-agents get self-contained context. |
| V. Durable boundaries and session isolation | PASS: assignments live in version-controlled files, not in conversation. |
| VI. Python quality and operational readiness | PASS: typed code, unit tests, ruff and mypy. |
| Security and compliance | PASS: hook blocks agent attempts to approve or tamper; no secrets recorded. |

No violations. Post-design re-check: unchanged.

## Project Structure

```text
specs/012-ai-dlc-agent-roster/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md  tasks.md
└── contracts/ cli.md  agent-files.md  hook.md

speckit_flow/
├── agents.py          # roster load/validate, assignments, actor check
├── models.py          # Profile gains optional assignments
└── cli.py             # agents list|validate|assign; actor validation

.specify/agents/roster.json
.github/agents/speckit-*.agent.md      # 14 roster agents + conductor
.github/hooks/speckit-guard.json
scripts/speckit_guard.py
tests/unit/speckit_flow/test_flow_agents.py
tests/unit/speckit_flow/test_flow_guard.py
```

**Structure Decision**: Extend the existing `speckit_flow` package and keep Copilot files in their native folders.

## Complexity Tracking

No constitution violations to justify.
