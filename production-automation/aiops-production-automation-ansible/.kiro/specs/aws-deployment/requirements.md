# Requirements Document

## Introduction

This document defines the requirements for deploying the AIOps Self-Healing Infrastructure application on AWS in a production-ready configuration. The deployment covers compute (ECS Fargate), networking (VPC, ALB), security (IAM, Secrets Manager, Security Groups), monitoring (CloudWatch, Prometheus), persistent storage (EFS for audit logs), and operational concerns (auto-scaling, CI/CD, disaster recovery). The service receives Prometheus Alertmanager webhooks, executes Ansible playbooks against target hosts via SSH, and notifies teams through Slack/Email/PagerDuty.

## Glossary

- **ECS_Service**: The AWS ECS Fargate service running the self-healing infrastructure container
- **ALB**: The Application Load Balancer that routes inbound webhook traffic to the ECS tasks
- **VPC**: The Virtual Private Cloud providing network isolation for all deployment resources
- **Secrets_Manager**: AWS Secrets Manager storing sensitive configuration values (Slack webhook URL, SSH keys, SMTP credentials)
- **EFS_Volume**: The Elastic File System volume mounted to ECS tasks for persistent audit log storage
- **CloudWatch**: AWS CloudWatch service collecting container logs, metrics, and alarms
- **ECR_Registry**: The Elastic Container Registry storing the Docker image for the self-healing service
- **Auto_Scaler**: The ECS Service Auto Scaling configuration that adjusts task count based on load
- **NAT_Gateway**: The NAT Gateway enabling outbound internet access from private subnets
- **Security_Group**: AWS Security Groups controlling inbound and outbound network traffic
- **IAM_Role**: AWS IAM roles providing least-privilege permissions to ECS tasks
- **Target_Host**: An EC2 instance or server that the self-healing service remediates via SSH
- **Parameter_Store**: AWS Systems Manager Parameter Store holding non-sensitive configuration values
- **CI_CD_Pipeline**: The AWS CodePipeline or GitHub Actions pipeline that builds, tests, and deploys the service

## Requirements

### Requirement 1: Container Compute on ECS Fargate

**User Story:** As a platform engineer, I want the self-healing service to run on ECS Fargate, so that I do not manage underlying EC2 instances and the service scales independently.

#### Acceptance Criteria

1. THE ECS_Service SHALL run the self-healing container on AWS Fargate with a desired count of 2 tasks distributed across at least 2 Availability Zones
2. THE ECS_Service SHALL allocate at least 1 vCPU and 2 GB memory per task to support 50 concurrent pipeline executions and 10 concurrent Ansible executions
3. WHEN a task fails its health check 3 consecutive times at an interval of 10 seconds against the GET /health endpoint, THE ECS_Service SHALL replace the unhealthy task with a new task within 60 seconds while maintaining at least 1 healthy task running
4. IF a replacement task fails to reach a healthy state within 120 seconds, THEN THE ECS_Service SHALL retry task placement up to 3 times, and IF all 3 retry attempts fail, THEN THE ECS_Service SHALL raise a service alarm after exactly the third failed retry attempt
5. THE ECS_Service SHALL configure the container stop timeout to 30 seconds to allow graceful SIGTERM-based pipeline draining
6. THE ECS_Service SHALL mount the EFS_Volume at /app/logs for persistent audit log storage across task replacements

### Requirement 2: Network Isolation and Load Balancing

**User Story:** As a security engineer, I want the service deployed in a private subnet behind an ALB, so that the service is not directly exposed to the internet and traffic is distributed across tasks.

#### Acceptance Criteria

1. THE VPC SHALL contain at least 2 public subnets and 2 private subnets across separate Availability Zones
2. THE ECS_Service SHALL run exclusively in private subnets with no public IP addresses assigned to tasks
3. THE ALB SHALL terminate HTTPS traffic on port 443 using an ACM-managed TLS certificate and forward requests to ECS tasks on port 8080
4. THE ALB SHALL perform health checks against the /health endpoint every 30 seconds with a 5-second timeout, a healthy threshold of 2 consecutive successes, and an unhealthy threshold of 3 consecutive failures
5. THE NAT_Gateway SHALL be deployed in each public subnet (one per Availability Zone) to provide redundant outbound internet access from private subnets for Slack webhook delivery, SMTP notifications, and PagerDuty API calls
6. WHEN the ALB receives an HTTP request on any port, THE ALB SHALL redirect the request to HTTPS port 443 with a 301 status code
7. THE Security_Groups SHALL restrict inbound traffic to the ALB on ports 443 and 80 from 0.0.0.0/0, and restrict inbound traffic to ECS tasks on port 8080 exclusively from the ALB security group
8. IF all registered ECS tasks fail health checks, THEN THE ALB SHALL return a 503 Service Unavailable response to the client

### Requirement 3: Security and Access Control

**User Story:** As a security engineer, I want least-privilege IAM roles and encrypted secrets, so that the service operates with minimal permissions and sensitive data is protected at rest and in transit.

#### Acceptance Criteria

1. THE IAM_Role SHALL grant the ECS task execution role permissions limited to pulling images from ECR_Registry, reading secrets from Secrets_Manager, writing logs to CloudWatch, and mounting EFS_Volume, with all policy statements scoped to specific resource ARNs and no wildcard (*) resource values
2. THE IAM_Role SHALL grant the ECS task role permissions limited to reading from Parameter_Store and writing to CloudWatch Metrics, with all policy statements scoped to specific resource ARNs and no wildcard (*) resource values
3. THE Secrets_Manager SHALL store SLACK_WEBHOOK_URL, SSH private keys, and SMTP credentials as encrypted secrets using AWS-managed KMS keys
4. THE Security_Group for ECS tasks SHALL allow inbound traffic only from the ALB Security_Group on port 8080 and SHALL deny all other inbound traffic by default
5. THE Security_Group for ECS tasks SHALL allow outbound traffic to Target_Host instances on port 22 (SSH), to the NAT_Gateway for internet-bound traffic, and to the EFS_Volume on port 2049 (NFS), and SHALL deny all other outbound traffic
6. THE ECS_Service SHALL run the container as the non-root user "appuser" with a read-only root filesystem where applicable, matching the USER directive in the Dockerfile
7. THE IAM_Role SHALL enforce task-level role scoping by assigning separate IAM roles to the task execution role and the task role, with no wildcard (*) resource ARNs and no inline policies granting broader permissions than those specified in criteria 1 and 2
8. IF the ECS task fails to retrieve secrets from Secrets_Manager at startup, THEN THE ECS_Service SHALL prevent the container from reaching a healthy state and SHALL log an error indicating the unreachable secret identifier

### Requirement 4: SSH Connectivity to Target Hosts

**User Story:** As a platform engineer, I want the ECS tasks to reach target hosts via SSH, so that Ansible playbooks can execute remediation actions on infrastructure.

#### Acceptance Criteria

1. WHEN an ECS task starts, THE ECS_Service SHALL retrieve SSH private keys from Secrets_Manager within 10 seconds and write them to an in-memory tmpfs mount with 0600 permissions owned by the task execution user
2. THE Security_Group for Target_Host instances SHALL allow inbound SSH (port 22) only from the ECS task Security_Group referenced by Security Group ID
3. WHEN an Ansible playbook execution exceeds 300 seconds, THE ECS_Service SHALL terminate the subprocess and log a timeout event to the audit log including the incident_id, target_host, and playbook_path
4. THE VPC SHALL provide network connectivity between private subnets (ECS tasks) and Target_Host instances via VPC peering, Transit Gateway, or same-VPC routing
5. IF the ECS_Service fails to retrieve SSH private keys from Secrets_Manager (API error, timeout, or access denied), THEN THE ECS_Service SHALL log an error including the secret ARN and failure reason, and SHALL not accept remediation requests until key retrieval succeeds
6. IF an SSH connection to a Target_Host fails (connection refused, authentication failure, or host unreachable), THEN THE ECS_Service SHALL mark the execution as failed, log the connection error including the target_host and failure reason, and return a failure result to the Orchestrator
7. WHEN an ECS task stops or is replaced, THE ECS_Service SHALL ensure SSH private key material is not persisted beyond the lifetime of the in-memory tmpfs mount

### Requirement 5: Monitoring and Observability

**User Story:** As an SRE, I want comprehensive monitoring of the deployed service, so that I can detect failures, track remediation success rates, and respond to service degradation.

#### Acceptance Criteria

1. THE ECS_Service SHALL send container stdout/stderr logs to a CloudWatch Log Group with a retention period of 30 days
2. THE CloudWatch SHALL collect the /metrics endpoint data via a Prometheus-compatible scraping mechanism at 60-second intervals with a scrape timeout of 10 seconds
3. WHEN the ECS_Service healthy task count drops below 2 for 2 consecutive evaluation periods of 60 seconds each, THE CloudWatch SHALL trigger an alarm and send a notification to the operations SNS topic within 60 seconds of the alarm state transition
4. WHEN the ALB target response time exceeds 5 seconds at the p95 percentile for 3 consecutive evaluation periods of 60 seconds each, THE CloudWatch SHALL trigger a latency alarm and send a notification to the operations SNS topic
5. THE CloudWatch SHALL create a dashboard displaying webhook request rate, playbook execution success/failure counts, active pipeline count, and task health status with a default time window of 3 hours and an auto-refresh interval of 60 seconds
6. WHEN an Ansible playbook execution fails, THE ECS_Service SHALL emit a CloudWatch custom metric named PlaybookExecutionFailure with a metric value of 1, unit of Count, and dimensions for alert_name and target_host; THE ECS_Service SHALL NOT emit this metric when playbook execution succeeds
7. IF the Prometheus-compatible scraping mechanism fails to collect metrics from the /metrics endpoint for 3 consecutive scrape intervals, THEN THE CloudWatch SHALL trigger an alarm and send a notification to the operations SNS topic
8. WHEN a CloudWatch alarm transitions from ALARM state back to OK state, THE CloudWatch SHALL send a resolution notification to the operations SNS topic; notifications SHALL only be sent on actual state transitions and SHALL NOT be sent for alarms already in OK state at system startup

### Requirement 6: Auto Scaling

**User Story:** As a platform engineer, I want the service to scale horizontally based on load, so that it handles alert storms without manual intervention and scales down during quiet periods to reduce cost.

#### Acceptance Criteria

1. WHEN average CPU utilization across all running ECS tasks in the service exceeds 60% for 3 consecutive 60-second evaluation periods, THE Auto_Scaler SHALL increase the ECS task count by adding 2 tasks
2. WHEN average CPU utilization across all running ECS tasks in the service drops below 30% for 10 consecutive 60-second evaluation periods, THE Auto_Scaler SHALL decrease the ECS task count by removing 1 task
3. IF any scaling event would cause the task count to exceed 10 or fall below 2, THEN THE Auto_Scaler SHALL clamp the resulting task count to the breached boundary (maximum 10, minimum 2) regardless of the calculated scaling adjustment
4. THE Auto_Scaler SHALL scale out by adding 2 tasks per scaling event and scale in by removing 1 task per scaling event to provide asymmetric scaling behavior
5. THE Auto_Scaler SHALL enforce a 120-second cooldown period independently for scale-out and scale-in directions, during which scaling events in the same direction SHALL be suppressed while scaling events in the opposite direction SHALL remain eligible

### Requirement 7: Persistent Audit Log Storage

**User Story:** As a compliance officer, I want audit logs persisted beyond container lifecycle, so that remediation actions are traceable for incident review and compliance audits.

#### Acceptance Criteria

1. THE EFS_Volume SHALL be mounted to all ECS tasks at /app/logs with read-write access
2. THE EFS_Volume SHALL use encryption at rest with an AWS-managed KMS key
3. WHILE ECS tasks are connected to the EFS_Volume, THE EFS_Volume SHALL enforce encryption in transit via TLS for all data transfers
4. THE EFS_Volume SHALL be configured with a lifecycle policy that transitions files to Infrequent Access storage after 30 days
5. IF an ECS task is replaced or scaled down, THEN THE EFS_Volume SHALL retain all previously written audit log files such that every file written prior to the task termination remains readable and byte-identical upon subsequent access
6. THE EFS_Volume SHALL retain audit log files for a minimum of 90 days from the file creation date before any automated deletion or archival removal is permitted
7. IF an ECS task fails to mount the EFS_Volume at startup, THEN THE ECS task SHALL fail to start and not proceed with remediation execution, even if the mount failure reporting mechanism itself fails; the task SHALL prioritize failing fast over successful status reporting
8. IF the EFS_Volume becomes unavailable during task execution, THEN THE ECS task SHALL log the failure locally to stdout and abort any in-progress remediation, dispatching a notification indicating audit log storage failure

### Requirement 8: Configuration Management

**User Story:** As a platform engineer, I want application configuration managed through AWS-native services, so that configuration changes do not require container redeployment and secrets are never stored in environment variables directly.

#### Acceptance Criteria

1. THE Parameter_Store SHALL store non-sensitive configuration values: ASSET_INVENTORY_PATH, MAPPING_CONFIG_PATH, AUDIT_LOG_PATH, PORT (valid range: 1024–65535), LOG_LEVEL (one of: DEBUG, INFO, WARNING, ERROR, CRITICAL), and SERVICE_VERSION (maximum 64 characters)
2. THE Secrets_Manager SHALL store sensitive configuration values: SLACK_WEBHOOK_URL, SSH private keys, SMTP credentials, and PagerDuty API token, each as individual secrets with a maximum value size of 10 KB
3. WHEN the ECS task starts, THE ECS_Service SHALL inject Parameter_Store values as plaintext environment variables and Secrets_Manager values as secret references (using the valueFrom field in the task definition) so that secret values are resolved at runtime and never stored as plaintext in the task definition or container inspection output
4. IF either Parameter_Store or Secrets_Manager is unreachable during ECS task startup, THEN THE ECS_Service SHALL fail the task launch and report a configuration retrieval error in the ECS stopped-task reason within 60 seconds; already-running tasks SHALL continue operating even if Parameter_Store or Secrets_Manager becomes unreachable after startup
5. WHEN a secret is rotated in Secrets_Manager, THE ECS_Service SHALL pick up the new secret value within 5 minutes by triggering a forced task redeployment that launches new tasks with the updated secret reference
6. IF a referenced parameter or secret is missing or deleted at task startup, THEN THE ECS_Service SHALL prevent the task from reaching RUNNING state and record the missing configuration key name in the ECS stopped-task reason

### Requirement 9: CI/CD Pipeline

**User Story:** As a developer, I want an automated pipeline that builds, tests, and deploys the service, so that code changes reach production safely with minimal manual steps.

#### Acceptance Criteria

1. WHEN code is pushed to the main branch, THE CI_CD_Pipeline SHALL build the Docker image, run unit and property-based tests, and push the image to ECR_Registry with a tag matching the git commit SHA, completing the build and test stages within 15 minutes
2. IF the build fails or any test fails during the build stage, THEN THE CI_CD_Pipeline SHALL abort the pipeline, skip the image push and deployment stages, and report the failure with the failing stage name and error summary
3. WHEN the image is successfully pushed to ECR_Registry, THE CI_CD_Pipeline SHALL perform a rolling deployment to ECS_Service with a minimum healthy percent of 100% and maximum percent of 200%, and THE CI_CD_Pipeline SHALL ensure the deployment completes successfully within 10 minutes
4. IF the new task fails health checks (3 consecutive failed health check responses) within 5 minutes of deployment, THEN THE CI_CD_Pipeline SHALL automatically roll back to the previous task definition revision
5. WHEN the rolling deployment completes successfully, THE CI_CD_Pipeline SHALL run a post-deployment smoke test that sends a synthetic webhook to the /webhook endpoint and verifies a 200 response within 10 seconds
6. IF the post-deployment smoke test does not receive a 200 response within 10 seconds after up to 3 retry attempts spaced 5 seconds apart, THEN THE CI_CD_Pipeline SHALL trigger a rollback to the previous task definition revision and report the smoke test failure

### Requirement 10: Disaster Recovery and High Availability

**User Story:** As a platform engineer, I want the deployment to survive single-AZ failures, so that the self-healing service remains available during AWS infrastructure incidents.

#### Acceptance Criteria

1. THE ECS_Service SHALL distribute tasks across at least 2 Availability Zones using the spread placement strategy with a minimum desired task count of 2 to ensure at least one task is schedulable in each Availability Zone
2. THE ALB SHALL route traffic only to healthy tasks as determined by the /health endpoint health check configured with a health check interval of 10 seconds, a timeout of 5 seconds, a healthy threshold of 2 consecutive successes, and an unhealthy threshold of 3 consecutive failures
3. THE EFS_Volume SHALL replicate data across at least 2 Availability Zones within the same AWS region
4. WHEN an entire Availability Zone becomes unavailable, THE ECS_Service SHALL maintain at least 1 running task in the remaining Availability Zone(s) and the ALB SHALL continue routing requests to healthy tasks such that the /webhook endpoint remains reachable within 60 seconds of the AZ failure event
5. THE VPC SHALL deploy NAT_Gateway instances in each public subnet to avoid single-AZ NAT failure impacting outbound connectivity
6. IF the ECS_Service desired task count falls below the minimum desired count of 2 due to an Availability Zone failure, THEN THE ECS_Service SHALL launch replacement tasks in the remaining healthy Availability Zone(s) to restore the desired count

### Requirement 11: Prometheus and Alertmanager Integration

**User Story:** As an SRE, I want Prometheus and Alertmanager deployed alongside the service on AWS, so that the existing alert pipeline continues to function in the cloud environment.

#### Acceptance Criteria

1. THE ECS_Service SHALL deploy Alertmanager as a separate ECS service with a desired task count of 1 in the same VPC, with its webhook receiver URL pointing to the ALB endpoint of the self-healing service
2. THE ECS_Service SHALL deploy Prometheus as a separate ECS service with a desired task count of 1, configured to scrape the self-healing service /metrics endpoint and the Alertmanager /metrics endpoint at a scrape interval of 15 seconds
3. THE Security_Group for Alertmanager SHALL allow inbound traffic only from the Prometheus Security_Group on port 9093 and outbound traffic to the ALB on port 443, with all other inbound and outbound traffic denied by default
4. WHEN Alertmanager sends a webhook to the self-healing service, THE ALB SHALL route the request to a healthy ECS task with a target routing time of 1 second; IF routing exceeds 1 second due to network latency or ALB processing delays, THE system SHALL still be considered compliant provided the request is eventually delivered successfully
5. IF Alertmanager fails to deliver a webhook to the self-healing service ALB endpoint, THEN Alertmanager SHALL retry the delivery up to 3 times with a minimum interval of 5 seconds between attempts before marking the notification as failed
6. THE ECS_Service SHALL store Prometheus time-series data on an EBS-backed volume or EFS mount with a minimum capacity of 50 GB and a retention period of at least 15 days
7. THE ECS_Service SHALL configure ECS health checks for both the Prometheus and Alertmanager tasks, polling the Prometheus /-/healthy endpoint on port 9090 and the Alertmanager /-/healthy endpoint on port 9093, with a health check interval of 30 seconds and an unhealthy threshold of 3 consecutive failures
8. IF the Prometheus or Alertmanager ECS task is replaced or restarted, THEN THE ECS_Service SHALL ensure the replacement task becomes healthy within 120 seconds and resumes its configured scrape or alerting functions without manual intervention
