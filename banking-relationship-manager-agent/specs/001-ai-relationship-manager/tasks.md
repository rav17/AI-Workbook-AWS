# Tasks: Aria AI Relationship Manager

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md)

## Phase 1: Setup

- [ ] T001 Create the Python package structure under `aria/` and `tests/` according to `plan.md`.
- [X] T002 Create `pyproject.toml`, `requirements.txt`, and `requirements-dev.txt` with the approved runtime and test dependencies.
- [X] T003 [P] Create `aria/config.py` and `aria/constants.py` with environment-driven configuration and non-secret defaults.
- [X] T004 [P] Create `tests/conftest.py` and shared fixtures for client, CRM, knowledge-base, guardrail, and AWS mocks.
- [X] T005 [P] Add linting, formatting, test markers, and local environment documentation in `pyproject.toml` and `README.md`.

## Phase 2: Foundational

- [ ] T006 Create typed error, result, logging, and provider-client abstractions in `aria/`.
- [ ] T007 [P] Implement domain models in `aria/models/` from `data-model.md` with validation and serialization tests.
- [ ] T008 [P] Implement safe secret and environment configuration loading in `aria/config.py` without committing credentials.
- [ ] T009 Implement fail-closed guardrail result handling and structured audit logging in `aria/guardrails/`.
- [ ] T010 [P] Add common retry, timeout, and graceful-degradation policies in `aria/providers/`.
- [ ] T011 Verify the foundation with `pytest tests/unit` and `ruff check .` before story work begins.

**Production foundation requirements**: T058-T066 below are mandatory before enabling the agent against live client data or side-effecting tools.

## Phase 3: User Story 1 - Personalized Client Profile (Priority: P1)

**Goal**: Load and update client context, assess risk, and suggest CTG for eligible families.

**Independent Test**: Profile, family, and risk fixtures produce the expected CRM updates, questionnaire sequence, and CTG suggestion.

- [ ] T012 [US1] Implement `get_risk_questionnaire` and `assess_risk_appetite` in `aria/tools/risk_tool.py`.
- [ ] T013 [US1] Implement profile retrieval and structured updates in `aria/tools/crm_tool.py`.
- [ ] T014 [US1] Implement client greeting, family detection, and CTG suggestion rules in `aria/agent.py`.
- [ ] T015 [US1] Add unit tests for profile updates, risk thresholds, and family-account CTG behavior in `tests/unit/`.

## Phase 4: User Story 5 - Service Query Resolution (Priority: P1)

**Goal**: Answer banking service questions from current knowledge and escalate unresolved requests.

**Independent Test**: Mocked knowledge responses produce sourced answers, step-by-step procedures, concise options, or escalation.

- [ ] T016 [US5] Implement `query_product_info` with confidence and source-date handling in `aria/tools/knowledge_tool.py`.
- [ ] T017 [US5] Implement service query routing and unresolved-query escalation in `aria/agent.py`.
- [ ] T018 [US5] Add knowledge retrieval, stale/low-confidence, and escalation tests in `tests/unit/`.

## Phase 5: User Story 6 - CRM Interaction Logging (Priority: P1)

**Goal**: Persist complete interaction summaries and follow-up reminders.

**Independent Test**: A completed session creates a structured CRM record with topics, preferences, flags, date, and reminders.

- [ ] T019 [US6] Implement `log_interaction` and `create_followup_reminder` in `aria/tools/crm_tool.py`.
- [ ] T020 [US6] Implement summary completeness and segment/date tagging in `aria/models/interaction.py`.
- [ ] T021 [US6] Add CRM logging and reminder tests in `tests/unit/`.

## Phase 6: User Story 7 - Sensitive Credential Protection (Priority: P1)

**Goal**: Detect, redact, reject, and never persist sensitive credentials.

**Independent Test**: Credential-bearing messages are blocked before model and tool processing and do not appear in persistence or logs.

- [ ] T022 [US7] Configure credential filters and prompt-attack filters in `aria/guardrails/config.py`.
- [ ] T023 [US7] Implement input and output processing with fail-closed behavior in `aria/guardrails/processor.py`.
- [ ] T024 [US7] Add unit and property tests for PIN, CVV, OTP, password, and combined credential inputs in `tests/`.

## Phase 7: User Story 8 - Market Risk Disclosure (Priority: P1)

**Goal**: Enforce market-risk disclosures and prevent guaranteed-return claims.

**Independent Test**: Market-linked and fixed-income responses are checked for required disclosure, source date, and prohibited claims.

- [ ] T025 [US8] Add risk-disclosure and prohibited-claim rules to the agent system behavior in `aria/agent.py`.
- [ ] T026 [US8] Add response validation tests for market-linked and fixed-income products in `tests/unit/`.

## Phase 8: User Story 9 - Regulatory Compliance (Priority: P1)

**Goal**: Gate product requests on KYC and flag AML activity.

**Independent Test**: Current, expired, missing, and threshold-breaching fixtures produce the required gate or escalation.

- [ ] T027 [US9] Implement `check_kyc_status` and `flag_aml_activity` in `aria/tools/compliance_tool.py`.
- [ ] T028 [US9] Implement KYC gating and compliance escalation in `aria/agent.py`.
- [ ] T029 [US9] Add KYC and AML unit/property tests in `tests/`.

## Phase 9: User Story 10 - Human RM Escalation (Priority: P1)

**Goal**: Route complex, sensitive, and regulated cases with timelines and full context.

**Independent Test**: Each escalation category creates the correct ticket, priority, team, context, and client-visible timeline.

- [ ] T030 [US10] Implement escalation reason, priority, assignment, and timeline mapping in `aria/tools/escalation_tool.py`.
- [ ] T031 [US10] Add escalation routing to the agent and CRM interaction context in `aria/agent.py`.
- [ ] T032 [US10] Add escalation category and timeline tests in `tests/unit/`.

## Phase 10: User Story 12 - Prompt Injection Defense (Priority: P1)

**Goal**: Detect, block, log, and safely refuse adversarial inputs.

**Independent Test**: Injection fixtures never reach the agent reasoning loop and produce a safe refusal with an audit record.

- [ ] T033 [US12] Implement prompt injection detection and denied-topic handling in `aria/guardrails/processor.py`.
- [ ] T034 [US12] Add adversarial input and no-system-detail-leakage tests in `tests/property/`.

## Phase 11: User Story 13 - Knowledge Base Accuracy (Priority: P1)

**Goal**: Return current, cited rates and escalate unavailable knowledge.

**Independent Test**: Mocked current, stale, conflicting, and absent knowledge results produce safe responses and escalation.

- [ ] T035 [US13] Add source-date extraction, citation formatting, and confidence thresholds to `aria/tools/knowledge_tool.py`.
- [ ] T036 [US13] Add rate citation and unavailable-knowledge tests in `tests/unit/`.

## Phase 12: User Story 14 - CRM and API Context (Priority: P1)

**Goal**: Load CRM context at session start and degrade safely when CRM is unavailable.

**Independent Test**: Session fixtures verify segment-aware behavior, limited functionality, and incident logging.

- [ ] T037 [US14] Implement `SessionManager` in `aria/session/manager.py` with DynamoDB persistence and recovery.
- [ ] T038 [US14] Implement authenticated WebSocket and REST handlers in `aria/api/`.
- [ ] T039 [US14] Implement CRM session context loading and unavailable-CRM degradation in `aria/agent.py`.
- [ ] T040 [US14] Add session, API authentication, rate-limit, and CRM outage tests in `tests/integration/`.

## Phase 13: User Story 2 - Wallet Profiling and Consolidation (Priority: P2)

- [ ] T041 [US2] Implement wallet profile updates and consolidation opportunity models in `aria/tools/crm_tool.py` and `aria/models/wallet.py`.
- [ ] T042 [US2] Add benefit-focused consolidation response behavior in `aria/agent.py`.
- [ ] T043 [US2] Add wallet disclosure and no-pressure messaging tests in `tests/unit/`.

## Phase 14: User Story 3 - Financial Product Recommendations (Priority: P2)

- [ ] T044 [US3] Implement risk-to-product mapping and balance-qualified offer rules in `aria/constants.py` and `aria/agent.py`.
- [ ] T045 [US3] Add protection, lending, payment, fee-waiver, and concierge recommendation behavior in `aria/agent.py`.
- [ ] T046 [US3] Add profile-sensitive recommendation tests in `tests/property/`.

## Phase 15: User Story 4 - Retention and Maturity Management (Priority: P2)

- [ ] T047 [US4] Implement maturity and outflow tools in `aria/tools/maturity_tool.py`.
- [ ] T048 [US4] Implement EventBridge handlers in `aria/events/handler.py` and `aria/events/lambda_handler.py`.
- [ ] T049 [US4] Add exact-30-day, 31-day, outflow-threshold, and reinvestment-rate tests in `tests/unit/test_maturity_tool.py`.

## Phase 16: User Story 11 - Actionable Conversation Style (Priority: P2)

- [ ] T050 [US11] Implement name personalization, empathetic tone, bullet formatting, and next-step response rules in `aria/agent.py`.
- [ ] T051 [US11] Add response-style and personalization property tests in `tests/property/`.

## Phase 17: Agent Assembly and Cross-Cutting Validation

- [ ] T052 Implement complete tool registration and orchestration in `aria/agent.py`.
- [ ] T053 [P] Add the 20 behavioral property tests described by the source Kiro task plan in `tests/property/`.
- [ ] T054 [P] Add structured CloudWatch logging and X-Ray tracing in `aria/observability.py` around requests, tools, guardrails, and escalations.
- [ ] T055 [P] Add deployment configuration in `infra/` for Lambda/API Gateway/EventBridge and document required parameters in `docs/deployment.md`.
- [ ] T056 Run the scenarios in `quickstart.md`, full test suite, linting, and security review.
- [ ] T057 Update provider contracts, operational limits, data retention, and the production runbook in `docs/`.

## Phase 18: Production Best-Practice Hardening

- [ ] T058 Create `aria/workflow/state.py`, `aria/workflow/patch.py`, and `aria/workflow/result.py` with typed workflow state, atomic patch operations, revisioning, and safe reason codes.
- [ ] T059 Create `aria/workflow/validator.py` with deterministic authorization, immutable-field, domain-rule, KYC/AML, and confirmation validation that does not depend on model instructions.
- [ ] T060 Create `aria/workflow/dependencies.py` and `aria/workflow/next_step.py` with declarative transitive invalidation and earliest-affected-step resolution.
- [ ] T061 Add optimistic concurrency, idempotency keys, conditional writes, and retry-safe side-effect handling in `aria/persistence/` and `aria/tools/`.
- [ ] T062 Integrate the pinned Strands session/context-management APIs in `aria/agent.py`, including bounded context, compact tool results, token/turn limits, cancellation, and explicit handling of guardrail stop reasons.
- [ ] T063 Integrate AgentCore Runtime session mapping and restart recovery in `aria/api/` and `aria/session/`, ensuring one authenticated user/conversation maps to one reused runtime session ID and concurrent writers are rejected or serialized.
- [ ] T064 Integrate scoped AgentCore Memory retrieval and extraction in `aria/memory/`, with tenant isolation, bounded top-k retrieval, retention/deletion policy, and current-workflow-state precedence.
- [ ] T065 Integrate AgentCore Gateway capability filtering and semantic discovery in `aria/tools/`, while enforcing authorization through IAM, Gateway policy, OAuth scopes, and backend checks.
- [ ] T066 Add Python quality gates in `pyproject.toml` and CI for Ruff format/lint, static typing, pytest, Hypothesis, dependency auditing, secret scanning, and coverage thresholds.
- [ ] T067 Add redaction-safe structured observability in `aria/observability.py` for correlation ID, runtime session, workflow revision, changed fields, validation result, stale fields, selected tools, model/tool latency, retries, and error category.
- [ ] T068 Add tests for corrections, multiple atomic updates, transitive invalidation, locked fields, memory conflicts, Runtime restart recovery, Gateway tool visibility, authorization, guardrail intervention, context growth, and concurrent session writes in `tests/`.
- [ ] T069 Document environment configuration, SDK version pins, data retention, deletion, SLOs, provider contracts, operational runbooks, and rollback strategy in `docs/`.

## Phase 19: AWS CDK Infrastructure

- [X] T070 Create the greenfield CDK v2 application under `cdk/` with pinned runtime and development dependencies, environment configuration, and no synthesis-time side effects.
- [X] T071 Define `cdk/stacks/stateful_stack.py` for DynamoDB, KMS, Secrets Manager, queues/topics, and event resources with environment-specific retention, encryption, termination protection, and backup policies.
- [ ] T072 Define `cdk/stacks/shared_stack.py`, `gateway_stack.py`, `runtime_stack.py`, and `observability_stack.py` only where lifecycle or deployment boundaries justify them; keep unrelated stacks independent.
- [ ] T073 Apply the organization permissions boundary with the CDK `PermissionsBoundary` API and implement least-privilege grants using L2 grant methods before any manual policy statements.
- [ ] T074 Implement environment tags, log groups, retention, data protection, alarms, X-Ray configuration, and CDK Nag checks in `cdk/constructs/` with documented, resource-scoped suppressions.
- [ ] T075 Implement cross-stack handoffs in `cdk/stacks/` using direct CDK references within the app and SSM only for independently deployed or runtime-resolved values; add parameter ownership and missing-parameter tests in `cdk/tests/`.
- [X] T076 Add `cdk.context.json` only for reviewed context lookups and make `cdk synth` deterministic without account mutation or network calls during normal CI synthesis.
- [ ] T077 Add CDK fine-grained assertions in `cdk/tests/test_security.py` for logical IDs, encryption, boundaries, IAM actions/resources, removal policies, tags, log retention, alarms, and environment overrides; use snapshots only where stable.
- [ ] T078 Add optional CDK integration tests in `cdk/tests/integ/` in a sandbox account after unit synthesis tests pass, covering deployment, runtime invocation, Gateway access, alarms, and rollback behavior.
- [ ] T079 Add controlled CI/CD commands for CDK tests, `cdk synth`, security checks, `cdk diff` or change-set generation, environment approval, federated deployment, and rollback; prohibit long-lived credentials and unreviewed production deploys.
- [ ] T080 Add resource discovery in `cdk/resource_discovery.py` only if repeated resource types justify it, with YAML schema validation, repository-root path resolution, registered-type allowlists, deterministic sorting, safe disable behavior, and discovery tests in `cdk/tests/test_resource_discovery.py`.
- [ ] T081 Document explicit-name exceptions, generated-name defaults, stack dependencies, SSM ownership, KMS boundaries, removal policies, bootstrap requirements, and deployment runbooks in `docs/infrastructure.md`.

## Phase 20: Shared Agent Framework

- [X] T082 Create `aria/framework/contracts.py` with runtime-checkable typed protocols for prompt builders, payload parsers, tool filters, skills builders, and pre-invocation guards, plus a validated parsed-turn model.
- [X] T083 Create `aria/framework/config.py` with lazy, validated, immutable configuration loading from approved environment/SSM sources; add safe diagnostics and tests for missing/transient configuration.
- [ ] T084 Create `aria/framework/gateway.py` with centralized SigV4/MCP or supported Gateway authentication, client lifecycle, timeouts, retries, and cleanup; prevent agent modules from duplicating authentication.
- [ ] T085 Create `aria/framework/memory.py` and `aria/framework/context.py` for bounded, tenant-scoped retrieval and dynamic context assembly with current workflow state precedence, redaction, and a plain-text provider-compatible fallback.
- [ ] T086 Create `aria/framework/model.py` with the pinned Strands/Bedrock model construction, structured-output configuration, retry policy, token/turn budgets, and model-cache options only after SDK compatibility tests pass.
- [ ] T087 Create `aria/framework/hooks.py` and `aria/framework/observability.py` with composable Strands lifecycle hooks, redaction-safe telemetry, latency/token/stop-reason metrics, tool limits, and expected-error classification.
- [X] T088 Create `aria/framework/runner.py` as the shared orchestration boundary with dependency injection, tested cleanup/finally behavior, state patch handoff, memory persistence, and supported sync/stream/async invocation modes.
- [X] T089 Create and validate the per-agent manifest schema under `aria/agents/<agent_name>/agent.yaml`, separating deployment fields from framework tuning and rejecting unknown or unsafe values.
- [X] T090 Migrate the first Aria agent to `aria/agents/<agent_name>/agentcore_entrypoint.py` plus `aria/agents/<agent_name>/system_prompt.py`, keeping business workflow, models, guards, skills, and tool filtering in agent-specific modules.
- [ ] T091 Add framework unit and contract tests in `tests/framework/` with mocked AgentCore Runtime, Gateway, Memory, Bedrock model, Strands hooks, configuration failures, guardrail interventions, tool failures, cancellation, and cleanup paths.
- [X] T092 Add a second minimal test agent under `aria/agents/framework_smoke/` and verify it can be discovered, synthesized, invoked, observed, and removed without modifying shared framework or CDK wiring.
- [ ] T093 Benchmark bounded context, memory retrieval, provider cache behavior, tool count, model latency, total latency, and cost in `tests/benchmarks/test_agent_framework.py` before enabling provider-specific optimizations in production.
- [ ] T094 Document framework extension contracts, manifest schema, lifecycle ordering, supported SDK versions, local-development boundary, and intentionally unimplemented provider-specific assumptions in `docs/agent-framework.md`.

## Dependencies and Execution Order

- Phase 1 precedes Phase 2; Phase 2 blocks all user stories.
- P1 stories can proceed in parallel after foundational work, with US1 and US14 providing shared context.
- P2 stories depend on the relevant P1 tools and can then proceed in parallel.
- Agent assembly and cross-cutting validation depend on all selected MVP stories.

## MVP Scope

Complete Setup, Foundational, US1, US5, US6, US7, US8, US9, US10, US12, US13, and US14 with mocked external services. This delivers a safe, compliant, context-aware service and escalation core before adding cross-sell breadth and proactive retention.

## Parallel Opportunities

- T003-T005 can run in parallel.
- T007-T010 can run in parallel after package scaffolding.
- Independent P1 story model, tool, and test tasks can run in parallel once foundational contracts are stable.
- T053-T055 can run in parallel after agent assembly.
- T058-T060 can run in parallel after the domain model is stable; T061 depends on T058-T060.
- T062-T065 can run in parallel once the provider contracts and authorization model are approved.
- T066-T069 can run in parallel after the application boundaries are defined.
- T070 must complete before T071-T081; T071-T074 can then proceed in parallel with T077.
- T075-T076 depend on the selected stack boundaries and environment model.
- T078 depends on T071-T077 and an isolated AWS sandbox account.
- T079 and T081 can proceed in parallel after the CDK app and security contracts are defined.
- T080 is optional and must not block the first deployable Aria infrastructure slice.
- T082-T087 can proceed in parallel after SDK versions and provider contracts are pinned; T088 depends on those contracts.
- T089 can proceed in parallel with T082-T087; T090 depends on T082-T089.
- T091-T093 depend on the first runner implementation; T094 can proceed in parallel with framework testing.
