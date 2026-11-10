# Research: Production Statement Explainer

**Date**: 2026-10-03
**Scope**: Replace the synthetic local prototype with an Aria-owned child agent that reads authorized DynamoDB statement records exclusively through AgentCore Gateway.

## Decisions

### Parent-to-specialist handoff

- **Decision**: Keep the nested Strands child exposed through `Agent.as_tool(name="account_statement_explainer", preserve_context=False)` inside the existing authenticated Runtime.
- **Rationale**: Aria retains Cognito identity, tenant/session ownership, guardrails, and final response handling. No second Runtime or independent identity system is needed.
- **Boundary**: The child receives verified tenant/user identity in a trusted Python closure. Identity values are not present in model-visible child tool schemas.

### Statement data access

- **Decision**: Route all statement reads through the existing AgentCore Gateway MCP endpoint and its Lambda target. The Gateway Lambda reads DynamoDB; the Runtime role receives no direct DynamoDB permissions.
- **Tools**: `list_authorized_statements` returns only active references mapped to the verified principal. `get_statement_transactions` checks the entitlement again, then returns bounded pages for an opaque statement reference and date range.
- **Rationale**: Gateway is the centralized backend access and authorization boundary. The child remains local orchestration and deterministic analysis, not a Gateway target.
- **Boundary**: Existing Gateway tools remain separately allowlisted for the Aria parent. Statement Gateway tools are called by trusted wrappers inside the child and are not exposed directly to the parent model.

### DynamoDB read model

- **Decision**: Provision `StatementEntitlements` keyed by `principal_scope` and `statement_ref`, and `StatementTransactions` keyed by `statement_ref` and `transaction_key` (`YYYY-MM-DD#TRANS.ID`). Add a statement-scoped transaction-ID index for exact lookup.
- **Identity scope**: `principal_scope` is SHA-256 of the verified tenant ID, a NUL separator, and the verified user subject. Runtime-derived values are injected by code; model/user-provided tenant, user, or account IDs are never trusted.
- **Data provisioning**: A trusted administrative or upstream process writes statement and entitlement items. This feature provides no write/upload API. No rows or entitlements are bundled with the application.
- **Security defaults**: Customer-managed KMS encryption, point-in-time recovery, non-dev retain policies, read-only Gateway Lambda permissions, and no TTL until a bank-approved retention policy exists.

### Deterministic analysis

- **Decision**: Keep period sums, category totals, comparisons, anomaly calculations, and transaction explanations deterministic and Decimal-based. Data is fetched through Gateway in bounded pages; calculations operate only on validated Gateway results.
- **Anomaly rule**: Compare a selected current period with the preceding three complete calendar months. Flag category spend at least 50% above a nonzero baseline monthly average. This threshold is a prototype rule, not a fraud/risk policy.

### Safe operational trace

- **Decision**: Emit only correlation IDs, allowlisted tool names, stable error codes, bounded summaries, and cited IDs. Never emit private reasoning, credentials, raw prompts, or complete statement rows.
- **Rationale**: Production traces should prove which authorized operations ran without becoming a second financial-data store.

## Current Integration Points

- Authenticated request and session mapping: `aria/api/rest_handler.py`, `aria/api/runtime_session.py`, and `aria/agents/aria/agentcore_entrypoint.py`.
- Gateway runtime client: `aria/framework/gateway.py`; existing IAM Gateway and Lambda target: `cdk/stacks/gateway_stack.py` and `aria/api/gateway_handler.py`.
- DynamoDB tables and encryption: `cdk/stacks/stateful_stack.py`.
- Runtime model and tool construction: `aria/agents/aria/agentcore_entrypoint.py` and `aria/agents/aria/statement_explainer/agent.py`.
- Production child registration remains controlled by `statement_explainer_enabled`, default false.

## Risks and Open Boundaries

- The upstream writer and operational process that populates entitlements and statement rows are outside this feature; access remains fail-closed until records are provisioned.
- Entitlement provisioning, retention duration, deletion, and legal-hold requirements require bank data-owner approval.
- AWS deployment and live end-user entitlement tests remain separate from local CDK synthesis and fake-backed tests.
