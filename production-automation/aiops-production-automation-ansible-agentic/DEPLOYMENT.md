# AIOps Self-Healing Infrastructure — Deployment Guide

## Overview

This guide covers deploying, testing, and tearing down the AIOps Self-Healing Infrastructure on AWS. The system automatically detects infrastructure issues via Prometheus alerts and resolves them through AI-powered or rule-based remediation — with human-in-the-loop approval via email.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          AWS Account                                 │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │ NetworkStack │   │  DataStack   │   │     ComputeStack       │  │
│  │              │   │              │   │                          │  │
│  │ VPC          │   │ DynamoDB     │   │ ECS Fargate Service     │  │
│  │ 2 AZs       │   │ SQS + DLQ   │   │ ┌────────────────────┐  │  │
│  │ NAT Gateway  │   │ ECR Repo    │   │ │ Self-Healing App   │  │  │
│  │ VPC Endpoints│   │             │   │ │ :8080              │  │  │
│  └──────────────┘   └──────────────┘   │ └────────────────────┘  │  │
│                                         │ IAM Roles (least-priv)  │  │
│  ┌──────────────────┐                  │ Auto-scaling (SQS depth)│  │
│  │ MonitoringStack   │                  └────────────────────────┘  │
│  │                   │                                               │
│  │ AMP Workspace     │   ┌────────────────────────┐                 │
│  │ ADOT Collector    │   │  ObservabilityStack     │                 │
│  │ Alertmanager      │   │                          │                 │
│  │   ↓ webhook       │   │ CloudWatch Alarms        │                 │
│  │   → Self-Healing  │   │ CloudWatch Dashboard     │                 │
│  └──────────────────┘   │ Synthetics Canary         │                 │
│                          │ AWS Budgets               │                 │
│                          └────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | v2+ | https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html |
| Node.js | 20+ | https://nodejs.org |
| Python | 3.11+ | https://python.org |
| Docker | 24+ | https://docs.docker.com/get-docker |
| pip | Latest | Comes with Python |

## Quick Start

```bash
# Clone and enter the project
cd aiops-production-automation-ansible-agentic

# Configure AWS credentials
aws configure
# OR
aws sso login --profile your-profile

# Deploy (handles everything: bootstrap, docker build, CDK deploy)
python deploy.py

# After deployment — run a test
python demo/trigger_scenario.py --scenario inject --alert-name HighCPUUsage --severity critical

# When done — tear it all down
python destroy.py
```

---

## Detailed Deployment

### Step 1: Configure AWS Credentials

```bash
# Option A: Access keys
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output (json)

# Option B: SSO
aws sso login

# Verify
aws sts get-caller-identity
```

### Step 2: Deploy

```bash
python deploy.py
```

The script performs these steps automatically:

| Step | Action | Duration |
|------|--------|----------|
| 1 | Check prerequisites (CLI tools, credentials) | 5s |
| 2 | Install Python dependencies | 30s |
| 3 | Bootstrap CDK (creates staging bucket + roles) | 60s |
| 4 | Verify SES email identity | 30s |
| 5 | Build Docker image + push to ECR | 2-5 min |
| 6 | Deploy 5 CDK stacks | 5-10 min |
| 7 | Health check verification | 10s |

**Total: ~10-15 minutes**

### Deploy Options

```bash
# Deploy to a specific environment
python deploy.py --environment dev          # Default
python deploy.py --environment staging
python deploy.py --environment prod

# Skip Docker build (use existing image in ECR)
python deploy.py --skip-docker

# Skip CDK bootstrap (already done previously)
python deploy.py --skip-bootstrap
```

### Step 3: Verify SES Email

During deployment, you'll receive a verification email at `ravindya@in.ibm.com`. **You must click the verification link** for the system to send approval emails.

---

## Testing the Deployment

### Test 1: Health Check

```bash
# Check CloudWatch logs for the service starting
aws logs tail /aiops/dev/ecs --follow --region us-east-1

# Get the running task ID
TASK_ID=$(aws ecs list-tasks --cluster aiops-cluster-dev --query 'taskArns[0]' --output text --region us-east-1)

# Check health endpoint via ECS Exec
aws ecs execute-command --cluster aiops-cluster-dev \
  --task $TASK_ID --container AiopsContainer \
  --interactive --command "curl -s http://localhost:8080/health"
```

### Test 2: Inject a Test Alert

```bash
python demo/trigger_scenario.py --scenario inject \
  --alert-name HighCPUUsage --severity critical
```

This sends an Alertmanager-format webhook directly to the service. You should see:
- Pipeline processing in CloudWatch logs
- Approval email in your inbox (if SES verified)
- Metrics incrementing in the CloudWatch Dashboard

### Test 3: Full Pipeline (Alert → Email → Click → Remediate)

```bash
# 1. Inject alert
python demo/trigger_scenario.py --scenario inject \
  --alert-name ServiceDown --severity critical

# 2. Check your email — you'll get an RCA email with "Approve" button

# 3. Click the approval link in the email

# 4. Watch remediation execute
aws logs tail /aiops/dev/ecs --follow --region us-east-1

# 5. Check metrics
# Open: https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AIOps-dev
```

### Test 4: Verify Alertmanager Integration

If the MonitoringStack is deployed, Prometheus + Alertmanager are running as ECS sidecars. They scrape the `/metrics` endpoint and fire alerts based on configured rules.

```bash
# Check if monitoring service is running
aws ecs list-tasks --cluster aiops-cluster-dev \
  --service-name aiops-monitoring-dev --region us-east-1
```

---

## Monitoring & Observability

### CloudWatch Dashboard

Open in browser:
```
https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=AIOps-dev
```

Shows:
- ECS task count (running vs desired)
- SQS queue depth
- AI reasoning latency (p50/p95/p99)
- Remediation success/failure rates
- DLQ depth

### CloudWatch Logs

```bash
# Application logs
aws logs tail /aiops/dev/ecs --follow --region us-east-1

# Monitoring sidecar logs
aws logs tail /aiops/dev/monitoring --follow --region us-east-1
```

### CloudWatch Alarms

Configured alerts (staging/prod only):
- DLQ depth > 5 messages
- AI latency p95 > 15s
- Remediation failure rate > 30%
- ECS unhealthy tasks > 0
- Composite: Rollback required

---

## Notification Flow

```
Alert fires
    │
    ▼
Pipeline matches playbook
    │
    ▼
Email sent to ravindya@in.ibm.com
┌─────────────────────────────────────┐
│ 🚨 Alert: HighCPUUsage              │
│ Host: web-server-01                  │
│                                      │
│ Root Cause: CPU > 90% for 5 min      │
│ Proposed: Restart web-frontend       │
│                                      │
│ ┌─────────────────────────────────┐  │
│ │   ✅ Approve Auto-Remediation   │  │
│ └─────────────────────────────────┘  │
│                                      │
│ ⏰ Expires in 30 minutes             │
└─────────────────────────────────────┘
    │
    ├─── Operator clicks ──→ Agent executes fix ──→ Success email
    │
    └─── Not clicked ──→ Expiry email ──→ Operator fixes manually
```

---

## Destroy / Cleanup

```bash
# Destroy dev environment
python destroy.py

# Destroy with ECR cleanup (removes all Docker images too)
python destroy.py --include-ecr

# Destroy staging
python destroy.py --environment staging

# Destroy prod (requires typing "prod" + "DESTROY" to confirm)
python destroy.py --environment prod

# Skip confirmation (not for prod)
python destroy.py -y
```

### What Gets Deleted

| Resource | Deleted? |
|----------|----------|
| ECS Cluster + Service | ✅ |
| VPC + Subnets + NAT GW | ✅ |
| DynamoDB Table | ✅ |
| SQS Queues | ✅ |
| AMP Workspace | ✅ |
| CloudWatch Alarms + Dashboard | ✅ |
| IAM Roles | ✅ |
| SSM Parameters | ✅ |
| ECR Repository | Only with `--include-ecr` |
| CDK Bootstrap (CDKToolkit) | ❌ (shared, manual removal) |
| SES Email Verification | ❌ (harmless, no cost) |

---

## Cost Estimate

| Environment | Monthly Cost |
|-------------|-------------|
| **dev** (FARGATE_SPOT, 1 task) | ~$50 |
| **staging** (FARGATE, 1-3 tasks) | ~$120 |
| **prod** (FARGATE, 1-10 tasks) | ~$200-400 |

Main cost drivers: NAT Gateway (~$32), ECS Fargate (~$8-80), AMP (~$5-20).

**Tip:** Destroy dev when not testing to avoid costs:
```bash
python destroy.py -y
```

---

## Troubleshooting

### Deploy fails at CDK synth

```bash
# Check CDK context is valid
npx aws-cdk@2 synth --all --context environment=dev 2>&1 | head -50
```

### ECS task keeps restarting

```bash
# Check task stopped reason
aws ecs describe-tasks --cluster aiops-cluster-dev \
  --tasks $(aws ecs list-tasks --cluster aiops-cluster-dev --query 'taskArns[0]' --output text) \
  --query 'tasks[0].stoppedReason' --output text --region us-east-1
```

### Emails not arriving

1. Check SES verification: `aws ses get-identity-verification-attributes --identities ravindya@in.ibm.com`
2. Check SES sending quota: `aws ses get-send-quota`
3. Check spam folder
4. SES may be in sandbox mode — request production access if needed

### Docker build fails

```bash
# Build manually to see errors
docker build -t aiops:test .
```

### Permission denied during deploy

Ensure your IAM user/role has:
- `AdministratorAccess` (for initial setup), OR
- CloudFormation, ECS, EC2, IAM, SQS, DynamoDB, ECR, CloudWatch, APS, SES permissions

---

## Project Structure

```
├── deploy.py              ← Deploy to AWS (run this)
├── destroy.py             ← Tear down from AWS
├── cdk.json               ← CDK configuration (account, region, etc.)
├── Dockerfile             ← Container image definition
├── pyproject.toml         ← Python dependencies (pinned)
├── requirements.lock      ← Locked transitive dependencies
│
├── src/
│   ├── app.py             ← FastAPI application (webhook, health, approve)
│   ├── orchestrator.py    ← Pipeline: normalize → enrich → match → execute
│   ├── approval_handler.py ← Token-based approval for email links
│   ├── email_notifier.py  ← SES email with RCA + approval button
│   ├── guardrails/        ← 7-layer safety engine
│   ├── concurrency/       ← Host locking, deduplication, circuit breaker
│   └── agentic_ai/
│       └── infra/         ← CDK stacks (Network, Data, Compute, Observability, Monitoring)
│
├── config/                ← Playbook mapping, asset inventory, guardrail configs
├── playbooks/             ← Ansible playbooks for remediation
├── monitoring/            ← Prometheus, Alertmanager, Grafana configs
├── runbooks/              ← Operational runbooks (8 guides)
├── demo/                  ← Demo trigger scripts + target host simulator
└── tests/                 ← Unit, property, integration, CDK tests
```
