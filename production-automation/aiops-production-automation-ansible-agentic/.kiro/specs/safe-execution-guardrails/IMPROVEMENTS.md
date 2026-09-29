# Safe Execution Guardrails — Improvement Proposals

## Document Information

| Field | Value |
|-------|-------|
| **Author** | Ravindra Yadav |
| **Date** | August 2026 |
| **Status** | Proposed |
| **Spec** | `.kiro/specs/safe-execution-guardrails` |
| **Informed By** | AWS SSM Change Calendar, AWS FIS Stop Conditions, ECS Deployment Circuit Breaker, SageMaker Deployment Guardrails, Amazon Bedrock Guardrails, AWS CodeDeploy Auto-Rollback, AWS Well-Architected Reliability Pillar |

---

## Executive Summary

This document proposes 10 improvements to the existing 7-layer Safe Execution Guardrails
engine. These recommendations are derived from analysis of:

1. A **critical bug** where the email approval flow bypasses all guardrails
2. AWS-native services that implement similar safety patterns at scale
3. Industry SRE/AIOps best practices for automated remediation safety

The improvements are prioritized by impact and effort, with the top items addressing
safety-critical gaps that could lead to unintended infrastructure damage.

### Current State (7 Guardrail Checks)

```
1. Self-Protection Guard     → Blocks targeting automation host
2. Maintenance Window Manager → Defers during planned maintenance
3. Circuit Breaker           → Halts after consecutive failures
4. Concurrency Guard         → Prevents duplicate/parallel remediations
5. Blast Radius Classifier   → Classifies risk (LOW/MEDIUM/HIGH/CRITICAL)
6. Health Checker            → Verifies peer health before action
7. Approval Gate             → Human approval for HIGH/CRITICAL risk
```

### Proposed State (10 Additional Capabilities)

```
 8. Unified Execution Path        → All paths route through guardrails
 9. Stop Conditions               → Abort execution if system degrades
10. Post-Execution Baking Period  → Verify fix actually worked
11. Service Availability Threshold → Enforce minimum healthy percentage
12. AI Remediation Plan Validation → Block dangerous AI-generated actions
13. SSM Change Calendar Integration→ Native AWS maintenance awareness
14. Graduated Execution Modes     → Dry-run for CRITICAL actions
15. Pre-Execution State Snapshot  → Enable rollback on failure
16. Cross-Service Dependency Check→ Cascade-aware blast radius
17. Escalation Fatigue Prevention → Auto-approve trusted patterns
```

---

## Improvement 1: Unified Execution Path (Critical Bug Fix)

### Priority: P1 — Critical Safety Gap

### Problem Statement

When an operator clicks "Approve Auto-Remediation" in the email, the request hits
`GET /approve/{token}` which calls `_execute_approved_remediation()`. This function
directly calls `executor.execute()` — **completely bypassing** all 7 guardrail checks
and the concurrency manager.

This means an approved remediation can:
- Execute against a protected host (self-protection bypass)
- Execute during a maintenance window
- Execute despite the circuit breaker being OPEN
- Execute in parallel with another remediation on the same host
- Execute without traffic draining
- Execute without peer health verification

### AWS Precedent

AWS CodeDeploy implements the principle that even after human approval, CloudWatch
alarms can still trigger an automatic rollback. Human approval ≠ bypassing all safety.

### Proposed Requirement

**Requirement 10: Unified Execution Path**

> ALL remediation execution paths — the automated pipeline, the email approval endpoint,
> and any future API-triggered execution — SHALL route through the GuardrailEngine
> before invoking the executor.
>
> When execution is triggered by an explicit human approval (email click), the
> Approval Gate check (check #7) SHALL be skipped, but all other 6 checks SHALL
> still be evaluated:
> 1. Self-Protection Guard — still evaluated
> 2. Maintenance Window Manager — still evaluated
> 3. Circuit Breaker — still evaluated
> 4. Concurrency Guard — still evaluated
> 5. Blast Radius Classifier — still evaluated (for risk context)
> 6. Health Checker — still evaluated
> 7. Approval Gate — SKIPPED (already approved by human)

### Acceptance Criteria

1. WHEN the `/approve/{token}` endpoint receives a valid approval, THE system SHALL
   construct a `RemediationAction` and pass it through `GuardrailEngine.evaluate()`
   with the Approval Gate disabled before calling `executor.execute()`
2. IF any guardrail check returns DENY after human approval, THE system SHALL display
   an HTML page explaining why execution was blocked (e.g., "Circuit breaker is OPEN
   for this host") and send a notification to the operator
3. IF the Concurrency Guard returns DEFER after human approval, THE system SHALL queue
   the action and notify the operator that execution is pending a lock release
4. THE `/approve/{token}` endpoint SHALL log which guardrail checks passed/failed
   with the same audit format as the pipeline path

### Implementation Sketch

```python
# In app.py: _execute_approved_remediation()
async def _execute_approved_remediation(approval) -> None:
    # Build guardrail action from approval data
    action = RemediationAction(
        incident_id=approval.incident_id,
        target_host=approval.affected_host,
        playbook_path=approval.playbook_path,
        service_name=approval.service_name,
        severity=approval.severity,
        # Flag that approval gate should be skipped
        pre_approved=True,
    )

    # Evaluate all guardrails except Approval Gate
    decision = await guardrail_engine.evaluate(action, skip_approval=True)

    if decision.decision_type == GuardrailDecisionType.DENY:
        logger.warning("Post-approval guardrail DENY: %s", decision.reason)
        # Notify operator that execution was blocked despite approval
        return

    # Proceed with execution...
    result = await executor.execute(...)
```

### Effort Estimate: 1-2 days

---

## Improvement 2: Stop Conditions During Execution

### Priority: P1 — High Safety Impact

### Problem Statement

Once a playbook starts executing, the system has no mechanism to abort it if the
action is actively making things worse. The only safety net is the 300-second timeout.
In that window, a misbehaving remediation could take down remaining healthy instances.

### AWS Precedent

- **AWS FIS** uses "Stop Conditions" — CloudWatch alarms that automatically halt a
  running experiment when triggered
- **SageMaker Deployment Guardrails** monitor CloudWatch alarms during the deployment
  and auto-rollback if any alarm trips
- **ECS Deployment Circuit Breaker** stops deploying new tasks when failures exceed
  a threshold

### Proposed Requirement

**Requirement 11: Stop Conditions During Execution**

> WHILE a remediation playbook is executing, the GuardrailEngine SHALL monitor a set
> of configurable "stop condition" CloudWatch alarms associated with the target host
> or service group.
>
> IF any stop condition alarm transitions to ALARM state during execution:
> 1. THE system SHALL send SIGTERM to the ansible-playbook subprocess immediately
> 2. THE system SHALL wait up to 10 seconds for graceful termination
> 3. IF the process does not terminate within 10 seconds, send SIGKILL
> 4. THE system SHALL mark the remediation as ABORTED (distinct from SUCCESS/FAILURE/TIMEOUT)
> 5. THE system SHALL trigger traffic restoration immediately if traffic was drained
> 6. THE system SHALL log the stop condition alarm name that triggered the abort
> 7. THE system SHALL record the abort in the circuit breaker as a failure

### Acceptance Criteria

1. THE system SHALL support configuring stop conditions per service group in
   `config/stop_conditions.yml` with CloudWatch alarm ARNs or metric expressions
2. WHEN no stop conditions are configured for a service group, THE system SHALL
   proceed without real-time monitoring (backward compatible)
3. THE stop condition polling interval SHALL be configurable (default 10 seconds,
   minimum 5 seconds, maximum 30 seconds)
4. WHEN a stop condition triggers, THE system SHALL capture and log any partial
   ansible output generated before the abort
5. THE ABORTED status SHALL be distinct from FAILURE in metrics and audit records
   to differentiate "remediation went wrong" from "remediation was preemptively stopped"

### Configuration Example

```yaml
# config/stop_conditions.yml
stop_conditions:
  - service_group: web-frontend
    alarms:
      - name: HealthyHostCountCritical
        metric: AWS/ApplicationELB/HealthyHostCount
        threshold: "< 1"
        description: "No healthy hosts remaining"
      - name: Error5xxSpike
        metric: AWS/ApplicationELB/HTTPCode_Target_5XX_Count
        threshold: "> 100 per minute"
        description: "5xx errors spiking during remediation"

  - service_group: api-gateway
    alarms:
      - name: LatencyP99Critical
        metric: custom/ApiLatencyP99
        threshold: "> 30000 ms"
        description: "API latency exceeded 30s"

  global:
    - name: MultiServiceDegradation
      metric: custom/DegradedServiceCount
      threshold: "> 3"
      description: "Multiple services degraded simultaneously"

defaults:
  polling_interval_seconds: 10
  grace_period_before_monitoring_seconds: 15
```

### Effort Estimate: 3-5 days

---

## Improvement 3: Post-Execution Baking Period

### Priority: P2 — Effectiveness Validation

### Problem Statement

A remediation is currently marked "SUCCESS" if the ansible-playbook exits with code 0.
But this doesn't mean the underlying issue is actually fixed. The killed process might
respawn, the disk might fill again in minutes, or the service might crash-loop after
restart.

### AWS Precedent

- **SageMaker Deployment Guardrails** enforce a "baking period" — a monitoring window
  after deployment where CloudWatch alarms are observed before declaring success
- **CodeDeploy** monitors alarms after deployment and can trigger rollback even after
  all instances report healthy

### Proposed Requirement

**Requirement 12: Post-Execution Validation (Baking Period)**

> AFTER a remediation completes with SUCCESS status, THE system SHALL enter a
> configurable "baking period" during which it monitors the original alert condition:
>
> 1. Wait for `baking_period_seconds` (default 120, min 30, max 600)
> 2. Re-query the original CloudWatch alarm that triggered the alert
> 3. Query the target host's health endpoint
> 4. Produce a validation result:
>    - EFFECTIVE: Alarm resolved AND host healthy
>    - INEFFECTIVE: Alarm still in ALARM state after baking
>    - DEGRADED: Host health check fails (escalate immediately)
>    - INCONCLUSIVE: Unable to determine (alarm not queryable)

### Acceptance Criteria

1. THE validation result SHALL be recorded in the Incident Memory Store alongside
   the execution result, enabling the AI agent to learn which remediations actually
   fix issues vs. which only appear to succeed
2. WHEN the baking period produces INEFFECTIVE, THE system SHALL increment a
   `RemediationIneffective` CloudWatch metric and send an escalation notification
3. WHEN the baking period produces DEGRADED, THE system SHALL immediately re-invoke
   the Health Checker and escalate to the on-call operator
4. THE baking period SHALL be configurable per risk level:
   - LOW risk: 60 seconds
   - MEDIUM risk: 120 seconds
   - HIGH risk: 180 seconds
   - CRITICAL risk: 300 seconds
5. THE circuit breaker SHALL count INEFFECTIVE outcomes as failures (contributing
   to the failure threshold)

### Integration with AI Learning

The baking period result feeds directly into the AI Reasoning Agent's historical
context. This enables the agent to learn:
- "Killing stress-ng via fix_high_cpu.yml is EFFECTIVE 95% of the time"
- "Restarting nginx via restart_service.yml is INEFFECTIVE 40% of the time
   (underlying issue is memory leak, not nginx crash)"

### Effort Estimate: 2-3 days

---

## Improvement 4: Service Availability Threshold

### Priority: P2 — Prevents Cascading Outages

### Problem Statement

The current Health Checker verifies "are there healthy peers?" (binary check) but
doesn't enforce a minimum healthy percentage. If a service group has 6 instances and
3 are already down, the guardrail still allows restarting a 4th — dropping availability
to 33%.

### AWS Precedent

- **ECS Deployment Configuration** uses `minimumHealthyPercent` (e.g., 100%) to
  ensure at least N% of tasks remain healthy during rolling updates
- **ECS Deployment Circuit Breaker** uses `BOUNDED_PERCENT` failure counting mode

### Proposed Requirement

**Requirement 13: Service Availability Threshold**

> BEFORE allowing a remediation action, THE Health Checker SHALL:
> 1. Query the current healthy instance count for the target's service group
> 2. Calculate projected availability: (current_healthy - 1) / total_instances
> 3. IF projected availability < configurable_minimum (default 50%):
>    - Return DENY with reason "would_breach_availability_threshold"
>    - Include in the denial: current_healthy, total_instances, projected_pct
> 4. IF projected availability >= minimum but < 75%:
>    - Return ALLOW with a WARNING annotation
>    - Include availability context in the approval email

### Acceptance Criteria

1. THE minimum availability threshold SHALL be configurable per service group
   in `config/risk_classification.yml` (default 50%, min 20%, max 90%)
2. THE Health Checker SHALL query instance health from the ALB target group
   or Cloud Map service registry (configurable source)
3. WHEN the threshold is breached, THE denial notification SHALL include
   a clear explanation: "Allowing this action would reduce web-frontend
   availability from 67% (4/6 healthy) to 50% (3/6), which is below the
   configured minimum of 50%"
4. THE threshold calculation SHALL account for instances already being
   remediated (held by Concurrency Guard) — treat them as unavailable

### Configuration Example

```yaml
# In config/risk_classification.yml
availability_thresholds:
  default: 50
  overrides:
    - service_group: api-gateway
      minimum_healthy_percent: 75
    - service_group: background-workers
      minimum_healthy_percent: 25
```

### Effort Estimate: 1-2 days

---

## Improvement 5: AI Remediation Plan Validation

### Priority: P2 — Prevents AI Hallucination Damage

### Problem Statement

When the AI Reasoning Agent generates a RemediationPlan, it could potentially suggest
dangerous commands (e.g., `rm -rf /`, `shutdown -h now`, scaling to 0 instances).
Currently there's no hard validation layer between AI output and execution.

### AWS Precedent

- **Amazon Bedrock Guardrails** implements "denied topics" — specific patterns that
  are always blocked regardless of model confidence
- **AWS Config Rules** enforce compliance by blocking non-compliant configurations

### Proposed Requirement

**Requirement 14: AI Remediation Plan Validation**

> WHEN the AI Reasoning Agent produces a RemediationPlan, THE system SHALL validate
> the plan against a configurable set of safety rules BEFORE passing it to the
> SSM Executor or GuardrailEngine:
>
> 1. **Denied Commands**: Block plans containing any command matching patterns in
>    `config/denied_commands.yml` (e.g., `rm -rf /`, `dd if=`, `mkfs`, `shutdown`)
> 2. **Parameter Bounds**: Validate plan parameters against safety limits:
>    - `timeout_seconds` SHALL NOT exceed 600
>    - `target_hosts` count SHALL NOT exceed 5 per single plan
>    - No wildcard patterns (`*`) in host targeting
>    - No root-level filesystem operations outside allowed paths
> 3. **Action Allowlist**: If configured, only permit actions from an explicit
>    allowlist of SSM documents / playbook names
> 4. **Rate Limiting**: No more than 3 AI-generated remediations per host per hour

### Acceptance Criteria

1. IF validation fails, THE system SHALL DENY the plan, fallback to rule-based
   matching, and log the specific validation rule that was violated
2. THE denied commands list SHALL be loaded from YAML and support regex patterns
3. THE validation SHALL complete within 100ms (pure in-memory pattern matching)
4. WHEN a plan is denied by validation, THE audit record SHALL include the
   AI model's original suggestion for post-incident review

### Configuration Example

```yaml
# config/denied_commands.yml
denied_patterns:
  - pattern: "rm\\s+(-rf?\\s+)?/"
    reason: "Recursive delete of root filesystem"
  - pattern: "shutdown|halt|poweroff|init\\s+0"
    reason: "Host shutdown not permitted via automation"
  - pattern: "dd\\s+if="
    reason: "Raw disk write operations not permitted"
  - pattern: "mkfs|format"
    reason: "Filesystem creation not permitted"
  - pattern: "iptables\\s+-F|iptables.*DROP"
    reason: "Firewall flush/drop-all not permitted"
  - pattern: "systemctl\\s+(disable|mask)"
    reason: "Permanently disabling services not permitted"

parameter_bounds:
  max_timeout_seconds: 600
  max_target_hosts: 5
  max_plan_steps: 10
  max_ai_executions_per_host_per_hour: 3
  
allowed_paths:
  - /var/log/
  - /tmp/
  - /opt/app/

action_allowlist_enabled: false
action_allowlist:
  - fix_high_cpu
  - restart_service
  - clear_disk
  - restart_process
```

### Effort Estimate: 2-3 days

---

## Improvement 6: SSM Change Calendar Integration

### Priority: P3 — AWS-Native Maintenance Awareness

### Problem Statement

The current `MaintenanceWindowManager` relies on a manually-edited YAML file for
maintenance windows. This creates several issues:
- Ops teams must edit YAML and push to Git for window changes
- No integration with existing enterprise calendar tools
- No EventBridge events on state transitions
- No API to query "is now a safe time?" from external systems

### AWS Precedent

[AWS SSM Change Calendar](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-change-calendar.html)
provides exactly this functionality:
- `DEFAULT_OPEN` calendars: block actions only during events
- `DEFAULT_CLOSED` calendars: allow actions only during events
- `GetCalendarState` API: returns OPEN/CLOSED for any timestamp
- Imports from Google Calendar, Outlook, iCloud
- Emits EventBridge events on state transitions
- Integrates with SSM Automation, Maintenance Windows, and State Manager

### Proposed Requirement

**Requirement 15: SSM Change Calendar Integration**

> THE Maintenance Window Manager SHALL support two configuration modes:
> 1. **Local mode** (current): YAML-based maintenance windows (backward compatible)
> 2. **AWS mode** (new): Query SSM Change Calendar via `GetCalendarState` API
>
> In AWS mode:
> - Call `ssm:GetCalendarState` with the configured calendar document names
> - IF state is CLOSED → return DEFER for all actions
> - IF state is OPEN → return ALLOW
> - Cache the state for 60 seconds to avoid API throttling (10 req/s limit)
> - On API failure → fallback to local YAML config

### Acceptance Criteria

1. THE mode SHALL be configurable via environment variable
   `MAINTENANCE_WINDOW_MODE` (values: `local`, `aws`, `hybrid`)
2. In `hybrid` mode, BOTH local YAML and SSM Calendar are checked — DEFER if
   EITHER indicates a maintenance window
3. THE CDK stack SHALL create a `DEFAULT_OPEN` SSM Change Calendar document
   named `aiops-change-calendar-{environment}`
4. THE system SHALL respect SSM Change Calendar's iCalendar-based scheduling
   including recurring events and timezone support

### Implementation Note

```python
# In maintenance_window.py
async def _check_aws_calendar(self) -> bool:
    """Returns True if changes are allowed (calendar OPEN)."""
    response = self._ssm_client.get_calendar_state(
        CalendarNames=[f"aiops-change-calendar-{self._environment}"]
    )
    return response["State"] == "OPEN"
```

### Effort Estimate: 2-3 days

---

## Improvement 7: Graduated Execution Modes (Dry-Run)

### Priority: P3 — Safer CRITICAL Actions

### Problem Statement

For CRITICAL risk actions (database restarts, single-instance services), the operator
receives an approval email but cannot see exactly what the playbook will do before
approving. They're approving blindly based on the alert name and suggested action.

### Proposed Requirement

**Requirement 16: Graduated Execution Modes**

> THE Blast Radius Classifier SHALL assign an execution mode based on risk level:
>
> | Risk Level | Execution Mode | Behavior |
> |---|---|---|
> | LOW | `AUTO_EXECUTE` | Execute immediately (skip approval) |
> | MEDIUM | `EXECUTE_WITH_BAKING` | Execute + post-execution baking period |
> | HIGH | `APPROVAL_REQUIRED` | Current behavior (email approval) |
> | CRITICAL | `DRY_RUN_FIRST` | Run ansible with `--check`, show diff in email |
>
> In `DRY_RUN_FIRST` mode:
> 1. Execute the playbook with `--check --diff` flags (no actual changes)
> 2. Capture the dry-run output showing what WOULD change
> 3. Include the dry-run output in the approval email
> 4. Operator reviews the actual impact before clicking approve
> 5. On approval, execute the playbook normally (without --check)

### Acceptance Criteria

1. THE dry-run output SHALL be included in the approval email in a `<pre>` block
   with monospace formatting for readability
2. THE dry-run execution SHALL have its own timeout (default 60s, separate from
   the real execution timeout of 300s)
3. IF the dry-run itself fails, THE system SHALL still send the approval email
   but indicate "Dry-run failed — exercise extra caution"
4. THE dry-run SHALL NOT count toward circuit breaker failure tracking

### Effort Estimate: 2-3 days

---

## Improvement 8: Pre-Execution State Snapshot

### Priority: P3 — Enables Remediation Rollback

### Problem Statement

If a playbook partially executes and fails (e.g., stops a service but can't start
the replacement), there's no automatic way to undo what was done. The operator must
manually intervene to restore the previous state.

### AWS Precedent

- **CloudFormation** captures the complete resource state before updates and rolls
  back all changes on failure
- **DynamoDB PITR** provides point-in-time recovery to any second within the retention window
- **EBS Snapshots** provide pre-change backup for instance volumes

### Proposed Requirement

**Requirement 17: Pre-Execution State Snapshot**

> BEFORE executing a remediation playbook, THE system SHALL capture a state snapshot
> of the target host via SSM Run Command:
>
> 1. Running services status (`systemctl list-units --type=service --state=running`)
> 2. Active network connections count (`ss -s`)
> 3. Current process list for the target service (`pgrep -a {service_name}`)
> 4. Configuration file hash (if service config path is known)
> 5. Current resource utilization (CPU%, memory%, disk%)
>
> Store the snapshot in DynamoDB with TTL of 24 hours.
> On FAILURE or ABORTED:
> - Attempt to restart any services that were stopped
> - Log the rollback attempt result
> - Include snapshot diff in the failure notification

### Acceptance Criteria

1. THE snapshot capture SHALL complete within 15 seconds via SSM RunCommand
2. IF snapshot capture fails, THE system SHALL proceed with execution but log
   a warning that rollback will not be available
3. THE snapshot SHALL be stored as a JSON document with the incident_id as key
4. THE rollback attempt SHALL be best-effort — it logs success/failure but does
   not block the pipeline

### Effort Estimate: 3-5 days

---

## Improvement 9: Cross-Service Dependency Awareness

### Priority: P4 — Cascade Prevention

### Problem Statement

The current guardrail engine evaluates each action independently. It doesn't consider
whether downstream services that depend on the target are already degraded, which
would amplify the blast radius of a restart.

### Proposed Requirement

**Requirement 18: Cross-Service Dependency Check**

> BEFORE allowing a remediation action, THE Health Checker SHALL:
> 1. Query the service dependency graph for services that depend on the target
> 2. Check the health status of direct downstream dependents
> 3. IF any downstream dependent is already in DEGRADED or ALARM state:
>    - Elevate the risk classification by one level
>    - Include the dependency impact chain in the approval notification
>    - Add a WARNING annotation to the guardrail decision
> 4. AFTER remediation completes, verify downstream services recovered

### Acceptance Criteria

1. THE dependency graph SHALL be loaded from `config/service_dependencies.yml`
2. THE dependency check SHALL query no more than 10 downstream services (cap
   for performance) within a 5-second timeout
3. THE elevated risk SHALL be recorded in the audit trail with the dependency
   reason (e.g., "risk elevated: downstream service 'payment-api' is degraded")
4. IF the dependency graph is unavailable, THE system SHALL proceed without
   elevation (fail-open for dependency checks, fail-closed for everything else)

### Configuration Example

```yaml
# config/service_dependencies.yml
dependencies:
  postgres-primary:
    dependents: [api-gateway, user-service, payment-service, order-service]
  redis-cache:
    dependents: [api-gateway, session-service]
  api-gateway:
    dependents: [web-frontend, mobile-backend]
```

### Effort Estimate: 2-3 days

---

## Improvement 10: Escalation Fatigue Prevention

### Priority: P4 — Operator Experience

### Problem Statement

If the same alert fires repeatedly (e.g., high CPU every day at 2am due to cron job),
operators receive the same approval email every time. Over time, they start approving
without reading — which defeats the human-in-the-loop safety purpose.

### Proposed Requirement

**Requirement 19: Escalation Fatigue Prevention**

> THE Approval Gate SHALL implement an "operator trust" mechanism:
>
> 1. **Auto-Approve Trusted Patterns**: If the same (alert_name + playbook + host)
>    combination has been approved by an operator 3 or more consecutive times in
>    the last 7 days with SUCCESS outcomes, THE system SHALL auto-approve subsequent
>    instances and log "auto_approved:operator_trust"
> 2. **Trust Reset**: If any execution of a trusted pattern results in FAILURE,
>    INEFFECTIVE, or ABORTED, THE system SHALL revoke trust and revert to requiring
>    manual approval
> 3. **Quiet Hours**: For LOW risk actions during configurable quiet hours (e.g.,
>    23:00-06:00), THE system SHALL auto-execute without approval and send a
>    summary notification at the end of quiet hours
> 4. **Batch Approval**: When an operator has > 5 pending approvals, THE email
>    SHALL include a "Approve All LOW/MEDIUM Risk" batch link

### Acceptance Criteria

1. THE trust history SHALL be stored in DynamoDB with the pattern fingerprint
   as key and approval count + last outcome as attributes
2. THE auto-approval SHALL still log a full audit record with reason
   "auto_approved:operator_trust:{approval_count}"
3. THE quiet hours SHALL be configurable per environment
   (dev: always auto-approve LOW, prod: quiet hours only)
4. THE batch approval link SHALL only batch actions at the SAME or LOWER risk
   level (never batch HIGH+LOW together)

### Effort Estimate: 2-3 days

---

## Architecture: Updated Guardrail Flow (After Improvements)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ BEFORE EXECUTION (Pre-Flight Checks)                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Self-Protection Guard                                                    │
│  2. Maintenance Window (YAML + SSM Change Calendar) ← [Improvement 6]       │
│  3. Circuit Breaker                                                          │
│  4. Concurrency Guard                                                        │
│  5. Blast Radius Classifier + Availability Threshold ← [Improvement 4]      │
│  6. Cross-Service Dependency Check ← [Improvement 9]                         │
│  7. Health Checker                                                           │
│  8. AI Plan Validation ← [Improvement 5]                                     │
│  9. Approval Gate (with fatigue prevention) ← [Improvement 10]               │
│ 10. Dry-Run for CRITICAL ← [Improvement 7]                                  │
│                                                                              │
│  ⟹ All paths (pipeline + email approval) route through this ← [Imp. 1]     │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ DURING EXECUTION (Real-Time Safety)                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  11. Pre-Execution State Snapshot ← [Improvement 8]                          │
│  12. Traffic Draining                                                        │
│  13. Execute Playbook/SSM Command                                            │
│  14. Stop Condition Monitoring ← [Improvement 2]                             │
│      ↳ Abort immediately if CloudWatch alarm triggers                        │
│  15. Traffic Restoration                                                     │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ AFTER EXECUTION (Validation)                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  16. Post-Execution Baking Period ← [Improvement 3]                          │
│      ↳ Monitor original alarm + host health for 120-300s                     │
│  17. Record outcome (EFFECTIVE / INEFFECTIVE / DEGRADED)                     │
│  18. Update circuit breaker + AI learning + operator trust                   │
│  19. Attempt rollback if FAILED/ABORTED ← [Improvement 8]                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Critical Safety Fixes (Week 1)

| Task | Improvement | Effort | Files Modified |
|------|-------------|--------|----------------|
| 1.1 | Fix approval bypass | 1-2 days | `src/app.py`, `src/guardrails/engine.py` |
| 1.2 | Add `skip_approval` flag to engine | 0.5 days | `src/guardrails/engine.py`, `src/guardrails/models.py` |
| 1.3 | Write tests for unified path | 0.5 days | `tests/unit/test_approval_guardrails.py` |

### Phase 2: Execution Safety (Week 2-3)

| Task | Improvement | Effort | Files Created |
|------|-------------|--------|---------------|
| 2.1 | Stop conditions monitor | 2 days | `src/guardrails/stop_conditions.py` |
| 2.2 | Stop conditions config | 0.5 days | `config/stop_conditions.yml` |
| 2.3 | Integrate with executor | 1 day | `src/executor.py` modification |
| 2.4 | Post-execution baking | 2 days | `src/guardrails/baking_validator.py` |
| 2.5 | Baking integration | 1 day | `src/orchestrator.py` modification |

### Phase 3: Enhanced Blast Radius (Week 3-4)

| Task | Improvement | Effort | Files Modified/Created |
|------|-------------|--------|------------------------|
| 3.1 | Availability threshold | 1.5 days | `src/guardrails/health_checker.py` |
| 3.2 | AI plan validation | 2 days | `src/guardrails/plan_validator.py` |
| 3.3 | Denied commands config | 0.5 days | `config/denied_commands.yml` |
| 3.4 | Integration tests | 1 day | `tests/integration/test_guardrails.py` |

### Phase 4: AWS-Native & UX (Week 4-5)

| Task | Improvement | Effort | Files Modified/Created |
|------|-------------|--------|------------------------|
| 4.1 | SSM Change Calendar | 2 days | `src/guardrails/maintenance_window.py` |
| 4.2 | Graduated modes (dry-run) | 2 days | `src/guardrails/classifier.py`, `src/executor.py` |
| 4.3 | State snapshot | 3 days | `src/guardrails/state_snapshot.py` |
| 4.4 | Dependency awareness | 2 days | `src/guardrails/health_checker.py` |
| 4.5 | Fatigue prevention | 2 days | `src/guardrails/approval.py` |

### Total Estimated Effort: 20-25 days

---

## New Files to Create

```
src/guardrails/
├── stop_conditions.py          ← Real-time execution monitoring
├── baking_validator.py         ← Post-execution effectiveness validation
├── plan_validator.py           ← AI remediation plan safety validation
├── state_snapshot.py           ← Pre-execution state capture + rollback
└── (existing files modified)

config/
├── stop_conditions.yml         ← CloudWatch alarms for abort triggers
├── denied_commands.yml         ← AI plan validation rules
├── service_dependencies.yml    ← Cross-service dependency graph
└── (existing files extended)
```

---

## Metrics Impact

### New CloudWatch Metrics

| Metric | Namespace | Description |
|--------|-----------|-------------|
| `GuardrailApprovalBypassed` | `AIOps/{env}` | Approval path that now routes through guardrails |
| `ExecutionAborted` | `AIOps/{env}` | Stop condition triggered during execution |
| `RemediationIneffective` | `AIOps/{env}` | Baking period determined fix didn't work |
| `AvailabilityThresholdDenied` | `AIOps/{env}` | Blocked due to low healthy instance count |
| `AIPlanValidationDenied` | `AIOps/{env}` | AI-generated plan blocked by safety rules |
| `OperatorTrustAutoApproved` | `AIOps/{env}` | Auto-approved via fatigue prevention |
| `DryRunCompleted` | `AIOps/{env}` | Dry-run executed for CRITICAL action |

### Expected Safety Improvements

| Scenario | Before | After |
|----------|--------|-------|
| Operator approves during maintenance | Executes (unsafe) | DEFERRED |
| Circuit breaker open + operator approves | Executes (unsafe) | DENIED |
| AI suggests dangerous command | Executes | DENIED + fallback |
| Remediation makes things worse | Waits for 300s timeout | Aborted in <10s |
| Fix runs but doesn't resolve issue | Marked "SUCCESS" | Marked "INEFFECTIVE" |
| Same alert approved 5x this week | 5 manual emails | Auto-approved on 4th |

---

## Next Steps

1. **Immediate (This Week)**: Implement Improvement 1 (fix the approval bypass)
   — this is a safety-critical bug that exists in production code today
2. **Review**: Share this document with the team for feedback on prioritization
3. **Sprint Planning**: Add Phase 1 and Phase 2 to the next sprint backlog
4. **CDK Update**: Add SSM Change Calendar resource to the ObservabilityStack
5. **Test Strategy**: Add property-based tests for each new guardrail check
   following the existing Hypothesis pattern in `tests/property/`

---

## References

- [AWS SSM Change Calendar](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-change-calendar.html)
- [AWS FIS Stop Conditions](https://docs.aws.amazon.com/fis/latest/userguide/what-is.html)
- [ECS Deployment Circuit Breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html)
- [SageMaker Deployment Guardrails — Auto-Rollback and Baking](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails-configuration.html)
- [Amazon Bedrock Guardrails — Denied Topics](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [AWS CodeDeploy Auto-Rollback with Alarms](https://docs.aws.amazon.com/codedeploy/latest/userguide/deployments-rollback-and-redeploy.html)
- [AWS Well-Architected Reliability Pillar](https://docs.aws.amazon.com/config/latest/developerguide/operational-best-practices-for-wa-Reliability-Pillar.html)

---

## Future Improvements (Not for Current Implementation)

The following gaps were identified through additional research against the AWS
Well-Architected Agentic AI Lens, AWS Agentic AI Security Scoping Matrix, and
progressive delivery patterns. They are documented here for future consideration
but are NOT part of the current implementation roadmap.

### Future Gap A: Bounded Autonomy Scope Constraints

**Source:** [AWS Well-Architected Agentic AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentic-ai-lens.html)
— *"Every agent operates within explicitly defined scope boundaries, with guardrails
that constrain behavior regardless of inputs received."*

**Gap:** Current guardrails focus on individual action safety (blast radius, denied
commands) but not on aggregate impact over time. Missing constraints:

- **Daily action budget**: Max N remediations per environment per 24 hours
  (prevents runaway automation loops from exhausting infrastructure)
- **Scope ceiling**: Agent can never restart more than X% of a service group
  in aggregate per calendar day, regardless of how many individual approvals
- **Time-bound execution window**: Approval tokens grant a 5-minute execution
  window (currently the 30-minute expiry only limits when the link can be clicked,
  not how long the system has to execute)

**Why deferred:** The existing hourly rate-limit in Improvement 5 (AI Plan Validator)
covers the most critical case. A daily budget adds incremental value but requires
a persistent counter (DynamoDB) and introduces complexity around timezone/reset logic.

---

### Future Gap B: Guardrail Configuration Drift Detection

**Source:** [AWS DevOps Guidance AG.ACG.6](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/ag.acg.6-implement-auto-remediation-for-non-compliant-findings.html)
— *"Implement auto-remediation for non-compliant findings"* and
[AWS Agentic AI Security Blog](https://aws.amazon.com/blogs/security/the-agentic-ai-security-scoping-matrix-a-framework-for-securing-autonomous-ai-systems/)
— *"Higher agency scopes require continuous behavioral analysis"*

**Gap:** If someone manually edits `protected_hosts.yml` to remove a critical host,
or empties `denied_commands.yml`, the guardrails silently become weaker. There is no
self-integrity mechanism that detects weakened safety configuration.

**Proposed future behavior:**
- On startup: compute SHA-256 hash of each safety config file
- Store baseline hashes in DynamoDB or SSM Parameter Store
- On each config reload: compare hash to baseline
- If hash changed AND file is smaller (fewer entries): emit `GuardrailConfigWeakened`
  alarm and require manual acknowledgment before accepting the weakened config
- Minimum count validation: `protected_hosts.yml` ≥ 1 entry, `denied_commands.yml` ≥ 5 patterns
- Emit EventBridge event on any safety config modification for audit trail

**Why deferred:** The existing hot-reload-with-fallback behavior (retain valid config
on malformed reload) covers the most dangerous case (corrupt file). Drift detection
adds observability value but is not a safety-critical gap.

---

### Future Gap C: Progressive (Canary-Style) Remediation

**Source:** [Google's Canary Analysis Service (ACM Queue)](https://queue.acm.org/detail.cfm?id=3194655)
— *"Canarying refers to a partial and time-limited deployment of a change, followed
by evaluation of whether the change is safe."* Also: [Argo Rollouts canary analysis](https://developer.harness.io/docs/continuous-delivery/gitops/argo-rollouts/argo-rollouts-with-cv)
— *"CV validates deployments by analyzing metrics at each canary stage."*

**Gap:** When a remediation needs to be applied to multiple hosts in a service group
(e.g., rolling restart of 6 nginx instances), the current system applies to one host
at a time (via concurrency guard rolling restart %), but doesn't explicitly designate
the FIRST application as a "canary" with enhanced monitoring.

**Proposed future behavior:**
1. First host in a rolling remediation = "canary host"
2. Apply fix to canary host
3. Enter extended baking period (2x normal) for the canary
4. Monitor canary metrics vs. baseline (error rate, latency, health)
5. Only if canary passes: proceed to remaining hosts at normal rolling pace
6. If canary fails: abort entire rolling remediation, escalate

**Why deferred:** The existing baking validator (Improvement 3) + rolling restart
percentage (concurrency spec) together provide adequate safety. The canary concept
adds value primarily for multi-host remediations affecting > 5 hosts, which is
uncommon in the current deployment topology. Worth revisiting when fleet size grows.

---

### Future Improvement Priority (When to Revisit)

| Gap | Revisit When | Trigger |
|-----|-------------|---------|
| A: Bounded Autonomy Budget | Fleet > 50 hosts OR ai_only mode in prod | Risk of automation loops grows with scale |
| B: Config Drift Detection | SOC2/compliance audit requirement | Regulatory or security team request |
| C: Canary Remediation | Service groups > 10 instances | Rolling restart affects meaningful traffic fraction |
