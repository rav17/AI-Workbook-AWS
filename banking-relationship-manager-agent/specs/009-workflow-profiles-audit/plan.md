# Implementation Plan: Workflow Profiles and Audit Trail

**Branch**: `009-workflow-profiles-audit` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-workflow-profiles-audit/spec.md`

## Summary

Add AI-DLC-inspired workflow profiles, per-feature state and an append-only audit trail to the Spec Kit workflow. Profiles are JSON files under `.specify/profiles/`. A small stdlib-only Python helper (`speckit_flow`) validates profiles, resolves a stage route, updates `state.json` and appends to `audit.jsonl` in the feature directory. A new `speckit-profile` skill and a profile-aware workflow call the helper; the default `feature` profile reproduces today's route and gates.

## Technical Context

**Language/Version**: Python 3.11+ (matches project)

**Primary Dependencies**: standard library only (json, argparse, dataclasses, datetime, hashlib, pathlib)

**Storage**: files in the feature directory: `state.json` (+ rendered `state.md`) and `audit.jsonl`

**Testing**: pytest (unit tests in `tests/unit/speckit_flow/`)

**Target Platform**: developer workstation / CI, Windows and POSIX

**Project Type**: library + CLI tooling for the dev workflow (not part of the Aria runtime or Lambda artifacts)

**Performance Goals**: each helper command completes in under 1 second

**Constraints**: append-only audit, atomic state writes, no secrets or customer data in events, no behavior change for the default profile

**Scale/Scope**: about 8 profiles, 6 stages, hundreds of events per feature

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Structured state authoritative | PASS: state is a typed model persisted in a file; code, not the LLM, owns transitions. |
| II. Deterministic safety | PASS: route validation, mid-run change rules and append-only guarantees are enforced in code. |
| III. Patch/validate/invalidate | PASS (adapted): profile change validates and keeps completed stages; no dependent-value invalidation needed. |
| IV. Bounded context | PASS: state.md gives compact resume context. |
| V. Durable boundaries | PASS: state persisted in files, independent of conversation. |
| VI. Python quality | PASS: type hints, dataclasses with explicit validation, tz-aware UTC timestamps, pytest, ruff/mypy via existing config. Pydantic not used because the tool is stdlib-only and its inputs are repository-owned files; documented simpler choice. |
| Security: audit events | PASS: events carry safe metadata only; a redaction check rejects obvious secret patterns (FR-013). |

No violations; Complexity Tracking not needed. Re-checked after design: still passing.

## Project Structure

### Documentation (this feature)

```text
specs/009-workflow-profiles-audit/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── profile.schema.json
│   └── audit-event.schema.json
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
speckit_flow/
├── __init__.py
├── models.py            # Profile, FeatureState, AuditEvent dataclasses + validation
├── profiles.py          # load/validate profiles, resolve route, suggest profile
├── state.py             # read/write state.json, render state.md, resume
├── audit.py             # append-only writer, hash chain, redaction check
└── cli.py               # `python -m speckit_flow ...`

.specify/profiles/       # express, feature, enterprise, bugfix, refactor, infra, security-patch, poc (.json)
.github/skills/speckit-profile/SKILL.md   # select/confirm/switch profile, record events
.specify/workflows/speckit/workflow.yml   # accepts `profile` input, calls helper

tests/unit/speckit_flow/
```

**Structure Decision**: a top-level `speckit_flow` package keeps dev tooling separate from the `aria` runtime so it is excluded from Lambda/runtime build artifacts. Profiles are data, so teams add one by dropping a JSON file.

## Complexity Tracking

None.
