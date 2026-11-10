# Implementation Plan: Compliance Plugin Pack

**Branch**: `025-compliance-plugin-pack` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-compliance-plugin-pack/spec.md`

## Summary

Ship `.specify/plugins/compliance/` (disabled by default) with a `compliance` profile, a compliance sensor and a read-only compliance agent. Research found that the current sensor engine cannot express FR-003/FR-004, so the plan also adds two small, reusable engine features: a `section` built-in sensor (heading must exist in a stage artifact) and an optional `profiles` scope on sensors.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: standard library only (`speckit_flow` package)

**Storage**: JSON files under `.specify/plugins/compliance/`

**Testing**: pytest (`tests/unit/speckit_flow`), ruff, mypy

**Target Platform**: any host running the `speckit_flow` CLI

**Project Type**: library/cli

**Performance Goals**: not applicable; sensors run once per gate

**Constraints**: plugins are add-only; plugin sensors may never replace core ones; pack ships disabled; core behaviour unchanged when disabled

**Scale/Scope**: 1 plugin folder (4 data files, 1 agent file), 2 engine changes (~40 lines), 1 doc section

## Constitution Check

The constitution governs the Aria banking agent, not the `speckit_flow` tooling. Applicable gates:

| Principle | Status | Note |
|-----------|--------|------|
| I/II Deterministic enforcement in code | Pass | Compliance check is a code sensor, not a prompt instruction |
| VI Typed, tested, linted Python | Pass | New code gets type hints, unit tests, ruff and mypy |
| Verification gates | Pass | Focused unit tests plus full suite |
| Security: no secrets in artifacts | Pass | No data handled beyond headings |

No violations. Re-checked after design: still no violations.

## Project Structure

### Documentation (this feature)

```text
specs/025-compliance-plugin-pack/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/plugin-pack.md
└── tasks.md            (created by /speckit-tasks)
```

### Source Code

```text
speckit_flow/sensors.py                       # section builtin + profiles scope
.specify/plugins/compliance/
├── plugin.json                               # enabled: false
├── profiles/compliance.json
├── sensors.json
├── agents.json
└── README.md
.github/agents/speckit-compliance-reviewer.agent.md
.github/agents/speckit-conductor.agent.md     # list the new agent
tests/unit/speckit_flow/test_flow_compliance_pack.py
docs/speckit-profiles.md
```

**Structure Decision**: Keep the pack as data; only the two generic sensor features touch code.
