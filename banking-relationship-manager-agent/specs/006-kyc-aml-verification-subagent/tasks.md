# Tasks: KYC/AML Verification Subagent

**Input**: Design documents from `/specs/006-kyc-aml-verification-subagent/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/verification-and-escalation.md`, `quickstart.md`

## Phase 1: Setup

- [ ] T001 Define immutable configuration for approved jurisdictions, document field allowlists, provider IDs, source allowlists, and policy versions without adding a default OCR/vendor dependency in `aria/agents/aria/kyc_aml/config.py`.
- [ ] T002 Establish synthetic masked identity fixtures and fake provider fixtures only in `tests/fixtures/kyc_aml/`.

## Phase 2: Foundational Contracts and Safety

- [ ] T003 [P] Add validation tests for document references, supported fields, confidence bounds, policy-date timezone/expiry, masking, source freshness, and malformed provider responses in `tests/unit/test_kyc_aml_verification.py`.
- [x] T004 Implement Pydantic entities for document observations, verification observations/results, effective-dated policy, explicit AML assessment states, compliance assessment, and audit events in `aria/agents/aria/kyc_aml/models.py`.
- [ ] T005 [P] Add reusable fake document extraction, identity verification, compliance policy, and AML providers plus synthetic masked fixtures in `aria/agents/aria/kyc_aml/providers.py` and `tests/fixtures/kyc_aml/`.
- [ ] T006 Add redaction/property tests proving raw documents and full identity numbers cannot enter logs, prompts, Memory, or audit summaries in `tests/property/test_kyc_aml_properties.py`.

## Phase 3: User Story 1 - Extract and Verify Identity Evidence (Priority: P1)

- [ ] T007 [P] [US1] Add tests for successful extraction, unsupported document type, low confidence, source match, source conflict, stale source, and provider failure in `tests/unit/test_kyc_aml_verification.py`.
- [x] T008 [US1] Implement document-reference validation and typed extraction orchestration with masked results in `aria/agents/aria/kyc_aml/verification.py`.
- [x] T009 [US1] Implement deterministic field-level comparison with provenance and explicit incomplete/conflict outcomes in `aria/agents/aria/kyc_aml/verification.py`.
- [ ] T010 [US1] Require approved source precedence and document policy; return unassessed/human-review when policy or provider configuration is absent in `aria/agents/aria/kyc_aml/policy.py`.

## Phase 4: User Story 2 - Assess Risk and Escalate (Priority: P1)

**Goal**: Risk/AML findings use an approved policy and ambiguous cases produce explainable human review, never model-only approval.

**Independent Test**: A test-only approved policy yields deterministic findings; missing policy, provider errors, conflicts, and unsupported statuses always fail closed and escalate.

- [ ] T011 [P] [US2] Add tests for missing/expired policy, configured risk factors, AML evidence outcomes, escalation reasons, and no-clearance behavior in `tests/unit/test_kyc_aml_verification.py`.
- [ ] T012 [US2] Implement policy-versioned deterministic risk/AML assessment with no built-in scores or thresholds in `aria/agents/aria/kyc_aml/policy.py` and `aria/agents/aria/kyc_aml/verification.py`.
- [ ] T013 [US2] Return a structured compliance assessment that separates verified facts, conflicts, missing evidence, policy findings, and human-review next steps in `aria/agents/aria/kyc_aml/agent.py`.
- [ ] T014 [US2] Add correlated, redaction-safe audit events for extraction, source reads, comparisons, policy decisions, and escalations in `aria/agents/aria/kyc_aml/audit.py`.

## Phase 5: User Story 3 - Integrate Through Aria Parent (Priority: P1)

**Goal**: KYC/AML cases use the existing verified parent identity and session; no separate endpoint or privilege path is introduced.

**Independent Test**: Fake-backed tests prove only compliance cases hand off, parent tenant/user/session values cannot be overwritten, missing providers fail closed, and unrelated Aria requests are unchanged.

- [ ] T015 [P] [US3] Add parent/subagent contract tests for verified identity propagation, no payload identity override, provider absence, and unrelated-route behavior in `tests/framework/test_kyc_aml_subagent.py`.
- [ ] T016 [US3] Expose the compliance specialist as one bounded child tool through `Agent.as_tool` and register it only for approved compliance flows in `aria/agents/aria/agentcore_entrypoint.py` and `aria/agents/aria/kyc_aml/agent.py`.
- [ ] T017 [US3] Preserve existing product recommendation KYC fail-closed gate and adapt only verified provider results into the established status contract in `aria/agent.py` and `aria/tools/compliance_tool.py`.
- [ ] T018 [US3] Add integration tests proving document values are masked and the specialist cannot self-certify KYC, clear AML, or authorize a product in `tests/framework/test_kyc_aml_subagent.py`.

## Phase 6: User Story 4 - Owner-Configured Provider Readiness (Priority: P2)

**Goal**: External providers and policies can be configured safely after owner decisions, without shipping assumed provider behavior.

**Independent Test**: A fake approved configuration enables the full workflow; absent/invalid configuration fails closed with actionable diagnostics and no secrets in logs.

- [ ] T019 [P] [US4] Define configuration validation for provider IDs, document schema, source allowlists, jurisdiction, and policy version without adding real credentials in `aria/agents/aria/kyc_aml/providers.py` and `aria/agents/aria/kyc_aml/config.py`.
- [ ] T020 [US4] Add a readiness diagnostic that identifies missing owner-supplied contracts/configuration without exposing secret values in `aria/agents/aria/kyc_aml/config.py` and tests.
- [ ] T021 [US4] Document the owner decisions required before live integration, raw-document handling, retention, and evaluation in `docs/agent-framework.md` and `specs/006-kyc-aml-verification-subagent/quickstart.md`.

## Dependencies and Execution Order

- T001-T006 define schemas, fake providers, and safety invariants before implementing extraction.
- T007-T010 implement extraction and multi-source verification using fake contracts.
- T011-T014 add policy-driven assessment, escalation, and audit after source verification is deterministic.
- T015-T018 integrate the child with the Aria parent and preserve existing fail-closed product gates.
- T019-T021 provide configuration readiness; live integrations remain blocked until owners supply source/policy/access decisions.

## Parallel Opportunities

- T003, T005, and T006 can proceed in parallel after the entity schema is agreed.
- T007 and T011 tests can be drafted in parallel against the same fake provider contracts.
- T014 audit tests can proceed alongside policy assessment work once event fields are fixed.
- T015 parent contract tests can proceed alongside T019 configuration validation.

## Implementation Strategy

1. Build typed provider contracts, masked entities, and fake fixtures.
2. Implement deterministic extraction-result normalization and multi-source comparison.
3. Add owner-policy-gated risk/AML assessment and explicit human escalation.
4. Integrate the specialist through Aria parent identity while retaining existing product KYC blocks.
5. Validate fake-backed behavior; do not connect live OCR/KYC/AML sources until provider, jurisdiction, access, retention, and policy decisions are approved.
