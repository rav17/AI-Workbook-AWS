# AIOps Self-Healing Infrastructure — Technical Documentation

## Executive Summary

The AIOps Self-Healing Infrastructure is an enterprise-grade automated incident remediation platform that combines AWS-native monitoring, AI-powered reasoning (Amazon Bedrock), and Ansible-based execution to detect, analyze, and resolve production infrastructure issues with human-in-the-loop safety controls.

**Key Value Proposition:**
- Reduces Mean Time To Resolution (MTTR) from ~30 minutes (manual) to ~3 minutes (automated)
- 60-90% cost reduction on AI inference via intelligent model routing
- Zero-downtime remediation with 7-layer safety guardrails
- Full audit trail and observability for compliance

---

## 1. Architecture Overview

### 1.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ EC2 Target Instance (stress-ng → CPU > 80%)                             │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ CloudWatch detects anomaly
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CloudWatch Alarm → SNS → Lambda                                          │
│ (converts alarm to Alertmanager webhook format)                          │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ POST /webhook
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ECS Fargate: Self-Healing Service (FastAPI)                               │
│                                                                          │
│ Pipeline: normalize → enrich → match → guardrail → execute → notify     │
│                                                                          │
│ ┌──────────────────────────────┐  ┌─────────────────────────────────┐   │
│ │ RULE MODE (playbook found)   │  │ AI MODE (no playbook)           │   │
│ │ → Email: RCA + Approve btn   │  │ → Bedrock AI analyzes           │   │
│ │ → Click = auto-remediation   │  │ → Email: suggested steps        │   │
│ └──────────────────────────────┘  └─────────────────────────────────┘   │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ Operator clicks Approve
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Ansible executes fix_high_cpu.yml on EC2 via SSM                         │
│ (kills stress-ng → CPU drops → alert resolves)                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Two Operating Modes

| Mode | Trigger Condition | Email Content | Outcome |
|------|------------------|---------------|---------|
| **Rule Mode** | Matching playbook exists in `playbook_mapping.yml` | Root Cause Analysis + "Approve Auto-Remediation" button | Click → Ansible executes fix |
| **AI Agent Mode** | No playbook match found | AI-generated analysis + suggested remediation steps | Operator resolves manually |

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Compute** | ECS Fargate | Serverless container hosting |
| **Application** | Python 3.11, FastAPI, Uvicorn | Webhook receiver + pipeline |
| **AI/ML** | Amazon Bedrock (Nova Pro, Claude Sonnet) | Intelligent remediation reasoning |
| **Execution** | Ansible + AWS SSM | Agentless remediation on EC2 |
| **Data** | DynamoDB (PAY_PER_REQUEST) | Incident memory + approval persistence |
| **Messaging** | SQS + DLQ | Reliable alert processing |
| **Networking** | VPC + VPC Endpoints | Private connectivity, no internet transit |
| **Notifications** | Amazon SES | Email with approval links |
| **Observability** | CloudWatch, OpenTelemetry, X-Ray | Metrics, traces, alarms |
| **Infrastructure** | AWS CDK (Python) | Infrastructure as Code |
| **CI/CD** | GitHub Actions | Lint, test, build, deploy |

---

## 3. Pipeline Architecture (Detailed)

### 3.1 Alert Ingestion (POST /webhook)

1. **Rate Limiting** — 60 requests/minute per IP (slowapi)
2. **Payload Size Limit** — 1 MB maximum
3. **Content-Type Enforcement** — 415 for non-JSON
4. **Pydantic Validation** — Strict schema enforcement with descriptive errors
5. **Storm Detection** — Sliding-window rate tracking; groups alerts during storms
6. **Fleet Breaker Check** — Halts all automation if fleet-wide failure detected
7. **Alert Inhibition** — Suppresses symptom alerts when root cause is firing

### 3.2 Normalize Stage

- Extracts `alertname`, `severity`, `instance`, `service_name` from labels
- Maps severity to internal enum (P1-P5)
- Generates unique `incident_id` (UUID)
- Parses timestamps (ISO 8601)

### 3.3 Enrich Stage

- Looks up target host in Asset Inventory (`config/asset_inventory.yml`)
- Adds service owner, location, IP address, tags
- Marks `is_enriched=True` if asset found

### 3.4 Match Stage

- Evaluates rules from `config/playbook_mapping.yml` in priority order
- Matches on alert_name, service_name, severity combinations
- Returns `PlaybookMatch` with rule name and playbook path
- If no match → triggers AI Agent Mode

### 3.5 Guardrail Stage (7-Layer Safety Engine)

Evaluates remediation actions through ordered checks with short-circuit semantics:

| # | Check | Purpose |
|---|-------|---------|
| 1 | Self-Protection | Blocks targeting of aiops infrastructure itself |
| 2 | Maintenance Window | Defers during scheduled maintenance |
| 3 | Circuit Breaker | Blocks if host has too many recent failures |
| 4 | Concurrency Guard | Prevents concurrent remediations on same host |
| 5 | Blast Radius Classifier | Classifies risk (LOW/MEDIUM/HIGH/CRITICAL) |
| 6 | Health Checker | Verifies target host is reachable via SSM |
| 7 | Approval Gate | Requires human approval for HIGH/CRITICAL risk |
| 8 | Plan Validator | Blocks dangerous AI-generated commands |

Overall timeout: 15 seconds (DENY on timeout).

### 3.6 Execute Stage

- Ansible playbook execution via asyncio subprocess
- 300-second timeout with SIGTERM → SIGKILL after 5s
- Concurrency limit: 10 simultaneous executions (Semaphore)
- Output capture: 10,000 chars max per stream (stdout/stderr)
- Stop Conditions Monitor: watches CloudWatch alarms during execution

### 3.7 Baking Stage (Post-Execution Validation)

- Monitors alarm resolution after execution
- Validates host health (HTTP health checks)
- Determines if the fix was effective
- Records outcome in incident memory

### 3.8 Notify Stage

- Sends SES email with execution results
- Records audit trail (JSON Lines)
- Emits CloudWatch custom metrics
- Records in DynamoDB incident memory

---

## 4. AI/LLM Integration (Amazon Bedrock)

### 4.1 Model Router — Cost-Optimized Inference

| Complexity | Model | Cost/Invocation | Criteria |
|-----------|-------|-----------------|----------|
| SIMPLE | Amazon Nova Lite | ~$0.0003 | Seen 5+ times, >90% success rate, P3+ |
| MODERATE | Amazon Nova Pro | ~$0.001 | Limited history, mixed outcomes, P2 |
| COMPLEX | Claude Sonnet | ~$0.003 | Never seen, P1, all past failures |

**Auto-Escalation:** If confidence < 0.5, automatically re-invokes with next-tier model.

### 4.2 Prompt Engineering

- Structured prompts with stable prefix (cacheable) + variable suffix
- Includes: alert context, historical outcomes (up to 50), excluded actions (always-failed)
- Max input: configurable (default 4000 tokens via char heuristic)
- Max output: 2048 tokens
- Temperature: 0.2 (deterministic)

### 4.3 Fallback Chain

```
Claude Sonnet → Nova Pro → Claude Haiku → Nova Lite → Rule-Based (PlaybookMapper)
```

Each model gets: 30s timeout + 2 retries with exponential backoff (1s, 2s).

### 4.4 Safety Controls

- Bedrock Guardrails (native content filtering via `BEDROCK_GUARDRAIL_ID`)
- Plan Validator blocks dangerous commands from `config/denied_commands.yml`
- Confidence thresholds: 0.7 general, 0.8 for P1 alerts
- Truncation detection when response appears cut off

---

## 5. Infrastructure (AWS CDK Stacks)

### 5.1 Network Stack (`Aiops-dev-Network`)

- VPC: 10.0.0.0/16, 2 AZs
- Subnets: 2 public + 2 private
- NAT Gateway: 1 (dev/staging), 2 (prod)
- VPC Endpoints: DynamoDB, S3 (gateway), SQS, SSM, SSM Messages, Logs, Secrets Manager, Bedrock Runtime (interface)
- Security Groups: ECS tasks SG (443 outbound, 8080 self-referencing), VPC Endpoints SG (443 from ECS)

### 5.2 Data Stack (`Aiops-dev-Data`)

- **DynamoDB Table**: `AiopsIncidentMemory-{env}`, PAY_PER_REQUEST, TTL on `expiry_timestamp`
  - GSIs: AlertNameIndex, ServiceIndex, OutcomeIndex
  - PITR + AWS Backup (prod only)
- **SQS Main Queue**: `aiops-main-{env}`, 300s visibility, 14d retention
- **SQS DLQ**: `aiops-dlq-{env}`, maxReceiveCount=3
- **ECR Repository**: `aiops`, scan-on-push, 20 image retention

### 5.3 Compute Stack (`Aiops-dev-Compute`)

- **ECS Cluster**: Fargate with Cloud Map service discovery
- **Task Definition**: 512 CPU / 1024 MB memory, container port 8080
- **IAM Task Role**: Bedrock InvokeModel, SQS Send/Receive/Delete, DynamoDB CRUD, SSM SendCommand/GetParameter, SES SendEmail, CloudWatch PutMetricData
- **API Gateway**: HTTP API with VPC Link to ECS (private integration)
- **Auto-Scaling**: SQS queue depth metric (1 → 3 tasks)
- **Secrets Manager**: API key with 90-day rotation Lambda
- **SSM Parameters**: service-base-url, config paths

### 5.4 Observability Stack (`Aiops-dev-Observability`)

- **SNS Topic**: aiops-alarms-{env}
- **CloudWatch Alarms** (staging/prod):
  - DLQ depth > 5 messages
  - AI reasoning latency p95 > 15s
  - Remediation failure rate > 30%
  - ECS unhealthy tasks > 0
  - Composite: Rollback (ECS unhealthy AND DLQ depth)
- **CloudWatch Dashboard**: operational + DORA metrics
- **WAF**: Rate limit 100 req/5min/IP, size constraints, AWS managed rules
- **Synthetics Canary**: 5-min health check
- **AWS Budgets**: $200/month (dev), $500 (staging), $2000 (prod)

### 5.5 Monitoring Stack (`Aiops-dev-Monitoring`)

- **Amazon Managed Prometheus** (AMP) workspace
- **ADOT Collector** sidecar (Prometheus scrape → AMP remote write)
- Scrapes node_exporter on target instances

### 5.6 Simulation Stack (`Aiops-dev-Simulation`)

- **EC2 Instance**: t3.micro (Amazon Linux 2023), private subnet
  - stress-ng, node_exporter, fake HTTP app
  - SSM Agent for agentless command execution
- **SSM Documents**: `aiops-break-cpu-{env}` (trigger), `aiops-fix-cpu-{env}` (fix)
- **CloudWatch Alarms**:
  - CPU > 80% → HighCPUUsage alert (Rule Mode)
  - Network packets > 1000/min → NetworkFloodDetected (AI Mode)
- **Lambda Functions**: Convert CloudWatch alarm → Alertmanager webhook

---

## 6. Safety & Resilience

### 6.1 Storm Detection

- Sliding-window rate counter (default: 50 alerts/minute threshold)
- Grouping by (alertname + service) during storms
- Only one representative processed per group
- HTTP 429 when queue depth > 100
- Auto-exit after 2 minutes below threshold

### 6.2 Fleet Circuit Breaker

- Tracks failures globally across all hosts
- Threshold: 5 failures in 300s window → OPEN state
- Cooldown: 600s pause on all automation
- Recovery: Adaptive ramp-up (1→2→4→8→max concurrent)
- Re-trips on failure during ramp-up

### 6.3 Human-in-the-Loop Approval

- HMAC-signed tokens (SHA-256, 32-byte signing secret)
- DynamoDB persistence (survives ECS task restarts)
- 30-minute expiry (configurable)
- Two-step: GET confirmation page → POST execution (anti-link-scanner)
- Atomic consumption via DynamoDB conditional writes

### 6.4 Graceful Shutdown

- SIGTERM → stop accepting new alerts
- Wait up to 25s for in-progress pipelines to drain
- Release DynamoDB host locks
- 5s buffer before ECS SIGKILL (30s stop timeout)
- SIGHUP → reload configuration without restart

---

## 7. Observability & Monitoring

### 7.1 Logging

- Structured JSON via custom `JsonFormatter`
- Always includes: timestamp, level, logger, message, incident_id
- Log groups: `/aiops/{env}/ecs`
- Retention: 30d (dev), 90d (staging), 365d (prod)

### 7.2 Metrics (CloudWatch Custom)

- Namespace: `AIOps/{env}`
- Metrics: alerts_received, remediation_success, remediation_failure, remediation_timeout, ai_latency_ms, storm_suppressed, fleet_breaker_tripped

### 7.3 Distributed Tracing (OpenTelemetry)

- Spans per pipeline stage with incident_id attribute
- Bedrock calls emit GenAI semantic conventions (model, tokens, latency)
- Export to X-Ray via ADOT collector
- Gracefully degrades if OpenTelemetry not installed

---

## 8. Security

- No hardcoded secrets — Secrets Manager with rotation
- ECS tasks in private subnets (no public IPs)
- All AWS API traffic via VPC endpoints
- WAF on API Gateway (staging/prod)
- Pydantic validation on all inputs
- Sensitive labels redacted before DynamoDB storage
- IAM least privilege with resource scoping
- Approval signing secret from Secrets Manager

---

## 9. Cost Optimization

| Component | Strategy |
|-----------|----------|
| AI Inference | Model routing: 70% Nova Lite, 20% Nova Pro, 10% Claude |
| NAT Gateway | 1 in dev/staging, VPC endpoints reduce data processing |
| DynamoDB | PAY_PER_REQUEST (no provisioned capacity waste) |
| ECS | Fargate Spot for dev, auto-scaling 1→3 |
| VPC Endpoints | Gateway endpoints free (DynamoDB, S3) |
| Budgets | Per-environment alerts at $200/$500/$2000 |

---

## 10. Demo Guide

### 10.1 Rule Mode (HighCPUUsage — has playbook)

```bash
python demo/break_target.py --mode cpu --duration 600
```

What happens:
1. stress-ng runs on EC2 → CPU > 80%
2. CloudWatch Alarm fires → Lambda → POST /webhook
3. Pipeline matches `HighCPUUsage` → `fix_high_cpu.yml`
4. Email sent with RCA + "Approve Auto-Remediation" button
5. Operator clicks → Ansible kills stress-ng → CPU drops → alert resolves

### 10.2 AI Agent Mode (NetworkFloodDetected — no playbook)

```bash
aws lambda invoke --function-name aiops-network-alert-dev --cli-binary-format raw-in-base64-out --payload "{}" output.json
```

What happens:
1. Lambda sends NetworkFloodDetected alert (no matching playbook)
2. AI Agent Mode: Bedrock Nova Pro analyzes the issue
3. Email sent with AI-generated analysis + suggested steps
4. Operator resolves manually using suggestions

---

## 11. Project Structure

```
├── src/
│   ├── app.py                 ← FastAPI: /webhook, /health, /approve/{token}
│   ├── orchestrator.py        ← Pipeline coordinator (50 concurrent)
│   ├── normalizer.py          ← Alertmanager → internal format
│   ├── enricher.py            ← Asset inventory lookup
│   ├── playbook_mapper.py     ← YAML rule → playbook matching
│   ├── executor.py            ← Ansible execution (10 concurrent, 300s timeout)
│   ├── approval_handler.py    ← Token-based email approval
│   ├── email_notifier.py      ← SES with RCA + approve button
│   ├── storm_detector.py      ← Alert storm protection
│   ├── tracing.py             ← OpenTelemetry distributed tracing
│   ├── guardrails/            ← 7-layer safety engine
│   ├── concurrency/           ← Host locks, dedup, fleet breaker, graceful shutdown
│   └── agentic_ai/
│       ├── agents/reasoning_agent.py  ← Bedrock AI with fallback chain
│       ├── agents/model_router.py     ← Cost-optimized model selection
│       ├── models/incident_store.py   ← DynamoDB incident memory
│       └── infra/stacks/              ← CDK stacks (6 total)
├── config/                    ← YAML configuration
├── playbooks/                 ← Ansible remediation playbooks
├── demo/                      ← Simulation scripts
├── tests/                     ← Unit, property, integration, CDK tests
└── .github/workflows/         ← CI/CD pipelines
```
