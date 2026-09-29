"""Safe Execution Guardrails module.

Multi-layered safety engine between playbook matching and execution stages.
Evaluates remediation actions through ordered checks producing
ALLOW, DENY, or DEFER decisions with full audit trail.

Components:
- GuardrailEngine: Orchestrates all checks with short-circuit semantics
- SelfProtectionGuard: Blocks targeting automation host
- MaintenanceWindowManager: Defers during planned maintenance
- CircuitBreaker: Halts after consecutive failures
- ConcurrencyGuard: Prevents duplicate/parallel remediations
- BlastRadiusClassifier: Classifies risk level
- HealthChecker: Verifies peer health
- ApprovalGate: Human approval for HIGH/CRITICAL risk
- PlanValidator: Blocks dangerous AI-generated commands (NEW)
- StopConditionsMonitor: Aborts execution on system degradation (NEW)
- BakingValidator: Validates fix effectiveness post-execution (NEW)
"""
