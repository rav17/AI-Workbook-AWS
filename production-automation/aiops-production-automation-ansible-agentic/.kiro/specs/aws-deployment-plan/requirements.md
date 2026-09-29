# Requirements Document

## Introduction

This document defines the requirements for the end-to-end deployment plan of the AIOps Self-Healing Infrastructure application on AWS. The deployment plan covers: building and publishing the Docker image to Amazon ECR, implementing all infrastructure via AWS CDK stacks, establishing CI/CD pipelines for automated deployments, managing configuration and secrets through AWS SSM Parameter Store and Secrets Manager, maintaining a three-tier environment strategy (dev/staging/prod), and providing operational runbooks for scaling, rollback, and monitoring.

These requirements build on and extend the infrastructure requirements defined in the `agentic-ai-aws-deployment` spec, which specifies the runtime AWS resources (ECS Fargate, SQS, DynamoDB, API Gateway, VPC, IAM, CloudWatch). This spec focuses on the delivery mechanics — how those resources are provisioned, updated, tested, and operated across environments.

## Glossary

- **CDK_App**: The AWS CDK application (`src/agentic_ai/infra/`) that synthesizes all CloudFormation stacks for the AIOps system, parameterized by environment (dev/staging/prod)
- **CDK_Stack**: An individual AWS CDK stack within the CDK_App, each owning a distinct layer of infrastructure (network, data, compute, pipeline)
- **ECR_Repository**: The Amazon Elastic Container Registry repository that stores versioned Docker images of the AIOps application
- **CI_Pipeline**: The automated build-and-test pipeline triggered on each commit to the repository, responsible for building the Docker image, running tests, and publishing the image to ECR
- **CD_Pipeline**: The automated deployment pipeline triggered on successful CI completion or on a manual approval gate, responsible for deploying CDK stacks to the target environment
- **Environment**: A named deployment target with fully isolated AWS resources — one of `dev`, `staging`, or `prod`
- **Image_Tag**: The unique identifier for a Docker image in ECR, composed of the short Git commit SHA and the environment name (e.g., `abc1234-prod`)
- **Parameter_Store**: AWS Systems Manager Parameter Store, used to store non-secret environment configuration values under a hierarchical path (`/aiops/{environment}/{parameter_name}`)
- **Secrets_Manager**: AWS Secrets Manager, used to store sensitive credentials (Slack webhook URL, PagerDuty routing key, API keys) with automatic rotation support
- **Deployment_Manifest**: The set of image tag, CDK stack versions, and configuration values that together define a complete deployed state of one Environment
- **Rollback**: The automated or manual process of reverting an Environment to the previous Deployment_Manifest after a failed or degraded deployment
- **Health_Gate**: An automated post-deployment check that queries the `/health` endpoint and CloudWatch alarms to determine whether a deployment has succeeded before advancing to the next stage or closing the deployment
- **Canary_Task**: A single ECS Fargate task deployed alongside the existing tasks during a staged deployment, receiving a controlled fraction of traffic before full rollout
- **Runbook**: A documented, step-by-step procedure for a recurring operational activity (scaling, rollback, incident response) stored in the repository alongside the code
- **DLQ**: Dead-letter queue — the Amazon SQS queue that receives messages after three failed processing attempts from the main SQS queue
- **CDK_Context**: The set of environment-specific values (account ID, region, VPC CIDR, Bedrock model ID) passed to the CDK_App at synthesis time via `cdk.json` or the `--context` flag

## Requirements

---

### Requirement 1: Docker Image Build and ECR Publishing

**User Story:** As a platform engineer, I want the AIOps application Docker image to be built reproducibly and published to a private ECR repository, so that every deployment uses a versioned, traceable image artifact.

#### Acceptance Criteria

1. THE CI_Pipeline SHALL build the Docker image from the repository `Dockerfile` using a multi-stage build that produces a final image based on `python:3.11-slim`, installs `ansible-core` and all Python dependencies from `requirements.txt`, and runs as a user with UID greater than 0 (non-root)
2. WHEN a Docker image build completes successfully for a target Environment (one of `dev`, `staging`, or `prod`), THE CI_Pipeline SHALL tag the image with the short Git commit SHA (7 characters) and the target Environment name, producing an Image_Tag in the format `{commit_sha}-{environment}` (e.g., `abc1234-dev`)
3. WHEN a Docker image build completes successfully, THE CI_Pipeline SHALL also tag the image with the `latest` tag for the target Environment (e.g., `latest-dev`) to support reference by downstream systems
4. WHEN a Docker image build fails, THE CI_Pipeline SHALL halt immediately, attach the full Docker build log as a CI pipeline artifact, and SHALL NOT publish any image to the ECR_Repository
5. THE ECR_Repository SHALL have image scanning on push enabled using ECR Enhanced Scanning; WHEN a scan completes (polling every 10 seconds for up to 300 seconds) and detects a CRITICAL or HIGH severity vulnerability, THE CI_Pipeline SHALL report the finding name, severity, and affected package for each finding, mark the build as failed, and SHALL NOT publish the image; IF the scan does not complete within 300 seconds, THE CI_Pipeline SHALL mark the build as failed with a scan-timeout error
6. THE ECR_Repository SHALL have a lifecycle policy configured to retain a maximum of 30 tagged images per Environment and automatically expire untagged images older than 7 days
7. WHEN the CI_Pipeline publishes an image, THE CI_Pipeline SHALL record the Image_Tag and image digest (SHA-256) in a deployment artifact file stored as a CI pipeline artifact for use by the CD_Pipeline
8. IF ECR login or push fails due to authentication error or service unavailability, THEN THE CI_Pipeline SHALL retry the push operation up to 2 times with 30-second intervals, and if all retries fail, SHALL mark the build as failed with an error message indicating the ECR failure reason
9. THE ECR_Repository SHALL enforce immutable image tags; IF a CI_Pipeline attempt pushes an image using a tag that already exists in the ECR_Repository, THEN the push SHALL be rejected and the CI_Pipeline SHALL fail with an error indicating tag immutability violation

---

### Requirement 2: CDK Infrastructure Stack Implementation

**User Story:** As a platform engineer, I want all AWS infrastructure defined as AWS CDK code organized into layered stacks, so that infrastructure is reproducible, version-controlled, and deployable to any environment by changing parameters alone.

#### Acceptance Criteria

1. THE CDK_App SHALL be organized into exactly four CDK_Stacks with explicit dependency ordering: `NetworkStack` (VPC, subnets, NAT Gateway, VPC endpoints), `DataStack` (DynamoDB table, SQS queues, DLQ, KMS keys), `ComputeStack` (ECS cluster, Fargate service, task definition, ECR reference, auto-scaling, IAM roles), and `ObservabilityStack` (CloudWatch log groups, metrics, alarms, dashboards); the ComputeStack SHALL declare an explicit CDK dependency on both NetworkStack and DataStack; the ObservabilityStack SHALL declare an explicit CDK dependency on the ComputeStack
2. THE NetworkStack SHALL create a VPC with CIDR configurable via CDK_Context (default `10.0.0.0/16`), 2 public subnets and 2 private subnets across 2 Availability Zones, a single NAT Gateway in one public subnet, and VPC endpoints for the following AWS services: ECR API, ECR DKR, S3, DynamoDB, SQS, SSM, Secrets Manager, CloudWatch Logs, and Bedrock Runtime; placing ECS tasks in private subnets with no direct inbound internet access
3. THE DataStack SHALL create the DynamoDB Incident_Memory_Store table with on-demand billing mode, TTL enabled on the `expiry_timestamp` attribute, and the following Global Secondary Indexes: `AlertNameIndex` (partition key: `alert_name`, sort key: `timestamp`), `ServiceIndex` (partition key: `service_name`, sort key: `timestamp`), and `OutcomeIndex` (partition key: `outcome`, sort key: `timestamp`); the table SHALL be encrypted with an AWS-managed KMS key
4. THE DataStack SHALL create the main SQS queue with a visibility timeout of 60 seconds, message retention of 4 days, and a DLQ with message retention of 14 days; the DLQ SHALL receive messages after exactly 3 failed processing attempts; both queues SHALL be encrypted with SSE-SQS
5. THE ComputeStack SHALL create an ECS Fargate task definition with 0.5 vCPU and 1024 MB memory, configure the container to use the published ECR image identified by the Image_Tag stored in CDK_Context, mount all configuration via environment variables sourced from Parameter_Store and Secrets_Manager (not baked into the image), and configure the ECS service with a minimum task count of 1 and maximum task count of 10
6. THE ComputeStack SHALL configure Application Auto Scaling for the ECS service based on SQS queue depth: scale out by 2 tasks when the `ApproximateNumberOfMessagesVisible` metric of the main SQS queue exceeds 10 for 2 consecutive 1-minute evaluation periods; scale in by 1 task when the metric is below 2 for 5 consecutive 1-minute evaluation periods
7. THE ComputeStack SHALL create a separate ECS task execution role and task role; the task execution role SHALL have permissions only for ECR image pull and CloudWatch Logs write; the task role SHALL be limited to: Bedrock `InvokeModel`, SQS `SendMessage`/`ReceiveMessage`/`DeleteMessage`/`GetQueueAttributes`, DynamoDB `GetItem`/`PutItem`/`UpdateItem`/`Query`, SSM `SendCommand`/`GetCommandInvocation`/`GetParameter`/`GetParameters`, Secrets Manager `GetSecretValue`, and CloudWatch `PutMetricData`/`PutLogEvents`; no wildcard resource permissions are permitted
8. THE ObservabilityStack SHALL create the following CloudWatch alarms with SNS notification actions: DLQ depth exceeding 5 messages (1-minute period, 1 consecutive violation), AI reasoning latency p95 exceeding 15 seconds (5-minute period, 2 consecutive violations), remediation failure rate exceeding 30 percent over 5 minutes (2 consecutive violations), and ECS service unhealthy task count exceeding 0 (1-minute period, 1 consecutive violation)
9. THE CDK_App SHALL accept the following required CDK_Context values: `environment` (one of `dev`, `staging`, or `prod`), `awsAccount` (12-digit numeric string), `awsRegion` (string matching the pattern `[a-z]{2}-[a-z]+-[0-9]`, e.g., `us-east-1`), `bedrockModelId` (non-empty string), and `costCenter` (non-empty string, default `platform-engineering`); IF any required CDK_Context value is absent or fails its validation rule, THEN THE CDK_App SHALL fail synthesis with an error message naming the missing or invalid context key
10. THE CDK_App SHALL apply the following resource tags to every resource: `project=aiops-self-healing`, `environment={environment}`, `managed-by=cdk`, and `cost-center={costCenter}` (value from CDK_Context, default `platform-engineering`)
11. WHEN the CDK_App synthesizes a stack for the `prod` environment, THE CDK_App SHALL enable CloudFormation termination protection on all four stacks to prevent accidental deletion
12. THE ObservabilityStack SHALL create a single SNS topic named `aiops-alarms-{environment}` that serves as the notification target for all four CloudWatch alarms defined in criterion 8; all alarm actions SHALL reference this SNS topic
13. THE CDK_App SHALL include CDK Assertions-based unit tests for each stack that verify: exactly 1 VPC, 4 subnets, 1 NAT Gateway, and 9 VPC endpoints are present in NetworkStack; exactly 1 DynamoDB table, 3 GSIs, and 2 SQS queues are present in DataStack; exactly 1 ECS cluster, 1 Fargate task definition, and 2 IAM roles are present in ComputeStack; exactly 4 CloudWatch alarms and 1 SNS topic are present in ObservabilityStack; IAM policies contain no wildcard resource permissions; security groups have no unrestricted inbound (0.0.0.0/0) rules; all four required tags are present on every resource; these tests SHALL be executable via `pytest -m cdk`

---

### Requirement 3: CI/CD Pipeline Implementation

**User Story:** As a platform engineer, I want a fully automated CI/CD pipeline that builds, tests, and deploys the AIOps application, so that every code change is validated and promoted through environments without manual toil.

#### Acceptance Criteria

1. THE CI_Pipeline SHALL be implemented as a GitHub Actions workflow triggered on: push to `main` branch (deploys to `dev`), push to `staging` branch (deploys to `staging`), and creation of a Git tag matching the pattern `v*.*.*` (deploys to `prod`)
2. THE CI_Pipeline SHALL execute the following stages in order, halting and reporting failure if any stage fails: (a) code lint and format check (`ruff` or equivalent), (b) unit tests (`pytest -m unit`), (c) property-based tests (`pytest -m property --hypothesis-seed=0`), (d) CDK stack synthesis (`cdk synth --all`), (e) CDK unit tests (`pytest -m cdk`), (f) Docker image build, (g) ECR vulnerability scan, (h) ECR image push
3. THE CD_Pipeline SHALL be a separate GitHub Actions workflow that receives the Image_Tag artifact from the CI_Pipeline and executes the following stages: (a) deploy NetworkStack and DataStack to the target Environment (parallel where no dependency), (b) deploy ComputeStack, (c) execute Health_Gate check by polling `/health` for 3 consecutive HTTP 200 responses within 120 seconds (retrying every 10 seconds up to 3 times per poll cycle), (d) deploy ObservabilityStack; IF the Health_Gate check fails, THEN THE CD_Pipeline SHALL halt, re-deploy the previous Image_Tag using the stored Deployment_Manifest, and notify the Slack channel before stopping — ObservabilityStack SHALL NOT be deployed after a failed Health_Gate
4. WHEN deploying to the `prod` Environment, THE CD_Pipeline SHALL require a manual approval from a designated approver (configured via GitHub Actions environment protection rules) before the ComputeStack deployment step; the manual approval step SHALL display the Image_Tag, commit SHA, commit message, and a link to the CI_Pipeline run for the approver's review; IF no approval is received within 4 hours, THE CD_Pipeline SHALL cancel the deployment and send a notification to the configured Slack channel
5. THE CI_Pipeline SHALL store AWS credentials using OIDC federation with an IAM role (not long-lived access keys); the GitHub Actions OIDC provider SHALL be the only entity permitted to assume the CI/CD IAM role, scoped to the specific repository and branch via the OIDC subject claim
6. THE CD_Pipeline SHALL perform a CDK diff (`cdk diff`) before each stack deployment and store the diff output as a pipeline artifact retained for 90 days; IF the diff output is empty (no changes), THE CD_Pipeline SHALL skip that stack's deployment step and log that no changes were detected
7. THE CI_Pipeline SHALL cache Python dependency installations (`.venv` or pip cache) and Docker layer caches between runs; the target pipeline duration from push to image push SHALL not exceed 15 minutes when caches are populated and no external service is throttling
8. WHEN any CD_Pipeline stage fails for the `prod` Environment, THE CD_Pipeline SHALL send a notification to the configured Slack channel including: environment name, stage that failed, Image_Tag, commit SHA, and a link to the failed pipeline run; IF the Slack webhook URL is not configured, THE CD_Pipeline SHALL log a warning and continue without treating the notification failure as a pipeline failure
9. THE CI_Pipeline SHALL enforce a minimum code coverage threshold of 80 percent for unit tests; IF coverage falls below 80 percent, THEN the unit test stage SHALL fail and the pipeline SHALL halt

---

### Requirement 4: Configuration and Secrets Management

**User Story:** As a platform engineer, I want all application configuration centralized in AWS SSM Parameter Store and Secrets Manager, so that configuration values are environment-specific, auditable, and never stored in the Docker image or source code.

#### Acceptance Criteria

1. THE CDK_App SHALL create the following SSM Parameter Store parameters under the path `/aiops/{environment}/` for each Environment: `operating-mode` (String, default `rules_only`), `escalation-threshold` (String, default `0.5`), `correlation-window-seconds` (String, default `300`), `max-concurrent-pipelines` (String, default `50`), `bedrock-model-id` (String, no default — required), `sqs-queue-url` (String, populated from DataStack output), `dynamodb-table-name` (String, populated from DataStack output), `audit-log-group-name` (String, populated from ObservabilityStack output), `asset-inventory-path` (String, default `/app/config/asset_inventory.yml`), and `mapping-config-path` (String, default `/app/config/playbook_mapping.yml`)
2. THE CDK_App SHALL create the following Secrets Manager secrets under the path `/aiops/{environment}/` for each Environment: `slack-webhook-url` (SecretString, no default — must be populated post-deployment), `pagerduty-routing-key` (SecretString, optional — empty by default), and `api-gateway-key` (SecretString, generated by CDK for the API Gateway usage plan)
3. WHEN the ECS task starts, THE Orchestrator SHALL retrieve all SSM parameters under `/aiops/{environment}/` using a batch `GetParameters` call before accepting any traffic; IF any of the following required parameters is missing or fails validation — `operating-mode` (must be one of `rules_only`, `ai_only`, `ai_with_fallback`), `escalation-threshold` (must be a float in range 0.0–1.0), `correlation-window-seconds` (must be an integer in range 1–86400), `max-concurrent-pipelines` (must be an integer in range 1–500), `bedrock-model-id` (must be a non-empty string), `sqs-queue-url` (must be a non-empty string), `dynamodb-table-name` (must be a non-empty string) — THEN THE Orchestrator SHALL log the specific parameter name and validation error and exit with a non-zero status code
4. THE Orchestrator SHALL re-fetch all SSM parameters at a configurable interval (minimum 60 seconds, maximum 3600 seconds, default 300 seconds) to pick up configuration changes without requiring a task restart; IF the SSM re-fetch fails, THE Orchestrator SHALL retain the last successfully fetched parameter values, log a warning with the error detail, and retry at the next scheduled interval; parameter changes SHALL take effect for the next alert processed after a successful re-fetch completes
5. WHEN the Orchestrator retrieves a secret from Secrets_Manager, THE Orchestrator SHALL cache the secret value in memory for a configurable TTL (minimum 60 seconds, maximum 86400 seconds, default 3600 seconds) before re-fetching; IF Secrets_Manager returns an error during a re-fetch of a cached secret, THEN THE Orchestrator SHALL continue using the cached value and log a warning with the error detail
6. THE ECS task role SHALL have SSM `GetParameter` and `GetParameters` permissions scoped only to the parameter path `/aiops/{environment}/*`; the task role SHALL have Secrets Manager `GetSecretValue` permission scoped only to secrets matching the path `/aiops/{environment}/*`; no broader parameter or secret access is permitted
7. WHEN a Secrets Manager secret for `slack-webhook-url` or `pagerduty-routing-key` has not been populated (value is empty string), THE Orchestrator SHALL disable the corresponding notification channel at startup and log a warning indicating the channel is unconfigured, rather than failing startup
8. THE CDK_App SHALL enable Secrets Manager automatic rotation for the `api-gateway-key` secret with a rotation schedule of 90 days, using a CDK-generated rotation Lambda; WHEN the secret is rotated, the API Gateway usage plan key SHALL be updated atomically before the old key is invalidated

---

### Requirement 5: Environment Strategy (Dev / Staging / Prod)

**User Story:** As a platform engineer, I want three fully isolated, progressively gated environments, so that changes are validated in lower environments before reaching production.

#### Acceptance Criteria

1. THE CDK_App SHALL deploy three completely isolated Environments (`dev`, `staging`, `prod`), each with fully independent sets of AWS resources (separate VPC, SQS queues, DynamoDB table, ECS service, API Gateway, CloudWatch log groups, SSM parameters, and Secrets Manager secrets) in the same or different AWS accounts as specified by CDK_Context
2. THE `dev` Environment SHALL use the following reduced resource configuration: 1 ECS Fargate task (no auto-scaling), DynamoDB on-demand billing, a single NAT Gateway, CloudWatch log retention of 30 days, and no CloudWatch alarms; the `dev` Environment SHALL NOT have CloudFormation termination protection enabled
3. THE `staging` Environment SHALL match the `prod` Environment resource configuration for ECS auto-scaling (same scale-out/scale-in thresholds), CloudWatch alarms (same 4 alarms), and SQS configuration (same visibility timeout and DLQ policy), but SHALL NOT include the prod-only protections in criterion 4; CloudWatch log retention for staging SHALL be 90 days
4. THE `prod` Environment SHALL have the following additional protections not present in lower environments: CloudFormation termination protection on all stacks, DynamoDB point-in-time recovery (PITR) enabled, SQS message retention extended to 14 days, CloudWatch log retention of 365 days, and AWS Backup plan for the DynamoDB table with daily backups retained for 35 days
5. WHEN a CD_Pipeline deployment to `staging` completes with a passing Health_Gate, THE CD_Pipeline SHALL automatically execute a promotion check that validates the following conditions before allowing promotion to `prod`: all CloudWatch alarms are in `OK` state, DLQ depth is 0, and the `/health` endpoint returns HTTP 200 with all dependencies healthy for 3 consecutive checks at 60-second intervals; IF any condition fails, THE CD_Pipeline SHALL block automatic promotion, notify the configured Slack channel, and require a platform engineer to manually re-trigger the promotion check after addressing the failure
6. THE CDK_App SHALL produce a separate CloudFormation template output file for each Environment (e.g., `cdk.out/dev/`, `cdk.out/staging/`, `cdk.out/prod/`) during synthesis, enabling environment-specific deployments from the same CDK_App codebase without re-running synthesis
7. WHEN deploying to `dev`, THE CD_Pipeline SHALL use CDK `--hotswap` deployment mode for ECS task definition changes to reduce deployment time; hotswap SHALL NOT be used for `staging` or `prod` deployments
8. THE `prod` Environment SHALL be deployable to a separate AWS account to provide account-level blast radius isolation; cross-account deployment SHALL be supported by the CDK_App via CDK cross-account role assumption using CDK_Context values (`awsAccount` and `awsRegion`)

---

### Requirement 6: Health Gates and Deployment Validation

**User Story:** As a platform engineer, I want automated post-deployment health checks to validate each deployment before it is declared successful, so that broken deployments are detected and rolled back before impacting users.

#### Acceptance Criteria

1. WHEN a ComputeStack deployment completes, THE CD_Pipeline SHALL execute the Health_Gate check by polling the ECS service's `/health` endpoint via API Gateway every 30 seconds for up to 5 minutes; the `/health` endpoint response body SHALL contain a JSON object listing each dependency (`sqs`, `dynamodb`) with status `healthy` or `unhealthy`; IF the endpoint returns HTTP 200 with both `sqs` and `dynamodb` reporting `healthy` for 3 consecutive polls, THE Health_Gate SHALL pass; IF the endpoint does not satisfy this condition within 5 minutes, THE Health_Gate SHALL fail
2. WHEN the Health_Gate fails, THE CD_Pipeline SHALL initiate a Rollback within 60 seconds by re-deploying the previous Deployment_Manifest (previous Image_Tag and CDK stack versions); the Rollback SHALL complete within 10 minutes; WHEN the Rollback completes, THE CD_Pipeline SHALL re-run the Health_Gate check on the rolled-back deployment
3. WHEN a new ECS task definition is deployed, THE CD_Pipeline SHALL use ECS rolling update with a minimum healthy percent of 100 and a maximum percent of 200 for `staging` and `prod` Environments, ensuring at least the current number of tasks remain healthy throughout the deployment
4. THE CD_Pipeline SHALL verify the following CloudWatch alarms are in the `OK` state after each deployment to `staging` or `prod` before declaring the Health_Gate passed: DLQ depth alarm, ECS unhealthy task alarm; IF any alarm is in `ALARM` or `INSUFFICIENT_DATA` state after the Health_Gate timeout period, THE Health_Gate SHALL fail
5. WHEN a Canary_Task deployment is requested (via pipeline flag), THE CD_Pipeline SHALL deploy exactly 1 new-version ECS task alongside existing tasks, wait 5 minutes as the observation window, query CloudWatch for error rate and p95 latency metrics from that task over the 5-minute observation window, and proceed to full rollout only if the error rate is below 5 percent and latency p95 is below 15 seconds; IF either threshold is exceeded, THE CD_Pipeline SHALL terminate the Canary_Task and retain the previous version
6. THE Health_Gate SHALL publish its pass/fail result (1 for pass, 0 for fail) and duration in seconds as custom CloudWatch metrics (`DeploymentHealthGatePassed`, `DeploymentHealthGateDuration`) tagged with the Environment and Image_Tag, upon Health_Gate completion

---

### Requirement 7: Rollback Procedures

**User Story:** As a platform engineer, I want automated and documented manual rollback procedures, so that any failed or degraded deployment can be reversed quickly and safely.

#### Acceptance Criteria

1. THE CD_Pipeline SHALL maintain a Deployment_Manifest for the last 5 successful deployments per Environment stored as SSM Parameter Store values under `/aiops/{environment}/deployment-history/{n}` where n=1 is the most recent and n=5 is the oldest; each Deployment_Manifest SHALL contain: Image_Tag, commit SHA, CDK stack versions (CloudFormation stack change set IDs), deployment timestamp, and Health_Gate result; GitHub Actions pipeline artifacts SHALL also retain a copy of each manifest for 90 days
2. WHEN an automated Rollback is triggered, THE CD_Pipeline SHALL re-deploy the most recent successful Deployment_Manifest (n=1) by re-running the CD_Pipeline with the stored Image_Tag and CDK context, bypassing the manual approval gate; the automated Rollback SHALL complete and pass the Health_Gate within 15 minutes
3. THE CDK_App SHALL support a manual rollback command via a parameterized `make rollback ENVIRONMENT={env} MANIFEST={n}` target in the project Makefile that retrieves the specified Deployment_Manifest from SSM Parameter Store and invokes the CD_Pipeline with those parameters; the Makefile target SHALL output the Deployment_Manifest contents for operator review before invoking the pipeline; IF the specified manifest (n) does not exist in SSM Parameter Store, THE Makefile target SHALL exit with a non-zero status code and an error message identifying the missing manifest, without invoking the CD_Pipeline
4. WHEN a CDK_Stack deployment fails, CloudFormation SHALL automatically roll back all resources in that stack to their previous state; THE CD_Pipeline SHALL detect the CloudFormation `ROLLBACK_COMPLETE` state, log the failure reason from the CloudFormation stack events, and halt the CD_Pipeline with a failure status
5. THE ObservabilityStack SHALL create a CloudWatch alarm named `RollbackRequired-{environment}` that activates when both the ECS unhealthy task alarm and the DLQ depth alarm are each continuously in `ALARM` state for 5 or more minutes at the same time; this alarm SHALL trigger an SNS notification to the on-call Slack channel indicating a rollback may be needed
6. WHEN a database schema migration is required (DynamoDB GSI addition or removal), THE CD_Pipeline SHALL apply the migration sequentially: to `dev` first, then wait until the Health_Gate passes AND no alarms are in `ALARM` state for a continuous 24-hour window, then apply to `staging`, then wait for the same 24-hour continuous success window, then apply to `prod`; schema migrations SHALL NOT be bundled with application code deployments — they SHALL be separate, sequenced deployments

---

### Requirement 8: Operational Runbooks

**User Story:** As an operations engineer, I want documented runbooks for common operational tasks, so that on-call engineers can respond to incidents consistently and safely without requiring tribal knowledge.

#### Acceptance Criteria

1. THE project repository SHALL contain a `runbooks/` directory with individual Markdown files for each of the following operational scenarios: `scale-out.md` (manual ECS task scaling), `scale-in.md` (manual ECS task reduction), `rollback.md` (manual deployment rollback procedure), `dlq-replay.md` (replaying messages from the DLQ to the main queue), `bedrock-throttling.md` (responding to Bedrock API throttling incidents), `parameter-update.md` (updating SSM parameters without service restart), and `incident-response.md` (general incident triage procedure)
2. IF a runbook describes a destructive or irreversible action (DLQ purge, task stop, table restore), THEN THE runbook SHALL include a `⚠️ WARNING` section formatted as an H2 or H3 Markdown heading immediately preceding the action step, describing what the action does, what data or availability may be affected, and the confirmation command required before execution
3. THE `scale-out.md` runbook SHALL document the following steps: how to verify the current ECS service task count via the AWS CLI, how to update the desired count using `aws ecs update-service`, how to verify the new tasks are healthy via the `/health` endpoint, and how to confirm the SQS queue depth is lower than the value observed 60 seconds before scaling
4. THE `dlq-replay.md` runbook SHALL document the following steps: how to inspect DLQ messages before replay using the AWS CLI, how to move messages from the DLQ back to the main queue using `aws sqs`, how to monitor the reprocessing via CloudWatch metrics, and how to identify and isolate messages that fail reprocessing 3 or more times
5. THE `rollback.md` runbook SHALL document both the automated rollback path (triggering the CD_Pipeline rollback) and the manual rollback path (using the `make rollback` Makefile target), including how to verify the rollback succeeded via Health_Gate output and CloudWatch alarms
6. THE `incident-response.md` runbook SHALL include a decision tree: starting from a CloudWatch alarm firing, it SHALL guide the engineer through checking ECS task health, SQS queue depth, DLQ depth, Bedrock throttling metrics, and CloudWatch application error logs, with specific AWS CLI commands for each check step

---

### Requirement 9: Monitoring and Alerting Strategy

**User Story:** As an operations engineer, I want a comprehensive monitoring strategy with meaningful alarms and dashboards, so that system health is continuously visible and critical issues are surfaced before they impact remediation outcomes.

#### Acceptance Criteria

1. THE ObservabilityStack SHALL create a CloudWatch dashboard named `AIOps-{environment}` containing the following widgets: ECS task count (current vs desired), SQS main queue depth (messages visible), DLQ depth, AI reasoning latency (p50/p95/p99 over 1-hour window), Bedrock invocation count and error count, remediation success/failure count, escalation count, and ECS CPU/memory utilization
2. THE Orchestrator SHALL publish the following custom CloudWatch metrics to the namespace `AIOps/{environment}`: `AlertsReceived` (Count), `AIReasoningInvocations` (Count), `AIReasoningLatency` (Milliseconds — p50, p95, p99), `FallbackToRulesCount` (Count), `RemediationsExecuted` (Count), `RemediationSuccessCount` (Count), `RemediationFailureCount` (Count), `HumanEscalationsCount` (Count), `BedrockThrottleCount` (Count), and `DeadLetterQueueDepth` (Count); all metrics SHALL be published within 60 seconds of the event occurring
3. THE ObservabilityStack SHALL configure a CloudWatch Contributor Insights rule on the application log group to identify the top 10 alert names by frequency over a 1-hour rolling window, enabling rapid identification of alert storms
4. WHEN any CloudWatch alarm in the `prod` Environment transitions to the `ALARM` state, THE ObservabilityStack SHALL trigger an SNS topic that publishes a notification to the configured Slack channel; WHERE the CDK_Context `pagerdutyRoutingKey` is configured and non-empty, THE ObservabilityStack SHALL also publish the same notification to the PagerDuty routing key; the notification SHALL include: alarm name, alarm description, metric value that triggered the alarm, and a link to the CloudWatch alarm console
5. THE ObservabilityStack SHALL create a CloudWatch Synthetics canary that sends a synthetic webhook payload to the API Gateway `/webhook` endpoint every 5 minutes and verifies an HTTP 200 response is received within 2 seconds; WHEN the canary receives a non-200 response or receives no response within 2 seconds on 2 consecutive checks, THE ObservabilityStack SHALL trigger the same SNS alarm notification as a real CloudWatch alarm
6. THE Orchestrator SHALL emit structured JSON log entries to CloudWatch Logs with the following fields present on every entry: `timestamp` (ISO 8601), `level` (INFO/WARN/ERROR), `incident_id`, `pipeline_stage`, `duration_ms`, `outcome`, and `environment`; log entries SHALL NOT contain raw secret values, PII, or unredacted alert label values matching the configured redaction patterns

---

### Requirement 10: Cost Controls and Governance

**User Story:** As a platform engineer, I want cost controls and tagging governance enforced at the infrastructure level, so that AWS spend is predictable, attributed, and bounded.

#### Acceptance Criteria

1. THE CDK_App SHALL create an AWS Budgets budget per Environment named `aiops-{environment}-monthly` with a configurable monthly USD limit (default $200 for `dev`, $500 for `staging`, $2000 for `prod`, configurable via CDK_Context)
2. WHEN actual spend in the current month reaches 80 percent of the configured monthly limit for an Environment, THE CDK_App SHALL send a budget alert to the cost-center email address configured in CDK_Context
3. WHEN actual spend in the current month reaches 100 percent of the configured monthly limit, THE CDK_App SHALL send a second budget alert to the same cost-center email address
4. IF the cost-center email address is not present in CDK_Context at synthesis time, THEN THE CDK_App SHALL fail synthesis with an error identifying the missing `costCenterEmail` context key
5. THE `dev` Environment SHALL use ECS Fargate Spot capacity provider as the primary task execution provider; IF Spot capacity is unavailable, THE `dev` Environment SHALL fall back to on-demand ECS Fargate capacity; the `staging` and `prod` Environments SHALL use on-demand ECS Fargate capacity only
6. THE `dev` Environment SHALL have no CloudWatch Synthetics canary deployed
7. THE ObservabilityStack SHALL create a CloudWatch metric math expression that estimates hourly Bedrock cost in USD based on the `AIReasoningInvocations` count multiplied by a configurable per-invocation cost estimate (stored in SSM Parameter Store at `/aiops/{environment}/bedrock-cost-per-invocation`); WHEN the estimated hourly Bedrock cost exceeds the configurable threshold (default $10/hour, stored in SSM at `/aiops/{environment}/bedrock-cost-alarm-threshold`), THE ObservabilityStack SHALL trigger an alarm notification via the SNS topic defined in Requirement 9
8. THE CDK_App SHALL enforce the `cost-center` tag as required on all resources; IF a resource is deployed without the `cost-center` tag during CDK synthesis, THEN THE CDK_App SHALL fail synthesis with an error identifying the resource missing the tag
9. WHEN the ECS auto-scaling configuration scales the service above 5 tasks, THE Orchestrator SHALL publish a CloudWatch metric named `AutoScalingAboveNominal` to the `AIOps/{environment}` namespace tagged with the current task count
10. WHEN the ECS service task count exceeds 8, THE ObservabilityStack alarm for high task count SHALL trigger a notification to the operations channel via the SNS topic defined in Requirement 9

