# Tasks: Operational Readiness

## Phase 1: Setup
- [X] T001 Confirm governance, hook absence and approved validation in `specs/029-operational-readiness/quickstart.md`.

## Phase 2: Foundation
- [X] T002 Add record-validation tests in `tests/unit/speckit_flow/test_flow_readiness.py`: UTF-8 regular files, 256 KiB limit, placeholders/comments/code/unchecked tasks excluded.
- [X] T003 Implement fixed-record parser and hashing in `speckit_flow/readiness.py`.

## Phase 3: US1 - Evidence-backed release (P1)
Goal: Required release/runbook structure blocks incomplete deploy decisions.
Independent test: missing/evidence-only/template records fail, complete records pass.
- [X] T004 [US1] Test readiness registration/scoping and gate failures in `tests/unit/speckit_flow/test_flow_readiness.py`.
- [X] T005 [US1] Integrate builtin and sensor-specific fingerprints in `speckit_flow/sensors.py`, preserving existing sensor behavior.
- [X] T006 [US1] Add disabled profile, sensor and templates under `.specify/plugins/operational-readiness/`.

## Phase 4: US2 - Operational handoff (P2)
Goal: Human-reviewed operational procedures, current local evidence.
Independent test: release/runbook edits/deletion stale passing deploy/operate results.
- [X] T007 [US2] Test stale/access-failure outcomes in `tests/unit/speckit_flow/test_flow_readiness.py`.
- [X] T008 [US2] Add `.github/skills/speckit-readiness/SKILL.md` and wire conductor/deploy/operations agent guidance under `.github/agents/`.

## Phase 5: US3 - Portable adoption (P3)
Goal: Unrelated project opts in, no default/cloud/domain changes.
Independent test: installed-project lifecycle checks both gates and human-only decisions.
- [X] T009 [US3] Extend installed-project tests in `tests/unit/test_speckit_bootstrap.py`.
- [X] T010 [US3] Add exact module/skill/plugin allowlist entries in `scripts/speckit-portable-bundle.json`.
- [X] T011 [US3] Document enablement, evidence limits and ownership in `docs/speckit-profiles.md`, `docs/speckit-portability.md` and plugin README.

## Phase 6: Validation
- [X] T012 Run approved tests/lint/types/doctor and `graphify update .`; record evidence in `specs/029-operational-readiness/quickstart.md`.

## Dependencies and parallel opportunities

T001 -> T002 -> T003. T003 -> T004 -> T005 -> T006. T005 -> T007.
T006 -> T008. T006 + T008 -> T009 -> T010 -> T011. All -> T012.
After T006, T007 (tests) and T008 (guidance) can proceed independently.
After T010, documentation can proceed while validation runs.

MVP: US1's deploy evidence checks. Add operate handoff and staleness tests,
then verify the portable installed project. All test tasks precede their
corresponding implementation or integration.
