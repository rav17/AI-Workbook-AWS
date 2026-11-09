# Data Model: Gateway-Backed Statement Explainer

## StatementTransaction

One validated transaction row returned by the authorized Gateway backend.

- `trans_id`: non-empty unique identifier within a dataset.
- `value_date`: ISO calendar date; rows sort by value date then transaction ID.
- `amount`: finite, non-negative `Decimal`; debit/credit direction is stored separately.
- `dr_cr_ind`: exactly `D` or `C` after input normalization.
- `narrative`: bounded plain text; sanitized before model context or audit.
- `category`: allowlisted value from the dataset taxonomy or `uncategorized`.
- `balance_after`: finite `Decimal` representing the balance after this row.
- `currency`: one configured currency code for the dataset.

Validation: reject invalid dates, invalid indicators, non-finite amounts, unsupported currencies/categories, and malformed row keys. Never use binary floating-point for money calculations. Duplicate transaction IDs within one statement are rejected by the backend write process.

## StatementEntitlement

One trusted assignment from a verified Aria principal to a statement the principal may access.

- `principal_scope`: SHA-256 of the verified tenant ID and user subject separated by a NUL byte; DynamoDB partition key.
- `statement_ref`: opaque, high-entropy statement reference; DynamoDB sort key.
- `access_status`: `ACTIVE` or `REVOKED`.
- `display_label`: masked, non-sensitive statement/account label suitable for specialist context.
- `period_start`, `period_end`: ISO dates bounding the statement.
- `currency`: ISO currency code.
- `opening_balance`: optional finite Decimal starting balance.

Authorization invariant: an active item must exist for the verified principal scope and requested statement reference before any transaction query. Unknown and revoked references return the same generic not-found response.

## StatementRecord

One DynamoDB item in the statement transaction table.

- Partition key: `statement_ref`.
- Sort key: `transaction_key`, formatted as `{VALUE.DATE}#{TRANS.ID}` for date-ordered range queries.
- Source fields: `trans_id`, `value_date`, `amount`, `dr_cr_ind`, `narrative`, `category`, `balance_after`, and `currency`.
- Optional GSI key: `statement_transaction_id` formatted as `{statement_ref}#{trans_id}` for unique transaction lookup.

Writes are performed only by a trusted data-provisioning process. The Runtime role and Gateway Lambda receive read-only permissions. No API in this feature creates or modifies statement records or entitlements.

## StatementAnalysisRequest

A specialist invocation scoped to the authenticated Runtime principal and an opaque statement reference.

- `statement_ref`: optional opaque reference chosen from the child-only `list_authorized_statements` result; Gateway rechecks its entitlement on every call.
- `question`: non-empty, guardrail-processed user question.
- `session_context`: optional bounded parent summary for follow-up references; no raw conversation transcript.

Validation: tenant/user identity is bound in the trusted tool wrapper and never appears in the model-visible tool schema. The child cannot broaden the backend authorization scope.

## StatementToolResult

A deterministic result returned to the specialist agent.

- `operation`: one of the five allowlisted analysis tool names.
- `summary`: bounded plain-text result for model reasoning.
- `metrics`: typed totals, averages, deltas, and anomaly baseline values as applicable.
- `transaction_ids`: only rows supporting the answer.
- `source_rows`: optional bounded rows, used internally by `explain_transaction` only.

Validation: all numeric metrics are computed from selected rows; result size is bounded; errors are typed and do not silently return success-shaped empty results.

## AgentActivityEvent

A safe, ordered internal activity/audit event.

- `run_id`: unique per parent request.
- `sequence`: strictly increasing event number.
- `event_type`: `run.started`, `agent.handoff`, `tool.started`, `tool.completed`, `tool.failed`, `answer.completed`, or `run.failed`.
- `tool_name`: allowlisted tool name where relevant.
- `summary`: sanitized bounded event detail.
- `transaction_ids`: cited IDs only; no full statement payload.

Validation: never include private chain-of-thought, raw prompts, credentials, unfiltered model chunks, or full statement rows.

## StatementExplainerSession

Conversation context bound to one Aria parent Runtime session.

- `session_id`: local opaque session identifier.
- `statement_ref`: selected opaque authorized statement reference.
- `conversation_context`: bounded Aria parent context needed for follow-ups.

Validation: no identity substitution; every Gateway operation revalidates entitlement; statement data is not written to AgentCore Memory.

## StatementAuditRecord

Safe audit summary for one request.

- `run_id`, `session_id`, `statement_ref`.
- `sanitized_question`.
- `tool_sequence`: ordered allowlisted tool names and bounded sanitized summaries.
- `final_status`, `final_response`, `cited_transaction_ids`.

Retention: use the existing protected application audit/log policy. Store no raw statement rows, credentials, or hidden reasoning; retention duration must follow the approved bank policy.
