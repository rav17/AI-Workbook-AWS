# Tasks: Production Readiness Remediation

**Input**: Design documents from `/specs/002-production-readiness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/invocation.md`, `quickstart.md`

## Phase 1: Setup

- [x] T001 Add deterministic dependency lock inputs for application, Lambda, Runtime, and CDK CLI in `pyproject.toml`, `uv.lock`, and `.github/workflows/deploy.yml`.
- [x] T002 Add deployment artifact build and inspection helpers with generated-output ignores in `scripts/build_artifacts.py` and `.gitignore`.

## Phase 2: Foundational Tests

- [x] T003 [P] Add API auth/claim-boundary tests in `tests/unit/test_api_and_events.py`.
- [x] T004 [P] Add KYC fail-closed tests in `tests/unit/test_service_and_compliance.py`.
- [x] T005 [P] Add CDK security/package/runtime assertions in `cdk/tests/test_security.py`.
- [x] T006 [P] Add Runtime payload/guardrail and Gateway event-contract tests in `tests/framework/test_agentcore_entrypoint.py` and `tests/unit/test_api_and_events.py`.
- [x] T007 [P] Add artifact exclusion, dependency-import, and size-limit tests in `tests/unit/test_deployment_artifacts.py`.

## Phase 3: User Story 1 - Trusted Client Access (Priority: P1)

**Goal**: Only verified client identities and authoritative compliance status can reach protected workflows.

**Independent Test**: Auth boundary tests reject absent/invalid credentials before agent execution, validated claims determine tenant/user, and protected actions deny missing/invalid KYC.

- [x] T008 [US1] Add a required Cognito/JWT authorizer and deployment issuer/audience inputs in `cdk/stacks/application_stack.py`.
- [x] T009 [US1] Require validated subject and tenant claims and remove header/payload/anonymous identity fallbacks in `aria/api/rest_handler.py` and `aria/api/runtime_session.py`.
- [x] T010 [US1] Define an injectable `KYCStatusProvider` contract and fail closed on missing, errored, malformed, or unsupported status in `aria/tools/compliance_tool.py` and `aria/agent.py`; concrete provider integration and credentials remain an external prerequisite.
- [x] T011 [US1] Add CDK and handler tests proving unauthenticated requests and spoofed claims never call agent/tool code in `cdk/tests/test_security.py` and `tests/unit/test_api_and_events.py`.

## Phase 4: User Story 2 - Deployable and Constrained AWS Artifacts (Priority: P1)

**Goal**: Build small reproducible Lambda and Runtime assets with current AgentCore Runtime configuration and least-privilege roles.

**Independent Test**: Build artifacts from the repository and verify contents/limits; synth assertions verify supported Runtime, MMDSv2, conditioned trust, and scoped permissions.

- [x] T012 [US2] Implement isolated Lambda and Runtime artifact assembly from `uv.lock`, explicit exclusions, and size reporting in `scripts/build_artifacts.py`.
- [x] T013 [US2] Point Lambda and Runtime CDK assets at generated artifacts and fail clearly when artifacts are missing in `cdk/stacks/application_stack.py`, `cdk/stacks/gateway_stack.py`, and `cdk/stacks/runtime_stack.py`.
- [x] T014 [US2] Select supported Python 3.13 and enable MMDSv2 through the ordered `UpdateAgentRuntime` custom resource in `cdk/stacks/runtime_stack.py` and `cdk/custom_resources/enable_mmdsv2.py`.
- [x] T015 [US2] Restrict Runtime/Gateway/Memory service trust and scope model/Memory/Gateway actions in `cdk/stacks/runtime_stack.py`, `cdk/stacks/stateful_stack.py`, and `cdk/stacks/gateway_stack.py`.
- [x] T016 [US2] Verify generated packages are Linux-compatible, under Lambda size limit, and exclude local environments/session/test roots in `tests/unit/test_deployment_artifacts.py`.

## Phase 5: User Story 3 - Safe Stateful Agent Execution (Priority: P1)

**Goal**: Runtime invokes the actual safe Strands workflow, persists authoritative state, scopes Memory by tenant, and dispatches Gateway tools using AWS's target contract.

**Independent Test**: Fake-backed entrypoint tests cover payload validation, guardrails, Strands dispatch, restart recovery, tenant isolation, and Gateway call success/denial.

- [x] T017 [US3] Validate Runtime prompt schema, reject structured/tool-use payloads, accept only the backend-verified principal from the restricted API Lambda path, and fail closed on missing Runtime configuration in `aria/agents/aria/agentcore_entrypoint.py`.
- [x] T018 [US3] Invoke Strands from Runtime and enforce input/output guardrails with safe stop handling in `aria/agents/aria/agentcore_entrypoint.py` and `aria/guardrails/processor.py`.
- [x] T019 [US3] Implement durable DynamoDB idempotency claims with leases, owner-scoped completion/release, API `Idempotency-Key` handling, duplicate conflict responses, optional owner-configured TTL, and restart/retry tests in `aria/persistence/store.py`, `aria/api/runtime_session.py`, and `cdk/stacks/stateful_stack.py`; DynamoDB session records retain conditional revision checks.
- [x] T020 [US3] Keep AgentCore Memory writes/extraction disabled until owner policy approval; distinguish 30-day event expiry from extracted-record retention, and define paginated tenant/user erasure in `aria/framework/agentcore.py` and `specs/002-production-readiness/research.md`.
- [x] T021 [US3] Adapt Gateway Lambda to direct event arguments and `bedrockAgentCoreToolName`, validate and sanitize tool inputs/outputs, and fail closed for customer-specific calls without an approved subject-to-customer mapping in `aria/api/gateway_handler.py`.
- [x] T022 [US3] Add Runtime safety, session recovery/concurrency, tenant Memory, and Gateway event contract tests in `tests/framework/test_agentcore_entrypoint.py` and `tests/framework/test_agentcore_adapters.py`.
- [x] T028 [US3] Route authenticated REST and WebSocket requests through SigV4 AgentCore Runtime invocation, resolve the Runtime ARN through SSM, and restrict Runtime resource-policy access to the request Lambda role in `aria/api/`, `cdk/stacks/application_stack.py`, and `cdk/stacks/runtime_stack.py`.

## Phase 6: User Story 4 - Verifiable Releases and Operations (Priority: P1)

**Goal**: CI/CD, CDK tests, telemetry, retention, and documentation require evidence and no longer overstate production readiness.

**Independent Test**: CI runs application/CDK/artifact gates; deployment tooling is pinned and protected; docs/tasks distinguish implementation, tests, synth, deploy, and invocation.

- [x] T023 [US4] Add CDK synth, CDK tests, artifact checks, audits for root/dev/CDK dependencies, and secret scans to `.github/workflows/quality.yml` and `.github/workflows/deploy.yml`.
- [x] T024 [US4] Pass the required permissions boundary to production synth, diff, and deploy; require quality/synth/diff and protected approval before deploy in `.github/workflows/deploy.yml`; external OIDC trust/environment reviewer configuration remains unverified.
- [x] T025 [US4] Add explicit log retention, CloudWatch sensitive-data audit/masking, configurable provisional SLO alarms, and an SNS alarm destination in `cdk/stacks/` and `cdk/cdk_constructs/`; application redaction already exists, while on-call SNS subscription remains external.
- [x] T026 [US4] Reconcile deployment/framework/README claims and document external prerequisites/evidence limits in `README.md`, `docs/deployment.md`, `docs/agent-framework.md`, and the original task tracker.
- [x] T027 [US4] Run strict formatting/lint/type, full Python, CDK, package, and security gates; record AWS sandbox deploy/invoke/rollback as `not_run` in `specs/002-production-readiness/quickstart.md` because sandbox credentials and external provider configuration are unavailable.

## Phase 7: User Story 2 and 3 Follow-up - Runtime Routing, Safe Gateway Tools, and Artifact Compatibility

**Goal**: Ensure the deployed API uses the existing Runtime coordinator, Strands can invoke a narrow safe Gateway tool, Gateway payloads are guarded, and each artifact matches its managed runtime platform.

**Independent Test**: Mock the Runtime and Gateway MCP client; prove an authenticated deployed-handler call reaches Runtime, only the explicitly allowed client-independent tool is registered, unsafe Gateway inputs/results fail closed, and artifact metadata distinguishes Lambda from Runtime.
- [x] T029 [US3] Route the configured Lambda entrypoint to the authenticated durable Runtime handler and test that API invocation reaches the mocked Runtime client in `aria/api/lambda_entry.py` and `tests/unit/test_api_and_events.py`.
- [x] T030 [US3] Replace the customer-message Gateway target with the argument-free `get_risk_questionnaire` tool and restrict the Gateway allowlist to client-independent tools in `cdk/stacks/gateway_stack.py`, `aria/api/gateway_handler.py`, and `cdk/tests/test_security.py`.
- [x] T031 [US3] Connect Strands MCPClient to the SigV4 Gateway `/mcp` endpoint and register only the explicit tool allowlist in `aria/agents/aria/agentcore_entrypoint.py` and `aria/framework/gateway.py`; add fake-client registration/lifecycle tests in `tests/framework/test_agentcore_entrypoint.py`.
- [x] T032 [US3] Enforce strict Gateway argument shape/size and sanitize serialized arguments/results with `GuardrailProcessor`, returning generic errors for blocked content in `aria/api/gateway_handler.py`; add boundary tests in `tests/framework/test_agentcore_adapters.py`.
- [x] T033 [US2] Select `x86_64-manylinux2014` for Lambda and `x86_64-manylinux_2_28` for Runtime dependency builds, then assert target/platform separation in `scripts/build_artifacts.py` and `tests/unit/test_deployment_artifacts.py`.

## Phase 8: User Story 4 Follow-up - Workflow Supply Chain and Release Configuration

**Goal**: Make the workflow reproducible and ensure production configuration is present before synth/diff; preserve external OIDC/environment verification as an explicit release gate.

**Independent Test**: Parse both workflows, confirm every third-party action uses a full commit SHA, and prove prod synth/diff/deploy receive the same required boundary variable while dev remains usable without it.

- [x] T034 [US4] Pin checkout, setup-uv, setup-python, setup-node, and AWS credential actions to verified full commit SHAs in `.github/workflows/quality.yml` and `.github/workflows/deploy.yml`.
- [x] T035 [US4] Add workflow configuration tests for immutable action references and permissions-boundary propagation in `tests/unit/test_deployment_artifacts.py`.
- [x] T036 [US4] Record fresh test/synth/artifact results and retain AWS deploy/invocation, OIDC trust, and production environment reviewer status as `not_run` or `not_verified` unless external evidence is available in `specs/002-production-readiness/quickstart.md`.

## Dependencies and Execution Order

- T001-T002 establish repeatable packages and tool versions before artifact-related implementation.
- T003-T007 are focused failing checks and precede behavior edits.
- User stories depend on the foundational tests; execute US1 before exposing any protected tool path.
- T012-T016 package/runtime changes precede Runtime deployment validation.
- T017-T022 connect the Runtime, persistence, Memory, and Gateway paths after authentication and packaging contracts exist.
- T023-T027 close CI/release/documentation gates; T027 is the final acceptance gate.
- T029-T032 complete API routing and safe Gateway wiring; customer-specific tools remain disabled pending an external mapping contract.
- T033 can be built and tested independently of T029-T032.
- T034-T035 provide immutable action and boundary configuration gates; T036 records evidence only after the final local checks.

## Parallel Opportunities

- T003-T007 can be authored in separate test files in parallel.
- Within US2, artifact exclusions/tests and Runtime schema research can proceed independently after T001-T002.
- US4 documentation reconciliation can proceed after core implementation facts are established; workflow/test edits should not conflict with application source work.

## Implementation Strategy

1. Establish locks/build tooling and write failing focused tests.
2. Complete trusted API identity and compliance gates first.
3. Build constrained deployment artifacts and correct Runtime/IAM settings.
4. Connect safe Runtime execution, durable state, Memory, and Gateway handling.
5. Gate release, correct evidence claims, and run all available validations.
6. Do not mark sandbox deployment/invocation complete without actual AWS evidence.

## Phase 9: T020 Follow-up - Memory Policy and Erasure

**Goal**: Prevent unapproved client-data extraction and provide complete, tenant/user-scoped erasure semantics without claiming an unapproved retention schedule.

**Independent Test**: A fake AgentCore data-plane client observes no write call; paginated user erasure deletes every validated in-scope record, rejects cross-tenant access, and propagates any partial failure as incomplete.

- [x] T037 [P] [US3] Add adapter tests for default-deny Memory writes, paginated actor-namespace enumeration/deletion, malformed/out-of-scope records, and partial failures in `tests/framework/test_agentcore_adapters.py`.
- [x] T038 [US3] Make live AgentCore Memory writes fail closed and implement bounded `ListMemoryRecords` pagination followed by per-record deletion for the authenticated actor namespace in `aria/framework/agentcore.py`; return success only after all deletes complete.

## Phase 10: T025 Follow-up - Operational Alarms and Log Data Protection

**Goal**: Protect service Lambda logs and publish actionable signals for API errors/latency, Lambda failures/throttles, and detected sensitive values using explicit provisional thresholds.

**Independent Test**: CDK synthesis shows explicit seven-day log groups with matching audit/masking policies, alarms with configured metrics/thresholds and SNS actions, and no raw prompt logging changes; alarm/SLO values are documented as provisional.

- [x] T039 [P] [US4] Add synth assertions for application/Gateway/workflow log retention and data-protection identifiers, API/Lambda/findings alarms, provisional thresholds, and SNS actions in `cdk/tests/test_security.py`.
- [x] T040 [US4] Create a shared CloudWatch observability construct, explicit Lambda log groups with audit/masking, an encrypted operations SNS topic, API error-rate/p95 alarms, Lambda error/throttle alarms, and sensitive-log findings alarms in `cdk/cdk_constructs/observability.py`, `cdk/stacks/application_stack.py`, `cdk/stacks/gateway_stack.py`, and `cdk/stacks/stateful_stack.py`.
- [x] T041 [US4] Document the current no-write Memory policy, owner approvals required to enable writes, proposed SLOs/provisional alarm thresholds, seven-day log retention basis, and SNS subscription prerequisite in `docs/deployment.md` and `specs/002-production-readiness/quickstart.md`.
- [x] T042 [US4] Run focused Memory/CDK tests, full Python and CDK tests, formatting/lint/type checks, dev synthesis, and Graphify refresh; record results and external AWS/on-call limitations in `specs/002-production-readiness/quickstart.md`.

## Phase 11: Synchronous API Timeout Budget

**Goal**: Prevent the request Lambda from inheriting AWS's three-second default while ensuring API Gateway remains the outer synchronous deadline.

**Independent Test**: CDK synthesis asserts a 28-second timeout for the Runtime request Lambda and a 29-second API Gateway integration timeout; no request integration can outlive API Gateway's default REST API limit.

- [x] T043 [P] [US3] Add CDK assertions for explicit request Lambda timeout and API Gateway integration timeout in `cdk/tests/test_security.py`.
- [x] T044 [US3] Set the request Lambda timeout to 28 seconds and its API Gateway Lambda integration timeout to 29 seconds in `cdk/stacks/application_stack.py`.
- [x] T045 [US4] Run focused and full tests, coverage, lint/format/type/lock/secrets checks, artifact build, CDK synth, and Graphify refresh; record AWS account/deployment limitations in `specs/002-production-readiness/quickstart.md`.

## Phase 12: Repository CI Formatting Scope

**Goal**: Keep the global Ruff gates focused on application and test code without reformatting the documentation-only XML diagram generator.

**Independent Test**: Repository-wide Ruff format and lint commands pass, while application modules and tests remain included in both checks.

- [x] T046 [US4] Exclude only the XML-heavy architecture diagram generator from global Ruff checks in `pyproject.toml` so application/test lint and format gates can run without unrelated diagram-string changes.
