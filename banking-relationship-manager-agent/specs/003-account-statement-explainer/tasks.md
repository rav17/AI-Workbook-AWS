# Tasks: Account Statement Explainer Subagent

**Input**: Design documents from `/specs/003-account-statement-explainer/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/activity-stream.md`, `quickstart.md`

## Phase 1: Setup

- [X] T001 Add an optional `demo` dependency group for the local web service and update `uv.lock` without adding demo packages to Lambda/Runtime exports in `pyproject.toml` and `uv.lock`.
- [X] T002 Create the local demo package under `demo/statement_explainer/` and a root `compose.yaml` entrypoint, bound to loopback and separate from CDK deployment stacks.

## Phase 2: Foundational Data and Validation

- [X] T003 [P] Add Pydantic validation tests for transaction IDs, ISO dates, finite Decimal amounts, debit/credit indicator, category, and balance consistency in `tests/unit/test_statement_explainer.py`.
- [X] T004 Implement statement, transaction, request, tool-result, and activity-event models with validation in `aria/agents/aria/statement_explainer/models.py`.
- [X] T005 [P] Add deterministic fixture integrity tests for 50-100 rows, three-month coverage, required transaction types, unique IDs, and running balances in `tests/unit/test_statement_explainer.py`.
- [X] T006 Create the synthetic statement fixture and loader using the documented fields and category taxonomy in `aria/agents/aria/statement_explainer/dataset.py` and `demo/statement_explainer/data/statement.json`.

## Phase 3: User Story 1 - Aria Specialist Handoff (Priority: P1)

**Goal**: Aria delegates statement-related questions to one bounded specialist and leaves unrelated requests on existing paths.

**Independent Test**: A fake-backed parent-agent test verifies statement-query handoff, non-statement no-handoff, active statement scoping, and safe failure when the selected dataset is missing.

- [X] T007 [P] [US1] Add parent routing/handoff contract tests in `tests/framework/test_statement_subagent.py`.
- [X] T008 [US1] Build the statement specialist prompt and child Strands Agent from the pinned model/session configuration in `aria/agents/aria/statement_explainer/agent.py`.
- [X] T009 [US1] Expose the child with `Agent.as_tool(name="account_statement_explainer", preserve_context=False)` and register it only when statement data is available in the Aria parent builder under `aria/agents/aria/`.
- [X] T010 [US1] Route statement questions to the child with a validated statement ID and bounded parent context; keep KYC, tool authorization, tenant identity, and unrelated parent behavior unchanged in `aria/agent.py` and `aria/agents/aria/agentcore_entrypoint.py`.
- [X] T025 [US1] Expose a strict CDK `statement_explainer_enabled` opt-in defaulting to false, pass it to the existing Runtime, add enabled-only parent delegation guidance, and test default-off/explicit-on synthesis in `cdk/app.py`, `cdk/stacks/runtime_stack.py`, `aria/agents/aria/agentcore_entrypoint.py`, and `cdk/tests/test_security.py`.

## Phase 4: User Story 2 - Deterministic Statement Analysis (Priority: P1)

**Goal**: The specialist answers transaction questions from deterministic, exact statement calculations.

**Independent Test**: Fixed fixtures produce exact matching rows, transaction explanations, period totals, category distributions, anomaly baselines, and comparisons.

- [X] T011 [P] [US2] Add unit tests for all five tool contracts, filters, date boundaries, empty results, and duplicate transaction IDs in `tests/unit/test_statement_explainer.py`.
- [X] T012 [US2] Implement `get_transactions` and `explain_transaction` with bounded result rows and source IDs in `aria/agents/aria/statement_explainer/tools.py`.
- [X] T013 [US2] Implement `summarise_period` and `categorise_spend` using Decimal-only arithmetic and deterministic category fields in `aria/agents/aria/statement_explainer/tools.py`.
- [X] T014 [US2] Implement `detect_anomalies` against the three preceding complete months using the documented 50% prototype threshold and a nonzero baseline in `aria/agents/aria/statement_explainer/tools.py`.
- [X] T015 [P] [US2] Add property tests for debit/credit balance reconciliation, order-independent aggregates, filtering bounds, and category totals in `tests/property/test_statement_properties.py`.
- [X] T016 [US2] Register only the five statement tools with the child agent and ensure the parent has no direct access to statement rows outside the specialist handoff in `aria/agents/aria/statement_explainer/agent.py`.

## Phase 5: User Story 3 - Safe Activity Trace (Priority: P1)

**Goal**: Reviewers can follow safe tool/action progress without exposing model-private reasoning or unbounded financial data.

**Independent Test**: Multi-tool requests emit ordered normalized SSE events; injected private model text, credentials, and raw tool payloads are never forwarded.

- [X] T017 [P] [US3] Add event normalization and redaction tests for Strands tool-use/completion/failure events in `tests/framework/test_statement_subagent.py`.
- [X] T018 [US3] Map Strands events to the allowlisted `AgentActivityEvent` schema and emit only safe status/tool summaries and the final guardrail-checked response in `aria/agents/aria/statement_explainer/events.py`.
- [X] T019 [US3] Implement the async local `POST /api/chat` SSE endpoint with stable error codes, ordered event IDs, bounded request/session state, and no forwarding of arbitrary Strands `data` events in `demo/statement_explainer/app.py`.

## Phase 6: User Story 4 - Local Reviewer Demo (Priority: P2)

**Goal**: Reviewers can launch one local UI, run all three scenarios, and see cited transactions highlighted.

**Independent Test**: Compose starts from a clean checkout; preset A/B/C complete with synthetic data; cited transaction rows highlight; the UI reports model/configuration and tool failures safely.

- [X] T020 [P] [US4] Add UI tests for preset selection, SSE event rendering, and transaction highlighting in `tests/integration/test_statement_demo.py`.
- [X] T021 [US4] Build the minimal chat/activity/statement-table UI with three preset scenarios and transaction-ID highlighting in `demo/statement_explainer/static/`.
- [X] T022 [US4] Finish the localhost-only Dockerfile and root Compose configuration, mounting no credentials into the image and documenting required host model configuration in `compose.yaml` and `demo/statement_explainer/README.md`.
- [X] T023 [US4] Add end-to-end checks for scenarios A/B/C, follow-up context, and safe behavior when Bedrock configuration is absent in `tests/integration/test_statement_demo.py`.
- [X] T024 [US4] Document the Aria subagent boundary, synthetic data scope, safe activity trace, local launch, and explicit non-production limitations in `docs/agent-framework.md` and `specs/003-account-statement-explainer/quickstart.md`.

## Phase 7: Production Gateway and DynamoDB Migration

**Goal**: Replace all runtime synthetic statement data with read-only DynamoDB access behind AgentCore Gateway, scoped to the authenticated principal's active entitlements.

**Independent Test**: Fake-backed Gateway tests prove authorized statement reads succeed, unknown/revoked/cross-user references fail closed, the Runtime has no direct DynamoDB permissions, and the child is the only model-visible path to statement Gateway tools.

- [ ] T026 [P] Add Gateway store/handler tests for principal hashing, entitlement denial, date paging, row validation, and bounded responses in `tests/unit/test_statement_gateway.py`.
- [ ] T027 Add encrypted `StatementEntitlements` and `StatementTransactions` DynamoDB tables, secondary transaction-ID index, PITR, and retain policies in `cdk/stacks/stateful_stack.py`.
- [ ] T028 Implement read-only DynamoDB repository operations and validated Gateway tool dispatch for `list_authorized_statements` and `get_statement_transactions` in `aria/persistence/statement_store.py` and `aria/api/gateway_handler.py`.
- [ ] T029 Add Gateway target schemas and least-privilege read permissions for the two tables in `cdk/stacks/gateway_stack.py`; add synthesis coverage in `cdk/tests/test_security.py`.
- [ ] T030 Inject verified tenant/user identity into child-only Gateway wrappers, validate Gateway tool availability, and prevent raw statement tools from reaching the parent in `aria/agents/aria/agentcore_entrypoint.py` and `aria/agents/aria/statement_explainer/agent.py`.
- [ ] T031 Remove the production synthetic loader and make the five deterministic analysis tools operate only on validated Gateway results in `aria/agents/aria/statement_explainer/dataset.py` and `aria/agents/aria/statement_explainer/tools.py`.
- [ ] T032 Remove the local synthetic UI, fixture, Compose/Docker files, and demo-only dependency group; keep synthetic rows only in isolated tests in `demo/`, `compose.yaml`, `pyproject.toml`, `uv.lock`, and `tests/integration/`.
- [ ] T033 Add Gateway integration tests for child handoff, authorized statement selection, multi-page calculations, and safe failures in `tests/integration/test_statement_gateway.py`.
- [ ] T034 Document the DynamoDB item contract, trusted provisioning process, Gateway boundary, and production enablement gate in `docs/agent-framework.md`, `specs/003-account-statement-explainer/data-model.md`, and `specs/003-account-statement-explainer/quickstart.md`.

## Dependencies and Execution Order

- T026 tests define the Gateway authorization contract before T027-T030 implement storage, Gateway, and child-only access.
- T031 migrates deterministic calculations to validated Gateway rows; T032 removes the superseded local demo and production fixture.
- T033-T034 verify and document production behavior; the existing Runtime flag remains disabled until entitlement and transaction data are provisioned.

## Parallel Opportunities

- T003 and T005 can be authored in parallel because they cover distinct validation contracts.
- T007 handoff tests can be authored alongside T011 tool tests after the data models are agreed.
- T012 and T013 touch separate tool functions in the same file and should be sequential unless split by ownership.
- T017 tests can proceed in parallel with deterministic tool implementation.
- T020 UI tests and event mapper tests can proceed in parallel after the contract is stable.

## Implementation Strategy

1. Define and test principal-to-statement entitlements and DynamoDB read contracts.
2. Expose only read-only statement operations through the existing Gateway target.
3. Bind verified identity in Runtime-owned child wrappers and keep Gateway tools out of the parent tool list.
4. Remove the synthetic runtime path and local demo; preserve only synthetic unit-test data.
5. Enable the Runtime feature flag only after trusted entitlement and statement records have been provisioned.
