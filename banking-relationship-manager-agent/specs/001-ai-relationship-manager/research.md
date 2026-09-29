# Research: Aria AI Relationship Manager

## Decision: Use the Strands Agents SDK with Amazon Bedrock Claude

**Rationale**: The source design explicitly selects Strands for tool-based orchestration and Bedrock Claude for the foundation model. This supports custom tools, conversation memory, and AWS deployment options.

**Alternatives considered**: A direct Bedrock client would reduce framework dependencies but would require rebuilding tool registration, orchestration, and agent state conventions.

## Decision: Use Amazon Bedrock Guardrails for input and output controls

**Rationale**: The requirements demand prompt injection detection, credential redaction, denied-topic enforcement, and safe output behavior. A managed guardrail service is the source design choice and can fail closed at the application boundary.

**Alternatives considered**: NeMo Guardrails or Llama Guard were listed in the requirements glossary, but the design selects Bedrock Guardrails for managed AWS integration.

## Decision: Use Bedrock Knowledge Bases for rate and policy retrieval

**Rationale**: The knowledge-base tool must retrieve current product data, preserve source dates, expose citations, and signal escalation when confidence is insufficient.

**Alternatives considered**: A custom OpenSearch retrieval layer would provide more control but would duplicate managed ingestion and retrieval responsibilities.

## Decision: Separate typed domain models from provider tools

**Rationale**: Client profiles, risk, compliance, interaction, session, and escalation values need deterministic validation and testability independent of AWS adapters.

**Alternatives considered**: Passing untyped dictionaries through tools would be faster initially but weakens validation, traceability, and property-based testing.

## Decision: Start with mocked external-service tests

**Rationale**: The initial repository has no provisioned AWS or CRM environment. Unit and property tests can validate safety and domain behavior without credentials; integration tests can be added once contracts and environments exist.

**Alternatives considered**: End-to-end tests against live AWS would be slower, cost-bearing, environment-dependent, and unsafe for credential-handling tests.

## Decisions requiring confirmation

- CRM provider and API schema.
- Production model, guardrail, knowledge-base, DynamoDB, and EventBridge identifiers.
- Authentication, authorization, audit retention, and data residency policies.
- Exact compliance thresholds and human response-time commitments.
- Production latency and availability objectives.

## Production Best Practices

### Strands state and structured output

Use Strands agent state only for agent-local, JSON-serializable state and use invocation state for request-scoped correlation data. Use Pydantic structured output or a typed patch tool for model proposals, then validate and persist changes in application code. Do not mutate conversation messages as a substitute for transactional state.

### Strands context management

Use the context-management or conversation-management feature supported by the pinned SDK version. Prefer proactive compression, bounded windows, compact tool results, message pinning for essential instructions, and token/turn limits. Do not configure a context manager and a competing conversation manager without verifying precedence. Context-management storage must be durable or reconstructible if sessions can restart.

### AgentCore Runtime

Reuse one unique runtime session ID for each logical conversation and map it to the authenticated user in the caller application. Runtime sessions provide isolated, multi-turn execution but compute and in-memory state are ephemeral; restart recovery must load authoritative workflow state from durable storage. Handle session conflicts with bounded exponential backoff and prevent concurrent writers for the same conversation.

### AgentCore Memory

Separate short-term conversational context from long-term facts, preferences, and summaries. Scope stores by tenant/user, retrieve only relevant records with a small top-k, define retention/deletion behavior, and prevent current transactional values from being overwritten by memory. Use a cheaper extractor where supported and do not synchronously extract memories on every turn unless measured requirements justify the cost.

### AgentCore Gateway

Use Gateway for secure MCP/API connectivity, credential exchange, routing, semantic tool discovery, and policy enforcement. Tool filtering reduces prompt size but is not authorization. Keep a capability allowlist per workflow step, expose only relevant tools, validate tool inputs at the backend, and test the configured MCP protocol version and auth flow.

### Amazon Bedrock and Guardrails

Pin model and Guardrails identifiers per environment. Configure input and output guardrails, explicit redaction behavior, trace handling for controlled diagnostics, and safe handling of `guardrail_intervened` results. Never log raw protected content or guardrail traces without a reviewed redaction policy. Use Bedrock retrieval with citations/source dates and escalate on low confidence rather than fabricating answers.

### Python engineering baseline

Use `pyproject.toml` as the project configuration source, pinned or locked dependencies, type hints, small modules, Pydantic models at external boundaries, timezone-aware UTC timestamps, explicit exception types, context managers for resources, and async-compatible clients on async paths. Run Ruff formatting/linting, static type checking, pytest, Hypothesis, dependency vulnerability scanning, and secret scanning in CI. Add timeouts, safe retries, idempotency keys, circuit-breaking or bounded degradation for remote calls, and structured logging with correlation IDs.

## AWS CDK v2 Decisions

### Decision: Use constructs for reuse and stacks for deployment boundaries

AWS CDK guidance recommends modeling reusable logical units as constructs and using stacks as deployment units. Start with stateful, shared, Gateway/runtime, and observability boundaries only where lifecycle and blast-radius requirements justify them. Do not create one stack per resource or serialize unrelated stacks without evidence.

### Decision: Prefer direct references inside one CDK app

Direct construct references provide CDK-managed dependency edges and are the simplest option inside one app. SSM Parameter Store is reserved for independently deployed stacks or runtime lookup of values that cannot be known at synthesis. Every SSM handoff needs ownership, existence, versioning, and rollback tests.

### Decision: Use explicit names selectively

AWS CDK guidance favors generated physical names because hard-coded names complicate replacement and multi-environment deployment. Explicit names are allowed for contractual resources, external integrations, or operational identifiers, but each must document replacement and migration behavior.

### Decision: Enforce boundaries through the supported API

Apply an organization permissions boundary with `iam.PermissionsBoundary.of(scope).apply(policy)` or the equivalent supported CDK API. A managed policy attached to a role is permissions, not a permissions boundary.

### Decision: Make synthesis deterministic and deployment controlled

Commit context lookup results when used, avoid side effects during synthesis, model environments in code, and test synthesized templates. Production deployment requires a federated role, security checks, `cdk diff` or a change set, approval, and rollback strategy. `--require-approval never` is not a production default.

### Decision: Test infrastructure contracts

Use fine-grained `aws_cdk.assertions` tests for encryption, permissions boundaries, logical IDs, removal policies, tags, log retention, alarms, and environment overrides. Use snapshots only for stable construct output. Add sandbox integration tests after synthesis tests pass.

### Decision: Treat auto-discovery as opt-in

YAML-driven resource discovery can reduce CDK code changes, but it increases validation and blast-radius complexity. It must be schema-validated, repository-rooted, allowlisted, deterministic, and independently tested. The first implementation should use hand-wired stacks and add discovery only when repeated resource types justify it.

## Shared Framework Decisions

### Decision: Centralize cross-agent lifecycle behavior, not domain behavior

Centralize configuration loading, model construction, Gateway/MCP authentication, bounded memory/context assembly, lifecycle hooks, cleanup, retries, and observability. Keep prompts, workflow transitions, patch semantics, tool selection policy, and business validation in each agent or shared domain packages. This creates a thin-entrypoint pattern without hiding business decisions inside a framework.

### Decision: Use typed extension contracts

Define runtime-checkable Python protocols for prompt builders, payload parsers, tool filters, skills builders, and pre-invocation guards. Validate required hooks at startup or the first controlled invocation and provide conservative defaults for optional hooks. Protocols should be small and should not expose provider internals to agent modules.

### Decision: Load configuration lazily and cache immutable settings

Configuration that depends on Runtime-provided environment variables, SSM, or other network resources must be loaded inside the invocation boundary, never at module import. Cache only validated immutable configuration and make failures observable with safe diagnostics. Tests must cover cold start, missing configuration, transient SSM failure, and refresh behavior.

### Decision: Keep context and memory strategy provider-compatible

The prompt's dynamic-context boundary is useful, but Bedrock prompt-cache block syntax, cache pricing, and model support are provider/API-version dependent. Implement a context assembler with a plain-text fallback, and add compatibility tests before enabling provider-specific cache blocks. Use Strands session/context managers or AgentCore Memory integrations when they meet the bounded-context requirement; use direct MemoryClient calls only when the selected SDK integration cannot provide the required scope, retrieval cap, redaction, or durability.

### Decision: Use shared hooks for observability and safety

Strands hooks are the right extension point for request/model/tool lifecycle telemetry, validation, redaction, retry decisions, and tool-count limits. Hooks must remain composable, record mutations, avoid raw sensitive content, and distinguish expected tool errors from programmer/configuration errors. Cleanup and memory flushes must be exception-safe, but their exact ordering must be tested against the pinned SDK lifecycle.

### Decision: Do not mandate background threads or synchronous invocation

The prompt's daemon-thread pattern and synchronous `agent(prompt)` requirement may be valid for a particular Runtime protocol, but they are not universal best practices. AgentCore supports synchronous, streaming, and asynchronous workloads; choose based on request timeout, cancellation, retry, and delivery semantics. Never use daemon threads for work whose completion or persistence is required unless Runtime explicitly supports and monitors that lifecycle. Test the selected model invocation API against the pinned Python SDK.

### Decision: Standardize agent manifests with framework tuning separated

Use `agent.yaml` for deployment discovery fields plus a namespaced framework section for tuning. Validate unknown fields, defaults, numeric bounds, tool allowlists, model IDs, memory scopes, and environment overrides before deployment. A new agent should require a manifest and entrypoint plus only the optional hooks it needs, without changing shared framework or CDK code.

### Evidence

- Strands state: https://strandsagents.com/docs/user-guide/concepts/agents/state/
- Strands session management: https://strandsagents.com/docs/user-guide/concepts/agents/session-management/
- Strands context management: https://strandsagents.com/docs/user-guide/concepts/context-management/
- Strands guardrails: https://strandsagents.com/docs/user-guide/safety-security/guardrails/
- AgentCore Runtime sessions: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html
- AgentCore Memory: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
- AgentCore Gateway: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html
- Python standard library and quality guidance: https://docs.python.org/3/tutorial/stdlib.html
- AWS CDK best practices: https://docs.aws.amazon.com/cdk/v2/guide/best-practices.html
- AWS CDK testing: https://docs.aws.amazon.com/cdk/v2/guide/testing.html
- AWS CDK permissions boundaries: https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/PermissionsBoundary.html
- AWS CDK bootstrapping: https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html
- Strands hooks: https://strandsagents.com/docs/user-guide/concepts/agents/hooks/
- Strands structured output: https://strandsagents.com/docs/user-guide/concepts/agents/structured-output/
