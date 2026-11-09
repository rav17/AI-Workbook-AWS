# Implementation Plan: Account Statement Explainer Subagent

**Branch**: `003-account-statement-explainer` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification in `specs/003-account-statement-explainer/spec.md`

## Summary

Add a statement-specialist Strands subagent to Aria using the pinned `Agent.as_tool` handoff. Route every production statement read through the existing AgentCore Gateway Lambda into encrypted DynamoDB entitlement and transaction tables. Keep deterministic analysis inside the child, identity/session ownership in the existing Aria parent, and Runtime registration as an explicit CDK opt-in disabled by default. Remove the synthetic runtime fixture and local demo; synthetic records remain test-only.

## Technical Context

**Language/Version**: Python 3.11 application and Gateway Lambda; existing AgentCore Runtime remains Python 3.13.

**Primary Dependencies**: Existing `strands-agents==1.34.1`, Bedrock model client, Pydantic, boto3, and the existing AgentCore Gateway MCP client. No new web dependency is required.

**Storage**: DynamoDB entitlement and transaction read models populated by a trusted administrative/source-system process. No statement rows in AgentCore Memory or application logs; no model-callable write path.

**Testing**: pytest, Hypothesis for transaction invariants, fake DynamoDB/Gateway/Strands clients, authorization contract tests, CDK synthesis tests, and deployment-artifact checks.

**Target Platform**: Existing authenticated Aria Runtime, AgentCore Gateway, Gateway Lambda, and DynamoDB.

**Project Type**: Python agent capability with a Gateway-backed DynamoDB read service.

**Performance Goals**: Match spec SC-006: safe `run.started` event within 3 seconds; single-tool completion within 10 seconds; three-tool completion within 20 seconds under configured demo conditions.

**Constraints**: Production reads only through Gateway; verified tenant/user-to-statement entitlement on every request; deterministic Decimal arithmetic; no hidden chain-of-thought, direct CoreBanking integration, write API, new Runtime, or Memory persistence; production child registration disabled by default; source/import process is trusted and out-of-band.

**Scale/Scope**: Two read-only DynamoDB tables, one Gateway Lambda target with bounded read tools, five deterministic analysis operations inside one specialist subagent, and opaque statement references scoped to verified users.

## Constitution Check

**PASS**: Parent Aria retains authority over authentication, tenant/session identity, safety checks, and response handling. The child has only bounded Gateway-backed read tools; Gateway checks the verified principal's entitlement before every DynamoDB query. Statement rows do not enter AgentCore Memory or logs. Production Runtime has no direct DynamoDB permission. Synthetic rows are test-only.

**Re-check after design**: Verify the subagent receives only the active statement selection, stream normalization never forwards arbitrary model chunks, and Compose binds only to localhost.

## Design Decisions

- Build a specialist `Agent` inside the existing Aria agent package and expose it to the parent with `Agent.as_tool`; do not create a second AgentCore Runtime, CDK stack, user identity, or production API.
- The parent owns session continuity. The child resets per invocation and receives the active statement ID plus only a bounded follow-up summary.
- The five statement analysis tools use validated `Decimal` rows returned through Gateway and deterministic computations. The LLM may choose tools and explain results but never calculates authoritative totals or anomaly values.
- The child calls named Gateway operations through a trusted wrapper that injects verified tenant/user identity from the Runtime invocation; identity fields are absent from model-visible child tool schemas.
- DynamoDB contains an entitlement table keyed by a hash of verified tenant/user identity plus opaque statement reference, and a transaction table keyed by statement reference plus ISO date/transaction ID. Gateway checks entitlements before reading transactions.
- Normalize Strands activity to the explicit event contract. Do not forward arbitrary model-generated `data` chunks, private reasoning, raw prompts, or unbounded tool results.
- CDK exposes a strict boolean `statement_explainer_enabled` opt-in, defaults it to false, and passes it to the existing Runtime as `STATEMENT_EXPLAINER_ENABLED`; the flag changes tool registration only, not identity, authorization, IAM data access, or deployment topology.

## Project Structure

### Documentation

```text
specs/003-account-statement-explainer/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/activity-stream.md
├── quickstart.md
├── checklists/requirements.md
└── tasks.md
```

### Source and Tests

```text
aria/agents/aria/statement_explainer/
├── agent.py
├── models.py
└── tools.py
aria/persistence/statement_store.py
aria/api/gateway_handler.py
aria/agents/aria/                 # Parent handoff registration and safe delegation
tests/unit/test_statement_explainer.py
tests/property/test_statement_properties.py
tests/framework/test_statement_subagent.py
tests/unit/test_statement_gateway.py
tests/integration/test_statement_gateway.py
```

**Structure Decision**: Keep specialist orchestration in the agent-specific package, pure calculations in its tool module, and all DynamoDB reads in the Gateway Lambda-backed store. Do not ship local demo code or fixtures in production artifacts.

## Validation Gates

- Exact results for all five tools using fixed fixtures, date/debit-credit boundaries, and Decimal arithmetic.
- Parent handoff tests prove statement intent delegates and unrelated messages do not.
- Gateway contract tests prove statement entitlement enforcement, bounded queries, safe outputs, and denial of cross-user references.
- Statement analysis operates only on rows returned by Gateway and cites source transaction IDs.
- Deployment artifact tests prove demo packages, synthetic fixtures, and optional web dependencies are absent from Lambda/Runtime bundles.
- CDK synthesis proves the production feature flag defaults off and can be explicitly enabled without adding a Runtime or statement-data permissions.
- Existing Aria authentication, KYC, session, Runtime, and unrelated parent-agent tests remain green.

## Risks and Open Decisions

- Statement and entitlement records must be provisioned by a trusted process; this change adds no upload or write API.
- The anomaly threshold and complete-month baseline are prototype assumptions only, not an approved financial risk rule.
- The source requirement asks for a visible reasoning trace; this plan implements a safe observable action/tool trace and explicitly excludes private chain-of-thought.
- Feed ownership, retention duration, and deletion behavior require data-owner and compliance approval before production records are loaded.

## Complexity Tracking

No new Runtime is required. The existing Gateway Lambda and DynamoDB stack are extended with read-only, entitlement-checked statement access.
