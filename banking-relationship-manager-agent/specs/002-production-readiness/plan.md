# Implementation Plan: Production Readiness Remediation

**Branch**: `002-production-readiness` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: User requested fixes for all findings in the 2026-10-01 production-readiness audit.

## Summary

Complete production-readiness remediation by routing the deployed API through the authenticated Runtime coordinator, connecting Strands to a narrowly allowlisted AgentCore Gateway tool, validating and sanitizing Gateway inputs/outputs, separating Lambda and Runtime wheel targets, and hardening production deployment configuration and workflow action references. Keep customer-specific Gateway operations disabled until an authoritative user-to-customer mapping is approved.

## Technical Context

**Language/Version**: Python 3.11 application baseline; AgentCore Runtime code version Python 3.13. Lambda Python 3.11 uses Amazon Linux 2; Runtime Python 3.13 uses Amazon Linux 2023.

**Primary Dependencies**: Existing `strands-agents==1.34.1`, `bedrock-agentcore==1.18.1`, boto3/botocore from `uv.lock`, Pydantic, httpx, AWS CDK v2 `2.270.0`, constructs `10.8.1`; Gateway access uses Strands MCPClient with SigV4 against the documented Gateway `/mcp` endpoint.

**Storage**: DynamoDB for authoritative conversation/workflow state and tenant-scoped idempotency; AgentCore Memory for bounded durable facts/preferences/summaries only.

**Testing**: pytest, Hypothesis, aws_cdk.assertions, handler/adapter unit tests, package manifest/size/runtime ABI checks, dependency/security scans; real AWS integration tests only in configured non-production accounts.

**Target Platform**: AWS Lambda/API Gateway, AgentCore Runtime/Memory/Gateway, and GitHub Actions using OIDC.

**Project Type**: Python agent service and AWS CDK infrastructure.

**Performance Goals**: Preserve configured request/context bounds; set production SLOs only after provider measurements.

**Constraints**: Reject missing identity, never use payload identity/KYC as authority, avoid raw sensitive content in logs/state, expose only client-independent Gateway tools until an approved subject-to-customer mapping exists, keep AgentCore Memory writes/extraction disabled until the data owner approves data categories, notice/consent basis, source-event and extracted-record retention, and erasure, target native wheels to each managed runtime OS, require production permissions-boundary configuration at synth/diff/deploy, use immutable workflow action SHAs, keep synthesis deterministic, and do not infer deployment from tests or synthesis. CloudWatch alarm thresholds are provisional until baseline traffic and service-owner SLO approval; the SNS topic needs an externally configured on-call subscription.

**Scale/Scope**: Audit-scoped remediation only; no redesign of all business features and no invented IdP/KYC provider contract.

## Constitution Check

- **PASS**: workflow truth stays in typed durable state, separate from session history and Memory.
- **PASS**: identity, KYC, tenant boundaries, tool authorization, and guardrails are deterministic controls outside prompts.
- **PASS**: provider boundaries are injectable; missing mandatory security/compliance configuration fails closed.
- **PASS**: package, dependency, test, synth, and release gates are explicit.
- **EXTERNAL RELEASE GATE**: IdP issuer/audience, KYC API, production OIDC trust, environment approvals, and approved retention periods need environment-owner configuration; tests use fakes and cannot establish those account-level facts.
- **No architecture exception**: use current owners/stacks; do not add stacks without lifecycle justification.

## Design

1. Protect API Gateway with a configured Cognito/JWT authorizer. Use only validated authorizer claims to derive tenant/user identity; reject direct handler calls without verified identity.
2. Introduce an authoritative compliance-provider contract; ignore request-body `kyc_status` and deny protected actions if status cannot be verified.
3. Create reproducible service-specific Lambda/Runtime artifacts from explicit dependency manifests. Exclude environments, local sessions, tests, caches, and secrets; assert artifact contents and size.
4. Upgrade Runtime to a currently supported Python code runtime; enable required MMDSv2 using current CloudFormation schema; condition trust with source account/resource and scope role permissions.
5. Route the deployed API Lambda through `rest_handler.handler`, preserving Cognito claims, DynamoDB session/idempotency coordination, and the SigV4 Runtime client.
6. Connect Strands to Gateway through MCPClient and SigV4. Publish only `get_risk_questionnaire`, which has no customer identifier or mutable customer state; reject customer-specific tools until a trusted identity-to-customer mapping contract is supplied.
7. Validate Gateway tool arguments against a strict per-tool schema, run input/output guardrails, bound serialized payload sizes, and return only sanitized JSON results.
8. Build Lambda wheels for `x86_64-manylinux2014` and Runtime wheels for `x86_64-manylinux_2_28`; validate target-specific metadata and imports.
9. Pass the production permissions boundary to synth, diff, and deploy; pin all third-party actions to verified full commit SHAs. Record OIDC trust and GitHub environment protections as external release gates.
10. Add CDK and unit assertions for routing, safe tool registration, input/output safety, artifact platforms, boundary propagation, and immutable action references.
11. Fail closed on every live AgentCore Memory write while policy approval is absent. Define erasure as listing all records below the authenticated user's namespace with bounded pagination, validating each returned namespace and ID, and deleting each record; a partial failure must not be reported as complete. Do not treat the Memory `EventExpiryDuration` as long-term record retention.
12. Create explicit seven-day CloudWatch log groups for application Lambdas (matching the existing workflow-log baseline), apply matching audit and de-identification identifiers for PII, financial identifiers, and credentials, and alarm on findings. Add API 5xx/error-rate and p95 latency alarms plus Lambda error/throttle alarms that publish to an SNS operations topic. Initial thresholds are configurable operational starters, not approved production SLOs.
13. Bound synchronous request handling with an explicit 28-second request-Lambda timeout and a 29-second REST API integration timeout; preserve a one-second response margin and keep the API integration within the default account quota.

## Project Structure

```text
aria/api/{lambda_entry,rest_handler,runtime_session,gateway_handler}.py
aria/agents/aria/agentcore_entrypoint.py
aria/framework/{agentcore,contracts,memory,runner,strands_runtime}.py
aria/guardrails/{config,processor}.py
aria/observability.py
aria/persistence/store.py
aria/tools/compliance_tool.py
cdk/stacks/{application,gateway,runtime,stateful}_stack.py
cdk/tests/test_security.py
tests/{framework,unit,property}/
.github/workflows/{quality,deploy}.yml
specs/002-production-readiness/{contracts/,data-model.md,quickstart.md,research.md,tasks.md}
```

**Structure Decision**: Modify existing modules and tests; add a helper only if required to keep artifact assembly deterministic and independently testable.

## Validation Gates

- Focused auth, KYC, API-to-Runtime routing, Runtime entrypoint, durable state, Memory, and Gateway contract tests.
- Fine-grained CDK assertions for API auth, Runtime support/MMDSv2, IAM trust/actions/resources, Memory namespaces, removal/retention policies, and deployment configuration.
- Built Lambda artifact <250 MB uncompressed and no `.venv*`, local session, tests, caches, or secrets; Lambda and Runtime native wheels are selected for their own operating-system baselines.
- CI passes formatting, lint, mypy, app tests, CDK tests/synth, dependency audit across app/CDK/dev inputs, secret scan, package inspection.
- Strands receives only safe allowlisted Gateway tools; customer-specific actions cannot be enabled without an approved identity-to-customer mapping.
- Production permissions boundary is present during synth/diff/deploy; workflow actions use immutable SHAs.
- Memory adapter tests prove the write API is never called while writes are disabled, paginated user erasure reaches all matching records only, and partial deletion fails visibly.
- CDK assertions verify explicit log groups/retention, matching audit and masking identifiers, configured CloudWatch alarms and SNS actions, and documented provisional thresholds.
- CDK assertions verify request Lambda and API Gateway integration timeouts are explicit and compatible with the REST API synchronous limit.
- Sandbox deploy/invoke/rollback is a distinct release gate requiring external AWS/IdP/KYC/OIDC configuration; unavailable evidence remains `not_run`.

## Risks and Open Decisions

- AgentCore runtime and MMDSv2 schema are time-sensitive; validate current AWS docs and deployed resource behavior in a sandbox.
- AWS_IAM Gateway MCP calls require SigV4 signing against the exact Gateway `/mcp` endpoint and a Gateway-supported MCP protocol version; only sandbox invocation proves the live service contract.
- Customer identity does not imply a CRM customer ID. Do not expose or infer a client mapping from model-provided tool arguments.
- Cognito pool/issuer, audience, tenant claim, KYC provider, AWS account, OIDC role trust, and production environment approvals are deployment-owned inputs.
- No authoritative KYC API contract is present; protected product actions remain unavailable until one is supplied and configured.
- Deterministic dependency bundling may require Docker/network; CI must fail clearly if build prerequisites are absent.
- The repository contains extensive pre-existing user changes; preserve them and edit only files required by these tasks.
