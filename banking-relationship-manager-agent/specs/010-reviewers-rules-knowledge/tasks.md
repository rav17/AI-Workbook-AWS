# Tasks: Reviewers, Learned Rules, Team Knowledge and Extended Stages

**Input**: Design documents in `specs/010-reviewers-rules-knowledge/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, quickstart.md
**Tests**: included (constitution requires pytest, ruff, mypy)

Format: `- [ ] T### [P] [US#] description with file path`

## Phase 1: Setup

- [x] T001 Create `.specify/knowledge/`, `.specify/rules/` folders and empty `.specify/rules/rules.json` (`{"rules": []}`)
- [x] T002 [P] Add starter knowledge docs `.specify/knowledge/README.md` and `.specify/knowledge/banking-compliance.md` (with `title:` and `stages:` lines)

## Phase 2: Foundational (blocks all stories)

- [x] T003 Extend `speckit_flow/models.py`: stage order `ideation, specify, clarify, plan, tasks, analyze, implement, deploy, operate`; validation (ideation may precede specify; deploy requires implement; operate requires deploy); keep all 009 profiles valid
- [x] T004 Extend `EVENT_TYPES` in `speckit_flow/models.py` with `review_recorded`, `gate_overridden`, `rule_proposed`, `rule_approved`, `rule_discarded`, `route_composed`
- [x] T005 [P] Add dataclasses `Finding`, `Review`, `Rule`, `KnowledgeDoc`, `Route` to `speckit_flow/models.py` per data-model.md
- [x] T006 [P] Update stage enums in `specs/010-reviewers-rules-knowledge/contracts` consumers and the 009 `contracts/profile.schema.json` copy if shipped under `.specify/`
- [x] T007 [P] Regression test that all 009 profiles and a 009 audit trail still validate in `tests/unit/speckit_flow/test_flow_compat.py`

## Phase 3: User Story 1 - Source-bound reviews gate approvals (P1) 🎯 MVP

**Goal**: reviews with cited findings, fingerprint staleness, review-aware gate approval.
**Independent test**: record a block review, approval is refused without `--override-reason`; editing a reviewed file makes the review stale.

- [x] T008 [P] [US1] Tests in `tests/unit/speckit_flow/test_flow_reviews.py`: blocker forces `block`; `pass` invalid with major/blocker; empty findings only on `pass`; reviewer != author; note max 500 chars and redaction; file must be in `files`; stale detection; id increments per stage
- [x] T009 [P] [US1] Tests in `tests/unit/speckit_flow/test_flow_gate_review.py`: comprehensive depth requires a non-stale review; `block` needs `--override-reason` and emits `gate_overridden`; approval detail includes `review=<id>`
- [x] T010 [US1] Implement `speckit_flow/reviews.py`: validate, save to `<feature>/reviews/<stage>-<n>.json`, fingerprint, staleness, latest review
- [x] T011 [US1] Extend `speckit_flow/state.py` gate approval to be review-aware and audit `review_recorded` / `gate_overridden` (audit before state change)
- [x] T012 [US1] Add CLI commands `review record|list|show|check` and `gate approve --override-reason` to `speckit_flow/cli.py` per contracts/cli.md
- [x] T013 [P] [US1] Create skill `.github/skills/speckit-review/SKILL.md` (spec/plan/code reviewer roles, citation rules)
- [x] T014 [P] [US1] Validate sample payloads against `specs/010-reviewers-rules-knowledge/contracts/review.schema.json` in test_flow_reviews.py

## Phase 4: User Story 2 - Learned rules and team knowledge (P2)

**Goal**: humans approve learned rules; active rules and knowledge titles surface per stage with bounded context.
**Independent test**: agent proposal stays pending; `agent:` approval refused; `human:` approval activates; list capped at 10.

- [x] T015 [P] [US2] Tests in `tests/unit/speckit_flow/test_flow_rules.py`: id `R-nnn`; text 1-300 chars and redaction; transitions pending→active/discarded, active→discarded only; human-only decisions; stage list cap 10; conflict flag
- [x] T016 [P] [US2] Tests in `tests/unit/speckit_flow/test_flow_knowledge.py`: title/stages parsing, defaults, titles and paths only
- [x] T017 [US2] Implement `speckit_flow/rules.py` (propose, approve, discard, list active per stage, conflict flag) with audit events
- [x] T018 [P] [US2] Implement `speckit_flow/knowledge.py` (index `.specify/knowledge/*.md`, list per stage)
- [x] T019 [US2] Add CLI `rules propose|approve|discard|list` and `knowledge list` to `speckit_flow/cli.py`
- [x] T020 [P] [US2] Create skill `.github/skills/speckit-learn/SKILL.md`

## Phase 5: User Story 3 - Composer for custom routes (P3)

**Goal**: validate and save a custom route with reasons per stage.
**Independent test**: invalid route rejected with same errors as profiles; valid route saved only with `--confirm`.

- [x] T021 [P] [US3] Tests in `tests/unit/speckit_flow/test_flow_compose.py`: validation parity with profiles, `reasons` entry for every stage, `--confirm` required, `custom-<feature>` id, `route_composed` audited, `init --route-file`
- [x] T022 [US3] Implement `speckit_flow/compose.py` and route.json loading in `speckit_flow/state.py`
- [x] T023 [US3] Add CLI `compose validate|save --confirm` and `init --route-file` to `speckit_flow/cli.py`
- [x] T024 [P] [US3] Create skill `.github/skills/speckit-compose/SKILL.md`

## Phase 6: User Story 4 - Extended stages (P3)

**Goal**: ideation, deploy, operate available through profiles.
**Independent test**: `full-lifecycle` profile validates and runs end to end.

- [x] T025 [P] [US4] Tests in `tests/unit/speckit_flow/test_flow_stages.py`: ordering and dependency rules, full-lifecycle valid, bad orders rejected
- [x] T026 [P] [US4] Add `.specify/profiles/full-lifecycle.json`
- [x] T027 [P] [US4] Add templates `.specify/templates/ideation.md`, `release.md`, `runbook.md`

## Phase 7: Polish

- [x] T028 Update `.github/skills/speckit-profile/SKILL.md` for review, knowledge, rules steps
- [x] T029 [P] Extend `docs/speckit-profiles.md` with reviews, rules, knowledge, composer, extended stages
- [x] T030 Run `ruff check`, `mypy speckit_flow` and `pytest tests/unit`; fix issues
- [x] T031 Walk through `specs/010-reviewers-rules-knowledge/quickstart.md` in a scratch directory
- [x] T032 Run `graphify update .`

## Dependencies

Setup → Foundational → US1 (MVP) → US2, US3, US4 (independent of each other after Foundational; US3 uses state.py changes after US1) → Polish.

## Parallel examples

- Foundational: T005, T006, T007 together.
- US1: T008, T009, T013, T014 before/alongside T010.
- US2: T015, T016, T018, T020 together.

## Strategy

MVP = Phases 1-3 (reviews + gating). Then add US2, US3, US4 incrementally, running the full unit suite after each.
