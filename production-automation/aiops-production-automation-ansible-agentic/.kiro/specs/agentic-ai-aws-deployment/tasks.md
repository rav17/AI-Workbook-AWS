# Implementation Plan: Agentic AI AWS Deployment

## Overview

This plan transforms the existing Self-Healing Infrastructure system into an Agentic AI solution deployed on AWS. Implementation proceeds incrementally: core data models and configuration first, then the AI reasoning agent, SSM executor, alert correlation, event-driven ingestion, escalation workflow, observability, and finally the CDK infrastructure stack. Each phase builds on the previous, with property-based tests validating correctness properties from the design document.

## Tasks

- [ ] 1. Set up project structure, data models, and configuration
  - [x] 1.1 Create project directory structure and core module layout
    - Create `src/agentic_ai/` package with submodules: `models/`, `agents/`, `executors/`, `ingestion/`, `observability/`, `escalation/`, `infra/`
    - Create `tests/property/`, `tests/unit/`, `tests/integration/`, `tests/cdk/` directories
    - Add `pyproject.toml` or `setup.py` with dependencies (boto3, hypothesis, strands-agents-sdk, pydantic, aws-cdk-lib)
    - _Requirements: 6.1_

  - [x] 1.2 Implement core data models and enums
    - Implement `OperatingMode`, `EscalationStatus`, `FallbackReason` enums
    - Implement `RemediationStep`, `RemediationPlan`, `CorrelationGroup`, `IncidentRecord`, `HumanResponse`, `PrerequisiteResult` dataclasses
    - Implement `AgentConfig` and `OrchestratorConfig` with validation for configurable ranges
    - _Requirements: 1.2, 1.3, 2.1, 3.1, 4.2, 8.2, 9.1, 12.1_

  - [ ] 1.3 Write property tests for data model validation
    - **Property 2: Remediation Plan Structure Validity** — Verify RemediationPlan always contains non-empty action, non-empty target, confidence in [0.0, 1.0], reasoning ≤ 2048 chars
    - **Property 7: Correlation Window Configuration Validation** — Verify effective window defaults to 300 for invalid/out-of-range values
    - **Validates: Requirements 1.2, 2.5, 2.6**

- [ ] 2. Implement Incident Memory Store (DynamoDB client)
  - [ ] 2.1 Implement IncidentMemoryStore class
    - Create `src/agentic_ai/models/incident_store.py`
    - Implement `record_incident()` with TTL calculation based on configurable retention (7-365 days)
    - Implement `query_history()` with matching on alert_name, severity, or service, ordered by recency, limited to 10 results, with 5-second timeout
    - Implement `record_outcome()` within 5 seconds of completion
    - Handle unreachable store gracefully (log warning, proceed without history)
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 11.1_

  - [ ] 2.2 Write property tests for historical query behavior
    - **Property 8: Historical Query Result Ordering and Limits** — Verify results ≤ 10 records, matching on at least one attribute, ordered by timestamp descending
    - **Property 10: TTL Expiry Calculation** — Verify expiry_timestamp = completion_timestamp + (retention_days × 86400)
    - **Validates: Requirements 3.2, 3.4**

  - [ ] 2.3 Write property tests for incident record completeness
    - **Property 23: Incident Record Completeness** — Verify all required fields present in stored records
    - **Validates: Requirements 11.1**

- [ ] 3. Implement AI Reasoning Agent
  - [ ] 3.1 Implement AIReasoningAgent core reasoning logic
    - Create `src/agentic_ai/agents/reasoning_agent.py`
    - Implement `reason()` method: retrieve history, build prompt, invoke Bedrock, parse response
    - Implement 30-second reasoning timeout with abort and fallback
    - Implement retry logic (up to 2 retries with exponential backoff starting at 1s)
    - Implement fallback to rule-based PlaybookMapper on failure
    - Record fallback events with reason in Incident Memory Store (or logs/CloudWatch if store unavailable)
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 1.7, 9.2_

  - [ ] 3.2 Implement prompt construction with token budget management
    - Create `_build_prompt()` method constructing prompt with alert context and historical data
    - Enforce configurable max input token count (default 4000, range 1000-16000)
    - Truncate historical context by recency first, then similarity
    - Include up to 50 historical incidents for context (Req 1.1) and cite success/failure counts
    - _Requirements: 1.1, 3.3, 12.1, 12.2_

  - [ ] 3.3 Implement response parsing and confidence-based decisions
    - Create `_parse_response()` method producing structured RemediationPlan
    - Implement confidence threshold logic (configurable, default 0.7 for general, 0.8 for P1)
    - Set `requires_escalation` flag when confidence < threshold
    - Handle truncation flag when response reaches max output tokens
    - Handle content filtering/model errors as failures triggering fallback
    - _Requirements: 1.2, 1.3, 8.3, 12.6, 12.7, 12.8_

  - [ ] 3.4 Implement historical failure exclusion logic
    - When all past attempts of a specific action for same alert name failed, exclude that action
    - Include exclusion reasoning in the explanation
    - _Requirements: 3.6_

  - [ ] 3.5 Write property tests for prompt construction
    - **Property 1: Prompt Construction Completeness** — Verify prompt contains all required context fields and at most 50 historical incidents
    - **Property 9: Historical Context in Prompt** — Verify correct citation of past success/failure counts
    - **Property 26: Token Budget Enforcement** — Verify input token count ≤ configured maximum
    - **Validates: Requirements 1.1, 3.3, 12.1, 12.2**

  - [ ] 3.6 Write property tests for confidence decisions and fallback
    - **Property 3: Confidence-Based Escalation Decision** — Verify escalation flag logic for general and P1 thresholds
    - **Property 4: Fallback Event Recording** — Verify fallback reason matches actual failure condition
    - **Property 11: Historical Failure Exclusion** — Verify excluded actions when all past attempts failed
    - **Property 27: Truncation Flag on Token Limit** — Verify truncation_flag set when max output tokens reached
    - **Validates: Requirements 1.3, 1.6, 3.6, 8.3, 12.6**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Alert Correlator
  - [ ] 5.1 Implement AlertCorrelator class
    - Create `src/agentic_ai/agents/correlator.py`
    - Implement `submit_alert()` with configurable window (30-900 seconds, default 300)
    - Group alerts sharing at least one common label (instance, service_name, location)
    - Enforce max 50 alerts per group
    - Process individual alerts when window elapses with no correlations
    - Validate correlation window env var (fallback to 300 for invalid values)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 5.2 Write property tests for alert correlation
    - **Property 5: Alert Correlation Grouping** — Verify grouping by shared labels and max 50 per group
    - **Property 6: Correlation Group ID Completeness** — Verify all incident IDs from group appear in RemediationPlan
    - **Validates: Requirements 2.1, 2.3**

- [ ] 6. Implement SSM Executor
  - [ ] 6.1 Implement SSMExecutor class
    - Create `src/agentic_ai/executors/ssm_executor.py`
    - Implement `execute()` with sequential step execution (max 20 steps), abort on failure
    - Implement parameter payload size validation (< 32,000 chars)
    - Implement prerequisite checks (registration, online, IAM role)
    - Implement configurable timeout (30-3600 seconds, default 300)
    - Implement output capture truncated to 10,000 chars
    - Implement asyncio semaphore for max 10 concurrent executions
    - Implement retry logic (up to 2 retries with exponential backoff) for SSM API failures
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ] 6.2 Write property tests for SSM execution logic
    - **Property 12: SSM Parameter Payload Size Validation** — Verify blocking when payload > 32,000 chars
    - **Property 13: SSM Output Truncation** — Verify output ≤ 10,000 chars preserving leading prefix
    - **Property 14: SSM Prerequisite Error Reporting** — Verify specific prerequisite failure identification
    - **Property 15: Sequential Step Execution with Abort on Failure** — Verify abort behavior and skip counting
    - **Validates: Requirements 4.2, 4.3, 4.5, 4.8**

- [ ] 7. Implement Event-Driven Alert Ingestion
  - [ ] 7.1 Implement AlertIngestionHandler
    - Create `src/agentic_ai/ingestion/handler.py`
    - Validate JSON structure, size (≤ 1 MB), and required fields (alerts array with alertname and severity)
    - Reject invalid payloads with HTTP 400
    - Reject unauthenticated requests with HTTP 401 (API key or SigV4)
    - Publish valid payloads to SQS and respond HTTP 200 within 2 seconds
    - Log authenticated requests (timestamp, source IP, last 4 chars of API key, path, status)
    - Log unauthorized attempts (timestamp, source IP, path, failure reason)
    - _Requirements: 5.1, 5.2, 5.7, 10.1, 10.5, 10.7_

  - [ ] 7.2 Write property tests for input validation
    - **Property 16: Invalid Payload Rejection** — Verify HTTP 400 for invalid JSON, oversized, or missing fields
    - **Validates: Requirements 5.7**

- [ ] 8. Implement Orchestrator with operating modes
  - [ ] 8.1 Implement AWSOrchestrator class
    - Create `src/agentic_ai/orchestrator.py`
    - Implement SQS polling loop with message processing and deletion on success
    - Implement pipeline stages: normalize → enrich → correlate → reason → execute → notify
    - Implement three operating modes (ai_only, rules_only, ai_with_fallback)
    - Default to "rules_only" when env var not set
    - Implement runtime mode-change API endpoint (validate mode values, reject invalid)
    - Load and validate YAML Mapping_Configuration on startup (refuse to start if invalid in rules/fallback modes)
    - Implement sensitive label redaction before DynamoDB storage
    - Implement health check endpoint at /health (check SQS, DynamoDB, Bedrock connectivity)
    - _Requirements: 5.3, 5.4, 5.5, 7.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 10.6_

  - [ ] 8.2 Write property tests for operating mode routing and redaction
    - **Property 20: Operating Mode Routing** — Verify AI agent not invoked in rules_only, PlaybookMapper not used in ai_only
    - **Property 21: Mode Change Validation** — Verify invalid mode values rejected, current mode unchanged
    - **Property 22: Sensitive Label Redaction** — Verify matching labels replaced with placeholder, non-matching preserved
    - **Validates: Requirements 9.1, 9.4, 9.6, 10.6**

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement Escalation Manager
  - [ ] 10.1 Implement EscalationManager class
    - Create `src/agentic_ai/escalation/manager.py`
    - Implement `escalate()`: dispatch notification to Slack/PagerDuty within 30 seconds
    - Implement notification retry (up to 3 times at 10-second intervals)
    - Record escalation in Incident Memory Store and pause automated remediation
    - Implement `check_timeout()`: execute if confidence > 0.3, mark unresolved if ≤ 0.3
    - Implement `handle_response()`: accept approve/reject/reject-with-alternative
    - Configurable escalation timeout (5-120 minutes, default 30)
    - _Requirements: 8.1, 8.2, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_

  - [ ] 10.2 Write property tests for escalation behavior
    - **Property 18: Post-Timeout Escalation Behavior** — Verify execution when confidence > 0.3, unresolved when ≤ 0.3
    - **Property 19: Human Response Recording** — Verify action, responder identity, and timestamp recorded
    - **Validates: Requirements 8.5, 8.6, 8.7**

- [ ] 11. Implement Observability (CloudWatch Metrics and Logging)
  - [ ] 11.1 Implement CloudWatchMetrics publisher
    - Create `src/agentic_ai/observability/metrics.py`
    - Publish custom metrics: alerts received, AI reasoning invocations, reasoning latency (p50/p95/p99), fallback count, remediations executed, success rate, escalations
    - Publish Bedrock cost estimate metric (hourly aggregation)
    - _Requirements: 7.1, 12.4_

  - [ ] 11.2 Implement structured JSON logging and audit trail
    - Create `src/agentic_ai/observability/audit.py`
    - Emit structured JSON logs with: incident_id, pipeline_stage, duration, outcome, AI reasoning summary
    - Log full reasoning chain (input context, historical incidents, confidence, selected action)
    - Include model_id, input/output token counts, reasoning latency in audit records
    - Implement audit write retry (up to 3 times with exponential backoff)
    - Publish failure notification if all retries fail
    - _Requirements: 7.2, 7.3, 11.1, 11.2, 11.3, 11.6_

  - [ ] 11.3 Write property tests for logging and audit
    - **Property 17: Structured Log Format** — Verify log entries are valid JSON with all required fields
    - **Property 24: Audit Event JSON Format** — Verify audit event is single valid JSON object with all incident fields
    - **Property 25: AI Decision Audit Fields** — Verify model_id, token counts, and latency present
    - **Validates: Requirements 7.2, 11.2, 11.3**

- [ ] 12. Implement CDK Infrastructure Stack
  - [ ] 12.1 Implement core CDK stack with VPC, ECS, and SQS
    - Create `src/agentic_ai/infra/stack.py` using AWS CDK (Python)
    - Define VPC with 2 public + 2 private subnets across 2 AZs
    - Define ECS Fargate service (0.5 vCPU, 1024 MB) in private subnets with NAT Gateway
    - Define auto-scaling based on SQS queue depth (scale up > 10 messages, scale down after 5 min empty, min 1, max 10)
    - Define SQS main queue (visibility timeout 60s) and DLQ (after 3 failures)
    - Define API Gateway with API key authentication
    - Accept required parameters: VPC CIDR (default 10.0.0.0/16), desired task count (1-10, default 2), Bedrock model ID (required)
    - Fail synthesis for missing/invalid parameters
    - _Requirements: 6.1, 6.2, 6.5, 6.7, 6.8, 5.3, 5.6, 10.1_

  - [ ] 12.2 Implement DynamoDB, IAM, encryption, and tagging in CDK
    - Define DynamoDB table with on-demand capacity, TTL on expiry_timestamp, and GSIs (AlertNameIndex, ServiceIndex, OutcomeIndex)
    - Define IAM roles: separate execution role and task role with least-privilege (Bedrock InvokeModel, SQS ops, DynamoDB ops, SSM ops, CloudWatch ops)
    - Configure encryption: DynamoDB with AWS-managed KMS, SQS with SSE-SQS, CloudWatch logs with encryption
    - Tag all resources with environment, project name, and cost-center
    - _Requirements: 6.3, 6.4, 6.6, 10.2, 10.3, 10.4, 12.5_

  - [ ] 12.3 Implement CloudWatch alarms and audit log group in CDK
    - Define CloudWatch alarms: DLQ depth > 5, AI reasoning latency p95 > 15s, remediation failure rate > 30% over 5 min, ECS unhealthy > 0
    - Define audit log group with configurable retention (90-3650 days, default 365)
    - _Requirements: 7.4, 11.4_

  - [ ] 12.4 Write CDK assertion tests
    - Verify resource creation (ECS, SQS, DynamoDB, IAM, VPC, CloudWatch)
    - Verify IAM least-privilege policies
    - Verify encryption configuration
    - Verify network topology (private subnets, NAT Gateway)
    - Verify auto-scaling, alarm thresholds, tag propagation, parameter validation
    - _Requirements: 6.1-6.9, 10.2-10.4_

- [ ] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Integration wiring and end-to-end pipeline
  - [ ] 14.1 Wire all components together in the Orchestrator
    - Connect AlertIngestionHandler → SQS → Orchestrator → Normalizer → Enricher → Correlator → AIReasoningAgent → SSMExecutor → NotificationDispatcher
    - Integrate EscalationManager into the pipeline flow
    - Integrate CloudWatchMetrics and audit logging at each pipeline stage
    - Ensure operating mode routing correctly bypasses/includes AI agent
    - _Requirements: 5.4, 9.1, 9.2, 9.4_

  - [ ] 14.2 Write integration tests for end-to-end pipeline
    - Test full pipeline from webhook receipt to remediation execution
    - Test SQS message lifecycle (publish, process, delete, DLQ routing)
    - Test DynamoDB read/write and TTL behavior
    - Test operating mode switching at runtime
    - _Requirements: 5.3, 5.4, 5.5, 9.5_

- [ ] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python throughout, matching the design document's code examples
- Hypothesis is used for property-based testing (already in the existing test suite)
- AWS CDK (Python) is used for infrastructure-as-code

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 4, "tasks": ["3.2", "3.3", "3.4"] },
    { "id": 5, "tasks": ["3.5", "3.6", "5.1", "6.1"] },
    { "id": 6, "tasks": ["5.2", "6.2", "7.1"] },
    { "id": 7, "tasks": ["7.2", "8.1"] },
    { "id": 8, "tasks": ["8.2", "10.1"] },
    { "id": 9, "tasks": ["10.2", "11.1", "11.2"] },
    { "id": 10, "tasks": ["11.3", "12.1"] },
    { "id": 11, "tasks": ["12.2", "12.3"] },
    { "id": 12, "tasks": ["12.4", "14.1"] },
    { "id": 13, "tasks": ["14.2"] }
  ]
}
```
