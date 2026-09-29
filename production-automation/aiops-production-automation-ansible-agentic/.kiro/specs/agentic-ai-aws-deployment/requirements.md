# Requirements Document

## Introduction

This document defines the requirements for transforming the existing Self-Healing Infrastructure system into an Agentic AI solution deployed on AWS. The transformation replaces the rule-based playbook matching with an AI agent powered by Amazon Bedrock that can reason about alerts, correlate patterns, determine root causes, and select or compose remediation strategies. The system is deployed using AWS-native services (ECS Fargate, SQS, DynamoDB, CloudWatch, Systems Manager) while preserving the existing pipeline architecture, audit trail, and property-based testing approach.

## Glossary

- **AI_Reasoning_Agent**: The component powered by Amazon Bedrock foundation models that analyzes enriched alerts, correlates patterns, determines root causes, and selects or composes remediation strategies
- **Agent_Framework**: The Strands Agents SDK or Amazon Bedrock AgentCore runtime used to orchestrate the AI agent's tool use, memory retrieval, and decision-making loop
- **Bedrock_Model**: An Amazon Bedrock foundation model (Claude or equivalent) invoked by the AI_Reasoning_Agent for natural language reasoning about infrastructure incidents
- **Incident_Memory_Store**: An Amazon DynamoDB table storing historical incident records, remediation outcomes, and learned patterns used by the AI_Reasoning_Agent for context
- **Confidence_Score**: A numeric value between 0.0 and 1.0 produced by the AI_Reasoning_Agent indicating its certainty in a remediation decision
- **Escalation_Threshold**: A configurable confidence score value (default 0.5) below which the AI_Reasoning_Agent escalates to human operators instead of executing remediation
- **Remediation_Plan**: A structured output from the AI_Reasoning_Agent containing one or more remediation steps, target resources, and expected outcomes
- **Alert_Correlation_Window**: A configurable time window (default 5 minutes) within which the AI_Reasoning_Agent groups related alerts for joint analysis
- **SSM_Executor**: The component that executes remediation actions via AWS Systems Manager Run Command or Automation documents, replacing Ansible subprocess execution
- **Event_Bus**: An Amazon EventBridge event bus or SQS queue used to decouple alert ingestion from pipeline processing
- **CDK_Stack**: An AWS CDK application defining all infrastructure resources as code for repeatable deployment
- **Feedback_Loop**: The mechanism by which remediation outcomes (success/failure) are recorded and used by the AI_Reasoning_Agent to improve future decisions
- **Orchestrator**: The AWS-deployed service coordinating the pipeline stages: normalize, enrich, AI reasoning, execute remediation, and notify
- **Alert_Ingestion_Endpoint**: The AWS-hosted HTTP endpoint (API Gateway or ALB) that receives Prometheus Alertmanager webhook payloads

## Requirements

### Requirement 1: AI-Powered Remediation Reasoning

**User Story:** As an operations engineer, I want an AI agent to analyze alerts and determine the best remediation strategy, so that incidents are resolved more intelligently than static rule matching allows.

#### Acceptance Criteria

1. WHEN an enriched alert is received, THE AI_Reasoning_Agent SHALL invoke the Bedrock_Model with the alert context (alert name, severity, labels, annotations, enrichment data) and up to the 50 most recent matching historical incidents from the Incident_Memory_Store (matched by alert name) to produce a Remediation_Plan
2. WHEN the Bedrock_Model returns a response, THE AI_Reasoning_Agent SHALL produce a Remediation_Plan containing: selected remediation action, target resource identifier, confidence score between 0.0 and 1.0 (inclusive), and a reasoning explanation of the decision limited to a maximum of 2048 characters
3. WHEN the AI_Reasoning_Agent produces a Confidence_Score below the configurable Escalation_Threshold (default: 0.7), THE AI_Reasoning_Agent SHALL mark the Remediation_Plan as requiring human escalation and include the reasoning for low confidence in the escalation record
4. IF the Bedrock_Model invocation fails due to throttling, timeout, or service error (including immediate failures), THEN THE AI_Reasoning_Agent SHALL retry the invocation at least 1 time and up to 2 times with exponential backoff starting at 1 second before activating fallback; if all retries fail, SHALL fall back to the existing rule-based Playbook_Mapper for that alert
5. THE AI_Reasoning_Agent SHALL complete its reasoning and produce a Remediation_Plan within 30 seconds of receiving the enriched alert; IF reasoning exceeds 30 seconds, THEN THE AI_Reasoning_Agent SHALL abort and fall back to the rule-based Playbook_Mapper
6. WHEN the rule-based fallback is used, THE AI_Reasoning_Agent SHALL record the fallback event in the Incident_Memory_Store with the reason for fallback (throttling, timeout, service error, or reasoning timeout); IF the Incident_Memory_Store is unavailable at the time of fallback, THEN THE AI_Reasoning_Agent SHALL record the fallback event via application logs and publish a fallback metric to CloudWatch instead
7. IF the Incident_Memory_Store is unreachable or returns an error when retrieving historical data, THEN THE AI_Reasoning_Agent SHALL proceed with the Bedrock_Model invocation using only the current alert context (without historical data) and log a warning indicating the memory store was unavailable

### Requirement 2: Alert Pattern Correlation

**User Story:** As an operations engineer, I want the AI agent to correlate related alerts occurring within a time window, so that root causes affecting multiple services are identified and addressed holistically.

#### Acceptance Criteria

1. WHEN two or more alerts arrive within the Alert_Correlation_Window, THE AI_Reasoning_Agent SHALL group alerts sharing at least one common label value among instance, service_name, or location into a correlation group, with a maximum of 50 alerts per group, before invoking reasoning on the group
2. WHEN a correlation group contains two or more alerts, THE AI_Reasoning_Agent SHALL analyze the group collectively and produce a single Remediation_Plan addressing the likely root cause rather than individual symptoms
3. THE AI_Reasoning_Agent SHALL include in the Remediation_Plan a list of all correlated alert incident IDs that the plan addresses
4. IF only one alert exists in the correlation window with no other alerts sharing at least one common label value (instance, service_name, or location), THEN THE AI_Reasoning_Agent SHALL process the alert individually once the Alert_Correlation_Window has elapsed
5. THE Alert_Correlation_Window SHALL be configurable via environment variable (default 300 seconds) with a minimum of 30 seconds and maximum of 900 seconds
6. IF the Alert_Correlation_Window environment variable is set to a value below 30 seconds, above 900 seconds, or is not a valid integer, THEN THE AI_Reasoning_Agent SHALL fall back to the default value of 300 seconds and log a warning indicating the invalid configuration value

### Requirement 3: Historical Incident Learning

**User Story:** As an operations engineer, I want the AI agent to learn from past remediation outcomes, so that its decisions improve over time based on what worked and what failed.

#### Acceptance Criteria

1. WHEN a remediation action completes (success, failure, or timeout), THE Feedback_Loop SHALL record the following fields in the Incident_Memory_Store within 5 seconds of completion: incident ID, alert name, severity, affected service, affected resource, remediation action taken, outcome (success/failure/timeout), execution duration in seconds, and timestamp of completion
2. WHEN the AI_Reasoning_Agent reasons about a new alert, THE AI_Reasoning_Agent SHALL retrieve up to 10 historical incidents from the Incident_Memory_Store that match on at least one of the following attributes: exact alert name, same severity level, or same affected service, ordered by most recent first
3. THE AI_Reasoning_Agent SHALL include retrieved historical outcomes in the prompt context sent to the Bedrock_Model: the Remediation_Plan's reasoning explanation SHALL reference historical data when available, citing the number of past successes and failures for the selected action against similar alerts
4. THE Incident_Memory_Store SHALL retain historical records for a configurable duration (default 90 days, minimum 7 days, maximum 365 days) and automatically expire records older than the retention period using DynamoDB TTL on the expiry_timestamp attribute
5. IF the Incident_Memory_Store is unreachable, does not respond within 5 seconds, or returns an error during reasoning, THEN THE AI_Reasoning_Agent SHALL proceed with reasoning using only the current alert context and log a warning indicating the specific technical condition that prevented historical data retrieval; WHEN the Incident_Memory_Store successfully returns empty results because no matching historical data exists, THE AI_Reasoning_Agent SHALL proceed normally without logging a warning
6. WHEN the AI_Reasoning_Agent retrieves historical incidents and all past attempts of a specific remediation action for the same alert name resulted in failure, THE AI_Reasoning_Agent SHALL not select that action and SHALL indicate in the reasoning explanation that the action was excluded due to historical failures; this exclusion logic SHALL apply regardless of the configured retention period value

### Requirement 4: AWS Systems Manager Remediation Execution

**User Story:** As a platform engineer, I want remediation actions to be executed via AWS Systems Manager instead of Ansible subprocesses, so that the system uses AWS-native tooling with built-in audit trails and IAM-based access control.

#### Acceptance Criteria

1. WHEN a Remediation_Plan specifies an SSM action, THE SSM_Executor SHALL invoke the corresponding AWS Systems Manager Run Command or Automation document against the target EC2 instance or managed resource
2. THE SSM_Executor SHALL pass alert context (incident ID, alert name, severity, labels) as parameters to the SSM document, with the combined parameter payload not exceeding 32,000 characters; IF the combined parameter payload exceeds 32,000 characters, THEN THE SSM_Executor SHALL block execution and mark the remediation as failed with an error indicating the payload size exceeded the limit
3. WHEN an SSM command execution completes, THE SSM_Executor SHALL capture the command output (stdout truncated to 10,000 characters), exit status, and execution duration, and record these results in the Incident_Memory_Store associated with the incident ID; WHEN an SSM command execution times out, THE SSM_Executor SHALL capture any partial output generated before the timeout (truncated to 10,000 characters) and include it in the timeout record
4. IF an SSM command execution exceeds a configurable timeout (default 300 seconds, minimum 30 seconds, maximum 3600 seconds), THEN THE SSM_Executor SHALL cancel the command and mark the remediation as timed-out
5. IF the target instance is not reachable via SSM, THEN THE SSM_Executor SHALL check individual prerequisites separately (registration status, online status, IAM role attachment) and mark the remediation as failed with an error message indicating which specific prerequisite failed (e.g., "instance not registered with SSM", "instance offline", or "instance missing required IAM role")
6. IF the SSM API invocation fails due to throttling, access denied, or service error, THEN THE SSM_Executor SHALL retry up to 2 times with exponential backoff starting at 1 second, and if all retries fail, SHALL mark the remediation as failed with an error indicating the SSM API failure reason
7. THE SSM_Executor SHALL support up to 10 concurrent command executions using an asyncio semaphore
8. WHEN the AI_Reasoning_Agent produces a Remediation_Plan with multiple steps (maximum 20 steps), THE SSM_Executor SHALL execute steps sequentially and abort remaining steps if any step fails, marking the overall remediation as failed and recording which step failed and how many steps were skipped

### Requirement 5: Event-Driven Alert Ingestion

**User Story:** As a platform engineer, I want alerts to be ingested through an event-driven architecture, so that the system can handle burst traffic and decouple ingestion from processing.

#### Acceptance Criteria

1. THE Alert_Ingestion_Endpoint SHALL receive Prometheus Alertmanager webhook payloads via HTTPS POST and publish validated alert messages to the Event_Bus
2. WHEN a valid alert payload is received, THE Alert_Ingestion_Endpoint SHALL respond with HTTP 200 within 2 seconds and enqueue the payload for asynchronous processing
3. THE Event_Bus SHALL use Amazon SQS with a visibility timeout of 60 seconds and a dead-letter queue configured after 3 failed processing attempts
4. WHEN a message is received from the Event_Bus, THE Orchestrator SHALL process the alert through the full pipeline (normalize, enrich, AI reasoning, execute, notify) and delete the message upon successful completion
5. IF pipeline processing fails for a message, THEN THE Orchestrator SHALL allow the message to return to the queue for retry; after 3 failed attempts, the message SHALL be moved to the dead-letter queue
6. THE Event_Bus SHALL support a throughput of at least 100 messages per second without message loss
7. WHEN a payload is received that is not valid JSON, exceeds 1 MB, or is missing required fields, THE Alert_Ingestion_Endpoint SHALL respond with HTTP 400 and discard the payload without enqueuing

### Requirement 6: AWS Infrastructure Deployment

**User Story:** As a platform engineer, I want the entire system deployed on AWS using infrastructure as code, so that environments are reproducible, scalable, and follow AWS best practices.

#### Acceptance Criteria

1. THE CDK_Stack SHALL define all AWS resources required for the system: ECS Fargate service, SQS queues, DynamoDB tables, IAM roles, CloudWatch log groups, VPC networking, and API Gateway or ALB endpoint
2. THE CDK_Stack SHALL deploy the Orchestrator as an ECS Fargate task with 0.5 vCPU and 1024 MB memory, with auto-scaling based on SQS queue depth (scale up when queue depth exceeds 10 messages, scale down when queue is empty for 5 minutes), with a minimum task count of 1 and a maximum task count of 10
3. THE CDK_Stack SHALL create a DynamoDB table for the Incident_Memory_Store with on-demand capacity mode and TTL enabled on the expiry_timestamp attribute
4. THE CDK_Stack SHALL configure IAM roles following least-privilege principles: the ECS task role SHALL have permissions only for Bedrock model invocation, SQS message operations, DynamoDB read/write, SSM command execution, and CloudWatch log/metric publishing
5. THE CDK_Stack SHALL deploy to a configurable AWS region and account, accepting parameters for VPC CIDR (default: 10.0.0.0/16), desired task count (range: 1 to 10, default: 2), and Bedrock model ID (no default, required parameter)
6. THE CDK_Stack SHALL tag all resources with environment (dev/staging/prod), project name, and cost-center tags for resource management
7. IF a required deployment parameter is not provided or fails validation, THEN THE CDK_Stack SHALL fail synthesis with an error message indicating which parameter is missing or invalid
8. THE CDK_Stack SHALL create the VPC with 2 public subnets and 2 private subnets across 2 Availability Zones, placing the ECS Fargate tasks in private subnets with NAT Gateway access for outbound connectivity
9. IF the CDK deployment fails, THEN THE CDK_Stack SHALL automatically roll back all resources to their previous state via CloudFormation rollback behavior

### Requirement 7: Observability and Monitoring

**User Story:** As an operations engineer, I want comprehensive observability for the AI-powered system, so that I can monitor agent decisions, pipeline health, and system performance.

#### Acceptance Criteria

1. THE Orchestrator SHALL publish custom CloudWatch metrics for: alerts received, AI reasoning invocations, AI reasoning latency (p50, p95, p99), fallback-to-rules count, remediations executed, remediation success rate, and human escalations
2. THE Orchestrator SHALL emit structured JSON logs to CloudWatch Logs containing: incident ID, pipeline stage, duration, outcome, and AI reasoning summary for each processed alert
3. WHEN the AI_Reasoning_Agent produces a Remediation_Plan, THE Orchestrator SHALL log the full reasoning chain including: input context, retrieved historical incidents, confidence score, and selected action; IF some reasoning data is temporarily unavailable, THE Orchestrator SHALL log the available parts and continue processing rather than skipping the log entry entirely; WHEN the AI_Reasoning_Agent runs but does not produce a Remediation_Plan, THE Orchestrator SHALL NOT log reasoning chain data for that invocation
4. THE CDK_Stack SHALL create CloudWatch alarms for: dead-letter queue depth exceeding 5 messages, AI reasoning latency exceeding 15 seconds at p95, remediation failure rate exceeding 30 percent over 5 minutes, and ECS task unhealthy count exceeding 0
5. THE Orchestrator SHALL expose a health check endpoint at /health that returns HTTP 200 when the ECS task is healthy (SQS connectivity, DynamoDB connectivity, and Bedrock endpoint reachable) and HTTP 503 when any single dependency is unavailable; the response body SHALL contain a JSON object listing each dependency name and its current status (healthy or unhealthy with error detail)

### Requirement 8: Human Escalation and Override

**User Story:** As an operations engineer, I want the AI agent to escalate to humans when confidence is low and allow manual override of AI decisions, so that critical incidents are not mishandled by uncertain automation.

#### Acceptance Criteria

1. WHEN the AI_Reasoning_Agent produces a Confidence_Score below the Escalation_Threshold, THE Orchestrator SHALL dispatch a notification to the configured escalation channel (Slack or PagerDuty) within 30 seconds, containing: alert summary, AI reasoning explanation, suggested action, and confidence score
2. THE Escalation_Threshold SHALL be configurable via environment variable (default 0.5) with a valid range of 0.1 to 0.9
3. WHEN a P1 severity alert is received, THE AI_Reasoning_Agent SHALL require a minimum Confidence_Score of 0.8 before executing automated remediation; below 0.8, the alert SHALL be escalated regardless of the general Escalation_Threshold
4. WHEN an alert is escalated, THE Orchestrator SHALL record the escalation in the Incident_Memory_Store and pause automated remediation for that incident until a human responds or the configurable escalation timeout (default 30 minutes, valid range 5 to 120 minutes) expires
5. IF the escalation timeout expires without human response and the Confidence_Score is above 0.3, THEN THE Orchestrator SHALL execute the AI-suggested remediation and record the auto-execution decision in the Incident_Memory_Store; automated remediation SHALL NOT execute before the escalation timeout expires, even if the Confidence_Score is sufficient
6. IF the escalation timeout expires without human response and the Confidence_Score is 0.3 or below, THEN THE Orchestrator SHALL set the incident status to unresolved, cease automated remediation for that incident, and send a follow-up notification to the escalation channel indicating the incident requires manual intervention
7. WHEN a human responds to an escalation, THE Orchestrator SHALL accept one of three actions (approve AI-suggested remediation, reject and provide alternative action, or reject without alternative) and record the human decision with responder identity and timestamp in the Incident_Memory_Store
8. IF the Orchestrator fails to deliver an escalation notification to the configured channel within 30 seconds, THEN THE Orchestrator SHALL retry delivery up to 3 times at 10-second intervals, and if all retries fail, SHALL log the delivery failure and mark the incident as requiring manual review
9. IF an internal error prevents the Orchestrator from completing retry attempts for escalation notification delivery, THEN THE Orchestrator SHALL still attempt all remaining retries in the sequence before marking the incident for manual review

### Requirement 9: Backward Compatibility and Fallback

**User Story:** As a platform engineer, I want the system to maintain backward compatibility with the existing rule-based approach, so that the AI agent can be gradually adopted without disrupting existing operations.

#### Acceptance Criteria

1. THE Orchestrator SHALL support a configurable operating mode via environment variable with exactly three valid values: "ai_only" (AI reasoning only), "rules_only" (rule-based matching only), or "ai_with_fallback" (AI reasoning with rule-based fallback on failure); IF the environment variable is not set, THEN THE Orchestrator SHALL default to "rules_only" mode
2. WHEN operating in "ai_with_fallback" mode and the AI_Reasoning_Agent returns an error response, returns no playbook recommendation, or does not respond within 30 seconds, THE Orchestrator SHALL invoke the existing rule-based Playbook_Mapper and execute the matched playbook via SSM_Executor
3. THE system SHALL load and validate the existing YAML Mapping_Configuration for rule-based matching on service startup regardless of operating mode; IF the YAML Mapping_Configuration fails validation, THEN THE system SHALL log an error indicating the validation failure and refuse to start in "rules_only" or "ai_with_fallback" mode
4. WHEN operating in "rules_only" mode, THE Orchestrator SHALL bypass the AI_Reasoning_Agent entirely and use the Playbook_Mapper directly, producing identical playbook selection results as the rule-based system for the same alert input
5. THE operating mode SHALL be changeable at runtime via an API endpoint without requiring service restart; mode changes SHALL take effect for the next alert processed after the API call returns a success response
6. IF the runtime mode-change API receives a value other than "ai_only", "rules_only", or "ai_with_fallback", THEN THE Orchestrator SHALL reject the request with an error response indicating the invalid mode value and SHALL retain the current operating mode unchanged

### Requirement 10: Security and Access Control

**User Story:** As a security engineer, I want the system to follow AWS security best practices, so that sensitive operations are properly authenticated, authorized, and audited.

#### Acceptance Criteria

1. THE Alert_Ingestion_Endpoint SHALL require authentication via API key (x-api-key header) validated by API Gateway usage plans or IAM signature (SigV4); either authentication method SHALL be independently sufficient to authorize the request
2. THE CDK_Stack SHALL encrypt all data at rest: DynamoDB tables with AWS-managed KMS keys, SQS queues with SSE-SQS encryption, and CloudWatch logs with log group encryption
3. THE ECS task execution role SHALL be separate from the task role, and the task role SHALL have permissions limited to the following AWS service actions: Bedrock InvokeModel, SQS SendMessage/ReceiveMessage/DeleteMessage, DynamoDB GetItem/PutItem/UpdateItem/Query, SSM SendCommand/GetCommandInvocation, and CloudWatch PutMetricData/PutLogEvents
4. THE CDK_Stack SHALL deploy the ECS tasks in private subnets with no direct internet access; outbound traffic SHALL route through a NAT Gateway or VPC endpoints for AWS services
5. IF an unauthorized request is received at the Alert_Ingestion_Endpoint (missing or invalid API key), THEN THE Alert_Ingestion_Endpoint SHALL respond with HTTP 401 within 2 seconds and log the unauthorized access attempt to CloudWatch Logs including: timestamp, source IP address, request path, and failure reason (missing key or invalid key)
6. THE Orchestrator SHALL redact label values matching configurable patterns stored in SSM Parameter Store (default: patterns containing "password", "secret", "token", or "key" as case-insensitive substrings) before storing alert data in DynamoDB, replacing matched values with a fixed placeholder string
7. WHEN an authenticated request completes processing at the Alert_Ingestion_Endpoint, THE Alert_Ingestion_Endpoint SHALL log the request to CloudWatch Logs including: timestamp, source IP address, API key identifier (last 4 characters only), request path, and response status code

### Requirement 11: Audit Trail and Compliance

**User Story:** As a compliance officer, I want all AI decisions and remediation actions to be persistently audited, so that there is a complete trail for review, analysis, and regulatory compliance.

#### Acceptance Criteria

1. WHEN the Orchestrator completes processing an incident, THE Orchestrator SHALL record the incident in the Incident_Memory_Store within 5 seconds of action completion with: incident ID, alert name, severity, affected resource, timestamp received, AI reasoning summary (maximum 2048 characters), confidence score, selected action, execution result, and notification status; IF the initial write attempt fails within the 5-second window, THEN retries (up to 3 with exponential backoff) MAY extend beyond the 5-second target
2. WHEN the Orchestrator records an incident, THE Orchestrator SHALL publish a corresponding audit event to a dedicated CloudWatch Logs log group in structured JSON format with one JSON object per log entry within 10 seconds of the incident record creation
3. WHEN the AI_Reasoning_Agent makes a decision, THE audit record SHALL include the model ID used, input token count, output token count, and reasoning latency in milliseconds measured from request submission to response receipt
4. THE audit log group SHALL have a configurable retention period with a minimum of 90 days, a maximum of 3650 days, and a default of 365 days, set via the CDK_Stack
5. THE Incident_Memory_Store SHALL support querying historical incidents by alert name, severity, affected resource, time range (with minute-level granularity), and remediation outcome, returning results within 5 seconds for queries spanning up to 90 days of data
6. IF the Orchestrator fails to write an audit record to the Incident_Memory_Store or CloudWatch Logs, THEN THE Orchestrator SHALL retry the write up to 3 times with exponential backoff starting at 1 second, and if all retries fail, SHALL publish a failure notification to the configured alerting channel indicating the incident ID and failure reason

### Requirement 12: Cost Management

**User Story:** As a platform engineer, I want the system to be cost-efficient, so that AI reasoning and AWS service usage do not result in unexpected expenses.

#### Acceptance Criteria

1. THE AI_Reasoning_Agent SHALL implement token budget management: each reasoning invocation SHALL be limited to a configurable maximum input token count (default 4000 tokens, configurable range 1000 to 16000 tokens) and maximum output token count (default 1000 tokens, configurable range 200 to 4000 tokens)
2. WHEN the AI_Reasoning_Agent constructs the prompt for the Bedrock_Model, THE AI_Reasoning_Agent SHALL truncate historical context to fit within the token budget, prioritizing incidents by recency (most recent first) and then by similarity to the current alert
3. THE CDK_Stack SHALL configure ECS Fargate tasks with configurable CPU (default 0.5 vCPU) and memory (default 1 GB) to control compute costs
4. THE Orchestrator SHALL publish a custom CloudWatch metric for Bedrock invocation cost (estimated from token counts and model pricing) at the end of each hourly aggregation window to enable cost monitoring
5. THE CDK_Stack SHALL configure DynamoDB with on-demand capacity mode to avoid provisioned capacity costs while supporting variable traffic loads
6. IF the Bedrock_Model response reaches the configured maximum output token count, THEN THE AI_Reasoning_Agent SHALL truncate the response at the token limit and include a truncation flag in the result indicating the token limit condition was met, regardless of whether actual content was removed by the truncation
7. IF the Bedrock_Model response is incomplete due to content filtering or model errors (rather than reaching the token limit), THEN THE AI_Reasoning_Agent SHALL treat the response as a failure and invoke the rule-based fallback; the truncation flag SHALL still be set if the token limit was also reached during the same invocation
8. IF the truncation mechanism itself fails when processing a token-limited response, THEN THE AI_Reasoning_Agent SHALL return the partial response as-is without the truncation flag
