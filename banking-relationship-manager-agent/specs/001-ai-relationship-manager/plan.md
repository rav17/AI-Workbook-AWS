# Implementation Plan: Aria AI Relationship Manager

**Branch**: `001-ai-relationship-manager` | **Date**: 2026-09-17 | **Spec**: [spec.md](spec.md)

## Summary

Implement Aria as a Python agent using the Strands Agents SDK and Amazon Bedrock Claude. The system will orchestrate guarded conversations, CRM context and logging, knowledge-base retrieval, risk assessment, retention events, compliance checks, human escalation, and authenticated API entry points.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: strands-agents (pin a tested release), strands-agents-tools, bedrock-agentcore, boto3, pydantic, httpx, python-dateutil

**Storage**: DynamoDB for authoritative workflow state, revisions, idempotency, and interaction logs; AgentCore Memory for scoped durable preferences/facts/summaries; CRM remains the system of record for client profile and CRM activity.

**Testing**: pytest, pytest-asyncio, Hypothesis, moto, Ruff, a Python type checker, dependency/security scanning; unit, property, integration, contract, red-team, and load tests with external services mocked or isolated in non-production.

**Target Platform**: AWS Lambda for API-backed handlers or AWS Fargate for long-running sessions.

**Project Type**: Python service with agent tools, event handlers, WebSocket/REST handlers, and AWS integrations.

**Performance Goals**: Return normal service responses within an agreed API latency budget; proactive events must be processed idempotently. Exact production SLOs require confirmation during research.

**Constraints**: Fail closed for guardrail failures, never persist credentials, do not fabricate rates, require KYC before product requests, preserve full escalation context, use bounded timeouts/retries, enforce idempotency for side effects, and keep authorization outside the model.

**Scale/Scope**: High-value retail and wealth-management clients in Premier and Imperia segments; scope includes 14 requirements and the components listed below.

## Constitution Check

The plan passes the ratified constitution:

- Structured workflow state is separate from conversation history and AgentCore Memory.
- State changes use typed patches, deterministic validation, revisions, and dependency invalidation.
- Runtime session continuity, durable workflow persistence, and long-term memory have separate responsibilities.
- Gateway tool visibility is treated as a context optimization; IAM, Gateway policy, and backend authorization remain authoritative.
- Guardrails, redaction, bounded retries, observability, Python quality gates, and isolated integration tests are explicit deliverables.

## Design Summary

- **Agent core**: `AriaAgent` handles input guardrails, session loading, tool-enabled reasoning, output guardrails, persistence, and CRM logging.
- **Workflow state**: `WorkflowState`, `StatePatch`, `StateValidator`, `DependencyResolver`, and `NextStepResolver` own current validated truth and corrections. The model can propose patches but cannot apply them directly.
- **Guardrails**: Amazon Bedrock Guardrails handle prompt injection, denied topics, sensitive information, and output sanitization. Processing fails closed, and intervention stop reasons are handled explicitly.
- **Tools**: CRM, knowledge base, risk, maturity/retention, compliance, and escalation tools use explicit typed models and Strands tool decorators.
- **Session**: AgentCore Runtime reuses one session ID per logical conversation; Strands session persistence is configured according to the pinned SDK; DynamoDB persists authoritative workflow state with optimistic concurrency and idempotency.
- **Memory**: AgentCore Memory stores scoped durable preferences, facts, and summaries. Retrieval is relevant and bounded; memory never overrides current workflow state.
- **Context**: Use the installed Strands context-management facility, compact context rendering, tool-result truncation/offloading, token/turn budgets, cancellation, and streaming. Do not configure competing context managers accidentally.
- **Gateway**: AgentCore Gateway provides MCP/API access, semantic discovery, credential exchange, routing, and policies. The application exposes only workflow-relevant tools and still enforces backend authorization.
- **Events**: EventBridge invokes maturity and outflow handlers for proactive outreach.
- **API**: API Gateway WebSocket chat and REST administration route authenticated requests to Lambda handlers.
- **Observability**: Structured logs and CloudWatch/X-Ray traces cover tool calls, guardrail outcomes, failures, and escalation IDs.
- **Python quality**: Use type hints, Pydantic at boundaries, Ruff formatting/linting, static type checking, pinned dependencies, timezone-aware datetimes, explicit exception taxonomy, safe async I/O, and no blocking calls on async paths.

## Project Structure

```text
aria/
├── __init__.py
├── agent.py
├── config.py
├── constants.py
├── models/
│   ├── client.py
│   ├── wallet.py
│   ├── interaction.py
│   ├── maturity.py
│   ├── risk.py
│   ├── compliance.py
│   ├── escalation.py
│   ├── session.py
│   └── knowledge.py
├── tools/
│   ├── crm_tool.py
│   ├── knowledge_tool.py
│   ├── risk_tool.py
│   ├── maturity_tool.py
│   ├── compliance_tool.py
│   └── escalation_tool.py
├── workflow/
│   ├── state.py
│   ├── patch.py
│   ├── validator.py
│   ├── dependencies.py
│   └── next_step.py
├── guardrails/
│   ├── config.py
│   └── processor.py
├── session/manager.py
├── memory/
│   └── manager.py
├── persistence/
│   ├── workflow_store.py
│   └── idempotency.py
├── providers/
│   ├── retry.py
│   └── clients.py
├── framework/
│   ├── __init__.py
│   ├── contracts.py
│   ├── config.py
│   ├── gateway.py
│   ├── memory.py
│   ├── context.py
│   ├── model.py
│   ├── hooks.py
│   ├── observability.py
│   └── runner.py
├── observability.py
├── events/
│   ├── handler.py
│   └── lambda_handler.py
└── api/
    ├── websocket_handler.py
    ├── rest_handler.py
    └── lambda_entry.py

tests/
├── conftest.py
├── unit/
├── integration/
└── property/

infra/
docs/
```

## Shared Agent Framework

Use a shared framework under `aria/framework/` so common AgentCore Runtime and Strands behavior is implemented once. The framework owns lazy configuration, model/provider construction, Gateway authentication and MCP lifecycle, bounded memory/context retrieval, shared hooks, cleanup, retries, and redacted observability. Agent modules own workflow-specific prompts, parsers, tool filters, skills, guards, domain models, and business rules.

The first agent entrypoint should be intentionally thin, but no fixed line count is a requirement. Readability, explicit dependency injection, and testability take precedence over a line-count target.

Recommended per-agent contract:

```text
aria/agents/<agent_name>/
├── agent.yaml
├── agentcore_entrypoint.py
├── system_prompt.py
├── workflow.py
├── models.py
├── skills.py              # optional
├── tool_filter.py         # optional
├── payload_parser.py      # optional
└── guards.py              # optional
```

The manifest schema must distinguish CDK/deployment fields from framework runtime tuning. Agent discovery must validate manifests before deployment and must not require CDK source changes for a new valid agent.

Framework invocation order is a tested default, not an unchangeable rule:

1. Authenticate and validate the request boundary.
2. Parse the payload into a typed request and resolve the Runtime session identity.
3. Load lazy, cached configuration.
4. Load authoritative workflow state.
5. Load only bounded, relevant memory/context.
6. Build the stable prompt plus dynamic context.
7. Discover/filter only relevant Gateway tools.
8. Construct the Strands agent with the pinned SDK configuration and shared hooks.
9. Invoke the agent using the supported Python API for the pinned release.
10. Validate/apply proposed state patches outside the model.
11. Persist state and memory with redaction and idempotency.
12. Emit telemetry and perform cleanup in `finally` paths.

The framework MUST NOT assume that a manual MemoryClient is always superior to Strands session/memory integrations. The implementation must benchmark and test the selected strategy. Likewise, background threads, fixed STM counts, provider-specific prompt-cache blocks, and synchronous versus asynchronous agent calls are compatibility decisions to verify against the pinned SDK and AgentCore Runtime protocol.

## Infrastructure Plan: AWS CDK v2

The infrastructure implementation is greenfield and must begin with the smallest deployable Aria slice. Use constructs for reusable resource patterns and stacks for deployment/lifecycle boundaries.

```text
cdk/
├── app.py
├── cdk.json
├── cdk.context.json
├── requirements.txt
├── requirements-dev.txt
├── constructs/
├── stacks/
│   ├── stateful_stack.py
│   ├── shared_stack.py
│   ├── gateway_stack.py
│   ├── runtime_stack.py
│   └── observability_stack.py
├── resource_discovery.py
├── staging.py
└── tests/
    ├── test_stateful.py
    ├── test_runtime.py
    ├── test_security.py
    └── conftest.py
```

### CDK deployment rules

- Stateful resources, compute, Gateway/runtime resources, and observability are separated only where their lifecycle or deployment safety justifies separate stacks. There is no mandatory seven-stack topology.
- `app.py` declares dependencies explicitly for actual resource ordering and shared policy serialization; unrelated stacks remain deployable in parallel.
- Use direct construct references between stacks in the same CDK app. Use SSM for independently deployed stacks or runtime resolution of non-deterministic values, with parameter existence and ownership tested.
- Apply the permissions boundary with `iam.PermissionsBoundary.of(app).apply(...)` or an equivalent CDK-supported API; do not add a boundary policy as an ordinary managed policy.
- Prefer generated physical names. Use explicit names only for contractual integrations, stable operational identifiers, or resources that must be referenced outside CloudFormation. Test replacement and migration behavior for every explicit name.
- Commit `cdk.context.json` when context lookups are used. CI may use `--lookups false` only when all required lookup values are already available and synthesis remains deterministic.
- Keep synthesis side-effect-free. Do not call AWS APIs from CDK code except supported context lookups; refresh external values through an explicit, reviewed command.
- Apply environment configuration at the CDK app boundary, use `DESTROY` only for approved development resources, use `RETAIN` and termination protection for production state, and never store secrets in `cdk.json`.
- Apply resource tags, encryption, log retention, data protection, alarms, and CDK Nag checks through reusable constructs or Aspects. Every suppression requires a specific rationale.
- Use fine-grained `aws_cdk.assertions` tests for security and lifecycle contracts; use snapshots sparingly for stable construct output. Add sandbox integration tests only after unit synthesis checks pass.
- Use federated/OIDC deployment roles and environment approvals. CI must run tests, synth, security checks, and diff/change-set review before production deployment.
- Treat auto-discovery as an optional extension. If enabled, validate YAML against a schema, resolve paths from the repository root, allow only registered resource types, sort discovery deterministically, and test add/disable/override behavior.

## Implementation Phases

1. Scaffold the Python project, configuration, typed models, test harness, and safe environment handling.
2. Implement workflow state, patch semantics, deterministic validation, optimistic concurrency, dependency invalidation, and next-step resolution before agent wiring.
3. Implement foundational Bedrock Guardrails, logging, external-client, idempotency, timeout, retry, and error-handling abstractions.
4. Deliver the P1 client profile, service query, CRM logging, credential protection, risk disclosure, compliance, escalation, knowledge, and CRM context stories.
5. Integrate AgentCore Runtime sessions, AgentCore Memory, compact context injection, and bounded Strands context management.
6. Deliver wallet profiling, product recommendations, retention events, conversation style, Gateway tool filtering, and policy enforcement.
7. Add agent orchestration, EventBridge handlers, API Gateway handlers, observability, deployment validation, and Python quality gates.
8. Implement and validate the AWS CDK app, stateful/compute boundaries, AgentCore resources, IAM boundaries, deterministic synthesis, CDK assertions, CDK Nag, and controlled CI/CD deployment.
9. Add property-based coverage for the 20 behavioral properties identified in the Kiro task plan plus correction, concurrency, security, context, tool-visibility, and infrastructure contract tests.
10. Build and validate the shared agent framework and migrate the first Aria entrypoint to it before adding additional agents.

## Risks and Open Decisions

- CRM Next versus Salesforce API contract and authentication.
- Bedrock model and Guardrails identifiers, regions, quotas, and latency.
- Exact AML thresholds, lending eligibility rules, outflow thresholds, and escalation SLAs.
- Whether chat is Lambda/WebSocket only or also requires a Fargate deployment.
- Data retention, audit, residency, encryption, and access-control requirements.
- The ratified constitution governs production implementation; amendments require explicit review and versioning.
- The first implementation milestone is the workflow state and validation boundary; no side-effecting tool should be enabled before it is in place.
- Strands SDK API names and context/session configuration MUST be verified against the pinned Python release; do not copy TypeScript examples into Python unchanged.
- AgentCore Runtime does not enforce application-level user-to-session mapping; the authenticated caller/session mapping belongs in the application boundary.
- AgentCore Memory extraction and retrieval policies require privacy, tenant scoping, retention, and deletion decisions before production.
- Gateway semantic tool search and dynamic tool loading require protocol/version compatibility tests and an authorization review.
- CDK stack count, physical names, SSM handoffs, KMS key boundaries, and auto-discovery remain architecture decisions to confirm before infrastructure code is generated.
- The shared framework must not become a second business-logic layer; domain rules remain in workflow/domain modules and deterministic validators.
- Exact Strands Python APIs for model caching, structured output, hooks, session managers, and context managers must be pinned and verified before implementation tasks hard-code them.
