# Research: Production Readiness Remediation

**Date**: 2026-10-01

## Decisions

### API and Runtime identity

- **Decision**: Use API Gateway's managed Cognito/JWT authorizer with required issuer/user-pool configuration; derive application tenant/user exclusively from validated authorizer claims. Reject direct handler events without verified claims.
- **Rationale**: A non-empty Authorization header is not authentication, and payload `client_id`/`conversation_id` is not an identity boundary. This minimizes custom token-validation code while supporting a configured identity provider.
- **Alternatives considered**: hand-written JWT/JWKS middleware; IAM-only API; shipping an example user pool. JWT verifier adds key-rotation/cache failure handling; IAM-only is unsuitable for direct end users; provisioning an unrequested identity tenant would invent account/product decisions.
- **Source**: [AgentCore Runtime authentication/security best practices](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html).

### Runtime and Memory IAM

- **Decision**: Set a currently supported AgentCore code runtime, enable MMDSv2 through the supported CloudFormation `MetadataConfiguration` property/override, add `aws:SourceArn` and `aws:SourceAccount` trust conditions, and scope Bedrock/Memory/Gateway permissions to required resources.
- **Rationale**: AWS states Runtime Python 3.11 deprecation/block-update dates have passed as of this audit and requires MMDSv2 from 2026-06-30. AWS also recommends source conditions and resource-scoped permissions.
- **Alternatives considered**: retain Python 3.11 with no metadata configuration; wildcard role permissions; defer Runtime changes until a failed deployment. These contradict current security/service requirements.
- **Sources**: [Supported code runtimes](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-code-deploy-supported-runtimes.html), [Runtime security best practices](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html), [CDK CfnRuntime reference](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrockagentcore/CfnRuntime.html).

### Runtime payload and Strands

- **Decision**: Validate an object with a non-empty string `prompt`; reject caller-supplied `toolUse`/structured model-history blocks; invoke the configured Strands agent through the existing runner and fail startup/invocation if required dependencies are absent.
- **Rationale**: AWS specifically warns that arbitrary JSON and supplied tool-use blocks may bypass model/guardrail controls. The local Strands builder currently is not connected to the Runtime entrypoint.
- **Sources**: [Runtime input validation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html), [Strands Agent loop](https://strandsagents.com/docs/user-guide/sdk/agents/agent-loop/).

### Memory namespaces/data API

- **Decision**: Use documented `CreateEvent`, `RetrieveMemoryRecords`, and `DeleteMemoryRecord` data-plane operations, bounded retrieval, and tenant-specific namespace paths; keep workflow state authoritative in DynamoDB.
- **Rationale**: The current local adapter does not prove service integration; actor-only namespaces do not distinguish tenants with overlapping actor IDs.
- **Sources**: [CreateEvent](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_CreateEvent.html), [RetrieveMemoryRecords](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_RetrieveMemoryRecords.html), [DeleteMemoryRecord](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_DeleteMemoryRecord.html), [Memory namespace guidance](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/specify-long-term-memory-organization.html).

### Memory writes, retention, and erasure (T020)

- **Decision**: Keep live AgentCore Memory writes and extraction disabled. No client-data categories, consent/notice basis, source-event retention, extracted-record retention, or approved deletion SLA are present, so no content may be extracted or retained yet. `EventExpiryDuration: 30` bounds short-term events only and is not evidence of extracted-record expiry.
- **Decision**: Implement user erasure by calling `ListMemoryRecords` with the authenticated actor's `namespacePath`, `maxResults` bounded to 100, and every returned `nextToken`; validate each summary's namespace and record ID, then call `DeleteMemoryRecord` for each record. Completion is returned only after every deletion succeeds; a listing/deletion error propagates as incomplete, and retrying the request is safe.
- **Rationale**: The API exposes `createdAt` but no extracted-record expiry field. Listing is namespace-prefix scoped and paginated, while delete is irreversible and record-specific. Event expiry alone cannot satisfy a long-term retention policy.
- **Owner approval required before enabling writes**: allowed derived categories (exclude credentials, payment security data, and raw prompts), notice/consent basis, source-event retention, extracted-record retention, deletion/erasure deadline and response semantics, and an accountable approver. Current policy is no writes and no retention of new client data.
- **Sources**: [ListMemoryRecords](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListMemoryRecords.html), [MemoryRecordSummary](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_MemoryRecordSummary.html), [DeleteMemoryRecord](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_DeleteMemoryRecord.html), [CreateEvent](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_CreateEvent.html).

### Operational alarms and sensitive logs (T025)

- **Decision**: Attach CloudWatch Logs data-protection policies with matching audit and de-identification statements to application Lambda log groups. Cover email, US phone/address/SSN, US bank account, payment card/security code, AWS secret key, and common private-key identifiers. Masking is defense in depth: it affects standard access after ingestion, does not rewrite historical events, and principals granted `logs:Unmask` can still view originals.
- **Decision**: Use explicit seven-day log retention, matching the existing workflow log group's retention; make log groups and retention explicit for request, event, and Gateway Lambdas. Publish alarms to an SNS topic; production on-call subscription and ownership remain external prerequisites.
- **Provisional thresholds**: 5-minute API 5xx/error-rate early warning at 1%, API p95 latency above 1,000 ms, any Lambda error/throttle, and any sensitive-log finding. Proposed service objectives are 99.9% monthly API availability and p95 latency below 1,000 ms. These are starting values only, not approved SLOs; owners must compare against representative traffic and approve/tune before production.
- **Rationale**: API Gateway and Lambda expose native CloudWatch metrics, and CloudWatch Logs publishes `AWS/Logs:LogEventsWithFindings`. CDK 2.270 supports log-group data-protection policies, explicit Lambda `log_group`, API metrics, Lambda metrics, and SNS alarm actions.
- **Sources**: [CloudWatch Logs data protection](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/mask-sensitive-log-data.html), [Managed data identifiers](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL-managed-data-identifiers.html), [CloudWatch metric filters for data protection](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CWL-data-protection-metrics.html).

### Synchronous request timeout budget

- **Decision**: Set the request Lambda timeout explicitly to 28 seconds and the API Gateway REST integration timeout to 29 seconds. This removes Lambda's three-second default and leaves one second for the integration to receive the Lambda result.
- **Rationale**: The request Lambda performs a synchronous AgentCore Runtime invocation; model and network latency can exceed three seconds. API Gateway REST integrations default to 29 seconds and can exceed that only after an account quota increase, so the deployed configuration must not silently assume a higher limit.
- **Validation**: CDK synthesis asserts both timeout properties. Runtime latency distributions still need non-production load testing; requests that exceed the synchronous budget require an async/streaming workflow, not a larger Lambda timeout alone.
- **Sources**: [Lambda timeout configuration](https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html), [API Gateway quotas](https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html), [CDK LambdaIntegrationOptions](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_apigateway/LambdaIntegrationOptions.html).

### Gateway Lambda event

- **Decision**: Read tool arguments from the event and the selected tool name from `context.client_context.custom['bedrockAgentCoreToolName']`; normalize target-prefixed names only against an explicit allowlist; return JSON-serializable tool output.
- **Rationale**: The current handler expects an event `toolName` field and drops context, which disagrees with the official Lambda target contract.
- **Sources**: [Official Lambda tool target example](https://github.com/awslabs/agentcore-samples/blob/main/03-integrations/gateway/agentcore-tool-search-plugin/lambda/travel_tools.py), [Gateway target authorization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building-adding-targets-authorization.html).

### Artifact and release pipeline

- **Decision**: Use an explicit runtime dependency manifest and deterministic bundling/exclusion rules; add CI package inspection and size gates. Pin the CDK CLI and run CDK tests/synth before the deployment job.
- **Rationale**: The existing root Lambda asset is roughly 504 MB uncompressed and includes `.venv311` and a local session file. AWS Lambda permits at most 250 MB unzipped. Current deployment installs a floating global CDK CLI.
- **Sources**: [Lambda Python package rules](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html), [CDK v2 API](https://docs.aws.amazon.com/cdk/api/v2/).

### KYC source and failures

- **Decision**: Replace payload-controlled KYC with an injected authoritative compliance provider contract; fail closed for protected operations when provider/config/status is absent or invalid. Keep the provider API itself out of scope until the owner supplies a contract.
- **Rationale**: No authoritative KYC provider contract is present in the repository. Hard-coding an assumed provider would create false assurance.
- **Tradeoff**: Protected product operations remain unavailable in environments without provider configuration; this is safer than treating client input or a default as verified compliance.

### Deployed API Runtime routing

- **Decision**: Keep the deployed Lambda entrypoint stable and delegate it to the existing authenticated `rest_handler.handler`, which resolves the Runtime ARN from SSM and invokes the Runtime through the DynamoDB-backed session/idempotency coordinator.
- **Rationale**: The direct `agentcore_entrypoint.main` path is a local demo path and bypasses Strands, Memory, durable session coordination, and API idempotency. Reusing the existing coordinator avoids a second Runtime integration implementation.
- **Alternatives considered**: Reimplement Runtime invocation in `lambda_entry.py` or change API Gateway to a second handler. Both duplicate or fragment the existing request contract.
- **Validation**: Unit test the deployed handler to verify authenticated input reaches the fake AgentCore client and invalid authentication never creates or invokes it.

### Strands to Gateway integration and tool scope

- **Decision**: Use the pinned Strands `MCPClient` with `streamablehttp_client` against `https://{gateway-id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp`, signed with the Runtime execution role using SigV4 service name `bedrock-agentcore`. Expose only the no-customer-state `get_risk_questionnaire` tool. Remove the customer-message tool from the Gateway target until an approved subject-to-customer mapping exists.
- **Rationale**: AWS documents `/mcp` and the Gateway host format, and its Strands integration uses MCPClient. The current Gateway is AWS_IAM-authenticated, and the Runtime role already has scoped `InvokeGateway`. No authoritative mapping currently permits binding an authenticated user to the model-supplied `client_id` field.
- **Alternatives considered**: Bearer/JWT forwarding is not configured in the current AWS_IAM Gateway; trusting `client_id` or `_verified_principal` sent in model-generated tool arguments would not establish customer authorization; disabling Gateway entirely leaves the audited integration disconnected.
- **Sources**: [Use an AgentCore gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using.html), [Call a Gateway tool](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-call.html), [Gateway IAM target authorization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building-adding-targets-authorization.html), [Strands Gateway integration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-agent-integration.html).

### Gateway tool safety

- **Decision**: Validate Gateway argument names/types and size before dispatch, run the existing local input/output guardrail processor at the Lambda boundary, and return a generic blocked/error result rather than raw exception or unsafe tool output.
- **Rationale**: AWS Bedrock sensitive-information filters do not inspect tool-use arguments or tool results. Gateway-side validation and backend policy remain necessary even when tool visibility is constrained.
- **Sources**: [Bedrock sensitive information filter limitations](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html), [AgentCore Runtime input-validation guidance](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-security-best-practices.html).

### Lambda and Runtime wheel platform selection

- **Decision**: Select Python 3.11 `x86_64-manylinux2014` for Lambda and Python 3.13 `x86_64-manylinux_2_28` for AgentCore Runtime; retain `--only-binary :all:` and add target-platform assertions to artifact tests.
- **Rationale**: Lambda Python 3.11 uses Amazon Linux 2, and AWS's Python package guide shows `manylinux2014` for x86_64 Lambda native wheels. AgentCore Runtime Python 3.13 is a distinct Amazon Linux 2023 execution target.
- **Source**: [Lambda Python native library packaging](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html), [Lambda runtime table](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html).

### Deployment workflow trust and configuration

- **Decision**: Make the production permissions boundary available at job scope, validate it before synth/diff, and use full commit SHAs for third-party actions in both quality and deploy workflows. Keep OIDC trust-policy restrictions and GitHub environment reviewer/branch controls as externally verified release gates.
- **Rationale**: CDK app construction fails for non-dev environments without the boundary, so all synthesis stages need the same configuration. GitHub documents full-SHA pins as the immutable action reference; repository files cannot verify AWS trust conditions or GitHub environment rule settings.
- **Sources**: [AWS CDK best practices](https://docs.aws.amazon.com/cdk/v2/guide/best-practices.html), [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions), [GitHub OIDC in AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services).

## Compatibility

- Pins currently declared are `strands-agents==1.34.1` and `bedrock-agentcore==1.9.1`; current PyPI versions observed during audit were `1.57.1` and `1.24.0`. Upgrade only after executing tests against the candidate versions; the version gap alone is a maintenance risk, not proof of breakage.
- Existing AgentCore CDK L1 types are available in `aws-cdk-lib==2.270.0`; use typed `CfnMemory` where available and raw overrides only for Runtime schema properties absent from the installed L1 interface.
