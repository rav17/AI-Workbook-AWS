# Implementation Plan: Reviewers, Learned Rules, Team Knowledge and Extended Stages

**Branch**: `010-reviewers-rules-knowledge` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-reviewers-rules-knowledge/spec.md`

## Summary

Extend the `speckit_flow` helper from feature 009 with: review records (source-bound, fingerprinted) that gate approvals, a rules store with human-approved learning, a knowledge folder index, a composer that validates and saves custom routes, and three optional stages (`ideation`, `deploy`, `operate`). Agent behaviour (writing reviews, proposing rules, composing routes) lives in new skills; deterministic validation, storage and gating live in code.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: standard library only (same as 009)

**Storage**: files: `<feature>/reviews/<stage>-<n>.json`, `<feature>/route.json` (composed route), `.specify/rules/rules.json`, `.specify/knowledge/*.md`

**Testing**: pytest in `tests/unit/speckit_flow/`

**Target Platform**: developer workstation / CI, Windows and POSIX

**Project Type**: library + CLI dev tooling, separate from the Aria runtime

**Performance Goals**: each command under 1 second

**Constraints**: backward compatible with 009 state and audit files; every action audited; no secrets in rules, knowledge indexes or reviews

**Scale/Scope**: tens of rules, tens of knowledge documents, a few reviews per stage

## Constitution Check

| Principle | Assessment |
|-----------|------------|
| I. Structured state authoritative | PASS: reviews, rules and routes are typed, validated records; code owns gating, not the agent. |
| II. Deterministic safety | PASS: citation requirement, block-override, self-review prohibition and rule activation are enforced in code, not in prompts. |
| III. Patch/validate/invalidate | PASS (adapted): a changed content fingerprint marks a review stale, which invalidates it for gating. |
| IV. Bounded context | PASS: only active rules relevant to a stage, capped, and knowledge titles (not bodies) are surfaced. |
| V. Durable boundaries | PASS: everything persists in version-controlled files. |
| VI. Python quality | PASS: type hints, explicit validation, UTC timestamps, pytest, ruff/mypy. Dataclasses instead of Pydantic as in 009. |
| Security: audit events | PASS: events carry ids and verdicts only; shared redaction check applied to rules, review notes and overrides. |

No violations. Re-checked after design: passing.

## Project Structure

### Documentation (this feature)

```text
specs/010-reviewers-rules-knowledge/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cli.md
│   ├── review.schema.json
│   └── rule.schema.json
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
speckit_flow/
├── models.py            # extend: new stages, Review/Finding/Rule/Route dataclasses
├── reviews.py           # NEW: validate, save, fingerprint, staleness, latest review
├── rules.py             # NEW: propose, approve, discard, list active, conflict flag
├── knowledge.py         # NEW: index knowledge docs, list consulted per stage
├── compose.py           # NEW: validate and save composed route
├── state.py             # extend: review-aware gate approval, route.json support
├── audit.py             # extend: new event types, shared redaction
└── cli.py               # extend: review, rules, knowledge, compose commands

.specify/knowledge/      # team standards (starter README + banking compliance note)
.specify/rules/rules.json
.specify/profiles/       # new example: full-lifecycle.json (all stages)
.github/skills/speckit-review/SKILL.md     # spec/plan/code reviewer roles
.github/skills/speckit-learn/SKILL.md      # propose rules, human approves
.github/skills/speckit-compose/SKILL.md    # composer
.github/skills/speckit-profile/SKILL.md    # update: review, knowledge, rules steps
tests/unit/speckit_flow/
```

**Structure Decision**: keep one package and add focused modules; stage extensions are data (profile files + stage list), so 009 profiles stay valid unchanged.

## Complexity Tracking

None.
