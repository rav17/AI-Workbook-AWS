# Tasks: Virtual Account Receivables Exception Resolution Subagent

**Input**: Design documents from `/specs/004-receivables-exception-resolution/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/investigation-and-approval.md`, `quickstart.md`

## Phase 1: Setup

- [ ] T001 Define validated, versioned configuration schemas for the single-customer/single-currency scope, approved procedure, tolerance rules, matching weights, confidence thresholds, and authorized analyst roles; missing policy values MUST fail closed in `aria/agents/aria/receivables/models.py` and `aria/agents/aria/receivables/policy.py`.
- [ ] T002 Add a synthetic one-customer/one-currency payment, virtual-account, customer, invoice, procedure, and labelled-exception fixture; mark all tolerance values as test-only approved fixtures in `tests/fixtures/receivables/`.

## Phase 2: Foundational Models, Sources, and Rules

- [ ] T003 [P] Add deterministic tests for exception scope, currency/date validity, active virtual-account mapping, open invoice eligibility, variance arithmetic, tolerance boundaries, and duplicate detection in `tests/unit/test_receivables_rules.py`.
- [ ] T004 Implement Pydantic models for exception requests, source evidence, candidates, policy, matching decisions, recommendations, analyst decisions, case tasks, and audit events in `aria/agents/aria/receivables/models.py`.
- [ ] T005 [P] Define read-only payment, virtual-account, customer, invoice, and procedure/tolerance source protocols plus fake adapters in `aria/agents/aria/receivables/sources.py` and `tests/fixtures/receivables/`.
- [ ] T006 Implement pure deterministic eligibility, effective-date, currency, variance/tolerance, invoice status, and duplicate/prior-allocation rules in `aria/agents/aria/receivables/rules.py`.
- [ ] T007 Add property tests for variance arithmetic, tolerance boundaries, duplicate invariance, and deterministic candidate ordering in `tests/property/test_receivables_properties.py`.

## Phase 3: User Story 1 - Bounded Aria Subagent Investigation (Priority: P1)

**Goal**: Aria delegates only supported receivables exceptions to a specialist that retrieves bounded evidence using read-only sources.

**Independent Test**: Fake-backed parent tests prove supported exception handoff, unrelated-message no-handoff, strict one-customer/one-currency scope, and source-read-only behavior.

- [ ] T008 [P] [US1] Add subagent handoff, scope, source-access, and untrusted-narrative tests in `tests/framework/test_receivables_subagent.py`.
- [ ] T009 [US1] Build the specialist prompt and investigation planner using structured steps and source protocols in `aria/agents/aria/receivables/agent.py`.
- [ ] T010 [US1] Implement bounded read-only evidence retrieval and provenance capture for payment, virtual-account, customer, invoice, and procedure sources in `aria/agents/aria/receivables/agent.py` and `aria/agents/aria/receivables/sources.py`.
- [ ] T011 [US1] Expose the specialist through one Aria parent `Agent.as_tool` handoff while preserving parent authentication/session context and existing behavior in `aria/agents/aria/agentcore_entrypoint.py`.

## Phase 4: User Story 2 - Deterministic, Evidence-Backed Recommendation (Priority: P1)

**Goal**: The specialist returns only eligible, evidence-supported allocation proposals and explicitly abstains on failures or ambiguity.

**Independent Test**: Labelled fixtures verify supported matches, policy tolerances, missing/inactive mappings, multiple candidates, conflicts, duplicate suspicion, and no-recommendation outcomes.

- [ ] T012 [P] [US2] Add tests for candidate eligibility/ranking, evidence coverage, confidence bands, no-recommendation outcomes, and policy-version traceability in `tests/unit/test_receivables_recommendations.py`.
- [ ] T013 [US2] Implement deterministic candidate generation, scoring from approved weights, and evidence-linked ranking in `aria/agents/aria/receivables/matching.py`.
- [ ] T014 [US2] Combine model hypotheses with mandatory rules so failed mapping, currency, invoice, duplicate, date, or tolerance checks cannot be overridden in `aria/agents/aria/receivables/agent.py`.
- [ ] T015 [US2] Produce structured recommendation/no-recommendation/escalation results with exact Decimal variance, policy/procedure reference, source IDs, confidence band, and draft note in `aria/agents/aria/receivables/agent.py`.

## Phase 5: User Story 3 - Analyst Approval and Sole Permitted Write (Priority: P1)

**Goal**: Human approval, revision, rejection, or escalation controls the case workflow; only approval can write a case task.

**Independent Test**: Workflow tests prove no write before approval, revision reruns deterministic checks, reject/escalate never write, and repeated approval is idempotent.

- [ ] T016 [P] [US3] Add transition tests for approve/revise/reject/escalate, analyst identity, recommendation version, and prohibited write attempts in `tests/unit/test_receivables_approval.py`.
- [ ] T017 [US3] Implement explicit analyst decision state transitions and revision revalidation in `aria/agents/aria/receivables/approval.py`.
- [ ] T018 [US3] Implement the sole idempotent case-task writer; require an authorized analyst and approved recommendation version, and expose no ledger/account/payment/virtual-account/master-data write methods in `aria/agents/aria/receivables/case_tasks.py`.
- [ ] T019 [US3] Add a controlled analyst decision interface for viewing evidence and choosing approve/revise/reject/escalate in `demo/receivables_exception/`.

## Phase 6: User Story 4 - Audit, Controls, and Evaluation (Priority: P1)

**Goal**: Every investigation and human decision is auditable, and evaluation reports the source-defined safety/accuracy metrics.

**Independent Test**: Replay the agreed labelled set and verify audit completeness, classification/top-candidate/precision/escalation thresholds, evidence/variance coverage, and zero prohibited financial writes.

- [ ] T020 [P] [US4] Add audit contract tests for source reads, rule outcomes, recommendation versions, analyst revisions/decisions, and case-task writes without raw prompts or unnecessary source payloads in `tests/unit/test_receivables_audit.py`.
- [ ] T021 [US4] Implement correlated append-oriented audit event creation and safe summaries in `aria/agents/aria/receivables/audit.py`.
- [ ] T022 [US4] Implement a labelled evaluation runner reporting classification >=90%, top-candidate >=85%, confident allocation precision >=95%, correct escalation >=90%, evidence coverage 100%, variance verification 100%, and prohibited writes ==0 in `tests/evaluation/test_receivables_mvp.py`.
- [ ] T023 [US4] Add adversarial tests proving payer/remittance instructions cannot alter tool selection, rules, analyst identity, or approval state in `tests/framework/test_receivables_subagent.py`.
- [ ] T024 [US4] Document owner-supplied policy/access prerequisites, mock-only source boundaries, approval flow, evaluation protocol, and prohibited actions in `docs/agent-framework.md` and `specs/004-receivables-exception-resolution/quickstart.md`.

## Dependencies and Execution Order

- T001-T007 establish approved configuration shape, synthetic evidence, typed models, read-only ports, and deterministic rules before any recommendation logic.
- T008-T011 build the bounded specialist and parent handoff using fake connectors.
- T012-T015 add evidence-backed candidate matching and fail-closed recommendation outcomes.
- T016-T019 add the analyst workflow and sole case-task write only after the proposal path is validated.
- T020-T024 add audit, safety, evaluation, and documentation before any sandbox connector is considered.
- Live source integrations remain out of this plan until operations/control owners approve access, procedure, tolerances, confidence thresholds, and evaluation data.

## Parallel Opportunities

- T003 and T005 can proceed in parallel after the one-customer/one-currency fixture shape is agreed.
- T008 and T012 can be developed against their fakes after foundational contracts exist.
- T016 and T020 can be authored in parallel because they validate separate approval and audit boundaries.
- T021 audit sink implementation can proceed independently after the audit event schema is agreed.

## Implementation Strategy

1. Week 1: obtain approved policy/test inputs, define schemas, and implement deterministic rules with boundary tests.
2. Week 2: implement read-only retrieval, triage plan, virtual-account verification, candidate matching, and parent handoff.
3. Week 3: implement evidence review, confidence/escalation, analyst decision transitions, mock case-task writer, and audit events.
4. Week 4: run the labelled evaluation, correct rules/prompts, complete analyst demo, and record acceptance evidence.
5. Do not connect live systems or permit writes until explicit owner access/policy approval and the evaluation gate are satisfied.
