# Tasks: Hybrid Plan Review

**Input**: [spec.md](./spec.md), [plan.md](./plan.md). The feature's development
route is `quick`; the new hybrid route is opt-in and separate.

## User Story 1: Opt in to independent plan review

**Independent test**: In a synthetic feature, select an eligible reviewer,
complete an inline plan, record an actual separate review invocation and its
source-bound result, and expose invocation outcome separately from verdict.

- [X] T001 [US1] Add focused selection, inline-plan dispatch and persisted-choice acceptance tests to `tests/unit/speckit_flow/test_flow_orchestration.py` and `tests/unit/speckit_flow/test_flow_profiles.py` (FR-001, FR-002, FR-008).
- [X] T002 [US1] Extend `speckit_flow/models.py`, `speckit_flow/orchestration.py` and `speckit_flow/state.py` with the opt-in route, operator-selected eligible reviewer, and durable confirmed selection without changing existing defaults (FR-001, FR-002, FR-008).
- [X] T003 [US1] Add call-accounting tests for inline lead, actual reviewer call, distinct outcome/verdict, duplicate prevention and bounded attempts in `tests/unit/speckit_flow/test_flow_calls.py` (FR-002, FR-003, FR-005, FR-007).
- [X] T004 [US1] Extend `speckit_flow/calls.py` and `speckit_flow/cli.py` for selected reviewer reservations, completion and safe invocation status with no invented inline-lead call (FR-002, FR-003, FR-005, FR-007, FR-010).
- [X] T005 [US1] Add `tests/unit/speckit_flow/test_flow_reviews.py` cases for matching plan fingerprint, separate invocation result and valid verdicts `pass`, `concerns`, `block` (FR-003, FR-004, FR-005).
- [X] T006 [US1] Integrate the selected reviewer, exact plan revision, review verdict and minimal input-evidence references using `speckit_flow/reviews.py` and `speckit_flow/cli.py`; never claim host evidence the host cannot establish (FR-003, FR-004, FR-005, FR-009, FR-010, FR-011).

## User Story 2: Preserve existing workflows

**Independent test**: Run unchanged existing profiles and confirm their stage
routes, assigned workers, reviews, sensors and gates remain unchanged.

- [X] T007 [US2] Add non-opt-in profile and gate regression cases in `tests/unit/speckit_flow/test_flow_profiles.py`, `tests/unit/speckit_flow/test_flow_orchestration.py` and `tests/unit/speckit_flow/test_flow_gate_review.py` (FR-001, FR-008).
- [X] T008 [US2] Add the separate opt-in hybrid configuration under `.specify/profiles/` and keep legacy profile files and defaults intact (FR-001, FR-002, FR-008).
- [X] T009 [US2] Update `scripts/speckit-portable-bundle.json`, `tests/unit/test_speckit_bootstrap.py` and `docs/speckit-portability.md` for any new portable configuration without exporting approvals or project rules (FR-001, FR-008, FR-011).

## User Story 3: Stop on untrustworthy review

**Independent test**: Exercise missing/invalid selection, unavailable or failed
reviewer, absent/unverified/inconsistent input evidence, malformed review and
stale plan; none can satisfy the hybrid review or bypass the human gate.

- [X] T010 [US3] Add failure and freshness acceptance tests in `tests/unit/speckit_flow/test_flow_calls.py`, `tests/unit/speckit_flow/test_flow_reviews.py` and `tests/unit/speckit_flow/test_flow_gate_review.py` for unavailable/failed calls, selection and boundary evidence, invalid/incomplete verdict, plan changes and gate enforcement (FR-002, FR-003, FR-004, FR-005, FR-007, FR-008).
- [X] T011 [US3] Implement fail-closed review input-evidence and freshness checks at stage completion and gate in `speckit_flow/calls.py`, `speckit_flow/reviews.py` and `speckit_flow/state.py`, with no silent substitution (FR-002, FR-003, FR-004, FR-005, FR-008, FR-009, FR-010).
- [X] T012 [US3] Add tests for the ten distinct plain-text status states and safe synthetic audit metadata in `tests/unit/speckit_flow/test_flow_orchestration.py` and `tests/unit/speckit_flow/test_flow_calls.py` (FR-006, FR-009, FR-010).
- [X] T013 [US3] Implement explicit status, reason, applicable finding/location/freshness and next action in `speckit_flow/cli.py` and `speckit_flow/orchestration.py` without storing raw prompts, sensitive data or changing retention/access policy (FR-006, FR-009, FR-010, FR-011).
- [X] T014 [US3] Update `.github/skills/speckit-workflow/SKILL.md` and `docs/speckit-profiles.md` with the opt-in host handoff, honest capability limitations, evidence requirements and ten-state accessibility procedure (FR-002, FR-003, FR-006, FR-008, FR-009, FR-010, FR-011).

## Verification and dependencies

- T001--T006 establish the opt-in path; T007--T009 ensure compatibility and
  portability; T010--T014 build on those interfaces and fail closed.
  Shared-file work is sequential; no parallel worker editing is required.
- From the project root, run
  `python -m pytest tests\unit\speckit_flow\test_flow_orchestration.py tests\unit\speckit_flow\test_flow_calls.py tests\unit\speckit_flow\test_flow_profiles.py tests\unit\speckit_flow\test_flow_reviews.py tests\unit\speckit_flow\test_flow_gate_review.py tests\unit\test_speckit_bootstrap.py -q`.
  Expect all selected tests to pass, covering the opt-in, unchanged paths,
  failure states, gate and portability acceptance cases. Run affected-file Ruff
  checks; broaden checks if shared behavior indicates regressions.
- A construction-checkpoint verification command requires separate human
  approval before execution. A named-reviewer smoke test on synthetic data must
  inspect actual host activity and input evidence; if the host cannot provide
  it, report the limitation and do not claim a successful hybrid review.
- The ten keyboard/screen-reader state checks require the actual host and
  appropriate assistive technology; text/unit tests alone do not prove them.
  Record each as passed, failed or not verified, never inferred.
- MVP is US1 plus the mandatory US2 compatibility and US3 fail-closed
  boundaries; a happy-path-only release would not meet the spec.

## Evidence integration verification

- Workflow regression run across reviews, gates, calls, orchestration and
  profiles: 156 passed, 2 skipped (optional `specify_cli` dependency absent).
- After final review validation/test changes: 43 passed across the complete
  review test file and portable installation/target-doctor test. These overlap
  the preceding run; do not sum them as unique tests.
- Affected-file Ruff lint and whitespace checks passed. No implementation
  extension hooks are configured.
- The approved real named-reviewer smoke invocation completed successfully.
  The adapter reader was checked against that actual recorded invocation,
  including its child input, timestamp wrapper, empty assistant frame,
  returned verdict and completion. The reader check supplied the previously
  recorded brief as its expectation; it is not an end-to-end live test of the
  new reservation/prompt/gate protocol.
- T012--T014 implementation and documentation are complete. No live plan-gate
  acceptance, keyboard/screen-reader acceptance, or speed/quality improvement
  is claimed. The ten-state accessibility table remains `Not verified` until
  the checks run in the actual host with keyboard-only interaction and
  assistive technology. Normal host/system instructions are outside the
  exposed child-user-input boundary; local records are operational evidence,
  not authentication.
- A later approved synthetic end-to-end attempt invoked the selected named
  reviewer, but the worker ran four tools despite the no-tool brief. The host
  adapter rejected the returned result, and no synthetic plan gate was reached.
  One worker command unintentionally saved a plan review in this real feature.
  That review file was removed with explicit human approval; its append-only
  audit event remains and must not be interpreted as valid review evidence.
  No automatic retry was made. A host-enforced no-tool worker boundary remains
  unverified.
- A separate `speckit-hybrid-plan-reviewer` now declares no tools; existing
  reviewers and confirmed selections are unchanged. Hybrid dispatch blocks
  reviewers with configured tools and requires separately human-confirmed host
  capability evidence. Each actual review's selected tools and observed calls
  are checked again. Synthetic regression: 133 passed, 2 skipped; portable
  installation: 1 passed. After the final gate-capability check, 18 focused
  roster/gate tests passed. These sets overlap. Ruff and whitespace checks
  passed. The new reviewer has not yet been discovered or invoked in the host,
  so actual empty-tool behavior and end-to-end acceptance remain unverified.
- Status reporting now distinguishes all ten specified states in plain text
  and JSON, keeps invocation outcome separate from verdict, displays only
  validated findings, explains stale evidence, and provides a reason and next
  action. Missing and invalid reviewer selection are reported during
  initialization; missing, unverified and inconsistent invocation-input
  evidence have separate dispatch states.
- Final affected regression across orchestration, calls and reviews: 143
  passed, 2 skipped because the optional `specify_cli` dependency is absent.
  Final focused tests after the last status assertions: 32 passed. Affected
  Ruff lint and whitespace checks passed. These test results do not prove
  actual-host accessibility or no-tool enforcement.
- The new named reviewer is not available in this host's callable-agent
  roster, so its no-tool capability and a full synthetic plan-gate journey
  remain unverified. No replacement reviewer was used. All ten actual-host
  keyboard/screen-reader checks remain `Not verified`; do not infer them from
  the unit tests or this documentation.
