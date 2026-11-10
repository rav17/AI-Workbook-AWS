# Tasks: Existing-Codebase Analysis

## Phase 1: Setup
- [X] T001 Confirm feature context, hooks and governance in `.specify/memory/constitution.md`.

## Phase 2: Foundation
- [X] T002 Add condition validation tests in `tests/unit/speckit_flow/test_flow_codebase.py`: only `existing-codebase`, optional only, never gated.
- [X] T003 Add the validated condition field in `speckit_flow/stagedefs.py` and profile checks in `speckit_flow/models.py`.

## Phase 3: US1 - Ground an existing project (P1)
Goal: inventory recognized files; architect reports evidence, never assumed test results.
Independent test: source/test/manifest fixture, bounded scan, CLI JSON.
- [X] T004 [US1] Write scanner/CLI tests in `tests/unit/speckit_flow/test_flow_codebase.py`.
- [X] T005 [US1] Implement path-only bounded inventory in `speckit_flow/codebase.py`: at most 10,000 entries, explicit errors, no symlink traversal.
- [X] T006 [US1] Add read-only `codebase scan` command in `speckit_flow/cli.py`.
- [X] T007 [US1] Add `.github/skills/speckit-codebase/SKILL.md` and consume its evidence in architect, conductor and plan guidance under `.github/`.

## Phase 4: US2 - Skip greenfield work (P2)
Goal: audited applicability without approval bypass.
Independent test: pending gate blocks skip; source runs; tooling-only skips.
- [X] T008 [US2] Add conditional lifecycle tests in `tests/unit/speckit_flow/test_flow_codebase.py`.
- [X] T009 [US2] Apply condition after normal checks in `speckit_flow/state.py`; audit pending -> skipped without gate.
- [X] T010 [US2] Add disabled stage/profile pack under `.specify/plugins/codebase-analysis/`.

## Phase 5: US3 - Portable reuse (P3)
Goal: install and enable capability in unrelated project, no default changes.
Independent test: installed project subprocess validates brownfield route and skipped/running stages.
- [X] T011 [US3] Extend `scripts/speckit-portable-bundle.json` exact allowlist with scanner, skill and plugin files.
- [X] T012 [US3] Add installed-project acceptance test in `tests/unit/test_speckit_bootstrap.py`.

## Phase 6: Polish
- [X] T013 Document heuristic, opt-in and limits in `docs/speckit-profiles.md` and `docs/speckit-portability.md`.
- [X] T014 Run human-approved targeted tests, lint/types, doctor and `graphify update .`; record results in `specs/028-existing-codebase-analysis/quickstart.md`.

## Dependencies and parallel opportunities

T001 -> T002 -> T003. T004 -> T005 -> T006. T003 + T005 -> T008 -> T009 -> T010.
T007 and T006 can proceed independently after T005. T007 + T010 -> T011 -> T012.
T013 follows T010/T011; all implementation precedes T014.

MVP: US1 standalone inventory and semantic analysis. Incrementally add safe skips,
then portable enablement. Test tasks precede implementation in each story.
