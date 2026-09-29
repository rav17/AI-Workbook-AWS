# Implementation Plan: Self-Healing Infrastructure

## Overview

This plan implements an automated self-healing infrastructure pipeline in Python using FastAPI, Ansible subprocess execution, and structured JSON logging. The system receives Prometheus Alertmanager webhooks and processes alerts through a multi-stage pipeline (normalization → enrichment → playbook matching → execution → notification) with full audit logging and Prometheus metrics. Implementation proceeds from data models and core components outward to integration and containerization.

## Tasks

- [x] 1. Set up project structure, dependencies, and data models
  - [x] 1.1 Create project directory structure and install dependencies
    - Create `src/` directory with `__init__.py` files for package structure
    - Create `tests/unit/`, `tests/property/`, `tests/integration/` directories
    - Create `pyproject.toml` or `requirements.txt` with dependencies: fastapi, uvicorn, pydantic, pyyaml, hypothesis, pytest, pytest-asyncio
    - Create `conftest.py` with shared fixtures
    - _Requirements: 10.1_

  - [x] 1.2 Implement data models and enums
    - Create `src/models.py` with all dataclasses: `AlertmanagerAlert`, `AlertmanagerPayload`, `NormalizedAlert`, `AssetInfo`, `EnrichedAlert`, `MappingRule`, `PlaybookMatch`, `ExecutionResult`, `AuditRecord`, `HealthResponse`
    - Implement enums: `Severity`, `RemediationStatus`, `AlertStatus`
    - Add Pydantic models for request/response validation on the webhook endpoint
    - _Requirements: 1.1, 2.1, 3.2, 5.2, 8.1, 9.2_

  - [x] 1.3 Write property tests for data models
    - **Property 25: Audit serialization as JSON lines**
    - **Validates: Requirements 8.2**

- [x] 2. Implement Normalizer component
  - [x] 2.1 Implement Normalizer class
    - Create `src/normalizer.py` with `Normalizer` class
    - Implement `normalize()` method that extracts individual alerts from grouped payload
    - Implement severity mapping: critical→P1, warning→P2, info→P3
    - Handle missing fields with defaults: empty string for alert name, P3 for unknown severity, "firing" for missing status, current time for missing starts_at
    - Generate UUID-based incident IDs for each alert
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 2.2 Write property tests for Normalizer
    - **Property 4: Normalization field extraction**
    - **Validates: Requirements 2.1**

  - [x] 2.3 Write property test for default value assignment
    - **Property 5: Default value assignment for missing or unknown fields**
    - **Validates: Requirements 2.3, 2.5**

  - [x] 2.4 Write property test for alert count preservation
    - **Property 6: Alert count preservation**
    - **Validates: Requirements 2.4**

- [x] 3. Implement Enricher component
  - [x] 3.1 Implement AssetInventory loader and Enricher class
    - Create `src/enricher.py` with `AssetInventory` and `Enricher` classes
    - Implement YAML-based asset inventory loading with hot-reload support
    - Implement `enrich()` method with label priority lookup: instance → hostname → job
    - Handle missing assets (mark unenriched), timeout (1s limit), and corrupted data
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 3.2 Write property tests for Enricher
    - **Property 7: Enrichment lookup key priority**
    - **Validates: Requirements 3.1, 3.5**

  - [x] 3.3 Write property test for asset metadata attachment
    - **Property 8: Asset metadata attachment completeness**
    - **Validates: Requirements 3.2**

  - [x] 3.4 Write property test for unresolved lookup
    - **Property 9: Unresolved lookup produces unenriched alert**
    - **Validates: Requirements 3.3**

- [x] 4. Implement Playbook Mapper component
  - [x] 4.1 Implement PlaybookMapper class
    - Create `src/playbook_mapper.py` with `PlaybookMapper` class
    - Implement YAML mapping configuration loading with max 500 rules
    - Implement `match()` method with best-fit rule selection (most matching attributes)
    - Implement tie-breaking: earliest rule in config wins
    - Implement `reload()` method with safe fallback on parse failure
    - Validate playbook path existence before returning match
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 4.2 Write property tests for Playbook Mapper
    - **Property 10: Playbook rule matching correctness**
    - **Validates: Requirements 4.2**

  - [x] 4.3 Write property test for tie-breaking
    - **Property 11: Tie-breaking selects earliest rule**
    - **Validates: Requirements 4.3**

  - [x] 4.4 Write property test for unmatched alerts
    - **Property 12: Unmatched alerts produce no playbook match**
    - **Validates: Requirements 4.4**

  - [x] 4.5 Write property test for malformed configuration
    - **Property 13: Malformed configuration preserves previous state**
    - **Validates: Requirements 4.6**

  - [x] 4.6 Write property test for non-existent playbook path
    - **Property 14: Non-existent playbook path treated as unmatched**
    - **Validates: Requirements 4.7**

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Remediation Executor component
  - [x] 6.1 Implement RemediationExecutor class
    - Create `src/executor.py` with `RemediationExecutor` class
    - Implement `execute()` method using `asyncio.create_subprocess_exec` for ansible-playbook invocation
    - Construct command with target host as inventory (`-i host,`) and extra vars (`-e`)
    - Implement timeout handling (default 300s) with SIGTERM → SIGKILL after 5s
    - Capture stdout/stderr truncated to 10,000 characters each
    - Implement concurrency limit (10 simultaneous executions) with asyncio.Semaphore
    - Validate playbook file existence before subprocess invocation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ] 6.2 Write property tests for Executor
    - **Property 15: Executor command construction**
    - **Validates: Requirements 5.1**

  - [ ] 6.3 Write property test for output capture
    - **Property 16: Output capture and truncation**
    - **Validates: Requirements 5.2**

  - [ ] 6.4 Write property test for non-zero return code
    - **Property 17: Non-zero return code marks failure**
    - **Validates: Requirements 5.4**

  - [ ] 6.5 Write property test for non-existent playbook
    - **Property 18: Non-existent playbook fails without subprocess**
    - **Validates: Requirements 5.7**

- [x] 7. Implement Notification Dispatcher component
  - [x] 7.1 Implement NotificationDispatcher class and channel adapters
    - Create `src/notification.py` with `NotificationDispatcher`, `SlackChannel`, `EmailChannel`, `PagerDutyChannel` classes
    - Implement `notify_incident()` with alert name, severity, affected host, timestamp
    - Implement `notify_remediation()` with action taken, outcome, duration
    - Implement `notify_manual_triage()` with manual intervention indicator
    - Implement retry logic: 3 attempts with exponential backoff (2s, 4s, 8s)
    - Handle individual channel failures independently
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 7.2 Write property tests for Notification Dispatcher
    - **Property 19: Incident notification content completeness**
    - **Validates: Requirements 6.1, 6.6**

  - [ ] 7.3 Write property test for remediation notification
    - **Property 20: Remediation notification content completeness**
    - **Validates: Requirements 6.2**

- [x] 8. Implement Audit Logger component
  - [x] 8.1 Implement AuditLogger class
    - Create `src/audit_logger.py` with `AuditLogger` class
    - Implement `log_incident()` method writing JSON lines to file
    - Implement output_summary truncation to 2,048 characters
    - Implement retry logic (3 attempts) on write failure with stderr fallback
    - Implement file rotation at 100 MB with 7 rotated files retention
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ] 8.2 Write property test for audit record completeness
    - **Property 24: Audit record completeness and truncation**
    - **Validates: Requirements 8.1, 8.4**

  - [ ] 8.3 Write property test for JSON serialization
    - **Property 25: Audit serialization as JSON lines**
    - **Validates: Requirements 8.2**

- [x] 9. Implement Metrics Collector component
  - [x] 9.1 Implement MetricsCollector class
    - Create `src/metrics.py` with `MetricsCollector` class
    - Implement monotonically increasing counters: alerts_received, remediation_success, remediation_failure, remediation_timeout, no_playbook_match, notification_failure
    - Implement `render_metrics()` in Prometheus exposition format with labels (alert_name, severity)
    - Counters start at zero and never decrease
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ] 9.2 Write property test for monotonic counters
    - **Property 29: Monotonically increasing counters**
    - **Validates: Requirements 11.1**

  - [ ] 9.3 Write property test for Prometheus format
    - **Property 30: Prometheus exposition format**
    - **Validates: Requirements 11.2**

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Orchestrator component
  - [x] 11.1 Implement Orchestrator class
    - Create `src/orchestrator.py` with `Orchestrator` class
    - Implement `process_alert_payload()` coordinating full pipeline: normalize → enrich → match → execute → notify
    - Assign UUID incident IDs per alert
    - Handle up to 50 concurrent pipelines with asyncio tasks
    - Implement stage failure handling: log failure, skip remaining stages, dispatch failure notification
    - Handle unmatched alerts: skip execution, dispatch manual triage notification
    - Handle failure notification failures: log and terminate pipeline
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ] 11.2 Write property test for pipeline UUID and sequential execution
    - **Property 21: Pipeline UUID uniqueness and sequential execution**
    - **Validates: Requirements 7.1**

  - [ ] 11.3 Write property test for stage failure handling
    - **Property 22: Stage failure triggers logging and notification**
    - **Validates: Requirements 7.3**

  - [ ] 11.4 Write property test for unmatched alert handling
    - **Property 23: Unmatched alert skips execution**
    - **Validates: Requirements 7.5**

- [x] 12. Implement Webhook Endpoint (FastAPI application)
  - [x] 12.1 Implement FastAPI application with webhook, health, and metrics endpoints
    - Create `src/app.py` with FastAPI application
    - Implement `POST /webhook` endpoint with Pydantic validation
    - Implement Content-Type enforcement (415 for non-JSON)
    - Implement payload size limit (1 MB)
    - Implement `GET /health` endpoint with dependency checks (Ansible binary, mapping config, asset inventory)
    - Implement `GET /metrics` endpoint exposing Prometheus metrics
    - Wire all components together via dependency injection
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 9.1, 9.2, 9.3, 9.4, 11.2_

  - [ ] 12.2 Write property tests for webhook endpoint
    - **Property 1: Valid payload acceptance**
    - **Validates: Requirements 1.2**

  - [ ] 12.3 Write property test for invalid payload rejection
    - **Property 2: Invalid payload rejection**
    - **Validates: Requirements 1.3**

  - [ ] 12.4 Write property test for Content-Type enforcement
    - **Property 3: Content-Type enforcement**
    - **Validates: Requirements 1.6**

  - [ ] 12.5 Write property test for health check
    - **Property 26: Health check dependency detection**
    - **Validates: Requirements 9.3**

- [x] 13. Implement configuration and container setup
  - [x] 13.1 Implement configuration loading and environment variable validation
    - Create `src/config.py` with configuration loading from environment variables
    - Validate required variables: notification credentials, asset inventory path, mapping config path
    - Exit with non-zero code and error message for missing required variables
    - Implement structured JSON logging to stdout/stderr
    - _Requirements: 10.2, 10.3, 10.5_

  - [ ] 13.2 Write property test for missing environment variable detection
    - **Property 27: Missing environment variable detection**
    - **Validates: Requirements 10.3**

  - [ ] 13.3 Write property test for structured JSON log output
    - **Property 28: Structured JSON log output**
    - **Validates: Requirements 10.5**

  - [x] 13.4 Create Dockerfile and container configuration
    - Create `Dockerfile` with Python base image, Ansible installation, non-root user
    - Install all runtime dependencies
    - Configure SIGTERM graceful shutdown (30s drain period)
    - Set default environment variables (port 8080)
    - Ensure container starts within 30 seconds
    - _Requirements: 10.1, 10.2, 10.4, 10.6_

- [x] 14. Integration wiring and sample configuration
  - [x] 14.1 Create sample configuration files
    - Create `config/asset_inventory.yml` with sample asset entries
    - Create `config/playbook_mapping.yml` with sample mapping rules
    - Create sample Ansible playbooks in `playbooks/` directory (e.g., restart_service.yml, clear_disk.yml)
    - Create `docker-compose.yml` for local development with Alertmanager
    - _Requirements: 3.1, 4.1, 4.5, 5.1_

  - [ ] 14.2 Create application entrypoint and SIGTERM handling
    - Create `src/main.py` as the application entrypoint
    - Wire all components together with proper initialization order
    - Implement SIGTERM signal handler: stop accepting new alerts, drain in-progress pipelines (30s), exit
    - Implement SIGHUP handler for configuration reload
    - _Requirements: 10.6, 4.1_

- [ ] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis
- Unit tests validate specific examples and edge cases
- The system uses Python with FastAPI, Ansible subprocess execution, and structured JSON logging
- All property tests should use the Hypothesis library with minimum 100 iterations per property

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1", "3.1", "4.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "3.2", "3.3", "3.4", "4.2", "4.3", "4.4", "4.5", "4.6"] },
    { "id": 4, "tasks": ["6.1", "7.1", "8.1", "9.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4", "6.5", "7.2", "7.3", "8.2", "8.3", "9.2", "9.3"] },
    { "id": 6, "tasks": ["11.1"] },
    { "id": 7, "tasks": ["11.2", "11.3", "11.4", "12.1"] },
    { "id": 8, "tasks": ["12.2", "12.3", "12.4", "12.5", "13.1"] },
    { "id": 9, "tasks": ["13.2", "13.3", "13.4", "14.1"] },
    { "id": 10, "tasks": ["14.2"] }
  ]
}
```
