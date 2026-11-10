# Tasks: Walking Skeleton

## Phase 1: Setup
- [X] T001 Confirm governance/hooks and approved verification in `specs/030-walking-skeleton/quickstart.md`.

## Phase 2: Foundation
- [X] T002 Write tracked-file and checkpoint tests in `tests/unit/speckit_flow/test_flow_skeleton.py`: maximum 100 files, each <=1 MiB, safe root-relative paths.
- [X] T003 Add optional tracked files, source-bound checkpoints and preservation-on-add in `speckit_flow/units.py`; expose `--files` in `speckit_flow/cli.py`.

## Phase 3: US1 - Thin slice first (P1)
Goal: skeleton checkpoint before full implementation.
Independent test: opted-in route blocks implementation until a human decision.
- [X] T004 [US1] Test skeleton unit/actual tasks/report/current checkpoint rules in `tests/unit/speckit_flow/test_flow_skeleton.py`.
- [X] T005 [US1] Add skeleton builtin, metadata/command/file fingerprints and gate checks in `speckit_flow/sensors.py` and `speckit_flow/units.py`.
- [X] T006 [US1] Add disabled stage/profile/sensor/template pack under `.specify/plugins/walking-skeleton/`.

## Phase 4: US2 - Current evidence (P2)
Goal: no stale or failed evidence reuse; explicit limits.
Independent test: mutate source/test/report/command or fail a recheck; gate refuses.
- [X] T007 [US2] Test failure invalidation, changes during verification and sensor freshness in `tests/unit/speckit_flow/test_flow_skeleton.py`.
- [X] T008 [US2] Add `.github/skills/speckit-skeleton/SKILL.md`, developer/conductor guidance and documentation in `docs/speckit-profiles.md`.

## Phase 5: US3 - Portable reuse (P3)
Goal: unrelated project verifies exact input-to-output behavior.
Independent test: installed reading-list entry point yields exact expected JSON.
- [X] T009 [US3] Add installed-project acceptance in `tests/unit/test_speckit_bootstrap.py`.
- [X] T010 [US3] Add exact pack/skill allowlist entries in `scripts/speckit-portable-bundle.json` and update `docs/speckit-portability.md`.

## Phase 6: Validation
- [X] T011 Run approved pytest/lint/types/doctor and `graphify update .`, recording results in `specs/030-walking-skeleton/quickstart.md`.

## Dependencies and parallel opportunities

T001 -> T002 -> T003. T003 -> T004 -> T005 -> T006. T003 -> T007.
T006 -> T008. T006 + T008 -> T009 -> T010. All -> T011.
After T006, T007 (tests) and T008 (guidance) can proceed independently.
MVP: US1's skeleton gate; then harden evidence invalidation and prove portability.
All tasks use checklist IDs/paths; no implementation task bypasses the test tasks.
