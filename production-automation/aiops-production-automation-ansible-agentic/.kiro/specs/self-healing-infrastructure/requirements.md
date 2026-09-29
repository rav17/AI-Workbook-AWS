# Requirements Document

## Introduction

This document defines the requirements for a Self-Healing Infrastructure system built with Python, Prometheus Alertmanager, and Ansible. The system automatically detects infrastructure incidents via Alertmanager webhooks, normalizes and enriches alert data, selects and executes appropriate Ansible remediation playbooks, and notifies teams in real time. The goal is to reduce mean time to resolution (MTTR) by automating common remediation workflows while maintaining full audit trails.

## Glossary

- **Webhook_Endpoint**: A Python HTTP endpoint that receives POST requests containing alert payloads from Prometheus Alertmanager
- **Alert_Payload**: The JSON data structure sent by Prometheus Alertmanager containing alert labels, annotations, status, severity, and timing information
- **Normalizer**: The component responsible for parsing raw Alertmanager payloads into a standardized internal alert representation
- **Enricher**: The component that augments normalized alerts with environment-specific context such as hostname, IP address, location, and service ownership from an asset inventory
- **Playbook_Mapper**: The component that matches enriched alerts to predefined Ansible remediation playbooks based on configurable alert-to-playbook mapping rules
- **Remediation_Executor**: The component that invokes Ansible playbooks programmatically and captures execution results (success, failure, output)
- **Notification_Dispatcher**: The component that sends real-time notifications about incidents and remediation outcomes to configured channels (Slack, email, PagerDuty)
- **Orchestrator**: The Python service that coordinates the full incident lifecycle from alert reception through remediation to notification
- **Asset_Inventory**: A configuration source containing environment-specific metadata (hostnames, IPs, locations, service owners) used to enrich alerts
- **Mapping_Configuration**: A YAML or JSON configuration file that defines rules for matching alert attributes to specific Ansible playbooks
- **Audit_Log**: A persistent record of all incidents, remediation actions taken, and their outcomes

## Requirements

### Requirement 1: Webhook Alert Reception

**User Story:** As an operations engineer, I want the system to expose a webhook endpoint that receives Prometheus Alertmanager alerts, so that incidents are automatically ingested for processing.

#### Acceptance Criteria

1. THE Webhook_Endpoint SHALL expose an HTTP POST route at a configurable path (default: /webhook) to receive Alert_Payloads from Prometheus Alertmanager in JSON format (Content-Type: application/json)
2. WHEN a valid Alert_Payload is received containing at least one alert object with non-empty alert name, status, and severity fields conforming to the Prometheus Alertmanager webhook JSON schema, THE Webhook_Endpoint SHALL respond with HTTP 200 status within 2 seconds
3. WHEN a payload is received that is not valid JSON, exceeds 1 MB in size, or is missing required fields (alert name, status, or severity), THE Webhook_Endpoint SHALL respond with HTTP 400 status and an error message indicating which validation check failed
4. THE Webhook_Endpoint SHALL accept concurrent alert deliveries without dropping or duplicating alerts, supporting at least 10 simultaneous requests with no upper bound enforced by the endpoint itself
5. IF the Webhook_Endpoint encounters an internal processing error, THEN THE Webhook_Endpoint SHALL respond with HTTP 500 status and log the error details
6. IF a request is received with a Content-Type other than application/json, THEN THE Webhook_Endpoint SHALL respond with HTTP 415 status and an error message indicating the supported content type
7. WHEN a request has Content-Type application/json but contains an invalid JSON body or is missing required fields, THE Webhook_Endpoint SHALL respond with HTTP 400 status (not HTTP 415) and an error message indicating the validation failure

### Requirement 2: Alert Normalization

**User Story:** As an operations engineer, I want incoming Alertmanager payloads to be normalized into a consistent internal format, so that downstream components can process alerts uniformly regardless of source variations.

#### Acceptance Criteria

1. WHEN a valid Alert_Payload is received, THE Normalizer SHALL extract alert name, severity, status, labels, annotations, starts-at timestamp, and ends-at timestamp into a standardized internal alert object
2. THE Normalizer SHALL map Alertmanager severity labels (critical, warning, info) to internal severity levels (P1, P2, P3)
3. IF an Alert_Payload contains a severity label not matching any known value (critical, warning, info), THEN THE Normalizer SHALL assign a default severity of P3 and log a warning indicating the unrecognized severity value
4. WHEN an Alert_Payload contains multiple alerts in a single group, THE Normalizer SHALL produce one normalized alert object per individual alert
5. IF a required field (alert name, severity, status, or starts-at timestamp) is missing from the Alert_Payload, THEN THE Normalizer SHALL assign a default value of empty string for alert name, P3 for severity, firing for status, and the current system time for starts-at timestamp, and log a warning identifying the missing field

### Requirement 3: Alert Enrichment

**User Story:** As an operations engineer, I want normalized alerts to be enriched with environment-specific context, so that remediation actions have the information needed to target the correct infrastructure.

#### Acceptance Criteria

1. WHEN a normalized alert is produced, THE Enricher SHALL look up the target host in the Asset_Inventory by attempting alert labels in priority order: instance, then hostname, then job, using the first label present and non-empty as the lookup key
2. WHEN a matching asset is found, THE Enricher SHALL attach hostname, IP address, location, service name, and service owner to the alert object; IF any enrichment field is missing from the asset record, THEN THE Enricher SHALL attach the available fields and set missing fields to a null marker
3. IF no matching asset is found in the Asset_Inventory, THEN THE Enricher SHALL mark the alert as unenriched and log a warning with the unresolved lookup key
4. IF a matching asset is found but the lookup fails due to partial data corruption or validation errors, THEN THE Enricher SHALL mark the alert as unenriched, log a warning with the failure reason, and allow the alert to proceed through the pipeline
5. IF none of the lookup labels (instance, hostname, job) are present or non-empty in the normalized alert, THEN THE Enricher SHALL mark the alert as unenriched and log a warning indicating no lookup key could be derived
6. IF the Asset_Inventory is unreachable or returns an error during lookup, THEN THE Enricher SHALL mark the alert as unenriched, log an error with the failure reason, and allow the alert to proceed through the pipeline
7. THE Enricher SHALL complete enrichment within 1 second per alert; IF enrichment exceeds 1 second, THEN THE Enricher SHALL abort the lookup, mark the alert as unenriched, and log a timeout warning

### Requirement 4: Playbook Matching

**User Story:** As an operations engineer, I want alerts to be automatically matched to the correct Ansible remediation playbook, so that the appropriate fix is applied without manual intervention.

#### Acceptance Criteria

1. THE Playbook_Mapper SHALL load alert-to-playbook mapping rules from the Mapping_Configuration at startup and WHEN a reload signal is received (SIGHUP or API call to a reload endpoint)
2. WHEN an enriched alert is received, THE Playbook_Mapper SHALL evaluate mapping rules against alert attributes (alert name, severity, labels, service name) to select a matching playbook
3. WHEN multiple mapping rules match an alert with equal number of matching attributes, THE Playbook_Mapper SHALL select the rule defined earliest in the Mapping_Configuration file
4. IF no mapping rule matches an alert, THEN THE Playbook_Mapper SHALL mark the alert as unmatched and route it to the Notification_Dispatcher for manual triage; malformed rule syntax or attribute evaluation errors SHALL be treated as configuration errors (logged and skipped) rather than routing the alert to manual triage
5. THE Mapping_Configuration SHALL support YAML format with rules specifying match conditions and target playbook paths, supporting a maximum of 500 rules
6. IF the Mapping_Configuration file is malformed or fails YAML parsing, THEN THE Playbook_Mapper SHALL retain the previously loaded valid configuration, log an error indicating the parse failure, and continue operating with the existing rules
7. IF a matched playbook path does not exist on the filesystem, THEN THE Playbook_Mapper SHALL treat the alert as unmatched, log a warning indicating the missing playbook path, and route the alert to the Notification_Dispatcher for manual triage

### Requirement 5: Ansible Playbook Execution

**User Story:** As an operations engineer, I want matched playbooks to be executed automatically against the target infrastructure, so that common incidents are remediated without human intervention.

#### Acceptance Criteria

1. WHEN a playbook is matched to an alert, THE Remediation_Executor SHALL invoke the Ansible playbook via the `ansible-playbook` subprocess with the target host as inventory and alert context (incident ID, alert name, severity, labels, and annotations) passed as extra variables
2. WHEN a playbook execution completes or is terminated, THE Remediation_Executor SHALL capture stdout and stderr (each truncated to a maximum of 10,000 characters), return code, and execution duration in seconds
3. WHEN a playbook completes successfully (return code 0), THE Remediation_Executor SHALL mark the remediation as successful
4. IF a playbook execution fails (non-zero return code), THEN THE Remediation_Executor SHALL mark the remediation as failed and include the captured stderr output (truncated to 10,000 characters) in the execution result
5. IF a playbook execution exceeds a configurable timeout (default 300 seconds), THEN THE Remediation_Executor SHALL terminate the subprocess and mark the remediation as timed-out
6. THE Remediation_Executor SHALL support up to 10 concurrent playbook executions, each running in an isolated subprocess with independent output capture and no shared mutable state between executions
7. IF the specified playbook file does not exist or is not readable at execution time, THEN THE Remediation_Executor SHALL mark the remediation as failed with an error indicating the playbook path is inaccessible, without invoking a subprocess
8. IF the maximum concurrent execution limit (10) is reached when a new execution is requested, THEN THE Remediation_Executor SHALL queue the execution and process it when a slot becomes available within the configured timeout period

### Requirement 6: Real-Time Notification

**User Story:** As an operations team member, I want to receive real-time notifications about incidents and remediation outcomes, so that I am aware of infrastructure issues and their resolution status.

#### Acceptance Criteria

1. WHEN an incident is detected, THE Notification_Dispatcher SHALL send a notification containing alert name, severity, affected host, and timestamp to all configured channels within 5 seconds of detection
2. WHEN a remediation action completes, THE Notification_Dispatcher SHALL send a follow-up notification containing the action taken, outcome (success/failure/timeout), and execution duration to all configured channels within 5 seconds of completion
3. THE Notification_Dispatcher SHALL send notifications via Slack webhook, email (SMTP), and PagerDuty integration as notification channels
4. IF a notification delivery fails on one channel, THEN THE Notification_Dispatcher SHALL retry delivery to that channel up to 3 times with exponential backoff starting at 2 seconds, while continuing delivery to other configured channels independently
5. IF all retry attempts for a channel fail, THEN THE Notification_Dispatcher SHALL log the delivery failure including the channel name and error reason, and continue processing without blocking the remediation workflow
6. WHEN an alert is routed for manual triage due to no matching playbook, THE Notification_Dispatcher SHALL send a notification containing alert name, severity, affected host, and an indication that manual intervention is required

### Requirement 7: Workflow Orchestration

**User Story:** As an operations engineer, I want the full incident lifecycle to be orchestrated automatically from detection to resolution, so that incidents are handled end-to-end without manual coordination.

#### Acceptance Criteria

1. WHEN an Alert_Payload is received, THE Orchestrator SHALL assign a UUID-format incident identifier to each individual alert and execute the pipeline stages in sequence: normalize, enrich, match playbook, execute remediation (if a playbook is matched), and dispatch notifications
2. THE Orchestrator SHALL handle up to 50 concurrent alert pipelines independently, ensuring no pipeline instance reads or modifies another pipeline instance's alert data
3. IF any pipeline stage (normalize, enrich, match, or execute) fails with an unhandled exception or error result, THEN THE Orchestrator SHALL log the failure with the incident identifier and stage name, skip remaining stages for that alert, and dispatch a failure notification via the Notification_Dispatcher
4. IF the failure notification dispatch itself fails, THEN THE Orchestrator SHALL log the notification failure and terminate the pipeline for that alert without further retry
5. WHEN a matched playbook is not found for an alert, THE Orchestrator SHALL skip the remediation execution stage and dispatch a notification indicating the alert requires manual triage
6. WHEN a playbook execution fails (non-zero return code or timeout), THE Orchestrator SHALL dispatch a notification indicating the alert requires manual triage in addition to the failure notification

### Requirement 8: Audit Logging

**User Story:** As a compliance officer, I want all incidents and remediation actions to be logged persistently, so that there is a complete audit trail for review and analysis.

#### Acceptance Criteria

1. THE Audit_Log SHALL record each incident with: incident ID, alert name, severity, affected host, timestamp received, enrichment data, matched playbook (or "unmatched" if no playbook was found), execution result (or "skipped" if execution was not attempted), and notification status
2. THE Audit_Log SHALL persist entries to a structured log file in JSON format with one JSON object per line
3. THE Audit_Log SHALL record entries within 1 second of the triggering event
4. WHEN a remediation succeeds or fails, THE Audit_Log SHALL record the outcome with execution duration in seconds and output summary truncated to a maximum of 2048 characters
5. IF the Audit_Log fails to persist an entry due to file system error, THEN THE Audit_Log SHALL retry the write up to 3 times and, if all retries fail, log the failure to stderr and continue processing without blocking the pipeline; THE Audit_Log SHALL continue attempting to record subsequent remediation outcomes even while experiencing file system errors
6. WHEN the structured log file reaches 100 MB in size, THE Audit_Log SHALL rotate the file by closing the current file and creating a new one, retaining a minimum of 7 rotated files before the oldest is deleted

### Requirement 9: Health Check Endpoint

**User Story:** As a platform engineer, I want the system to expose a health check endpoint, so that container orchestrators and monitoring tools can verify the service is operational.

#### Acceptance Criteria

1. THE Webhook_Endpoint SHALL expose an HTTP GET route at /health that returns a JSON response within 2 seconds
2. WHEN all critical dependencies (Ansible binary, Mapping_Configuration file, Asset_Inventory file) are available, THE Webhook_Endpoint SHALL return HTTP 200 with a JSON body containing status set to "healthy", uptime in seconds since service start, version string, and a dependencies object listing each checked component and its status
3. IF a critical dependency (Ansible binary, Mapping_Configuration file, Asset_Inventory file) is unavailable, THEN THE Webhook_Endpoint SHALL return HTTP 503 with a JSON body containing status set to "degraded", uptime in seconds, version string, and a dependencies object identifying each unavailable component
4. THE health check response SHALL require no authentication to allow unauthenticated probes from container orchestrators

### Requirement 10: Containerized Deployment

**User Story:** As a platform engineer, I want the system to be deployable as a container, so that it can run in any container orchestration platform with consistent behavior.

#### Acceptance Criteria

1. THE Orchestrator SHALL be packaged as a Docker container image with all runtime dependencies (Python, Ansible, required libraries) and SHALL run its main process as a non-root user
2. THE container SHALL accept configuration via environment variables for: webhook port (default: 8080), notification channel credentials, asset inventory path, and mapping configuration path
3. IF a required environment variable (notification channel credentials, asset inventory path, or mapping configuration path) is not set at startup, THEN THE container SHALL exit with a non-zero exit code and log an error message indicating which variable is missing
4. THE container SHALL start the Webhook_Endpoint and begin accepting alerts within 30 seconds of launch
5. THE container SHALL log all output to stdout/stderr in structured JSON format for log aggregation
6. WHEN the container receives a SIGTERM signal, THE container SHALL stop accepting new alerts, allow in-progress remediation pipelines up to 30 seconds to complete, and then exit with code 0; IF in-progress pipelines do not complete within the 30-second timeout, THEN THE container SHALL exit with a non-zero exit code to indicate incomplete shutdown

### Requirement 11: Feedback and Metrics Tracking

**User Story:** As an operations manager, I want remediation outcomes to be tracked over time, so that the team can identify patterns, measure effectiveness, and improve playbooks.

#### Acceptance Criteria

1. THE Orchestrator SHALL maintain monotonically increasing counters for: total alerts received (incremented once per normalized alert), alerts remediated successfully, alerts remediated with failure, alerts remediated with timeout, alerts with no matching playbook, and alerts with notification failures
2. THE Orchestrator SHALL expose metrics at an HTTP endpoint with a configurable path (default /metrics) and port (default same as webhook port) in Prometheus exposition format, including metric labels for alert name and severity on each counter
3. WHEN a remediation completes with success, failure, or timeout, THE Orchestrator SHALL update the corresponding counter within 1 second under normal load; under heavy load, counter updates MAY be delayed but SHALL still be recorded accurately without data loss
4. IF the Orchestrator is restarted, THEN THE Orchestrator SHALL reset all counters to zero and begin accumulating from that point
