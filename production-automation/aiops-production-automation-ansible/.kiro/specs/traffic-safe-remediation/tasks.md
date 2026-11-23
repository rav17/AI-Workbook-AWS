# Implementation Plan: Traffic-Safe Remediation

## Overview

This plan implements the Traffic-Safe Remediation feature by building each component incrementally: data models and configuration first, then individual safety mechanisms (risk classifier, self-target detector, pool health inspector), followed by the drain/restore controller, and finally pipeline integration with metrics. Each step builds on the previous, ensuring no orphaned code.

## Tasks

- [ ] 1. Define data models, enums, and configuration loader
  - [ ] 1.1 Create `src/traffic_safety_models.py` with enums and dataclasses
    - Define `RiskLevel` enum (SAFE, DISRUPTIVE, DESTRUCTIVE)
    - Define `DrainOutcome` enum (COMPLETED, TIMEOUT_EXCEEDED, SKIPPED, FAILED)
    - Define `RestorationOutcome` enum (HEALTHY, INCOMPLETE, FAILED, SKIPPED)
    - Define `TrafficRejectionReason` enum (SELF_TARGET_BLOCKED, POOL_HEALTH_VIOLATION, DRAIN_FAILED, IDENTITY_UNRESOLVED)
    - Define `SystemIdentity` dataclass (hostname, fqdn, ip_addresses)
    - Define `PoolHealthStatus` dataclass (target_group_arn, total_targets, healthy_targets, unhealthy_targets, target_is_healthy)
    - Define `DrainRecord` dataclass (incident_id, target_host, drain_start_time, drain_duration_seconds, drain_outcome, affected_target_group_arns)
    - Define `TrafficDrainResult` dataclass (execution_result, drain_outcome, drain_duration_seconds, affected_target_groups, restoration_outcome)
    - _Requirements: 1.1, 2.6, 3.7, 4.1_

  - [ ] 1.2 Create `src/traffic_safety_config.py` with `TrafficSafetyConfig`
    - Implement `TrafficSafetyConfig` dataclass with defaults (drain_timeout=30, health_check_timeout=60, health_check_poll_interval=5, min_healthy_threshold=0.5, re_register_max_retries=3, service_target_groups={})
    - Implement `from_yaml()` class method to load from `config/traffic_safety.yml`
    - Implement `validate()` method returning warnings for out-of-range parameters
    - Implement range validation: drain_timeout [1,300], health_check_timeout [10,300], min_healthy_threshold (percentage 1-100 or absolute ≥1)
    - Implement fallback to defaults for invalid parameters with warning logging
    - Implement ARN format validation (must match `arn:aws:elasticloadbalancing:*`), exclude invalid entries
    - Implement `to_yaml()` serialization method
    - Handle missing file (log warning, use all defaults) and invalid YAML syntax
    - Enforce maximum 200 service-to-target-group entries
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 2.7, 2.8, 2.9_

  - [ ]* 1.3 Write property tests for configuration round-trip and validation
    - **Property 11: Configuration Round-Trip** — Generate valid TrafficSafetyConfig instances, serialize to YAML and parse back, verify semantic equivalence
    - **Property 12: Configuration Parameter Range Validation** — Generate integers for drain_timeout, health_check_timeout, threshold; verify acceptance/rejection per range
    - **Property 13: Target Group ARN Format Validation** — Generate strings (valid ARNs and random), verify only valid ARNs are included
    - Create `tests/property/test_traffic_config_properties.py`
    - **Validates: Requirements 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 2.8, 2.9**

- [ ] 2. Implement PlaybookRiskClassifier
  - [ ] 2.1 Create `src/playbook_risk_classifier.py`
    - Implement `PlaybookRiskClassifier` class with `__init__` accepting mapping config path
    - Implement `from_yaml()` class method to load risk levels from `config/playbook_mapping.yml` rules
    - Implement `classify(playbook_path)` returning `RiskLevel` (defaults to SAFE if not configured)
    - Implement `requires_drain(playbook_path)` returning True for DISRUPTIVE or DESTRUCTIVE
    - Accept risk_level values case-insensitively, normalize to lowercase
    - Reject invalid risk_level values (log warning, treat as unconfigured → SAFE default)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 2.2 Write property tests for risk classification
    - **Property 1: Risk Level Classification Domain and Default** — Generate random playbook paths, verify classify() always returns a valid RiskLevel; verify unconfigured paths return SAFE
    - **Property 3: Risk Level Round-Trip** — Generate valid risk strings with random casing, verify parse/serialize produces case-insensitive equal value
    - Create `tests/property/test_risk_classifier_properties.py`
    - **Validates: Requirements 1.1, 1.2, 1.6, 1.7, 1.8**

  - [ ]* 2.3 Write unit tests for PlaybookRiskClassifier
    - Test classification of configured playbooks (safe, disruptive, destructive)
    - Test default to SAFE for unconfigured playbooks
    - Test case-insensitive parsing ("DISRUPTIVE", "Disruptive", "disruptive")
    - Test invalid risk_level values are rejected with warning
    - Test `requires_drain()` returns correct boolean
    - Create `tests/unit/test_risk_classifier.py`
    - _Requirements: 1.1, 1.2, 1.7, 1.8_

- [ ] 3. Implement SelfTargetDetector
  - [ ] 3.1 Create `src/self_target_detector.py`
    - Implement `SelfTargetDetector` class
    - Implement `resolve_identity()` to read local hostname, FQDN, and all bound IP addresses (IPv4, IPv6, loopback 127.0.0.1, ::1)
    - Implement `is_self_target(target_host)` comparing against cached identity
    - Handle hostname comparison (case-insensitive, short name and FQDN)
    - Handle IP address comparison (all bound interfaces including loopback)
    - Treat "localhost" as a self-target match
    - Implement `is_resolved` property and `identity` property
    - If identity resolution fails at startup, log error and block all remediations
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ]* 3.2 Write property tests for self-target detection
    - **Property 8: Self-Target Detection** — Generate IPs, hostnames, case variations matching system identity; verify is_self_target returns True. Generate non-matching strings; verify returns False.
    - Create `tests/property/test_self_target_properties.py`
    - **Validates: Requirements 5.1, 5.2, 5.4, 5.5, 5.8**

  - [ ]* 3.3 Write unit tests for SelfTargetDetector
    - Test detection of matching hostname (short, FQDN, case variations)
    - Test detection of matching IP addresses (IPv4, IPv6, loopback)
    - Test "localhost" is always detected as self-target
    - Test non-matching hosts are allowed
    - Test identity resolution failure blocks all remediations
    - Create `tests/unit/test_self_target_detector.py`
    - _Requirements: 5.1, 5.3, 5.4, 5.5, 5.7_

- [ ] 4. Implement PoolHealthInspector
  - [ ] 4.1 Create `src/pool_health_inspector.py`
    - Implement `PoolHealthInspector` class with elb_client, min_healthy_threshold, api_timeout
    - Implement `check_pool_health(target_host, target_group_arns)` querying AWS ELB describe-target-health API
    - Implement `can_drain(target_host, target_group_arns)` returning (allowed, reason) tuple
    - Implement `would_breach_threshold(health_status)` checking if removing one healthy target breaches threshold
    - Handle percentage threshold (round up to nearest whole instance) and absolute count threshold
    - If target host is already unhealthy, treat removal as not reducing healthy count
    - Reject remediation if any single target group would fall below threshold (multi-TG evaluation)
    - Handle AWS API failure or timeout (>10s): reject remediation, log error
    - Handle host not registered in any target group: permit without checks
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10_

  - [ ]* 4.2 Write property tests for pool health threshold enforcement
    - **Property 7: Pool Health Threshold Enforcement** — Generate (total_targets, healthy_targets, threshold, target_is_healthy) tuples; verify would_breach_threshold returns correct decision
    - Create `tests/property/test_pool_health_properties.py`
    - **Validates: Requirements 4.2, 4.3, 4.9**

  - [ ]* 4.3 Write unit tests for PoolHealthInspector
    - Test threshold enforcement with percentage and absolute count
    - Test unhealthy target is permitted when healthy count meets threshold
    - Test multi-target-group evaluation (reject if any breaches)
    - Test AWS API failure results in rejection
    - Test host not in any target group is permitted
    - Mock boto3 elbv2 describe_target_health responses
    - Create `tests/unit/test_pool_health_inspector.py`
    - _Requirements: 4.1, 4.3, 4.5, 4.6, 4.9_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement TrafficDrainController
  - [ ] 6.1 Create `src/traffic_drain_controller.py` with drain and restore workflows
    - Implement `TrafficDrainController` class wrapping `RemediationExecutor`
    - Implement `execute()` method orchestrating: self-target check → risk classification → pool health check → drain → execute → restore
    - Implement `_drain_host()`: deregister from all target groups, poll until zero connections or timeout
    - Implement `_restore_host()`: re-register in all target groups, poll health checks every 5s until healthy or timeout
    - Handle partial deregistration failure: rollback already-deregistered targets, abort
    - Handle drain timeout: proceed with execution, record outcome as TIMEOUT_EXCEEDED
    - Handle restoration failure: retry up to 3 times with exponential backoff (1s, 2s, 4s)
    - If re-registration fails after retries, log error, dispatch notification, mark as manual intervention
    - Always attempt restoration after drain regardless of execution outcome (try/finally)
    - Pass through extra_vars to executor without modification
    - Record structured log entries for drain operations (start time, duration, outcome, affected TGs)
    - Skip drain workflow entirely for SAFE playbooks
    - Skip drain workflow when host not in any target group
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.10, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 7.3_

  - [ ]* 6.2 Write property tests for TrafficDrainController
    - **Property 2: Risk Level Determines Drain Invocation** — Generate (playbook, risk_level) pairs, verify drain invocation matches risk
    - **Property 4: Drain Deregisters All Target Groups Before Execution** — Generate lists of 1-10 TG ARNs, verify all deregistered before execute
    - **Property 5: No Target Groups Implies Drain Skipped** — Generate hosts with empty TG lists, verify SKIPPED outcome
    - **Property 6: Partial Deregistration Failure Triggers Rollback** — Generate TG lists with failure at random position K, verify rollback of 0..K-1
    - **Property 9: Restoration Always Attempted After Drain** — Generate execution results (success/failure/timeout), verify restoration attempted
    - **Property 10: Extra Vars Passthrough Preservation** — Generate arbitrary extra_vars dicts, verify executor receives identical dict
    - **Property 14: Rejection Dispatches Notification** — Generate rejection reasons, verify notification dispatched
    - Create `tests/property/test_drain_controller_properties.py`
    - **Validates: Requirements 1.4, 1.5, 2.1, 2.4, 2.5, 2.10, 3.1, 3.5, 7.2, 7.3**

  - [ ]* 6.3 Write unit tests for TrafficDrainController
    - Test full drain → execute → restore cycle (happy path)
    - Test drain timeout proceeds with execution
    - Test partial deregistration failure triggers rollback
    - Test restoration retry with exponential backoff
    - Test restoration failure dispatches notification
    - Test safe playbook bypasses drain
    - Test self-target rejection
    - Test pool health rejection
    - Test extra_vars passthrough
    - Create `tests/unit/test_traffic_drain_controller.py`
    - _Requirements: 2.1, 2.3, 2.5, 3.1, 3.4, 3.5, 7.3_

- [ ] 7. Implement pipeline integration and metrics
  - [ ] 7.1 Extend `src/metrics.py` with traffic safety Prometheus metrics
    - Add `traffic_drain_started_total` counter (labels: service_name, target_host)
    - Add `traffic_drain_completed_total` counter (labels: service_name, outcome)
    - Add `traffic_drain_timeout_total` counter (labels: service_name, target_host)
    - Add `traffic_drain_duration_seconds` histogram (labels: service_name)
    - Add `traffic_pool_health_rejections_total` counter (labels: service_name, target_group)
    - Add `traffic_self_target_blocks_total` counter (labels: target_host)
    - Add `traffic_restoration_completed_total` counter (labels: service_name, outcome)
    - Add `traffic_restoration_duration_seconds` histogram (labels: service_name)
    - _Requirements: 7.5_

  - [ ] 7.2 Integrate TrafficDrainController into `src/orchestrator.py`
    - Insert TrafficDrainController after ConcurrencyGuard and before RemediationExecutor in the pipeline
    - Load TrafficSafetyConfig at startup; if config missing, bypass controller entirely
    - Initialize SelfTargetDetector at startup, resolve identity
    - Initialize PlaybookRiskClassifier from playbook mapping config
    - Initialize PoolHealthInspector with boto3 elbv2 client
    - On controller rejection, treat as pipeline failure, include rejection reason in notification
    - On unexpected exception in controller, log error, abort remediation, dispatch notification
    - Record incident_id, target_host, drain duration, outcome in audit log
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.6, 7.7_

  - [ ] 7.3 Create `config/traffic_safety.yml` with default configuration
    - Include example service_target_groups mapping
    - Include default drain_timeout, health_check_timeout, min_healthy_threshold values
    - Include comments documenting valid ranges
    - _Requirements: 6.1, 6.3, 6.4, 6.5, 6.6_

  - [ ] 7.4 Extend `config/playbook_mapping.yml` with risk_level field
    - Add `risk_level` field to existing playbook mapping rules
    - Assign appropriate risk levels to existing playbooks (restart_service → disruptive, clear_disk → safe)
    - _Requirements: 1.3_

  - [ ]* 7.5 Write integration tests for pipeline with TrafficDrainController
    - Test end-to-end pipeline with mocked AWS APIs (drain → execute → restore)
    - Test bypass behavior when config file is absent
    - Test interaction with ConcurrencyGuard (controller respects guard decisions)
    - Test rejection notification dispatch
    - Test unexpected exception handling
    - Create `tests/integration/test_traffic_safety_integration.py`
    - _Requirements: 7.1, 7.2, 7.6, 7.7_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The project uses Python with asyncio, boto3, hypothesis, and pytest
- All new source files go in `src/` directory following existing patterns
- All property tests go in `tests/property/` following existing naming conventions
- All unit tests go in `tests/unit/` following existing patterns

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2", "3.3", "4.1"] },
    { "id": 3, "tasks": ["4.2", "4.3"] },
    { "id": 4, "tasks": ["6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "7.4"] },
    { "id": 7, "tasks": ["7.5"] }
  ]
}
```
