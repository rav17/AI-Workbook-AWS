# Self-Healing Infrastructure — Improvement Proposals

## Document Information

| Field | Value |
|-------|-------|
| **Author** | Ravindra Yadav |
| **Date** | August 2026 |
| **Status** | Proposed |
| **Spec** | `.kiro/specs/self-healing-infrastructure` |
| **Informed By** | MAPE-K Autonomic Computing Loop, AWS CloudWatch Anomaly Detection, AWS EventBridge Auto-Remediation, OpenTelemetry Distributed Tracing, Prometheus Alertmanager Grouping/Inhibition, Google SRE Alerting on SLOs, Elastic AIOps Remediation, Research papers on self-healing effectiveness |

---

## Executive Summary

The self-healing-infrastructure spec defines the core pipeline: webhook → normalize →
enrich → match → execute → notify. This pipeline is already well-implemented. The
improvements below address gaps that become visible at production scale and align the
system with the MAPE-K (Monitor-Analyze-Plan-Execute-Knowledge) autonomic computing
model — the academic standard for self-healing systems.

### Current Pipeline (Implemented)

```
Alertmanager → Webhook → Normalize → Enrich → Match → Execute → Notify
                                                              ↓
                                                         Audit Log
```

### Target Pipeline (After Improvements)

```
                    ┌──────────── Knowledge Store (Feedback Loop) ────────────┐
                    │                                                          │
Alertmanager → [Storm Filter] → Normalize → Enrich → [Smart Match] → Execute → [Verify]
                                                          ↑                        ↓
                                              Playbook Effectiveness         Notify + Learn
                                              Scoring from K-Store
```

---

## Current Strengths (Already Well-Implemented)

- ✅ FastAPI webhook with validation, size limits, Content-Type enforcement
- ✅ Alertmanager payload normalization with severity mapping and defaults
- ✅ YAML-based asset inventory enrichment with priority lookup
- ✅ Best-fit playbook matching with tie-breaking and hot-reload
- ✅ Ansible subprocess execution with timeout, output capture, concurrency
- ✅ Multi-channel notifications (email/Slack/PagerDuty) with retry
- ✅ Orchestrator with 50 concurrent pipelines, stage failure handling
- ✅ JSON-lines audit logging with rotation
- ✅ Prometheus metrics exposition
- ✅ Docker containerization with SIGTERM handling

---

## Improvement 1: Alert Storm Protection (Backpressure & Rate Limiting)

### Priority: P1 — Prevents System Overload

### Problem Statement

The webhook currently accepts up to 10 concurrent requests with no upper bound.
During an infrastructure-wide outage (network partition, DNS failure), Alertmanager
can fire hundreds of alerts simultaneously. The system processes all of them,
overwhelming the executor (10 concurrent limit), flooding the notification channels,
and potentially causing cascading failures in the self-healing system itself.

### Industry Precedent

- [Prometheus Alertmanager Grouping](https://prometheus.io/docs/alerting/alertmanager/):
  Groups alerts by labels before routing, sending one notification per group
- [Google SRE: Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/):
  Recommends rate-limiting alert processing during low-signal/high-noise periods
- Webhook scaling pattern: "receive-fast/process-later" with queue as shock absorber

### Proposed Improvement

```
Alert Storm Detection:
1. Track incoming alert rate (sliding 60-second window)
2. IF rate > configurable threshold (default 50 alerts/minute):
   - Enter STORM mode
   - Group alerts by (alertname + service_name) — process one per group
   - Suppress duplicate groups for storm_suppression_window (default 120s)
   - Send ONE "alert storm detected" notification with grouped summary
3. IF rate drops below threshold for 2 consecutive minutes:
   - Exit STORM mode
   - Resume normal per-alert processing

Backpressure:
- When pipeline queue depth > configurable limit (default 100):
  - Respond HTTP 429 (Too Many Requests) with Retry-After header
  - Alertmanager will retry with backoff
  - Log backpressure activation event
```

### Acceptance Criteria

1. THE system SHALL track incoming alert rate in a 60-second sliding window
2. WHEN rate exceeds threshold, THE system SHALL group alerts by (alertname + service)
   and process only one representative per group
3. THE system SHALL send a single "alert storm" notification summarizing all suppressed groups
4. THE system SHALL respond HTTP 429 when internal queue depth exceeds capacity
5. Storm mode activation/deactivation SHALL be logged and metriced

### Effort Estimate: 2-3 days

---

## Improvement 2: Distributed Tracing with OpenTelemetry

### Priority: P2 — Pipeline Observability

### Problem Statement

The current system logs each pipeline stage independently. When debugging a failure
("why did incident X not get remediated?"), operators must correlate multiple log
entries by incident_id manually. There's no visual trace of the full pipeline
showing timing, dependencies, and where bottlenecks occur.

### Industry Precedent

- [OpenTelemetry Tracing](https://opentelemetry.io/docs/concepts/observability-primer/):
  Industry standard for distributed tracing across services
- [AWS X-Ray](https://aws.amazon.com/blogs/dotnet/net-observability-with-opentelemetry-part-3-distributed-tracing-using-aws-x-ray/):
  Distributed tracing for AWS services with service map visualization

### Proposed Improvement

```
Add OpenTelemetry tracing to the pipeline:

Root span: "process_alert" (incident_id as trace context)
  ├── Child span: "normalize" (duration, alert_count)
  ├── Child span: "enrich" (duration, lookup_key, enriched=true/false)
  ├── Child span: "match" (duration, matched_rule, playbook_path)
  ├── Child span: "guardrail_evaluate" (duration, decision, checks_passed)
  ├── Child span: "execute" (duration, status, return_code)
  │     └── Child span: "ansible_subprocess" (command, timeout)
  ├── Child span: "baking_validate" (duration, outcome)
  └── Child span: "notify" (duration, channels_sent, failures)

Export traces to:
- AWS X-Ray (via ADOT Collector) for production
- Jaeger (local Docker) for development
```

### Acceptance Criteria

1. EACH pipeline execution SHALL produce a single trace with child spans per stage
2. THE trace SHALL include incident_id, alert_name, and severity as span attributes
3. Traces SHALL be exported via OpenTelemetry Protocol (OTLP) to a configurable endpoint
4. THE system SHALL add trace context headers to outgoing notifications (for end-to-end tracing)
5. Tracing SHALL be opt-in via environment variable `OTEL_TRACING_ENABLED` (default: false)

### Effort Estimate: 2-3 days

---

## Improvement 3: Playbook Effectiveness Scoring (Knowledge Store)

### Priority: P2 — Closes the MAPE-K Feedback Loop

### Problem Statement

The current system has no feedback loop. A playbook that fails 80% of the time is
still matched with the same priority as one that succeeds 95% of the time. The
AI agent learns from history (via DynamoDB), but the rule-based PlaybookMapper is
completely static — it doesn't learn which playbooks actually work.

### Industry/Academic Precedent

- [MAPE-K Loop](https://api.emergentmind.com/topics/mape-k-loop): The "K" (Knowledge)
  component maintains a shared, versioned knowledge base that the Analyze and Plan
  phases use to improve decisions over time
- [Research: "Intelligent Feedback-Driven Recovery Loops"](https://www.researchgate.net/publication/390947114):
  "Continuously learns from failures, adjusts remediation policies in real time,
  and closes the loop with contextual feedback"
- [Elastic AIOps](https://www.elastic.co/observability-labs/blog/aiops-remediation-elastic-worklfows):
  "Self-healing systems that detect, analyse, and fix infrastructure issues automatically"

### Proposed Improvement

```
Maintain a playbook effectiveness score per (alert_name, playbook, host_pattern):

effectiveness_score = successes / (successes + failures + ineffectives)

Usage in PlaybookMapper:
- When multiple rules match with equal specificity:
  - Select the rule with HIGHEST effectiveness_score (not earliest in file)
- When a playbook's score drops below threshold (default 0.3):
  - Log WARNING: "Playbook {path} has {score} effectiveness for {alert_name}"
  - Route to AI agent instead of rule-based execution
  - Send weekly "playbook health" digest email to ops team

Score storage:
- DynamoDB table: PlaybookEffectiveness
  PK: {alert_name}#{playbook_path}
  Attributes: successes, failures, ineffectives, last_updated, score
- Updated after every baking period validation result
```

### Acceptance Criteria

1. THE system SHALL maintain success/failure/ineffective counts per (alert, playbook) pair
2. WHEN multiple rules match with equal specificity, THE PlaybookMapper SHALL prefer
   the rule with highest effectiveness_score
3. WHEN effectiveness_score < 0.3, THE system SHALL route to AI agent instead of rule-based
4. THE effectiveness store SHALL be updated after baking period validation
5. A weekly digest SHALL summarize playbooks with declining effectiveness

### Effort Estimate: 3-4 days

---

## Improvement 4: Alert Inhibition and Smart Grouping

### Priority: P2 — Reduces Noise, Prevents Redundant Remediations

### Problem Statement

When a database goes down, every service that depends on it fires alerts (API timeout,
connection refused, health check failed). The system currently processes each alert
independently, potentially executing 5 different playbooks when only the database
restart is needed. The Alertmanager has inhibition rules, but these are often
incomplete or misconfigured.

### Industry Precedent

- [Prometheus Alertmanager Inhibition](https://prometheus.io/docs/alerting/alertmanager/):
  "Takes care of silencing and inhibition of alerts" — suppress symptom alerts when
  the root cause alert is already firing
- [OpenTelemetry Alert Deduplication](https://oneuptime.com/blog/post/2026-02-06-alert-deduplication-grouping-opentelemetry/view):
  "When your database goes down, every service that depends on it fires its own
  error rate alert"

### Proposed Improvement

```
Add a pre-processing stage between Normalize and Enrich:

Stage 1.5: Smart Grouping & Inhibition
1. Check if incoming alert matches an active "root cause" alert pattern:
   - If parent service (from dependency graph) already has an active incident:
     - Suppress the dependent alert
     - Link it to the parent incident
     - Log: "Suppressed {alert} — covered by parent incident {parent_id}"
2. Group alerts arriving within 30-second window with same target host:
   - Process as a single batch
   - Select the highest-severity alert as the "primary"
   - Attach others as "related alerts" in the audit record
3. Respect Alertmanager's resolved status:
   - If alert status = "resolved" → cancel any pending execution for that alert
   - Don't process already-resolved alerts through the pipeline

Configuration:
  inhibition_rules:
    - source_alert: DatabaseDown
      target_alerts: [APITimeout, ConnectionRefused, HealthCheckFailed]
      condition: same(service_dependency_of)
```

### Acceptance Criteria

1. THE system SHALL suppress alerts whose parent service already has an active incident
2. THE system SHALL group alerts for the same host within a 30-second window
3. WHEN alert status is "resolved", THE system SHALL skip pipeline processing
4. Inhibition rules SHALL be configurable in YAML
5. Suppressed alerts SHALL still appear in audit log (with reason)

### Effort Estimate: 2-3 days

---

## Improvement 5: Resolved Alert Auto-Cancellation

### Priority: P2 — Prevents Unnecessary Remediations

### Problem Statement

Alertmanager sends both "firing" and "resolved" payloads. The current system
processes both through the pipeline. If an alert fires at T=0 and resolves at T=30s
(auto-recovery), but the pipeline is slow (queued actions, approval pending), the
system may still execute a remediation for an already-resolved issue — wasting
resources and potentially disrupting a now-healthy service.

### Proposed Improvement

```
Track active incidents and honor "resolved" signals:

1. Maintain in-memory set of active incidents: {incident_id: status}
2. When alert with status="resolved" arrives:
   a. If incident_id has a PENDING execution in queue → cancel it
   b. If incident_id has an ACTIVE execution running → let it complete
      (don't interrupt mid-execution)
   c. If incident_id was already executed → log "resolved after remediation"
   d. Send "auto-resolved" notification (no action taken)
3. When approval token is clicked for an already-resolved incident:
   - Show HTML: "This alert has already resolved. No action needed."
   - Don't execute the playbook

Metrics:
- AutoResolvedBeforeRemediation: count of alerts that resolved before execution
- This metric indicates self-recovery capacity of the infrastructure
```

### Acceptance Criteria

1. WHEN a resolved alert arrives, THE system SHALL cancel any pending (not yet executing)
   actions for that incident
2. WHEN a resolved alert arrives for an actively executing action, THE system SHALL NOT
   interrupt the execution (fail-safe: let it complete)
3. THE approval endpoint SHALL check if the incident has resolved before executing
4. THE system SHALL track auto-resolution rate as a metric

### Effort Estimate: 1-2 days

---

## Improvement 6: Enrichment from Live AWS Sources (Dynamic Inventory)

### Priority: P3 — Replaces Static YAML with Live Data

### Problem Statement

The asset inventory is a static YAML file (`config/asset_inventory.yml`). When
instances are launched/terminated by Auto Scaling, the YAML becomes stale. The system
marks alerts for new instances as "unenriched" because they don't exist in the static file.

### AWS Precedent

- [AWS Systems Manager Inventory](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-inventory.html):
  Collects metadata about managed instances automatically
- [EC2 Describe Instances](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeInstances.html):
  Live query for instance metadata, tags, and state
- [AWS Cloud Map](https://docs.aws.amazon.com/cloud-map/latest/api/Welcome.html):
  Service discovery with health-aware instance registration

### Proposed Improvement

```
Support multiple enrichment sources (fallback chain):

1. Primary: AWS Cloud Map / EC2 Tags (live, always current)
   - Query by instance-id or private IP
   - Extract: hostname, service_name, environment from tags
2. Secondary: SSM Managed Instance metadata
   - Query by instance-id
   - Get: platform, agent version, last ping time
3. Tertiary: Static YAML (fallback for non-AWS or offline environments)
   - Current behavior preserved as last resort

Caching: 5-minute TTL on AWS API results to avoid rate limiting
Timeout: 2-second total for live lookup, then fall back to YAML
```

### Acceptance Criteria

1. THE Enricher SHALL support configurable source priority (aws/ssm/yaml)
2. AWS lookups SHALL be cached with configurable TTL (default 5 minutes)
3. IF live lookup fails or times out, THE system SHALL fall back to static YAML
4. NEW instances (from ASG scaling) SHALL be enrichable without config changes
5. THE system SHALL log which enrichment source was used for each alert

### Effort Estimate: 2-3 days

---

## Improvement 7: Structured Pipeline Events (Event Sourcing)

### Priority: P3 — Enables Replay and Analytics

### Problem Statement

The current audit log is append-only JSON lines per incident. It captures the final
state but not the journey. If an operator asks "show me all alerts that were suppressed
by deduplication last week" or "which playbooks were matched but not executed due to
guardrails?", there's no efficient way to query this.

### Proposed Improvement

```
Emit structured events to a DynamoDB stream or CloudWatch Logs Insights:

Event types:
- alert.received         {incident_id, alert_name, severity, timestamp}
- alert.normalized       {incident_id, severity_mapped, fields_defaulted}
- alert.enriched         {incident_id, source, hostname, service}
- alert.unenriched       {incident_id, reason, lookup_key}
- playbook.matched       {incident_id, rule_name, playbook_path, score}
- playbook.unmatched     {incident_id, rules_evaluated, reason}
- guardrail.evaluated    {incident_id, decision, checks, duration}
- execution.started      {incident_id, playbook, host, extra_vars}
- execution.completed    {incident_id, status, duration, output_truncated}
- execution.aborted      {incident_id, stop_condition, partial_output}
- baking.result          {incident_id, outcome, alarm_resolved, host_healthy}
- notification.sent      {incident_id, channels, latency}
- alert.suppressed       {incident_id, reason, parent_incident_id}
- alert.auto_resolved    {incident_id, resolution_time_seconds}

Benefits:
- CloudWatch Logs Insights queries across all events
- DynamoDB streams for real-time dashboarding
- Replay capability: re-process historical alerts through updated pipeline
```

### Acceptance Criteria

1. EACH pipeline stage transition SHALL emit a structured event with incident_id
2. Events SHALL be queryable by type, incident_id, time range, and outcome
3. THE event schema SHALL be versioned (schema_version field) for forward compatibility
4. Events SHALL be emitted within 1 second of the stage completing

### Effort Estimate: 2-3 days

---

## Improvement 8: Graceful Degradation Modes

### Priority: P3 — System Resilience Under Partial Failure

### Problem Statement

If a single dependency fails (DynamoDB down, SES throttled, Bedrock unavailable),
the system currently continues processing but may produce incomplete results.
There's no explicit "degraded mode" that adjusts behavior based on which
components are available.

### Proposed Improvement

```
Define explicit operating modes based on dependency health:

FULL MODE (all dependencies healthy):
  - Normal pipeline: normalize → enrich → match → guardrails → execute → baking → notify

DEGRADED MODE - NO ENRICHMENT (Asset Inventory unavailable):
  - Skip enrichment, use alert labels directly as target host
  - Log warning per alert: "operating without enrichment"
  - Still execute playbooks (host from 'instance' label)

DEGRADED MODE - NO AI (Bedrock unavailable):
  - Automatically switch operating_mode to "rules_only"
  - Skip correlation window (process alerts individually)
  - Resume AI mode when Bedrock connectivity restored

DEGRADED MODE - NO NOTIFICATIONS (SES/Slack down):
  - Continue executing remediations (don't block on notification failure)
  - Buffer notifications for retry when channel recovers
  - Log to CloudWatch as fallback notification channel

DEGRADED MODE - NO EXECUTION (SSM/Ansible unavailable):
  - Accept and process alerts through match stage
  - Queue matched actions for later execution
  - Send "execution deferred" notification to operator
  - Resume execution when connectivity restored

Health check at /health reports which mode is active.
```

### Acceptance Criteria

1. THE system SHALL detect partial dependency failures via health probes
2. THE system SHALL automatically enter the appropriate degraded mode
3. THE system SHALL automatically recover to FULL mode when dependencies heal
4. THE /health endpoint SHALL report the current operating mode
5. Mode transitions SHALL be logged and metriced

### Effort Estimate: 2-3 days

---

## Implementation Plan

### Phase 1: Storm Protection & Auto-Resolution (Week 1-2)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 1.1 | Alert storm detector (sliding window + grouping) | `src/app.py`, `src/storm_detector.py` | 1.5d |
| 1.2 | HTTP 429 backpressure when queue full | `src/app.py` | 0.5d |
| 1.3 | Resolved alert auto-cancellation | `src/orchestrator.py` | 1d |
| 1.4 | Cancel pending approvals for resolved alerts | `src/approval_handler.py`, `src/app.py` | 0.5d |
| 1.5 | Storm mode metrics + notifications | `src/metrics.py`, `src/notification.py` | 0.5d |

**Deliverable:** System survives alert storms without overload; auto-resolved alerts don't trigger unnecessary remediations.

### Phase 2: Feedback Loop & Smart Matching (Week 2-3)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 2.1 | Playbook effectiveness scoring data model | `src/models.py`, DynamoDB table | 1d |
| 2.2 | Update scores after baking validation | `src/orchestrator.py` | 0.5d |
| 2.3 | Integrate scores into PlaybookMapper tie-breaking | `src/playbook_mapper.py` | 1d |
| 2.4 | Route low-score playbooks to AI agent | `src/orchestrator.py` | 0.5d |
| 2.5 | Alert inhibition pre-processing stage | `src/inhibitor.py` | 1.5d |
| 2.6 | Inhibition rules config | `config/inhibition_rules.yml` | 0.5d |

**Deliverable:** System learns which playbooks work; dependent alerts are suppressed when root cause is active.

### Phase 3: Observability & Dynamic Enrichment (Week 3-4)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 3.1 | OpenTelemetry tracing integration | `src/orchestrator.py`, `src/tracing.py` | 2d |
| 3.2 | Span annotations for each pipeline stage | All pipeline components | 1d |
| 3.3 | AWS EC2/Cloud Map dynamic enrichment source | `src/enricher.py` | 2d |
| 3.4 | Enrichment source fallback chain | `src/enricher.py` | 0.5d |
| 3.5 | Structured pipeline events | `src/events.py`, `src/orchestrator.py` | 2d |

**Deliverable:** Full pipeline traces visible in X-Ray; new instances auto-enrichable; queryable event history.

### Phase 4: Resilience (Week 4-5)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 4.1 | Dependency health monitoring | `src/app.py` (health endpoint extension) | 1d |
| 4.2 | Degraded mode state machine | `src/degradation_manager.py` | 1.5d |
| 4.3 | Auto-recovery when dependencies heal | `src/degradation_manager.py` | 0.5d |
| 4.4 | Notification buffering for channel recovery | `src/notification.py` | 1d |
| 4.5 | Integration tests for degraded modes | `tests/integration/test_degradation.py` | 1d |

**Deliverable:** System explicitly handles partial failures; auto-recovers without restart.

---

## Total Effort Summary

| Phase | Duration | Effort | Key Deliverable |
|-------|----------|--------|-----------------|
| Phase 1: Storm Protection | Week 1-2 | 4 days | Alert storm survival + auto-resolution |
| Phase 2: Feedback Loop | Week 2-3 | 5 days | Effectiveness scoring + inhibition |
| Phase 3: Observability | Week 3-4 | 7.5 days | Tracing + dynamic enrichment + events |
| Phase 4: Resilience | Week 4-5 | 5 days | Graceful degradation modes |
| **Total** | **5 weeks** | **~21.5 days** | |

---

## New Files to Create

```
src/
├── storm_detector.py          ← Alert storm detection + grouping
├── inhibitor.py               ← Alert inhibition pre-processing
├── tracing.py                 ← OpenTelemetry tracing setup
├── events.py                  ← Structured pipeline event emitter
├── degradation_manager.py     ← Graceful degradation state machine
└── (existing files modified)

config/
├── inhibition_rules.yml       ← Parent-child alert suppression rules
└── (existing files extended)
```

---

## Metrics Impact

### New CloudWatch Metrics

| Metric | Description |
|--------|-------------|
| `AlertStormActivated` | Storm mode entered (count) |
| `AlertsSuppressedByStorm` | Alerts grouped/suppressed during storm |
| `AlertsAutoResolved` | Alerts that resolved before remediation started |
| `PlaybookEffectivenessScore` | Per-playbook success rate (gauge) |
| `AlertsInhibited` | Alerts suppressed by dependency inhibition |
| `PipelineTraceDuration` | End-to-end trace duration (p50/p95/p99) |
| `EnrichmentSourceUsed` | Which source provided enrichment (aws/ssm/yaml) |
| `DegradedModeActive` | Which degraded mode is active (dimension) |

---

## References

- [MAPE-K Autonomic Computing Loop](https://api.emergentmind.com/topics/mape-k-loop)
- [AWS CloudWatch Anomaly Detection + Auto-Remediation](https://aws.amazon.com/blogs/mt/how-to-set-up-cloudwatch-anomaly-detection-to-set-dynamic-alarms-automate-actions-and-drive-online-sales/)
- [AWS EventBridge Custom CloudWatch Alarm Responses](https://repost.aws/knowledge-center/eventbridge-custom-cloudwatch-alarm-responses)
- [Prometheus Alertmanager Grouping & Inhibition](https://prometheus.io/docs/alerting/alertmanager/)
- [Google SRE: Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
- [OpenTelemetry Distributed Tracing](https://opentelemetry.io/docs/concepts/observability-primer/)
- [Elastic AIOps: Self-Healing Architecture](https://www.elastic.co/observability-labs/blog/aiops-remediation-elastic-worklfows)
- [Red Hat: How to Architect Self-Healing Infrastructure](https://www.redhat.com/en/blog/self-healing-infrastructure)
- [Research: Intelligent Feedback-Driven Recovery Loops (2025)](https://www.researchgate.net/publication/390947114)
- [Research: MAPE-K Self-Healing Controller with ECA Rules (2026)](http://www.scitepress.org/Papers/2026/147981/147981.pdf)
- [AWS Well-Architected Agentic AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentic-ai-lens.html)

---

## Future Improvements (Not for Current Implementation)

### Future: CloudWatch Anomaly Detection Integration

Replace static alarm thresholds with ML-based anomaly detection bands. CloudWatch
automatically learns normal patterns and creates dynamic thresholds. Deferred because
it requires metric history (>2 weeks of data) and adds complexity to alarm management.

### Future: Multi-Region Alert Aggregation

Aggregate alerts across multiple AWS regions into a single pipeline with region-aware
playbook routing. Deferred until the platform expands beyond single-region deployment.

### Future: Automated Playbook Generation from AI

When the AI agent successfully reasons a fix for an unmatched alert, automatically
generate a draft Ansible playbook from the AI's suggested steps and submit it as a
PR for ops team review. This closes the loop from "AI one-off fix" to "permanent
automation." Deferred because it requires validated AI output and human PR review workflow.
