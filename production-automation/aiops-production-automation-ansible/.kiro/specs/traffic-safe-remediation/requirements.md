# Requirements Document

## Introduction

This feature adds traffic-aware safety to the AIOps self-healing infrastructure system. Currently, when the automation executes disruptive playbooks (service restarts, server reboots), it does so without regard for active traffic flowing through the target host. This causes dropped connections, user-facing errors, and potential capacity loss in load-balanced service pools.

The Traffic-Safe Remediation feature introduces a pre-execution traffic drain workflow, post-execution traffic restoration, service pool health awareness, self-target protection, and playbook risk classification. These mechanisms ensure that automated remediations do not cause more harm than the original alert condition.

## Glossary

- **Traffic_Drain_Controller**: The component responsible for orchestrating load balancer deregistration, connection draining, and re-registration of target hosts during disruptive remediations.
- **Pool_Health_Inspector**: The component that queries AWS Elastic Load Balancing APIs to determine the current healthy instance count in a target group and enforces minimum healthy thresholds.
- **Self_Target_Detector**: The component that compares remediation target hosts against the automation system's own identity (hostname, IP addresses) to detect self-affecting operations.
- **Playbook_Risk_Classifier**: The component that assigns risk levels to playbooks and determines whether traffic drain workflow is required before execution.
- **Target_Group**: An AWS ALB or NLB target group that routes traffic to a set of registered instances.
- **Drain_Timeout**: The maximum duration (in seconds) to wait for in-flight connections to complete after deregistering a host from the load balancer.
- **Minimum_Healthy_Threshold**: The minimum number or percentage of healthy instances that must remain in a target group before a disruptive remediation is permitted.
- **Risk_Level**: A classification assigned to each playbook indicating its potential for service disruption: safe, disruptive, or destructive.
- **Service_Pool**: The set of instances registered in a target group that collectively serve traffic for a given service.
- **Orchestrator**: The existing pipeline coordinator that processes alerts through normalize, enrich, match, guard, execute, and notify stages.
- **ConcurrencyGuard**: The existing concurrency safety layer that enforces host locking, deduplication, conflict matrix, priority queuing, circuit breakers, and blast radius limiting.

## Requirements

### Requirement 1: Playbook Risk Classification

**User Story:** As an operations engineer, I want playbooks to be classified by risk level, so that the system can automatically determine which playbooks require traffic drain before execution.

#### Acceptance Criteria

1. THE Playbook_Risk_Classifier SHALL support exactly three risk levels: safe, disruptive, and destructive.
2. WHEN a playbook has no explicit risk_level configured in the playbook mapping configuration, THE Playbook_Risk_Classifier SHALL default to the safe risk level.
3. THE Playbook_Risk_Classifier SHALL read risk level assignments from the playbook mapping configuration file (config/playbook_mapping.yml).
4. WHEN a playbook is classified as disruptive or destructive, THE Orchestrator SHALL invoke the Traffic_Drain_Controller before executing the playbook.
5. WHEN a playbook is classified as safe, THE Orchestrator SHALL execute the playbook without invoking the Traffic_Drain_Controller.
6. FOR ALL valid playbook mapping configurations, parsing the risk_level field and serializing it back SHALL produce a case-insensitive string-equal value (round-trip property).
7. IF a playbook's risk_level value in the configuration is not one of the three valid levels (safe, disruptive, destructive), THEN THE Playbook_Risk_Classifier SHALL reject the configuration entry, log a warning indicating the invalid value and playbook identifier, and treat that playbook as having no explicit risk_level configured.
8. THE Playbook_Risk_Classifier SHALL accept risk_level values in a case-insensitive manner and normalize them to lowercase before classification.

### Requirement 2: Pre-Execution Traffic Drain

**User Story:** As a site reliability engineer, I want the system to drain traffic from a host before executing disruptive playbooks, so that active user connections are not terminated mid-request.

#### Acceptance Criteria

1. WHEN a disruptive or destructive playbook targets a host registered in one or more Target_Groups, THE Traffic_Drain_Controller SHALL deregister the host from all associated Target_Groups before playbook execution begins.
2. WHEN the host is deregistered from a Target_Group, THE Traffic_Drain_Controller SHALL poll the target health status and wait until the host reports zero active connections or the Drain_Timeout expires, whichever occurs first.
3. WHEN the Drain_Timeout expires and connections remain, THE Traffic_Drain_Controller SHALL proceed with playbook execution regardless of remaining connections and record the drain outcome as "timeout_exceeded."
4. WHEN the target host is not registered in any Target_Group, THE Traffic_Drain_Controller SHALL skip the drain workflow and proceed directly to playbook execution.
5. IF the AWS API call to deregister the host fails from any Target_Group, THEN THE Traffic_Drain_Controller SHALL abort the remediation, re-register the host in any Target_Groups from which it was already successfully deregistered, and return a failure result with an error message indicating the failed Target_Group ARN and the API error reason.
6. THE Traffic_Drain_Controller SHALL record the drain start time, drain duration, drain outcome (completed, timeout_exceeded, skipped, or failed), and the list of affected Target_Group ARNs in structured log entries.
7. WHEN the Drain_Timeout is not explicitly configured, THE Traffic_Drain_Controller SHALL use a default value of 30 seconds.
8. THE Traffic_Drain_Controller SHALL support configuring the Drain_Timeout via the traffic safety configuration file (config/traffic_safety.yml) with a valid range of 1 to 300 seconds inclusive.
9. IF the configured Drain_Timeout value is outside the valid range of 1 to 300 seconds, THEN THE Traffic_Drain_Controller SHALL reject the configuration and fall back to the default value of 30 seconds.
10. WHEN the host is registered in multiple Target_Groups, THE Traffic_Drain_Controller SHALL deregister the host from all Target_Groups and wait for drain completion on each before proceeding to playbook execution.

### Requirement 3: Post-Execution Traffic Restoration

**User Story:** As a site reliability engineer, I want the system to restore traffic to a host after a successful remediation, so that the host resumes serving requests once healthy.

#### Acceptance Criteria

1. WHEN a playbook execution completes successfully and the host was previously deregistered, THE Traffic_Drain_Controller SHALL re-register the host in the Target_Group.
2. WHEN the host is re-registered, THE Traffic_Drain_Controller SHALL poll the load balancer health check status every 5 seconds until the host is reported as healthy or the health check timeout is reached.
3. WHEN the health check does not pass within the configured health check timeout (default 60 seconds, configurable from 10 to 300 seconds via config/traffic_safety.yml), THE Traffic_Drain_Controller SHALL log a warning and mark the restoration as incomplete.
4. IF the AWS API call to re-register the host fails after up to 3 retry attempts with exponential backoff, THEN THE Traffic_Drain_Controller SHALL log an error, dispatch a notification to the operations team, and mark the remediation as requiring manual intervention.
5. WHEN a playbook execution fails and the host was previously deregistered, THE Traffic_Drain_Controller SHALL still attempt to re-register the host in the Target_Group.
6. IF re-registration fails after a failed playbook execution, THEN THE Traffic_Drain_Controller SHALL log an error, dispatch a notification to the operations team, and mark the host as requiring manual re-registration.
7. THE Traffic_Drain_Controller SHALL record the registration outcome, health check wait duration, number of retry attempts, and final health status in structured log entries.

### Requirement 4: Service Pool Health Awareness

**User Story:** As a site reliability engineer, I want the system to check service pool health before allowing a disruptive remediation, so that the system does not reduce capacity below safe operating levels.

#### Acceptance Criteria

1. WHEN a disruptive or destructive playbook targets a host in a Target_Group, THE Pool_Health_Inspector SHALL query the current number of healthy instances in that Target_Group before permitting the remediation.
2. THE Pool_Health_Inspector SHALL enforce a configurable Minimum_Healthy_Threshold expressed as either a percentage (1% to 100%, rounded up to the nearest whole instance) or an absolute count (minimum value of 1).
3. WHEN removing the target host would cause the healthy instance count to fall below the Minimum_Healthy_Threshold, THE Pool_Health_Inspector SHALL reject the remediation request. IF the target host is already in an unhealthy state, THEN THE Pool_Health_Inspector SHALL treat the removal as not reducing the healthy count and permit the remediation provided the current healthy count already meets the Minimum_Healthy_Threshold.
4. WHEN the remediation is rejected due to pool health constraints, THE Pool_Health_Inspector SHALL return a descriptive rejection reason including the current healthy count, the threshold value, and the target group identifier.
5. WHEN the target host is not registered in any Target_Group, THE Pool_Health_Inspector SHALL permit the remediation without pool health checks.
6. IF the AWS API call to describe target health fails or does not respond within 10 seconds, THEN THE Pool_Health_Inspector SHALL reject the remediation and log an error rather than proceeding without health data.
7. THE Pool_Health_Inspector SHALL read the Minimum_Healthy_Threshold from the traffic safety configuration file (config/traffic_safety.yml).
8. WHEN the Minimum_Healthy_Threshold is not configured, THE Pool_Health_Inspector SHALL default to requiring at least 50% of instances to remain healthy.
9. WHEN the target host is registered in multiple Target_Groups, THE Pool_Health_Inspector SHALL evaluate the Minimum_Healthy_Threshold against each Target_Group independently and SHALL reject the remediation if any single Target_Group would fall below its threshold.
10. IF the configured Minimum_Healthy_Threshold value is invalid (non-numeric, negative, zero, or a percentage exceeding 100%), THEN THE Pool_Health_Inspector SHALL log a warning and fall back to the default threshold of 50%.

### Requirement 5: Self-Target Protection

**User Story:** As an operations engineer, I want the system to detect when a remediation targets its own host, so that the automation does not inadvertently disrupt itself.

#### Acceptance Criteria

1. WHEN a remediation request targets a host, THE Self_Target_Detector SHALL compare the target host against the automation system's own hostname and IP addresses.
2. WHEN the target host matches the automation system's own identity, THE Self_Target_Detector SHALL block the remediation and return a rejection result that includes the rejection reason, the incident_id, and the target host value that triggered the match.
3. THE Self_Target_Detector SHALL resolve the automation system's identity at startup by reading the local hostname, the fully qualified domain name, and all bound IP addresses including loopback addresses (127.0.0.1, ::1) and IPv4/IPv6 addresses on all network interfaces.
4. WHEN the target host is specified as an IP address, THE Self_Target_Detector SHALL compare it against all IP addresses bound to the automation system's network interfaces, including loopback addresses and both IPv4 and IPv6 addresses.
5. WHEN the target host is specified as a hostname, THE Self_Target_Detector SHALL compare it against both the automation system's short hostname and fully qualified domain name using case-insensitive matching, and SHALL also treat the value "localhost" as a self-target match.
6. WHEN a self-targeting attempt is detected, THE Self_Target_Detector SHALL log a warning-level message including the incident_id and target host value.
7. IF the Self_Target_Detector fails to resolve the automation system's own identity at startup, THEN THE Self_Target_Detector SHALL log an error and block all remediation requests until identity resolution succeeds, to prevent accidental self-targeting.
8. FOR ALL combinations of hostname formats (FQDN, short name, IP address), the Self_Target_Detector SHALL produce a deterministic allow or block decision for the same underlying host identity.

### Requirement 6: Traffic Safety Configuration

**User Story:** As an operations engineer, I want traffic safety parameters to be configurable via a YAML file, so that I can tune drain timeouts, health thresholds, and target group mappings without code changes.

#### Acceptance Criteria

1. THE Orchestrator SHALL load traffic safety configuration from config/traffic_safety.yml at startup.
2. IF the configuration file is missing or contains invalid YAML syntax, THEN THE Orchestrator SHALL log a warning and use default values for all traffic safety parameters (Drain_Timeout: 30 seconds, health check timeout: 60 seconds, Minimum_Healthy_Threshold: 50%).
3. THE configuration file SHALL support specifying a mapping from service names to AWS target group ARNs, with a maximum of 200 service-to-target-group entries.
4. THE configuration file SHALL support specifying the default Drain_Timeout as an integer value between 5 and 300 seconds inclusive.
5. THE configuration file SHALL support specifying the health check timeout as an integer value between 5 and 600 seconds inclusive.
6. THE configuration file SHALL support specifying the Minimum_Healthy_Threshold as either a percentage between 1 and 100 inclusive or an absolute count of at least 1.
7. FOR ALL valid traffic safety configurations, parsing the YAML file into an in-memory representation and serializing it back SHALL produce a semantically equivalent configuration where all parameter values are preserved (round-trip property).
8. IF the configuration file contains a syntactically valid YAML value that is outside the permitted range for its parameter (e.g., Drain_Timeout less than 5 or greater than 300), THEN THE Orchestrator SHALL log a warning identifying the invalid parameter and use the default value for that specific parameter.
9. IF the configuration file contains a target group ARN that does not match the AWS ARN format (arn:aws:elasticloadbalancing:*), THEN THE Orchestrator SHALL log a warning and exclude that entry from the service-to-target-group mapping.

### Requirement 7: Pipeline Integration

**User Story:** As a developer, I want the traffic safety mechanisms to integrate cleanly into the existing orchestrator pipeline, so that the feature works alongside the existing concurrency guard without disruption.

#### Acceptance Criteria

1. THE Traffic_Drain_Controller SHALL execute after the ConcurrencyGuard approves the remediation and before the RemediationExecutor runs the playbook.
2. WHEN the Traffic_Drain_Controller rejects a remediation (due to pool health or self-targeting), THE Orchestrator SHALL treat the rejection as a pipeline failure, include the rejection reason and target host in the notification payload, and dispatch the notification.
3. THE Traffic_Drain_Controller SHALL pass through all existing extra_vars to the RemediationExecutor without modification.
4. WHEN the Traffic_Drain_Controller completes the drain workflow, THE Orchestrator SHALL record the incident_id, target_host, drain duration in seconds, and outcome status (success, timeout, or skipped) in the audit log.
5. THE Traffic_Drain_Controller SHALL expose Prometheus metrics for drain operations (drain_started_total, drain_completed_total, drain_timeout_total, pool_health_rejections_total, self_target_blocks_total).
6. WHEN the traffic safety configuration is not present, THE Orchestrator SHALL bypass the Traffic_Drain_Controller entirely and execute playbooks via the RemediationExecutor using the pre-existing pipeline path without traffic drain.
7. IF the Traffic_Drain_Controller raises an unexpected exception during execution, THEN THE Orchestrator SHALL log the error, abort the remediation for that request, and dispatch a notification indicating an internal traffic safety failure.
