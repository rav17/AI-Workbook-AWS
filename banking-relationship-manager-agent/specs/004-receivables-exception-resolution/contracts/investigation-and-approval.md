# Contract: Receivables Investigation, Analyst Decision and Mock Case Task

**Status**: Plan-gate proposal for human review. Not an approved policy, fixture, implementation or production-permission contract. Supersedes the pre-plan draft (structured handoff removed because `Agent.as_tool` exposes only one `input` string; see `research.md` R1).

## C1. Parent -> specialist tool (SDK-defined schema)
Tool name `receivables_exception_investigator`, built by `Agent(...).as_tool(name=..., description=..., preserve_context=False)`.
```json
{"input": "string - free text from the parent model, e.g. 'Investigate EXC-SYN-A02'"}
```
- The model-supplied text is untrusted. It cannot carry tenant, user, session, analyst, role, customer scope, currency, policy or approval.
- Context reaches the closure only from a separately trusted server-side provider or an explicit synthetic harness. A payload `_verified_principal` field by itself is not proof. No Runtime provider wiring is included; without a trusted source the operation refuses to proceed. Parent retains final response and guardrails.
- Child must be built without a session manager (SDK raises `ValueError` otherwise). Concurrent calls return an SDK error result; treat as unavailable.

## C2. Child closure tools (model-visible; read-only deterministic)
| Tool | Args | Behaviour |
|---|---|---|
| `investigate_exception` | `exception_id: str` matching `^EXC-SYN-[A-Z0-9]{3,8}$` | Reads synthetic ports via TrustedContext, runs deterministic engine, returns a compact structured result. Q5 permits isolated synthetic local persistence within the stated boundary; proposal persistence and this design remain unapproved proposals, not construction authorization. |
| `get_proposal_status` | `exception_id` | Returns the current stored proposal summary and state (read-only). |
No other tools. There is no approve, confirm, decide, write, ledger, account, virtual-account, payment-repair or master-data tool.

## C3. Investigation result (stored, authoritative; model text is not)
**Illustrative abbreviated fragment only?not an executable result, a valid `recommend` payload, or a success claim.** It omits the required seven evidence types and per-citation snapshot/version references with matching digest, so it does not satisfy SC-005. The `reference_match` entry is inference, not authoritative evidence.
```json
{
 "proposal_id": "PROP-SYN-A02-1", "exception_id": "EXC-SYN-A02", "version": 1,
 "outcome": "recommend | no_recommendation | escalate | out_of_scope",
 "classification": "invalid_mapping | amount_reference_mismatch | suspected_duplicate | null",
 "primary_reason": "NONE | <reason code>", "secondary_reasons": [],
 "proposed_invoice_id": "INV-SYN-1002",
 "variance": {"payment_amount":"12450.00","expected_amount":"12500.00","variance_amount":"-50.00","currency":"USD"},
 "policy": {"policy_id":"POLICY-SYN-RX-V1","version":"1.0.0-draft","approval_status":"approved_synthetic_test_only"},
 "evidence": [{"evidence_id":"EV-1","source_type":"payment","source_record_id":"PAY-SYN-A02","as_of":"2026-03-16T10:30:00Z","freshness":"fresh","availability":"available","evidence_kind":"reference_match","kind":"inference"}],
 "source_snapshot_digest": "<sha256>", "expires_at": "2026-03-16T12:30:00Z",
 "draft_operations_note": "deterministic template text", "safe_next_step": null,
 "requires_analyst_decision": true
}
```
- `proposed_invoice_id` and variance appear **only** for `recommend`. Other outcomes omit them, explain the limitation, disclose availability/freshness, and give a safe next step. `availability` includes `partial`; partial required evidence never supports a recommendation and fails closed as `EVIDENCE_PARTIAL`. For partial evidence, `safe_next_step` tells the operator to refresh/complete the named source, rerun, and route for human review if still incomplete. Approval is unavailable for non-recommend outcomes.
- `recommend` requires evidence of types payment, virtual_account, customer, invoice, payment_history, allocation_ledger, policy.
- A reference match is explicitly `evidence_kind: reference_match` and `kind: inference`; a payer-name match is also `kind: inference`. Neither is authoritative identity/fact, establishes eligibility, or repairs mapping.

## C4. Analyst decision service (NOT model-callable)
`decide(context, proposal_id, proposal_version, decision, rationale, revision?)` with `decision` in `approve|revise|reject|escalate`. Confirmation is a separate operation and is not a decision enum value.
- `analyst_id`/role from `TrustedContext` only; role must equal `receivables_operations_analyst` (synthetic). Caller-supplied identity fields are ignored/rejected.
- `approve` requires outcome `recommend`, current proposal version and unexpired proposal. The proposed design has server-side code issue an opaque `confirmation_id` and atomically bind it to tenant/session/exception, proposal/version, decision revision, canonical payload hash and trusted context with the approval state/event. It is not supplied or selected by model/caller. Q5 permits this isolated synthetic local persistence scope, but does not approve these design details or their implementation; no case task is created by approval.
- `revise` re-runs all deterministic checks, creates a new proposal version and invalidates the prior approval. A later approval gets a new confirmation ID; the old ID can never be rebound. `reject`/`escalate` are decisions, not confirmation actions.

## C5. Confirmation and case-task writer (NOT model-callable)
`confirm(context, confirmation_id, proposal_id, proposal_version, decision_revision, payload_hash)` -> proposed `BEGIN IMMEDIATE` transaction as in `plan.md` section 7 (Q5 permits the isolated synthetic local persistence scope; this design and its implementation remain unapproved):
1. Resolve the server-issued identity within trusted tenant/session and compare all supplied/derived fields with its immutable approval binding. Changed exception, proposal/version, revision, payload hash or same-scope context under that ID -> `conflict`, no mutation; cross-scope access fails closed as `unauthorized`.
2. If an exact matching task is already committed, return it as `replayed` before checking current decision state, even after a later stale/revise/reject/escalate decision. The same committed retry keeps the same ID and binding. A revised approval has a distinct server-issued ID.
3. Otherwise validate current version, decision revision/state, TTLs, policy effectiveness and evidence freshness; failure -> `stale_confirmation`, no task.
4. Insert task, confirmation/audit event and state atomically; commit. Audit/DB failure -> rollback and `unconfirmed`/error, never success. Confirmation is a distinct persisted event, not an AnalystDecision.
Results: `created | replayed | stale_confirmation | conflict | unauthorized | unconfirmed | error`. `unconfirmed` is distinct from a verified `not_created`.
- Race semantics: decision first -> confirmation `stale_confirmation`; task first -> later decision recorded, task untouched (DB trigger immutability).
- The writer has no update/delete/upsert method and no ledger/account/payment/virtual-account/master-data method.

## C6. Mock case-task payload (immutable)
Fields listed in `data-model.md`. `payload_hash` is the canonical payload binding, not a retry identity. The server-issued `confirmation_id` is stable across retries and distinct from payload/version hashes; the scoped immutable binding and unique constraints are described in `plan.md` section 7. The model never supplies or chooses the ID.

## C7. Audit contract
Every retrieval, deterministic check summary, proposal version, decision, confirmation, replay, rejection and task result emits a correlated event (`sequence`, `actor`, `source_refs`, `policy_version`, `reason_codes`, safe summary). Raw prompts, credentials, hidden reasoning and raw payer/remittance/narrative text are excluded. Audit write failure means the surrounding operation is not reported successful.

## C8. Contract tests required (construction)
Tool schema is exactly `{input}`; closure tools take only `exception_id`; no tenant/user/session/analyst/role/confirmation-ID field in any model-visible schema; model-callable tool set excludes decide/confirm; trusted context is accepted only from a separately trusted provider or explicit synthetic harness, never from payload `_verified_principal` alone. Tests cover server-issued stable retry identity, exact replay after later stale state, changed binding conflict, new identity after revised approval, cross-tenant/session isolation, partial-evidence fail-closed disclosure, and confirmation as a separate audit/state event. Assert write/ledger method absence by introspection.
