# Tasks: Virtual Account Receivables Exception Resolution

**Feature**: `004-receivables-exception-resolution`  
**Scope**: Synthetic-only, harness-first implementation; partial FR-001 conformance. Runtime registration and changes to authentication, session, KYC, or existing Aria boundaries are out of scope. The only business write is the approved create-only synthetic mock case task.

All tasks are intentionally unchecked. Test tasks precede their corresponding implementation tasks. The commands in the final phase are the existing, human-approved commands in `quickstart.md`; do not alter them or add verification commands.

## Phase 1: Setup

- [ ] T001 Create package markers in `aria/agents/aria/receivables/__init__.py` and `demo/receivables_exception/__init__.py`; do not modify existing Aria entrypoints or configuration.

## Phase 2: Foundational Context and Contracts

**Checkpoint F1**: Context and shared interfaces are defined and tested before story implementation.

- [ ] T002 [P] Add tests in `tests/unit/test_receivables_trusted_context.py` for frozen trusted context, allowed authority sources, model/payload identity rejection, and context scope mismatches (FR-001).
- [ ] T003 Implement frozen boundary models in `aria/agents/aria/receivables/models.py` for the data-model entities, enums, validation rules, and immutable proposal/decision/confirmation payloads.
- [ ] T004 Implement trusted-context construction and rechecks in `aria/agents/aria/receivables/trusted_context.py`; accept only a separately trusted provider or explicit synthetic harness, never payload `_verified_principal` alone (FR-001).
- [ ] T005 Define typed read-only source, audit, clock, and proposal-store interfaces in `aria/agents/aria/receivables/ports.py`; source interfaces must expose no write operations.

## Phase 3: User Story 1 — Request a Bounded Exception Investigation (P1)

**Goal**: Route supported synthetic investigations to a bounded specialist while preserving parent identity and session responsibilities.

**Independent test**: Framework tests demonstrate supported handoff, no investigation for unrelated/out-of-scope requests, an `{input}` SDK handoff, and no model-visible identity or decision/write tools.

- [ ] T006 [P] [US1] Add fake-backed handoff, scope, no-handoff, and tool-visibility tests in `tests/framework/test_receivables_subagent.py`; assert supported and out-of-scope requests preserve the parent boundary, closure tools accept only `exception_id`, and no analyst decision or writer is exposed. With controlled time and cancellation, verify the four-child-turn and 30-second caller-deadline limits stop further model/tool calls; do not claim a blocked synchronous call is forcibly terminated (FR-001, FR-016).
- [ ] T007 [P] [US1] Add a real `Agent.as_tool` test in `tests/framework/test_receivables_agent_as_tool.py` using a scripted, model-free `Model`; verify the SDK `{input}` schema, `preserve_context=False`, no child session manager, and no external/model calls (FR-001).
- [ ] T008 [US1] Implement the bounded specialist builder and `exception_id`-only closure tools in `aria/agents/aria/receivables/agent.py`; bind context through closures, accept investigation behavior through an injected interface, keep decision/confirmation operations outside model tools, and do not register the tool in Runtime or edit existing Aria entrypoints. The builder and its fake-backed tests must not require the concrete US2 engine or adapters to exist (FR-001).

**Checkpoint US1**: Both framework tests establish the harness-only boundary before deterministic investigation work proceeds.

## Phase 4: User Story 2 — Review an Evidence-Backed Proposal or Escalation (P1)

**Goal**: Produce deterministic, explainable proposals or fail-closed outcomes from synthetic read-only evidence.

**Independent test**: Synthetic cases verify evidence provenance, candidate and variance calculations, scope guards, freshness limits, and fail-closed behavior for missing, unknown, partial, conflicting, stale, malformed, duplicate, prior-allocation, and unapproved-policy conditions.

- [ ] T009 [P] [US2] Add deterministic policy/rule boundary tests in `tests/unit/test_receivables_rules.py`, including inclusive policy dates and tolerance limits, ranking/margin ties, ineligible invoices, duplicate/prior-allocation states, precedence, untrusted payer/remittance text, and fail-closed errors for missing, unapproved, expired, ambiguous, or inapplicable policy. Test activation against the separate human `gate_approved` provenance and require current-byte SHA-256 values for each linked artifact to match `specs/004-receivables-exception-resolution/approval-provenance.md`; reject absent or mismatched approval/bindings and never infer approval from fixture `approval_status` or `approval_record_ref`. Distinguish linked-artifact byte hashes from canonical source, policy-record, and citation digests; never substitute the whole Markdown policy-file hash for a policy-record digest (FR-006, FR-007, FR-008, FR-009, FR-010, FR-017).
- [ ] T010 [P] [US2] Add catalogue, citation, bounded-read, and guard tests in `tests/unit/test_receivables_fixtures.py` using `specs/004-receivables-exception-resolution/synthetic-fixtures.json`; check 57 total cases (52 scored, 5 guards), synthetic scope and exception categories, freshness disclosures, read-only adapters, guard cases causing zero source reads, and unchanged expected counts/labels. For each of the seven evidence types (payment, virtual_account, customer, invoice, payment_history, allocation_ledger, policy), verify each citation carries a source-record ID, immutable snapshot/version binding, and canonical source- or policy-record digest; resolves to that exact record; and independently matches the aggregate snapshot digest. Verify authoritative facts are distinguished from reference/payer-name inference, and missing, unresolvable, or mismatched citations fail closed. Derive runtime immutable snapshot bindings and record digests from the approved fixture bytes without modifying fixtures or relabeling cases. Assert no more than 7 source reads and the approved 20 candidate/row limit; test finite input/output handling using engineering limits chosen within the tests/harness, not new business-policy thresholds (FR-002, FR-003, FR-004, FR-005, FR-011, FR-016).
- [ ] T011 [P] [US2] Add property tests in `tests/property/test_receivables_properties.py` for deterministic Decimal variance, signed amounts, tolerance boundaries, and stable candidate ranking under equivalent input ordering (FR-006).
- [ ] T012 [US2] Implement policy loading and synthetic-approval validation in `aria/agents/aria/receivables/policy.py`; require the separate human `gate_approved` provenance in `specs/004-receivables-exception-resolution/approval-provenance.md` and verify current-byte SHA-256 values for `plan.md`, `synthetic-policy.md`, `synthetic-fixtures.json`, and `quickstart.md` against its linked-artifact bindings. Reject missing approval or any missing/mismatched binding; mutable fixture approval status/reference fields and model output cannot grant approval. Keep linked-artifact hashes distinct from canonical source/policy-record/citation digests: a Markdown policy-file hash binds artifact bytes only and is not a policy-record digest. Derive immutable runtime snapshot/version bindings and canonical source/policy-record digests from the exact approved fixture bytes; do not edit or relabel policy/fixture files or expected cases (FR-007, FR-008).
- [ ] T013 [US2] Implement deterministic rules in `aria/agents/aria/receivables/rules.py` from `specs/004-receivables-exception-resolution/synthetic-policy.md`: exact reference-token inference, integer scoring/bands, inclusive tolerance and competition rules, eligibility, classification, duplicate/prior-allocation checks, precedence, and reason codes; treat payer/remittance text as untrusted data (FR-006, FR-007, FR-009, FR-010, FR-017).
- [ ] T014 [US2] Implement source freshness and policy/proposal/confirmation expiry checks in `aria/agents/aria/receivables/freshness.py`; use the approved synthetic limits (4h and 24h source classes, 30-minute proposal TTL, 10-minute confirmation window) and fail closed on future timestamps or stale evidence (FR-011).
- [ ] T015 [US2] Implement investigation orchestration in `aria/agents/aria/receivables/engine.py`; resolve every citation to its exact source-record ID and immutable snapshot/version, validate its canonical record digest and independently validate the aggregate snapshot digest, and disclose evidence availability/freshness and safe next steps. Require all seven evidence types for recommendations; distinguish authoritative facts from reference and payer-name inference, reject partial required evidence, and never let model text override deterministic checks. Cooperatively enforce the 30-second caller deadline and cancellation before initiating each subsequent read or other operation; after expiry/cancellation issue no further reads, calls, or writes, while making no promise that a blocked synchronous call can be killed. Keep finite input/output limits as engineering limits selected in tests/harness, not new business policy; use no network or real models (FR-005, FR-008, FR-009, FR-010, FR-011, FR-017, FR-020).
- [ ] T016 [US2] Implement local synthetic fixture adapters in `demo/receivables_exception/adapters.py`; enforce trusted tenant/customer/currency and supported-category scope, provide read-only source access, and return explicit unavailable/unknown/partial/conflicting results rather than treating missing data as clear (FR-002, FR-003, FR-004, FR-016).

**Checkpoint US2**: Run the US2 tests before analyst workflow work; confirm that recommendations require all seven evidence types and the applicable approved policy.

## Phase 5: User Story 3 — Decide Whether to Create a Synthetic Mock Case Task (P1)

**Goal**: Keep analyst decisions and explicit confirmation separate from investigation; create only an immutable, idempotent synthetic task.

**Independent test**: Real SQLite tests verify approve/revise/reject/escalate and confirmation behavior, transaction rollback, audit coupling, and both decision/task race orders.

- [ ] T017 [P] [US3] Add real-SQLite workflow tests in `tests/unit/test_receivables_store.py` for all 14 workflow scenarios in `specs/004-receivables-exception-resolution/synthetic-fixtures.json`, including approve/revise/reject/escalate, non-recommendation approval denial, confirmation binding, stable server-issued retry IDs, exact replay, binding conflicts, failed/uncertain outcomes not reported as success, create-only task and safe-reference audit coupling, stale confirmation, and both race orders. Assert audit excludes raw payer, remittance, narrative, prompt, and credential-like text; safe references remain usable for tracing; and failure/rollback/uncertain states are not recorded or reported as successful (FR-012, FR-013, FR-014, FR-015, FR-016, FR-018, FR-020).
- [ ] T018 [P] [US3] Add local-demo accessibility assertions in `tests/unit/test_receivables_store.py` for semantic headings and labels, keyboard-operable controls with visible focus, non-color status, and announced loading/result/error states (FR-019).
- [ ] T019 [US3] Implement the isolated SQLite store in `demo/receivables_exception/store.py`; use real transactions for local confirmation binding, task creation and audit, enforce immutable create-only synthetic tasks, return exact replays before stale-state checks, reject changed bindings, and roll back on audit/write failure without representing uncertain writes as successful. Limit atomicity claims to local SQLite state and immutable synthetic fixtures; do not imply external-source reads or freshness checks are transactionally locked or atomically coupled (FR-014, FR-015, FR-016, FR-018, FR-020).
- [ ] T020 [US3] Implement analyst decision and confirmation services in `demo/receivables_exception/service.py`; support approve/revise/reject/escalate as separate operations, issue opaque server-side confirmation IDs, revalidate current proposal/decision/evidence state, prevent approval of non-recommendations, and preserve safe retry context (FR-012, FR-013, FR-014, FR-020).
- [ ] T021 [US3] Implement the usable local synthetic demo in `demo/receivables_exception/app.py`; display proposal facts separately from inference, expose the exact task before confirmation, communicate failed or uncertain outcomes without claiming success and provide a safe next step, and meet the accessibility assertions in `tests/unit/test_receivables_store.py` (FR-019, FR-020).

**Checkpoint US3**: Confirm no task exists before explicit confirmation; verify reject/escalate never write, revision requires new approval, and task-first races cannot mutate a committed task.

## Phase 6: User Story 4 — Evaluate and Trace the Bounded MVP (P2)

**Goal**: Measure the approved synthetic catalogue and instrumented workflow without treating targets or unobserved surfaces as results.

**Independent test**: Approved pytest paths exercise evaluation formulas, catalogue denominators, abstention/error accounting, coverage limitations, fixture immutability, and workflow audit assertions.

- [ ] T022 [P] [US4] Add evaluation and citation-trace tests in `tests/unit/test_receivables_metrics.py` and `tests/unit/test_receivables_fixtures.py` for the 57-case E path and metric conventions: 50 classification-scored plus 2 unscored, 13 top-candidate cases, 36 escalation-required and 16 not-required, exact per-stratum counts, abstentions/errors in denominators, unlabelled counts, zero-denominator `N/A`, and no success-target claims before an approved labelled evaluation is run. Verify missing, unresolvable, or mismatched per-citation record/snapshot digests are not counted as valid evidence and are accounted for as errors/abstentions under the existing denominator rules; preserve fixture labels and counts (FR-021).
- [ ] T023 [US4] Implement metric calculation and E/W instrumentation in `aria/agents/aria/receivables/metrics.py`; report numerators, denominators, dispositions, unscored cases, per-stratum results, citation-trace failures, and coverage; compare immutable fixture hashes before/after; and mark missing or unexercised surfaces unmeasured—not zero. Exercise E/W through the approved pytest paths; do not add a standalone evaluator command or claim unmeasured success targets (FR-018, FR-021).
- [ ] T024 [US4] Document the local-only demo, synthetic boundary, analyst review/confirmation flow, accessibility, and evaluation limits in `demo/receivables_exception/README.md`; refer to `specs/004-receivables-exception-resolution/quickstart.md` without changing its approved commands or claiming measured results or unapproved success targets (FR-021).

**Checkpoint US4**: Results remain unclaimed until the approved tests are run; distinguish targets from measurements and limit write-safety conclusions to instrumented, exercised surfaces.

## Phase 7: Applicable Architecture Diagrams

Diagram paths below are relative to `specs/004-receivables-exception-resolution/architecture/diagrams/`. Create only the applicable views; use neutral shapes and label the harness-first limitation. Deployment and operations views are not required because deployment is deferred and no operational environment/signals are approved.

- [ ] T025 Create `architecture/diagrams/index.md` with relative links, applicability/status, stage, sources, and rationale; register context, overview, components, and interactions as draft views and record deployment/operations as deferred/not applicable for this feature scope.
- [ ] T026 [P] Create `architecture/diagrams/context.drawio` showing only confirmed actors and boundaries: analyst, Aria parent, synthetic harness/specialist, read-only sources, and isolated local demo/store.
- [ ] T027 [P] Create `architecture/diagrams/overview.drawio` showing the harness-first specialist flow and explicit partial FR-001 limitation; do not imply Runtime registration or production integration.
- [ ] T028 [P] Create `architecture/diagrams/components.drawio` for trusted context, specialist, deterministic engine, read-only ports, analyst service, local SQLite store, and safe audit.
- [ ] T029 [P] Create `architecture/diagrams/interactions.drawio` for investigation and the separate decision/approval/confirmation flow, including replay and decision-first/task-first outcomes.
- [ ] T030 Review `architecture/diagrams/index.md`, `architecture/diagrams/context.drawio`, `architecture/diagrams/overview.drawio`, `architecture/diagrams/components.drawio`, and `architecture/diagrams/interactions.drawio` together; verify each view is editable uncompressed draw.io XML with resolved graph references, relative index links, and no unsupported components or flows. Do not add or run an unapproved validator command.

## Phase 8: Final Approved Verification

Run only the commands already listed in `specs/004-receivables-exception-resolution/quickstart.md`, unchanged. These tasks are parallelizable after implementation and tests are ready.

- [ ] T031 [P] Run the approved unit pytest command from `specs/004-receivables-exception-resolution/quickstart.md` unchanged; it covers `tests/unit/test_receivables_rules.py`, `tests/unit/test_receivables_fixtures.py`, `tests/unit/test_receivables_metrics.py`, `tests/unit/test_receivables_store.py`, and `tests/unit/test_receivables_trusted_context.py`.
- [ ] T032 [P] Run the approved framework pytest command from `specs/004-receivables-exception-resolution/quickstart.md` unchanged; it covers `tests/framework/test_receivables_subagent.py` and `tests/framework/test_receivables_agent_as_tool.py`.
- [ ] T033 [P] Run the approved property pytest command from `specs/004-receivables-exception-resolution/quickstart.md` unchanged; it covers `tests/property/test_receivables_properties.py`.
- [ ] T034 [P] Run the approved regression pytest command from `specs/004-receivables-exception-resolution/quickstart.md` unchanged; it covers the listed AgentCore entrypoint, KYC/AML, statement specialist, gateway, and statement verification tests.
- [ ] T035 [P] Run the approved scoped Ruff check command from `specs/004-receivables-exception-resolution/quickstart.md` unchanged.
- [ ] T036 [P] Run the approved Ruff format check command from `specs/004-receivables-exception-resolution/quickstart.md` unchanged.
- [ ] T037 [P] Run the approved scoped mypy command from `specs/004-receivables-exception-resolution/quickstart.md` unchanged.

## Dependencies and Checkpoints

- **Foundation**: T001 → T002 → T003–T005. Complete checkpoint F1 before story implementation.
- **US1**: T003–T005 → T006–T007 → T008. T008 consumes an injected investigation interface/fake, so its builder and tests can precede the concrete US2 engine/adapters; no dependency cycle or requirement to pass integration tests before that engine exists.
- **US2**: T003–T005 → T009–T011 → T012–T016. US2 depends on the trusted context and ports; the test tasks precede their implementation.
- **US3**: US2 proposal path → T017–T018 → T019–T021.
- **US4**: US2 and US3 → T022 → T023–T024.
- **Diagrams**: T025 precedes T026–T029; T030 follows all diagram tasks. T026–T029 may proceed in parallel.
- **Verification**: T031–T037 only after implementation is ready; these approved commands may run in parallel.

## Parallel Opportunities

- T006 and T007 use separate framework test files.
- T009, T010, and T011 use separate approved test files.
- T017 and T018 may be authored independently, but coordinate changes to their shared test module.
- T026–T029 are separate diagram files based on the same approved design sources.
- T031–T037 are separate approved commands; run only after their dependencies are complete.

## Implementation Strategy

Deliver the bounded investigation and deterministic evidence-backed outcomes (US1–US2) as the first useful MVP slice. Add analyst-controlled, create-only local task workflow (US3) next. Complete catalogue evaluation, traceability, and documentation (US4) before making any performance or safety claims. Runtime registration, live integrations, production authorization, and financial/source-record writes remain outside this plan.

**Task count**: 37  
**By phase/story**: Setup 1; foundational 4; US1 3; US2 8; US3 5; US4 3; diagrams 6; final verification 7.  
**Format**: All tasks use unchecked checklist syntax, sequential IDs, exact paths, and story labels on user-story tasks.  
**Independent test criteria**: Stated for US1–US4 above.  
**MVP**: US1–US2.  
**No results are claimed; no verification commands were run in this task-authoring stage.**

## Implementation Addendum — SC-005 Provenance and Cooperative Bounds

This addendum provides implementation-only acceptance criteria for T002, T006, T008, T010, T012, T015, and T024. It does not add task IDs, change the 37-task count, approve a gate, or amend `spec.md`, `data-model.md`, `plan.md`, `synthetic-policy.md`, `synthetic-fixtures.json`, `quickstart.md`, their values, or expected labels/results. The separate human approval provenance remains authoritative. Treat this as a concrete implementation interpretation of existing SC-005, not as a claim that the draft data-model representation was approved or edited. If implementation would require changing policy values, policy semantics, fixture data, labels, or expected results, stop and return that substantive conflict to the conductor; do not make a silent change.

### T002 and T010 — Contract and read-only interface tests

- In the existing `tests/unit/test_receivables_trusted_context.py` (T002), test imports of `aria.agents.aria.receivables` and `demo.receivables_exception`; all declared enum values and rejection of unknown values; Pydantic schema validation of invalid/missing fields; and immutability by attempting field assignment and mutation of nested collections on models specified as immutable. Verify read-only source interfaces expose no write methods. Do not incorrectly impose that restriction on audit or proposal-store interfaces that have write responsibilities.
- In the existing `tests/unit/test_receivables_fixtures.py` (T010), test fixture-backed adapter imports and schema validation, citation and snapshot-manifest immutability, exact read-only citation resolution, and absence of source-adapter write methods. Exercise the engine’s cooperative deadline/cancellation boundary here as well as the builder boundary in T006. Do not create a new test module for these checks.

### T010, T012, and T015 — Reproducible citation and snapshot representation

Use this implementation representation for each citation: `source_type`, `source_record_id`, `snapshot_id`, `snapshot_version`, `record_digest`, and `classification`, where `classification` is exactly `authoritative` or `inference`. Keep `evidence_kind` where applicable; it does not replace `classification`. Reference-match and payer-name-match evidence is `inference`, never an authoritative fact.

Canonical bytes are the UTF-8 encoding of `json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)`. Do not Unicode-normalize strings. Preserve schema string values and meaningful source-list order; preserve monetary decimals as their exact schema strings, including scale (for example, `100.00`), and never convert them to binary floats. Reject non-finite numbers and floats. Canonicalize objects by sorted keys; do not sort source lists whose order is meaningful.

For a non-policy record, digest an envelope containing its `source_type`, exact `source_record_id`, `source_version`, and every original approved source-record field after schema normalization. Exclude only derived citation, snapshot, and digest metadata. Domain-separate the digest with `receivables-exception-resolution/source-record/v1\0`; format every digest as `sha256:` followed by 64 lowercase hexadecimal characters. Resolve the citation from the read-only catalogue and independently recompute this digest over that exact record; reject missing, ambiguous, or mismatched resolution. Use an existing schema version verbatim when present. Where the source record has no version field, use runtime binding metadata `fixture-v1@sha256:<verified-fixture-artifact-hash>`; do not add that metadata to the fixture or pretend it was fixture-declared. Use the record’s existing schema identifier for `source_record_id`; if an exact record or identifier cannot be resolved, fail closed rather than inventing source facts or IDs.

For the policy record only, use an explicit projection matching the current fixture’s policy keys: `policy_id`, `version`, `tenant_id`, `currency`, `exception_types`, `effective_from`, `effective_to`, `tolerance_abs`, `tolerance_pct`, `weights`, `bands`, `competing_margin`, `duplicate_window_days`, `proposal_ttl_minutes`, and `confirmation_window_minutes`. Exclude only `approval_status_current`, `approval_status_after_human_approval`, and `approval_record_ref` as approval metadata. Preserve all projected values, including monetary strings and array order. Fail closed if a required projected key is absent or an unexpected policy key appears; do not silently broaden or narrow the projection. Domain-separate this digest with `receivables-exception-resolution/policy-record/v1\0`. This is a canonical policy-record digest, not the SHA-256 of the policy Markdown file and not an approval signal.

After verifying the exact current fixture artifact bytes against the linked-artifact SHA-256 binding in `approval-provenance.md`, construct an immutable runtime-only `FixtureDerivedPolicyManifestV1` from that approved catalogue. The phrase “fixture-declared policy digest” is not a literal field in the current fixture: represent it only as this named derived runtime manifest, outside the fixture, and do not claim the fixture declared it. Keep the linked-artifact byte hash, canonical policy-record digest, per-record digest, and aggregate snapshot digest distinct. For payment history and allocation ledger, include only exact records resolvable from approved fixture-backed source data; never turn expected statuses or labels into source facts.

The immutable snapshot manifest contains entries keyed uniquely by `(source_type, source_record_id, source_version)`, each with the matching `record_digest`. Represent entries as a list sorted lexicographically by that tuple for hashing; reject duplicate keys. Define the manifest body as that sorted list, without snapshot identity fields or aggregate digest. Compute `snapshot_id` as `snap-` plus the lowercase hex SHA-256 of `receivables-exception-resolution/snapshot-id/v1\0` concatenated with the canonical manifest body. Compute `snapshot_version` as `v1-` plus the lowercase hex SHA-256 of `receivables-exception-resolution/snapshot-version/v1\0` concatenated with the same body. Compute the aggregate digest independently as `sha256:` plus the lowercase hex SHA-256 of `receivables-exception-resolution/snapshot-manifest/v1\0` concatenated with the same body. This avoids circular inputs while deriving both identifiers and the aggregate from the manifest.

Each citation must resolve to exactly one entry matching its source namespace, record ID, and version, and its record digest must match the independently resolved record. Independently rebuild the sorted manifest and aggregate digest; compare it with the proposal’s existing `source_snapshot_digest` and verify all citations bind to the exact snapshot ID/version. Missing or unresolvable required evidence fails closed under existing outcome rules. Tests must cover successful independent reconstruction and exact resolution, plus changed record fields, wrong source namespace/version, duplicate manifest keys, missing entries, malformed digests, and aggregate or per-record mismatches. Do not change fixture contents, policy values, expected labels, or outcomes to make these checks pass.

### T006, T008, and T015 — Four-turn and 30-second cooperative limits

T008 must enforce both limits at the specialist’s scheduling boundaries, not merely document or test them. Count one child model iteration immediately before every specialist model invocation, including a continuation after a tool result; permit at most four iterations per investigation and never schedule a fifth. Establish one monotonic deadline at invocation entry, no later than 30 seconds from entry and no later than any earlier caller deadline. Before scheduling every model invocation, closure tool, source read, or other operation, check the iteration budget, deadline, and cancellation state. At exhausted budget, expired deadline, or cancellation, stop safely and schedule no further operation. Use wrappers or the existing injected interfaces; do not invent SDK setters or rely on undocumented SDK configuration. Keep decision, confirmation, and write operations unavailable to the model.

T006 must use a scripted, model-free model and controlled clock/cancellation to prove the four-iteration ceiling, prevention of a fifth invocation, and no new model/tool operation after deadline or cancellation. T010 must prove the corresponding engine behavior for reads and other operations, including no subsequent read after expiry/cancellation. These are cooperative controls: a synchronous call already in progress is not forcibly terminated, and no bounded-completion claim may be made for it. After such a call returns, the boundary checks must prevent any subsequent operation. Do not add real-model, network, or live-resource paths.

### T024 — README acceptance

In `demo/receivables_exception/README.md`, include clearly labeled, reviewable sections for scope/data boundary, investigation, analyst decision and explicit confirmation, accessibility, and evaluation limits. State that the demo is local and synthetic-only; source adapters are read-only; the sole business write is the approved create-only mock task after explicit confirmation; there is no Runtime/live integration, production authority, financial/source-record mutation, or real-model/network path. Explain the facts-versus-inference distinction and safe handling of failed or uncertain outcomes. Link to `specs/004-receivables-exception-resolution/quickstart.md` without reproducing or changing its commands. Distinguish targets from measurements, make no unmeasured success claims, and distinguish linked-artifact approval provenance from draft/pending fixture policy labels. Acceptance is a documentation review against each of these statements; it does not require changing approved artifacts or running an additional command.

### Addendum checkpoints and preservation

Complete T002’s contract checks before T003–T005 and retain checkpoint F1. Complete T010’s citation, manifest, and engine-budget tests before the corresponding US2 implementations and retain checkpoint US2. Complete T006/T007 before T008. T024 remains after the US4 implementation and evaluation work as already ordered. These refinements use only the existing test modules and README path; they add no task ID or verification command. Preserve all 37 existing task IDs as unchecked and preserve every existing approved command and value unchanged.
