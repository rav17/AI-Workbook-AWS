# Tasks: Profile-Aware Workflow Orchestration

**Input**: [spec.md](./spec.md), [plan.md](./plan.md) and design artifacts.
**Tests**: Required, including portability and actual bounded host invocation.

## Phase 1: Setup

- [x] T001 Record approved routing policy and verification scope in `specs/032-profile-aware-orchestration/quickstart.md`.

## Phase 2: Foundation

- [x] T002 Reject model-disabled assigned agents in `speckit_flow/agents.py`.

## Phase 3: US1 - Select the right lifecycle

**Independent test**: Category matrix, explicit override, ambiguity, no mutations.

- [x] T003 [US1] Test category recommendations and CLI output in `tests/unit/speckit_flow/test_flow_orchestration.py` (FR-001, FR-002, FR-003).
- [x] T004 [US1] Implement transient recommendation with `confirmation_required` always true in `speckit_flow/orchestration.py`.
- [x] T005 [US1] Expose `workflow recommend` in `speckit_flow/cli.py`, preserving legacy commands.

## Phase 4: US2 - Assigned agent execution

**Independent test**: Profile-driven briefs and direct-skill handoff without
recursion; pending gates/parked state/audit/configuration failures block.

- [x] T006 [US2] Test dispatch guards, roles and profile overrides in `tests/unit/speckit_flow/test_flow_orchestration.py` (FR-004, FR-007, FR-008, FR-009, FR-010).
- [x] T007 [US2] Implement read-only dispatch brief in `speckit_flow/orchestration.py` and `speckit_flow/cli.py`.
- [x] T008 [US2] Add shared entry skill at `.github/skills/speckit-workflow/SKILL.md` and recursion-safe preambles in lifecycle stage skills (FR-006).
- [x] T009 [US2] Update `.github/agents/speckit-conductor.agent.md` for preflight, read-only contributions, independent reviews and explicit failures.
- [x] T010 [US2] Route `.specify/workflows/speckit/workflow.yml` through the shared entry point and update obsolete static-route assertions in workflow/profile tests (FR-005).
- [x] T011 [US2] Validate installed-engine dispatch and bounded real host subagents; record evidence in `specs/032-profile-aware-orchestration/quickstart.md` (FR-012).

## Phase 5: US3 - Portable integration

**Independent test**: Non-banking install contains shared routing with no inherited approvals.

- [x] T012 [US3] Update `.github/copilot-instructions.md`, `.github/instructions/speckit-workflow.instructions.md`, and portable bundle allowlist for routing (FR-011).
- [x] T013 [US3] Extend `tests/unit/test_speckit_bootstrap.py` for installed recommendation/preflight/handoff behavior.
- [x] T014 [US3] Update `docs/speckit-profiles.md` and `docs/speckit-portability.md` with routing, resume and evidence boundaries.

## Phase 6: Validation

- [x] T015 Run approved verification and record exact results in `specs/032-profile-aware-orchestration/quickstart.md`.
- [x] T016 Run `graphify update .`, inspect feature-scoped diff and preserve unrelated edits.

## Dependencies and parallel opportunities

T002 precedes T006/T007. T003 precedes T004/T005. T006 precedes T007.
T007 precedes T008/T009/T010; T008 and T009 are separate-file opportunities.
T008/T009/T010 precede T011. T012 precedes T013. T014 depends on T010/T012.
All implementation tasks precede T015/T016.

## Implementation Strategy

Recommendation first, then guarded host handoff, then standard/portable wiring.
No new verification approval, production deployment, plugin enablement or commit.
