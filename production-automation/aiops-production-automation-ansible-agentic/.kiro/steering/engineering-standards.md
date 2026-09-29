# Engineering Standards — AIOps Self-Healing Infrastructure

This document is the single source of truth for coding, infrastructure, AI/LLM, and operational standards in this project. All contributions must follow these guidelines.

---

## Python Standards

### Project Structure
- All application code lives in `src/` with clear module boundaries
- Infrastructure code lives in `src/agentic_ai/infra/`
- Tests mirror source structure under `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/cdk/`
- Configuration files live in `config/` (YAML)
- Ansible playbooks live in `playbooks/`

### Code Style
- **Formatter:** ruff format (enforced in CI)
- **Linter:** ruff check (enforced in CI)
- **Type hints:** Required on all function signatures. Use `from __future__ import annotations` for forward references
- **Docstrings:** Required on all public classes and functions (Google style)
- **Max line length:** 100 characters
- **Imports:** stdlib → third-party → local, separated by blank lines

### Dependency Management
- Runtime deps pinned in `pyproject.toml` with exact versions (`==`)
- Lock file at `requirements.lock` for Docker reproducibility
- Dev/CDK deps in `[project.optional-dependencies]`
- Never use open version ranges in production dependencies

### Exception Handling
- Never silently swallow exceptions. Always log at minimum
- Use specific exception types, not bare `except Exception`
- Critical paths must have fallback behavior (graceful degradation)
- External service calls (Bedrock, SQS, DynamoDB) must have retry + timeout

### Logging
- Use structured JSON logging via `src/config.JsonFormatter`
- Always include `incident_id` in extra fields when available
- Log levels: ERROR for failures, WARNING for degradation, INFO for lifecycle events
- Never log secrets, tokens, or PII

### Security
- No hardcoded secrets — use Secrets Manager or SSM Parameter Store
- No credentials in environment variables at CDK definition time (use `ecs.Secret`)
- Validate and sanitize all external inputs (Pydantic models for API payloads)
- Redact sensitive labels before storage (see `AWSOrchestrator._redact_sensitive_labels`)

---

## AWS CDK / Infrastructure Standards

### Construct Design
- One stack per concern: Network, Data, Compute, Observability, Simulation
- Cross-stack references via constructor parameters, not `Fn.importValue`
- Stack naming: `Aiops-{environment}-{Purpose}` (e.g., `Aiops-prod-Compute`)
- All stacks accept a validated `CdkContext` dataclass

### IAM (Least Privilege)
- Scope resources to specific ARNs where possible
- Use conditions (`ssm:resourceTag`) for instance-level scoping
- Document why `Resource: "*"` is needed (e.g., "AWS-mandated for DescribeAlarms")
- SES scoped to `arn:aws:ses:{region}:{account}:identity/*`
- Bedrock scoped to `foundation-model/*` (required for fallback chain)

### Environment Separation
- Context-driven via `cdk.json` (`environment`, `awsAccount`, `awsRegion`)
- Resource names include environment suffix: `aiops-main-{env}`, `AiopsIncidentMemory-{env}`
- Termination protection enabled for prod stacks
- PITR and AWS Backup enabled for prod DynamoDB only

### Naming Conventions
- CDK construct IDs: PascalCase (`MainQueue`, `TaskRole`)
- AWS resource names: kebab-case with env suffix (`aiops-cluster-dev`)
- SSM parameters: `/aiops/{environment}/{parameter-name}`
- Secrets: `/aiops/{environment}/{secret-name}`

### Resilience
- Prod: 2 NAT Gateways (one per AZ)
- Dev/staging: 1 NAT Gateway (cost savings)
- VPC endpoints for DynamoDB (gateway), S3 (gateway), SQS, SSM, Logs, Secrets Manager, Bedrock (interface)
- SQS: DLQ with `maxReceiveCount=3`, visibility timeout 300s
- DynamoDB: PAY_PER_REQUEST billing, TTL for automatic expiry

### Safe Defaults
- Lambda timeout: 60s minimum
- ECS stop timeout: 30s (with 25s drain period)
- SQS visibility timeout: 300s (must exceed max processing time)
- API Gateway: WAF with rate limiting (100 req/5min/IP)

---

## AI / LLM Standards (Amazon Bedrock)

### Model Selection
- Use ModelRouter for cost-optimized routing:
  - SIMPLE (seen 5+ times, >90% success): Nova Lite (~$0.0003)
  - MODERATE (limited history, mixed outcomes): Nova Pro (~$0.001)
  - COMPLEX (P1, never seen, all past failed): Claude Sonnet (~$0.003)
- Escalation: if confidence < 0.5, auto-escalate to next tier

### Prompt Design
- Structured prompts with stable prefix (cacheable) + variable suffix
- Always include: alert context, historical outcomes, excluded actions
- Max input enforced by character-to-token heuristic (4 chars ≈ 1 token)
- Max output: 2048 tokens

### Retry & Fallback
- 30-second timeout per Bedrock invocation
- 2 retries with exponential backoff (1s, 2s)
- Model fallback chain: Claude Sonnet → Nova Pro → Claude Haiku → Nova Lite
- If all models fail: rule-based fallback (PlaybookMapper)
- FallbackReason tracked for observability

### Safety
- AI-generated plans pass through PlanValidator (blocks dangerous commands)
- Denied commands list in `config/denied_commands.yml`
- Confidence threshold: 0.7 general, 0.8 for P1 alerts
- Truncation flag set if response appears cut off
- Bedrock Guardrails: set `BEDROCK_GUARDRAIL_ID` + `BEDROCK_GUARDRAIL_VERSION` env vars
  for native content filtering (blocks dangerous commands the denylist might miss)

---

## Event-Driven Design Standards

### SQS
- Visibility timeout must be >= 6x processing time
- DLQ configured with `maxReceiveCount=3`
- Messages must be processed idempotently (use incident_id deduplication)
- Never delete message before processing completes

### Idempotency
- Alert deduplication via fingerprint in DynamoDB (TTL-based expiry)
- Approval tokens: single-use, consumed atomically via DynamoDB conditional writes
- Host locks: DynamoDB conditional PutItem with TTL

### Backpressure
- Storm detector: rate threshold triggers grouping mode
- Fleet circuit breaker: stops all automation when failure rate spikes
- HTTP 429 returned when system at capacity (Alertmanager retries natively)

### Concurrency
- Host-level DynamoDB locks prevent conflicting remediations
- Asyncio semaphore limits to 50 concurrent pipelines
- Executor semaphore limits to 10 concurrent Ansible invocations
- Priority queue with severity-based ordering

---

## Security Standards

### Secrets Management
- All secrets in AWS Secrets Manager with automatic rotation
- API Gateway key: 90-day rotation via Lambda
- Approval signing secret: shared across tasks via Secrets Manager
- Never store secrets in SSM StringParameter (use SecureString or Secrets Manager)

### Network Security
- ECS tasks in private subnets (no public IPs)
- All AWS API traffic via VPC endpoints (no internet transit for API calls)
- Security groups: least-privilege ingress/egress
- WAF on API Gateway (staging/prod): rate limiting, size constraints, AWS managed rules

### API Security
- Payload validation via Pydantic models (rejects malformed input)
- Content-Type enforcement (415 for non-JSON)
- Payload size limit: 1 MB
- Approval endpoint: two-step (GET confirmation page → POST execution) to prevent link-scanner auto-approval

### Data Protection
- DynamoDB encryption: AWS-managed keys
- SQS encryption: SQS-managed keys
- Sensitive labels redacted before DynamoDB storage
- Audit logs: no secrets, no full payloads, only incident metadata

---

## Observability Standards

### Logging
- Structured JSON to stdout (CloudWatch collects via awslogs driver)
- Log retention: 30d (dev), 90d (staging), 365d (prod)
- Always include: timestamp, level, logger, message, incident_id (when available)
- Pipeline stage transitions logged at INFO level

### Metrics (Prometheus Format)
- Custom metrics emitted to CloudWatch via PutMetricData
- Namespace: `AIOps/{environment}`
- Required metrics: alerts_received, remediation_success/failure/timeout, AI latency, storm suppressed
- Labels: alert_name, severity

### Alarms (staging/prod only)
- DLQ depth > 5 messages
- AI reasoning latency p95 > 15s
- Remediation failure rate > 30%
- ECS unhealthy tasks > 0
- Composite: RollbackRequired (ECS unhealthy AND DLQ depth)

### Dashboards
- Operational: ECS tasks, SQS depth, DLQ, AI latency, remediation outcomes
- DORA: deployment frequency, lead time, change failure rate, MTTR

### Distributed Tracing (OpenTelemetry)
- Module: `src/tracing.py` — gracefully degrades if OpenTelemetry not installed
- Install with: `pip install -e ".[tracing]"`
- Each pipeline stage emits a span with incident_id attribute
- Bedrock calls emit GenAI semantic convention spans (model, tokens, latency)
- Export to X-Ray via ADOT collector, or console in dev
- Config: `OTEL_ENABLED`, `OTEL_EXPORTER`, `OTEL_OTLP_ENDPOINT`
- Tracing failure must NEVER block the pipeline (wrapped in try/except)

---

## CI/CD Standards

### CI Pipeline (on push/PR)
1. Lint (ruff check + format)
2. Unit tests (coverage >= 80%)
3. Property-based tests (Hypothesis)
4. CDK synth (validates templates)
5. CDK assertion tests
6. Docker build + ECR push + vulnerability scan

### CD Pipeline (on CI success)
1. Prepare (resolve image tag, environment)
2. Production approval gate (4h timeout, manual)
3. Deploy stacks in order: Network → Data → Compute → Health Gate → Observability
4. Health gate: 3 consecutive healthy responses within 5 minutes
5. Rollback: automatic on health gate failure (previous manifest from SSM)
6. Store deployment manifest in SSM (5-slot sliding window)

### Deployment Safety
- `--require-approval never` only in CI (human review happens at PR)
- CDK diff uploaded as artifact for every deployment
- `--hotswap` only for dev environment ComputeStack
- Prod requires explicit approval via GitHub Environment

### Branch Strategy
- `main` → dev environment
- `staging` → staging environment
- `v*.*.*` tags → prod environment

---

## Common Pitfalls to Avoid

| Pitfall | Why It's Bad | What to Do Instead |
|---------|-------------|-------------------|
| `boto3.client()` inside a loop or per-request | Connection overhead, memory churn | Create client once at module level or use singleton |
| `Resource: "*"` without comment | Appears to violate least privilege | Add comment explaining AWS mandates it |
| In-memory state for cross-request data | Lost on ECS task restart/scaling | Use DynamoDB with TTL |
| `import json; import json` | Duplicate imports signal copy-paste | Run `ruff check` to catch |
| Visibility timeout < processing time | Message reappears → duplicate execution | Set to 5-6x expected processing time |
| GET endpoint with side effects | Email link scanners trigger unintended actions | Use GET for display, POST for execution |
| Hardcoded AWS account/region | Breaks cross-environment deployment | Read from CDK context |
| `sys.exit()` in library code | Kills the entire process unexpectedly | Raise exceptions, let caller decide |
| Bare `except:` | Catches KeyboardInterrupt, SystemExit | Use `except Exception:` at minimum |
| Missing `encoding='utf-8'` on `open()` | Fails on Windows (cp1252 default) | Always specify encoding |

---

## Mandatory PR Checklist

Before merging any PR:

- [ ] `ruff check .` passes with no errors
- [ ] `ruff format --check .` passes
- [ ] All existing tests pass (`pytest -m unit`)
- [ ] New functionality has corresponding tests
- [ ] No hardcoded secrets, accounts, or credentials
- [ ] CDK synth succeeds (`npx aws-cdk@2 synth --all --context environment=dev`)
- [ ] Docstrings on all new public functions
- [ ] Structured logging includes incident_id where applicable
- [ ] External service calls have timeout + retry + fallback
- [ ] IAM permissions follow least privilege with Resource scoping
- [ ] No breaking changes to API contracts without version bump
