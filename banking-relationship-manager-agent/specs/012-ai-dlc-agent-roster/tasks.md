# Tasks: AI-DLC Agent Roster

**Input**: Design documents in `/specs/012-ai-dlc-agent-roster/`
**Tests**: Required (constitution VI).

## Phase 1: Setup

- [x] T001 Create `.specify/agents/roster.json` with the 14 agents, the conductor, roles, tiers and stage ownership from research.md
- [x] T002 [P] Create the 14 roster agent files `.github/agents/speckit-<id>.agent.md` per contracts/agent-files.md
- [x] T003 [P] Create `.github/agents/speckit-conductor.agent.md` listing all roster agents in `agents:`

## Phase 2: Foundational

- [x] T004 Add optional `assignments` field with shape validation to `Profile` in `speckit_flow/models.py` (round-trips through `to_dict`)
- [x] T005 Create `speckit_flow/agents.py`: load roster, validate roster against files and tool scopes, resolve assignments, check agent actors
- [x] T006 Make `decide_gate` in `speckit_flow/state.py` refuse non-human actors (audited as a failure)

## Phase 3: User Story 1 - Roster (P1)

- [x] T007 [P] [US1] Tests in `tests/unit/speckit_flow/test_flow_agents.py`: 14 agents (11/2/1) plus conductor, unique names, files exist, reviewers lack `edit`, domain agents lack `agent`, conductor allow-list complete
- [x] T008 [US1] Add `agents list` and `agents validate` to `speckit_flow/cli.py`

## Phase 4: User Story 2 - Stage assignments (P2)

- [x] T009 [P] [US2] Tests: every stage of every shipped profile resolves one lead; unknown agent and stage-outside-route in `assignments` are rejected; legacy profile unchanged
- [x] T010 [US2] Add `agents assign` to the CLI and include the lead agent in `status` output

## Phase 5: User Story 3 - Audit attribution and enforcement (P3)

- [x] T011 [P] [US3] Tests: known agent actor accepted for stage start/done and review save; unknown agent refused; agent gate approve/reject refused; rule approve refused
- [x] T012 [US3] Validate `agent:<id>` actors against the roster in the CLI
- [x] T013 [P] [US3] Create `scripts/speckit_guard.py` and `.github/hooks/speckit-guard.json` per contracts/hook.md
- [x] T014 [P] [US3] Tests in `tests/unit/speckit_flow/test_flow_guard.py`: deny gate/rule decisions and writes to audit/state/rules files; allow status, review save, rules propose, stage commands; unparseable input allows

## Phase 6: Polish

- [x] T015 [P] Update stage skills (`speckit-profile`, `speckit-review`, `speckit-compose`) to name lead agents and the conductor
- [x] T016 [P] Add a 012 section to `docs/speckit-profiles.md`
- [x] T017 Run `ruff format`, `ruff check`, `mypy speckit_flow`, `pytest tests/unit`
- [x] T018 Walk through quickstart.md in a scratch folder
- [x] T019 Run `graphify update .`

## Dependencies

T001-T003 → T005 → T007-T012. T004 → T009/T010. T013 → T014. T017-T019 last.
