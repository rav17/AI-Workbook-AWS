# Spec Kit Sandbox Constitution

## Core Principles

### I. Intent Before Implementation

For greenfield features, brownfield enhancements, and planned refactoring,
establish a specification with testable acceptance criteria before changing
application code. Define what and why in the specification; define how in
the plan. Keep the specification, plan, tasks, implementation, and directly
related documentation synchronized when requirements or decisions change.
Use the installed bug assessment, fix, and test process for repairs and
hotfixes, updating affected specifications when intended behavior changes.

### II. Evidence-Based Brownfield Changes

Inspect the existing architecture, contracts, conventions, dependencies,
and relevant tests before designing a change. Record baseline checks and
pre-existing failures. Reuse established components and preserve public
contracts and existing behavior unless a change is explicitly approved.
For schema, data, or breaking interface changes, document compatibility,
migration, verification, and rollback before implementation.
Do not require a retrospective specification of the entire existing system.

### III. Verifiable Outcomes

Map acceptance criteria to tasks and verification evidence. Use existing
test, lint, and build commands; add focused tests for introduced or fixed
behavior. Compare relevant regression results with the baseline.
Record actual commands, results, failures, and checks not run. Do not equate
generated artifacts, passing structural checks, or an unexecuted test with
verified application behavior. Declare a bug verified only after the
original symptom and relevant regression checks have been exercised.

### IV. Bounded Exploration

State the question, stable requirements, alternatives, evaluation criteria,
timebox, and exit decision before an exploratory spike. Preserve alternative
plans and evidence without overwriting an approved delivery plan.
Run prototype code only within an explicitly approved scope and isolated
location. Record limitations and compare measured results; do not silently
promote a prototype to production. Select a delivery approach, request
clarification, or stop based on the recorded evidence.

### V. Explicit Review and Scope Control

Review specifications before planning, plans before task generation, and
tasks plus cross-artifact analysis before implementation. Resolve blocking
ambiguities and constitution conflicts before proceeding.
At each approval gate, present the decision and scope, artifact links,
change summary, actual review and validation results, unresolved risks,
and precisely what approval authorizes. Wait for explicit approval.
Do not expand approved scope or make technology and compliance mandates
without supporting requirements.

## Development Workflow

- Greenfield: constitution, specify, clarify as needed, plan, tasks,
  analyze, implement, then converge. Use checklist when requirements need
  additional quality review. Repeat implementation and convergence until
  convergence reports `Converged`.
- Brownfield: inspect and baseline first, then follow the same feature
  lifecycle for the bounded change. Specify preserved behavior and
  regression checks. Refactoring must state behavioral invariants.
- Exploratory: compare alternative plans against the same specification.
  Authorize bounded prototype tasks separately from production delivery.
  After selection, reconcile the chosen plan and design artifacts, generate
  delivery tasks, analyze, and obtain implementation approval.
- Repairs and hotfixes: assess, review the cause and scope, fix, then test.
  Urgency does not waive assessment, verification, or recording risks.
- Keep shared feature artifacts under `specs/` and repair reports under
  `.specify/bugs/`. Resume from existing artifacts rather than recreating
  them. Select the active feature explicitly when context is ambiguous.

## Tooling and Data Boundaries

Use the current client's installed Spec Kit integration. Integration
selection changes shared state, so do not switch integrations concurrently
in the same workspace. Use separate workspace copies for parallel agents.
Copilot and Claude co-installation is an accepted local exception to
Spec Kit's multi-install safety declaration, not a clean status result.

Use an existing Graphify graph for repository context, verify gaps against
source, and refresh the local AST graph after code changes. Graphify does
not replace specifications or test evidence. Keep extraction local and
code-only; do not enable external LLM extraction or cloud publishing.
Never commit secrets or expose sensitive data in generated artifacts.

## Governance

This constitution governs subsequent project work. Its initial
technology-neutral baseline was explicitly approved by the workspace user.
No application stack, performance target, coverage threshold, or deployment
platform is mandated without a later approved requirement.

Amendments require rationale, explicit approval, a version/date update,
and review of affected specifications, plans, tasks, and agent instructions.
Record exceptions and their scope rather than silently bypassing principles.
Use semantic versioning: major for incompatible governance changes, minor
for new principles, and patch for clarifications.

**Version**: 1.0.0 | **Ratified**: 2026-11-17 | **Last Amended**: 2026-11-17
