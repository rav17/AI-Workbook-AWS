# Concurrent Execution Safety — Improvement Proposals

## Document Information

| Field | Value |
|-------|-------|
| **Author** | Ravindra Yadav |
| **Date** | August 2026 |
| **Status** | Proposed |
| **Spec** | `.kiro/specs/concurrent-execution-safety` |
| **Informed By** | AWS DynamoDB Lock Client, SQS FIFO Message Groups, AWS Step Functions Concurrency Control, Kubernetes Operator Reconciliation Patterns, Resilience4j Bulkhead/Rate Limiter, AWS FIS, Martin Kleppmann's "Designing Data-Intensive Applications" fencing token pattern |

---

## Executive Summary

The current concurrent-execution-safety spec implements 7 mechanisms (host locking,
resource conflicts, deduplication, priority queue, circuit breaker, dependency graph,
observability). These are well-designed. The improvements below address gaps found
by comparing against:

1. **AWS DynamoDB Lock Client** best practices (heartbeats, fencing tokens)
2. **SQS FIFO** message group serialization pattern
3. **Kubernetes operator** reconciliation and leader election patterns
4. **Resilience4j** bulkhead isolation and rate limiting
5. Industry SRE incident response orchestration practices

---

## Current Strengths (Already Well-Implemented)

- ✅ DynamoDB-backed distributed locks with TTL (solid foundation)
- ✅ Conditional writes for atomic lock acquisition (race-condition safe)
- ✅ Per-host circuit breaker with CLOSED/OPEN/HALF_OPEN states
- ✅ Priority-based queuing with P1-P5 severity ordering
- ✅ Alert fingerprint deduplication with suppression windows
- ✅ DAG-based dependency management with cycle detection
- ✅ YAML-driven resource conflict configuration with hot-reload
- ✅ Preemption logic (P1/P2 can preempt P4/P5)
- ✅ Status API for observability

---

## Improvement 1: Heartbeat-Based Lock Renewal (Fencing Tokens)

### Priority: P1 — Prevents Split-Brain Execution

### Problem Statement

The current lock implementation uses a fixed TTL (executor_timeout + 60s). If a
remediation takes longer than expected (e.g., a slow SSH connection) but is still
actively running, the lock expires and another action could start on the same host.
This creates a split-brain where TWO remediations run concurrently.

### AWS Precedent

The [AWS DynamoDB Lock Client](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_DistributedLocking.html)
uses **heartbeats** + **lease duration** + **fencing tokens**:
- Lock holder sends heartbeats every `leaseDuration / 3` to extend the lease
- If heartbeats stop (process died), lock expires after lease duration
- Fencing token (monotonically increasing number) ensures stale lock holders
  can't perform writes after losing their lock

### Proposed Improvement

```
WHEN a host lock is acquired:
1. Record a fencing_token (auto-increment counter) in the lock record
2. Start a background heartbeat task (every TTL/3 seconds)
3. Heartbeat extends the lock TTL by the original duration
4. Pass fencing_token to the executor as an extra_var

WHEN the executor finishes:
1. Verify the fencing_token hasn't changed before recording outcome
2. If token changed → another process took over → discard result

WHEN heartbeat fails (DynamoDB unreachable):
1. Log warning but continue execution (best-effort)
2. If 3 consecutive heartbeat failures → mark lock as unhealthy
3. Do NOT release the lock (let it expire naturally)
```

### Why This Matters

Without heartbeats, a 10-minute playbook with a 6-minute TTL will lose its lock
at minute 6, potentially allowing a conflicting action to start. With heartbeats,
the lock stays active as long as the process is alive.

### Effort Estimate: 2-3 days

---

## Improvement 2: SQS FIFO Message Groups for Natural Host Serialization

### Priority: P2 — Architectural Simplification

### Problem Statement

The current system uses a Standard SQS queue + custom DynamoDB locking for
per-host serialization. This requires managing locks, TTLs, heartbeats, and
cleanup. SQS FIFO queues provide per-group serialization natively.

### AWS Precedent

[SQS FIFO message groups](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-understanding-logic.html)
guarantee that messages with the same `MessageGroupId` are processed sequentially
by a single consumer. While one message from a group is being processed (invisible),
no other consumer can receive messages from that same group.

### Proposed Improvement

```
Use SQS FIFO queue with MessageGroupId = target_hostname

Benefits:
- Host-level serialization WITHOUT custom DynamoDB locks
- Deduplication via MessageDeduplicationId (5-minute window built-in)
- Ordering guarantee (per-host FIFO)
- Different hosts process in parallel automatically

Architecture:
  Alert → FIFO Queue (GroupId=host) → Consumer
                                        ↓
  host-A messages → only 1 at a time
  host-B messages → only 1 at a time (parallel with host-A)
```

### Trade-offs

| Pro | Con |
|-----|-----|
| Eliminates custom lock store | 5-minute dedup window is fixed (vs configurable 30-1800s) |
| Native AWS ordering guarantee | 300 msg/s throughput limit per group |
| No orphaned locks possible | Can't preempt in-flight messages |
| Simpler failure handling | Requires FIFO queue (higher cost) |

### Recommendation

Use as a **complementary layer**, not a replacement:
- FIFO queue provides the base serialization guarantee
- DynamoDB locks remain for the resource conflict detection and preemption logic
- The FIFO queue handles the common case; locks handle the complex cases

### Effort Estimate: 3-5 days (if adopting hybrid approach)

---

## Improvement 3: Bulkhead Isolation per Service Group

### Priority: P2 — Prevents Cross-Service Interference

### Problem Statement

The current system has a global semaphore (`asyncio.Semaphore(10)`) for total
concurrent executions. If 10 alerts for the `web-frontend` service arrive
simultaneously, they consume ALL execution slots and starve other services
(e.g., `api-gateway`, `database`) from getting any remediation capacity.

### Industry Precedent

[Resilience4j Bulkhead](https://medium.com/@bolot.89/comprehensive-guide-to-resilience4j-and-the-circuit-breaker-pattern-85c6349d3535)
isolates concurrent operations into separate pools, preventing one failing
component from consuming all resources:
- ThreadPool Bulkhead: separate thread pools per service
- Semaphore Bulkhead: separate semaphore limits per service

### Proposed Improvement

```
Replace single global semaphore with per-service-group bulkheads:

service_bulkheads:
  web-frontend:    max_concurrent: 3
  api-gateway:     max_concurrent: 2
  database:        max_concurrent: 1
  background-jobs: max_concurrent: 5
  _default:        max_concurrent: 2
  _global:         max_concurrent: 10  # total cap across all services
```

### Acceptance Criteria

1. EACH service group SHALL have an independent concurrency limit
2. WHEN a service group's bulkhead is full, new actions for THAT service
   SHALL be queued, but actions for OTHER services SHALL proceed normally
3. THE global cap SHALL still be enforced across all bulkheads
4. THE bulkhead configuration SHALL be loadable from YAML with hot-reload
5. THE status API SHALL report per-bulkhead utilization

### Effort Estimate: 2 days

---

## Improvement 4: Fleet-Wide Error Threshold (Global Circuit Breaker)

### Priority: P2 — Prevents Fleet-Wide Cascading Failure

### Problem Statement

The current circuit breaker operates per-host. If 5 different hosts each fail once,
no circuit breaker trips (each host is at 1/3 threshold). But collectively, 5 failures
in 2 minutes across the fleet suggests a systemic issue (e.g., SSM service degradation,
bad playbook pushed to all hosts, network partition).

### AWS Precedent

[SSM Automation error threshold](https://docs.aws.amazon.com/systems-manager/latest/userguide/running-automations-scale-controls.html)
stops sending automation to remaining targets after a configurable number of failures
across the fleet, regardless of which individual targets failed.

### Proposed Improvement

```
Add a fleet-wide error threshold alongside the per-host circuit breaker:

fleet_circuit_breaker:
  failure_threshold: 5           # total failures across any hosts
  time_window_seconds: 300       # within 5 minutes
  cooldown_seconds: 600          # pause all automation for 10 minutes
  auto_reset: true               # auto-resume after cooldown

Behavior:
- Tracks failures globally (across all hosts/services)
- When threshold breached: REJECT ALL new executions fleet-wide
- Existing in-flight executions allowed to complete
- Escalation notification with all failed incident IDs
- After cooldown: resume with adaptive ramp-up (Improvement 7)
```

### Acceptance Criteria

1. THE fleet circuit breaker SHALL track failures across all hosts in a sliding window
2. WHEN the threshold is breached, THE system SHALL reject all new actions with
   reason "fleet_circuit_breaker_open" regardless of target host
3. THE fleet circuit breaker SHALL be independent of per-host circuit breakers
4. THE status API SHALL report fleet circuit breaker state

### Effort Estimate: 1-2 days

---

## Improvement 5: Adaptive Concurrency Ramp-Up

### Priority: P2 — Prevents Post-Recovery Flood

### Problem Statement

When a circuit breaker resets (HALF_OPEN → CLOSED) or a maintenance window ends,
all queued actions are released simultaneously. If 15 actions were queued during
a 10-minute outage, all 15 try to execute at once — potentially overwhelming the
just-recovered host or service.

### AWS Precedent

[SSM Automation adaptive concurrency](https://docs.aws.amazon.com/systems-manager/latest/userguide/running-automations-scale.html):
"The queueing system delivers the automation to a single resource and waits until
the initial invocation is complete before sending the automation to two more resources.
The system exponentially sends the automation to more resources until the concurrency
value is met."

### Proposed Improvement

```
After circuit breaker CLOSED or maintenance window end:
1. Execute 1 queued action (probe) — wait for result
2. If SUCCESS: execute 2 concurrent — wait for results
3. If all SUCCESS: execute 4 concurrent
4. Continue doubling until reaching service bulkhead limit
5. If ANY failure during ramp-up: halt and re-evaluate

Ramp-up sequence: 1 → 2 → 4 → 8 → max_concurrent
Back-off on failure: immediately pause ramp-up, re-enter cooldown
```

### Effort Estimate: 2 days

---

## Improvement 6: Compensating Transactions (Saga Pattern)

### Priority: P3 — Enables Partial Rollback

### Problem Statement

When a multi-step remediation fails at step 3 (out of 7), steps 1-2 have already
made changes (e.g., stopped a service, drained connections). The system marks the
action as FAILED but doesn't undo the partial changes, leaving the host in an
inconsistent state.

### AWS Precedent

[AWS Step Functions Saga Pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/implement-the-serverless-saga-pattern-by-using-aws-step-functions.html):
"If a business transaction fails, saga orchestrates a series of compensating
transactions that undo the changes that were made by the preceding transactions."

### Proposed Improvement

```yaml
# In playbook_mapping.yml — add compensating actions
rules:
  - name: restart_nginx
    conditions:
      alert_name: NginxDown
    playbook_path: playbooks/restart_service.yml
    compensate_path: playbooks/compensate/restore_nginx.yml
    compensate_steps:
      - step: 1  # If stop succeeded but start failed
        action: "systemctl start nginx"  
      - step: 2  # If config was modified
        action: "cp /etc/nginx/nginx.conf.bak /etc/nginx/nginx.conf"
```

```
On multi-step failure at step K:
1. Record which steps completed successfully (1..K-1)
2. Execute compensating actions for steps K-1, K-2, ..., 1 (reverse order)
3. If compensation succeeds → mark as "FAILED_COMPENSATED"
4. If compensation fails → mark as "FAILED_UNCOMPENSATED" + escalate
5. Release host lock only after compensation completes
```

### Effort Estimate: 3-5 days

---

## Improvement 7: Lock Poisoning for Unreachable Hosts

### Priority: P3 — Stops Retry Loops on Dead Hosts

### Problem Statement

When a host is terminated/decommissioned but alerts keep firing for it (stale
CloudWatch alarm), the system enters an infinite cycle: try → SSM unreachable →
fail → circuit breaker opens → cooldown → half-open → probe fails → repeat.

### Proposed Improvement

```
After 3 consecutive "instance_not_reachable" failures (SSM delivery failures,
NOT playbook failures):

1. Mark host as POISONED in DynamoDB lock table
2. REJECT all future actions for this host with "host_poisoned"
3. Drain all queued actions for this host from Priority Queue
4. Emit HostPoisoned CloudWatch metric
5. Send escalation notification: "Host {host} appears unreachable — 
   removed from automation scope"

Un-poisoning:
- Manual API call: POST /concurrency/hosts/{host}/unpoison
- Auto-unpoison when a health check succeeds (periodic probe every 30 min)
```

### Effort Estimate: 1-2 days

---

## Improvement 8: Correlation-Aware Lock Grouping

### Priority: P3 — Reduces Lock Contention

### Problem Statement

When the Alert Correlator groups 5 alerts for the same host (CPU high, memory high,
disk full, service slow, connections exhausted), the system tries to acquire 5
separate locks for what is one underlying issue needing one remediation.

### Proposed Improvement

```
When alerts share a correlation_group:
1. Acquire ONE host lock for the correlation group (not per-alert)
2. Execute the root-cause remediation (single action for the group)
3. After execution: mark all 5 incidents as "resolved_by_correlation"
4. Release ONE lock
5. Suppress the other 4 individual action attempts

Integration point: ConcurrencyManager.request_execution() checks if
incident_id belongs to an active correlation_group lock.
```

### Effort Estimate: 2 days

---

## Improvement 9: Queue Depth Observability Signals

### Priority: P4 — Better Auto-Scaling Decisions

### Problem Statement

The current system publishes a single `queue_depth` metric. But operations teams
need to distinguish between two different types of queuing:
- Lock contention (host busy — more ECS tasks won't help)
- Compute contention (all 10 semaphore slots full — more ECS tasks WILL help)

### Proposed Improvement

```
Publish separate CloudWatch metrics:

ConcurrencyLockContentionDepth:  # waiting for host locks
  - Dimension: HostName
  - Value: count of actions queued per host

ConcurrencyComputeContentionDepth:  # waiting for semaphore slots
  - Value: count of actions waiting for global/bulkhead semaphore

AutoScalingRecommendation:
  - 0 = no scaling needed
  - 1 = scale out (compute contention detected)
  - -1 = scale in (all idle)

Only ConcurrencyComputeContentionDepth should feed into ECS auto-scaling.
Lock contention is solved by faster playbooks, not more containers.
```

### Effort Estimate: 1 day

---

## Improvement 10: Graceful Shutdown Lock Handoff (ECS Deployment Safety)

### Priority: P1 — Prevents Lock Leaks During Deployments

### Problem Statement

When ECS rolls a new task during deployment (sends SIGTERM → waits 30s → SIGKILL),
any in-flight remediation holding DynamoDB locks will lose its process without
releasing the locks. The locks then remain held until TTL expiry (up to 660 seconds),
blocking all queued actions for those hosts during the entire period.

This means every ECS deployment creates a ~10-minute window where certain hosts
are "locked out" of remediation with no active process holding the lock.

### AWS Precedent

[ECS Graceful Shutdown](https://aws.amazon.com/blogs/containers/graceful-shutdowns-with-ecs/):
ECS sends SIGTERM to the container process and waits `stopTimeout` seconds (max 120s
on Fargate) before SIGKILL. Applications should catch SIGTERM, drain in-flight work,
and release resources.

[ECS Connection Draining](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/load-balancer-connection-draining.html):
ECS coordinates deregistration timeout with the stop signal to allow in-flight
requests to complete before the task is killed.

### Proposed Improvement

```python
# In src/main.py or src/app.py — SIGTERM handler

import signal
import asyncio

class GracefulShutdownHandler:
    """Handles ECS SIGTERM for clean lock release."""

    def __init__(self, concurrency_manager, executor):
        self._cm = concurrency_manager
        self._executor = executor
        self._shutting_down = False

    def register(self):
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

    def _handle_sigterm(self, signum, frame):
        self._shutting_down = True
        asyncio.create_task(self._drain_and_release())

    async def _drain_and_release(self):
        """
        1. Stop accepting new request_execution() calls
        2. Wait for in-flight executions (up to 25s, leaving 5s buffer)
        3. Release all held locks
        4. Exit cleanly
        """
        logger.info("SIGTERM received — starting graceful shutdown")

        # Step 1: Block new requests
        self._cm.set_draining(True)

        # Step 2: Wait for in-flight (max 25s to stay within ECS 30s window)
        for _ in range(25):
            if not self._cm.has_active_executions():
                break
            await asyncio.sleep(1)

        # Step 3: Force-release any remaining locks
        released = await self._cm.release_all_held_locks()
        logger.info("Graceful shutdown: released %d locks", released)

        # Step 4: Exit
        raise SystemExit(0)

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down
```

### Acceptance Criteria

1. WHEN ECS sends SIGTERM, THE system SHALL stop accepting new `request_execution()` calls
   within 1 second
2. THE system SHALL wait up to 25 seconds for in-flight remediations to complete naturally
3. AFTER the wait period, THE system SHALL release all held DynamoDB locks explicitly
   (not relying on TTL expiry)
4. THE system SHALL exit with code 0 to signal clean shutdown to ECS
5. IF combined with Improvement 1 (heartbeats), THE heartbeat task SHALL also stop
   on SIGTERM, allowing locks to expire naturally as a fallback

### Integration with Improvement 1 (Heartbeats)

When heartbeats are implemented, the shutdown sequence becomes:
1. SIGTERM → stop heartbeats (locks will naturally expire if release fails)
2. Wait for in-flight to finish
3. Explicitly release locks (fast path — don't wait for TTL)
4. Exit cleanly

This double-safety means even if explicit release fails (DynamoDB unreachable during
shutdown), the heartbeat stopping ensures locks expire within one lease period.

### Effort Estimate: 0.5-1 day

---

## Improvement 11: Execution-Level Idempotency Key

### Priority: P2 — Prevents Duplicate SSM Command Execution

### Problem Statement

The current deduplication operates at the **alert level** (fingerprint = alert_name +
host + severity). But once an alert passes deduplication and reaches the SSM executor,
the executor can retry a failed API call (network timeout) — and the command might
execute TWICE on the host. The alert deduplicator won't catch this because it's the
same incident retrying, not a new alert.

Example failure sequence:
1. SSM `SendCommand` sent → network timeout (no response received)
2. Executor doesn't know if command executed or not
3. Executor retries → SSM executes the command AGAIN
4. Host gets restarted twice, or disk cleared twice

### Industry Precedent

[AWS Lambda Durable Functions Idempotency](https://docs.aws.amazon.com/lambda/latest/dg/durable-execution-idempotency.html):
Uses execution names to prevent duplicate runs. The same execution name returns
the previous result instead of re-executing.

[Idempotency for AI Agent Tools](https://bhavishyapandit9.substack.com/p/idempotency-and-retry-semantics-for):
"The execution layer decides what it can be trusted to attempt twice. Idempotency
is quietly becoming a foundational building block of production agents."

### Proposed Improvement

```
For each remediation execution:
1. Generate idempotency_key = f"{incident_id}:{step_number}:{attempt_number}"
2. Before executing SSM command:
   - Check DynamoDB for a record with this idempotency_key
   - If found with status=COMPLETED → return cached result (don't re-execute)
   - If found with status=IN_PROGRESS and age < timeout → wait and poll
   - If not found → write IN_PROGRESS record, then execute
3. After execution:
   - Update record with result + status=COMPLETED
4. TTL: 24 hours (matches incident memory store)

DynamoDB Schema addition:
  PK: IDEMPOTENCY#{idempotency_key}
  SK: RESULT
  status: IN_PROGRESS | COMPLETED | FAILED
  result_payload: {exit_code, stdout_truncated, duration}
  created_at: timestamp
  ttl: timestamp + 86400
```

### Acceptance Criteria

1. WHEN the SSM executor retries a command due to network timeout, THE system SHALL
   return the cached result instead of executing the command again
2. THE idempotency key SHALL include incident_id, step_number, and attempt_number
   to distinguish different steps within the same multi-step plan
3. THE idempotency record SHALL expire after 24 hours via DynamoDB TTL
4. IF the idempotency check itself fails (DynamoDB unreachable), THE system SHALL
   proceed with execution (fail-open for idempotency, fail-closed for locks)
5. THE cached result SHALL be returned within 100ms (DynamoDB single-item read)

### Effort Estimate: 1-1.5 days

---

## Improvement 12: Priority Inversion Prevention

### Priority: P3 — Reduces P1 Wait Time Behind Low-Priority Locks

### Problem Statement

When a P1 alert arrives for a host currently locked by a P3 remediation, the P1
must wait for the P3 to finish (up to 600 seconds). The preemption logic only
fires when severity difference ≥ 2 AND the conflict resolution strategy is PREEMPT.
For cases where preemption isn't configured (strategy = QUEUE), the P1 just waits.

This is the classic "priority inversion" problem from real-time systems — a high-
priority task blocked by a lower-priority task holding a shared resource.

### Industry Precedent

Real-time operating systems solve this with **priority inheritance**: when a high-
priority task blocks on a lock held by a low-priority task, the low-priority task
temporarily "inherits" the higher priority — meaning it gets more CPU time and
shorter timeouts to finish faster.

In the remediation context, "inheriting priority" means: reduce the remaining
timeout tolerance for the blocking execution, or boost its monitoring frequency.

### Proposed Improvement

```
When a P1/P2 action queues behind a P3/P4/P5 lock holder:

1. Record "priority pressure" on the lock:
   - lock.waiting_priority = P1 (highest waiting)
   - lock.priority_boost_at = now()

2. Apply priority boost to the blocking execution:
   - Reduce its remaining timeout from 600s → 120s (allow fast completion)
   - Increase monitoring frequency (check completion every 5s instead of 30s)
   - If blocking execution doesn't complete within boosted timeout:
     - Send SIGTERM to the blocking process
     - Wait 10s for graceful stop
     - Force-release the lock
     - Execute the P1 action

3. Notification:
   - Alert the operator: "P3 remediation on host-X was terminated early
     to allow P1 incident {id} to proceed"

4. After P1 completes:
   - Re-queue the terminated P3 action for retry
```

### Acceptance Criteria

1. WHEN a P1/P2 action queues behind a lower-priority lock holder, THE system SHALL
   reduce the remaining timeout for the blocking execution to 120 seconds
2. IF the blocking execution does not complete within the boosted timeout, THE system
   SHALL terminate it and release the lock for the higher-priority action
3. THE terminated action SHALL be re-queued at its original priority for later retry
4. THE system SHALL log the priority inversion event with both incident IDs
5. Priority boost SHALL only apply when the severity difference is ≥ 2 levels
   (P1 boosts P3/P4/P5, P2 boosts P4/P5 — same logic as preemption threshold)

### Trade-offs

| Pro | Con |
|-----|-----|
| P1 incidents resolved faster | Lower-priority work gets interrupted |
| Prevents indefinite P1 blocking | Adds complexity to lock management |
| Operator notified of termination | Terminated remediation may leave partial state |

### Mitigation

Combine with Improvement 6 (Compensating Transactions): when a lower-priority
action is terminated due to priority boost, execute its compensation steps
before releasing the lock.

### Effort Estimate: 2-3 days

---

## Implementation Plan

### Phase 0: Quick Wins (Week 0, First 2 Days) — Deployment Safety

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 0.1 | Add SIGTERM handler for graceful lock release | `src/main.py`, `src/concurrency/manager.py` | 0.5d |
| 0.2 | Add `set_draining()` and `release_all_held_locks()` to ConcurrencyManager | `src/concurrency/manager.py` | 0.5d |
| 0.3 | Add idempotency key check before SSM execution | `src/agentic_ai/executors/ssm_executor.py` | 1d |

**Deliverable:** Deployments no longer leak locks; SSM retries can't double-execute commands.

### Phase 1: Lock Safety (Week 1) — Prevents Split-Brain

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 1.1 | Add `fencing_token` field to HostLock model | `src/concurrency/models.py` | 0.5d |
| 1.2 | Implement heartbeat background task in LockStore | `src/concurrency/lock_store.py` | 1.5d |
| 1.3 | Add token validation to `complete_execution()` | `src/concurrency/manager.py` | 0.5d |
| 1.4 | Pass fencing_token as extra_var to executor | `src/orchestrator.py` | 0.5d |
| 1.5 | Write unit tests for heartbeat and fencing | `tests/unit/test_lock_heartbeat.py` | 1d |

**Deliverable:** Lock can no longer expire while actively held; stale holders are detected.

### Phase 2: Bulkhead Isolation (Week 2) — Prevents Cross-Service Starvation

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 2.1 | Create BulkheadManager class | `src/concurrency/bulkhead.py` | 1d |
| 2.2 | Add bulkhead config to ConcurrencyConfig | `src/concurrency/config.py` | 0.5d |
| 2.3 | Create bulkhead YAML configuration | `config/bulkhead_limits.yml` | 0.5d |
| 2.4 | Integrate BulkheadManager into ConcurrencyManager | `src/concurrency/manager.py` | 1d |
| 2.5 | Add bulkhead utilization to status API | `src/concurrency/api.py` | 0.5d |
| 2.6 | Write property tests for bulkhead isolation | `tests/property/test_bulkhead.py` | 1d |

**Deliverable:** Services have independent concurrency pools; P1 database fix is never blocked by P3 web-frontend queue.

### Phase 3: Fleet-Wide Safety (Week 2-3) — Prevents Cascading Fleet Damage

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 3.1 | Add FleetCircuitBreaker class | `src/concurrency/fleet_breaker.py` | 1d |
| 3.2 | Integrate fleet breaker into request_execution | `src/concurrency/manager.py` | 0.5d |
| 3.3 | Add adaptive ramp-up logic to dequeue | `src/concurrency/manager.py` | 1.5d |
| 3.4 | Add fleet breaker state to status API | `src/concurrency/api.py` | 0.5d |
| 3.5 | Write tests for fleet breaker + ramp-up | `tests/unit/test_fleet_breaker.py` | 1d |

**Deliverable:** System pauses all automation when multiple hosts fail simultaneously; resumes gradually.

### Phase 4: Resilience (Week 3-4) — Handles Edge Cases

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 4.1 | Add host poisoning logic | `src/concurrency/lock_store.py`, `manager.py` | 1d |
| 4.2 | Add unpoison API endpoint | `src/concurrency/api.py` | 0.5d |
| 4.3 | Add correlation-aware lock grouping | `src/concurrency/manager.py` | 1.5d |
| 4.4 | Add compensating transaction support | `src/concurrency/compensator.py` | 2d |
| 4.5 | Add compensate config to playbook mapping | `config/playbook_mapping.yml` | 0.5d |
| 4.6 | Add priority inversion prevention | `src/concurrency/manager.py`, `lock_store.py` | 2d |
| 4.7 | Write tests for poisoning + compensation + priority | `tests/unit/test_compensator.py`, `test_priority.py` | 1.5d |

**Deliverable:** Dead hosts stop consuming retry cycles; failed multi-step actions are partially rolled back; P1 incidents are never indefinitely blocked by P4.

### Phase 5: Observability + SQS FIFO (Week 4-5) — Persistence + Signals

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 5.1 | Add split metrics (lock vs compute contention) | `src/concurrency/metrics.py` | 0.5d |
| 5.2 | Add auto-scaling recommendation metric | `src/concurrency/metrics.py` | 0.5d |
| 5.3 | Evaluate SQS FIFO as complementary queue | (Spike/investigation) | 1d |
| 5.4 | If adopted: create FIFO queue in CDK | `src/agentic_ai/infra/stacks/data_stack.py` | 1d |
| 5.5 | If adopted: implement FIFO publisher/consumer | `src/concurrency/fifo_queue.py` | 2d |
| 5.6 | Integration tests for full flow | `tests/integration/test_concurrency_e2e.py` | 1d |

**Deliverable:** Better observability signals; optional persistent queue that survives ECS task restarts.

---

## New Files to Create

```
src/concurrency/
├── bulkhead.py              ← Per-service-group execution pools
├── fleet_breaker.py         ← Fleet-wide error threshold circuit breaker
├── compensator.py           ← Saga-style compensating transactions
├── fifo_queue.py            ← SQS FIFO integration (optional)
└── (existing files modified)

config/
├── bulkhead_limits.yml      ← Per-service concurrency caps
└── (existing playbook_mapping.yml extended with compensate_path)

tests/
├── unit/test_lock_heartbeat.py
├── unit/test_fleet_breaker.py
├── unit/test_compensator.py
├── property/test_bulkhead.py
└── integration/test_concurrency_e2e.py
```

---

## Configuration Examples

### `config/bulkhead_limits.yml`

```yaml
# Bulkhead Isolation Configuration
# Controls maximum concurrent executions per service group.
# Prevents one service from monopolizing all execution slots.

bulkheads:
  web-frontend:
    max_concurrent: 3
    overflow_to_global: true
  api-gateway:
    max_concurrent: 2
    overflow_to_global: true
  postgres-primary:
    max_concurrent: 1
    overflow_to_global: false  # NEVER exceed 1 for database
  redis-cache:
    max_concurrent: 1
    overflow_to_global: false
  background-workers:
    max_concurrent: 5
    overflow_to_global: true

defaults:
  max_concurrent: 2
  overflow_to_global: true

global:
  max_total_concurrent: 10
  reserved_for_p1: 3  # Always keep 3 slots for P1 alerts
```

---

## Total Effort Summary

| Phase | Duration | Effort | Key Deliverable |
|-------|----------|--------|-----------------|
| Phase 0: Quick Wins | Day 1-2 | 2 days | Graceful shutdown + idempotency keys |
| Phase 1: Lock Safety | Week 1 | 4 days | Heartbeats + fencing tokens |
| Phase 2: Bulkhead | Week 2 | 4.5 days | Per-service isolation |
| Phase 3: Fleet Safety | Week 2-3 | 4.5 days | Global circuit breaker + ramp-up |
| Phase 4: Resilience | Week 3-4 | 6.5 days | Poisoning + compensation + priority inversion |
| Phase 5: Observability | Week 4-5 | 6 days | Metrics + optional FIFO queue |
| **Total** | **5 weeks** | **~27.5 days** | |

---

## Dependencies and Risks

| Risk | Mitigation |
|------|-----------|
| Heartbeat adds DynamoDB write cost (every 10s per active lock) | Use DynamoDB on-demand; at 10 concurrent locks = 60 writes/min = negligible cost |
| SQS FIFO has 300 msg/s per MessageGroupId | Sufficient for per-host serialization; high-volume use per-host is unrealistic |
| Bulkhead misconfiguration could block services | Validate total of all bulkheads ≤ global max; default to allow if config missing |
| Compensation playbooks need to be idempotent | Document in runbook; enforce `--check` dry-run validation |
| Fleet breaker false positive during planned maintenance | Integration with Maintenance Window Manager: suppress fleet breaker during active windows |

---

## References

- [DynamoDB Lock Client — Heartbeats and Fencing](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_DistributedLocking.html)
- [SSM Automation Rate Controls](https://docs.aws.amazon.com/systems-manager/latest/userguide/running-automations-scale-controls.html)
- [Step Functions Saga Pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/implement-the-serverless-saga-pattern-by-using-aws-step-functions.html)
- [SQS FIFO Message Groups](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-understanding-logic.html)
- [Resilience4j Bulkhead Pattern](https://medium.com/@bolot.89/comprehensive-guide-to-resilience4j-and-the-circuit-breaker-pattern-85c6349d3535)
- [Fencing Tokens — Preventing Stale Lock Holders](https://levelup.gitconnected.com/beyond-the-lock-why-fencing-tokens-are-essential-5be0857d5a6a)
- [Kubernetes Lease Coordination](https://kubernetes.io/docs/concepts/architecture/leases/)
- [DynamoDB Conditional Write Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_ImplementingVersionControl.html)
