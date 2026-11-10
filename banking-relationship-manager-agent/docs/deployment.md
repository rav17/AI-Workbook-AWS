# Deployment

## Required inputs

- AWS account and region configured for CDK.
- `CDK_PERMISSIONS_BOUNDARY_ARN` for every environment other than `dev`.
- `COGNITO_USER_POOL_ARN`, `COGNITO_APP_CLIENT_ID`, and `TENANT_CLAIM_NAME` for authenticated API requests.
- `BEDROCK_MODEL_ID` approved for the target region and granted to the Runtime role.
- CDK bootstrap completed in the target account and region.

The authoritative KYC/CRM provider contract and credentials are not present in this repository. Product recommendations fail closed until an approved provider is injected and configured; request-body KYC values are never authoritative.

## Synthesis

From the repository root:

```powershell
uv lock --check --python 3.11
uv run python scripts/build_artifacts.py --target all
cd cdk
cdk synth --quiet
```

For a non-development environment:

```powershell
$env:CDK_PERMISSIONS_BOUNDARY_ARN = "arn:aws:iam::<account>:policy/<boundary>"
$env:COGNITO_USER_POOL_ARN = "arn:aws:cognito-idp:<region>:<account>:userpool/<pool-id>"
$env:COGNITO_APP_CLIENT_ID = "<approved-client-id>"
$env:BEDROCK_MODEL_ID = "<approved-model-id>"
$env:TENANT_CLAIM_NAME = "custom:tenant_id"
cdk synth --context environment=prod
```

The request Lambda has a 28-second timeout and API Gateway has a 29-second integration timeout. This removes Lambda's three-second default while preserving a one-second response margin below the default REST API ceiling. It is a hard synchronous deadline, not a latency SLO; if measured AgentCore Runtime calls need more time, use an asynchronous/streaming workflow or obtain and verify an API Gateway quota increase before changing the integration timeout.

## Deployed components

- `AriaStatefulStack`: encrypted DynamoDB session and idempotency state, KMS, provider secret,
  workflow EventBridge bus, SQS queue, protected log group, and encrypted operations alarm topic.
- `AriaApplicationStack`: staged request/event Lambdas, Cognito-authorized API Gateway `POST /messages`,
  a 28-second request Lambda timeout and 29-second REST integration timeout, protected seven-day Lambda logs,
  CloudWatch API/Lambda alarms, and EventBridge rules for maturity and large-outflow events.
- `AriaGatewayStack`: an IAM-authorized MCP Gateway and Lambda-backed target exposing only the no-argument `get_risk_questionnaire` tool. Customer-specific tools are intentionally not published until an authoritative authenticated-user-to-customer mapping exists.
- `AriaRuntimeStack`: a staged Python 3.13 AgentCore Runtime with MMDSv2 enabled through an ordered `UpdateAgentRuntime` custom resource. Its resource policy permits invocation only by the request Lambda role; the Runtime ARN is published to a scoped SSM parameter and read by that Lambda at invocation time.
- `AriaStatefulStack`: AgentCore Memory uses a validated tenant namespace key and 30-day source-event expiry. No client-data category is approved for extraction, so the application rejects all live Memory writes. Event expiry does not define extracted-record retention. A tenant/user-scoped erasure operation enumerates all matching records across pages and deletes each record; failures propagate and must not be reported as complete. The operation is an adapter capability, not a public API workflow.

## Memory and observability policy

Current Memory policy is **no new client-data writes or extraction**. Before enabling writes, the data owner must approve the allowed derived-data categories (excluding credentials, payment security data, and raw prompts), notice/consent basis, source-event retention, extracted-record retention, deletion deadline/semantics, and an accountable approver. `EventExpiryDuration: 30` covers short-term events only; AgentCore's extracted-record summaries expose creation time but no expiry field. Do not claim extracted-record retention is configured.

Application request/event, Gateway, and workflow log groups have explicit seven-day retention and CloudWatch data-protection audit/masking for common email, address, US phone/SSN/bank-account, payment-card, AWS-secret-key, and private-key patterns. Findings emit the undimensioned `AWS/Logs:LogEventsWithFindings` metric. Masking applies at ingestion and does not retroactively mask prior events; principals with `logs:Unmask` can view unmasked content. Application logging must continue to avoid raw prompts and payloads.

Initial service objectives proposed for baseline review are 99.9% monthly API availability and API p95 latency below 1,000 ms. Provisional alarms default to a 1% API 5xx rate over five minutes when at least 100 requests are present, p95 latency above 1,000 ms, any Lambda error/throttle in a five-minute period, and any sensitive-log finding. Override API alarm thresholds with CDK context `alarm_api_error_rate_percent` and `alarm_api_p95_latency_ms`; these values are not approved production SLOs until service owners review representative traffic and sign off. Alarms publish to the encrypted `OperationsAlarmTopic`; CDK intentionally creates no subscriber. The operations owner must subscribe an approved on-call endpoint before production use.

The AgentCore resources are provisioned by CDK CloudFormation resources. The
deployment order is `AriaStatefulStack`, `AriaApplicationStack`,
`AriaGatewayStack`, then `AriaRuntimeStack`. The Runtime stack references the
request Lambda role to create its resource policy; the ARN handoff uses SSM to
avoid a reverse CloudFormation dependency.

Production deployments should use CI-provided configuration and permissions boundaries.
Do not commit account identifiers, boundary ARNs, provider credentials, or secret
values to the repository.

The artifact builder selects `x86_64-manylinux2014` wheels for Python 3.11 Lambda
functions and `x86_64-manylinux_2_28` wheels for the Python 3.13 Runtime. Keep
these targets separate when changing either managed runtime.

## GitHub Actions deployment

Use the `Deploy AgentCore Infrastructure` workflow with a GitHub Environment named
`dev` or `prod`. Configure these environment variables:

- `AWS_DEPLOY_ROLE_ARN`: IAM role trusted by GitHub Actions OIDC.
- `AWS_REGION`: target AWS region.
- `CDK_PERMISSIONS_BOUNDARY_ARN`: required for non-development deployments.
- `COGNITO_USER_POOL_ARN`: existing user pool ARN.
- `COGNITO_APP_CLIENT_ID`: allowed token audience/client.
- `TENANT_CLAIM_NAME`: verified tenant claim name (defaults to `custom:tenant_id`).
- `BEDROCK_MODEL_ID`: approved regional Bedrock model ID.
- `IDEMPOTENCY_TTL_SECONDS`: optional owner-approved duplicate-retention period in seconds; unset records do not expire automatically.

The workflow builds locked deployment bundles, runs `cdk synth` and `cdk diff`, and deploys only when the Boolean input is true. Configure GitHub Environment required reviewers and an AWS OIDC role trust policy restricted to this repository, branch, and environment; those external settings are not verifiable from this repository. Record synthesis, deployment, and invocation outcomes separately.