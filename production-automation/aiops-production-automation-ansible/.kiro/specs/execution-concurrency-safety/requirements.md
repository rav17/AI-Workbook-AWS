# Requirements Document

## Introduction

This feature adds concurrency safety mechanisms to the self-healing infrastructure system to prevent simultaneous Ansible playbook executions from interfering with each other. Currently, the orchestrator processes alerts concurrently (up to 50 pipelines) and the executor allows up to 10 simultaneous playbook executions with no conflict detection. Multiple alerts can fire simultaneously for the same host (e.g., HighCPUUsage and HighMemoryUsage both targeting web-server-01), causing double-restarts, race conditions, or cascading failures. This feature introduces host-level locking, alert deduplication, conflict detection, priority-based queuing, and circuit breaker patterns to ensure safe concurrent remediation.

## Glossary

- **Concurrency_Guard**: The module responsible for coordinating safe concurrent access to hosts and preventing conflicting playbook executions.
- **Host_Lock_Manager**: The component that maintains per-host asyncio locks ensuring only one playbook executes against a given host at any time.
- **Alert_Deduplicator**: The component that detects and suppresses duplicate or redundant alerts within a configurable suppression window.
- **Conflict_Matrix**: A configuration structure defining which playbooks are mutually exclusive and cannot run concurrently on the same host or dependent hosts.
- **Priority_Queue**: The component that orders pending remediation requests by alert severity (P1 > P2 > P3) with FIFO ordering within the same priority level.
- **Circuit_Breaker**: The component that tracks consecutive failures per host and halts further remediation attempts after a configurable failure threshold is reached.
- **Suppression_Window**: A configurable time duration during which duplicate alerts for the same host and alert name are suppressed.
- **Blast_Radius_Limiter**: The component that caps the maximum number of hosts undergoing simultaneous remediation to prevent widespread disruption.
- **Execution_Slot**: A position in the Priority_Queue representing a pending playbook execution request.
- **Conflict_Group**: A named set of playbooks that are mutually exclusive and cannot execute concurrently on the same host.

## Requirements

### Requirement 1: Host-Level Locking

**User Story:** As a platform engineer, I want only one playbook to execute against a given host at a time, so that concurrent remediations do not interfere with each other and cause undefined behavior.

#### Acceptance Criteria

1. WHEN a playbook execution is requested for a host, THE Host_Lock_Manager SHALL acquire an exclusive lock for that host before execution begins.
2. WHILE a lock is held for a host, THE Host_Lock_Manager SHALL queue subsequent execution requests for the same host until the lock is released.
3. WHEN a playbook execution completes (success, failure, or timeout), THE Host_Lock_Manager SHALL release the host lock within 1 second.
4. IF a lock acquisition exceeds a configurable wait timeout (default 120 seconds), THEN THE Host_Lock_Manager SHALL return a failure result with lock_result=LOCK_TIMEOUT and execution_status=FAILURE.
5. THE Host_Lock_Manager SHALL maintain independent locks per unique hostname, allowing concurrent executions across different hosts.
6. FOR ALL sequences of execution requests targeting the same host, acquiring then releasing a lock SHALL leave the Host_Lock_Manager in a state equivalent to no lock held (round-trip property).

### Requirement 2: Alert Deduplication and Suppression

**User Story:** As a platform engineer, I want duplicate alerts for the same host and alert type to be suppressed within a time window, so that alert storms do not trigger redundant remediations.

#### Acceptance Criteria

1. WHEN an alert is received for a host and alert name combination that was already processed within the Suppression_Window, THE Alert_Deduplicator SHALL suppress the duplicate alert and skip execution.
2. THE Alert_Deduplicator SHALL use a configurable Suppression_Window duration (default 300 seconds).
3. WHEN the Suppression_Window expires for a host and alert name combination, THE Alert_Deduplicator SHALL allow the next alert for that combination to proceed.
4. THE Alert_Deduplicator SHALL log each suppressed alert with the incident_id, alert_name, host, and reason for suppression.
5. WHEN a suppressed alert has higher severity than the original alert that established the suppression, THE Alert_Deduplicator SHALL allow the higher-severity alert to proceed and reset the Suppression_Window.
6. THE Alert_Deduplicator SHALL track suppression state independently per unique (hostname, alert_name) pair.
7. FOR ALL alert sequences within a Suppression_Window targeting the same host and alert name, the number of executions triggered SHALL be less than or equal to the number of distinct severity escalations plus one (metamorphic property).

### Requirement 3: Conflict Matrix and Mutual Exclusion Groups

**User Story:** As a platform engineer, I want to define which playbooks conflict with each other, so that mutually exclusive remediations do not run concurrently on the same host.

#### Acceptance Criteria

1. THE Conflict_Matrix SHALL be defined in a YAML configuration file specifying named Conflict_Groups, each containing a list of playbook paths that are mutually exclusive.
2. WHEN a playbook execution is requested, THE Concurrency_Guard SHALL check whether any playbook in the same Conflict_Group is currently executing on the same host.
3. IF a conflicting playbook is already executing on the same host, THEN THE Concurrency_Guard SHALL queue the new request until the conflicting execution completes.
4. THE Conflict_Matrix SHALL support defining conflicts across dependent services (e.g., playbooks targeting the same node but different services).
5. WHEN the Conflict_Matrix configuration file is invalid or missing, THE Concurrency_Guard SHALL log a warning and fall back to host-level locking only.
6. THE Conflict_Matrix parser SHALL produce a valid in-memory representation from any well-formed YAML configuration, and serializing that representation back to YAML SHALL produce an equivalent configuration (round-trip property).

### Requirement 4: Priority-Based Queuing

**User Story:** As a platform engineer, I want higher-severity alerts to be remediated before lower-severity alerts, so that critical issues are addressed first during alert storms.

#### Acceptance Criteria

1. THE Priority_Queue SHALL order Execution_Slots by severity: P1 (critical) before P2 (warning) before P3 (info).
2. WHILE multiple Execution_Slots have the same severity, THE Priority_Queue SHALL process them in FIFO order based on arrival time.
3. WHEN a P1 alert arrives and the Priority_Queue contains only P2 and P3 items for the same host, THE Priority_Queue SHALL schedule the P1 alert as the next execution for that host.
4. THE Priority_Queue SHALL expose the current queue depth per host as a metric for observability.
5. IF the Priority_Queue depth for a single host exceeds a configurable maximum (default 20), THEN THE Priority_Queue SHALL reject new entries and return a queue-full failure.
6. FOR ALL sequences of enqueue and dequeue operations, the Priority_Queue SHALL maintain the invariant that dequeued items are ordered by (severity descending, arrival_time ascending).

### Requirement 5: Circuit Breaker per Host

**User Story:** As a platform engineer, I want remediation attempts to stop after repeated failures on the same host, so that the system does not amplify problems by retrying against a broken host.

#### Acceptance Criteria

1. WHEN a playbook execution fails on a host, THE Circuit_Breaker SHALL increment the consecutive failure count for that host.
2. WHEN the consecutive failure count for a host exceeds a configurable threshold (default 3, meaning OPEN at 4 failures), THE Circuit_Breaker SHALL transition to OPEN state for that host.
3. WHILE the Circuit_Breaker is in OPEN state for a host, THE Circuit_Breaker SHALL reject all execution requests for that host and return a circuit-open failure result.
4. WHEN the Circuit_Breaker has been in OPEN state for a configurable recovery period (default 600 seconds), THE Circuit_Breaker SHALL transition to HALF-OPEN state.
5. WHILE the Circuit_Breaker is in HALF-OPEN state, THE Circuit_Breaker SHALL allow exactly one execution request through as a probe.
6. WHEN the probe execution succeeds in HALF-OPEN state, THE Circuit_Breaker SHALL transition to CLOSED state and reset the failure count to zero.
7. IF the probe execution fails in HALF-OPEN state, THEN THE Circuit_Breaker SHALL transition back to OPEN state and restart the recovery period.
8. WHEN a playbook execution succeeds on a host, THE Circuit_Breaker SHALL reset the consecutive failure count for that host to zero.
9. THE Circuit_Breaker SHALL expose the current state (CLOSED, OPEN, HALF-OPEN) per host as a metric.
10. FOR ALL sequences of success and failure events, the Circuit_Breaker state SHALL be deterministic: applying the same sequence of events from CLOSED state SHALL always produce the same final state (idempotence of state transitions given identical input).

### Requirement 6: Blast Radius Limiting

**User Story:** As a platform engineer, I want to cap the number of hosts undergoing simultaneous remediation, so that a widespread alert storm does not saturate infrastructure and cause cascading failures.

#### Acceptance Criteria

1. THE Blast_Radius_Limiter SHALL enforce a configurable maximum number of hosts undergoing concurrent remediation (default 5).
2. WHEN the number of hosts with active remediations reaches the maximum, THE Blast_Radius_Limiter SHALL queue new execution requests for additional hosts until an active host completes.
3. THE Blast_Radius_Limiter SHALL count distinct hosts, not distinct executions (a host with a queued second execution does not count twice).
4. THE Blast_Radius_Limiter SHALL expose the current active host count and queue depth as metrics.
5. IF the queued host count exceeds a configurable overflow threshold (default 50), THEN THE Blast_Radius_Limiter SHALL reject new requests and return a capacity-exceeded failure.
6. FOR ALL states of the Blast_Radius_Limiter, the number of hosts with active executions SHALL be less than or equal to the configured maximum (invariant property).

### Requirement 7: Concurrency Guard Integration with Orchestrator

**User Story:** As a platform engineer, I want the concurrency safety mechanisms to integrate seamlessly with the existing orchestrator pipeline, so that all protections are applied without requiring changes to the alert processing flow.

#### Acceptance Criteria

1. THE Concurrency_Guard SHALL be invoked by the Orchestrator between the match stage and the execute stage of the pipeline.
2. WHEN the Concurrency_Guard rejects an execution (lock timeout, circuit open, queue full, or capacity exceeded), THE Orchestrator SHALL log the rejection reason and dispatch a notification.
3. THE Concurrency_Guard SHALL accept the same parameters as the current executor interface (playbook_path, target_host, extra_vars) and return an ExecutionResult.
4. WHEN the Concurrency_Guard queues a request, THE Orchestrator SHALL await the result without blocking other independent pipeline executions.
5. THE Concurrency_Guard SHALL record an audit trail entry for each rejected or queued execution, including the rejection reason and queue wait time.
6. THE Concurrency_Guard SHALL expose metrics for: lock acquisitions, lock wait times, suppressed alerts, conflict rejections, circuit breaker trips, and queue depths.
