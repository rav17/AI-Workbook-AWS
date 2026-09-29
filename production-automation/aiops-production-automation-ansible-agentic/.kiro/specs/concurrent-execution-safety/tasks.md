# Tasks: Concurrent Execution Safety

## Task 1: Create concurrency data models and enums
- [x] Create `src/concurrency/__init__.py` package
- [x] Create `src/concurrency/models.py` with data models: `HostLock`, `QueueEntry`, `CircuitBreakerState`, `FingerprintRecord`, `ResourceConflict`, `ExecutionDecision`, `StateTransition`, `PreemptionRecord`
- [x] Create `src/concurrency/enums.py` with enums: `ConflictResolutionStrategy`, `CircuitBreakerStateEnum`, `ExecutionDecisionType`
- [x] Create `src/concurrency/config.py` with `ConcurrencyConfig` dataclass holding all configurable parameters with defaults and validation

## Task 2: Implement the DynamoDB-backed LockStore
- [x] Create `src/concurrency/lock_store.py` with `LockStore` class
- [x] Implement `acquire_host_lock()` using DynamoDB conditional writes with TTL
- [x] Implement `release_host_lock()` with conditional delete
- [x] Implement `acquire_host_locks_atomic()` for multi-host atomic lock acquisition
- [x] Implement fingerprint CRUD: `read_fingerprint()`, `write_fingerprint_conditional()`, `delete_fingerprint()`
- [x] Implement circuit breaker state storage: `get_circuit_breaker_state()`, `update_circuit_breaker_state()`
- [x] Handle DynamoDB unreachability gracefully (reject execution, never proceed unsafely)

## Task 3: Implement AlertDeduplicator
- [x] Create `src/concurrency/deduplicator.py` with `AlertDeduplicator` class
- [x] Implement `compute_fingerprint()` deterministically combining alert_name, target_host, severity
- [x] Implement `check_and_acquire()` using LockStore conditional writes
- [x] Implement `clear_on_failure()` to remove fingerprint after failed remediation
- [x] Validate suppression window config (30-1800s, default 300s)

## Task 4: Implement PriorityQueue
- [x] Create `src/concurrency/priority_queue.py` with `PriorityQueue` class
- [x] Implement severity-ordered (P1 highest) then timestamp-ordered queuing
- [x] Implement `enqueue()` with max depth check (default 20 per host)
- [x] Implement `dequeue_for_host()` returning highest-priority entry
- [x] Implement `expire_stale_entries()` for queue timeout handling
- [x] Implement `contains_incident()` for duplicate submission detection
- [x] Implement `get_depth()` and `remove_by_incident()`

## Task 5: Implement CircuitBreakerManager
- [x] Create `src/concurrency/circuit_breaker.py` with `CircuitBreakerManager` class
- [x] Implement CLOSED → OPEN transition after configurable consecutive failures (default 3)
- [x] Implement OPEN → HALF_OPEN transition after cooldown period (default 300s)
- [x] Implement HALF_OPEN → CLOSED on probe success, HALF_OPEN → OPEN on probe failure
- [x] Implement `check_state()` returning allow/reject decision with reason
- [x] Implement `record_outcome()` tracking success/failure
- [x] Implement `manual_reset()` for API-driven circuit breaker reset

## Task 6: Implement ResourceConflictRegistry
- [x] Create `src/concurrency/resource_registry.py` with `ResourceConflictRegistry` class
- [x] Implement YAML configuration loading with schema validation
- [x] Implement `get_resource_categories()` returning resource list per action
- [x] Implement `detect_conflicts()` comparing active executions' resources
- [x] Implement `get_resolution_strategy()` for each resource category
- [x] Support runtime reload within 30 seconds of file modification
- [x] Handle unregistered actions (allow execution with warning)

## Task 7: Implement DependencyGraph
- [x] Create `src/concurrency/dependency_graph.py` with `DependencyGraph` class
- [x] Implement YAML configuration loading with cycle detection
- [x] Implement `get_predecessors()` and `get_transitive_successors()`
- [x] Implement `are_independent()` for parallel execution decisions
- [x] Implement `validate_acyclic()` rejecting cycles with error logging
- [x] Enforce max 200 nodes and 500 edges limits

## Task 8: Implement ConcurrencyMetrics
- [x] Create `src/concurrency/metrics.py` with `ConcurrencyMetrics` class
- [x] Implement structured JSON log emission for: queued, conflict, suppression, circuit breaker, preemption events
- [x] Implement CloudWatch metric publishing at 60-second intervals
- [x] Implement retry logic for failed log emissions (retry once within 5 seconds)
- [x] Track dropped-logs counter for failed retries

## Task 9: Implement ConcurrencyManager facade
- [x] Create `src/concurrency/manager.py` with `ConcurrencyManager` class
- [x] Implement `request_execution()` orchestrating: deduplication → circuit breaker → dependency → resource conflict → host lock
- [x] Implement `complete_execution()` releasing locks, updating circuit breaker, clearing fingerprints on failure
- [x] Implement preemption logic for P1/P2 vs P4/P5 (severity difference ≥ 2)
- [x] Implement forced lock release after configurable timeout (default 600s)
- [x] Wire all subsystems together in the correct order

## Task 10: Implement Status API endpoints
- [x] Create `src/concurrency/api.py` with FastAPI router
- [x] Implement `GET /concurrency/status` returning active locks, queue depths, circuit breaker states, suppression entries
- [x] Implement `POST /concurrency/circuit-breaker/{host}/reset` for manual circuit breaker reset
- [x] Cap response to 1000 entries per category with total count field

## Task 11: Create YAML configuration files
- [x] Create `config/resource_conflicts.yaml` with sample action-to-resource mappings
- [x] Create `config/execution_dependencies.yaml` with sample dependency edges
- [x] Document configuration schema in YAML comments

## Task 12: Integrate ConcurrencyManager with Orchestrator
- [x] Modify `src/orchestrator.py` to accept optional `ConcurrencyManager` dependency
- [x] Insert `request_execution()` call between match and execute stages
- [x] Insert `complete_execution()` call after execution completes
- [x] Maintain backward compatibility (concurrency manager is optional)
