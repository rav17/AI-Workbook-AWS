# Agent Framework

This project separates the shared runtime framework from the business-specific agent behavior.

## Core contracts

- A framework runner is responsible for execution mode selection, state patch handoff, cleanup, and safe error handling.
- Runtime-checkable provider contracts and adapters isolate AgentCore Runtime session mapping,
  tenant-bounded Memory retrieval, and Gateway discovery/authorization from business logic.
- An agent manifest defines runtime and framework tuning values without allowing unsafe or unknown fields.
- Business-specific logic remains in the agent entrypoint and system prompt instead of the shared framework layer.

## AgentCore boundary

`aria/framework/agentcore.py` provides injectable adapters and a tenant-bound Memory data-plane client. API Gateway verifies Cognito JWTs, then the request Lambda invokes Runtime with SigV4 and a backend-generated verified-principal payload. The Runtime resource policy restricts invocation to that Lambda role. The Runtime entrypoint validates prompts, applies input/output guardrails, invokes Strands, and retrieves bounded tenant-scoped Memory context. The authenticated API path uses DynamoDB-backed session state. Strands connects to the IAM-authorized Gateway using MCPClient and SigV4; the Runtime filters discovered tools to the no-argument `get_risk_questionnaire` operation. The Gateway Lambda validates exact argument shape/size and applies local input/output guardrails because Bedrock PII filtering does not inspect tool arguments or results. Customer-specific operations remain unavailable until a trusted user-to-customer mapping is supplied. The Gateway Lambda handler reads tool names from the documented Lambda client-context field.

These source paths and local/fake tests do not prove that AgentCore resources were deployed or invoked. Runtime `CreateEvent` writes are intentionally not enabled because no approved memory extraction policy exists for raw client messages. KYC authorization also remains unavailable until an authoritative provider contract is supplied; request-body KYC values are ignored.

## Manifest schema

Each agent under `aria/agents/<agent_name>/agent.yaml` contains:

- `name`: the logical agent name
- `version`: the agent version
- `entrypoint`: Python callable path used at runtime
- `system_prompt`: prompt factory path
- `runtime`: execution mode and limits
- `framework`: framework tuning and environment settings
- `allowed_tools`: tool names allowed for that agent
- `unsafe_fields`: explicit disallowed workflow fields

## Local development and release evidence

The framework is intentionally thin. It provides orchestration, context redaction, and state guardrails, but does not hard-code business product logic or enforcement rules in the shared layer.

## Supported assumptions

- Framework support is for sync, async, and stream-style execution patterns.
- Local tests use injected/fake providers and do not call AWS.
- Provider-specific model budgets, memory writes/extraction, and Gateway policy-engine configuration remain release gates until compatibility and sandbox tests are complete.
- Report source implementation, automated tests, fresh CDK synthesis, deployment, and successful AWS invocation as separate evidence states.

## Account statement explainer prototype

The statement explainer is an optional Aria child tool, disabled by default. Operators can opt the existing AgentCore Runtime in with `cdk synth -c statement_explainer_enabled=true`; CDK passes `STATEMENT_EXPLAINER_ENABLED=true` only to that Runtime. The parent supplies the existing model/session configuration and conditionally receives delegation guidance. The child exposes five deterministic operations over the bundled `demo-statement-001` synthetic ledger and resets context between invocations. Unknown statement IDs fail closed. Statement rows are not added to AgentCore Memory or production persistence. This switch does not authorize real customer statement access.

The local reviewer UI is a separate FastAPI demo started with `docker compose up --build`. Compose publishes the service on `127.0.0.1:8000` and the container receives no AWS credential mounts. The current demo executes deterministic tools without invoking Bedrock; optional model/region values are status metadata only. Its SSE stream contains normalized run/tool status, bounded summaries, cited IDs, and a guardrail-checked answer, never arbitrary Strands chunks or private reasoning. In-memory session summaries and audit records are bounded and discarded when the process stops.

The fixture and interface are explicitly non-production. They do not ingest real statements, call CoreBanking, perform authenticated customer-specific lookup, or deploy another AgentCore Runtime. See [the statement explainer quickstart](../specs/003-account-statement-explainer/quickstart.md) for launch and test commands.
