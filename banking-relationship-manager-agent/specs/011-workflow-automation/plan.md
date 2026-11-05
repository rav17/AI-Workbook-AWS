# Implementation Plan: Spec Kit Workflow Automation

**Branch**: `011-workflow-automation` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-workflow-automation/spec.md`

## Summary

Wire the current Spec Kit workflow into the lifecycle helper without changing its four-stage order or supported integrations. A new deterministic `workflow begin` CLI operation initializes state once, verifies audit integrity and confirms that the static workflow route matches the selected profile. After the specify command creates the feature directory, workflow shell steps record the specify start/completion before the first gate. Additional shell steps start and complete plan, tasks and implement. Existing engine approval gates branch on approve/reject to record the corresponding lifecycle decision, with rejection audited before stopping. Reviews remain source-bound and gate approval remains enforced by the existing helper.

## Technical Context

**Language/Version**: Python 3.11+ for the lifecycle CLI; YAML workflow and Markdown skill files

**Primary Dependencies**: Standard library for `speckit_flow`; installed Spec Kit workflow engine (existing dependency)

**Storage**: Existing per-feature `state.json`, `state.md`, `audit.jsonl`, review JSON files, and `.specify/feature.json`

**Testing**: pytest; YAML parsing (PyYAML is already used optionally by profile tests); installed `specify` workflow validator for end-to-end syntax validation

**Target Platform**: Windows and POSIX developer environments supported by Spec Kit

**Project Type**: Local Python CLI / workflow configuration and agent skill

**Performance Goals**: Lifecycle preflight and each state transition complete in under 1 second for normal feature state files

**Constraints**: Preserve the workflow's specify → plan → tasks → implement order; do not mark a stage complete on failure; do not bypass review-aware gate enforcement; no shell interpolation of free-text input; legacy state and audit remain readable

**Scale/Scope**: One standard workflow route and its two existing gates; other profiles remain managed by `speckit-profile`

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Structured state authoritative | PASS: `speckit_flow` remains the only writer of lifecycle state and audit; workflow shell steps call its CLI. |
| II. Deterministic safety | PASS: profile match, transition order, review freshness, block override and gate authorization remain validated in code. |
| III. Patch, validate, invalidate | PASS: no transactional values are introduced; reviews continue to invalidate when source fingerprints change. |
| IV. Bounded context and tool use | PASS: workflow stages and reviews stay bounded; no additional conversation history is persisted. |
| V. Durable boundaries and session isolation | PASS: lifecycle remains feature-local and version-controlled; no conversation state is authoritative. |
| VI. Python quality and operational readiness | PASS: typed CLI helpers, focused unit tests, ruff and mypy validation are required. |
| Security and compliance | PASS: fixed shell arguments only; free-text gate reasons are not interpolated into shell commands; audit details remain redaction-checked. |

No constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/011-workflow-automation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   └── workflow.md
└── tasks.md
```

### Source Code (repository root)

```text
speckit_flow/
├── cli.py                         # workflow begin command and route/audit preflight
└── state.py                       # deterministic preflight helper

.specify/
└── workflows/speckit/workflow.yml # lifecycle wrappers and audited gate branches

docs/speckit-profiles.md                  # explain automatic standard-workflow tracking

tests/unit/speckit_flow/
└── test_flow_workflow.py            # preflight, route mismatch, state/audit, workflow structure
```

**Structure Decision**: Extend existing `speckit_flow` CLI/state modules and update the one workflow and skill already responsible for the standard path. Avoid adding a separate orchestration package or dependency.

## Complexity Tracking

None.
