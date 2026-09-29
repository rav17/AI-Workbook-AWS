# Production Implementation Plan — AIOps Self-Healing Platform

## Document Information

| Field | Value |
|-------|-------|
| **Author** | Production Architecture Review |
| **Date** | August 2026 |
| **Status** | Actionable Roadmap |
| **Scope** | 5 Spec Modules, 45+ Improvements |
| **Total Effort** | ~14 weeks (phased rollout) |
| **Target** | Production-grade at scale on AWS |

---

## Executive Summary

This plan consolidates improvements from 5 independent spec modules into a unified,
prioritized, production-grade roadmap. The improvements are sequenced to maximize
safety-critical fixes first, then optimize cost, then add operational excellence.

### Spec Modules Analyzed

| # | Spec | Purpose | Improvements |
|---|------|---------|-------------|
| 1 | self-healing-infrastructure | Core alert→remediation pipeline | 8 improvements |
| 2 | agentic-ai-aws-deployment | AI reasoning + Bedrock integration | 6 improvements |
| 3 | aws-deployment-plan | CDK infra + CI/CD + deployment safety | 7 improvements |
| 4 | concurrent-execution-safety | Distributed locks + serialization | 12 improvements |
| 5 | safe-execution-guardrails | 7-layer safety engine | 10 improvements |

---

## Critical Path Summary (Priority Order)

```
Week 1-2:  SAFETY CRITICAL fixes (guardrail bypass, lock leaks, split-brain)
Week 3-4:  COST OPTIMIZATION (Graviton, prompt caching, model routing)
Week 5-6:  RESILIENCE (storm protection, fleet breaker, degradation modes)
Week 7-8:  OBSERVABILITY (tracing, structured events, DORA metrics)
Week 9-10: INTELLIGENCE (effectiveness scoring, calibration, evaluation)
Week 11-12: SECURITY (WAF, SBOM, multi-account, drift detection)
Week 13-14: ARCHITECTURE (Strands SDK, canary deploys, SQS FIFO)
```

---

## Spec 1: Self-Healing Infrastructure

### Summary

Core pipeline: Alertmanager webhook → normalize → enrich → match → execute → notify.
Well-implemented with FastAPI, Ansible subprocess execution, Docker containerization.
Gaps: no storm protection, no feedback loop, static enrichment, no graceful degradation.

### Key Improvements (Prioritized)

| Priority | Improvement | Impact | Effort |
|----------|------------|--------|--------|
| P1 | Alert Storm Protection (backpressure + rate limiting) | Prevents system overload during outages | 4d |
| P2 | Resolved Alert Auto-Cancellation | Prevents unnecessary remediations | 1.5d |
| P2 | Alert Inhibition & Smart Grouping | Reduces noise, prevents redundant work | 2.5d |
| P2 | OpenTelemetry Distributed Tracing | Full pipeline observability | 3d |
| P2 | Playbook Effectiveness Scoring | Closes MAPE-K feedback loop | 4d |
| P3 | Dynamic AWS Enrichment | Replaces stale YAML with live EC2/Cloud Map | 2.5d |
| P3 | Structured Pipeline Events | Enables replay and analytics | 2.5d |
| P3 | Graceful Degradation Modes | Resilience under partial failure | 3d |

### Implementation Plan

**Phase 1 (Week 5-6): Storm Protection & Auto-Resolution**

```
Files to create:
  src/storm_detector.py         — Sliding window rate tracker + grouping logic
  src/inhibitor.py              — Alert inhibition pre-processing stage

Files to modify:
  src/app.py                    — HTTP 429 backpressure, storm mode entry
  src/orchestrator.py           — Resolved alert cancellation, inhibition stage
  src/approval_handler.py       — Cancel pending approvals for resolved alerts
  src/metrics.py                — Storm mode + auto-resolution metrics
  src/notification.py           — Grouped storm notification

Config to create:
  config/inhibition_rules.yml   — Parent-child alert suppression rules
```

Steps:
1. Implement `StormDetector` class with sliding 60s window, configurable threshold (default 50/min)
2. Add grouping by `(alertname + service_name)` — process one representative per group
3. Add HTTP 429 response when internal queue depth > 100 (configurable)
4. Track active incidents in-memory set; honor `status=resolved` signals
5. Cancel pending (not executing) actions when resolved signal arrives
6. Add inhibition YAML config with `source_alert → target_alerts` mapping
7. Verify Alertmanager retries on 429 with exponential backoff

**Phase 2 (Week 7-8): Feedback Loop & Smart Matching**

```
Files to create:
  (DynamoDB table: PlaybookEffectiveness via CDK)

Files to modify:
  src/orchestrator.py           — Update scores post-baking validation
  src/playbook_mapper.py        — Use effectiveness_score in tie-breaking
  src/agentic_ai/models/domain.py — Effectiveness data model
```

Steps:
1. Create DynamoDB table: PK=`{alert_name}#{playbook_path}`, attributes: successes, failures, score
2. After each baking validation, increment success/failure counter
3. Modify `PlaybookMapper.match()` to prefer higher effectiveness_score on ties
4. Route playbooks with score < 0.3 to AI agent instead of rule-based execution
5. Add weekly digest Lambda (or scheduled task) for playbook health report

**Phase 3 (Week 9-10): Observability & Dynamic Enrichment**

```
Files to create:
  src/tracing.py                — OpenTelemetry setup, span factory
  src/events.py                 — Structured event emitter (CloudWatch/DynamoDB)

Files to modify:
  src/enricher.py               — AWS EC2/Cloud Map source + fallback chain
  src/orchestrator.py           — Span creation per pipeline stage
```

Steps:
1. Add `opentelemetry-sdk`, `opentelemetry-exporter-otlp` to requirements
2. Create root span `process_alert` with child spans per stage
3. Export to AWS X-Ray via ADOT Collector (prod) or Jaeger (dev)
4. Add EC2 `describe-instances` + Cloud Map lookup in enricher with 5-min cache
5. Implement fallback: AWS → SSM → static YAML
6. Emit structured events to CloudWatch Logs with schema versioning

### Architecture Changes

```
BEFORE:
  Alertmanager → Webhook → Normalize → Enrich → Match → Execute → Notify

AFTER:
  Alertmanager → [Storm Filter] → [Inhibitor] → Normalize → Enrich(live) →
  [Smart Match(scored)] → Execute → [Baking] → Notify + [Event Store]
       ↑                                                        ↓
       └──────────── Knowledge Store (effectiveness feedback) ──┘
```

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Storm detection false positive suppresses real alerts | Missed remediation | Conservative threshold (50/min); suppress only duplicates within group, not all |
| EC2 API rate limiting during enrichment | Enrichment failures | 5-min cache + 2s timeout + YAML fallback; use bulk describe-instances |
| Effectiveness scoring cold-start (no data) | No tie-breaking benefit | Default score = 0.5 for unknown pairs; fall through to existing priority logic |
| Tracing overhead on hot path | Added latency | Sampling (10% in prod); async span export; disable via env var |

---

## Spec 2: Agentic AI AWS Deployment

### Summary

AI-powered reasoning replacing static playbook matching. Uses Amazon Bedrock (Claude
Sonnet → Nova Pro → Haiku → Nova Lite fallback chain), DynamoDB incident memory,
SSM executor, alert correlation, escalation management. Three operating modes.
Gaps: no cost optimization (always starts expensive), no quality evaluation, no calibration.

### Key Improvements (Prioritized)

| Priority | Improvement | Impact | Effort |
|----------|------------|--------|--------|
| P1 | Bedrock Prompt Caching | 90% cost + 85% latency reduction | 1.5d |
| P1 | Intelligent Model Routing | 40-70% additional cost savings | 2.5d |
| P2 | Offline Agent Evaluation Framework | Reasoning quality assurance | 5d |
| P2 | Strands Agents SDK Integration | Better agent architecture | 6d |
| P3 | Bedrock AgentCore Runtime | Serverless agent hosting | 4d |
| P3 | Confidence Calibration | More trustworthy decisions | 2.5d |

### Implementation Plan

**Phase 1 (Week 3-4): Cost Optimization — Immediate 60-90% Savings**

```
Files to create:
  src/agentic_ai/agents/model_router.py    — Complexity classifier + routing
  config/model_routing.yml                  — Thresholds for model selection

Files to modify:
  src/agentic_ai/agents/reasoning_agent.py — Prompt caching structure + routing
  src/agentic_ai/observability/metrics_publisher.py — Cache hit + cost metrics
```

Steps:
1. Restructure prompts: stable system prefix (cacheable) + variable user suffix
2. Add `cache_control: {"type": "ephemeral"}` to system prompt block
3. Implement `AlertComplexityClassifier`:
   - SIMPLE (70%): seen 5+ times, effectiveness > 90%, single host, P3/P4
   - MODERATE (20%): mixed outcomes, 2-3 correlation group, P2
   - COMPLEX (10%): never-seen, 4+ correlated, P1, past failures
4. Route: SIMPLE → Nova Lite, MODERATE → Nova Pro, COMPLEX → Claude Sonnet
5. If cheap model confidence < 0.5, re-invoke with next-tier model
6. Publish `PromptCacheHitRate`, `CostPerInvocation`, `ModelRoutingDecision` metrics

**Expected Cost Impact:**
```
Before:  100 alerts/day × $0.003/invocation = ~$9/month
After:   70% × $0.0003 + 20% × $0.001 + 10% × $0.003 = ~$1.20/month (87% reduction)
```

**Phase 2 (Week 9-10): Quality Assurance**

```
Files to create:
  tests/evaluation/golden_dataset.json     — 50+ labeled test cases
  tests/evaluation/run_evaluation.py       — Evaluation harness
  tests/evaluation/metrics.py              — Accuracy/calibration/latency metrics
  src/agentic_ai/agents/calibration.py     — Isotonic regression calibration
  scripts/recalibrate.py                   — Weekly cron recalibration

Files to modify:
  .github/workflows/ci.yml                 — Add evaluation gate
```

Steps:
1. Curate 50 golden test cases from DynamoDB incident history:
   - 20 simple (known playbook, high confidence)
   - 20 complex (correlation groups, root-cause analysis)
   - 10 edge cases (should escalate, not auto-remediate)
2. Build evaluation harness: replay incidents, compare output vs. human labels
3. Metrics: action_correctness, confidence_calibration, escalation_accuracy
4. CI gate: fail if accuracy < 80% or escalation accuracy < 95%
5. Implement isotonic regression calibration on (raw_confidence, actual_outcome) pairs
6. Store calibration curve in SSM Parameter Store; reload weekly

**Phase 3 (Week 13-14): Agent Architecture Upgrade**

```
Files to create:
  src/agentic_ai/agents/tools/__init__.py
  src/agentic_ai/agents/tools/history_tool.py
  src/agentic_ai/agents/tools/health_tool.py
  src/agentic_ai/agents/tools/execute_tool.py

Files to modify:
  src/agentic_ai/agents/reasoning_agent.py — Refactor to Strands SDK
  src/agentic_ai/orchestrator.py           — Update agent invocation
```

Steps:
1. Define `@tool` decorated functions for: query_incident_history, check_host_health, execute_remediation
2. Create `Agent()` with Bedrock model, tools list, structured RemediationPlan output
3. Migrate memory management to Strands built-in memory
4. Validate multi-step tool-use loops work for complex alerts
5. (Optional) Deploy to AgentCore Runtime for serverless hosting

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Prompt caching 5-min TTL miss for low-volume alerts | No cost savings on rare alerts | Acceptable — rare alerts are < 10% of volume; savings come from common patterns |
| Model routing misclassifies complex alert as simple | Weak reasoning, missed root cause | Confidence-based escalation: if cheap model < 0.5, auto-escalate to expensive model |
| Evaluation dataset becomes stale | Tests don't catch new failure modes | Refresh dataset quarterly; add new incidents as they occur |
| Strands SDK breaking changes | Agent regression | Pin SDK version; run evaluation suite post-upgrade |

---

## Spec 3: AWS Deployment Plan

### Summary

4 CDK stacks (Network → Data → Compute → Observability), GitHub Actions CI/CD with
OIDC auth, ECR scanning, 3-tier environments, health gates, rollback, SSM config.
Gaps: rolling update (not canary) in prod, x86 only (not Graviton), no WAF, no drift detection.

### Key Improvements (Prioritized)

| Priority | Improvement | Impact | Effort |
|----------|------------|--------|--------|
| P1 | ECS Canary/Linear Deployments | Safer prod deploys with auto-rollback | 4d |
| P1 | AWS Graviton ARM64 | 40% compute cost reduction | 1.5d |
| P2 | Infrastructure Drift Detection | Catches manual console changes | 1.5d |
| P2 | AWS WAF on API Gateway | Webhook security hardening | 1.5d |
| P2 | Multi-Account Role Chaining | Blast radius isolation | 2.5d |
| P3 | Container Image SBOM + Signing | Supply chain security | 2d |
| P3 | DORA Metrics Dashboard | Deployment observability | 1.5d |

### Implementation Plan

**Phase 1 (Week 3-4): Cost & Safety — Graviton + Canary**

```
Files to modify:
  Dockerfile                               — Multi-arch build (ARM64 + x86)
  .github/workflows/ci.yml                 — Docker BuildX for ARM64
  .github/workflows/cd.yml                 — Canary deployment flow
  src/agentic_ai/infra/stacks/compute_stack.py — ARM64 runtime, canary config
  src/agentic_ai/infra/stacks/observability_stack.py — Canary alarm rollback

Files to create:
  scripts/publish_deployment_metrics.py    — Deployment duration/status metrics
```

Steps:
1. Update Dockerfile with `FROM --platform=linux/arm64` and multi-stage build
2. Add `docker buildx build --platform linux/arm64` to CI workflow
3. Set `runtimePlatform: { cpuArchitecture: ARM64, operatingSystemFamily: LINUX }` in CDK
4. Configure ECS canary deployment: 10% → monitor 5min → 50% → monitor 3min → 100%
5. Add CloudWatch alarms (error rate < 5%, latency p95 < 15s) as rollback triggers
6. Keep dev/staging on rolling update for faster iteration

**Cost Impact:**
```
Before: 0.5 vCPU × $0.04048/hr × 730hr = $29.55/month (x86)
After:  0.5 vCPU × $0.03238/hr × 730hr = $23.64/month (ARM64) = 20% savings
Actual: With 40% better price-performance on compute-bound work = ~35-40% effective savings
```

**Phase 2 (Week 11-12): Security & Drift**

```
Files to create:
  .github/workflows/drift-check.yml       — Daily drift detection cron
  docs/multi-account-setup.md             — IAM trust policy templates

Files to modify:
  .github/workflows/cd.yml                — Drift check before prod deploy + role chaining
  src/agentic_ai/infra/stacks/observability_stack.py — WAF WebACL resource
```

Steps:
1. Add `cdk drift --all` step before prod deployment in CD workflow
2. If drift detected: halt pipeline, send Slack notification, store report in S3
3. Create daily scheduled workflow (`cron: '0 6 * * *'`) for proactive drift check
4. Add WAF WebACL to API Gateway stage:
   - Rate limit: 100 req/5min per IP
   - Size constraint: block > 1MB
   - AWS Managed Rules: `AWSManagedRulesCommonRuleSet`
5. Document multi-account setup: DevOps hub → Dev/Prod spoke role chaining
6. Add `deployRoleArn` to CDK context per environment

**Phase 3 (Week 11-12): Supply Chain Security**

```
Files to modify:
  .github/workflows/ci.yml               — SBOM generation + cosign signing
  .github/workflows/cd.yml               — Signature verification before deploy
```

Steps:
1. Add Syft SBOM generation: `syft packages <image> -o cyclonedx-json`
2. Add cosign OIDC keyless signing: `cosign sign --yes <image-digest>`
3. Attach SBOM as in-toto attestation: `cosign attest --predicate sbom.json`
4. Add verification step in CD: `cosign verify <image-digest>` before deploy
5. Create DORA metrics dashboard (deployment frequency, lead time, MTTR, CFR)

### Architecture Changes

```
BEFORE:
  GitHub → Build(x86) → ECR → ECS Rolling Update(all at once) → Health Gate

AFTER:
  GitHub → Build(ARM64+x86) → Sign → ECR → Drift Check → 
  ECS Canary(10%→50%→100%) → Alarm-Based Auto-Rollback → DORA Metrics
  WAF ← API Gateway (rate limit + managed rules)
```

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| ARM64 Python package incompatibility | Build failure | Multi-arch manifest; fallback to x86 if ARM build fails |
| Canary extends deployment time (8-10 min vs 2 min) | Slower releases | Only for prod; dev/staging keep rolling update |
| WAF rate limit blocks Alertmanager burst | Missed alerts | Set limit at 100/5min; Alertmanager retry handles transient blocks |
| Drift detection false positives from CDK metadata | Noisy alerts | Filter drift report to exclude CDK-internal metadata changes |

---

## Spec 4: Concurrent Execution Safety

### Summary

DynamoDB-backed distributed locks with TTL, per-host circuit breaker, priority queue
with preemption, alert fingerprint deduplication, DAG dependency graph, YAML resource
conflicts with hot-reload, status API. Gaps: no heartbeats (split-brain risk), no
bulkhead isolation, no fleet-wide breaker, lock leaks on deployment.

### Key Improvements (Prioritized)

| Priority | Improvement | Impact | Effort |
|----------|------------|--------|--------|
| P1 | Graceful Shutdown Lock Handoff | Prevents lock leaks during ECS deploys | 1d |
| P1 | Heartbeat-Based Lock Renewal (Fencing) | Prevents split-brain execution | 3d |
| P2 | Execution-Level Idempotency Key | Prevents duplicate SSM commands | 1.5d |
| P2 | Bulkhead Isolation per Service | Prevents cross-service starvation | 2d |
| P2 | Fleet-Wide Error Threshold | Prevents cascading fleet damage | 1.5d |
| P2 | Adaptive Concurrency Ramp-Up | Prevents post-recovery flood | 2d |
| P3 | Compensating Transactions (Saga) | Enables partial rollback | 4d |
| P3 | Lock Poisoning for Unreachable Hosts | Stops retry loops on dead hosts | 1.5d |
| P3 | Correlation-Aware Lock Grouping | Reduces lock contention | 2d |
| P3 | Priority Inversion Prevention | Reduces P1 wait time | 2.5d |
| P4 | Queue Depth Observability Signals | Better auto-scaling decisions | 1d |
| P2 | SQS FIFO Message Groups (hybrid) | Architectural simplification | 4d |

### Implementation Plan

**Phase 0 (Week 1-2): CRITICAL — Deployment Safety + Split-Brain Prevention**

```
Files to modify:
  src/main.py                             — SIGTERM handler registration
  src/concurrency/manager.py              — set_draining(), release_all_held_locks()
  src/concurrency/lock_store.py           — heartbeat task, fencing_token field
  src/concurrency/models.py               — HostLock model + fencing_token

Files to create:
  (None — modifications only for Phase 0)
```

Steps:
1. Add SIGTERM signal handler in `src/main.py`:
   - Set `draining = True` (reject new requests)
   - Wait up to 25s for in-flight executions
   - Force-release all held DynamoDB locks
   - Exit with code 0
2. Add `fencing_token` (auto-increment counter) to HostLock DynamoDB record
3. Start background heartbeat coroutine (every `TTL/3` seconds):
   - Extend lock TTL via conditional UpdateItem
   - If 3 consecutive heartbeat failures → log warning, let lock expire naturally
4. Pass fencing_token as `extra_var` to executor
5. Validate fencing_token hasn't changed before recording outcome
6. Add `release_all_held_locks()` method for shutdown path

**Phase 1 (Week 5-6): Idempotency + Bulkhead Isolation**

```
Files to create:
  src/concurrency/bulkhead.py             — Per-service semaphore pools
  config/bulkhead_limits.yml              — Service concurrency caps

Files to modify:
  src/agentic_ai/executors/ssm_executor.py — Idempotency key check before execution
  src/concurrency/manager.py              — Integrate bulkhead into request_execution
  src/concurrency/api.py                  — Bulkhead utilization in status API
```

Steps:
1. Add DynamoDB idempotency record: PK=`IDEMPOTENCY#{incident_id}:{step}:{attempt}`, TTL=24h
2. Before SSM SendCommand: check for existing record
   - If COMPLETED → return cached result
   - If IN_PROGRESS and age < timeout → poll and wait
   - If not found → write IN_PROGRESS, then execute
3. Create `BulkheadManager` with per-service `asyncio.Semaphore` instances
4. Load config from `bulkhead_limits.yml` with hot-reload
5. Integrate: `request_execution()` acquires service bulkhead before global semaphore
6. Reserve 3 global slots for P1 alerts (never let lower priority exhaust all capacity)

**Phase 2 (Week 5-6): Fleet-Wide Safety**

```
Files to create:
  src/concurrency/fleet_breaker.py        — Global failure threshold tracker

Files to modify:
  src/concurrency/manager.py              — Fleet breaker integration + ramp-up
  src/concurrency/api.py                  — Fleet breaker state in status API
```

Steps:
1. Track failures globally in sliding 5-min window (any host, any service)
2. When 5+ failures in window → REJECT ALL new executions fleet-wide
3. Allow in-flight executions to complete (don't abort)
4. After 10-min cooldown: adaptive ramp-up (1 → 2 → 4 → 8 → max)
5. If any failure during ramp-up → re-enter cooldown
6. Suppress fleet breaker during active maintenance windows (integration point)

**Phase 3 (Week 7-8): Resilience + Sagas**

```
Files to create:
  src/concurrency/compensator.py          — Saga-style rollback executor

Files to modify:
  src/concurrency/lock_store.py           — Host poisoning logic
  src/concurrency/manager.py              — Correlation-aware lock grouping, priority inversion
  src/concurrency/api.py                  — Unpoison endpoint
  config/playbook_mapping.yml             — Add compensate_path per rule
```

Steps:
1. After 3 consecutive "instance_not_reachable" SSM failures → mark host POISONED
2. Reject all future actions for poisoned hosts; drain queued actions
3. Auto-unpoison on successful health probe (every 30 min)
4. When correlation_group has multiple alerts for same host → acquire ONE lock
5. On multi-step failure at step K: execute compensating actions in reverse (K-1..1)
6. Priority inversion: when P1 waits behind P3+ lock, reduce blocking timeout to 120s

### Architecture Changes

```
BEFORE:
  Alert → Global Semaphore(10) → DynamoDB Lock(fixed TTL) → Execute → Release

AFTER:
  Alert → [Bulkhead(per-service)] → [Fleet Breaker] → DynamoDB Lock(heartbeat) → 
  [Idempotency Check] → Execute → [Compensate on failure] → Release(or poison)
  
  On ECS SIGTERM: drain → wait 25s → force-release all locks → exit cleanly
  On recovery: adaptive ramp-up (1→2→4→8→max)
```

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Heartbeat DynamoDB write cost | Increased bill | On-demand pricing; 10 concurrent locks × 6 writes/min = ~$0.01/day |
| Fleet breaker false positive | All remediation paused | Integration with maintenance window; conservative threshold (5 failures, not 3) |
| Bulkhead misconfiguration blocks a service | No remediation for that service | Validate sum of bulkheads ≤ global max; default=2 if service not in config |
| Compensation playbook has its own bugs | Double-failure state | Run compensation with `--check` in tests; mark FAILED_UNCOMPENSATED + escalate |
| Poisoning legitimate host during transient network issue | Missed remediation | Require 3 consecutive failures; auto-unpoison probe every 30 min |

---

## Spec 5: Safe Execution Guardrails

### Summary

7-layer safety engine: self-protection, maintenance window, circuit breaker, concurrency,
blast radius classification, health check, approval gate. Already has baking validator,
stop conditions, and plan validator files present in codebase. Critical bug: email
approval endpoint bypasses all guardrails.

### Key Improvements (Prioritized)

| Priority | Improvement | Impact | Effort |
|----------|------------|--------|--------|
| P1 | Unified Execution Path (bug fix) | Closes critical safety bypass | 2d |
| P1 | Stop Conditions During Execution | Abort if action makes things worse | 4d |
| P2 | Post-Execution Baking Period | Validates fix actually worked | 2.5d |
| P2 | Service Availability Threshold | Prevents cascading outages | 1.5d |
| P2 | AI Remediation Plan Validation | Blocks dangerous AI commands | 2.5d |
| P3 | SSM Change Calendar Integration | Native AWS maintenance awareness | 2.5d |
| P3 | Graduated Execution (Dry-Run) | Safer CRITICAL actions | 2.5d |
| P3 | Pre-Execution State Snapshot | Enables rollback on failure | 4d |
| P4 | Cross-Service Dependency Check | Cascade-aware blast radius | 2.5d |
| P4 | Escalation Fatigue Prevention | Better operator experience | 2.5d |

### Implementation Plan

**Phase 0 (Week 1-2): CRITICAL — Fix Guardrail Bypass**

```
Files to modify:
  src/app.py                              — Route approval through GuardrailEngine
  src/guardrails/engine.py                — Add skip_approval parameter
  src/guardrails/models.py                — Add pre_approved field to RemediationAction

Files to create:
  tests/unit/test_approval_guardrails.py  — Verify all checks still run post-approval
```

Steps:
1. In `_execute_approved_remediation()`: construct `RemediationAction` from approval data
2. Call `guardrail_engine.evaluate(action, skip_approval=True)`
3. If DENY → return HTML explaining which guardrail blocked + notify operator
4. If DEFER (concurrency) → queue action, notify that execution is pending
5. Only if ALLOW → proceed to executor
6. Log all guardrail checks (pass/fail) with same audit format as pipeline path
7. Write integration test: approve during maintenance window → should be DENIED

**Phase 1 (Week 5-6): Execution Safety**

```
Files to modify:
  src/guardrails/stop_conditions.py       — Real-time alarm monitoring during execution
  src/executor.py                         — Integration with stop condition monitor
  src/guardrails/baking_validator.py      — Post-execution validation logic
  src/orchestrator.py                     — Baking period integration
  config/stop_conditions.yml              — Alarm definitions per service
```

Steps:
1. Implement stop condition monitor: poll CloudWatch alarms every 10s during execution
2. On alarm ALARM state → send SIGTERM to ansible subprocess
3. Wait 10s for graceful termination → SIGKILL if needed
4. Mark execution as ABORTED (distinct from FAILURE)
5. Add 15s grace period at execution start before monitoring begins
6. Implement baking validator: after SUCCESS, wait configurable period (60-300s by risk)
7. Re-query original CloudWatch alarm + host health endpoint
8. Produce outcome: EFFECTIVE / INEFFECTIVE / DEGRADED / INCONCLUSIVE
9. Feed outcome into circuit breaker (INEFFECTIVE counts as failure)

**Phase 2 (Week 7-8): Enhanced Blast Radius**

```
Files to modify:
  src/guardrails/health_checker.py        — Availability threshold logic
  src/guardrails/plan_validator.py        — AI plan denied commands validation
  config/denied_commands.yml              — Pattern + bounds configuration
  config/risk_classification.yml          — Per-service availability thresholds
```

Steps:
1. Add availability check: query ALB target group healthy count
2. Calculate projected availability: `(current_healthy - 1) / total`
3. If projected < minimum (default 50%) → DENY with explanation
4. Validate AI plans against denied command patterns (regex match)
5. Enforce parameter bounds: max timeout 600s, max 5 hosts, max 10 steps
6. If AI plan blocked → fallback to rule-based matching; audit blocked plan

**Phase 3 (Week 11-12): AWS-Native + UX**

```
Files to modify:
  src/guardrails/maintenance_window.py    — SSM Change Calendar support
  src/guardrails/classifier.py            — DRY_RUN_FIRST mode for CRITICAL
  src/executor.py                         — ansible --check --diff support
  src/guardrails/approval.py             — Fatigue prevention + batch approval
```

Steps:
1. Add SSM `GetCalendarState` integration with 60s cache + YAML fallback
2. CRITICAL risk actions: run `ansible-playbook --check --diff` first
3. Include dry-run output in approval email (`<pre>` block)
4. Track operator trust: 3+ consecutive approvals with SUCCESS → auto-approve
5. Reset trust on any FAILURE/INEFFECTIVE/ABORTED outcome
6. Implement batch approval link for > 5 pending LOW/MEDIUM actions

### Architecture Changes

```
BEFORE:
  Email Approve → _execute_approved_remediation() → executor.execute() [NO GUARDRAILS]
  Pipeline → guardrail_engine.evaluate() → executor.execute()

AFTER:
  ALL PATHS → guardrail_engine.evaluate(skip_approval=True if pre-approved) →
  [Stop Conditions Monitor] → executor.execute() → [Baking Validator] → outcome

  New checks in guardrail chain:
  5b. Availability Threshold (min healthy %)
  6b. Cross-Service Dependency Check
  8.  AI Plan Validation (denied commands + bounds)
  9.  Approval Gate (with fatigue prevention + batch)
  10. Dry-Run for CRITICAL (show diff before real execution)
```

### Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Stop condition polling adds CloudWatch API calls | Cost + latency | Batch alarm queries; 10s interval; only for services with configured alarms |
| Baking period delays incident resolution metrics | Slower MTTR reporting | Track "time-to-action" separately from "time-to-confirmed-fix" |
| Auto-approve (fatigue prevention) reduces safety | Bypassed human review | Trust requires 3+ SUCCESS outcomes; any failure resets trust immediately |
| Dry-run for CRITICAL adds delay | Slower P1 resolution | Dry-run timeout = 60s (short); only for CRITICAL (rare); P1 overrides to APPROVAL_REQUIRED |
| Availability threshold blocks legitimate last-resort restart | Can't restart only instance | Allow override via P1 severity: "P1 overrides availability threshold with escalation" |

---

## Cross-Spec Recommendations

### Overlapping Improvements (Consolidation Required)

| Pattern | Specs Involved | Recommendation |
|---------|---------------|----------------|
| Circuit Breaker | self-healing, concurrent-execution, guardrails | Single `CircuitBreakerRegistry` shared across specs; per-host + fleet-wide in one component |
| Baking/Validation | self-healing (Imp 3), guardrails (Imp 3) | Single `BakingValidator` service used by both orchestrator and guardrail engine |
| Graceful Degradation | self-healing (Imp 8), guardrails (stop conditions) | Unified `DegradationManager` that both pipeline and guardrails consult |
| Alert Deduplication | self-healing (storm), concurrent-execution (dedup) | Storm detector feeds into existing deduplicator; don't duplicate logic |
| Maintenance Windows | guardrails (SSM Calendar), concurrent-execution (fleet breaker) | Fleet breaker suppressed during maintenance; single maintenance state source |
| DynamoDB Access | all specs | Shared DynamoDB client with connection pooling; unified table design |
| CloudWatch Metrics | all specs | Single metrics namespace `AIOps/{env}`; shared metric publisher |

### Reusable Components to Extract

```
src/shared/
├── dynamodb_client.py          — Connection pool, retry config, table references
├── cloudwatch_client.py        — Metrics publisher (batched PutMetricData)
├── alarm_monitor.py            — Poll CloudWatch alarms (used by stop conditions + baking)
├── health_probe.py             — Generic host/service health check (used by multiple specs)
├── config_loader.py            — Hot-reload YAML with fallback (used by all config files)
└── graceful_shutdown.py        — SIGTERM handler (used by main.py + any background task)
```

### Shared Data Stores (DynamoDB Table Design)

```
Single DynamoDB table with composite keys:

PK                              | SK                    | Purpose
────────────────────────────────┼───────────────────────┼─────────────────────────────
LOCK#{host}                     | ACTIVE                | Host lock (concurrency)
INCIDENT#{incident_id}          | METADATA              | Incident memory (AI agent)
INCIDENT#{incident_id}          | EXECUTION#{attempt}   | Execution history
EFFECTIVENESS#{alert}#{playbook}| SCORE                 | Playbook effectiveness
IDEMPOTENCY#{key}               | RESULT                | SSM execution idempotency
TRUST#{alert}#{playbook}#{host} | APPROVAL_HISTORY      | Fatigue prevention trust
CALIBRATION                     | CURVE                 | Confidence calibration data
FLEET_BREAKER                   | STATE                 | Fleet circuit breaker state
```

### Standardization Guidelines

**1. Error Handling Pattern (all specs)**
```python
# Standard: structured error with context, retry decision, and metric emission
class PipelineStageError(Exception):
    def __init__(self, stage: str, incident_id: str, reason: str, retryable: bool):
        self.stage = stage
        self.incident_id = incident_id
        self.reason = reason
        self.retryable = retryable

# Usage: emit metric + structured log on every error
```

**2. Configuration Loading Pattern (all specs)**
```python
# Standard: YAML load → Pydantic validation → hot-reload with fallback
class ConfigManager:
    def load(self, path: str, model: Type[BaseModel]) -> BaseModel:
        """Load YAML, validate with Pydantic, cache, watch for changes."""
    def reload(self) -> None:
        """Hot-reload; on error, keep previous valid config."""
```

**3. Metrics Emission Pattern (all specs)**
```python
# Standard: batch CloudWatch PutMetricData with dimensions
NAMESPACE = f"AIOps/{environment}"
DIMENSIONS = [{"Name": "Service", "Value": service_name}]
# Emit at stage boundaries, not inside loops
```

**4. Audit Logging Pattern (all specs)**
```python
# Standard: structured JSON with mandatory fields
{
    "timestamp": "ISO8601",
    "incident_id": "uuid",
    "stage": "normalize|enrich|match|execute|...",
    "action": "what happened",
    "outcome": "success|failure|skipped|deferred",
    "duration_ms": 123,
    "context": {}  # stage-specific data
}
```

**5. Health Check Pattern (all specs)**
```python
# Standard: /health returns operating mode + dependency status
{
    "status": "healthy|degraded|unhealthy",
    "mode": "full|degraded_no_ai|degraded_no_enrichment|...",
    "dependencies": {
        "dynamodb": "healthy",
        "bedrock": "healthy",
        "ssm": "unhealthy"
    },
    "active_locks": 3,
    "fleet_breaker": "closed",
    "storm_mode": false
}
```

---

## Unified Timeline & Dependencies

### Week-by-Week Execution Plan

```
WEEK 1-2: SAFETY CRITICAL (Must-do first — production bugs)
├── [Guardrails] Fix approval bypass (Imp 1) — 2 days
├── [Concurrency] Graceful shutdown lock handoff — 1 day
├── [Concurrency] Heartbeat-based lock renewal + fencing tokens — 3 days
└── Total: 6 days | Deliverable: No more guardrail bypass, no lock leaks

WEEK 3-4: COST OPTIMIZATION (Quick ROI)
├── [AI] Bedrock prompt caching — 1.5 days
├── [AI] Intelligent model routing — 2.5 days
├── [Deploy] Graviton ARM64 migration — 1.5 days
├── [Deploy] Canary deployment setup — 4 days (can parallel with AI work)
└── Total: 9.5 days | Deliverable: 60-90% AI cost reduction + 40% compute savings

WEEK 5-6: RESILIENCE (Prevent cascading failures)
├── [Self-Heal] Alert storm protection — 4 days
├── [Self-Heal] Resolved alert auto-cancellation — 1.5 days
├── [Concurrency] Idempotency keys — 1.5 days
├── [Concurrency] Bulkhead isolation — 2 days
├── [Concurrency] Fleet-wide circuit breaker — 1.5 days
├── [Guardrails] Stop conditions during execution — 4 days (starts mid-week 5)
└── Total: 15 days (2 engineers parallel) | Deliverable: System survives storms + fleet failures

WEEK 7-8: OBSERVABILITY + RESILIENCE CONT'D
├── [Self-Heal] OpenTelemetry tracing — 3 days
├── [Self-Heal] Graceful degradation modes — 3 days
├── [Guardrails] Baking period validation — 2.5 days
├── [Guardrails] Service availability threshold — 1.5 days
├── [Concurrency] Adaptive ramp-up — 2 days
└── Total: 12 days | Deliverable: Full pipeline traces + degraded mode resilience

WEEK 9-10: INTELLIGENCE (Feedback loops)
├── [Self-Heal] Playbook effectiveness scoring — 4 days
├── [Self-Heal] Alert inhibition & smart grouping — 2.5 days
├── [AI] Evaluation framework + golden dataset — 5 days
├── [AI] Confidence calibration — 2.5 days
├── [Guardrails] AI plan validation — 2.5 days
└── Total: 16.5 days (2 engineers) | Deliverable: System learns + safer AI output

WEEK 11-12: SECURITY + PLATFORM
├── [Deploy] WAF on API Gateway — 1.5 days
├── [Deploy] Drift detection — 1.5 days
├── [Deploy] Multi-account role chaining — 2.5 days
├── [Deploy] SBOM + image signing — 2 days
├── [Guardrails] SSM Change Calendar — 2.5 days
├── [Guardrails] Graduated execution (dry-run) — 2.5 days
├── [Guardrails] Fatigue prevention — 2.5 days
└── Total: 15.5 days (2 engineers) | Deliverable: Hardened security + operator UX

WEEK 13-14: ARCHITECTURE (Long-term improvements)
├── [AI] Strands Agents SDK migration — 6 days
├── [Self-Heal] Structured pipeline events — 2.5 days
├── [Self-Heal] Dynamic AWS enrichment — 2.5 days
├── [Concurrency] Compensating transactions — 4 days
├── [Concurrency] SQS FIFO evaluation + implementation — 4 days
└── Total: 19 days (2 engineers) | Deliverable: Modern agent architecture + event sourcing
```

### Critical Dependencies Between Specs

```
[Guardrails] Baking Validator ──depends-on──→ [Self-Heal] Effectiveness Scoring
  (baking outcome feeds effectiveness score update)

[Concurrency] Fleet Breaker ──integrates-with──→ [Guardrails] Maintenance Window
  (suppress fleet breaker during planned maintenance)

[AI] Model Routing ──uses──→ [Self-Heal] Effectiveness Scoring
  (historical effectiveness determines alert complexity classification)

[Guardrails] Stop Conditions ──shares-with──→ [Self-Heal] Graceful Degradation
  (both poll CloudWatch alarms; share alarm_monitor component)

[Concurrency] Graceful Shutdown ──enables──→ [Deploy] Canary Deployments
  (clean shutdown required for safe ECS task replacement during canary)

[AI] Evaluation Framework ──validates──→ [AI] Strands SDK Migration
  (run evaluation suite to confirm no regression after SDK migration)
```

---

## Testing Strategy

### Unit Tests (Per Improvement)

| Spec | Test File | Key Assertions |
|------|-----------|----------------|
| Self-Heal | `tests/unit/test_storm_detector.py` | Sliding window counts correctly; storm mode activates/deactivates at threshold |
| Self-Heal | `tests/unit/test_inhibitor.py` | Parent-child suppression; resolved alerts cancel pending |
| AI | `tests/unit/test_model_router.py` | Complexity classification correct; routing matches expected model |
| AI | `tests/unit/test_calibration.py` | Isotonic regression produces monotonic curve; cold-start returns 0.5 |
| Concurrency | `tests/unit/test_lock_heartbeat.py` | Heartbeat extends TTL; fencing token increments; stale holder detected |
| Concurrency | `tests/unit/test_fleet_breaker.py` | Trips at threshold; cooldown respected; ramp-up sequence correct |
| Concurrency | `tests/unit/test_bulkhead.py` | Per-service limits enforced; global cap honored; P1 reservation works |
| Guardrails | `tests/unit/test_approval_guardrails.py` | Approved action still blocked by maintenance window/circuit breaker |
| Guardrails | `tests/unit/test_stop_conditions.py` | SIGTERM sent on alarm; ABORTED status distinct from FAILURE |
| Guardrails | `tests/unit/test_plan_validator.py` | Denied patterns block; parameter bounds enforced; allowlist works |

### Integration Tests

| Test File | Scenario |
|-----------|----------|
| `tests/integration/test_full_pipeline.py` | Alert → storm detection → normalize → execute → baking → effective |
| `tests/integration/test_degradation.py` | Bedrock unavailable → auto-switch to rules_only → auto-recover |
| `tests/integration/test_concurrency_e2e.py` | 10 concurrent alerts → bulkhead isolation → P1 priority → completion |
| `tests/integration/test_deployment_safety.py` | Simulate SIGTERM during execution → locks released → no orphans |
| `tests/integration/test_guardrail_unified.py` | Approval endpoint → guardrail evaluation → deny during maintenance |

### Load/Performance Tests

| Test | Target | Acceptance Criteria |
|------|--------|-------------------|
| Alert burst (1000 alerts/minute) | Storm detector + backpressure | System stays responsive; HTTP 429 returned; no OOM |
| Sustained load (100 alerts/minute, 1 hour) | Full pipeline with all improvements | No memory leak; DynamoDB capacity sufficient; metrics accurate |
| Canary deployment under load | Canary + traffic shift | Zero dropped alerts during deployment; locks clean after task rotation |
| Fleet breaker recovery | 10 simultaneous failures → cooldown → ramp-up | Recovery completes in < 15 minutes; no thundering herd |

### Property-Based Tests (Hypothesis)

| Test File | Properties |
|-----------|-----------|
| `tests/property/test_bulkhead.py` | ∀ execution sequences: no service exceeds its bulkhead limit |
| `tests/property/test_storm_detector.py` | ∀ alert streams: rate never exceeds threshold+1 when storm mode active |
| `tests/property/test_lock_safety.py` | ∀ concurrent lock attempts: at most 1 holder per host at any time |
| `tests/property/test_priority_queue.py` | ∀ mixed priority insertions: P1 always dequeued before P3+ |

---

## Infrastructure Changes (CDK)

### New CDK Resources

| Stack | Resource | Purpose |
|-------|----------|---------|
| DataStack | DynamoDB: `PlaybookEffectiveness` table (or GSI on existing) | Effectiveness scoring |
| DataStack | SQS FIFO Queue: `aiops-alerts-{env}.fifo` (optional Phase 5) | Persistent alert queue |
| ObservabilityStack | WAF WebACL: `AiopsWaf` | API Gateway protection |
| ObservabilityStack | CloudWatch Dashboard: `AIOps-Deployments-{env}` | DORA metrics |
| ObservabilityStack | SSM Change Calendar: `aiops-change-calendar-{env}` | Maintenance scheduling |
| ComputeStack | ECS Deployment Controller: `CODE_DEPLOY` (prod) | Canary deployments |
| ComputeStack | CodeDeploy Application + Deployment Group | Traffic shifting |

### CDK Context Updates

```python
# cdk.json additions
{
  "context": {
    "graviton": true,              # ARM64 for staging+prod
    "canaryDeployment": true,      # Canary for prod only
    "wafEnabled": true,            # WAF on API Gateway
    "driftDetection": true,        # Daily drift checks
    "deployRoleArn": {             # Multi-account
      "dev": "arn:aws:iam::111:role/AIOpsDeployRole",
      "prod": "arn:aws:iam::222:role/AIOpsDeployRole"
    }
  }
}
```

### IAM Policy Additions

```yaml
# New permissions needed by ECS task role:
- ssm:GetCalendarState            # Maintenance calendar check
- cloudwatch:DescribeAlarms       # Stop conditions + baking validation
- ec2:DescribeInstances           # Dynamic enrichment
- servicediscovery:DiscoverInstances  # Cloud Map enrichment
- elasticloadbalancing:DescribeTargetHealth  # Availability threshold
- dynamodb:UpdateItem (PlaybookEffectiveness)  # Score updates
- xray:PutTraceSegments           # OpenTelemetry export
```

---

## Rollout Strategy

### Feature Flags & Environment Progression

| Feature | Dev | Staging | Prod | Feature Flag |
|---------|-----|---------|------|--------------|
| Storm Detection | ON | ON | ON (threshold=50) | `STORM_DETECTION_ENABLED` |
| Prompt Caching | ON | ON | ON | Always on (Bedrock-native) |
| Model Routing | ON | ON | ON (conservative) | `MODEL_ROUTING_ENABLED` |
| Graviton | OFF (x86 for local) | ON | ON | CDK context `graviton` |
| Canary Deploy | OFF (rolling) | OFF (rolling) | ON | CDK context `canaryDeployment` |
| Fleet Breaker | ON | ON | ON (threshold=5) | `FLEET_BREAKER_ENABLED` |
| Bulkhead | ON | ON | ON | Always on (config-driven) |
| OTel Tracing | ON (Jaeger) | ON (X-Ray) | ON (X-Ray, 10% sample) | `OTEL_TRACING_ENABLED` |
| Effectiveness Scoring | ON | ON | ON | Always on |
| WAF | OFF | ON | ON | CDK context `wafEnabled` |
| Auto-Approve Trust | OFF | ON | ON (conservative) | `FATIGUE_PREVENTION_ENABLED` |

### Canary/Phased Deployment Plan (for the improvements themselves)

```
Phase 0 (Safety fixes):
  Deploy to DEV → validate with synthetic alerts → deploy to STAGING →
  run integration tests → deploy to PROD (rolling, with health gate)
  Rollback: revert to previous task definition

Phase 1 (Cost optimization):
  Deploy to DEV → measure cost metrics → deploy to STAGING for 3 days →
  validate cost reduction matches expected → deploy to PROD
  Rollback: disable model routing flag → falls back to Claude-always

Phase 2+ (Resilience/Intelligence):
  Deploy to DEV → full test suite → deploy to STAGING for 1 week →
  synthetic load test → deploy to PROD via canary (10%→50%→100%)
  Rollback: CodeDeploy automatic rollback on alarm trigger
```

### Rollback Plan (Per Improvement)

| Improvement | Rollback Mechanism | Recovery Time |
|-------------|-------------------|---------------|
| Storm Detection | Set `STORM_DETECTION_ENABLED=false` → redeploy | < 5 min |
| Prompt Caching | Remove `cache_control` from prompt → standard invocation | < 5 min |
| Model Routing | Set `MODEL_ROUTING_ENABLED=false` → all alerts use Claude | < 5 min |
| Graviton | Change CDK `cpuArchitecture: X86_64` → redeploy | ~10 min |
| Canary Deploy | Switch back to ECS rolling update in CDK | Next deploy |
| Heartbeat Locks | Heartbeat is additive; disable by stopping background task | < 5 min |
| Fleet Breaker | Set threshold to 999 (effectively disabled) | < 5 min |
| WAF | Set WAF to COUNT mode (monitor only, don't block) | < 2 min |
| Strands SDK | Feature flag: `AGENT_MODE=legacy` uses old custom agent | < 5 min |

---

## Data Migration Strategy

### DynamoDB Schema Evolution

No destructive migrations required. All changes are additive:

1. **PlaybookEffectiveness**: New table or GSI — no existing data affected
2. **Idempotency Records**: New PK prefix `IDEMPOTENCY#` — no collision with existing
3. **Fencing Token**: New attribute on existing lock records — backward compatible (old records have no token = treated as token 0)
4. **Trust History**: New PK prefix `TRUST#` — no collision
5. **Calibration Curve**: New singleton record — no migration needed

**Strategy**: Deploy code that writes new attributes first, then deploy code that reads them. This ensures no read-before-write errors during rolling deployment.

### Configuration File Evolution

All new configs are additive files (no modification to existing):
- `config/inhibition_rules.yml` — new file
- `config/bulkhead_limits.yml` — new file
- `config/model_routing.yml` — new file

Existing files extended (backward compatible):
- `config/playbook_mapping.yml` — add optional `compensate_path` field
- `config/risk_classification.yml` — add optional `availability_thresholds` section
- `config/stop_conditions.yml` — already exists, extend with per-service alarms

---

## Cost Impact Summary

### Monthly Cost Changes (Estimated for 100 alerts/day baseline)

| Category | Current | After Improvements | Savings |
|----------|---------|-------------------|---------|
| Bedrock AI invocations | $9/month | $1.20/month | 87% ↓ |
| ECS Fargate compute (2 tasks) | $29/month | $18/month | 38% ↓ |
| DynamoDB (additional writes for heartbeats, effectiveness) | $0 | +$2/month | +$2 |
| CloudWatch (additional metrics, alarms) | $5/month | +$8/month | +$8 |
| WAF (WebACL + rules) | $0 | +$6/month | +$6 |
| SQS FIFO (if adopted) | $0 | +$1/month | +$1 |
| X-Ray tracing | $0 | +$3/month | +$3 |
| **Net Monthly** | **$43/month** | **$39/month** | **$4/month saved** |

**Key Insight**: Cost optimizations (Graviton + prompt caching + model routing) more than offset the new service costs. Net effect is cost-neutral with massively improved capabilities.

### Scaling Cost at 1000 alerts/day

| Category | Current | After | Delta |
|----------|---------|-------|-------|
| Bedrock | $90/month | $12/month | -87% |
| ECS (5 tasks for throughput) | $73/month | $44/month | -40% |
| DynamoDB | $5/month | $12/month | +$7 |
| Total | $168/month | $68/month | -60% overall |

At scale, the cost optimization improvements produce significant savings.

---

## Final Summary: Production Readiness Scorecard

### Before Improvements

| Dimension | Score | Gap |
|-----------|-------|-----|
| Scalability | 6/10 | No storm protection; global semaphore bottleneck |
| Reliability | 5/10 | Lock leaks on deploy; split-brain possible; no auto-resolution |
| Observability | 5/10 | Logs only; no tracing; no effectiveness feedback |
| Security | 6/10 | Guardrail bypass via email; no WAF; no image signing |
| Performance | 6/10 | Always uses expensive model; x86 only |
| Deployment Safety | 5/10 | Rolling update (all-at-once); no canary; no drift detection |
| **Overall** | **5.5/10** | |

### After Improvements

| Dimension | Score | Key Additions |
|-----------|-------|---------------|
| Scalability | 9/10 | Storm protection + bulkheads + fleet breaker + FIFO queue |
| Reliability | 9/10 | Heartbeat locks + graceful shutdown + degradation modes + sagas |
| Observability | 9/10 | OpenTelemetry + structured events + DORA + effectiveness scoring |
| Security | 9/10 | Unified execution path + WAF + SBOM + AI plan validation + multi-account |
| Performance | 9/10 | Prompt caching + model routing + Graviton + caching enrichment |
| Deployment Safety | 9/10 | Canary + drift detection + auto-rollback + graceful shutdown |
| **Overall** | **9/10** | |

---

## Immediate Next Actions

1. **This week**: Fix guardrail bypass (Spec 5, Imp 1) — safety-critical production bug
2. **This week**: Add SIGTERM handler (Spec 4, Imp 10) — prevents lock leaks every deploy
3. **Next week**: Implement heartbeat locks (Spec 4, Imp 1) — prevents split-brain
4. **Next week**: Enable prompt caching (Spec 2, Imp 1) — immediate 90% cost savings
5. **Sprint planning**: Add Week 1-4 items to backlog with story points from effort estimates

---

*End of Production Implementation Plan*
