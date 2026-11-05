# Tasks: Workflow Profiles and Audit Trail

**Input**: Design documents from `/specs/009-workflow-profiles-audit/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. The constitution requires focused unit tests for state transitions and validators.

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

## Phase 1: Setup

- [x] T001 Create package skeleton `speckit_flow/__init__.py` and `speckit_flow/__main__.py` (calls `cli.main`), plus `tests/unit/speckit_flow/__init__.py`
- [x] T002 [P] Ensure `speckit_flow` is covered by the existing ruff/mypy config in `pyproject.toml` and excluded from Lambda/runtime artifacts in `scripts/build_artifacts.py`

## Phase 2: Foundational (blocks all stories)

- [x] T003 Define `Profile`, `FeatureState`, `StageStatus`, `AuditEvent` dataclasses and enums in `speckit_flow/models.py` per data-model.md (stage names `specify, clarify, plan, tasks, analyze, implement`; depth `minimal|standard|comprehensive`; event types per data-model.md; actor pattern `^(human|agent):.+`; detail max 500 chars)
- [x] T004 [P] Implement atomic JSON write helper (temp file + `os.replace`) and UTC tz-aware timestamp helper in `speckit_flow/state.py`
- [x] T005 [P] Implement feature-dir resolution from `.specify/feature.json` and `--feature-dir` in `speckit_flow/cli.py` (argparse skeleton with `--json`, one-line errors, non-zero exit)

## Phase 3: User Story 1 - Workflow profiles (P1) MVP

**Goal**: Choose, validate, list and suggest profiles; default `feature` equals current workflow.

**Independent Test**: `profiles validate` passes for all 8 profiles; `init --profile bugfix` skips omitted stages; unknown profile lists valid ones and fails.

- [x] T006 [P] [US1] Unit tests for profile validation (specify first; `plan` requires `specify`; `implement` requires `tasks` unless `implement-without-tasks` exempt; no duplicates; gates subset of stages; unknown fields rejected; id matches filename) in `tests/unit/speckit_flow/test_profiles.py`
- [x] T007 [P] [US1] Unit tests for `suggest` (bug, CVE, refactor, terraform/infra, default `feature`) and that `feature` route/gates equal `.specify/workflows/speckit/workflow.yml` in `tests/unit/speckit_flow/test_suggest.py`
- [x] T008 [P] [US1] Create profile files `feature.json`, `enterprise.json`, `express.json`, `bugfix.json`, `refactor.json`, `infra.json`, `security-patch.json`, `poc.json` in `.specify/profiles/` per research.md D3
- [x] T009 [US1] Implement profile loading and validation (reject invalid with clear message) in `speckit_flow/profiles.py` (depends on T003, T008)
- [x] T010 [US1] Implement deterministic keyword `suggest` in `speckit_flow/profiles.py` (advisory, default `feature`)
- [x] T011 [US1] Implement `profiles list|validate|suggest` commands in `speckit_flow/cli.py`
- [x] T012 [US1] Implement `init --profile` (default `feature`, unknown id lists valid profiles and exits non-zero) creating `state.json` with omitted stages marked `skipped` with reason in `speckit_flow/state.py` and `speckit_flow/cli.py`

## Phase 4: User Story 2 - Persistent feature state (P2)

**Goal**: State survives sessions; resume, switch, rebuild.

**Independent Test**: init, complete plan, new process `resume` reports next stage; delete `state.json` then `rebuild` restores it.

- [x] T013 [P] [US2] Unit tests for transitions (pendingâ†’in_progressâ†’done, out-of-order rejected, gate sets `pending_gate`, `switch` rejected mid-stage or without `--confirm`, completed stages kept on switch, revision increments) in `tests/unit/speckit_flow/test_state.py`
- [x] T014 [P] [US2] Unit tests for resume with missing/corrupt `state.json` and `rebuild` from `spec.md`/`plan.md`/`tasks.md` in `tests/unit/speckit_flow/test_resume.py`
- [x] T015 [US2] Implement state transitions (`stage start|done`, `gate approve|reject`, `switch`) with revision counter in `speckit_flow/state.py`
- [x] T016 [US2] Implement `state.md` rendering (profile, current/next stage, pending gate, skipped reasons) in `speckit_flow/state.py`
- [x] T017 [US2] Implement `status`, `resume`, `rebuild` and `stage`, `gate`, `switch` commands in `speckit_flow/cli.py`

## Phase 5: User Story 3 - Append-only audit trail (P2)

**Goal**: Every event is recorded, ordered, tamper-evident.

**Independent Test**: run approve and reject gates; `audit.jsonl` has ordered events with increasing `seq`; editing a middle line is detected by `status`.

- [x] T018 [P] [US3] Unit tests for audit (seq increments, prev_hash chain, append-only file mode, tamper detection, concurrent-feature isolation, secret/PII-pattern rejection, write failure leaves state unchanged) in `tests/unit/speckit_flow/test_audit.py`
- [x] T019 [US3] Implement append-only writer (read last line only; `seq`, `prev_hash` SHA-256; open with `"a"`) and chain verification in `speckit_flow/audit.py`
- [x] T020 [US3] Implement redaction check (AWS keys, bearer tokens, long hex/base64, account-number-like digit runs) in `speckit_flow/audit.py`
- [x] T021 [US3] Wire every state change to audit-first-then-state ordering and emit events (`profile_selected`, `profile_changed`, `stage_started`, `stage_completed`, `stage_skipped`, `gate_approved`, `gate_rejected`, `failure`) in `speckit_flow/state.py`
- [x] T022 [US3] Make `status` verify the hash chain and report the first broken line in `speckit_flow/cli.py`

## Phase 6: Workflow integration and polish

- [x] T023 Create `.github/skills/speckit-profile/SKILL.md` (select/suggest, confirm, switch, call CLI at stage boundaries, never run before confirmation)
- [x] T024 Skill-driven fallback (research.md D5) chosen: `.specify/workflows/speckit/workflow.yml` is intentionally unchanged so default behaviour stays identical; the `speckit-profile` skill drives profile gating
- [x] T025 [P] Document usage in `docs/` (new `docs/speckit-profiles.md`) and link from `README.md`
- [x] T026 Run `ruff`, `mypy` and `pytest tests/unit/speckit_flow -q`, then walk through `specs/009-workflow-profiles-audit/quickstart.md`
- [x] T027 Run `graphify update .` to refresh the knowledge graph

## Dependencies

- Phase 1 â†’ Phase 2 â†’ stories. US1 (MVP) first; US2 depends on US1 `init`; US3 audit writer (T019, T020) can start after Phase 2, but T021 needs T015.
- Phase 6 needs US1â€“US3.

## Parallel Examples

- T004 and T005; T006, T007 and T008; T013 and T014; T018 alongside T015.

## Implementation Strategy

MVP = Phase 1â€“3 (profiles usable via `init`). Then US2, then US3, then integration.
