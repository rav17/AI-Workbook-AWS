# Requirements Document

## Introduction

This document defines the requirements for the Concurrent Execution Safety feature of the AIOps Production Automation system. The system currently uses a basic `asyncio.Semaphore(10)` for global concurrency limiting but lacks mechanisms to prevent interference between concurrent remediation executions targeting the same hosts or conflicting resources. This feature introduces host-level locking, resource conflict detection, alert deduplication, priority-based queuing, circuit breaker protection, and execution dependency management to ensure that concurrent remediations do not cause cascading failures or make incidents worse.

## Glossary

- **Concurrency_Manager**: The component responsible for coordinating concurrent remediation executions, enforcing host locks, detecting resource conflicts, and managing the priority queue
- **Host_Lock**: A mutual exclusion lock associated with a specific host identifier that prevents multiple remediations from executing against the same host simultaneously
- **Resource_Conflict_Registry**: A configuration-driven registry that maps each remediation action to the resources it modifies (e.g., services, ports, filesystems, memory), used to detect conflicts between concurrent executions
- **Resource_Conflict**: A condition where two or more pending remediation executions would modify overlapping resources on the same host or service, as determined by the Resource_Conflict_Registry
- **Suppression_Window**: A configurable time duration during which duplicate alerts (same alert name, same target host, same severity) are suppressed to prevent redundant remediation executions
- **Alert_Fingerprint**: A unique identifier derived from the combination of alert name, target host, and severity, used to detect duplicate alerts within the Suppression_Window
- **Priority_Queue**: An ordered queue of pending remediation executions sorted by alert severity (P1 highest, P5 lowest), then by arrival time within the same severity level
- **Circuit_Breaker**: A protection mechanism that stops automated remediation against a specific host after a configurable number of consecutive failures, requiring manual reset or automatic recovery after a cooldown period
- **Circuit_Breaker_State**: One of three states for a host's circuit breaker: CLOSED (normal operation, executions allowed), OPEN (executions blocked after consecutive failures), or HALF_OPEN (single test execution allowed after cooldown to verify recovery)
- **Execution_Dependency_Graph**: A directed acyclic graph defining ordering constraints between remediation actions, specifying which actions must complete before others can begin
- **Lock_Store**: The persistent storage (DynamoDB) holding active Host_Locks, Circuit_Breaker_States, and Suppression_Window records
- **Remediation_Action**: A specific playbook or SSM document execution targeting a host or resource
- **Conflict_Resolution_Strategy**: The action taken when a Resource_Conflict is detected: QUEUE (wait for conflicting execution to complete), REJECT (fail immediately with conflict reason), or PREEMPT (cancel lower-priority conflicting execution)

## Requirements

### Requirement 1: Host-Level Mutual Exclusion

**User Story:** As an operations engineer, I want only one remediation to execute against a given host at a time, so that concurrent playbooks do not interfere with each other and cause partial restarts or cascading failures.

#### Acceptance Criteria

1. WHEN a Remediation_Action is submitted for execution against a target host, THE Concurrency_Manager SHALL attempt to acquire a Host_Lock for that host before execution begins
2. WHILE a Host_Lock is held for a target host, THE Concurrency_Manager SHALL prevent any other Remediation_Action from executing against that same host
3. WHEN a Remediation_Action completes (success, failure, or timeout), THE Concurrency_Manager SHALL release the Host_Lock for the target host within 2 seconds of completion
4. IF a Host_Lock cannot be acquired because another execution holds the lock, THEN THE Concurrency_Manager SHALL place the pending Remediation_Action in the Priority_Queue and record the queue entry with: incident ID, target host, requested action, queue position, and timestamp of queuing
5. WHEN a Host_Lock is released, THE Concurrency_Manager SHALL dequeue the highest-priority pending Remediation_Action for that host from the Priority_Queue ordered by alert severity descending (P1 before P2 before P3) and then by queue entry timestamp ascending (earliest first among equal severity), and attempt execution
6. IF a Host_Lock is held for longer than a configurable maximum duration (default 600 seconds, minimum 60 seconds, maximum 3600 seconds), THEN THE Concurrency_Manager SHALL forcibly release the lock, mark the holding execution as timed-out, and log a warning indicating the forced lock release with the incident ID and duration held
7. THE Concurrency_Manager SHALL store Host_Lock state in the Lock_Store with a TTL equal to the maximum lock duration to prevent orphaned locks from blocking future executions
8. WHEN a Remediation_Action targets multiple hosts (maximum 20 hosts), THE Concurrency_Manager SHALL acquire Host_Locks for all target hosts atomically; IF any single host lock cannot be acquired, THEN THE Concurrency_Manager SHALL release all already-acquired locks for that action and queue the entire multi-host action; WHEN a Host_Lock is subsequently released for any host required by the queued multi-host action, THE Concurrency_Manager SHALL re-attempt atomic acquisition of all required locks before executing the action
9. IF the Lock_Store is unreachable or returns an error when the Concurrency_Manager attempts to acquire or release a Host_Lock, THEN THE Concurrency_Manager SHALL atomically reject the Remediation_Action execution and mark the action as failed with an error indicating Lock_Store unavailability, guaranteeing that no execution attempt occurs once the action is marked as failed, and log a warning with the incident ID and the specific Lock_Store error

### Requirement 2: Resource-Level Conflict Detection

**User Story:** As a platform engineer, I want the system to detect when two remediations would modify conflicting resources, so that actions like scaling up and draining connections do not execute simultaneously.

#### Acceptance Criteria

1. THE Resource_Conflict_Registry SHALL define for each Remediation_Action a list of resource categories it modifies (maximum 20 resource categories per action), where each resource category is a string identifier with a maximum length of 128 characters (e.g., "service:nginx", "filesystem:/var/log", "network:port-80", "memory:system")
2. WHEN a Remediation_Action is submitted, THE Concurrency_Manager SHALL query the Resource_Conflict_Registry to retrieve the resource categories for the submitted action and compare them against resource categories of all currently executing Remediation_Actions on the same host or service
3. IF the submitted Remediation_Action shares one or more resource categories with a currently executing action on the same host, THEN THE Concurrency_Manager SHALL apply the configured Conflict_Resolution_Strategy for that resource category
4. WHEN the Conflict_Resolution_Strategy is QUEUE, THE Concurrency_Manager SHALL place the submitted action in the Priority_Queue regardless of whether a conflicting execution is currently active, and SHALL hold the action until any conflicting execution completes or a configurable maximum queue wait time (default 600 seconds, minimum 60 seconds, maximum 3600 seconds) elapses; IF the maximum queue wait time elapses, THEN THE Concurrency_Manager SHALL fail the queued action with a timeout error indicating the conflicting resource categories and the duration waited
5. WHEN the Conflict_Resolution_Strategy is REJECT, THE Concurrency_Manager SHALL immediately fail the submitted action with a conflict error containing: the conflicting resource categories, the incident ID of the blocking execution, and the estimated remaining duration of the blocking execution
6. WHEN the Conflict_Resolution_Strategy is PREEMPT and the submitted action has a strictly higher numeric priority value than the currently executing action (where lower numeric value indicates higher priority), THE Concurrency_Manager SHALL cancel the lower-priority execution, release its locks within 10 seconds, automatically queue the preempted action at its original priority level to run after the higher-priority action completes, and proceed with the higher-priority action; IF lock release does not complete within 10 seconds, THEN THE Concurrency_Manager SHALL force-release the locks and log a warning
7. IF the Conflict_Resolution_Strategy is PREEMPT and the submitted action has equal or lower priority (equal or higher numeric value) than the currently executing action, THEN THE Concurrency_Manager SHALL reject the submitted action with a conflict error indicating that preemption was denied due to insufficient priority
8. IF a Remediation_Action is not registered in the Resource_Conflict_Registry, THEN THE Concurrency_Manager SHALL treat the action as having no declared resource categories and allow execution without resource-level conflict checks, logging a warning that the action lacks resource declarations
9. THE Resource_Conflict_Registry SHALL be loadable from a YAML configuration file and support runtime updates without service restart, applying configuration changes within 30 seconds of file modification; IF the YAML configuration file is malformed or fails schema validation, THEN THE Resource_Conflict_Registry SHALL retain the previously loaded valid configuration and log an error indicating the validation failure

### Requirement 3: Alert Deduplication and Suppression

**User Story:** As an operations engineer, I want duplicate alerts firing within a short window to be deduplicated, so that the same remediation does not execute multiple times for the same underlying issue.

#### Acceptance Criteria

1. WHEN an alert is received, THE Concurrency_Manager SHALL compute an Alert_Fingerprint by deterministically combining the alert name, target host, and severity into a single identifier such that identical inputs always produce the same fingerprint value
2. WHEN an alert is received and a matching Alert_Fingerprint exists in the Lock_Store with a timestamp within the active Suppression_Window, THE Concurrency_Manager SHALL suppress the duplicate alert, skip execution, and log the suppression with: alert fingerprint, original incident ID, duplicate incident ID, and time since the original alert
3. WHEN an alert is received and no matching Alert_Fingerprint exists within the Suppression_Window, THE Concurrency_Manager SHALL acquire a lock on the Alert_Fingerprint in the Lock_Store using a conditional write (create-if-not-exists) with the current timestamp and proceed with normal execution only if the lock is successfully acquired; THE Concurrency_Manager MAY still reject the alert after successful lock acquisition if other validation checks fail (e.g., circuit breaker open, queue full)
4. THE Suppression_Window SHALL be configurable via environment variable (default 300 seconds, minimum 30 seconds, maximum 1800 seconds)
5. IF the Suppression_Window environment variable is set to a value below 30 seconds, above 1800 seconds, or is not a valid integer, THEN THE Concurrency_Manager SHALL fall back to the default value of 300 seconds and log a warning indicating the invalid configuration value
6. WHEN a remediation execution completes with failure status, THE Concurrency_Manager SHALL clear the Alert_Fingerprint from the Lock_Store to allow a subsequent alert for the same issue to trigger a retry; WHEN a remediation execution completes with success or timeout status, THE Concurrency_Manager SHALL retain the Alert_Fingerprint in the Lock_Store until TTL expiry to prevent duplicate execution within the Suppression_Window
7. THE Concurrency_Manager SHALL store Alert_Fingerprint records in the Lock_Store with a TTL equal to the Suppression_Window duration to ensure automatic cleanup of expired suppression records
8. IF the Lock_Store is unreachable or returns an error when the Concurrency_Manager attempts to read or write an Alert_Fingerprint, THEN THE Concurrency_Manager SHALL suppress the alert without executing remediation if a locally cached fingerprint match indicates an obvious duplicate; otherwise THE Concurrency_Manager SHALL reject the alert without executing remediation, log an error indicating the Lock_Store failure reason, and allow the alert to be retried via the Event_Bus retry mechanism
9. IF a conditional write to the Lock_Store fails because a matching Alert_Fingerprint was concurrently created by another process, THEN THE Concurrency_Manager SHALL treat the alert as a duplicate and suppress it

### Requirement 4: Priority-Based Execution Queuing

**User Story:** As an SRE, I want higher-severity alerts to preempt lower-severity ones for lock acquisition, so that P1 incidents are not blocked by P3 remediations.

#### Acceptance Criteria

1. THE Priority_Queue SHALL order pending Remediation_Actions by severity level (P1 highest priority through P5 lowest priority), then by arrival timestamp (earliest first) within the same severity level
2. WHEN a Host_Lock is released, THE Concurrency_Manager SHALL select the highest-priority pending action for that host from the Priority_Queue, not the longest-waiting action
3. WHEN a P1 or P2 severity alert is received and the target host has a Host_Lock held by a P4 or P5 severity execution, THE Concurrency_Manager SHALL preempt the lower-priority execution by sending a cancellation signal, waiting up to 10 seconds for graceful termination, and then forcibly terminating the execution if the signal is not acknowledged
4. WHEN a preemption occurs, THE Concurrency_Manager SHALL record the preemption event with: preempted incident ID, preempting incident ID, severity of both, and timestamp, and SHALL re-queue the preempted action at its original priority level with its original arrival timestamp preserved for queue ordering
5. IF the severity difference between a pending higher-priority action and a currently executing lower-priority action is less than 2 levels (e.g., P2 SHALL NOT preempt P3), THEN THE Concurrency_Manager SHALL not preempt the executing action and SHALL queue the higher-priority action to await lock release
6. IF the Priority_Queue for a specific host exceeds a configurable maximum depth (default 20, minimum 5, maximum 100), THEN THE Concurrency_Manager SHALL reject new submissions for that host with a queue-full error and log the rejection with the current queue depth and host identifier
7. WHEN a Remediation_Action has been queued for longer than a configurable maximum wait time (default 600 seconds, minimum 60 seconds, maximum 3600 seconds), THE Concurrency_Manager SHALL expire the queued action, mark it as timed-out-in-queue in the Incident_Memory_Store, and log the expiration with incident ID and wait duration
8. WHEN a preemption forcibly terminates an execution, THE Concurrency_Manager SHALL mark any partial work from the preempted action as incomplete in the Incident_Memory_Store and record the execution progress at the point of termination (step number completed out of total steps)
9. IF a Remediation_Action is submitted to the Priority_Queue with an incident ID that already exists in the queue for the same host, THEN THE Concurrency_Manager SHALL reject the duplicate submission and log the rejection with the incident ID and host identifier

### Requirement 5: Circuit Breaker Protection

**User Story:** As an operations engineer, I want the system to stop executing against a host after repeated failures, so that a misconfigured or degraded host does not receive continuous failed remediation attempts.

#### Acceptance Criteria

1. THE Concurrency_Manager SHALL maintain a Circuit_Breaker_State for each host that has received at least one remediation execution, with valid states being CLOSED, OPEN, or HALF_OPEN, and an initial state of CLOSED
2. WHEN a Remediation_Action against a host completes with a failed outcome (exit status indicating error, execution timeout, or SSM delivery failure), THE Concurrency_Manager SHALL increment the consecutive failure counter for that host in the Lock_Store; a successful remediation outcome SHALL reset the consecutive failure counter to zero
3. WHEN the consecutive failure counter for a host reaches a configurable threshold (default 3, minimum 2, maximum 10), THE Concurrency_Manager SHALL transition the Circuit_Breaker_State for that host from CLOSED to OPEN
4. WHILE the Circuit_Breaker_State for a host is OPEN, THE Concurrency_Manager SHALL reject all Remediation_Actions targeting that host with a circuit-open error containing: host identifier, failure count, time of last failure, and estimated cooldown remaining in seconds
5. WHILE the Circuit_Breaker_State for a host is OPEN, WHEN the configurable cooldown period (default 300 seconds, minimum 60 seconds, maximum 3600 seconds) has elapsed since the last failure, THE Concurrency_Manager SHALL transition the state to HALF_OPEN
6. WHILE the Circuit_Breaker_State for a host is HALF_OPEN, THE Concurrency_Manager SHALL allow exactly one Remediation_Action to execute as a probe and reject all other Remediation_Actions targeting that host until the probe completes
7. WHEN a probe Remediation_Action in HALF_OPEN state succeeds, THE Concurrency_Manager SHALL transition the Circuit_Breaker_State to CLOSED and reset the failure counter to zero
8. IF a probe Remediation_Action in HALF_OPEN state fails, THEN THE Concurrency_Manager SHALL transition the Circuit_Breaker_State back to OPEN and restart the cooldown period from the time of the probe failure
9. WHEN the Circuit_Breaker_State transitions to OPEN, THE Concurrency_Manager SHALL dispatch a notification to the configured escalation channel containing: host identifier, consecutive failure count, list of failed incident IDs (up to the last 5), and the name of the last failed remediation action
10. THE Concurrency_Manager SHALL support manual circuit breaker reset via an API endpoint that accepts a host identifier and transitions the state from OPEN or HALF_OPEN to CLOSED, resetting the failure counter; IF the host is already in CLOSED state, THEN THE Concurrency_Manager SHALL return a success response with no state change; IF the host identifier is not found in the Lock_Store, THEN THE Concurrency_Manager SHALL return an error response indicating the host has no circuit breaker state
11. IF the configurable failure threshold or cooldown period environment variable is set to a value outside its valid range or is not a valid integer, THEN THE Concurrency_Manager SHALL fall back to the default value and log a warning indicating the invalid configuration value

### Requirement 6: Execution Dependency Management

**User Story:** As a platform engineer, I want to define ordering constraints between remediation actions, so that dependent actions execute in the correct sequence and independent actions can safely run in parallel.

#### Acceptance Criteria

1. THE Execution_Dependency_Graph SHALL define directed edges between Remediation_Actions where an edge from action A to action B means action A must complete successfully (SSM command returns a success exit status) before action B can begin
2. WHEN a Remediation_Action is submitted and the Execution_Dependency_Graph specifies predecessor actions that have not yet completed for the same incident or correlation group, THE Concurrency_Manager SHALL hold the action in a waiting state until all predecessors complete successfully; IF a waiting action's predecessors have not all completed within a configurable dependency timeout (default 600 seconds, minimum 60 seconds, maximum 3600 seconds), THEN THE Concurrency_Manager SHALL mark the waiting action as failed with a dependency-timeout reason and cancel its execution
3. IF a predecessor action in the Execution_Dependency_Graph fails or times out, THEN THE Concurrency_Manager SHALL mark all transitively dependent successor actions (direct successors and their successors recursively through the graph) as skipped with a dependency-failed reason containing the failed predecessor's incident ID and action name
4. THE Execution_Dependency_Graph SHALL be loadable from a YAML configuration file and SHALL be validated on load to reject cycles; IF a cycle is detected, THEN THE Concurrency_Manager SHALL log an error identifying the cycle path and refuse to load the graph, retaining the previously loaded valid graph
5. WHEN two or more Remediation_Actions have no dependency relationship in the Execution_Dependency_Graph and target different hosts, THE Concurrency_Manager SHALL allow parallel execution up to the SSM_Executor concurrency limit, subject to host-level locking where no two actions targeting the same host execute simultaneously
6. THE Execution_Dependency_Graph SHALL support a maximum of 200 nodes (actions) and 500 edges (dependencies); IF the configuration exceeds these limits, THEN THE Concurrency_Manager SHALL reject the configuration with an error indicating which limit was exceeded

### Requirement 7: Observability and Audit for Concurrency Events

**User Story:** As an SRE, I want visibility into why an execution was queued, blocked, or skipped, so that I can understand system behavior under high alert volume and tune concurrency parameters.

#### Acceptance Criteria

1. WHEN a Remediation_Action is queued due to host lock contention, THE Concurrency_Manager SHALL emit a structured JSON log entry within 2 seconds of the queuing event containing: incident ID, target host, blocking incident ID, queue position, and estimated wait time in seconds (calculated from the average lock hold duration for that host over the previous 60 minutes, or the configured maximum lock duration if no history is available)
2. WHEN a Remediation_Action is rejected due to resource conflict, THE Concurrency_Manager SHALL emit a structured JSON log entry within 2 seconds of the rejection containing: incident ID, target host, conflicting resource categories, blocking incident ID, and conflict resolution strategy applied (QUEUE, REJECT, or PREEMPT)
3. WHEN a duplicate alert is suppressed, THE Concurrency_Manager SHALL emit a structured JSON log entry within 2 seconds of the suppression containing: alert fingerprint, suppressed incident ID, original incident ID, and suppression window remaining in seconds
4. WHEN a circuit breaker transitions state, THE Concurrency_Manager SHALL emit a structured JSON log entry within 2 seconds of the transition containing: host identifier, previous state (CLOSED, OPEN, or HALF_OPEN), new state (CLOSED, OPEN, or HALF_OPEN), consecutive failure count, and trigger event (failure, cooldown elapsed, test success, test failure, or manual reset)
5. THE Concurrency_Manager SHALL publish custom CloudWatch metrics at 60-second intervals for: lock acquisitions per minute, lock contentions per minute, queue depth per host, suppressed alerts per minute, circuit breaker trips per minute, preemptions per minute, and average lock hold duration in seconds per minute
6. WHEN a preemption occurs, THE Concurrency_Manager SHALL emit a structured JSON log entry within 2 seconds of the preemption containing: preempted incident ID, preempting incident ID, severity of both (P1 through P5), target host, and preemption reason (severity difference threshold met, or manual override)
7. THE Concurrency_Manager SHALL expose a status API endpoint that returns within 5 seconds a JSON object containing: all active Host_Locks (maximum 1000 entries), Priority_Queue depths per host, Circuit_Breaker_States, and active Suppression_Window entries; IF the number of active entries exceeds 1000 in any category, THEN the response SHALL include only the 1000 most recent entries and a total count field indicating the full number
8. IF the Concurrency_Manager fails to publish CloudWatch metrics for 3 consecutive 60-second intervals, THEN THE Concurrency_Manager SHALL emit a structured JSON log entry indicating the metric publishing failure with the timestamp of the last successful publish and the error reason, and SHALL retry publishing on the next interval; this log emission requirement is independent of the metric publishing itself and does not require successful metric delivery
9. IF the Concurrency_Manager fails to emit a structured log entry for any concurrency event, THEN THE Concurrency_Manager SHALL retry the log emission once within 5 seconds; if the retry fails, THE Concurrency_Manager SHALL increment a local dropped-logs counter and continue processing without blocking the concurrency operation
