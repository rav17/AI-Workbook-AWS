# Contract: Statement Explainer Gateway Access

## Parent-to-child handoff

The authenticated Aria parent exposes one child tool named `account_statement_explainer` using `Agent.as_tool(..., preserve_context=False)`. The child receives a guardrail-processed question and bounded follow-up context. The parent does not accept `tenant_id`, `user_id`, `account_id`, or `statement_ref` as trusted identity from the user prompt.

The Runtime builder binds the verified tenant and user from `_verified_principal` to private child-tool closures. These values do not appear in model-visible tool schemas. The child may call only the statement Gateway tools listed below; the parent receives only the existing Gateway allowlist plus the child handoff.

## Gateway MCP tools

Gateway target: `aria-statements` using the existing `AWS_IAM`-authorized Gateway and Gateway Lambda execution path.

`list_authorized_statements` accepts the trusted `tenant_id` and `user_id` injected by the Runtime wrapper. It returns at most 25 active statement references assigned to that principal, with masked display labels, currency, and period bounds. It returns no transaction rows.

`get_statement_transactions` accepts the trusted `tenant_id` and `user_id` injected by the Runtime wrapper plus an opaque `statement_ref`, optional inclusive ISO date bounds, an optional paging token, and a page size from 1 through 100. The Gateway verifies an active entitlement before querying DynamoDB. It returns validated source rows, at most 100 per call, and an optional continuation key containing only the last sort key.

The child may expose higher-level local tools such as transaction search, period summary, spend categorization, anomaly analysis, and transaction explanation. Those wrappers invoke only the Gateway MCP tools for data; they may perform bounded Decimal calculations on the authorized rows returned. The Gateway MCP tools themselves are not added to the parent tool list.

## DynamoDB access contract

`StatementEntitlements` is keyed by `principal_scope` (SHA-256 of verified tenant ID, NUL, verified user subject) and `statement_ref`. An item is usable only when `access_status` is `ACTIVE`.

`StatementTransactions` is keyed by `statement_ref` and `transaction_key`, where `transaction_key` is `{value_date}#{trans_id}`. Items contain the validated transaction source fields from `data-model.md`. A secondary index supports a unique transaction lookup scoped to a statement reference.

The Gateway Lambda has read-only `GetItem`/`Query` access. The AgentCore Runtime role has Gateway invocation permission only and no DynamoDB permissions. No Gateway or Runtime tool can write statements or entitlements. Trusted provisioning is out-of-band.

## Failure behavior

Missing, revoked, malformed, or unassigned statement references return a generic not-found/denied result and do not query transaction rows. Malformed rows, oversized results, DynamoDB errors, and Gateway errors produce stable safe failures. Tool summaries and final answers contain only bounded aggregates and cited transaction IDs; raw rows are not written to logs or AgentCore Memory.