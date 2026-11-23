# Implementation Plan: AWS Deployment

## Overview

Deploy the AIOps Self-Healing Infrastructure application on AWS using CDK (Python) with nested stacks. The implementation follows a bottom-up approach: foundational infrastructure (VPC, security, storage) first, then compute and load balancing, followed by monitoring, auto-scaling, Prometheus/Alertmanager, and finally the CI/CD pipeline. Each stack is implemented as a separate CDK Stack class with cross-stack references.

## Tasks

- [ ] 1. Set up CDK project structure and shared configuration
  - [ ] 1.1 Initialize CDK Python project with directory structure and dependencies
    - Create `cdk_app/` directory with `app.py`, `stacks/`, `constructs/`, and `tests/` directories
    - Create `cdk.json` with context values (vpc_cidr, service_name, container_port, desired_count, cpu, memory, health_check_path, efs_mount_path, log_retention_days, etc.)
    - Create `requirements.txt` with aws-cdk-lib, constructs, pytest, cdk-nag dependencies
    - Define dataclass models in `cdk_app/config.py`: TaskConfig, ServiceConfig, SecretConfig, ParameterConfig, ScalingPolicy, AlarmConfig
    - _Requirements: 1.1, 1.2, 6.3, 8.1, 8.2_

  - [ ] 1.2 Create CDK App entry point with nested stack wiring
    - Implement `cdk_app/app.py` that instantiates all stacks in dependency order
    - Wire cross-stack references: NetworkStack → SecurityStack → StorageStack → ComputeStack → LoadBalancerStack → MonitoringStack → AutoScalingStack → PrometheusStack → PipelineStack
    - Pass VPC, security groups, roles, and service references between stacks via constructor parameters
    - _Requirements: 1.1, 2.1, 3.1_

- [ ] 2. Implement NetworkStack
  - [ ] 2.1 Create VPC with multi-AZ subnets and NAT Gateways
    - Implement `cdk_app/stacks/network_stack.py` with VPC (10.0.0.0/16, 2 AZs)
    - Configure 2 public subnets (for ALB, NAT Gateways) and 2 private subnets (for ECS, EFS)
    - Deploy 1 NAT Gateway per AZ for redundant outbound connectivity
    - Expose `vpc`, `private_subnets`, `public_subnets` as stack properties
    - _Requirements: 2.1, 2.5, 4.4, 10.5_

  - [ ]* 2.2 Write CDK template assertion tests for NetworkStack
    - Test VPC has correct CIDR and 2 AZs
    - Test NAT Gateway count equals 2 (one per AZ)
    - Test subnet configuration (public/private per AZ)
    - _Requirements: 2.1, 2.5, 10.5_

- [ ] 3. Implement SecurityStack
  - [ ] 3.1 Create IAM roles with least-privilege policies
    - Implement `cdk_app/stacks/security_stack.py`
    - Create Task Execution Role: ECR pull, Secrets Manager read, CloudWatch logs, EFS mount — all scoped to specific resource ARNs (no wildcard resources)
    - Create Task Role: Parameter Store read, CloudWatch Metrics write — all scoped to specific resource ARNs
    - Enforce separate execution role and task role with no inline wildcard policies
    - _Requirements: 3.1, 3.2, 3.7_

  - [ ] 3.2 Create Security Groups with least-privilege rules
    - ALB Security Group: inbound 443/80 from 0.0.0.0/0
    - ECS Security Group: inbound 8080 from ALB SG only, outbound to Target Hosts on port 22, NAT Gateway for internet, EFS on port 2049
    - EFS Security Group: inbound 2049 from ECS SG
    - Prometheus Security Group: allow scraping ECS on 8080 and Alertmanager on 9093
    - Alertmanager Security Group: inbound from Prometheus SG on 9093, outbound to ALB on 443
    - _Requirements: 2.7, 3.4, 3.5, 4.2, 11.3_

  - [ ] 3.3 Configure Secrets Manager and Parameter Store entries
    - Create Secrets Manager secrets: SLACK_WEBHOOK_URL, SSH private keys, SMTP credentials, PagerDuty API token (each as individual secrets, max 10 KB)
    - Create Parameter Store parameters: ASSET_INVENTORY_PATH, MAPPING_CONFIG_PATH, AUDIT_LOG_PATH, PORT, LOG_LEVEL, SERVICE_VERSION
    - Use AWS-managed KMS keys for secret encryption
    - _Requirements: 3.3, 8.1, 8.2_

  - [ ]* 3.4 Write compliance tests for SecurityStack
    - Test no IAM policy statement contains `Resource: "*"`
    - Test ECS SG only allows inbound from ALB SG on port 8080
    - Test ALB SG allows only 443/80 from 0.0.0.0/0
    - Test EFS SG allows only 2049 from ECS SG
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.7, 2.7_

- [ ] 4. Implement StorageStack
  - [ ] 4.1 Create EFS file system with encryption and lifecycle policies
    - Implement `cdk_app/stacks/storage_stack.py`
    - Configure EFS with encryption at rest (AWS-managed KMS key)
    - Enable encryption in transit (TLS)
    - Set lifecycle policy: transition to Infrequent Access after 30 days
    - Create mount targets in each private subnet
    - Configure 90-day minimum retention before deletion
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 10.3_

  - [ ] 4.2 Create ECR repository with lifecycle policy
    - Create ECR repository for the self-healing service image
    - Configure image scanning on push
    - Add lifecycle policy to remove untagged images after 30 days
    - _Requirements: 9.1_

  - [ ]* 4.3 Write CDK template assertion tests for StorageStack
    - Test EFS has `Encrypted: true` with KMS key association
    - Test EFS lifecycle policy transitions to IA after 30 days
    - Test ECR repository exists with scanning enabled
    - _Requirements: 7.2, 7.3, 7.4_

- [ ] 5. Checkpoint - Ensure foundational stacks synthesize correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement ComputeStack
  - [ ] 6.1 Create ECS cluster and task definition
    - Implement `cdk_app/stacks/compute_stack.py`
    - Create ECS cluster with container insights enabled
    - Define Fargate task definition: 1 vCPU, 2 GB memory
    - Configure EFS volume mount at /app/logs
    - Set container stop timeout to 30 seconds for graceful SIGTERM draining
    - Configure container health check: GET /health, interval 10s, retries 3
    - Inject secrets via `valueFrom` (Secrets Manager ARN references)
    - Inject parameters as plaintext environment variables from Parameter Store
    - Configure container to run as non-root user "appuser" with read-only root filesystem
    - _Requirements: 1.2, 1.3, 1.5, 1.6, 3.6, 8.3_

  - [ ] 6.2 Create ECS Fargate service with deployment configuration
    - Configure desired count of 2, spread placement strategy across AZs
    - Enable deployment circuit breaker with automatic rollback
    - Set deployment min healthy percent to 100%, max percent to 200%
    - Assign ECS security group, place in private subnets with no public IP
    - _Requirements: 1.1, 1.3, 1.4, 2.2, 9.3, 10.1, 10.6_

  - [ ]* 6.3 Write CDK template assertion tests for ComputeStack
    - Test task definition has CPU=1024, Memory=2048
    - Test EFS volume mount configuration at /app/logs
    - Test `AssignPublicIp: DISABLED` in network configuration
    - Test container stop timeout is 30 seconds
    - Test deployment circuit breaker is enabled with rollback
    - Test spread placement strategy across AZs
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 2.2, 10.1_

- [ ] 7. Implement LoadBalancerStack
  - [ ] 7.1 Create ALB with HTTPS listener and HTTP redirect
    - Implement `cdk_app/stacks/loadbalancer_stack.py`
    - Create internet-facing ALB in public subnets with ALB security group
    - Configure HTTPS listener on port 443 with ACM certificate
    - Configure HTTP listener on port 80 with 301 redirect to HTTPS
    - Create target group on port 8080 with health check: /health, interval 30s, timeout 5s, healthy threshold 2, unhealthy threshold 3
    - Register ECS service as target
    - _Requirements: 2.3, 2.4, 2.6, 2.8, 10.2_

  - [ ]* 7.2 Write CDK template assertion tests for LoadBalancerStack
    - Test HTTPS listener on port 443
    - Test HTTP redirect action returns 301
    - Test target group health check configuration
    - Test ALB is internet-facing in public subnets
    - _Requirements: 2.3, 2.4, 2.6_

- [ ] 8. Implement MonitoringStack
  - [ ] 8.1 Create CloudWatch log groups, alarms, and SNS topic
    - Implement `cdk_app/stacks/monitoring_stack.py`
    - Create CloudWatch Log Group with 30-day retention
    - Create SNS topic for operations notifications
    - Create alarm: healthy task count < 2 for 2 periods of 60s
    - Create alarm: ALB p95 response time > 5s for 3 periods of 60s
    - Create alarm: metrics scrape failure for 3 consecutive intervals
    - Configure alarm actions to notify SNS topic on state transitions (ALARM and OK)
    - _Requirements: 5.1, 5.3, 5.4, 5.7, 5.8_

  - [ ] 8.2 Create CloudWatch dashboard
    - Create dashboard with widgets: webhook request rate, playbook execution success/failure counts, active pipeline count, task health status
    - Set default time window to 3 hours with 60-second auto-refresh
    - Define custom metric namespace for PlaybookExecutionFailure (dimensions: alert_name, target_host)
    - _Requirements: 5.5, 5.6_

  - [ ]* 8.3 Write CDK template assertion tests for MonitoringStack
    - Test log group retention is 30 days
    - Test alarm thresholds and evaluation periods match requirements
    - Test SNS topic exists with alarm actions configured
    - Test dashboard widget configuration
    - _Requirements: 5.1, 5.3, 5.4, 5.5_

- [ ] 9. Implement AutoScalingStack
  - [ ] 9.1 Create asymmetric auto-scaling policies
    - Implement `cdk_app/stacks/autoscaling_stack.py`
    - Configure scalable target: min capacity 2, max capacity 10
    - Scale-out policy: CPU > 60% for 3 consecutive 60s periods → add 2 tasks, 120s cooldown
    - Scale-in policy: CPU < 30% for 10 consecutive 60s periods → remove 1 task, 120s cooldown
    - Enforce independent cooldowns for scale-out and scale-in directions
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 9.2 Write CDK template assertion tests for AutoScalingStack
    - Test min/max capacity bounds (2, 10)
    - Test scale-out threshold (60%), periods (3), adjustment (+2), cooldown (120s)
    - Test scale-in threshold (30%), periods (10), adjustment (-1), cooldown (120s)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 10. Checkpoint - Ensure core infrastructure stacks pass all tests
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement PrometheusStack
  - [ ] 11.1 Create Prometheus and Alertmanager ECS services
    - Implement `cdk_app/stacks/prometheus_stack.py`
    - Create Prometheus task definition: 0.5 vCPU, 1 GB, EFS/EBS volume for TSDB (50 GB, 15-day retention)
    - Create Alertmanager task definition: 0.25 vCPU, 0.5 GB
    - Configure Prometheus to scrape self-healing /metrics and Alertmanager /metrics at 15s interval
    - Configure Alertmanager webhook receiver URL pointing to ALB endpoint
    - Set health checks: Prometheus /-/healthy on 9090, Alertmanager /-/healthy on 9093 (interval 30s, unhealthy threshold 3)
    - Apply Prometheus and Alertmanager security groups
    - _Requirements: 11.1, 11.2, 11.3, 11.6, 11.7, 11.8_

  - [ ]* 11.2 Write CDK template assertion tests for PrometheusStack
    - Test Prometheus task definition (0.5 vCPU, 1 GB, storage volume)
    - Test Alertmanager task definition (0.25 vCPU, 0.5 GB)
    - Test health check configuration for both services
    - Test security group rules for Prometheus and Alertmanager
    - _Requirements: 11.1, 11.2, 11.3, 11.7_

- [ ] 12. Implement PipelineStack
  - [ ] 12.1 Create CI/CD pipeline with build, deploy, and rollback stages
    - Implement `cdk_app/stacks/pipeline_stack.py`
    - Source stage: trigger on push to main branch
    - Build stage: Docker build, run unit tests and CDK assertion tests (15 min timeout)
    - Push stage: tag image with git commit SHA, push to ECR
    - Deploy stage: rolling update to ECS service (min healthy 100%, max 200%)
    - Smoke test stage: POST /webhook, verify 200 within 10s (3 retries, 5s interval)
    - Rollback: on health check failure (3 consecutive) within 5 min or smoke test failure
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 12.2 Write CDK template assertion tests for PipelineStack
    - Test pipeline has source, build, deploy, and smoke test stages
    - Test build stage timeout is 15 minutes
    - Test deployment configuration (min healthy 100%, max 200%)
    - _Requirements: 9.1, 9.3_

- [ ] 13. Implement reusable constructs
  - [ ] 13.1 Create FargateService and SecureEFS reusable constructs
    - Implement `cdk_app/constructs/fargate_service.py` — reusable L3 construct wrapping task definition, service, and security group assignment
    - Implement `cdk_app/constructs/secure_efs.py` — reusable construct wrapping EFS with encryption, lifecycle, and mount target configuration
    - Use these constructs in ComputeStack, StorageStack, and PrometheusStack to reduce duplication
    - _Requirements: 1.1, 7.1, 7.2, 7.3_

- [ ] 14. Write integration test suite
  - [ ]* 14.1 Write integration tests for deployed infrastructure
    - Create `tests/integration/test_deployment.py`
    - Test ALB health check returns 200
    - Test webhook endpoint accepts payload and returns 200
    - Test HTTP→HTTPS redirect returns 301
    - Test ECS service maintains minimum 2 running tasks
    - Test EFS mount is writable from ECS task
    - Test secrets are injected at runtime via container environment
    - _Requirements: 2.3, 2.4, 2.6, 1.1, 7.1, 8.3_

  - [ ]* 14.2 Write smoke test script for post-deployment validation
    - Create `tests/smoke/test_smoke.py`
    - Test synthetic webhook delivery returns 200 within 10s
    - Test /health endpoint returns 200
    - Test /metrics endpoint returns Prometheus text format
    - _Requirements: 9.5, 5.2_

- [ ] 15. Final checkpoint - Ensure all stacks synthesize and tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation of CDK synthesis
- This is IaC — testing uses CDK template assertions and compliance checks, NOT property-based testing
- The design uses Python (AWS CDK) throughout; all code examples and implementations use Python
- Cross-stack references are passed via constructor parameters, not CloudFormation exports
- cdk-nag can be integrated for additional compliance rule checking

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "3.3"] },
    { "id": 3, "tasks": ["2.2", "3.1", "3.2"] },
    { "id": 4, "tasks": ["3.4", "4.1", "4.2"] },
    { "id": 5, "tasks": ["4.3", "6.1"] },
    { "id": 6, "tasks": ["6.2", "13.1"] },
    { "id": 7, "tasks": ["6.3", "7.1"] },
    { "id": 8, "tasks": ["7.2", "8.1"] },
    { "id": 9, "tasks": ["8.2", "8.3", "9.1"] },
    { "id": 10, "tasks": ["9.2", "11.1"] },
    { "id": 11, "tasks": ["11.2", "12.1"] },
    { "id": 12, "tasks": ["12.2", "14.1"] },
    { "id": 13, "tasks": ["14.2"] }
  ]
}
```
