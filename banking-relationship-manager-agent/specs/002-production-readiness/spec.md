# Feature Specification: Production Readiness Remediation

**Feature Branch**: `002-production-readiness`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User request to fix all issues identified in the production-readiness audit.

## User Scenarios & Testing

### User Story 1 - Trusted Client Access (Priority: P1)

As a client and compliance officer, I need every client request to be authenticated, attributable to a verified tenant and user, and checked against authoritative compliance status so that untrusted requests cannot access customer workflows or bypass KYC controls.

**Why this priority**: The current public API has no authorizer and request payload fields can influence identity and KYC decisions.

**Independent Test**: Exercise every public entry point with absent, malformed, expired, and valid credentials; verify only verified claims establish tenant/user identity and unverified KYC is denied.

**Acceptance Scenarios**:
1. Given no valid credential, when a client calls a public endpoint, then the request is rejected before agent or tool execution.
2. Given a valid identity token, when the request is processed, then tenant and user identity come only from validated claims and cannot be replaced by payload fields.
3. Given KYC is missing, expired, or unavailable from the authoritative provider, when a protected product action is requested, then the action fails closed with an appropriate next step.

### User Story 2 - Deployable and Constrained AWS Artifacts (Priority: P1)

As an operator, I need small, reproducible deployment artifacts and current, least-privilege AWS Runtime configuration so deployments can be reviewed and invoked without local machine contents or unsafe roles.

**Why this priority**: The existing Lambda asset exceeds the uncompressed deployment limit and carries local environment/session content; Runtime settings and roles do not meet current AWS guidance.

**Independent Test**: Build artifacts from a clean checkout, inspect their manifests and sizes, synthesize each environment, and validate runtime version, MMDSv2, trust conditions, and scoped permissions.

**Acceptance Scenarios**:
1. Given a clean build, when Lambda and Runtime artifacts are produced, then they contain only required application files and dependencies and meet the service package limits.
2. Given a deployment environment, when infrastructure is synthesized, then Runtime uses a supported language version, requires MMDSv2, and service-role trust is constrained to the intended account/resources.
3. Given a policy review, when Runtime and Memory permissions are inspected, then each action is current and scoped to required models, memories, gateway, and tenant namespaces.

### User Story 3 - Safe Stateful Agent Execution (Priority: P1)

As a client, I need requests to pass through the actual configured agent, safety checks, durable session handling, and tenant-scoped memory so responses and tools behave consistently across turns and failures.

**Why this priority**: The Runtime entrypoint does not invoke the Strands runner; guardrails, durable storage, and live Memory integrations are not on the request path; Gateway's handler does not match its invocation contract.

**Independent Test**: With provider services mocked, invoke the Runtime entrypoint using valid and invalid payloads, verify Strands execution and guardrails, persist/recover session state, isolate tenants, and invoke a tool through the documented Gateway event shape.

**Acceptance Scenarios**:
1. Given a valid prompt, when Runtime handles the request, then schema validation and input controls run before Strands and output controls run before the response is returned.
2. Given a process restart or concurrent request, when the same authenticated conversation resumes, then authoritative state is recovered and concurrent writes do not silently overwrite each other.
3. Given a tenant-scoped memory request, when records are retrieved or deleted, then no other tenant's records are visible and configured retention/deletion is honored.
4. Given an authenticated API request, when the deployed Lambda handler processes it, then it invokes AgentCore Runtime through the durable session coordinator and has an explicit timeout longer than AWS's three-second default.
9. Given the request Lambda reaches its configured 28-second timeout, when API Gateway waits up to its configured 29-second integration deadline, then the Lambda is terminated before the integration deadline expires.
5. Given no data-owner-approved Memory policy, when any component attempts to write or extract client data, then the operation is rejected without storing short- or long-term Memory content.
6. Given an approved erasure request, when records are enumerated and deleted, then deletion is restricted to the authenticated user's tenant-scoped namespaces and completion is reported only after every matching record is deleted.
7. Given the Runtime connects to Gateway, when Strands starts, then only explicitly allowlisted client-independent tools are exposed; customer-specific tools remain unavailable until an authoritative subject-to-customer mapping is configured.
8. Given a Gateway Lambda target invokes a tool, when the documented event and client context are delivered, then the handler validates and sanitizes arguments and results, identifies the allowed tool, and fails closed for unauthorized or unsafe calls.
9. Given a synchronous API request exceeds the configured processing deadline, when API Gateway ends the integration, then the Lambda does not continue running beyond the configured API request budget.

### User Story 4 - Verifiable Releases and Operations (Priority: P1)

As an operator and reviewer, I need CI/CD, CDK assertions, monitoring, retention guidance, and task status to reflect actual evidence so a release cannot be mistaken for deployed or production-ready without validation.

**Why this priority**: Current gates omit CDK tests/synthesis and dependency coverage, deploy tooling floats, and task/documentation claims overstate integrations.

**Independent Test**: Run quality and CDK gates without AWS credentials, inspect the deploy workflow's protected approval path, and compare documentation/task claims to implementation and recorded deployment evidence.

**Acceptance Scenarios**:
1. Given a code change, when CI runs, then Python tests/security scans, CDK tests, synthesis, and artifact checks are required before deployment.
2. Given a production deployment request, when the workflow runs, then the permissions boundary is available to synth, diff, and deploy, third-party actions are pinned to immutable revisions, and a federated role, protected environment, and reviewed diff are required before applying changes.
3. Given a feature status is reported, when implementation, tests, synth, deploy, and invocation evidence are reviewed, then each is represented separately and unsupported completion claims are removed.
4. Given deployment artifacts are built for Lambda and AgentCore Runtime, when native wheels are installed, then each artifact targets the operating-system ABI of its respective managed runtime.
5. Given the service is deployed, when API errors, latency, Lambda failures/throttles, or sensitive-data findings exceed configured thresholds, then CloudWatch alarms publish to the configured operations topic; thresholds remain provisional until traffic baselines and owners approve SLOs.
6. Given application logs are ingested, when supported sensitive identifiers are detected, then CloudWatch records audit findings and masks matching values from standard log access without relying on masking to protect previously ingested events.

## Edge Cases

- API Gateway supplies claims using a different authorizer event shape than the local tests.
- A valid identity has no tenant claim, or tenant/user identifiers contain unsafe namespace characters.
- The KYC provider is unavailable, times out, or returns malformed/expired status.
- Runtime or Memory SDK imports/configuration are absent in a deployed artifact.
- A Gateway tool receives malformed, oversized, credential-bearing, or prompt-injection content in its arguments or result.
- A Runtime user has no authoritative mapping to a customer record and a model attempts a customer-specific tool call.
- Lambda and Runtime artifacts resolve different native wheel variants for their distinct operating-system baselines.
- A production deployment environment has no permissions-boundary value or its external OIDC/reviewer policy is not configured.
- A client-supplied structured message contains tool-use blocks or a prompt field of the wrong type.
- DynamoDB condition checks fail, retries occur, or an idempotency key is reused across tenants.
- Memory returns no records, malformed records, or records outside the requested namespace.
- Gateway target names are prefixed and the tool name is only available in Lambda client context.
- AWS updates service runtime requirements or CloudFormation property schemas after dependency pinning.
- External AWS account, identity-provider, OIDC trust, and approval settings cannot be inspected from this repository.

## Requirements

### Functional Requirements

- **FR-001**: Every public chat/API route MUST require a configured, validated authentication mechanism and reject unauthenticated requests before agent execution.
- **FR-002**: Tenant and user identities MUST derive only from verified authorizer claims or trusted AWS identity context; payload-supplied identity and anonymous/default tenant fallbacks MUST NOT authorize access.
- **FR-003**: Protected product actions MUST require current KYC from an authoritative provider and fail closed when status is missing, expired, malformed, or unavailable.
- **FR-004**: Deployment packages MUST be reproducible from declared locked dependencies, exclude virtual environments, local sessions, caches, tests, and secrets, and satisfy each target service's documented package limits.
- **FR-005**: AgentCore Runtime MUST use a currently supported Python runtime and explicitly require MMDSv2; synthesized infrastructure MUST assert both settings.
- **FR-006**: AgentCore service trust policies MUST restrict source account and resource; execution permissions MUST use current service actions and least-privilege resource scopes.
- **FR-007**: The deployed API request handler MUST route authenticated requests through the durable Runtime coordinator; the Runtime entrypoint MUST validate request schema, invoke the configured Strands runner, and handle model/tool/guardrail stop outcomes explicitly.
- **FR-008**: Input and output safety checks MUST be integrated in every public agent execution path, including Gateway tool arguments and results; caller-provided tool-use blocks MUST be rejected and protected content MUST not be logged or persisted.
- **FR-009**: Authenticated conversation state MUST be durably stored and recoverable across process/runtime restarts with conditional revision checks and tenant-scoped idempotency.
- **FR-010**: Live AgentCore Memory retrieval and deletion MUST use tenant-specific namespaces and bounded pagination. Writes and extraction MUST remain disabled until the data owner approves allowed derived-data categories, notice/consent basis, source-event and extracted-record retention, and an auditable deletion process. `EventExpiryDuration` MUST NOT be represented as extracted-record retention. Erasure MUST enumerate and delete every record in scope, and report completion only after all deletions succeed.
- **FR-011**: Gateway Lambda targets MUST implement the documented event and client-context contract; Strands MUST receive only explicitly allowlisted Gateway tools; tool allowlisting MUST be combined with backend authorization and Gateway/IAM policy; customer-specific tools MUST fail closed until a trusted subject-to-customer mapping exists.
- **FR-012**: Observability MUST redact sensitive values, emit correlation and safe error/latency/status metadata, set explicit log retention, and provide CloudWatch audit/masking policies and actionable alarms for API availability/latency, Lambda errors/throttles, and sensitive-log findings without logging raw prompts. Starter alarm thresholds MUST be configurable and documented as provisional until traffic baselines and service owners approve SLOs; alarm notifications MUST publish to an operations topic whose on-call subscription is an external deployment prerequisite.
- **FR-013**: CI MUST run Python quality/security checks, CDK tests and synth, dependency audits for app/CDK/dev dependencies, and package-content/size assertions.
- **FR-014**: Deployment tooling and third-party workflow actions MUST be immutably pinned, use OIDC with an explicitly scoped trust policy, require protected production approvals and reviewed changes, and pass the required permissions boundary consistently to synth, diff, and deploy; rollback MUST be documented and no long-lived credentials are allowed.
- **FR-015**: Documentation and task status MUST distinguish source implementation, automated test coverage, fresh CDK synthesis, deployment, and successful AWS invocation; unavailable external evidence MUST remain explicitly unverified.
- **FR-016**: Lambda and AgentCore Runtime artifacts MUST use native dependency wheels compatible with their respective managed operating-system baselines, and artifact validation MUST reject incompatible target configuration.
- **FR-016**: Lambda and AgentCore Runtime artifacts MUST use native dependency wheels compatible with their respective managed operating-system baselines, and artifact validation MUST reject incompatible target configuration.
- **FR-017**: The synchronous request Lambda and API Gateway integration MUST have explicit, compatible timeouts. The Lambda timeout MUST exceed the AWS default of three seconds, remain below the API Gateway integration timeout, and the integration timeout MUST respect the account's REST API limit unless an increased quota is verified.

### Key Entities

- **VerifiedPrincipal**: Authenticated tenant, subject, scopes, and issuer-derived identity used for authorization.
- **DeploymentArtifact**: Target service, reproducible dependency manifest, packaged files, and measured archive/unpacked size.
- **ConversationState**: Tenant/user/conversation identity, revision, authoritative workflow state, and idempotency metadata.
- **MemoryRecord**: Tenant-scoped namespace, actor/session identifiers, content category, expiry, and deletion status.
- **ReleaseEvidence**: Commit/build identity and separate test, synth, deploy, and invocation outcomes.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of public API tests reject missing/invalid credentials before any agent or tool callback is invoked.
- **SC-002**: 100% of identity/tenant tests show payload fields cannot override verified principal claims.
- **SC-003**: Every generated Lambda artifact is below the AWS 250 MB uncompressed limit and contains no local virtual environment, test session, cache, or secret fixture.
- **SC-004**: Clean-artifact Runtime startup succeeds with required dependencies and fails with an actionable error when they are absent.
- **SC-005**: CDK assertions verify supported Runtime, MMDSv2, conditioned trust, scoped service permissions, authenticated API method, and package exclusions.
- **SC-006**: Tests demonstrate guardrail enforcement, durable state recovery, tenant-isolated Memory operations, and successful Gateway invocation using the documented Lambda event shape.
- **SC-007**: Tests prove every deployed API request reaches AgentCore Runtime and that the Runtime exposes only safe allowlisted Gateway tools; customer-scoped tools are denied without an authoritative mapping.
- **SC-008**: Required CI checks block deployment on any failed test, security scan, synth, or artifact check; production synth, diff, and deploy use the same required permissions boundary and production deployment requires protected approval and a reviewed diff.
- **SC-009**: Each deployment artifact passes a runtime-specific native-wheel compatibility check before CDK synthesis.
- **SC-010**: Every reported completion claim maps to separate test, synth, deployment, or invocation evidence; absent AWS access is reported as unverified.
- **SC-011**: Without documented data-owner approval for categories, notice/consent, retention, and deletion, every AgentCore Memory write attempt fails closed and does not call a Memory write API.
- **SC-012**: For an approved deletion scope, every matching tenant-scoped record is enumerated across pages and deleted; partial or failed deletion is reported as incomplete.
- **SC-013**: Synthesized application and Gateway Lambda log groups have explicit retention and matching CloudWatch audit/masking identifiers, and alarms for API 5xx/latency, Lambda errors/throttles, and sensitive-log findings publish to the operations SNS topic.
- **SC-014**: Alarm thresholds are explicit, configurable starting values and are labeled provisional; the repository does not claim an approved production SLO without measured traffic baselines and owner sign-off.
- **SC-015**: CDK synthesis verifies an explicit request-Lambda timeout of 28 seconds and API Gateway integration timeout of 29 seconds, so the Lambda cannot be terminated at the three-second default or run after API Gateway has returned.

## Assumptions

- The project will continue using AWS CDK v2, Python, Strands, AgentCore Runtime/Memory/Gateway, API Gateway, Lambda, and DynamoDB.
- Identity-provider issuer/audience, authoritative CRM/KYC API, AWS account/region, production OIDC trust, and environment approvals are external deployment inputs; missing required security configuration fails closed.
- Local and CI tests use deterministic fakes; real deployment/invocation validation requires an explicitly configured non-production AWS account.
- Runtime identity cannot be treated as a customer record mapping. Customer-specific Gateway tools remain disabled until the application owner provides and approves an authoritative mapping contract.
- GitHub OIDC trust conditions and environment reviewer/branch protections are configured outside this repository and remain unverified by local CI.
- This remediation does not claim regulatory certification or invent banking retention periods; data owners must approve the required retention/deletion schedule before production.
- No owner-approved AgentCore Memory data categories, notice/consent basis, source-event retention, extracted-record retention, or full erasure workflow is present. Memory writes/extraction therefore remain disabled; specific-record deletion is not equivalent to user-wide erasure.
- Initial CloudWatch alarm thresholds are operational starting points only; an operations owner must review traffic baselines, approve SLOs, and subscribe the emitted SNS topic before production use.
