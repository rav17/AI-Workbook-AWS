# Aria AI Relationship Manager Constitution

## Core Principles

### I. Structured State Is Authoritative

Transactional workflow state MUST be represented by typed Python models and persisted independently of conversation history and long-term memory. The model may propose a change, but application code owns state transitions, revisions, persistence, and recovery.

### II. Deterministic Safety and Authorization

Business rules, immutable fields, KYC/AML gates, tenant boundaries, tool authorization, and credential handling MUST be enforced in application code, Gateway policy, IAM, or backend services. Prompts and tool visibility are not security boundaries.

### III. Patch, Validate, and Invalidate

User corrections MUST use patch semantics. Accepted patches MUST be validated transactionally, increment the state revision, invalidate declaratively defined dependent values, preserve unrelated valid values, and return the earliest affected workflow step.

### IV. Bounded Context and Tool Use

System prompts MUST remain stable and concise. Each model call MUST receive only the relevant state, memory, tools, and tool results. Tool schemas and results MUST be compact. Strands context-management facilities, invocation limits, timeouts, and cancellation MUST be configured and measured rather than relying on unbounded history.

### V. Durable Boundaries and Session Isolation

AgentCore Runtime session IDs MUST be unique per user conversation and reused for related turns. Runtime and Strands session state are continuity mechanisms, not the sole durable store. AgentCore Memory is for scoped durable facts, preferences, and summaries, never authoritative current transactional state.

### VI. Python Quality and Operational Readiness

Python code MUST use type hints, Pydantic validation at external boundaries, small cohesive modules, explicit exception handling, timezone-aware timestamps, dependency pinning, linting, formatting, static analysis, security checks, and deterministic tests. External calls MUST have bounded timeouts, retries only for safe transient failures, idempotency where side effects exist, structured logs, metrics, traces, and redaction.

## Security and Compliance Requirements

- Bedrock Guardrails MUST be applied to input and output where configured, and guardrail intervention MUST be handled explicitly.
- Credentials, tokens, secrets, and unnecessary sensitive client data MUST NOT be logged, persisted in prompts, or returned in tool results.
- Gateway tool filtering MAY reduce model context but MUST NOT replace IAM, OAuth scopes, Gateway policies, or backend authorization.
- Configuration MUST be environment-specific and loaded from approved configuration or secret-management mechanisms.
- Audit events MUST include correlation identifiers and safe metadata without raw prompts or sensitive payloads.

## Development and Verification Gates

- Every change MUST include focused unit tests; state transitions, validators, provider adapters, and security boundaries require property or integration coverage as appropriate.
- CI MUST run formatting, linting, type checking, dependency/security checks, unit tests, and contract tests before deployment.
- Live AWS/CRM tests MUST be isolated to explicitly configured non-production environments.
- Architecture decisions, assumptions, SLOs, data retention, and provider contracts MUST be documented before production enablement.

## Governance

This constitution governs implementation decisions for the Aria agent. A simpler alternative may be chosen only when the reason, risk, and compensating tests are documented in the feature plan. Changes to security, state authority, or data handling require review and an update to this constitution or the relevant architecture record.

**Version**: 1.0.0 | **Ratified**: 2026-09-17 | **Last Amended**: 2026-09-17
