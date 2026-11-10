# Tasks: Dispute Resolution Subagent

**Input**: Design documents from `/specs/005-dispute-resolution-subagent/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/investigation-and-review.md`, `quickstart.md`

## Phase 1: Setup

- [ ] T001 Define validated, versioned schemas for dispute scope, evidence allowlists, policy, action proposals, and analyst roles; missing or expired policy MUST fail closed in `aria/agents/aria/dispute_resolution/models.py` and `aria/agents/aria/dispute_resolution/policy.py`.
- [ ] T002 Add synthetic/de-identified fraud and merchant dispute fixtures with transaction, account, merchant/order/delivery evidence, and labelled expected outcomes in `tests/fixtures/disputes/`.

## Phase 2: Foundational Evidence and Rules

- [ ] T003 [P] Add deterministic tests for transaction/customer scope, source evidence freshness, required evidence, policy validity, and allowed dispute types in `tests/unit/test_dispute_rules.py`.
- [ ] T004 Implement Pydantic models for disputes, evidence, policies, findings, recommendations, decisions, simulated actions, and audit events in `aria/agents/aria/dispute_resolution/models.py`.
- [ ] T005 [P] Define narrow read-only payment/account/merchant/order/delivery source protocols and fake adapters in `aria/agents/aria/dispute_resolution/sources.py` and `tests/fixtures/disputes/`.
- [ ] T006 Implement deterministic policy evaluation for eligibility, required evidence, fraud signals, merchant evidence, and human-review conditions in `aria/agents/aria/dispute_resolution/rules.py`.
- [ ] T007 Add property tests proving failed/missing rules never become auto-eligible and rule evaluation is deterministic for equivalent evidence in `tests/property/test_dispute_properties.py`.

## Phase 3: User Story 1 - Aria Dispute Specialist Handoff (Priority: P1)

**Goal**: Aria delegates supported disputes to one specialist while preserving parent authentication, tenant/session context, and existing behavior.

**Independent Test**: Fake-backed tests show only supported disputes hand off, the verified customer scope is preserved, unrelated queries do not invoke the child, and no write-capable source is available.

- [ ] T008 [P] [US1] Add tests for parent handoff, supported dispute classification, identity propagation, and out-of-scope rejection in `tests/framework/test_dispute_subagent.py`.
- [ ] T009 [US1] Build the specialist prompt and investigation planner as one child Strands Agent in `aria/agents/aria/dispute_resolution/agent.py`.
- [ ] T010 [US1] Implement bounded evidence retrieval, provenance capture, and contradiction/missing-evidence findings through read-only protocols in `aria/agents/aria/dispute_resolution/agent.py` and `aria/agents/aria/dispute_resolution/sources.py`.
- [ ] T011 [US1] Expose the child as one bounded `Agent.as_tool` handoff from the authenticated Aria parent without changing Cognito, KYC, session, or Runtime boundaries in `aria/agents/aria/agentcore_entrypoint.py`.

## Phase 4: User Story 2 - Explainable Dispute Recommendation (Priority: P1)

**Goal**: The specialist returns evidence-backed outcomes and only proposes actions allowed by approved deterministic policy.

**Independent Test**: Synthetic fraud and merchant cases verify evidence references, applicable policy version, automatic-versus-review outcome, and abstention on missing/conflicting evidence.

- [ ] T012 [P] [US2] Add tests for fraud evidence, merchant delivery evidence, contradictory sources, missing policy, action thresholds, and no-recommendation outcomes in `tests/unit/test_dispute_recommendations.py`.
- [ ] T013 [US2] Implement deterministic decision evaluation and policy-controlled simulated action proposals in `aria/agents/aria/dispute_resolution/rules.py` and `aria/agents/aria/dispute_resolution/agent.py`.
- [ ] T014 [US2] Produce structured findings, explanation, confidence/review status, evidence citations, and simulated actions in `aria/agents/aria/dispute_resolution/agent.py`.
- [ ] T015 [US2] Add the fraudulent-transaction and merchant-dispute walkthrough tests proving no unsupported conclusion or real action can occur in `tests/unit/test_dispute_recommendations.py`.

## Phase 5: User Story 3 - Human Decision and Simulated Action Gate (Priority: P1)

**Goal**: Human approve/revise/reject/escalate decisions control the workflow; the MVP has no real financial-action connector.

**Independent Test**: State-transition tests prove no simulated action event before authorized approval, revise revalidates evidence/policy, reject/escalate create no action, and stale decisions cannot approve newer recommendations.

- [ ] T016 [P] [US3] Add decision-transition and no-action-before-approval tests in `tests/unit/test_dispute_approval.py`.
- [ ] T017 [US3] Implement versioned approve/revise/reject/escalate transitions with analyst identity validation in `aria/agents/aria/dispute_resolution/approval.py`.
- [ ] T018 [US3] Implement an in-memory simulated action recorder and deny all real card/refund/ledger/account writes in `aria/agents/aria/dispute_resolution/actions.py`.
- [ ] T019 [US3] Build the controlled mock analyst review interface for evidence display and explicit decisions in `demo/dispute_resolution/`.

## Phase 6: User Story 4 - Audit and Evaluation (Priority: P2)

**Goal**: Every source read, finding, recommendation, decision, and simulated action is auditable and the labelled evaluation reports source-defined metrics.

**Independent Test**: Replay the labelled mock set and verify audit completeness, reported accuracy/justification, and zero real financial writes.

- [ ] T020 [P] [US4] Add audit-event contract tests that reject raw prompts, credentials, hidden reasoning, and unbounded evidence payloads in `tests/unit/test_dispute_audit.py`.
- [ ] T021 [US4] Implement correlated safe audit-event creation for source reads, rule outcomes, recommendations, human decisions, and simulated actions in `aria/agents/aria/dispute_resolution/audit.py`.
- [ ] T022 [US4] Implement a labelled evaluation runner that reports decision accuracy/justification, governance/audit coverage, human-review rates, and practical workflow measures without inventing target thresholds in `tests/evaluation/test_dispute_mvp.py`.
- [ ] T023 [US4] Add adversarial tests proving payer, merchant, delivery, and transaction text cannot alter rules, analyst identity, or approval state in `tests/framework/test_dispute_subagent.py`.
- [ ] T024 [US4] Document mock-only connectors, simulated actions, policy-owner inputs, evaluation results, and the separate approval required for live action integrations in `docs/agent-framework.md` and `specs/005-dispute-resolution-subagent/quickstart.md`.

## Dependencies and Execution Order

- T001-T007 establish schema, fixtures, source boundaries, and deterministic rules before any model recommendation.
- T008-T011 connect a single specialist to the Aria parent using only read-only source adapters.
- T012-T015 add recommendation generation and evidence handling after deterministic rule tests pass.
- T016-T019 implement the analyst decision gate before exposing any simulated action.
- T020-T024 complete audit, safety, evaluation, and documentation.
- No task introduces production integrations or real dispute actions; those require a separate approval and feature plan.

## Parallel Opportunities

- T003 and T005 can be authored in parallel after the fixture schema is agreed.
- T008 handoff tests can proceed alongside T012 decision tests using the same fakes.
- T016 approval tests and T020 audit tests can be developed in parallel because they cover separate boundaries.
- T021 audit implementation and T022 evaluation runner can proceed in parallel after their event/result schemas are fixed.

## Implementation Strategy

1. Week 1: obtain approved test policy and labelled fixtures; implement models and deterministic rule tests first.
2. Week 2: implement mock read-only evidence retrieval and Aria subagent handoff.
3. Week 3: add recommendations, analyst review transitions, simulated-only actions, and audit.
4. Week 4: run labelled evaluation, refine policy configuration, demonstrate both dispute scenarios, and record results.
5. Do not connect live evidence systems or real card/refund/ledger actions in this MVP.
