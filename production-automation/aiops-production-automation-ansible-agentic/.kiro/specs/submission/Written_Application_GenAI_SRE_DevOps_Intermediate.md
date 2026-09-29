# IBM Consulting Generative & Agentic AI — SRE/DevOps Engineer Experienced Level
## Written Application

---

## 1. Client Need / Business Problem

**Project Name:** AIOps Self-Healing Infrastructure Platform  
**Dates:** 2025 – Present  
**Objective:** Reduce Mean Time to Resolution (MTTR) for production infrastructure incidents by building an AI-powered, agentic self-healing platform that autonomously detects, diagnoses, and remediates infrastructure issues — with human-in-the-loop approval for safety.

**Business Problem:**  
Production operations teams face alert fatigue, slow incident response times, and inconsistent remediation practices. Manual triage of CloudWatch alarms leads to delays (often 15–30+ minutes) before an operator can even begin troubleshooting. This project addresses the need for an intelligent automation layer that:

- Automatically correlates alerts with asset context and historical incident data
- Uses generative AI (Amazon Bedrock) to perform root cause analysis when no existing playbook matches the alert
- Proposes remediation actions to operators via email with one-click approval
- Executes Ansible playbooks on target infrastructure (via AWS SSM) once approved
- Maintains a full audit trail, structured observability, and safety guardrails to prevent unintended blast radius

The platform targets SRE/DevOps teams managing cloud-native workloads on AWS who need to scale their incident response capabilities without proportionally scaling headcount.

---

## 2. Relevant IBM Generative & Agentic AI Offering

This project demonstrates capabilities aligned with **IBM Consulting's AIOps and Intelligent Automation offerings**, specifically:

- **AIOps for IT Operations** — Automated incident detection, correlation, and resolution using AI
- **Generative AI for SRE** — Leveraging large language models to generate root cause analyses, remediation plans, and operational recommendations
- **Agentic AI Patterns** — Building autonomous agents that reason over incidents, retrieve historical context, and produce structured remediation plans with confidence scoring and escalation logic

The solution directly supports IBM Consulting's "Client First...with a Point of View" approach by demonstrating how generative and agentic AI transforms traditional reactive operations into proactive, self-healing infrastructure management.

---

## 3. Use of watsonx and/or Strategic Partner Products

This implementation uses **Amazon Bedrock** as the generative AI foundation, which is a Strategic Partner product within IBM Consulting's multi-cloud delivery model. Specifically:

### AI Models Used (with Fallback Chain)
1. **Anthropic Claude 3 Sonnet** (via Bedrock) — Primary reasoning model for complex root cause analysis
2. **Amazon Nova Pro** — Secondary model for cost-effective reasoning
3. **Anthropic Claude 3 Haiku** (via Bedrock) — Lightweight fallback for simple incident classification
4. **Amazon Nova Lite** — Final fallback ensuring graceful degradation

### How the AI Agent Works
The `AIReasoningAgent` class implements a full agentic AI pattern:

- **Memory:** Retrieves up to 50 historical incidents from a DynamoDB-backed incident store, including past outcomes (success/failure) and execution durations
- **Reasoning:** Builds structured prompts with alert context, labels, historical patterns, and excluded actions (actions that always failed in the past)
- **Structured Output:** Produces a JSON `RemediationPlan` with confidence scores (0.0–1.0), step-by-step remediation instructions, and escalation flags
- **Fallback Logic:** If AI is unavailable (throttling, timeout, access denied), gracefully falls back to rule-based playbook matching
- **Confidence Thresholds:** P1 incidents require 80% confidence; others require 70% — below threshold triggers escalation to human operators

### Prompt Engineering Techniques
- Structured prompts with clear sections: ALERT CONTEXT, HISTORICAL CONTEXT, EXCLUDED ACTIONS
- Output schema enforcement (JSON format with defined fields)
- Historical context injection for few-shot-style learning from past incidents
- Token budget management with truncation by recency
- Temperature control (0.2) for deterministic, reproducible reasoning

---

## 4. Solution / Deliverables / Work Products

### Architecture Delivered

The platform is a production-grade, fully deployable AWS solution consisting of **6 CDK stacks**:

| Stack | Resources |
|-------|-----------|
| **Network** | VPC, 2 AZs, NAT Gateway, VPC Endpoints, Security Groups |
| **Data** | DynamoDB (incident store), SQS + Dead Letter Queue, ECR Repository |
| **Compute** | ECS Fargate, IAM Roles (least privilege), API Gateway, Cloud Map, Secrets Manager |
| **Observability** | SNS, CloudWatch Alarms, Budget Alerts, CloudWatch Dashboard |
| **Monitoring** | Amazon Managed Prometheus, ADOT Collector, Alertmanager |
| **Simulation** | EC2 target instance, CloudWatch CPU/Network Alarms, Alert trigger Lambdas |

### Key Work Products

1. **AI Reasoning Agent** (`src/agentic_ai/agents/reasoning_agent.py`)
   - 300+ lines of production Python implementing the full agentic reasoning loop
   - Bedrock model invocation with async execution, retry logic, and multi-model fallback
   - Prompt engineering with historical context injection and confidence scoring
   - Graceful degradation to rule-based matching on AI failure

2. **7-Layer Guardrail Safety Engine** (`src/guardrails/`)
   - Self-Protection check (prevents the agent from modifying its own infrastructure)
   - Maintenance Window awareness (defers actions during planned maintenance)
   - Circuit Breaker (stops repeated failures from cascading)
   - Concurrency Guard (prevents parallel remediation on the same host)
   - Blast Radius Classifier (classifies risk as LOW/MEDIUM/HIGH/CRITICAL)
   - Health Checker (validates target host health before execution)
   - Approval Gate (human-in-the-loop email approval for HIGH/CRITICAL risk)

3. **Self-Healing Pipeline** (`src/orchestrator.py`)
   - 5-stage pipeline: Normalize → Enrich → Match → Execute → Notify
   - Supports 50 concurrent pipeline executions via asyncio semaphore
   - Integrates both guardrail engine and concurrency manager between match and execute stages
   - Full audit trail with structured JSON logging

4. **Email-Based Human-in-the-Loop Approval** (`src/email_notifier.py`)
   - Rich HTML emails with root cause analysis, severity coloring, and one-click approval buttons
   - Token-based approval links with expiry (30 minutes)
   - If not clicked, operator receives expiry notification and must resolve manually

5. **Concurrency Safety System** (`src/concurrency/`)
   - Host-level locking to prevent conflicting remediation actions
   - Alert deduplication to suppress duplicate processing
   - Circuit breaker pattern to halt after consecutive failures
   - Priority queue for severity-based execution ordering
   - Dependency graph awareness for service relationships

6. **Infrastructure as Code** (`src/agentic_ai/infra/`)
   - 6 AWS CDK stacks in Python with proper dependency management
   - Environment-aware deployment (dev/staging/prod) with termination protection
   - Standard tagging for cost allocation and governance

7. **CI/CD Pipeline** (`.github/workflows/`)
   - Lint → Unit Tests (80% coverage gate) → Property Tests → CDK Synth → CDK Tests → Docker Build → ECR Scan → Push
   - OIDC-based authentication (no long-lived credentials)
   - ECR vulnerability scanning gate before deployment

8. **Operational Runbooks** (`runbooks/`)
   - 8 detailed operational guides: Incident Response, Disaster Recovery, DLQ Replay, Rollback, Scale Out/In, Bedrock Throttling, Parameter Updates

9. **Ansible Remediation Playbooks** (`playbooks/`)
   - `fix_high_cpu.yml` — Kills runaway processes, restarts application service
   - `restart_service.yml` — Graceful systemd service restart
   - `clear_disk.yml` — Removes old log files and temporary data

10. **Comprehensive Test Suite** (`tests/`)
    - Unit tests, Property-based tests (Hypothesis), Integration tests, CDK assertion tests, Load tests (Locust)

---

## 5. Approach to Delivery Using IBM Tools, Techniques, and Methods

### IBM Consulting Advantage & Core Method Alignment

- **Discovery & Framing:** Started with analysis of operational pain points (alert fatigue, slow MTTR, inconsistent remediation). Mapped the current-state process and identified AI intervention points.

- **Architecture Decision Records:** Documented key decisions:
  - Email over Slack (universal access, no dependency on third-party integrations)
  - Human-in-the-loop for HIGH/CRITICAL risk (no fully autonomous execution for dangerous actions)
  - SSM over SSH (no key management, works with private subnet instances)
  - CloudWatch-native alerting (reduces operational complexity vs. external Prometheus)

- **Iterative Delivery (IBM Garage Methodology):**
  - Sprint 1: Core pipeline (normalize → enrich → match → execute)
  - Sprint 2: AI reasoning agent with Bedrock integration
  - Sprint 3: Guardrail safety engine (7 layers)
  - Sprint 4: Concurrency management and observability
  - Sprint 5: CI/CD, CDK infrastructure, deployment automation
  - Sprint 6: Operational runbooks, demo scenarios, documentation

- **Infrastructure as Code (IaC):** All infrastructure defined in AWS CDK Python, enabling reproducible deployments across environments with `npx aws-cdk deploy --all`.

- **Observability-First Design:** Structured JSON logging, Prometheus metrics, CloudWatch dashboards, and audit trails built into every component from the start — not bolted on afterward.

- **Twelve-Factor App Principles:** Configuration via environment variables, stateless compute (ECS Fargate), explicit dependency declaration, port binding, concurrency via process model, disposability.

---

## 6. Risks, Ethical Concerns, and Trustworthy AI

### Identified Risks

| Risk | Mitigation |
|------|-----------|
| **AI hallucination / incorrect remediation** | Confidence scoring with escalation below threshold (70%/80% for P1). Human approval required for HIGH/CRITICAL blast radius. |
| **Blast radius of automated actions** | 7-layer guardrail engine classifies every action. Single-instance services and database restarts auto-classified as CRITICAL. Production environment elevation rule. |
| **Runaway automation (cascading failures)** | Circuit breaker pattern halts execution after consecutive failures. Concurrency guard prevents parallel actions on same host. |
| **Data accuracy (stale asset inventory)** | Asset enrichment uses live metadata. Historical context is bounded (max 50 incidents) and time-decayed. |
| **Model bias toward certain remediation patterns** | Historical action exclusion: actions that always failed in the past are explicitly excluded from AI consideration. |
| **Availability of AI service** | 4-model fallback chain (Claude Sonnet → Nova Pro → Claude Haiku → Nova Lite). If all fail, graceful degradation to rule-based matching. |
| **Unauthorized execution** | Token-based approval with 30-minute expiry. No auto-execution without operator click for HIGH/CRITICAL. |

### IBM Trustworthy AI Principles Applied

1. **Transparency:** Full audit logging of every decision — which model was used, confidence score, reasoning explanation, which guardrails passed/failed, and execution outcome. Operators see the complete chain of reasoning in their approval email.

2. **Explainability:** The AI agent produces structured `reasoning_explanation` fields (up to 2048 characters) explaining why it chose a particular remediation. This is included in the operator's approval email so they can make an informed decision.

3. **Fairness:** The system does not make decisions based on operator identity or team membership. All incidents are processed through the same pipeline with consistent rules regardless of origination.

4. **Robustness:** The 7-layer guardrail engine, circuit breaker pattern, and multi-model fallback chain ensure the system degrades gracefully rather than failing catastrophically. A 15-second evaluation timeout ensures guardrails never block the pipeline indefinitely.

5. **Privacy:** No customer PII is processed. Alert labels and asset metadata contain only infrastructure identifiers (hostnames, service names, IP addresses). Audit logs are stored in DynamoDB with encryption at rest.

6. **Governance:** Human-in-the-loop approval for all HIGH and CRITICAL risk actions. Protected hosts configuration prevents automation from ever targeting critical infrastructure. Maintenance window awareness defers actions during planned change windows.

7. **Safety:** Self-protection check ensures the agent cannot modify its own running infrastructure. The system is designed so that failure (AI unavailable, approval expired, guardrail denied) always results in "do nothing" rather than "do something potentially harmful."

---

## Summary

This project demonstrates end-to-end delivery of a generative and agentic AI solution for SRE/DevOps operations. It combines Amazon Bedrock's large language models with a production-grade safety framework, infrastructure-as-code deployment, CI/CD automation, and comprehensive observability — all following IBM Consulting's delivery methods and Trustworthy AI principles. The result is a platform that transforms reactive incident response into proactive, AI-assisted self-healing while maintaining human oversight for high-risk actions.

---

*Submitted by: Ravindra Yadav*  
*Role: SRE/DevOps Engineer*  
*Date: August 2026*
