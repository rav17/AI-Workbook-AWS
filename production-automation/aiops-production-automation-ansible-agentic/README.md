# AIOps Self-Healing Infrastructure

An automated self-healing infrastructure platform that detects issues via CloudWatch alarms, processes them through a multi-stage pipeline, and resolves them with human-in-the-loop approval via email.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│ EC2 Target Instance                                                      │
│ (stress-ng running → CPU > 80%)                                         │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ CloudWatch detects
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CloudWatch Alarm → SNS → Lambda                                          │
│ (sends Alertmanager webhook to self-healing service)                     │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ POST /webhook
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ECS Fargate: Self-Healing Service                                        │
│                                                                          │
│ Pipeline: normalize → enrich → match playbook                           │
│                                                                          │
│ ┌─────────────────────────────┐  ┌────────────────────────────────────┐ │
│ │ RULE MODE (playbook found)  │  │ AI MODE (no playbook)              │ │
│ │ → Email with Approve button │  │ → Bedrock Nova Pro analyzes        │ │
│ │ → Click = auto-remediation  │  │ → Email with suggested steps       │ │
│ └─────────────────────────────┘  └────────────────────────────────────┘ │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ Operator clicks Approve
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Ansible executes fix_high_cpu.yml on EC2 via SSM                         │
│ (kills stress-ng → CPU drops → alert resolves)                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Two Operating Modes

| Mode | When | Email Content | Action |
|------|------|---------------|--------|
| **Rule Mode** | Matching playbook exists | RCA + "Approve Auto-Remediation" button | Click → agent executes fix |
| **AI Agent Mode** | No playbook match | AI analysis + suggested steps | Operator fixes manually |

## Quick Start

See [DEMO-GUIDE.md](DEMO-GUIDE.md) for full deployment and testing instructions.

```bash
# Deploy to AWS
npx aws-cdk@2 deploy --all --context environment=dev --context imageTag=v9-dev --require-approval never

# Test Rule Mode (has playbook → email with approve button)
python demo/break_target.py --mode cpu --duration 600

# Test AI Mode (no playbook → AI suggests steps)
aws lambda invoke --function-name aiops-network-alert-dev --cli-binary-format raw-in-base64-out --payload "{}" --region us-east-1 output.json

# Destroy
npx aws-cdk@2 destroy --all --context environment=dev --force
```

## AWS Architecture

| Stack | Resources |
|-------|-----------|
| **Aiops-dev-Network** | VPC, 2 AZs, NAT Gateway, VPC Endpoints, Security Groups |
| **Aiops-dev-Data** | DynamoDB, SQS + DLQ, ECR Repository |
| **Aiops-dev-Compute** | ECS Fargate, IAM Roles, API Gateway, Cloud Map, Secrets Manager, SSM Parameters |
| **Aiops-dev-Observability** | SNS, CloudWatch Alarms, Budget Alerts |
| **Aiops-dev-Simulation** | EC2 target instance, CloudWatch CPU/Network Alarms, Alert trigger Lambdas |

## Project Structure

```
├── deploy.py / destroy.py     ← Deploy/teardown scripts
├── cdk.json                   ← CDK configuration (account, region, model)
├── Dockerfile                 ← Container image (Python + Ansible)
├── requirements.lock          ← Pinned dependencies
│
├── src/
│   ├── app.py                 ← FastAPI: /webhook, /health, /approve/{token}
│   ├── orchestrator.py        ← Pipeline: normalize → enrich → match → execute
│   ├── approval_handler.py    ← Token-based approval for email links
│   ├── email_notifier.py      ← SES emails with RCA + approval button
│   ├── normalizer.py          ← Alertmanager payload → internal format
│   ├── enricher.py            ← Asset inventory lookup
│   ├── playbook_mapper.py     ← YAML rule → playbook matching
│   ├── executor.py            ← Ansible playbook execution
│   ├── guardrails/            ← 7-layer safety engine
│   ├── concurrency/           ← Host locking, deduplication, circuit breaker
│   └── agentic_ai/
│       ├── agents/reasoning_agent.py  ← Bedrock AI (Nova Pro/Claude) with fallback
│       └── infra/stacks/      ← CDK stacks
│
├── config/
│   ├── playbook_mapping.yml   ← Alert → playbook rules
│   ├── asset_inventory.yml    ← Host metadata
│   ├── protected_hosts.yml    ← Hosts never targeted by automation
│   └── risk_classification.yml
│
├── playbooks/
│   ├── fix_high_cpu.yml       ← Kills stress-ng, restarts app
│   ├── restart_service.yml    ← Restarts systemd service
│   └── clear_disk.yml         ← Removes old logs
│
├── demo/
│   ├── break_target.py        ← Trigger CPU/network stress on EC2
│   └── trigger_aws.py         ← Send alerts via SQS
│
├── monitoring/                ← Prometheus, Alertmanager, Grafana (local dev)
├── runbooks/                  ← 8 operational guides
├── tests/                     ← Unit, property, integration, CDK tests
├── DEMO-GUIDE.md             ← Step-by-step demo instructions
└── DEPLOYMENT.md             ← Full deployment reference
```

## Key Decisions

- **Email instead of Slack** — Approval links are clickable in any email client
- **Human-in-the-loop** — No auto-execution without operator approval (for HIGH/CRITICAL risk)
- **AI fallback chain** — Tries Nova Pro → Claude Sonnet → Claude Haiku → Nova Lite
- **Graceful degradation** — If AI unavailable, sends generic suggestions
- **SSM for remediation** — No SSH keys needed, works with EC2 instances in private subnets
- **CloudWatch for alerting** — Native AWS, no external Prometheus required for basic scenarios
