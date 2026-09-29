# Implementation Plan: Safe Execution Guardrails

## Overview

This plan implements a multi-layered safety engine between the playbook matching and execution stages of the AIOps self-healing pipeline. The engine evaluates remediation actions through seven ordered checks—Self-Protection, Maintenance Window, Circuit Breaker, Concurrency Guard, Blast Radius Classification, Health Check, and Approval Gate—producing a deterministic ALLOW, DENY, or DEFER decision with full audit trail. Implementation uses Python with async/await patterns, YAML-driven configuration, and Hypothesis for property-based testing.

## Tasks

- [x] 1. Set up guardrails module structure and core data models
  - [x] 1.1 Create directory structure and models module
    - Create `src/guardrails/` package with `__init__.py`
    - Create `src/guardrails/models.py` with all dataclasses: `RiskLevel` enum, `GuardrailDecisionType` enum, `CheckResultType` enum, `CheckResult`, `RemediationAction`, `GuardrailDecision`, `DeferredAction`
    - Implement `RiskLevel.elevate()` method that returns the next higher level capped at CRITICAL
    - _Requirements: 1.1, 9.1_

  - [x] 1.2 Create supporting protocol interfaces
    - Create `src/guardrails/interfaces.py` with `LockStore`, `ServiceRegistry`, and `LoadBalancerClient` Protocol classes
    - Define `GuardrailCheck` Protocol with `check(action: RemediationAction) -> CheckResult` and `name: str` property
    - _Requirements: 5.6, 3.1, 4.1_

  - [x] 1.3 Create configuration YAML files
    - Create `config/risk_classification.yml` with rules for service/playbook combinations, environment elevation, single-instance services, and database services
    - Create `config/protected_hosts.yml` with automation host and critical dependencies
    - Create `config/maintenance_windows.yml` with recurring and one-time window examples
    - _Requirements: 1.1, 1.2, 7.1, 7.3, 8.2, 8.4_

- [x] 2. Implement Self-Protection Guard
  - [x] 2.1 Implement SelfProtectionGuard class
    - Create `src/guardrails/self_protection.py`
    - Load protected hosts from `config/protected_hosts.yml` at initialization
    - Implement case-insensitive matching against hostname and FQDN
    - Implement startup validation: refuse to start on malformed YAML, empty list, or schema failure
    - Implement fallback to local hostname if config file is missing
    - Implement hot-reload with retention of valid config on invalid reload
    - Enforce MAX_PROTECTED_HOSTS = 50 limit
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [ ]* 2.2 Write property test for case-insensitive self-protection matching
    - **Property 16: Self-protection denies with case-insensitive matching**
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 2.3 Write property test for hot-reload config retention
    - **Property 7: Hot-reload retains valid config on invalid file (SelfProtectionGuard)**
    - **Validates: Requirements 7.8**

- [x] 3. Implement Maintenance Window Manager
  - [x] 3.1 Implement MaintenanceWindowManager class
    - Create `src/guardrails/maintenance_window.py`
    - Load maintenance window schedules from `config/maintenance_windows.yml`
    - Implement `is_in_window()` for recurring (daily, weekly, monthly) and one-time windows with timezone support
    - Implement scope matching: global windows defer all actions, service-group windows defer only matching actions
    - Implement conservative deferral for unknown service groups
    - Implement periodic reload every 60 seconds with retention of valid config on failure
    - Implement startup validation: refuse to start on missing/invalid config
    - Enforce MAX_WINDOWS = 100 and MAX_DEFER_AGE = 3600 seconds
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9_

  - [ ]* 3.2 Write property test for maintenance window scope matching
    - **Property 17: Maintenance window defers actions for matching scope**
    - **Validates: Requirements 8.1, 8.5, 8.6**

  - [ ]* 3.3 Write property test for recurring schedule detection
    - **Property 18: Recurring schedule detection**
    - **Validates: Requirements 8.4**

- [x] 4. Implement Circuit Breaker
  - [x] 4.1 Implement CircuitBreaker class
    - Create `src/guardrails/circuit_breaker.py`
    - Implement state machine: CLOSED → OPEN → HALF_OPEN → CLOSED
    - Implement sliding time window failure tracking
    - Implement OPEN state: deny all new actions
    - Implement HALF_OPEN state: allow exactly one probe action
    - Implement cooldown period with automatic HALF_OPEN transition
    - Implement `record_failure()`, `record_success()`, `manual_reset()`
    - Implement config validation with clamping to defaults for out-of-range values
    - Dispatch escalation notification on OPEN transition
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10_

  - [ ]* 4.2 Write property test for circuit breaker threshold breach
    - **Property 13: Circuit breaker opens on threshold breach**
    - **Validates: Requirements 6.1**

  - [ ]* 4.3 Write property test for open circuit breaker denying all
    - **Property 14: Open circuit breaker denies all actions**
    - **Validates: Requirements 6.2**

  - [ ]* 4.4 Write property test for config validation clamping
    - **Property 15: Circuit breaker config validation clamps to defaults**
    - **Validates: Requirements 6.4, 6.8**

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Concurrency Guard
  - [x] 6.1 Implement ConcurrencyGuard class
    - Create `src/guardrails/concurrency_guard.py`
    - Implement duplicate detection via lock store (DENY with "duplicate_remediation")
    - Implement rolling restart threshold calculation: max(floor(group_size × pct / 100), 1)
    - Implement DEFER when threshold reached, with re-evaluation on slot release
    - Implement configurable rolling restart percentage with bounds validation (5-50%, default 25%)
    - Implement lock auto-expiry after executor_timeout + 60 seconds
    - Implement `acquire()`, `release()` methods for slot management
    - Handle lock store unavailability with DENY and "lock_store_unavailable" reason
    - Implement max defer duration with expiry (default 600s, min 60s, max 3600s)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 6.2 Write property test for duplicate remediation denial
    - **Property 10: Duplicate remediation always denied**
    - **Validates: Requirements 5.1**

  - [ ]* 6.3 Write property test for rolling restart threshold
    - **Property 11: Rolling restart threshold enforces concurrency limit**
    - **Validates: Requirements 5.2, 5.4**

  - [ ]* 6.4 Write property test for lock auto-expiry
    - **Property 12: Lock auto-expiry after timeout plus buffer**
    - **Validates: Requirements 5.6**

- [x] 7. Implement Blast Radius Classifier
  - [x] 7.1 Implement BlastRadiusClassifier class
    - Create `src/guardrails/classifier.py`
    - Load risk classification rules from `config/risk_classification.yml`
    - Implement classification logic in priority order: single-instance override → database override → rule match → environment elevation → default to high
    - Implement production environment elevation (one level up, capped at CRITICAL)
    - Implement hot-reload with retention of valid config on failure
    - Default all classifications to HIGH when config is missing or unparseable
    - Complete classification within 2 seconds
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 7.2 Write property test for classification totality
    - **Property 1: Classification always produces exactly one valid RiskLevel**
    - **Validates: Requirements 1.1**

  - [ ]* 7.3 Write property test for single-instance critical classification
    - **Property 2: Single-instance services always classify as critical**
    - **Validates: Requirements 1.4**

  - [ ]* 7.4 Write property test for database restart/stop critical classification
    - **Property 3: Database restart/stop always classifies as critical**
    - **Validates: Requirements 1.5**

  - [ ]* 7.5 Write property test for production environment elevation
    - **Property 4: Production environment elevates risk by exactly one level**
    - **Validates: Requirements 1.7**

  - [ ]* 7.6 Write property test for unknown service/playbook defaults
    - **Property 5: Unknown service or playbook defaults to high**
    - **Validates: Requirements 1.6**

  - [ ]* 7.7 Write property test for missing config fallback
    - **Property 6: Missing config defaults all classifications to high**
    - **Validates: Requirements 1.3**

- [x] 8. Implement Health Checker
  - [x] 8.1 Implement HealthChecker class
    - Create `src/guardrails/health_checker.py`
    - Query health of all peer instances via HTTP GET to configurable health endpoints
    - Implement 5-second per-peer timeout and 10-second overall timeout
    - Implement decision logic: single instance → DENY for critical/high; all peers unhealthy → DENY + escalation; <2 healthy peers → DENY for critical, ALLOW with warning for others
    - Handle timeout: DENY for high/critical, ALLOW with warning for low/medium
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 8.2 Write property test for peer health verification
    - **Property 23: Health check peer verification for multi-instance groups**
    - **Validates: Requirements 3.1**

  - [ ]* 8.3 Write property test for risk-based health decision
    - **Property 24: Health check risk-based decision for low peer availability**
    - **Validates: Requirements 3.3**

- [x] 9. Implement Approval Gate
  - [x] 9.1 Implement ApprovalGate class
    - Create `src/guardrails/approval.py`
    - Skip approval for low/medium risk (return ALLOW immediately)
    - Send approval request for high/critical risk via notification dispatcher
    - Implement configurable timeout with clamping (default 300s, min 30s, max 1800s)
    - Implement delivery retry: up to 2 retries with exponential backoff starting at 2s
    - Return DENY on delivery failure or timeout expiry
    - Implement `resolve()` method for human approval/denial responses
    - Include responder identity in denial notifications
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 9.2 Write property test for approval gate skip on low/medium risk
    - **Property 8: Approval gate skipped for low/medium risk**
    - **Validates: Requirements 2.7**

  - [ ]* 9.3 Write property test for approval timeout clamping
    - **Property 9: Approval timeout validation clamps to defaults**
    - **Validates: Requirements 2.6**

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement Traffic Drainer
  - [x] 11.1 Implement TrafficDrainer class
    - Create `src/guardrails/traffic_drainer.py`
    - Implement `drain()`: remove instance from LB within 30s, wait configurable drain period (default 30s, min 5s, max 300s)
    - Implement `restore()`: health-check instance, re-register with LB within 60s
    - Implement health check polling at 5-second intervals with configurable timeout (default 60s, min 10s, max 300s)
    - Implement re-registration retry: up to 3 retries with exponential backoff starting at 2s
    - Handle LB removal failure: verify absence from active target list, DENY if still present
    - Always attempt re-registration after execution regardless of removal success
    - Re-register even if health check fails, with warning logged
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ]* 11.2 Write unit tests for traffic drainer drain/restore sequences
    - Test successful drain and restore flow
    - Test LB removal failure scenarios
    - Test health check timeout with forced re-registration
    - Test re-registration retry with exponential backoff
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

- [x] 12. Implement Guardrail Engine orchestrator
  - [x] 12.1 Implement GuardrailEngine class
    - Create `src/guardrails/engine.py`
    - Inject all seven guardrail checks, notification dispatcher, and audit logger
    - Implement `evaluate()` with fixed evaluation order and short-circuit semantics
    - Implement 15-second overall evaluation timeout (DENY with "guardrail_timeout")
    - Implement `_run_check()` with try/except error isolation (exception → DENY)
    - Implement `record_outcome()` for circuit breaker and concurrency tracking
    - Implement `release_action()` for concurrency slot release
    - Log structured JSON audit entry for every evaluation
    - Log ordered list of all checks when decision is ALLOW
    - Dispatch notification on DENY/DEFER within 30 seconds
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9_

  - [ ]* 12.2 Write property test for short-circuit on non-ALLOW
    - **Property 19: Evaluation short-circuits on non-ALLOW result**
    - **Validates: Requirements 9.2, 9.3**

  - [ ]* 12.3 Write property test for fixed evaluation order
    - **Property 20: Evaluation order is fixed and deterministic**
    - **Validates: Requirements 9.1, 9.9**

  - [ ]* 12.4 Write property test for audit log completeness
    - **Property 21: Every evaluation produces a structured audit log**
    - **Validates: Requirements 9.4**

  - [ ]* 12.5 Write property test for exception handling
    - **Property 22: Internal check errors result in DENY**
    - **Validates: Requirements 9.8**

- [x] 13. Integrate Guardrail Engine into Orchestrator pipeline
  - [x] 13.1 Wire GuardrailEngine into Orchestrator._run_pipeline()
    - Inject `GuardrailEngine` between Stage 3 (Match) and Stage 4 (Execute) in the Orchestrator
    - Call `engine.evaluate(action)` after playbook match
    - On ALLOW: proceed to traffic drain → execute → restore → record outcome → release slot
    - On DENY: dispatch denial notification, skip execution
    - On DEFER: dispatch deferral notification, queue for re-evaluation
    - Ensure existing normalize, enrich, and match stages remain unmodified
    - _Requirements: 9.7, 9.2, 9.3, 9.5_

  - [x] 13.2 Implement deferred action queue and re-evaluation
    - Create deferred action storage with max defer duration tracking
    - Implement re-evaluation on slot release (within 30s) and maintenance window end (within 60s)
    - Implement stale action expiry after 60 minutes
    - _Requirements: 5.3, 8.7, 8.8_

  - [ ]* 13.3 Write integration tests for full pipeline flow
    - Test match → guardrail → execute flow with ALLOW decision
    - Test DENY flow with notification dispatch
    - Test DEFER flow with re-evaluation
    - Test deferred action expiry
    - _Requirements: 9.1, 9.2, 9.3, 9.5, 9.7_

- [ ] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis (minimum 100 iterations per property)
- Unit tests validate specific examples and edge cases using pytest
- All guardrail components use async/await patterns for non-blocking I/O
- Configuration is YAML-driven with hot-reload support across all configurable components
- The fail-safe philosophy means any ambiguity or error defaults to DENY

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3", "4.2", "4.3", "4.4"] },
    { "id": 3, "tasks": ["6.1", "7.1", "8.1", "9.1"] },
    { "id": 4, "tasks": ["6.2", "6.3", "6.4", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7", "8.2", "8.3", "9.2", "9.3"] },
    { "id": 5, "tasks": ["11.1"] },
    { "id": 6, "tasks": ["11.2", "12.1"] },
    { "id": 7, "tasks": ["12.2", "12.3", "12.4", "12.5"] },
    { "id": 8, "tasks": ["13.1", "13.2"] },
    { "id": 9, "tasks": ["13.3"] }
  ]
}
```
