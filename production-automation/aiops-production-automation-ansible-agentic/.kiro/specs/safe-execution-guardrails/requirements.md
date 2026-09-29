# Requirements Document

## Introduction

The Safe Execution Guardrails feature introduces a multi-layered safety framework between the playbook matching stage and the playbook execution stage of the AIOps self-healing pipeline. Currently, the orchestrator pipeline (normalize → enrich → match → execute → notify) has no safety gates between alert matching and playbook execution. This means destructive actions like service restarts can execute immediately without verifying peer health, draining traffic, checking for concurrent operations, or obtaining human approval for high-risk targets. This feature adds blast radius classification, human approval gates, pre-execution health checks, traffic draining, concurrency guards, circuit breaker logic, self-protection, and maintenance window awareness to prevent outages caused by automated remediation.

## Glossary

- **Guardrail_Engine**: The component that evaluates all safety checks between playbook matching and playbook execution, producing an allow/deny/defer decision
- **Blast_Radius_Classifier**: The component that assigns a risk level (low, medium, high, critical) to a remediation action based on the target service, playbook type, and environment context
- **Approval_Gate**: The component that requests and awaits human approval for high-risk or critical-risk remediation actions via configured notification channels
- **Health_Checker**: The component that verifies the target host has healthy peers and is not the last healthy instance in its service group before allowing destructive actions
- **Traffic_Drainer**: The component that removes a target instance from its load balancer, waits for in-flight requests to complete, and re-registers the instance after successful remediation
- **Concurrency_Guard**: The component that prevents duplicate remediations on the same host/service and enforces rolling restart percentage limits within a service group
- **Circuit_Breaker**: The component that tracks remediation failure rates and halts all automated actions when failures exceed a configured threshold within a time window
- **Self_Protection_Guard**: The component that detects and blocks remediation actions targeting the automation host itself or its critical dependencies
- **Maintenance_Window_Manager**: The component that checks whether the current time falls within a configured maintenance or deployment window and defers or blocks destructive actions accordingly
- **Service_Group**: A logical grouping of hosts that provide the same service (e.g., all web-frontend instances behind a load balancer)
- **Risk_Level**: An enumeration of low, medium, high, or critical that determines which guardrail policies apply to a remediation action
- **Remediation_Action**: A combination of a matched playbook and a target host that the executor would run
- **Guardrail_Decision**: The output of the Guardrail_Engine: one of ALLOW, DENY, DEFER, or PENDING_APPROVAL
- **Rolling_Restart_Percentage**: The maximum percentage of instances in a Service_Group that may be restarted concurrently

## Requirements

### Requirement 1: Blast Radius Classification

**User Story:** As an operations engineer, I want each remediation action classified by risk level, so that appropriate safety policies are applied based on the potential impact of the action.

#### Acceptance Criteria

1. WHEN a Remediation_Action is evaluated, THE Blast_Radius_Classifier SHALL assign exactly one Risk_Level of low, medium, high, or critical based on the target service name, playbook type (e.g., restart, stop, scale, log-rotate), and environment tier (production, staging, or development), and SHALL complete the classification within 2 seconds of receiving the action for evaluation
2. THE Blast_Radius_Classifier SHALL load risk classification rules from a YAML configuration file at `config/risk_classification.yml` on service startup and support runtime reload within 30 seconds of file modification without requiring service restart; IF the reloaded file is malformed or fails schema validation, THEN THE Blast_Radius_Classifier SHALL retain the previously loaded valid configuration and log an error indicating the validation failure
3. IF the risk classification configuration file is missing at startup or fails YAML parsing, THEN THE Blast_Radius_Classifier SHALL default all actions to high Risk_Level and log a warning indicating the file path and the specific error (file not found or parse error)
4. THE Blast_Radius_Classifier SHALL classify services listed as single-instance (no peers) in the risk classification configuration as critical Risk_Level regardless of other rules; THE single-instance classification SHALL be applied as a base rule before environment tier elevation; since critical is the maximum Risk_Level, no further elevation applies; this rule SHALL NOT prevent other non-single-instance services from reaching critical Risk_Level through other classification rules (AC5, AC7, or AC6)
5. WHEN a playbook performs a restart or stop action on a service categorized as a database service in the risk classification configuration, THE Blast_Radius_Classifier SHALL assign critical Risk_Level
6. IF a Remediation_Action references a service name or playbook type not present in the loaded risk classification rules, THEN THE Blast_Radius_Classifier SHALL assign a default Risk_Level of high and log a warning indicating the unmatched service name or playbook type
7. WHEN the environment tier is production, THE Blast_Radius_Classifier SHALL elevate the Risk_Level by one level (low becomes medium, medium becomes high, high becomes critical, critical remains critical) compared to the base rule match for the same service and playbook type in non-production tiers

### Requirement 2: Human Approval Gates

**User Story:** As an operations engineer, I want high-risk and critical-risk actions to require human approval before execution, so that destructive automation does not proceed without human oversight.

#### Acceptance Criteria

1. WHEN the Blast_Radius_Classifier assigns a Risk_Level of high or critical, THE Approval_Gate SHALL send an approval request to the configured notification channel containing: remediation action name, target host identifier, service name, Risk_Level, incident ID, and alert summary
2. WHILE the Approval_Gate is awaiting a response, THE Guardrail_Engine SHALL return a Guardrail_Decision of PENDING_APPROVAL and the pipeline SHALL pause execution for that incident
3. WHEN a human approves the action within the configured timeout period, THE Guardrail_Engine SHALL return a Guardrail_Decision of ALLOW and the pipeline SHALL proceed to execution
4. WHEN a human denies the action, THE Guardrail_Engine SHALL return a Guardrail_Decision of DENY, the pipeline SHALL skip execution, and the Approval_Gate SHALL send a denial notification to the configured notification channel containing: incident ID, denied action name, target host, and the identity of the responder who denied
5. IF the approval timeout expires without a response, THEN THE Guardrail_Engine SHALL return a Guardrail_Decision of DENY and dispatch an escalation notification to the configured notification channel containing: incident ID, action name, target host, Risk_Level, and the timeout duration that elapsed
6. THE Approval_Gate SHALL support a configurable timeout (default 300 seconds, minimum 30 seconds, maximum 1800 seconds); IF the configured timeout value is below 30 seconds, above 1800 seconds, or is not a valid integer, THEN THE Approval_Gate SHALL fall back to the default value of 300 seconds and log a warning indicating the invalid configuration value
7. WHEN the Risk_Level is low or medium, THE Approval_Gate SHALL not be invoked and the pipeline SHALL proceed without human approval
8. IF the Approval_Gate fails to deliver the approval request to the configured notification channel within 10 seconds, THEN THE Approval_Gate SHALL retry delivery up to 2 times with exponential backoff starting at 2 seconds, and if all retries fail, SHALL return a Guardrail_Decision of DENY and log an error indicating the notification delivery failure reason

### Requirement 3: Pre-Execution Health Checks

**User Story:** As an operations engineer, I want the system to verify that a target host has healthy peers before restarting it, so that the automation does not take down the last healthy instance of a service.

#### Acceptance Criteria

1. WHEN a Remediation_Action targets a host in a Service_Group with 2 or more instances, THE Health_Checker SHALL query the health status of all peer instances (excluding the target) in that Service_Group by issuing an HTTP GET request to each peer's configurable health endpoint and treating an HTTP 2xx response received within 5 seconds as healthy and any other response, timeout, or connection error as unhealthy
2. IF the target host is the only healthy instance in its Service_Group (all peers are unhealthy or no peers exist), THEN THE Guardrail_Engine SHALL return a Guardrail_Decision of DENY and dispatch an escalation notification to the configured escalation channel containing: target host identifier, Service_Group name, number of unhealthy peers, and the denied Remediation_Action name
3. IF fewer than 2 healthy peer instances remain in the Service_Group after excluding the target, THEN THE Guardrail_Engine SHALL return a Guardrail_Decision of DENY for critical Risk_Level actions; for high, medium, and low Risk_Level actions, THE Guardrail_Engine SHALL return a Guardrail_Decision of ALLOW and log a warning indicating reduced peer availability
4. WHEN the Health_Checker cannot determine peer health status within 10 seconds of initiating the check, THE Guardrail_Engine SHALL treat the check as failed and return a Guardrail_Decision of DENY for high and critical Risk_Level actions; for medium and low Risk_Level actions, THE Guardrail_Engine SHALL return a Guardrail_Decision of ALLOW and log a warning indicating the health check timed out
5. THE Health_Checker SHALL determine instance health by issuing an HTTP GET request to a configurable health endpoint for each peer in the Service_Group, where a response with HTTP status code in the range 200-299 received within 5 seconds indicates a healthy instance
6. IF the Remediation_Action targets a host in a Service_Group with only 1 instance (no peers), THEN THE Guardrail_Engine SHALL return a Guardrail_Decision of DENY for critical and high Risk_Level actions and dispatch an escalation notification to the configured escalation channel indicating that no peers are available for health verification

### Requirement 4: Traffic Draining

**User Story:** As an operations engineer, I want the system to drain traffic from an instance before restarting it, so that in-flight requests are not dropped during remediation.

#### Acceptance Criteria

1. WHEN a Remediation_Action with Risk_Level of medium or higher targets a load-balanced instance, THE Traffic_Drainer SHALL remove the target instance from the load balancer within 30 seconds of initiating the removal request and before playbook execution begins
2. WHEN the target instance has been removed from the load balancer, THE Traffic_Drainer SHALL wait for a configurable drain period (default 30 seconds, minimum 5 seconds, maximum 300 seconds) to allow in-flight requests to complete before signaling that playbook execution may proceed
3. WHEN playbook execution completes successfully, THE Traffic_Drainer SHALL re-register the instance with the load balancer within 60 seconds of execution completion; THE Traffic_Drainer SHALL attempt re-registration after playbook execution regardless of whether the initial removal from the load balancer succeeded
4. WHEN playbook execution fails, THE Traffic_Drainer SHALL re-register the instance with the load balancer within 60 seconds and include the re-registration status (success or failure with error reason) in the execution result
5. IF the Traffic_Drainer fails to remove the instance from the load balancer within 30 seconds or receives an error response from the load balancer API, THEN THE Traffic_Drainer SHALL verify the instance is no longer receiving traffic by confirming it is absent from the load balancer's active target list; IF the instance remains in the active target list after the 30-second removal window, THEN THE Guardrail_Engine SHALL return a Guardrail_Decision of DENY and log the failure reason including the target instance identifier and the specific error condition
6. THE Traffic_Drainer SHALL verify the instance passes a health check before re-registering it with the load balancer by confirming the instance returns a successful response (HTTP 200) on the configured health check endpoint within a configurable timeout (default 60 seconds, minimum 10 seconds, maximum 300 seconds), polling at 5-second intervals
7. IF the instance fails to pass the health check within the configured health check timeout after playbook execution completes, THEN THE Traffic_Drainer SHALL re-register the instance with the load balancer regardless, mark the health check as failed in the execution result, and log a warning indicating the instance identifier and the number of failed health check attempts
8. IF the Traffic_Drainer fails to re-register the instance with the load balancer after playbook execution (success or failure), THEN THE Traffic_Drainer SHALL retry re-registration up to 3 times with exponential backoff starting at 2 seconds, and if all retries fail, SHALL log an error with the instance identifier and failure reason and include the re-registration failure in the execution result

### Requirement 5: Concurrency and Deduplication Guards

**User Story:** As an operations engineer, I want the system to prevent duplicate remediations and limit concurrent restarts, so that cascading failures and restart storms are avoided.

#### Acceptance Criteria

1. WHEN a Remediation_Action targets a host that already has a concurrency slot held (a lock exists in the lock mechanism that has not expired and has not been released), THE Concurrency_Guard SHALL return a Guardrail_Decision of DENY with reason "duplicate_remediation"
2. WHEN a Remediation_Action targets a service in a Service_Group and the number of hosts currently holding concurrency slots in that Service_Group equals or exceeds the Rolling_Restart_Percentage of the total Service_Group size, THE Concurrency_Guard SHALL return a Guardrail_Decision of DEFER for that action
3. IF the Concurrency_Guard returns a Guardrail_Decision of DEFER, THEN THE Concurrency_Guard SHALL re-evaluate the deferred action within 30 seconds after any concurrency slot is released in the same Service_Group; IF the action remains deferred for longer than a configurable maximum defer duration (default 600 seconds, minimum 60 seconds, maximum 3600 seconds), THEN THE Concurrency_Guard SHALL expire the action and return a Guardrail_Decision of DENY with reason "defer_timeout"
4. THE Concurrency_Guard SHALL use a configurable Rolling_Restart_Percentage (default 25 percent, minimum 5 percent, maximum 50 percent) of the Service_Group size; THE rolling restart threshold SHALL always be computed as the maximum of the percentage calculation or 1 (ensuring at least 1 host may be remediated concurrently); no manual overrides of the computed threshold SHALL be permitted
5. WHEN a remediation completes (success or failure), THE Concurrency_Guard SHALL release the concurrency slot for that host and Service_Group within 5 seconds
6. THE Concurrency_Guard SHALL track active remediations using a lock mechanism with automatic expiry after the configured SSM_Executor timeout (default 300 seconds) plus 60 seconds
7. IF the lock mechanism is unreachable or returns an error when the Concurrency_Guard attempts to acquire or release a concurrency slot, THEN THE Concurrency_Guard SHALL reject the Remediation_Action with a Guardrail_Decision of DENY with reason "lock_store_unavailable" and log a warning indicating the lock mechanism error

### Requirement 6: Circuit Breaker

**User Story:** As an operations engineer, I want the system to halt all automated actions when multiple remediations fail in a short period, so that a systemic issue does not cause cascading damage.

#### Acceptance Criteria

1. WHEN the number of Remediation_Actions that complete with a failed outcome (exit status indicating error, execution timeout, or delivery failure) within the configured time window exceeds the configured failure threshold, THE Circuit_Breaker SHALL transition to an OPEN state
2. WHILE the Circuit_Breaker is in OPEN state, THE Guardrail_Engine SHALL return a Guardrail_Decision of DENY for all new Remediation_Action submissions regardless of Risk_Level; Remediation_Actions already in-flight at the time of transition SHALL be allowed to complete but their outcomes SHALL still be recorded
3. WHEN the Circuit_Breaker transitions to OPEN state, THE Circuit_Breaker SHALL dispatch an escalation notification containing: the failure count, the time window duration in seconds, and the list of up to the 10 most recent failed incident IDs within the time window
4. THE Circuit_Breaker SHALL support a configurable failure threshold (default 3, minimum 2, maximum 20) and a configurable sliding time window (default 300 seconds, minimum 60 seconds, maximum 1800 seconds); failures older than the time window SHALL NOT count toward the threshold
5. WHEN the configurable cooldown period (default 300 seconds, minimum 60 seconds, maximum 3600 seconds) elapses after the Circuit_Breaker enters OPEN state, THE Circuit_Breaker SHALL transition to HALF_OPEN state and allow exactly one Remediation_Action to proceed as a test probe, selecting the highest-priority pending action if multiple are queued
6. WHEN a test probe Remediation_Action succeeds in HALF_OPEN state, THE Circuit_Breaker SHALL transition to CLOSED state, reset the failure counter to zero, and resume normal operation
7. WHEN a test probe Remediation_Action fails in HALF_OPEN state, THE Circuit_Breaker SHALL transition back to OPEN state and restart the cooldown period from the time of the probe failure
8. IF any configurable parameter (failure threshold, time window, or cooldown period) is set to a value outside its valid range or is not a valid integer, THEN THE Circuit_Breaker SHALL fall back to the default value for that parameter and log a warning indicating the invalid configuration value
9. THE Circuit_Breaker SHALL support manual reset via an API endpoint that transitions the state from OPEN or HALF_OPEN to CLOSED and resets the failure counter to zero; IF the Circuit_Breaker is already in CLOSED state, THEN the endpoint SHALL return a success response with no state change
10. IF the Circuit_Breaker is manually reset to CLOSED state during the cooldown period, THE automatic HALF_OPEN transition SHALL still be triggered when the original cooldown elapses, at which point the Circuit_Breaker SHALL remain in CLOSED state if already CLOSED

### Requirement 7: Self-Protection

**User Story:** As an operations engineer, I want the system to detect and block actions targeting its own host or critical dependencies, so that the automation cannot disable itself.

#### Acceptance Criteria

1. THE Self_Protection_Guard SHALL maintain a list of protected hosts that includes the automation host and its critical dependencies (e.g., the database storing audit logs, the notification service), supporting a maximum of 50 entries in the protected hosts list
2. WHEN a Remediation_Action targets a host in the protected hosts list, THE Self_Protection_Guard SHALL return a Guardrail_Decision of DENY with reason "self_protection"; host matching SHALL be case-insensitive and SHALL match against both hostname and FQDN if configured for a protected entry
3. THE Self_Protection_Guard SHALL load the protected hosts list from a configuration file at `config/protected_hosts.yml` at service startup and reload the configuration within 30 seconds of file modification without requiring a service restart
4. IF the protected hosts configuration file is missing, THEN THE Self_Protection_Guard SHALL resolve the automation host identity at startup using the local system hostname and protect at minimum the local hostname
5. IF the protected hosts configuration file is present but contains malformed YAML or fails schema validation, THEN THE Self_Protection_Guard SHALL refuse to start the service and log an error indicating the validation failure reason
6. IF the protected hosts list is empty after loading (file exists but contains no entries), THEN THE Self_Protection_Guard SHALL refuse to start the service and log an error indicating that at least one protected host must be configured
7. WHEN a self-targeting action is blocked, THE Self_Protection_Guard SHALL log a critical-level warning within 2 seconds containing the incident_id, target host, and playbook path
8. WHEN a runtime reload of the protected hosts configuration results in a malformed or invalid file, THE Self_Protection_Guard SHALL retain the previously loaded valid configuration and log an error indicating the reload validation failure

### Requirement 8: Maintenance Window Awareness

**User Story:** As an operations engineer, I want the system to defer destructive actions during maintenance windows or active deployments, so that automated remediation does not interfere with planned changes.

#### Acceptance Criteria

1. WHEN a Remediation_Action is evaluated and the current timestamp falls within an active maintenance window, THE Maintenance_Window_Manager SHALL return a Guardrail_Decision of DEFER and record the deferred action with its incident ID, original Remediation_Plan, and deferral timestamp
2. THE Maintenance_Window_Manager SHALL load maintenance window schedules from the configuration file at `config/maintenance_windows.yml` at service startup and reload the file every 60 seconds to detect schedule changes without requiring a restart
3. IF the configuration file at `config/maintenance_windows.yml` is missing, unparseable, or fails schema validation at startup, THEN THE Maintenance_Window_Manager SHALL refuse to start and log an error indicating the specific validation failure; IF the file becomes missing or invalid during a periodic reload, THEN THE Maintenance_Window_Manager SHALL retain the last successfully loaded schedule and log a warning
4. THE Maintenance_Window_Manager SHALL support recurring schedules (daily, weekly, or monthly) and one-time windows, each defined with start and end timestamps, with a maximum of 100 maintenance windows defined in the configuration file
5. WHEN a maintenance window applies to a specific Service_Group, THE Maintenance_Window_Manager SHALL only defer actions targeting that Service_Group and allow actions targeting other Service_Groups to proceed
6. WHEN a maintenance window applies globally, THE Maintenance_Window_Manager SHALL defer all Remediation_Actions regardless of target Service_Group, overriding any service-group-specific maintenance window behavior
7. IF a deferred action remains pending after the maintenance window ends, THEN THE Guardrail_Engine SHALL re-evaluate the action through all guardrail checks within 60 seconds of the window ending before allowing execution
8. IF a deferred action has been pending for more than 60 minutes after its original deferral timestamp, THEN THE Guardrail_Engine SHALL discard the action as stale, mark it as expired in the Incident_Memory_Store, and not execute it
9. IF the target Service_Group of a Remediation_Action cannot be determined, THEN THE Maintenance_Window_Manager SHALL treat any active service-group-specific maintenance window as applicable and defer the action

### Requirement 9: Guardrail Engine Orchestration

**User Story:** As an operations engineer, I want all guardrail checks to be evaluated in a defined order with clear precedence, so that the safety decision is deterministic and auditable.

#### Acceptance Criteria

1. THE Guardrail_Engine SHALL evaluate checks in the following fixed order: Self_Protection_Guard, Maintenance_Window_Manager, Circuit_Breaker, Concurrency_Guard, Blast_Radius_Classifier, Health_Checker, Approval_Gate; each check SHALL return exactly one of three results: ALLOW, DENY, or DEFER
2. WHEN any guardrail check returns DENY, THE Guardrail_Engine SHALL stop evaluation immediately and return a final Guardrail_Decision of DENY without evaluating subsequent checks; WHEN all guardrail checks return ALLOW, THE Guardrail_Engine SHALL return a final Guardrail_Decision of ALLOW and permit the Remediation_Action to proceed to the execute stage
3. WHEN any guardrail check returns DEFER, THE Guardrail_Engine SHALL stop evaluation immediately, return a final Guardrail_Decision of DEFER, and hold the Remediation_Action in a pending state until the deferring check resolves (e.g., Approval_Gate awaiting human approval or Maintenance_Window_Manager awaiting window closure)
4. THE Guardrail_Engine SHALL log a structured JSON entry for every Remediation_Action evaluated containing: incident ID, Guardrail_Decision (ALLOW, DENY, or DEFER), the name of the check that produced the terminal decision, the reason string (maximum 512 characters), and a timestamp
5. WHEN the Guardrail_Engine returns DENY or DEFER, THE Guardrail_Engine SHALL include the denial or deferral reason in the audit record and dispatch a notification to the configured escalation channel within 30 seconds containing: incident ID, Guardrail_Decision, the check that produced it, and the reason
6. THE Guardrail_Engine SHALL complete all guardrail evaluations (excluding Approval_Gate wait time) within 15 seconds; IF evaluation exceeds 15 seconds, THEN THE Guardrail_Engine SHALL return DENY with reason "guardrail_timeout"
7. THE Guardrail_Engine SHALL be inserted into the Orchestrator pipeline between the match stage and the execute stage without modifying the existing normalize, enrich, or match stages
8. IF any guardrail check fails due to an internal error, exception, or unavailability, THEN THE Guardrail_Engine SHALL treat the failed check as returning DENY with reason indicating the check name and failure type, stop evaluation, and log the error
9. WHEN the Guardrail_Engine returns a final Guardrail_Decision of ALLOW, THE Guardrail_Engine SHALL log the ordered list of all checks evaluated and their individual results (all ALLOW) to provide a complete audit trail of the evaluation sequence
