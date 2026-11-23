# Implementation Plan: Execution Concurrency Safety

## Overview

This plan implements a Concurrency Guard layer between the orchestrator's match and execute stages. The implementation builds incrementally: configuration and data models first, then individual safety components (lock manager, deduplicator, conflict matrix, priority queue, circuit breaker, blast radius limiter), followed by the facade that integrates them, orchestrator wiring, and finally comprehensive testing.

All components are pure asyncio-based Python, use the existing `Severity` enum, and follow the project's existing patterns (YAML config, dataclasses, structured logging).

## Tasks

- [x] 1. Configuration and data models
  - [x] 1.1 Create `config/concurrency.yml` and `config/conflict_matrix.yml` configuration files
    - Create `config/concurrency.yml` with all default values (host_lock_timeout: 120, suppression_window: 300, priority_queue_max_depth: 20, circuit_breaker threshold: 3, recovery_period: 600, blast_radius max_concurrent_hosts: 5, overflow_threshold: 50)
    - Create `config/conflict_matrix.yml` with example conflict groups (service-restart, disk-operations, network-changes)
    - _Requirements: 1.4, 2.2, 3.1, 4.5, 5.2, 5.4, 6.1, 6.5_

  - [x] 1.2 Create `src/concurrency_models.py` with enums, dataclasses, and ConcurrencyConfig
    - Define `GuardRejectionReason` enum (SUPPRESSED, LOCK_TIMEOUT, CIRCUIT_OPEN, QUEUE_FULL, CAPACITY_EXCEEDED, CONFLICT_TIMEOUT)
    - Define `CircuitState` enum (CLOSED, OPEN, HALF_OPEN)
    - Define `SuppressionEntry` dataclass (hostname, alert_name, severity, timestamp)
    - Define `CircuitBreakerState` dataclass (state, consecutive_failures, last_failure_time, opened_at)
    - Define `ExecutionSlot` dataclass with ordering (priority, arrival_time, playbook_path, target_host, extra_vars, severity, alert_name, incident_id)
    - Define `ConflictGroup` dataclass (name, playbooks)
    - Define `ConcurrencyConfig` dataclass with all defaults and a `from_yaml(path)` classmethod that loads from YAML with fallback to defaults
    - _Requirements: 1.4, 2.2, 3.1, 4.5, 5.2, 5.4, 6.1, 6.5_

- [ ] 2. Implement HostLockManager
  - [x] 2.1 Create `src/host_lock_manager.py` with per-host asyncio lock management
    - Implement `HostLockManager` class with lazy `dict[str, asyncio.Lock]` population
    - Implement `acquire(hostname)` with configurable timeout using `asyncio.wait_for`
    - Implement `release(hostname)` to release the lock
    - Implement `is_locked(hostname)` to check lock state
    - Use `try/finally` pattern to guarantee lock release on exceptions
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [-] 2.2 Write property test for Host Mutual Exclusion (Property 1)
    - **Property 1: Host Mutual Exclusion**
    - Generate concurrent request counts, verify that at most one execution is active per host at any time
    - Create `tests/property/test_host_lock_properties.py`
    - **Validates: Requirements 1.1, 1.2**

  - [-] 2.3 Write property test for Host Lock Independence (Property 2)
    - **Property 2: Host Lock Independence**
    - Generate pairs of distinct hostnames, verify acquiring lock on one does not block the other
    - **Validates: Requirements 1.5**

  - [-] 2.4 Write property test for Lock Acquire/Release Round-Trip (Property 3)
    - **Property 3: Lock Acquire/Release Round-Trip**
    - Generate acquire/release sequences, verify lock returns to unlocked state
    - **Validates: Requirements 1.6**

- [ ] 3. Implement AlertDeduplicator
  - [x] 3.1 Create `src/alert_deduplicator.py` with suppression window logic
    - Implement `AlertDeduplicator` class with `dict[tuple[str, str], SuppressionEntry]` state
    - Implement `should_suppress(hostname, alert_name, severity)` checking suppression window and severity escalation
    - Implement `record_execution(hostname, alert_name, severity)` to start suppression window
    - Implement `cleanup_expired()` to remove stale entries (called periodically)
    - Allow higher-severity alerts to pass through and reset the suppression window
    - Use `time.monotonic()` for timing to avoid clock drift issues
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [-] 3.2 Write property test for Deduplication Metamorphic Bound (Property 4)
    - **Property 4: Deduplication Metamorphic Bound**
    - Generate alert sequences with varying severities within suppression window, verify executions ≤ severity escalations + 1
    - Create `tests/property/test_deduplicator_properties.py`
    - **Validates: Requirements 2.1, 2.3, 2.6, 2.7**

  - [-] 3.3 Write property test for Severity Escalation Override (Property 5)
    - **Property 5: Severity Escalation Override**
    - Generate severity pairs (lower, higher), verify higher-severity alert passes through suppression
    - **Validates: Requirements 2.5**

- [ ] 4. Implement ConflictMatrix
  - [x] 4.1 Create `src/conflict_matrix.py` with YAML-based conflict group management
    - Implement `ConflictMatrix` class with `from_yaml(path)` classmethod
    - Implement `get_conflicts(playbook_path)` returning set of conflicting playbook paths
    - Implement `is_conflicting(playbook_path, active_playbooks)` checking for active conflicts
    - Implement `to_yaml()` for serialization back to YAML
    - Handle missing/invalid YAML gracefully (log warning, return empty matrix)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [-] 4.2 Write property test for Conflict Detection (Property 6)
    - **Property 6: Conflict Detection**
    - Generate conflict groups and active playbook sets, verify conflicts are correctly detected
    - Create `tests/property/test_conflict_matrix_properties.py`
    - **Validates: Requirements 3.2**

  - [-] 4.3 Write property test for Conflict Matrix Configuration Round-Trip (Property 7)
    - **Property 7: Conflict Matrix Configuration Round-Trip**
    - Generate valid YAML configs, verify parse → serialize → parse produces equivalent result
    - **Validates: Requirements 3.6**

- [~] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement HostPriorityQueue
  - [-] 6.1 Create `src/priority_queue.py` with per-host bounded priority queue
    - Implement `ExecutionSlot` ordering using `@dataclass(order=True)` with priority (1=P1, 2=P2, 3=P3) and arrival_time
    - Implement `HostPriorityQueue` class with configurable `max_depth` (default 20)
    - Implement `enqueue(slot)` using `heapq` for O(log n) insertion, returning False if queue full
    - Implement `dequeue()` as async method using `asyncio.Event` or `asyncio.Condition` for blocking
    - Expose `depth` and `is_full` properties
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_

  - [~] 6.2 Write property test for Priority Queue Ordering Invariant (Property 8)
    - **Property 8: Priority Queue Ordering Invariant**
    - Generate mixed-severity slot sequences, verify dequeue order is (severity descending, arrival_time ascending)
    - Create `tests/property/test_priority_queue_properties.py`
    - **Validates: Requirements 4.1, 4.2, 4.6**

- [ ] 7. Implement HostCircuitBreaker
  - [~] 7.1 Create `src/circuit_breaker.py` with per-host state machine
    - Implement `HostCircuitBreaker` class with `dict[str, CircuitBreakerState]` per-host state
    - Implement `get_state(hostname)` returning current `CircuitState`
    - Implement `record_success(hostname)` resetting failure count and transitioning HALF_OPEN→CLOSED
    - Implement `record_failure(hostname)` incrementing failures and transitioning CLOSED→OPEN when threshold exceeded
    - Implement `can_execute(hostname)` checking state: CLOSED=allow, OPEN=reject (check recovery period for HALF_OPEN transition), HALF_OPEN=allow one probe
    - Use `time.monotonic()` for recovery period timing
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_

  - [~] 7.2 Write property test for Circuit Breaker Threshold and Rejection (Property 9)
    - **Property 9: Circuit Breaker Threshold and Rejection**
    - Generate failure counts exceeding threshold, verify transition to OPEN and rejection of requests
    - Create `tests/property/test_circuit_breaker_properties.py`
    - **Validates: Requirements 5.2, 5.3**

  - [~] 7.3 Write property test for Circuit Breaker Success Reset (Property 10)
    - **Property 10: Circuit Breaker Success Reset**
    - Generate failure sequences followed by success, verify failure count resets to zero
    - **Validates: Requirements 5.8**

  - [~] 7.4 Write property test for Circuit Breaker Determinism (Property 11)
    - **Property 11: Circuit Breaker Determinism**
    - Generate event sequences (success/failure), replay twice from CLOSED state, verify identical final state
    - **Validates: Requirements 5.10**

- [ ] 8. Implement BlastRadiusLimiter
  - [~] 8.1 Create `src/blast_radius_limiter.py` with host slot management
    - Implement `BlastRadiusLimiter` class with configurable `max_concurrent_hosts` and `overflow_threshold`
    - Implement `acquire_host_slot(hostname)` using asyncio.Semaphore or counter with distinct host tracking
    - Implement `release_host_slot(hostname)` to free the slot
    - Expose `active_host_count` and `queued_host_count` properties
    - Count distinct hosts (not distinct executions) toward the limit
    - Return False (CAPACITY_EXCEEDED) when queued hosts exceed overflow threshold
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [~] 8.2 Write property test for Blast Radius Invariant (Property 12)
    - **Property 12: Blast Radius Invariant**
    - Generate acquire/release sequences, verify active hosts never exceed configured maximum
    - Create `tests/property/test_blast_radius_properties.py`
    - **Validates: Requirements 6.1, 6.6**

  - [~] 8.3 Write property test for Blast Radius Distinct Host Counting (Property 13)
    - **Property 13: Blast Radius Distinct Host Counting**
    - Generate multi-execution-per-host scenarios, verify a host with multiple executions counts as one
    - **Validates: Requirements 6.3**

- [~] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement ConcurrencyGuard facade and metrics
  - [~] 10.1 Extend `src/metrics.py` with concurrency guard metrics
    - Add counter: `guard_lock_acquisitions_total` (hostname label)
    - Add histogram: `guard_lock_wait_seconds` (hostname label)
    - Add counter: `guard_alerts_suppressed_total` (hostname, alert_name labels)
    - Add counter: `guard_conflict_rejections_total` (hostname, playbook labels)
    - Add counter: `guard_circuit_breaker_trips_total` (hostname label)
    - Add gauge: `guard_queue_depth` (hostname label)
    - Add gauge: `guard_active_hosts` (no labels)
    - Add counter: `guard_capacity_rejections_total` (no labels)
    - _Requirements: 4.4, 5.9, 6.4, 7.6_

  - [~] 10.2 Create `src/concurrency_guard.py` implementing the ConcurrencyGuard facade
    - Implement `ConcurrencyGuard.__init__` accepting `RemediationExecutor`, `ConcurrencyConfig`, and `MetricsCollector`
    - Initialize all sub-components: `AlertDeduplicator`, `BlastRadiusLimiter`, `HostCircuitBreaker`, `ConflictMatrix`, `HostPriorityQueue` (per-host dict), `HostLockManager`
    - Implement `execute(playbook_path, target_host, extra_vars, severity, alert_name, incident_id)` orchestrating the full flow:
      1. AlertDeduplicator check → return SUPPRESSED if duplicate
      2. BlastRadiusLimiter acquire → return CAPACITY_EXCEEDED if overflow
      3. CircuitBreaker check → return CIRCUIT_OPEN if open
      4. ConflictMatrix check → queue if conflicting
      5. PriorityQueue enqueue → return QUEUE_FULL if full
      6. HostLockManager acquire → return LOCK_TIMEOUT if timeout
      7. Delegate to `RemediationExecutor.execute()`
      8. Record success/failure in circuit breaker
      9. Release lock and blast radius slot in `finally` block
    - Return `ExecutionResult` with appropriate `GuardRejectionReason` in stderr on rejection
    - Record metrics at each decision point
    - Implement structured JSON logging for all guard decisions
    - Handle internal exceptions with fail-open behavior (log error, attempt execution without guard)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [ ] 11. Integrate ConcurrencyGuard with Orchestrator
  - [~] 11.1 Modify `src/orchestrator.py` to use ConcurrencyGuard between match and execute stages
    - Add `ConcurrencyGuard` as an optional dependency in `Orchestrator.__init__`
    - In `_run_pipeline`, after match stage, call `ConcurrencyGuard.execute()` instead of `self._executor.execute()` when guard is available
    - Pass `severity`, `alert_name`, and `incident_id` from the enriched alert to the guard
    - When guard rejects (status=FAILURE with guard rejection reason in stderr), log rejection and dispatch notification
    - Ensure rejected/queued executions do not block other independent pipeline executions
    - Record audit trail entry for rejected or queued executions including rejection reason and queue wait time
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [~] 11.2 Update `src/main.py` and `src/app.py` to wire ConcurrencyGuard into the application
    - Load `ConcurrencyConfig` from `config/concurrency.yml`
    - Instantiate `ConcurrencyGuard` with executor, config, and metrics collector
    - Pass guard to orchestrator constructor
    - Start background task for `AlertDeduplicator.cleanup_expired()` every 60 seconds
    - _Requirements: 7.1_

- [ ] 12. Unit tests for all components
  - [~] 12.1 Write unit tests for ConcurrencyConfig and YAML loading
    - Test loading valid config, missing file (defaults), invalid YAML (defaults)
    - Create `tests/unit/test_concurrency_config.py`
    - _Requirements: 1.4, 2.2, 3.5_

  - [~] 12.2 Write unit tests for HostLockManager
    - Test lock acquisition, release, timeout, concurrent access serialization
    - Create `tests/unit/test_host_lock_manager.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [~] 12.3 Write unit tests for AlertDeduplicator
    - Test suppression within window, expiry after window, severity escalation override, cleanup
    - Create `tests/unit/test_alert_deduplicator.py`
    - _Requirements: 2.1, 2.3, 2.4, 2.5_

  - [~] 12.4 Write unit tests for ConflictMatrix
    - Test YAML loading, conflict detection, missing file fallback, round-trip serialization
    - Create `tests/unit/test_conflict_matrix.py`
    - _Requirements: 3.1, 3.2, 3.5, 3.6_

  - [~] 12.5 Write unit tests for HostPriorityQueue
    - Test priority ordering, FIFO within same priority, queue full rejection, depth metric
    - Create `tests/unit/test_priority_queue.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.5_

  - [~] 12.6 Write unit tests for HostCircuitBreaker
    - Test state transitions: CLOSED→OPEN→HALF_OPEN→CLOSED, probe success/failure, recovery period
    - Create `tests/unit/test_circuit_breaker.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [~] 12.7 Write unit tests for BlastRadiusLimiter
    - Test max host cap, distinct host counting, overflow rejection, slot release
    - Create `tests/unit/test_blast_radius_limiter.py`
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [~] 12.8 Write unit tests for ConcurrencyGuard facade
    - Test full flow (happy path), each rejection path, fail-open on internal error, metrics recording
    - Create `tests/unit/test_concurrency_guard.py`
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6_

- [ ] 13. Integration tests
  - [~] 13.1 Write integration tests for end-to-end pipeline with ConcurrencyGuard
    - Test concurrent alert processing verifying no host conflicts
    - Test circuit breaker recovery after simulated failures
    - Test blast radius limiting under simulated alert storm
    - Test orchestrator correctly dispatches notifications on guard rejection
    - Create `tests/integration/test_concurrency_integration.py`
    - _Requirements: 7.1, 7.2, 7.4_

- [~] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (13 properties using Hypothesis)
- Unit tests validate specific examples and edge cases
- All components use `time.monotonic()` for timing to avoid clock drift
- The ConcurrencyGuard is fail-open: internal exceptions log an error and attempt execution without the guard
- Background cleanup task for expired suppression entries runs every 60 seconds

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "3.2", "3.3", "4.2", "4.3", "6.1"] },
    { "id": 3, "tasks": ["6.2", "7.1", "8.1"] },
    { "id": 4, "tasks": ["7.2", "7.3", "7.4", "8.2", "8.3"] },
    { "id": 5, "tasks": ["10.1"] },
    { "id": 6, "tasks": ["10.2"] },
    { "id": 7, "tasks": ["11.1", "11.2"] },
    { "id": 8, "tasks": ["12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.7"] },
    { "id": 9, "tasks": ["12.8", "13.1"] }
  ]
}
```
