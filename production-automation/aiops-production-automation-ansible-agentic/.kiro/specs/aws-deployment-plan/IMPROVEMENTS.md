# AWS Deployment Plan — Improvement Proposals

## Document Information

| Field | Value |
|-------|-------|
| **Author** | Ravindra Yadav |
| **Date** | August 2026 |
| **Status** | Proposed |
| **Spec** | `.kiro/specs/aws-deployment-plan` |
| **Informed By** | AWS ECS Canary/Linear Deployments, CDK Drift Detection, CloudFormation Drift-Aware Change Sets, GitHub Actions OIDC Multi-Account, AWS Graviton Fargate, AWS WAF API Protection, AWS Well-Architected Cost Optimization Pillar, SOC 2 Compliant CI/CD Patterns |

---

## Executive Summary

The aws-deployment-plan spec covers Docker/ECR publishing, 4 CDK stacks, CI/CD
pipelines, configuration management, 3-tier environments, health gates, rollback,
and operational runbooks. These are well-implemented. The improvements below address
production-scale gaps: safer deployments (canary/linear), cost optimization (Graviton),
security hardening (WAF), and operational excellence (drift detection).

---

## Current Strengths (Already Well-Implemented)

- ✅ 4 layered CDK stacks (Network → Data → Compute → Observability)
- ✅ GitHub Actions CI/CD with OIDC authentication (no long-lived keys)
- ✅ ECR image scanning with vulnerability gate
- ✅ Health gate (3 consecutive HTTP 200 before proceeding)
- ✅ Deployment manifest rotation (5 history slots in SSM)
- ✅ Automated rollback on health gate failure
- ✅ 3-tier environment strategy (dev/staging/prod)
- ✅ Prod manual approval with 4-hour timeout
- ✅ SSM Parameter Store + Secrets Manager configuration
- ✅ Operational runbooks (8 documents)
- ✅ CloudWatch alarms + SNS notifications
- ✅ Budget alerts at 80%/100%

---

## Improvement 1: ECS Canary/Linear Deployments (Replace Rolling Update)

### Priority: P1 — Safer Production Deployments

### Problem Statement

The current deployment uses ECS rolling update (min 100%, max 200%). This replaces
ALL tasks with the new version simultaneously. If the new version has a bug that only
manifests under real traffic (not caught by health check), ALL tasks are affected
before the issue is detected. The health gate checks AFTER full rollout.

### AWS Feature

[ECS Canary and Linear Deployments](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/canary-deployment.html):
- **Canary**: Route 10% of traffic to new version, monitor for 5 minutes, then shift 100%
- **Linear**: Shift traffic in 10% increments every 5 minutes until 100%
- **Auto-rollback**: If CloudWatch alarm fires during shift, automatically revert

### Proposed Improvement

```
Production deployment strategy:
  Stage 1: Deploy canary task (1 task with new version) → 10% traffic
  Stage 2: Monitor for 5 minutes (baking period)
    - Check: error rate < 5%, latency p95 < 15s, no DLQ spike
  Stage 3: If healthy → shift to 50% traffic, monitor 3 more minutes
  Stage 4: If healthy → shift to 100% traffic (full rollout)
  On any alarm → automatic rollback to previous version (zero manual action)

Dev/Staging: Keep rolling update (faster iteration)
Prod: Canary with 10% → 50% → 100% traffic shift
```

### Acceptance Criteria

1. Prod deployments SHALL use CodeDeploy blue/green or ECS native canary deployment
2. Canary SHALL receive 10% traffic for configurable baking period (default 5 min)
3. Auto-rollback SHALL trigger if any alarm fires during canary window
4. Dev/staging SHALL continue using rolling update for speed
5. Deployment duration SHALL be visible in CloudWatch as custom metric

### Effort Estimate: 3-5 days (CDK changes + CodeDeploy setup)

---

## Improvement 2: AWS Graviton (ARM) for 40% Cost Savings

### Priority: P1 — Immediate Cost Reduction

### Problem Statement

The current ECS task definition uses x86_64 (Intel/AMD) architecture. The application
is Python + Ansible — both are fully compatible with ARM64. AWS Graviton processors
provide up to 40% better price-performance for Fargate tasks.

### AWS Feature

[ECS Fargate with Graviton2](https://docs.aws.amazon.com/prescriptive-guidance/latest/optimize-costs-microsoft-workloads/net-graviton.html):
"You can achieve up to 45 percent savings when you switch to Graviton."
Graviton Fargate costs 20% less per vCPU-hour AND delivers 20% more performance.

### Proposed Improvement

```
Changes needed:
1. Dockerfile: build for linux/arm64 (multi-arch with BuildX)
2. CDK ComputeStack: set runtimePlatform to ARM64
3. ECR: store multi-arch manifest (supports both x86 and arm64)
4. CI pipeline: build with --platform linux/arm64

No application code changes needed (Python + Ansible are arch-independent).

task_definition:
  runtime_platform:
    cpu_architecture: ARM64
    operating_system_family: LINUX
```

### Cost Impact

| Config | Monthly Cost (1 task 24/7) | With Graviton |
|--------|---------------------------|---------------|
| 0.5 vCPU, 1 GB | ~$14.57/month (x86) | ~$11.66/month (ARM64) |
| Saving per task | — | $2.91/month (20% less) |
| 10 tasks at peak | ~$145.70/month | ~$116.60/month |

### Acceptance Criteria

1. THE Dockerfile SHALL produce a multi-architecture image (amd64 + arm64)
2. THE ComputeStack SHALL set `runtimePlatform` to ARM64 for staging and prod
3. Dev MAY remain on x86 for faster local testing (optional)
4. THE CI pipeline SHALL build arm64 images using Docker BuildX
5. THE ECR repository SHALL store a multi-arch manifest

### Effort Estimate: 1-2 days

---

## Improvement 3: Infrastructure Drift Detection

### Priority: P2 — Catches Manual Changes

### Problem Statement

If someone modifies a security group, IAM policy, or DynamoDB setting via the AWS
Console (bypassing CDK), the deployed state silently diverges from the code. The next
CDK deploy might fail unexpectedly or revert important manual fixes.

### AWS Feature

[CDK Drift Command](https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-drift.html):
"Use `cdk drift` when you need to verify if resources have been modified outside
of CloudFormation."

[CloudFormation Drift-Aware Change Sets](https://aws.amazon.com/about-aws/whats-new/2025/11/configuration-drift-enhanced-cloudformation-sets):
Safely handle drift by creating change sets that account for out-of-band changes.

### Proposed Improvement

```
Add automated drift detection to the CD pipeline:

Schedule: Run daily (cron) + before every prod deployment
Command: cdk drift --all --context environment=prod

Results:
- If NO drift → log "infrastructure in sync" and proceed
- If DRIFT DETECTED:
  a. Publish drift report as pipeline artifact
  b. Send Slack notification: "Drift detected in {stack}: {resources}"
  c. For prod deployments: HALT deployment until drift is resolved
  d. For dev/staging: log warning but proceed

CDK Drift Report → stored in S3 for audit trail (90 days retention)
```

### Acceptance Criteria

1. THE CD pipeline SHALL run `cdk drift` before prod deployments
2. IF drift is detected in prod, THE pipeline SHALL halt and notify
3. Drift reports SHALL be stored as artifacts for 90 days
4. A daily scheduled workflow SHALL check for drift across all environments
5. Drift detection SHALL NOT block dev/staging deployments (warning only)

### Effort Estimate: 1-2 days

---

## Improvement 4: AWS WAF on API Gateway (Webhook Security)

### Priority: P2 — Production Security Hardening

### Problem Statement

The API Gateway webhook endpoint is exposed to the internet (receives Alertmanager
webhooks). It currently relies only on API key authentication. Without WAF, the
endpoint is vulnerable to:
- HTTP request floods (DDoS)
- Malicious payload injection attempts
- Bot traffic consuming API Gateway quotas

### AWS Feature

[AWS WAF with API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html):
Rate-based rules automatically block IPs exceeding request thresholds.

### Proposed Improvement

```
Add WAF WebACL to the API Gateway stage:

Rules:
1. Rate limit: Max 100 requests/5 minutes per IP (Alertmanager sends bursts, not floods)
2. Size constraint: Block requests > 1 MB (matches application validation)
3. IP allowlist (optional): Only allow Alertmanager source IPs
4. AWS Managed Rule Group: AWSManagedRulesCommonRuleSet (XSS, SQLi protection)
5. Geographic restriction (optional): Block non-expected regions

CDK addition to ObservabilityStack:
  const waf = new wafv2.CfnWebACL(this, 'AiopsWaf', {
    scope: 'REGIONAL',
    rules: [rateLimit, sizeLimit, managedRules],
  });
```

### Acceptance Criteria

1. THE CDK stack SHALL create a WAF WebACL attached to the API Gateway stage
2. Rate limiting SHALL block IPs exceeding 100 requests per 5 minutes
3. THE WAF SHALL log all blocked requests to CloudWatch for audit
4. THE WAF SHALL NOT block legitimate Alertmanager traffic patterns
5. WAF metrics SHALL be visible on the CloudWatch dashboard

### Effort Estimate: 1-2 days

---

## Improvement 5: Multi-Account Deployment with Role Chaining

### Priority: P2 — Blast Radius Isolation

### Problem Statement

The current spec supports cross-account deployment via CDK context (`awsAccount`),
but the OIDC trust policy and IAM roles are not fully documented for the multi-account
pattern. In practice, prod should be in a SEPARATE AWS account for blast radius isolation.

### AWS Pattern

[GitHub Actions Multi-Account OIDC Role Chaining](https://nerdleveltech.com/github-actions-multi-account-aws-oidc-role-chaining-tutorial):
Hub-and-spoke pattern — one OIDC-trusted role in a "hub" account, deploy roles
per workload account, role-chaining via `aws-actions/configure-aws-credentials`.

### Proposed Improvement

```
Account structure:
  - DevOps Account (hub): GitHub OIDC provider + CI role
  - Dev Account: dev resources (CDK deploys via cross-account role)
  - Prod Account: prod resources (separate blast radius)

Role chain:
  GitHub → OIDC → DevOps CI Role → AssumeRole → Dev Deploy Role
  GitHub → OIDC → DevOps CI Role → AssumeRole → Prod Deploy Role

CDK changes:
  - Add cross-account deploy role ARN to CDK context per environment
  - CI/CD workflow uses role-chaining: true in configure-aws-credentials
  - Prod account has tighter IAM boundaries (no delete permissions)
```

### Acceptance Criteria

1. THE CDK context SHALL support `deployRoleArn` per environment
2. THE CD workflow SHALL use role chaining for cross-account deployment
3. Prod deploy role SHALL NOT have CloudFormation delete permissions
4. Each environment SHALL be deployable to an independent AWS account
5. THE documentation SHALL include IAM trust policy templates

### Effort Estimate: 2-3 days

---

## Improvement 6: Container Image SBOM and Signing

### Priority: P3 — Supply Chain Security

### Problem Statement

The current pipeline scans images for vulnerabilities (ECR Enhanced Scanning) but
doesn't produce a Software Bill of Materials (SBOM) or sign the image. Without
signing, there's no guarantee that the deployed image is the one that was scanned
and approved.

### Proposed Improvement

```
Add to CI pipeline after Docker build:

1. SBOM generation: Use Syft to produce CycloneDX SBOM
   docker run anchore/syft:latest packages <image> -o cyclonedx-json > sbom.json

2. Image signing: Use cosign to sign with OIDC keyless signing
   cosign sign --yes <image-digest>

3. Signature verification in CD: Before deploying, verify signature
   cosign verify <image-digest>

4. SBOM attestation: Attach SBOM as in-toto attestation to image
   cosign attest --predicate sbom.json --type cyclonedx <image-digest>

Benefits:
- Tamper-proof guarantee that deployed image = scanned image
- SBOM enables vulnerability scanning against future CVE disclosures
- Meets SOC 2 / supply chain security compliance requirements
```

### Effort Estimate: 2 days

---

## Improvement 7: Deployment Observability Dashboard

### Priority: P3 — Operational Visibility

### Problem Statement

The current CloudWatch dashboard (`AIOps-{environment}`) focuses on runtime metrics
(queue depth, error rate, latency). There's no deployment-focused view showing:
deployment frequency, lead time, change failure rate, MTTR — the four DORA metrics.

### Proposed Improvement

```
Create a "Deployments" CloudWatch dashboard with:

1. Deployment frequency: count of successful deployments per week
2. Lead time: time from commit push to production deployment
3. Change failure rate: % of deployments triggering rollback
4. Mean time to recovery: time from failed deployment to successful rollback
5. Canary success rate: % of canary phases that pass without rollback
6. Health gate pass rate: % of deployments passing health gate on first attempt
7. Pipeline duration: CI + CD total time (p50/p95)

Data source: Custom CloudWatch metrics published by CD pipeline scripts
Stored in: SSM Parameter Store (deployment history already tracks this)
```

### Effort Estimate: 1-2 days

---

## Implementation Plan

### Phase 1: Cost & Safety (Week 1-2)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 1.1 | Multi-arch Dockerfile (ARM64 + x86) | `Dockerfile` | 0.5d |
| 1.2 | CDK ARM64 runtime platform for Fargate | `src/agentic_ai/infra/stacks/compute_stack.py` | 0.5d |
| 1.3 | CI BuildX for ARM64 | `.github/workflows/ci.yml` | 0.5d |
| 1.4 | ECS canary deployment config in CDK | `src/agentic_ai/infra/stacks/compute_stack.py` | 2d |
| 1.5 | Canary alarm-based auto-rollback | `src/agentic_ai/infra/stacks/observability_stack.py` | 1d |
| 1.6 | Update CD workflow for canary flow | `.github/workflows/cd.yml` | 1d |

**Deliverable:** 40% compute cost reduction + zero-impact prod deployments with auto-rollback.

### Phase 2: Security & Drift (Week 2-3)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 2.1 | Add WAF WebACL to CDK | `src/agentic_ai/infra/stacks/observability_stack.py` | 1d |
| 2.2 | WAF rules (rate limit, size, managed) | Same as above | 0.5d |
| 2.3 | Drift detection in CD pipeline | `.github/workflows/cd.yml` | 1d |
| 2.4 | Daily drift check scheduled workflow | `.github/workflows/drift-check.yml` | 0.5d |
| 2.5 | Multi-account role chaining setup | `.github/workflows/cd.yml`, CDK context | 2d |
| 2.6 | Cross-account IAM trust policy docs | `docs/multi-account-setup.md` | 0.5d |

**Deliverable:** Production endpoint hardened against attacks; manual drift caught before deployments.

### Phase 3: Supply Chain & Observability (Week 3-4)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 3.1 | SBOM generation (Syft) in CI | `.github/workflows/ci.yml` | 0.5d |
| 3.2 | Image signing (cosign) in CI | `.github/workflows/ci.yml` | 1d |
| 3.3 | Signature verification in CD | `.github/workflows/cd.yml` | 0.5d |
| 3.4 | DORA metrics collection in CD scripts | `scripts/publish_dora_metrics.py` | 1d |
| 3.5 | Deployments dashboard in CDK | `src/agentic_ai/infra/stacks/observability_stack.py` | 1d |

**Deliverable:** Signed images with SBOM; deployment health visibility via DORA metrics.

---

## Total Effort Summary

| Phase | Duration | Effort | Key Deliverable |
|-------|----------|--------|-----------------|
| Phase 1: Cost & Safety | Week 1-2 | 5.5 days | Graviton + canary deployments |
| Phase 2: Security & Drift | Week 2-3 | 5.5 days | WAF + drift detection + multi-account |
| Phase 3: Supply Chain | Week 3-4 | 4 days | SBOM + signing + DORA metrics |
| **Total** | **4 weeks** | **~15 days** | |

---

## References

- [ECS Canary Deployments](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/canary-deployment.html)
- [ECS CodeDeploy Linear/Canary](https://aws.amazon.com/blogs/containers/aws-codedeploy-now-supports-linear-and-canary-deployments-for-amazon-ecs)
- [AWS Graviton Fargate (40% savings)](https://docs.aws.amazon.com/prescriptive-guidance/latest/optimize-costs-microsoft-workloads/net-graviton.html)
- [CDK Drift Detection](https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-drift.html)
- [CloudFormation Drift-Aware Change Sets](https://aws.amazon.com/about-aws/whats-new/2025/11/configuration-drift-enhanced-cloudformation-sets)
- [AWS WAF API Gateway Protection](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-control-access-aws-waf.html)
- [GitHub Actions OIDC Multi-Account Role Chaining](https://nerdleveltech.com/github-actions-multi-account-aws-oidc-role-chaining-tutorial)
- [SOC 2 Compliant CI/CD on AWS](https://devops.com/building-soc-2-compliant-ci-cd-pipelines-on-aws-with-github-actions/)
- [Fargate Cost Optimization (Right-Sizing)](https://docs.aws.amazon.com/prescriptive-guidance/latest/optimize-costs-microsoft-workloads/optimizer-ecs-fargate.html)
- [AWS DDoS Resiliency Best Practices](https://docs.aws.amazon.com/whitepapers/latest/aws-best-practices-ddos-resiliency/protecting-api-endpoints-bp4.html)

---

## Future Improvements (Not for Current Implementation)

### Future: GitOps with ArgoCD/Flux for Infrastructure

Replace GitHub Actions CD with GitOps pattern where infrastructure state is
reconciled continuously from Git. Deferred because the current system is single-
region single-cluster and doesn't benefit from GitOps' multi-cluster strengths.

### Future: Ephemeral Preview Environments

Deploy a full isolated environment per PR for integration testing. Deferred due
to cost (each environment includes NAT Gateway, VPC endpoints, etc.) — would need
a "lite" stack variant first.

### Future: Feature Flags for Operating Mode

Replace the runtime mode-change API with a proper feature flag service (LaunchDarkly
or AWS AppConfig) that supports percentage rollouts, targeting rules, and kill switches.
Deferred until the number of configurable behaviors exceeds 5.
