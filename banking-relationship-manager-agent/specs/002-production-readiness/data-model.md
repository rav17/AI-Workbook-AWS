# Data Model: Production Readiness Remediation

## VerifiedPrincipal

Represents caller identity established by an API Gateway authorizer or trusted AWS principal.

- `subject`: required stable authenticated subject; never sourced from request body.
- `tenant_id`: required tenant claim mapped by explicit configuration; no `default` or `anonymous` fallback.
- `scopes`: verified permissions used for endpoint/tool authorization.
- `issuer`: validated identity-provider issuer.

Validation: reject absent/empty subject or tenant; reject mismatched issuer/audience; normalize tenant/subject before using them in keys/namespaces.

## ConversationState

Authoritative state for one tenant/user conversation.

- `tenant_id`, `user_id`, `conversation_id`: required ownership key components.
- `runtime_session_id`: AgentCore continuity identifier, not the state-store key by itself.
- `revision`: monotonically incremented by conditional update.
- `state`: typed workflow state; no credentials or raw secret-bearing prompts.
- `updated_at`: timezone-aware UTC timestamp.

Relationships: one principal may own multiple conversations; a conversation has one owner and one current revision.

## IdempotencyRecord

- `tenant_id`, `idempotency_key`: composite identity preventing cross-tenant collision.
- `status`, `claim_id`, `lease_until`, optional `expires_at`, `result_reference`: conditional claim ownership, crash recovery, duplicate detection, and owner-approved expiration. Persist only opaque hashes and status metadata; do not store request bodies or responses.

## MemoryRecord

- `tenant_id`, `user_id`, optional `conversation_id`: scope.
- `namespace`: generated from configured tenant/user-safe template.
- `category`: allowlisted durable fact, preference, or summary.
- `content`: redacted content only; must not contain credentials or workflow-authoritative values.
- `expires_at`: owner-approved extracted-record retention boundary; currently unset because no extracted-record expiry mechanism or retention period has been approved.

Validation: read/delete operations always include tenant and authenticated-user scope; listing is bounded and paginated; writes/extraction are denied until an owner approves categories, notice/consent, source-event and extracted-record retention, and erasure semantics. AgentCore's 30-day event expiry applies to source events, not extracted records. Memory may not override current workflow state.

## ReleaseEvidence

- `revision`: source revision/build identifier.
- `python_tests`, `cdk_tests`, `security_scans`, `synthesis`, `artifact_inspection`: separate gate results.
- `deployment`, `invocation`: separately recorded AWS outcomes or `not_run`.

Validation: never infer deployment or invocation success from source, unit tests, or synthesized templates.
