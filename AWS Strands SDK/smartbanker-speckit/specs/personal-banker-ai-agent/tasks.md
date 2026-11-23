# Tasks: Personal Banker AI Agent

**Input**: `spec.md`, `plan.md`
**Prerequisites**: `spec.md` and `plan.md` must be finalized before task execution.

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create Python project structure with `src/`, `tests/`, and `deployment/` directories.
- [ ] T002 Initialize Python package metadata and dependency manifest.
- [ ] T003 Add environment configuration and AWS runtime variable support in `src/config/settings.py`.
- [ ] T004 Add basic structured logging in `src/observability/logger.py`.
- [ ] T005 Create strict tool schema definitions in `src/tools/registry.py`.
- [ ] T006 Define AgentCore Lambda gateway tool integration and Lambda wrapper contracts.

---

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T010 Implement AgentCore short-term memory manager in `src/memory/agentcore_memory.py`. **Acceptance**: Define interface contract with methods `add(interaction_record)`, `retrieve(limit=20, filter_by_failure=true)`, `prune_duplicates()`, `get_size()`. Include mock/stub implementation for unit testing without live AgentCore. Return type: List[InteractionRecord], ordered by failure flag then timestamp descending.
- [ ] T011 Implement AgentCore semantic memory manager in `src/memory/agentcore_memory.py`. **Acceptance**: Define interface for `add_embedding(pattern_vector, metadata)`, `retrieve_similar(query_vector, top_k=5)`, `filter_by_age(max_days=365)`. Include timestamp-based filtering logic; return no results if all matches exceed 365-day cutoff. Mock/stub for testing.
- [ ] T012 Create Bedrock client wrapper in `src/llm/bedrock_client.py`. **Acceptance**: Implement methods `invoke_text(prompt, model_id)` and `invoke_embedding(text, model_id)`. Include mock responses for unit testing. Test both text and embedding endpoints.
- [ ] T013 Create Lambda gateway wrappers for each tool and document integration endpoints.
- [ ] T014 Define shared output contract models and validation helpers across agents.
- [ ] T015 Implement `CoordinatorAgent` orchestration in `src/agents/coordinator.py`.
- [ ] T016 Implement `DelegatorAgent` routing and tool compatibility validation in `src/agents/delegator.py`.
- [ ] T017 Implement `RiskComplianceAgent` in `src/agents/workers/risk_compliance.py`.
- [ ] T018 Add agent runner entrypoint in `src/agents/agent_runner.py`.

**Checkpoint**: Foundational support for memory, Bedrock, agent orchestration, and tool validation must be complete before worker-specific features.

---

## Phase 3: User Story 1 - Spending Analysis (Priority: P1)

**Goal**: Build spending insight recommendations with safe risk labels.

- [ ] T020 Implement `SpendingAnalyzerAgent` in `src/agents/workers/spending_analyzer.py`.
- [ ] T021 Add spending analysis sample tool metadata in `src/tools/registry.py`.
- [ ] T022 Add a unit test for spending insight output contract in `tests/test_risk_recommendation.py`.
- [ ] T023 Integrate spending analysis with the coordinator and delegator.

**Independent Test**: Simulate a budget query and verify output JSON contract and risk label.

---

## Phase 4: User Story 2 - Savings Strategy (Priority: P2)

**Goal**: Build personalized savings recommendations and memory-aware avoidance of failed advice.

- [ ] T030 Implement `SavingsAdvisorAgent` in `src/agents/workers/savings_advisor.py`.
- [ ] T031 Add savings strategy personalization through user preference and account summary.
- [ ] T032 Add a unit test for repeated savings advice avoidance in `tests/test_repeated_bad_advice_learning.py`.
- [ ] T033 Integrate savings advice into the coordinator reflection flow.

---

## Phase 5: User Story 3 - Investment Guidance (Priority: P2)

**Goal**: Build risk-aware investment advice with compliance gating.

- [ ] T040 Implement `InvestmentAdvisorAgent` in `src/agents/workers/investment_advisor.py`.
- [ ] T041 Add investment data API tool metadata in `src/tools/registry.py`.
- [ ] T042 Add a unit test for risk-aware investment output in `tests/test_risk_recommendation.py`.
- [ ] T043 Add a repeated bad investment scenario test in `tests/test_repeated_bad_advice_learning.py`.
- [ ] T044 Integrate investment advice with the delegator and risk compliance validation.

---

## Phase 6: User Story 4 - Query Assistant (Priority: P3)

**Goal**: Build direct financial Q&A with explainable answers.

- [ ] T050 Implement `QueryAssistantAgent` in `src/agents/workers/query_assistant.py`.
- [ ] T051 Add query assistant tool integration and validation.
- [ ] T052 Add a contract-level test for query assistant JSON output in `tests/test_risk_recommendation.py`.
- [ ] T053 Integrate the query assistant with the coordinator for direct intent handling.

---

## Phase 7: User Story 6 - HDFC Private Banker Programme Guidance (Priority: P3)

**Goal**: Build tier-based programme benefit comparisons, RM eligibility rules, and clear private banker capability boundaries.

- [ ] T055 Implement HDFC programme tier models and eligibility rules in `src/agents/workers/risk_compliance.py`.
- [ ] T056 Add programme-specific benefit mapping (Classic, Preferred, Imperia, etc.) and family extension rules.
- [ ] T057 Implement RM boundaries logic: loan approval constraints, fiduciary limitations, and policy override prevention.
- [ ] T058 Add unit test for programme tier comparison and RM boundary enforcement in `tests/test_risk_recommendation.py`.

**Independent Test**: Query system for Classic vs Preferred tier comparison and verify RM capability boundaries are enforced.

---

## Phase 8: Self-Healing and Reflection

**Goal**: Build retry/reflection and improve memory learning.

- [ ] T060 Implement reflection and retry decision logic in `src/agents/coordinator.py`.
- [ ] T061 Add short-term memory retrieval rules and pruning logic. **Acceptance**: Retrieve only via `retrieve(limit=20, filter_by_failure=true)` from AgentCoreMemoryManager; apply deduplication BEFORE prioritization; return sorted list (failures first, then timestamp descending).
- [ ] T062 Add long-term semantic retrieval and reuse logging. **Acceptance**: Query semantic memory via `retrieve_similar(query_vector, top_k=5)` ONLY. Apply age filter `filter_by_age(max_days=365)` before returning results. Context window NEVER exceeds top-K embeddings; DO NOT send full embedding DB to any LLM prompt. Log reuse events with similarity score and age.
- [ ] T063 Add tests for memory pruning and retry decisions in `tests/test_memory_pruning.py`.
- [ ] T064 Document the self-healing flow in `deployment/agentcore_compatibility.md`.

---

## Phase 9: Tool Implementation and Lambda Wrappers

**Goal**: Implement business logic for financial tools and expose via Lambda gateway.

- [ ] T065 Implement `transaction_fetcher` tool with transaction parsing and categorization in `src/tools/transaction_fetcher.py`.
- [ ] T066 Implement `balance_checker` tool for account summary and balance retrieval in `src/tools/balance_checker.py`.
- [ ] T067 Implement `investment_data_api` tool for portfolio and investment data retrieval in `src/tools/investment_data_api.py`.
- [ ] T068 Implement `budgeting_calculator` tool for budget analysis and spending forecasts in `src/tools/budgeting_calculator.py`.
- [ ] T069 Create Lambda wrapper handlers for each tool and document gateway endpoints in `deployment/lambda_tool_gateway.md`.

---

## Phase 10: Polish & Deployment

- [ ] T070 Create deployment documentation in `deployment/aws_deployment.md`.
- [ ] T071 Add `README.md` with quickstart instructions.
- [ ] T072 Add environment and IAM guidance for production.
- [ ] T073 Review and update docs for SpecKit compliance and enterprise readiness.
- [ ] T074 Run all tests with `pytest` and validate package import paths.

---

## Task Dependency Graph

**Phase Execution Order**:
1. Phase 1 (Setup) → Phase 2 (Foundational + Tool gateway contracts)
2. Phase 2 → Phase 3-7 (User Stories can be parallelized)
3. Phase 8 (Self-Healing) → Phase 9 (Tool Implementation)
4. Phase 9 → Phase 10 (Polish/Deployment) → Final

**Parallel Execution Opportunities**:
- US1 (Phase 3), US2 (Phase 4), US3 (Phase 5) can run in parallel after Phase 2 is complete
- US4 (Phase 6) and US6 (Phase 7) can run in parallel
- Tool implementation (Phase 9) can run alongside US1-US7 once Phase 2 is complete
- Self-Healing (Phase 8) builds on memory/reflection logic from Phase 2 and US implementations
