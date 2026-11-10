# Research: Receivables Exception Resolution Specialist

**Date**: 2026-11-10 (refresh). Labels: **[SRC]** read from code, **[PROP]** proposed, **[ASSUME]** unverified. No commands were executed. All unknowns are either resolved below or listed as human decisions in `plan.md` section 9.

## R1. Agent-as-tool API and handoff [SRC]
- **Decision**: build the child with `strands.Agent(model=..., name=..., system_prompt=..., tools=[closure tools])` and expose with `child.as_tool(name="receivables_exception_investigator", description=..., preserve_context=False)`.
- **Evidence**: `Agent.as_tool` signature at `strands/agent/agent.py:637-669`; `_AgentAsTool.tool_spec` has a single `input` string; `preserve_context=False` forbids a child session manager; busy-lock returns an error result.
- **Consequence**: the previous contract's structured JSON handoff (`customer_scope`, `session_context`, `currency` as tool arguments) cannot be a tool schema and would also let the model supply scope. Replaced by (a) free-text `input` the model forwards, (b) closure tools accepting only `exception_id`, (c) context constructed only from a separately trusted server-side provider or explicit synthetic harness and bound by closure. A payload `_verified_principal` field alone is not proof; no Runtime provider wiring is included.
- **Rejected**: `@tool` wrapper with a structured schema around the child (breaks the SDK prior-art pattern and still model-visible); `preserve_context=True` (conversation as state, violates Constitution I).

## R2. Prior art in this repo [SRC]
`statement_explainer` and `kyc_aml` bind identity by closure and pass `preserve_context=False`. Existing tests fake `Agent` and `tool` by monkeypatch (`tests/framework/test_statement_subagent.py:222-300`), which verifies registration but not real `_AgentAsTool` behaviour. **Decision**: keep that pattern for registration tests, and add one test with a real `Agent` + scripted `Model` for the real `as_tool` path.

## R3. Runtime integration [SRC][PROP]
`_build_strands_agent` shows how child tools are appended behind an env flag [SRC]. **Proposal, pending the plan-gate scope decision (D-INT-1)**: use a synthetic parent harness first and defer Runtime registration. This is partial FR-001 conformance only; deployable Aria Runtime registration is not delivered or verified and requires separate approval and evidence. Rejected for this proposal: a default-off env flag in the entrypoint, because it still changes an existing authenticated boundary file and risks wiring mock ports and writer into a deployed Runtime.

## R4. Identity and authority [SRC][PROP]
`resolve_runtime_identity` (`agentcore_entrypoint.py:30-80`) accepts a payload principal or verified JWT; gateway handler allowlists keys but identity values come from the event (`gateway_handler.py:20-30,86-125`). The payload `_verified_principal` provenance is not established by this feature and the field itself is not proof. **Decision**: construct `TrustedContext` only from a separately trusted server-side provider or explicit synthetic harness; analyst role in this proposal comes only from the synthetic harness. Runtime registration/provider wiring is deferred, and no existing payload identity is used as a substitute. Auth, session and KYC code remain untouched.

## R5. Model-free test seams [PROP]
- Fake clock (fixed `2026-03-16T12:00:00Z`), immutable read-only fixture ports with call recorder, scripted result seam, decision-store interleaving hook, in-memory audit sink, no network, no boto3, no real model.
- Real `Agent` + scripted `Model` subclass implementing `update_config`, `get_config`, `structured_output`, `stream` [SRC: abstract members]. [ASSUME] event dictionary shape must be confirmed at construction from `strands/models/model.py` and `strands/types`.
- **Rejected**: a Bedrock-backed model in tests (network, nondeterminism); testing only via FakeAgent (does not cover `_AgentAsTool`).

## R6. Store and atomicity [PROP; within Q5-approved storage scope, implementation not approved]
- **Proposed design within the Q5-approved boundary**: stdlib `sqlite3` file in a temp/demo directory; `BEGIN IMMEDIATE`; unique scoped server-issued confirmation identity and one immutable binding per approval; unique task confirmation reference; triggers abort `UPDATE`/`DELETE` on `case_tasks`; audit and state changes in the same transaction. The confirmation identity is independent of version/payload hashes and is not caller/model selected. Q5 permits isolated synthetic local persistence only; it does not approve this design or its implementation.
- **Rationale**: this proposed design could demonstrate local atomic confirmation, binding conflict, replay and create-only task behavior without cloud, using immutable synthetic fixtures; construction and verification still require their respective human approvals.
- **Alternatives**: cloud conditional writes are out of scope; JSON file storage lacks a multi-record transaction; in-memory state cannot demonstrate durable replay, audit or recovery. None is substituted without a human decision.
- **Limit**: local SQLite evidence would prove nothing about cloud stores or production concurrency.

## R6b. Resolved storage boundary (Q5)
The human permits isolated synthetic local test/demo persistence for internal proposals, analyst decisions, confirmation/idempotency bindings and audit. The create-only synthetic mock case task remains the sole business write; no financial, source-record or production changes are permitted. This resolves the storage-scope question only: it does not approve the proposed SQLite design, schemas, transaction details, implementation, policy values, fixtures, evaluation labels or commands. Those remain proposals pending their respective human approvals.

## R7. Deterministic rules [PROP]
Defined in `synthetic-policy.md`: reference extraction regex, integer scoring, bands, competition margin, duplicate window, prior-allocation checks, freshness, partial-evidence handling, precedence-ordered disposition table and deterministic classification. A reference-token match is explicitly an inference/candidate hypothesis, not authoritative identity or fact; it cannot repair mapping or independently establish eligibility. The model cannot override any failed check or supply clearance (FR-009).

## R8. Classification design weakness [PROP]
Classification is evidence-derived (mapping > duplicate/prior > residual `amount_reference_mismatch`); the intake hint is recorded but ignored. The residual class is easy to hit, so SC-001 is only strong for `invalid_mapping` (8) and `suspected_duplicate` (5). Flagged as human decision D-B; not hidden.

## R9. Evaluation convention [PROP]
Denominators fixed from the catalogue; unscored (labelled "classification not determinable") cases reported separately, not dropped. A non-confident result is "candidate information", not an "allocation recommendation"; only `recommend` carries `proposed_invoice_id`. Both SC-003 rates therefore normally share a denominator and are reported with defect-detection counts (confident on non-allocatable cases).

## R10. Freshness and expiry [PROP]
Source max-age 4h (payment, invoice, payment history, allocation ledger) and 24h (virtual account, customer); proposal TTL 30 min; confirmation window 10 min after approval; re-evaluated at confirmation. All values are for human review; none established by the spec (FR-011).

## R11. AWS [SRC from AWS support, not independently verified]
No cloud resources, CDK, AgentCore Runtime changes or clients are needed; parent cloud dependencies are unchanged. No AWS behaviour evidence was gathered.

## R12. Compliance and security inputs
Synthetic data only; no real or de-identified customer data; no secrets or credential-like narrative text in artifacts or logs; safe trace IDs; no external regulation asserted. Q2-Q4 are promises to review at the plan gate, not approvals.

## R13. Aria stale items replaced
Earlier research said "approved de-identified data" allowed and that approve "creates/updates" a task. Both conflict with the spec and are removed.
