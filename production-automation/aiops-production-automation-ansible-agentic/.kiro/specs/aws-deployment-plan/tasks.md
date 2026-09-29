# Implementation Plan: AWS Deployment Plan

## Overview

This plan implements the end-to-end AWS deployment system for the AIOps Self-Healing Infrastructure application. The implementation follows the design's layered CDK stack architecture (NetworkStack → DataStack → ComputeStack → ObservabilityStack), CI/CD pipelines via GitHub Actions with OIDC authentication, configuration management via SSM/Secrets Manager, health gates, automated rollback, and operational runbooks. All infrastructure is defined in Python CDK code, tested with CDK Assertions and Hypothesis property-based tests.

## Tasks

- [x] 1. Set up CDK project structure and core utilities
  - [x] 1.1 Create CDK project scaffolding and entry point
    - Create directory structure: `src/agentic_ai/infra/`, `src/agentic_ai/infra/stacks/`, `src/agentic_ai/infra/constructs/`
    - Create `__init__.py` files for all packages
    - Create `cdk.json` with default context values (environment, awsAccount, awsRegion, bedrockModelId, costCenter, costCenterEmail, vpcCidr, monthlyBudgetUsd)
    - Add `.gitignore` entry for `cdk.context.json`
    - _Requirements: 2.1, 2.9_

  - [x] 1.2 Implement CdkContext dataclass and validation
    - Create `src/agentic_ai/infra/context.py` with `CdkContext` dataclass
    - Implement `validate_cdk_context(raw: dict) -> CdkContext` function
    - Validate: environment ∈ {dev, staging, prod}, awsAccount is 12-digit numeric, awsRegion matches pattern, bedrockModelId non-empty, costCenter non-empty, costCenterEmail required
    - Raise `ValueError` naming the specific invalid key on failure
    - _Requirements: 2.9, 10.4_

  - [ ]* 1.3 Write property test for CDK context validation (Property 3)
    - **Property 3: CDK Context Validation Rejects Invalid or Missing Keys**
    - Use Hypothesis to generate invalid context dicts (missing keys, bad formats)
    - Verify `validate_cdk_context` raises `ValueError` for invalid inputs and returns `CdkContext` for valid ones
    - **Validates: Requirements 2.9, 10.4**

  - [x] 1.4 Implement standard tagging utility
    - Create `src/agentic_ai/infra/tags.py` with `apply_standard_tags(scope, context: CdkContext)` helper
    - Apply tags: `project=aiops-self-healing`, `environment={environment}`, `managed-by=cdk`, `cost-center={costCenter}`
    - Enforce `cost-center` tag presence — fail synthesis if missing
    - _Requirements: 2.10, 10.8_

  - [x] 1.5 Implement CDK App entry point
    - Create `src/agentic_ai/infra/app.py` — reads CDK context, validates via `validate_cdk_context()`, instantiates all four stacks with explicit dependencies
    - Enable termination protection for prod environment
    - Wire cross-stack references via constructor parameters
    - _Requirements: 2.1, 2.11_

- [x] 2. Implement NetworkStack
  - [x] 2.1 Create NetworkStack with VPC, subnets, and NAT Gateway
    - Create `src/agentic_ai/infra/stacks/network_stack.py`
    - VPC with configurable CIDR (default 10.0.0.0/16), 2 public + 2 private subnets across 2 AZs
    - Single NAT Gateway in one public subnet
    - Internet Gateway attached to VPC
    - ECS tasks security group (no inbound, HTTPS outbound only)
    - VPC endpoints security group (HTTPS inbound from ECS tasks SG only)
    - _Requirements: 2.2_

  - [x] 2.2 Create VpcEndpoints construct
    - Create `src/agentic_ai/infra/constructs/vpc_endpoints.py`
    - Implement 9 VPC endpoints: S3 (Gateway), DynamoDB (Gateway), ECR API, ECR DKR, SQS, SSM, Secrets Manager, CloudWatch Logs, Bedrock Runtime (all Interface)
    - Interface endpoints use private subnets with private DNS enabled
    - _Requirements: 2.2_

  - [ ]* 2.3 Write CDK assertion tests for NetworkStack
    - Create `tests/cdk/test_network_stack.py`
    - Verify: 1 VPC, 4 subnets, 1 NAT GW, 9 VPC endpoints, no SGs with 0.0.0.0/0 inbound, all 4 required tags present
    - _Requirements: 2.13_

- [x] 3. Implement DataStack
  - [x] 3.1 Create DataStack with DynamoDB and SQS
    - Create `src/agentic_ai/infra/stacks/data_stack.py`
    - DynamoDB table: `AiopsIncidentMemory-{environment}`, on-demand billing, TTL on `expiry_timestamp`, AWS-managed KMS encryption
    - GSIs: AlertNameIndex, ServiceIndex, OutcomeIndex (all with timestamp sort key)
    - SQS main queue: 60s visibility timeout, redrive to DLQ after 3 failures
    - SQS DLQ: 14-day retention, SSE-SQS encryption
    - Prod-only: PITR enabled, message retention 14 days (main queue), AWS Backup daily plan
    - CfnOutput exports for table name, queue URL, DLQ URL
    - _Requirements: 2.3, 2.4, 5.4_

  - [ ]* 3.2 Write CDK assertion tests for DataStack
    - Create `tests/cdk/test_data_stack.py`
    - Verify: 1 DynamoDB table, 3 GSIs, TTL enabled, 2 SQS queues, DLQ redrive maxReceiveCount=3
    - Test prod variant: PITR enabled, 14-day retention
    - _Requirements: 2.13_

- [x] 4. Implement ComputeStack
  - [x] 4.1 Create ComputeStack with ECS Fargate service
    - Create `src/agentic_ai/infra/stacks/compute_stack.py`
    - Receives network_stack and data_stack as constructor parameters
    - ECS cluster, Fargate task definition (0.5 vCPU, 1024 MB)
    - Container image from ECR with environment-specific Image_Tag
    - Environment variables and secrets injection via ECS task definition (SSM + Secrets Manager)
    - CloudWatch log group with environment-specific retention (30d/90d/365d)
    - ECS service with rolling update deployment
    - Dev: FARGATE_SPOT with FARGATE fallback, desired=1 fixed
    - Staging/Prod: FARGATE on-demand, min healthy 100%, max 200%
    - _Requirements: 2.5, 5.2, 5.3, 10.5_

  - [x] 4.2 Implement Application Auto Scaling
    - Scale out: +2 tasks when SQS depth > 10 for 2×1min periods, +4 when > 50
    - Scale in: -1 task when SQS depth < 2 for 5×1min periods
    - Dev environment: no auto-scaling (fixed desired=1)
    - _Requirements: 2.6_

  - [x] 4.3 Implement IAM roles with least-privilege policies
    - Task Execution Role: ECR pull, CloudWatch Logs write, SSM GetParameter, Secrets Manager GetSecretValue (scoped to `/aiops/{env}/*`)
    - Task Role: Bedrock InvokeModel, SQS operations, DynamoDB CRUD, SSM SendCommand/GetCommandInvocation/GetParameter, Secrets Manager GetSecretValue, CloudWatch PutMetricData/PutLogEvents
    - No wildcard resource permissions except AWS-mandated (ecr:GetAuthorizationToken, cloudwatch:PutMetricData)
    - _Requirements: 2.7, 4.6_

  - [ ]* 4.4 Write CDK assertion tests for ComputeStack
    - Create `tests/cdk/test_compute_stack.py`
    - Verify: 1 ECS cluster, 1 Fargate task def, 2 IAM roles, no wildcard resource in policies
    - Create `tests/cdk/test_iam_policies.py` — verify Property 2 invariant across all stacks
    - _Requirements: 2.13_

  - [ ]* 4.5 Write property test for IAM no-wildcard invariant (Property 2)
    - **Property 2: IAM No-Wildcard Resource Invariant**
    - Synthesize templates for all environments, verify no Resource: "*" except exempted actions
    - All SSM/Secrets Manager ARNs contain `/aiops/{environment}/` path prefix
    - **Validates: Requirements 2.7, 4.6**

- [x] 5. Checkpoint - Verify CDK stacks synthesize correctly
  - Ensure all tests pass, ask the user if questions arise.
  - Run `npx aws-cdk@2 synth --all --context environment=dev` to verify synthesis works end-to-end

- [x] 6. Implement ObservabilityStack
  - [x] 6.1 Create ObservabilityStack with alarms and dashboard
    - Create `src/agentic_ai/infra/stacks/observability_stack.py`
    - Receives compute_stack as constructor parameter
    - SNS topic: `aiops-alarms-{environment}`
    - 4 CloudWatch alarms: DLQ depth > 5, AI latency p95 > 15s, remediation failure > 30%, ECS unhealthy tasks > 0
    - Composite alarm `RollbackRequired-{env}`: ECS unhealthy AND DLQ depth in ALARM for 5+ min
    - High task count alarm: ECS tasks > 8
    - Bedrock cost estimate alarm via metric math
    - CloudWatch dashboard `AIOps-{environment}` with specified widget layout
    - Dev environment: no alarms created
    - _Requirements: 2.8, 2.12, 7.5, 9.1, 9.4, 10.7_

  - [x] 6.2 Implement CloudWatch Synthetics canary
    - Canary `aiops-canary-{environment}` for staging/prod only
    - Schedule: rate(5 minutes), sends synthetic webhook payload, asserts HTTP 200 within 2s
    - Alarm on 2 consecutive failures → SNS topic
    - Dev environment: no canary (Requirement 10.6)
    - _Requirements: 9.5, 10.6_

  - [x] 6.3 Implement AWS Budgets
    - Budget per environment: dev $200, staging $500, prod $2000 (configurable via CDK_Context)
    - Alert at 80% and 100% to costCenterEmail
    - Fail synthesis if costCenterEmail is absent
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 6.4 Write CDK assertion tests for ObservabilityStack
    - Create `tests/cdk/test_observability_stack.py`
    - Verify: 4 CloudWatch alarms, 1 SNS topic, all alarms reference same topic ARN, 1 dashboard
    - Create `tests/cdk/test_tags.py` — verify Property 4 (all resources have required tags)
    - _Requirements: 2.13_

  - [ ]* 6.5 Write property test for required tags (Property 4)
    - **Property 4: Required Tags Present on All CDK Resources**
    - Synthesize all stacks for each environment, verify every resource has 4 required tags
    - **Validates: Requirements 2.10, 10.8**

- [x] 7. Implement Configuration Loading and Health Gate
  - [x] 7.1 Implement ConfigLoader class
    - Create `src/agentic_ai/infra/constructs/config_loader.py`
    - Startup: batch SSM `GetParametersByPath`, validate required params (operating-mode, escalation-threshold, correlation-window-seconds, max-concurrent-pipelines, bedrock-model-id, sqs-queue-url, dynamodb-table-name)
    - Exit with non-zero status on validation failure, logging specific param name
    - Periodic refresh loop: re-fetch at configurable interval (60–3600s, default 300s)
    - Retain cached values on fetch failure, log warning
    - Secrets Manager: cache with configurable TTL (60–86400s, default 3600s), retain cached on failure
    - Empty secret value → disable channel, log warning
    - _Requirements: 4.3, 4.4, 4.5, 4.7_

  - [ ]* 7.2 Write property test for SSM startup validation (Property 6)
    - **Property 6: SSM Startup Parameter Validation Rejects Invalid Configs**
    - Generate parameter dicts with missing/invalid values via Hypothesis
    - Verify SystemExit(1) raised with specific param name logged
    - Valid dicts return without raising
    - **Validates: Requirements 4.3**

  - [ ]* 7.3 Write property test for config cache preservation (Property 7)
    - **Property 7: Config Cache Preserved on Fetch Failure**
    - Simulate SSM/SM failures after loading valid state
    - Verify cached values remain unchanged after failure
    - **Validates: Requirements 4.4, 4.5**

  - [x] 7.4 Implement HealthGateChecker class
    - Create `scripts/health_gate.py` with `HealthGateChecker` dataclass
    - Poll /health every 30s for up to 5 min
    - Pass: 3 consecutive HTTP 200 with sqs=healthy and dynamodb=healthy
    - Fail: timeout without 3 consecutive passes
    - Reset counter on any non-healthy result
    - Publish CloudWatch metrics: DeploymentHealthGatePassed (1/0), DeploymentHealthGateDuration
    - _Requirements: 6.1, 6.6_

  - [ ]* 7.5 Write property test for Health Gate state machine (Property 5)
    - **Property 5: Health Gate Consecutive-Success State Machine**
    - Generate sequences of PollResult objects with Hypothesis
    - Verify PASS iff 3+ consecutive healthy results, counter resets on failure
    - **Validates: Requirements 3.3, 5.5, 6.1**

- [x] 8. Implement CI/CD Scripts and Deployment Manifest
  - [x] 8.1 Implement ECR push and scan script
    - Create `scripts/ecr_push_and_scan.py`
    - Login to ECR, push image with immutable tag
    - Poll scan results every 10s for up to 300s
    - Fail on CRITICAL/HIGH vulnerability (report finding name, severity, package)
    - Fail on scan timeout
    - Retry push up to 2 times on auth/service failure (30s intervals)
    - Write image-tag.json artifact
    - _Requirements: 1.5, 1.7, 1.8, 1.9_

  - [x] 8.2 Implement deployment manifest store/rotate script
    - Create `scripts/store_manifest.py` — store new manifest as n=1, rotate existing 1→2, 2→3, etc., cap at 5
    - Create `scripts/rollback_trigger.py` — `get_manifest(env, n)` retrieves from SSM, exits 1 if not found
    - Manifest contains: Image_Tag, commit SHA, CDK stack versions, timestamp, Health_Gate result
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]* 8.3 Write property test for deployment manifest sliding window (Property 9)
    - **Property 9: Deployment Manifest Sliding-Window Invariant**
    - Generate sequences of store operations, verify n=1 is most recent, no n>5
    - **Validates: Requirements 7.1, 7.2**

  - [x] 8.4 Implement image tag builder and canary decision function
    - Create `src/agentic_ai/infra/constructs/image_tag.py` — `build_image_tag(sha, env)` returns `{sha}-{env}` format
    - Create canary decision function: PROCEED iff error_rate < 5.0 AND latency_p95 < 15000
    - _Requirements: 1.2, 1.3, 6.5_

  - [ ]* 8.5 Write property test for image tag format (Property 1)
    - **Property 1: Image_Tag Format Invariant**
    - Generate valid SHA strings and environment names via Hypothesis
    - Verify output matches `^[0-9a-f]{7}-(dev|staging|prod)$`
    - **Validates: Requirements 1.2, 1.3**

  - [ ]* 8.6 Write property test for canary threshold decision (Property 8)
    - **Property 8: Canary Metric Threshold Decision**
    - Generate pairs of (error_rate, latency_p95) via Hypothesis
    - Verify PROCEED iff error_rate < 5.0 AND latency_p95 < 15000
    - **Validates: Requirements 6.5**

- [x] 9. Checkpoint - Verify all unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.
  - Run `pytest -m cdk` and `pytest -m property` to verify infrastructure tests

- [x] 10. Implement GitHub Actions CI/CD Workflows
  - [x] 10.1 Create CI workflow
    - Create `.github/workflows/ci.yml`
    - Trigger: push to main/staging, tags v*.*.*, PRs to main
    - OIDC permissions: id-token write, contents read
    - Jobs in order: lint (ruff), unit-tests (pytest -m unit, coverage ≥80%), property-tests (pytest -m property --hypothesis-seed=0), cdk-synth (cdk synth --all), cdk-tests (pytest -m cdk), docker-build (BuildX with GHA cache), ecr-scan-push
    - Cache pip dependencies and Docker layers between runs
    - Image tag format: `{SHA7}-{environment}`
    - Upload artifacts: cdk-out/, image-tag.json
    - _Requirements: 1.1–1.9, 3.1, 3.2, 3.5, 3.7, 3.9_

  - [x] 10.2 Create CD workflow
    - Create `.github/workflows/cd.yml`
    - Trigger: workflow_run on CI completion (main/staging), workflow_dispatch for prod
    - Download image-tag artifact
    - CDK diff before each stack deployment (store as artifact, skip deploy if no changes)
    - Deploy order: NetworkStack → DataStack → ComputeStack → Health Gate → ObservabilityStack
    - Dev: use --hotswap for ComputeStack
    - Prod: manual approval with 4h timeout, display Image_Tag/SHA/commit message
    - Health Gate failure: rollback to n=1 manifest, re-run health gate, halt CD
    - Store deployment manifest on success
    - Slack notifications on prod failures (non-fatal if webhook missing)
    - _Requirements: 3.3, 3.4, 3.5, 3.6, 3.8, 5.5, 5.7, 6.1–6.4, 7.1, 7.4_

  - [x] 10.3 Create OIDC trust policy and IAM role definitions
    - Document the IAM OIDC provider trust policy for GitHub Actions
    - CI role: scoped to repo/branch, permissions for ECR, CDK synth
    - CD role: scoped to repo/branch, permissions for CDK deploy, SSM, ECS
    - _Requirements: 3.5_

- [x] 11. Implement SSM Parameters and Secrets Manager resources in CDK
  - [x] 11.1 Create SSM parameters in CDK
    - Add SSM parameters under `/aiops/{environment}/` in DataStack or ComputeStack:
      operating-mode, escalation-threshold, correlation-window-seconds, max-concurrent-pipelines, bedrock-model-id, sqs-queue-url, dynamodb-table-name, audit-log-group-name, asset-inventory-path, mapping-config-path
    - _Requirements: 4.1_

  - [x] 11.2 Create Secrets Manager secrets in CDK
    - Create secrets: slack-webhook-url, pagerduty-routing-key, api-gateway-key
    - Enable automatic rotation for api-gateway-key (90-day schedule with rotation Lambda)
    - _Requirements: 4.2, 4.8_

- [x] 12. Implement Monitoring Metrics and Structured Logging
  - [x] 12.1 Implement custom CloudWatch metrics publisher
    - Create metrics publisher module for: AlertsReceived, AIReasoningInvocations, AIReasoningLatency, FallbackToRulesCount, RemediationsExecuted, RemediationSuccessCount, RemediationFailureCount, HumanEscalationsCount, BedrockThrottleCount, DeadLetterQueueDepth
    - Namespace: `AIOps/{environment}`, publish within 60s of event
    - Implement `publish_scaling_metric(task_count)` — publish AutoScalingAboveNominal only when count > 5
    - _Requirements: 9.2, 10.9_

  - [ ]* 12.2 Write property test for custom metrics (Properties 10, 12)
    - **Property 10: Custom Metric Name and Unit Completeness**
    - **Property 12: AutoScaling Above-Nominal Metric Trigger**
    - Verify metric names/units match spec for all event types
    - Verify AutoScalingAboveNominal published iff task_count > 5
    - **Validates: Requirements 9.2, 10.9**

  - [x] 12.3 Implement structured JSON logging
    - Configure structured logging with required fields: timestamp, level, incident_id, pipeline_stage, duration_ms, outcome, environment
    - Implement secret redaction patterns (no raw secrets in logs)
    - _Requirements: 9.6_

  - [ ]* 12.4 Write property test for structured log entries (Property 11)
    - **Property 11: Structured Log Entry Field Completeness**
    - Generate log events at all levels via Hypothesis
    - Verify all 7 required fields present and non-null, no raw secrets
    - **Validates: Requirements 9.6**

- [x] 13. Extend /health endpoint and create Makefile
  - [x] 13.1 Extend /health endpoint with dependency checks
    - Modify `src/app.py` to add SQS and DynamoDB dependency health checks
    - Return JSON: `{"dependencies": {"sqs": "healthy|unhealthy", "dynamodb": "healthy|unhealthy"}}`
    - Use env vars injected by ECS for queue URL and table name
    - _Requirements: 6.1_

  - [x] 13.2 Create Makefile with deployment targets
    - Add targets: `deploy` (CDK deploy all stacks), `diff` (CDK diff), `rollback ENVIRONMENT={env} MANIFEST={n}`, `destroy`
    - Rollback target: retrieve manifest from SSM, display for review, invoke CD pipeline
    - Exit non-zero with error if specified manifest doesn't exist
    - _Requirements: 7.3_

- [x] 14. Create Operational Runbooks
  - [x] 14.1 Create runbooks directory and files
    - Create `runbooks/scale-out.md` — verify task count, update desired count, verify health, confirm SQS depth reduced
    - Create `runbooks/scale-in.md` — verify queue depth low, reduce desired count, verify tasks drain
    - Create `runbooks/rollback.md` — automated path (CD pipeline) and manual path (make rollback), verify via Health_Gate
    - Create `runbooks/dlq-replay.md` — inspect DLQ messages, move to main queue, monitor reprocessing, isolate repeat failures
    - Create `runbooks/bedrock-throttling.md` — check throttle metrics, switch to rules_only mode, monitor recovery
    - Create `runbooks/parameter-update.md` — update SSM param, wait for refresh interval, verify new value in logs
    - Create `runbooks/incident-response.md` — decision tree from alarm firing through triage steps with AWS CLI commands
    - Include ⚠️ WARNING sections for destructive actions (DLQ purge, task stop, table restore)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 15. Create CDK test fixtures and conftest
  - [x] 15.1 Create shared CDK test fixtures
    - Create `tests/cdk/__init__.py` and `tests/cdk/conftest.py`
    - Shared fixtures: CDK app, context for each environment (dev/staging/prod), synthesized templates
    - Create `tests/property/__init__.py` for property test package
    - _Requirements: 2.13_

- [x] 16. Final checkpoint - Full test suite verification
  - Ensure all tests pass, ask the user if questions arise.
  - Run full test suite: `pytest -m unit`, `pytest -m property`, `pytest -m cdk`
  - Verify CDK synth works for all three environments: dev, staging, prod

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design document
- Unit tests (CDK assertions) validate specific resource counts and configurations
- All infrastructure code is Python (AWS CDK), all tests use pytest with Hypothesis
- The design explicitly uses Python — no language selection needed
- CI/CD workflows are GitHub Actions YAML files (not executed, only created)
- Runbooks are Markdown documentation files

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "1.5", "15.1"] },
    { "id": 2, "tasks": ["2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "3.1"] },
    { "id": 4, "tasks": ["3.2", "4.1"] },
    { "id": 5, "tasks": ["4.2", "4.3"] },
    { "id": 6, "tasks": ["4.4", "4.5", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3"] },
    { "id": 8, "tasks": ["6.4", "6.5"] },
    { "id": 9, "tasks": ["7.1", "7.4", "8.4"] },
    { "id": 10, "tasks": ["7.2", "7.3", "7.5", "8.5", "8.6"] },
    { "id": 11, "tasks": ["8.1", "8.2"] },
    { "id": 12, "tasks": ["8.3", "10.1", "10.2", "10.3"] },
    { "id": 13, "tasks": ["11.1", "11.2"] },
    { "id": 14, "tasks": ["12.1", "12.3", "13.1", "13.2"] },
    { "id": 15, "tasks": ["12.2", "12.4", "14.1"] }
  ]
}
```
