# Implementation Plan: Virtual Account Receivables Exception Resolution Specialist

**Branch**: `004-receivables-exception-resolution` | **Plan refresh**: 2026-11-10 | **Spec**: [spec.md](spec.md)
**Status**: Plan authored for human gate review. The Q1, Q3 and Q5 scope decisions in section 2 are recorded; they do not approve this plan, proposed policy values, fixtures, evaluation labels, construction, or verification commands. No construction, verification command, or measurement has been run or approved.

## 1. Summary

Propose a harness-first bounded receivables specialist for one synthetic customer and one currency, covering three exception categories. This proposal is partial FR-001 conformance only: a synthetic parent harness does not deliver or verify deployable registration within Aria. Matching, variance, eligibility, duplicate and prior-allocation checks, freshness and disposition are **deterministic Decimal code**. Reference matches are candidate inferences, not authoritative identity or facts. The model only narrates structured results. Analyst approve/revise/reject/escalate are **not model-callable tools**; confirmation is a separate application operation. Q5 resolves the storage boundary: isolated synthetic local test/demo persistence for internal proposals, decisions, confirmation/idempotency bindings and audit is permitted, while the create-only synthetic mock case task remains the sole business write. The proposed store architecture and its implementation remain unapproved. No financial, source-record, production or other business-system write is proposed.

Planning evidence is split into three labels used throughout: **[SRC]** read from current code, **[PROP]** proposed here and unapproved, **[ASSUME]** unverified assumption.

## 2. Approval provenance (actual vs proposed)

| Item | Actual human decision on record (`questions.md`) | Proposed in this package (NOT approved) |
|---|---|---|
| Q1 role | Use mock role `receivables_operations_analyst` for synthetic owner-approved mock case-task fixtures only; not production authorization, not a gate approval. | The role is injected by the synthetic harness into `TrustedContext`, never from model, payload, or JWT (section 6). |
| Q2 policy supplier | Human will review and approve the proposed synthetic policy, fixtures and labelled evaluation set at the plan gate. No not-yet-authored policy values or real/production policy are approved. | `synthetic-policy.md` v1 draft values (tolerance, weights, bands, margins, windows, TTLs). Every value is `PENDING_HUMAN_REVIEW`. |
| Q3 mock write | Create-only in isolated test/demo storage; idempotent retries. Approves mock-write scope only, not unreviewed fixture contents, construction commands, production permissions or financial writes. | Local SQLite store design (section 7), `synthetic-fixtures.json`, payload and key definitions. |
| Q4 labels | Human will review and approve the evaluation set and labels at the plan gate; denominators and proposed test commands remain subject to review; none approved or measured. | 57-case catalogue (52 scored + 5 scope guards), labels, fixed denominators (section 8), commands in `quickstart.md`. |
| Q5 persistence boundary | Permit isolated synthetic local test/demo persistence only for internal proposals, analyst decisions, confirmation/idempotency bindings and audit. The create-only mock case task is the sole business write; no financial, source-record or production changes. This is not plan or implementation approval. | Proposed local store design, schema, transaction details and implementation remain unapproved. |

No performance has been measured. SC-001..SC-004 stay *targets*.

## 3. Source evidence ([SRC], read-only; paths relative to repo root `banking-relationship-manager-agent`)

| Finding | Evidence |
|---|---|
| Strands `Agent.as_tool(*, name, description, preserve_context=False)` returns `_AgentAsTool`. | `.venv311/Lib/site-packages/strands/agent/agent.py:637-669` |
| The tool schema is a single `input: string`; the wrapped agent is run with that string. Structured JSON handoffs are impossible at the tool boundary. | `strands/agent/_agent_as_tool.py` `tool_spec` and `stream` (lines ~28-215) |
| `preserve_context=False` is rejected (`ValueError`) if the child has a session manager; state is reset to construction state each call; concurrent call returns an error result via a non-blocking lock. | same file, `__init__`/`stream` |
| `Model` is abstract: `update_config`, `get_config`, `structured_output`, `stream`. A scripted model is feasible; event format not verified. | `strands/models/model.py:38-110` |
| Existing child pattern binds verified identity in a closure; model cannot choose identity. | `aria/agents/aria/statement_explainer/agent.py` (`build_statement_explainer_tool`, tenant_id/user_id closure, `as_tool(preserve_context=False)`); `aria/agents/aria/kyc_aml/agent.py:19-56` |
| Parent construction injects the tool in `_build_strands_agent` behind env flag `STATEMENT_EXPLAINER_ENABLED`; session id sanitized from tenant:user:session. | `aria/agents/aria/agentcore_entrypoint.py` (function `_build_strands_agent`) |
| `run_runtime_invocation` applies guardrails to input and output; `agent_factory` and `identity_resolver` are injectable. | same file, `run_runtime_invocation` |
| `resolve_runtime_identity` accepts a payload `_verified_principal` dict or verifies a Cognito JWT (RS256, issuer, audience, tenant claim). Payload-supplied principal provenance is upstream, unverified here. | `agentcore_entrypoint.py:30-80` |
| Memory client rejects a tenant that differs from the authenticated tenant. | `aria/framework/agentcore.py:39-41` |
| Gateway handler allowlists tools/keys and strips identity keys from guardrail input, but identity values arrive in the event. | `aria/api/gateway_handler.py:20-30,86-125` |
| `AriaAgent` takes injected specialist callables. | `aria/agent.py:28-58` |
| Prior-art test fakes `Agent`/`tool` via monkeypatch; this does **not** exercise real `_AgentAsTool`. | `tests/framework/test_statement_subagent.py:222-300` |
| Tooling config: pytest `testpaths=["tests"]`, `pythonpath=["."]`; ruff line 100 `E,F,I,UP`; mypy `strict`; hypothesis and `strands-agents==1.34.1` pinned. | `pyproject.toml` (lines ~7-56) |
| No receivables code exists in `aria/`. | glob of `aria/**/*.py` |

**Limitations/stale**: no `codebase.md`; graph not queried structurally; prior plan/research/contract text predating the clarify session was stale (de-identified data allowed, "created/updated" task, `Agent.as_tool` structured handoff, mutable task wording) and is replaced. `tasks.md` is stale and untouched. The source/SDK entries above are read-only planning observations; feature-specific integration seams and their contracts remain planned, not delivered or verified.

## 4. Technical Context

- **Language**: Python 3.11 (mypy `python_version`), Pydantic v2 at boundaries, `Decimal` for money, UTC timezone-aware timestamps. Existing Runtime Python 3.13 untouched.
- **Dependencies**: existing only (`strands-agents==1.34.1`, pydantic, pytest, hypothesis; stdlib `sqlite3`, `hashlib`, `json`). No new dependency, no boto3 use, no network. **[SRC: AWS support]** no CDK/AgentCore/cloud change required.
- **Storage [Q5 scope approved; design/implementation proposed]**: Q5 permits isolated synthetic local test/demo persistence for internal workflow state, with the create-only mock case task as the sole business write. The proposed design uses one local SQLite store under a temp or demo directory, separate from fixtures and with audit in the same transaction. Its schema, transaction details, location and implementation remain unapproved and require the relevant human approvals. Parent persistence (`aria/persistence/*`) remains untouched.
- **Testing**: pytest + Hypothesis; model-free fakes; scripted `Model` for the real `as_tool` path.
- **Target proposal**: harness-first local demo/test; this is partial FR-001 conformance only. Actual deployable Aria Runtime registration is not delivered or verified; it needs separate approval and evidence.
- **Performance**: no target invented; harness records latencies without asserting a number.
- **Scale**: 1 customer, 1 currency (USD), 3 categories, 57 catalogue cases.

## 5. Architecture decisions (rationale and rejected alternatives in `research.md`)

- **D-INT-1 Integration shape [PROPOSAL; pending human scope decision]**: propose `build_receivables_subagent_tool(model, trusted_context, ports, services)` returning `Agent(...).as_tool(name="receivables_exception_investigator", preserve_context=False)`, with a synthetic parent harness. This harness-first proposal is partial FR-001 conformance only; it does not deliver or verify a deployable specialist within Aria. Runtime registration and its trusted-provider seam are not delivered or verified and require separate approval and evidence. At the plan gate, ask the human to accept this staged limitation or request different scope. No auth, session, or KYC edits are proposed.
- **D-INT-2 Handoff**: the tool's only model input is the SDK `input` string. The child's closure tools take only an opaque `exception_id` matching `^EXC-SYN-[A-Z0-9]{3,8}$`. `tenant_id`, `user_id`, `session_id`, `analyst_id`, role, customer scope, currency and policy are **never** parameters visible to the model.
- **D-INT-3 Authoritative output is not model text**: `_AgentAsTool` returns the child's text. The authoritative proposal is persisted by deterministic code and read by `proposal_id` from the store by the harness/analyst UI. The draft operations note is a deterministic template over structured fields (no raw payer/remittance text).
- **D-AUTH Trusted context**: frozen `TrustedContext` is created only from a separately trusted server-side provider or an explicit synthetic harness. A payload `_verified_principal` field, by itself, is not proof of trusted provenance. Context is injected by closure/dependency and rechecked at adapters and writer. The agent-as-tool is **not** a security boundary (Constitution II). No Runtime provider wiring is included; without an approved trusted source, the operation must refuse context-dependent work.
- **D-WRITE Decision/confirmation/case writer**: analyst approve/revise/reject/escalate and confirmation are separate application operations, never Strands tools. Confirmation is not an analyst decision enum value. A server-issued opaque `confirmation_id` is created and persisted with the approval binding; neither the model nor analyst selects or derives it.
- **D-STORE [PROPOSED; within Q5 scope, not implementation approval]**: propose one SQLite file and `BEGIN IMMEDIATE` transactions. The immutable confirmation binding has a scoped unique constraint on `(tenant_id, session_id, confirmation_id)` and is bound at approval to exception, proposal/version, decision revision, canonical payload hash and trusted context. Enforce one binding per approval; make `case_tasks.confirmation_id` unique; abort task `UPDATE`/`DELETE`; write the audit event in the same transaction as each persistent state change. Q5 permits the isolated synthetic local persistence scope; this specific design and its implementation remain subject to human plan approval.
- **D-A (Q5) — RESOLVED STORAGE-SCOPE DECISION**: The human permits isolated synthetic local test/demo persistence of proposals, analyst decisions, confirmation/idempotency bindings and audit. The create-only synthetic mock case task remains the sole business write; financial, source-record, production and other business-system changes are not permitted. This resolves the FR-014 boundary only; it does not approve the proposed SQLite architecture, schema, transaction details, implementation, plan, policy values, fixtures, evaluation labels or commands. Those remain subject to their respective human approvals.

### Component view (text)

```
Analyst UI / harness ──> TrustedContext(factory) ──┐
   │                                               ▼
   │ (not model tools)             Parent Strands Agent ── as_tool ──> Receivables child Agent
   │  decide/confirm                                                         │ closure tools (exception_id only)
   ▼                                                                         ▼
AnalystDecisionService ──┐                      InvestigationEngine (rules.py, policy.py: Decimal, pure)
                          ▼                                  │ read-only ports (fixtures, immutable)
                    SQLite store  <── ProposalStore         PaymentPort VAPort CustomerPort InvoicePort
                    (decisions, tasks[create-only],          PaymentHistoryPort AllocationPort PolicyPort
                     audit, same txn)
```

Draw.io diagrams and a diagram register (speckit-diagrams) are **not produced**: the host is read-only and the delegated scope excluded them. Deferred explicitly, not omitted by oversight.

## 6. Trusted-context and fail-closed policy

1. `TrustedContext` may be constructed only from a separately trusted server-side provider or an explicit synthetic harness. A payload field named `_verified_principal` is not proof of provenance. Context is immutable, never model-visible, and rechecked against record/policy tenant and proposal session at each port, service and writer. A missing or mismatched trusted context fails closed.
2. In the proposed synthetic harness only, `analyst_role` is the fixed `receivables_operations_analyst` value. It is not read from a Runtime payload, JWT, `_verified_principal`, memory or model. Production role mapping and Runtime registration are out of scope. No trusted-provider integration is implemented or assumed by this plan; without that provider, no Runtime operation is authorized.
3. Existing payload `_verified_principal` provenance is upstream-unverified [SRC]. This feature does not treat that payload value as a trusted source, does not change auth/session/KYC handling, and does not claim an authenticated Runtime path.
4. Fail closed (no confident allocation, escalate) for unknown, unavailable, partial, conflicting, stale or malformed required evidence; suspected/confirmed duplicate or prior allocation; and missing, unapproved, expired, mismatched, cross-tenant or inapplicable policy. Partial evidence never supports an assertion based on the missing portion. For partial evidence, disclose the affected source and safe next step: refresh or complete that source, rerun, and route for human review if still incomplete.
5. Existing parent guardrails remain unchanged. Payer/remittance/narrative are untrusted data, never instructions. Audit excludes raw narrative, payer/remittance text, prompts, credentials and hidden reasoning.

## 7. Atomic confirmation, retry identity and replay design [PROP; within Q5-approved storage scope, implementation not approved]

- `payload_hash = SHA-256(canonical JSON)` (sorted keys, UTF-8, Decimal as a 2dp string) of the immutable case-task payload. It is a binding value, not a retry identity.
- At approval, trusted server-side code issues an opaque, stable `confirmation_id` for that approval. It is distinct from payload, proposal version and their hashes; neither model nor caller chooses or derives it. A revised proposal that is approved gets a new `confirmation_id`.
- In the same proposed approval transaction, bind the ID to tenant, session, exception, proposal ID/version, decision revision, canonical payload hash and trusted context. Enforce unique `(tenant_id, session_id, confirmation_id)` and one binding per approval; a case task references its `confirmation_id` uniquely. Q5 permits this isolated synthetic local persistence scope, but does not approve these binding/transaction details or their implementation.
- `confirm(context, confirmation_id, proposal_id, proposal_version, payload_hash)` first resolves the stored binding under the trusted tenant/session. A changed exception, proposal/version, payload hash, decision revision or context under the same scoped ID returns `conflict` without mutation. Cross-tenant/session access fails closed as unauthorized. The supplied values are checked against the server-side binding; they do not establish it.
- In one `BEGIN IMMEDIATE` confirmation transaction: (1) compare the supplied/derived binding with the immutable approval binding; (2) if an exact matching task is already committed, return that task as `replayed` before checking later decision state, preserving an identical retry after a subsequent stale/revise/reject/escalate decision; (3) otherwise verify current proposal/version, approval state and revision, proposal TTL, confirmation window, policy effectiveness and re-evaluated evidence freshness; failure returns `stale_confirmation` without a task; (4) insert task and confirmation/audit event, advance state to `task_created`, and commit. Audit or DB failure rolls back and is never reported as success.
- `revise|reject|escalate` are analyst decisions and bump decision revision under the same lock. Decision first means confirmation is stale; task first means a later decision is recorded without altering the immutable task. Confirmation is a distinct persisted event with its ID and binding, not a decision action and does not itself increment decision revision.
- An uncertain commit is `unconfirmed` until lookup by the same scoped confirmation ID proves committed or absent. No content/version-derived key is used as the retry identity.
- **Test limitation**: a SQLite file can demonstrate only local transaction/constraint behavior. Fakes do not prove atomicity; no result proves cloud behavior. These are proposed persistence claims, not verified implementation behavior; construction and tests require their separate human approvals.

## 8. Evaluation design summary (details: `synthetic-policy.md`, `synthetic-fixtures.json`)

Fixed denominators come from the catalogue, not from runtime output. Abstention, no-candidate and error stay in denominators as incorrect; zero denominator = **N/A, not pass**; per-stratum counts always reported.

| Metric (target) | Denominator (fixed, proposed) | Numerator | Per-stratum |
|---|---|---|---|
| SC-001 classification (>=90%) | 50 catalogue cases have `classification_scored=true`; 2 (`S03`,`S07`) are explicitly unscored by the proposed fixture labels and reported separately. All labels remain proposed, not owner-approved. | system class == expected class | S1 13, S2 7, S3 5, S4 4, S5 6, S6 3, S7 7, S8 5; scored expected classes: invalid_mapping 8, suspected_duplicate 5, amount_reference_mismatch 37 |
| SC-002 top candidate (>=85%) | 13 allocatable cases (stratum S1) | top-ranked eligible candidate in acceptable ids | S1 only |
| SC-003 confident precision (>=95%) | all system outputs presenting `recommend` (expected 13 if perfect; not claimed) | recommend with correct candidate and no eligibility/dup/prior violation | by catalogue stratum of the case; also report confident outputs on 39 non-allocatable cases separately |
| SC-003 incorrect-allocation rate | all allocation recommendations (confident or not) | incorrect ones | same; abstain/no-candidate/error counts shown |
| SC-004 escalation (>=90%) | 36 escalation-required cases (S2 7, S3 5, S4 4, S5 6, S7 9, S8 5) | explicit escalate and no confident allocation | by stratum; false escalations over 16 not-required cases (S1 13, S6 3) reported separately |
| SC-005 evidence/variance (100%) | every `recommend` output | required evidence types present; variance recomputes identically | N/A if zero recommendations |
| SC-006 prohibited writes (zero) | all instrumented calls on every implemented planned source and writer surface reached by both E and W; report surface/call coverage. Also compare immutable fixture-file hashes before/after and assert DB immutability/allowed create-only task behavior if the proposed local DB design is separately approved and implemented. | prohibited writes observed | N/A is not a pass: if no relevant path is exercised, a planned surface is absent, or any surface is uninstrumented, report unmeasured/coverage gap, not global zero. Scope is only the implemented paths actually observed; no cloud/network or absent-surface claim. |
| SC-007 trace (100%) | all retrievals, proposals, decisions, confirmation bindings/events and task writes emitted in runs E and W | those with corresponding audit rows | by event type and surface coverage |

Run E = 57 catalogue cases, investigation only (no analyst). Run W = 14 workflow scenarios (approve/confirm/race/replay/binding conflict/failure). Guard cases (5) are excluded from SC-001..004 and reported as `out_of_scope` counts with a zero-port-call assertion. The catalogue remains 57 total = 52 scored + 5 guards; SC-001 remains 50 scored + 2 unscored. Partial-evidence behavior reuses S04; no case is added.

## 9. Constitution Check

| Principle | Result | Notes |
|---|---|---|
| I State authority | PROPOSED / NOT VERIFIED | Q5 permits isolated synthetic local persistence within the stated boundary. The proposed typed state, store design, transactions and audit behavior are not implemented or verified, and this decision does not approve them. |
| II Deterministic safety | PROPOSED / NOT VERIFIED | The proposed design calls for deterministic rules and trusted-context checks at adapters and the writer; no receivables implementation exists, so enforcement is neither implemented nor verified. Agent-as-tool is not a security boundary; the inherited `_verified_principal` limitation is recorded. |
| III Patch/validate/invalidate | PROPOSED / NOT VERIFIED | The design says `revise` re-runs all checks, creates a new proposal version, and invalidates prior approval/confirmation; no implementation or validation exists. |
| IV Bounded context | CONDITIONAL / NOT YET VERIFIED | Read-only inspection of the existing SDK informs the proposed compact handoff and concurrent-call behavior; feature-specific `exception_id` closure, no-history configuration, and tool integration remain planned and unverified. Existing SDK evidence does not establish bounded invocation lifetime, call budgets, deadlines, or cancellation. Proposed synthetic-only gate budget, unapproved: at most 7 source reads per invocation (one each for payment, virtual account, customer, invoice search, payment history, allocation ledger, and policy); invoice search returns at most 20 candidates, history and ledger at most 20 rows each, and deterministic evaluation processes at most 20 candidates. Target at most 4 child model/tool turns and one active `as_tool` invocation; overlapping calls fail as unavailable. Propose a 30-second monotonic caller deadline and cooperative cancellation/deadline propagation through the deterministic engine and adapters, checked between reads/records and before persistence/commit; after a signal/deadline, schedule no further source calls or writes and roll back a transaction if cancellation is observed before commit. These are architecture budgets, not asserted Strands limit setters. The caller deadline cannot guarantee interruption of a blocked synchronous call or transaction, safe thread termination, or bounded SDK completion. Future model-free fake-clock/call-recorder tests should measure/enforce call, candidate and turn caps, overlap refusal, deadline/cancellation stop points, and no subsequent writes; no tests have run, and these tests would not prove interruption of blocked work. |
| V Durable boundaries | PROPOSED / NOT VERIFIED | The design excludes AgentCore Memory and proposes session isolation by key scope; neither persistence nor isolation behavior is implemented or verified. |
| VI Python quality | PROPOSED / NOT VERIFIED | The plan proposes Pydantic boundaries, Decimal, UTC time, a fake clock and structured audit with redaction. No implementation or checks exist; dependency/security checks and CI-scale gates are not claimed here. |
| Security/Compliance | PROPOSED / NOT VERIFIED | The design is synthetic-only and proposes excluding secrets/real data and redacting credential-like narrative text from audit (case L05); no enforcement is implemented or verified. |

Post-design re-check: Q5 resolves the storage boundary in favor of isolated synthetic local persistence for the stated internal workflow records, with the create-only mock task as the sole business write. It does not approve the proposed storage architecture, implementation or Constitution I enforcement; these remain proposals, unimplemented and unverified. No learned rule or gate is approved here.

**Human decisions still pending**: Q5 has resolved the storage boundary, but the proposed SQLite architecture and implementation remain unapproved. D-INT-1 is a scope proposal, not an approved decision: the plan gate asks the human to accept the harness-first partial FR-001 limitation or request different scope. Actual deployable Aria Runtime registration is not delivered or verified and requires separate approval and evidence. D-B (the residual `amount_reference_mismatch` class is a weak discriminator, making its SC-001 result easy) remains for human review. All policy windows, TTLs and other `PENDING_HUMAN_REVIEW` values remain proposals, not approvals.

## 10. Project structure (proposed, construction later)

```text
specs/004-receivables-exception-resolution/   (this package)
aria/agents/aria/receivables/
  __init__.py  models.py  trusted_context.py  ports.py  policy.py  rules.py
  engine.py  freshness.py  metrics.py  agent.py
demo/receivables_exception/
  __init__.py  store.py  service.py  adapters.py  fixtures/ (copied after approval)
tests/unit/test_receivables_rules.py  test_receivables_fixtures.py  test_receivables_metrics.py
           test_receivables_store.py  test_receivables_trusted_context.py
tests/framework/test_receivables_subagent.py  test_receivables_agent_as_tool.py
tests/property/test_receivables_properties.py
```

Existing files are not modified. Verification commands are in `quickstart.md`; they have not been run and are not approved.

## 11. Risks

1. Labels derived from the same proposed rules can be tautological; independent human label review at the gate is essential.
2. Scripted-`Model` event format is unverified; construction must read `strands/models/model.py` and event types before relying on it. Fallback is the existing FakeAgent pattern plus direct `_AgentAsTool.stream` calls.
3. TOCTOU window between evidence re-check and commit in the local store is acknowledged; prior-allocation data is read-only synthetic so races are only simulated via hooks.
4. Windows file locking/SQLite behaviour is not verified.
5. SC-006 cannot support a global claim from a fake observing no writes. Instrument every implemented planned source and writer surface in both evaluation and workflow/demo paths; report coverage, immutable fixture hashes and DB assertions. A missing or unexercised surface is unmeasured, not a passing zero. Results are limited to observed implemented paths; no cloud/network or absent-surface claim.
