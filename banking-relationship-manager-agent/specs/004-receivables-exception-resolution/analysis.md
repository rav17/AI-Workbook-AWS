# Specification Analysis Report — Receivables Exception Resolution

**Route:** full-lifecycle  
**Scope reviewed:** Current `spec.md`, `plan.md`, `tasks.md` including its Implementation Addendum, `analysis.md`, `approval-provenance.md`, `data-model.md`, `contracts/investigation-and-approval.md`, `synthetic-policy.md`, `synthetic-fixtures.json`, `quickstart.md`, and the requirements checklist.  
**Result:** **No substantive approved-policy conflict identified.** The addendum supplies an explicit implementation contract for the previously underspecified citation/digest and specialist-budget requirements without changing approved artifact bytes, policy values, fixture data, or labels. A diagram-status discrepancy remains between the plan and task list; the diagrams are not present, so the planned comparison has not occurred.

## Approval and scope interpretation

`approval-provenance.md` records the human plan-gate decision at audit event `seq: 38`, `type: gate_approved`, `stage: plan`. Its recorded scope is the linked synthetic-only `plan.md`, `synthetic-policy.md`, `synthetic-fixtures.json`, and `quickstart.md`, including the disclosed synthetic values, 57-case catalogue, harness-first boundary, local SQLite scope, and quickstart commands. This is synthetic approval only—not approval of production policy, real or de-identified data, live integrations, Runtime registration, financial/source-record writes, or measured results.

Historical pre-gate or draft-status language in `spec.md` Assumptions; `checklists/requirements.md` Outstanding Prerequisites and Notes; `plan.md` §§2, 5, and 9; `synthetic-policy.md`’s heading/status text; and `synthetic-fixtures.json` status fields remains in place. Interpret such language in light of the later, narrower approval provenance: the linked artifacts are approved for the stated synthetic scope. The historical labels are not themselves approval evidence. In particular, this approval does not establish a production/business policy, an evaluated performance result, or a deployable Runtime path. Do not change the linked artifact bytes to remove the historical wording.

The provenance records hashes from `reviews/plan-3.json` and says they were not independently recomputed there. This analysis did not recompute or verify those hashes. Implementation tasks T009 and T012 explicitly require checking current bytes against the recorded bindings; no approval or verification result is inferred here.

## Findings

| ID | Category | Severity | Location(s) | Disposition |
|---|---|---:|---|---|
| A1 | Policy/source digest contract | MEDIUM, resolved for implementation | `synthetic-policy.md` §5; `synthetic-fixtures.json` policy block; `tasks.md` Implementation Addendum, “T010, T012, and T015 — Reproducible citation and snapshot representation” | The legacy policy wording refers to a “fixture-declared digest,” but the fixture has no such literal field. The addendum explicitly says this is not a literal fixture field and defines a runtime-only `FixtureDerivedPolicyManifestV1`, separate from artifact-byte hashes and canonical policy-record digests. It specifies canonical JSON bytes, the policy-record projection, exclusions, domain separation, digest format, and fail-closed behavior for missing or unexpected fields. This closes the implementation-contract gap without claiming the fixture declared a digest or changing policy values. The legacy wording remains a source-artifact caveat, not an executable definition. |
| A2 | Citation schema / SC-005 representation | MEDIUM, resolved for implementation | `spec.md` Success Criteria, SC-005; `data-model.md` “EvidenceItem” and “SourceSnapshot”; `contracts/investigation-and-approval.md` illustrative fragment; `tasks.md` Implementation Addendum, “T010, T012, and T015 — Reproducible citation and snapshot representation” | The legacy model specifies a source ID and `kind`, and an aggregate `snapshot_digest`, but does not define per-citation snapshot/version and canonical record-digest fields. The contract itself warns that its abbreviated fragment omits the required per-citation bindings and does not satisfy SC-005. The addendum now mandates the citation representation (`source_type`, `source_record_id`, `snapshot_id`, `snapshot_version`, `record_digest`, `classification`, and `evidence_kind` where applicable), exact read-only resolution, independent record and aggregate digest verification, manifest construction, and failure cases. Treat this task addendum as the explicit implementation acceptance contract for SC-005; the old data-model text is incomplete legacy documentation, not evidence that the representation is executable or implemented. |
| A3 | Task-to-test and acceptance traceability | LOW, resolved in task acceptance | `tasks.md` T002, T006, T008, T010, T024 and Implementation Addendum sections T002/T010 and T024; prior analysis A3 | The addendum makes model imports, enums, schema validation, immutability, read-port no-write assertions, citation/manifest behavior, T008’s scheduling-boundary limits, and README review criteria explicit within existing tests and deliverables. These address the earlier T001/T003/T005/T024 acceptance gaps: package imports are asserted in T002; model assertions and read-only interface assertions are assigned there; and T024 has a concrete documentation-review checklist. No task IDs or test modules are added. |
| A4 | Diagram status and missing views | MEDIUM | `plan.md` §5 “Component view (text)”; `tasks.md` Phase 7 T025–T030; `specs/004-receivables-exception-resolution/architecture/diagrams/` | The plan says diagrams and a register are not produced and are deferred, while Phase 7 assigns four applicable views and a joint review. No diagram directory or views are present. Thus source and inter-view comparisons cannot yet be made, and the current plan/task status is inconsistent unless the plan statement is treated as an authoring-time status. T025–T030 remain pending, not completed or reviewed. Resolve the status at the appropriate human/conductor review; do not infer view correctness or edit the approved plan in this analysis. Deployment and operations views are explicitly not required for this harness-first scope. No XML validation was performed; structural XML validation alone would not prove factual consistency. |
| A5 | Historical approval-status language | LOW, bounded by provenance | `spec.md` Assumptions; `checklists/requirements.md` Outstanding Prerequisites and Notes; `plan.md` §§2, 5, 9; `synthetic-policy.md`; `synthetic-fixtures.json`; `approval-provenance.md` | Earlier “pending,” “not approved,” or “not yet authored” wording predates the recorded plan-gate approval for the linked synthetic artifacts. Interpret those historical statements only within the approval scope above. Preserve the wording and bytes. Neither draft-status fields nor this interpretation extends approval to production, live resources, or measured claims. |
| A6 | Reported test execution deviation | Informational | Prior worker report recorded in this analysis; `tasks.md` T031–T037 | A worker-reported repository pytest run was unauthorized for that earlier stage. Preserve it solely as an unverified execution deviation; it is not UC8 evidence, feature-test proof, or gate evidence. This analysis did not repeat it or independently verify it. |

**Critical issues:** 0.  
**Substantive approved-policy value/label contradictions:** 0 identified.  
**Implementation-contract gaps addressed by the addendum:** citation representation/digest canonicalization and T008 cooperative scheduling limits.  
**Outstanding artifact-level issue:** plan/task diagram status discrepancy and absent views.

## Requirement and success-criterion coverage

Coverage below means planned implementation and test or acceptance work is mapped. It does **not** mean implementation exists, tasks are complete, tests passed, or results were measured. SC-001–SC-007 remain evaluation/traceability criteria, not achieved outcomes.

| Requirement | Has task? | Task IDs | Planned test/acceptance |
|---|---:|---|---|
| FR-001 | Yes | T002, T004, T006–T008 | Trusted context, handoff, model-free `Agent.as_tool`, tool visibility, cooperative specialist limits |
| FR-002 | Yes | T010, T016 | Synthetic catalogue/scope and adapter tests |
| FR-003 | Yes | T010, T016 | Synthetic-only catalogue and adapter scope |
| FR-004 | Yes | T005, T010, T016 | Read-only ports/adapters and no-source-write assertions |
| FR-005 | Yes | T010, T015, T022 | Evidence, citation, inference distinction, and trace tests |
| FR-006 | Yes | T009, T011, T013 | Policy boundary and Decimal property tests |
| FR-007 | Yes | T009, T012, T013 | Provenance/binding checks and deterministic policy tests |
| FR-008 | Yes | T009, T012, T013, T015 | Fail-closed policy/evidence tests |
| FR-009 | Yes | T009, T013, T015 | Duplicate/prior-allocation rule and source tests |
| FR-010 | Yes | T009, T013, T015 | Classification, competition, and fail-closed tests |
| FR-011 | Yes | T010, T015, T022 | Citation resolution, freshness, and disclosure tests |
| FR-012 | Yes | T017, T020 | SQLite workflow and decision-service tests |
| FR-013 | Yes | T017, T020 | Non-recommendation approval denial tests |
| FR-014 | Yes | T017, T019, T020 | Confirmation binding, races, create-only task, and rollback tests |
| FR-015 | Yes | T017, T019, T020 | Exact replay, changed binding, and uncertain-write tests |
| FR-016 | Yes | T006, T010, T016, T017, T019 | No writer exposure, read-only adapters, and local-store tests |
| FR-017 | Yes | T009, T013, T015 | Untrusted payer/remittance handling tests |
| FR-018 | Yes | T017, T019, T023 | Audit redaction/coupling and trace instrumentation tests |
| FR-019 | Yes | T018, T021 | Accessibility assertions for the local demo |
| FR-020 | Yes | T015, T017, T019–T021 | Evidence limitations, safe retry, and failed/uncertain outcome tests |
| FR-021 | Yes | T022–T024 | Metric conventions, no unmeasured target claims, and documentation review |
| SC-001 | Yes | T022, T023 | Classification denominators, labels, and metric calculation |
| SC-002 | Yes | T022, T023 | Candidate denominator and acceptable-ID scoring |
| SC-003 | Yes | T022, T023 | Precision, incorrect-allocation rate, and disposition accounting |
| SC-004 | Yes | T022, T023 | Escalation-required and false-escalation accounting |
| SC-005 | Yes | T010, T015, T022, T023 | Seven evidence types, per-citation resolution/digests, and Decimal recomputation, using the addendum’s explicit representation |
| SC-006 | Yes | T010, T017, T019, T022, T023 | Read-only sources, create-only task path, instrumentation, and coverage reporting |
| SC-007 | Yes | T017, T019, T022, T023 | Safe-reference audit assertions and E/W trace coverage |

**Planned requirement/criterion mapping:** 28/28. This is a planning-coverage count only—not implementation coverage, test success, or achieved outcomes.

## Task-to-test / acceptance traceability

| Task(s) | Corresponding planned test or acceptance | Gap / qualification |
|---|---|---|
| T001 | T002 import assertions for `aria.agents.aria.receivables` and `demo.receivables_exception` | Import assertion is in the later foundational test task; T001 remains unchecked. |
| T002 | `tests/unit/test_receivables_trusted_context.py`; addendum model, enum, schema, immutability, import, and source-port assertions | Explicit acceptance is now present; no result is established. |
| T003 | Model validation/enum/immutability assertions specified under T002 | The legacy model does not itself specify the new citation representation; the addendum is the implementation acceptance contract for citation fields. |
| T004 | T002 trusted-context boundary tests | Planned only. |
| T005 | T002 source-port assertion that source interfaces expose no write methods | Audit and proposal-store interfaces retain their planned write responsibilities. |
| T006 | `tests/framework/test_receivables_subagent.py` | Fake-backed scope, handoff, tool visibility, iteration, deadline, and cancellation tests are specified. |
| T007 | `tests/framework/test_receivables_agent_as_tool.py` | Scripted, model-free SDK handoff test is specified. |
| T008 | T006/T007 plus the addendum’s required implementation-boundary behavior | Addendum requires four-iteration and 30-second cooperative enforcement before scheduling operations, not merely documentation or tests. |
| T009 | `tests/unit/test_receivables_rules.py` | Approval provenance and byte bindings must be distinguished from canonical digests; no test result is established. |
| T010 | `tests/unit/test_receivables_fixtures.py` | Addendum specifies exact citation/manifest reconstruction, mutation/mismatch cases, immutability, imports, and engine deadline/cancellation checks. |
| T011 | `tests/property/test_receivables_properties.py` | Decimal and deterministic ordering properties are specified. |
| T012–T016 | T009–T011 and `tests/unit/test_receivables_fixtures.py` | Policy, rules, freshness, engine, and adapters have named corresponding checks; exact-byte verification and canonical digests remain future implementation/test work. |
| T017 | `tests/unit/test_receivables_store.py` | SQLite workflow, audit, replay, race, rollback, and uncertain outcome cases are specified. |
| T018 | Accessibility assertions in `tests/unit/test_receivables_store.py` | Planned only. |
| T019–T020 | T017 workflow tests | Store and service behavior is test-mapped; external-source atomicity is explicitly excluded. |
| T021 | T018 accessibility assertions and T017 failure/uncertain outcome checks | Planned only. |
| T022 | `tests/unit/test_receivables_metrics.py` and `tests/unit/test_receivables_fixtures.py` | Denominators, citation validity, abstention/error accounting, and fixture preservation are specified. |
| T023 | T022 tests and approved pytest paths | Missing/unexercised surfaces must be marked unmeasured; no evaluator command is added. |
| T024 | README review acceptance specified in the addendum | Sections and scope, data, confirmation, accessibility, evaluation, provenance, and safe-outcome assertions are explicit. |
| T025–T029 | T030 joint manual review of the register and four views | Views and register do not exist; deliverables and review remain pending. |
| T030 | Joint comparison of views to cited sources and one another | Not performed because the diagram artifacts are absent. |
| T031–T037 | The exact approved pytest, Ruff, and mypy commands in `quickstart.md` | Verification tasks remain unchecked and were not run in this analysis. |

**Unmapped feature requirements:** None at the planned-task level.  
**Task acceptance gaps identified in the prior analysis:** Addressed by the addendum for T001/T002, T003, T005, and T024.  
**Diagram completion/review:** Still pending; T025–T030 are not evidence of completed views or validation.

## Constitution alignment

- **I — Structured State Is Authoritative:** Typed models and immutable citation/manifest representations are planned. Model behavior has explicit test acceptance; no implementation was verified.
- **II — Deterministic Safety and Authorization:** Trusted context, model-inaccessible decisions/writes, deterministic rules, provenance binding, and audit redaction are assigned tests. No implementation was verified.
- **III — Patch, Validate, and Invalidate:** Revision and stale-confirmation behavior are assigned workflow and race tests. No implementation was verified.
- **IV — Bounded Context and Tool Use:** T006, T008, T010, and T015 specify a four-iteration ceiling, a monotonic 30-second/caller deadline, cancellation checks, read/candidate limits, finite input/output handling, and no subsequent operation after expiry/cancellation. These are cooperative controls: an already-running synchronous call is not claimed to be forcibly terminated. No implementation or measurements are established.
- **V — Durable Boundaries and Session Isolation:** The plan limits persistence to isolated synthetic local state and excludes production/live resources. Tests limit atomicity claims to local SQLite and immutable fixtures; no remote-source atomicity is claimed.
- **VI — Python Quality and Operational Readiness:** Approved scoped pytest, Ruff, and mypy commands are assigned in T031–T037. They were not run by this analysis; no quality result is established.
- **Security/compliance:** Synthetic-only scope, non-authoritative untrusted text, safe audit references, and redaction are assigned planned controls. No enforcement has been verified.

No constitution violation is established by the current plan/tasks. Planned controls must not be presented as implemented or verified.

## Dependency and readiness review

The planned dependency order is broadly coherent: foundational tests precede implementations; US1 tests use the injected investigation seam and do not require the concrete US2 engine; US2 tests precede engine/adapters; US3 workflow tests precede store/service; US4 tests precede metrics; and final verification follows implementation. The addendum preserves the 37 unchecked task IDs, existing test modules, and approved commands.

The addendum provides a concrete implementation interpretation of SC-005 and the cooperative limits without claiming that the legacy data model was amended or that work has been implemented. Its required policy manifest is derived at runtime from verified linked fixture bytes; approval status continues to come from the separate human provenance record, not from fixture approval fields or the derived digest. If implementation would require changing approved policy semantics, fixture data, labels, values, or expected outcomes, the addendum directs that conflict back to the conductor rather than allowing a silent change.

Readiness is limited to proceeding with the approved synthetic implementation subject to human/conductor review. The diagram status discrepancy remains open and the views are absent. This is not production readiness, deployed Runtime registration, implementation completion, or evidence that feature code or tests pass.

## Diagram review (full-lifecycle)

The applicable planned views are context, overview, components, and interactions (T025–T030). No `specs/004-receivables-exception-resolution/architecture/diagrams/` artifacts were present. Accordingly, no view could be compared with its cited sources or with the other views. The plan’s §5 statement that diagram work is deferred must be reconciled with the current task list assigning Phase 7 diagrams; neither statement establishes completed work. Deployment and operations views are explicitly deferred/not applicable to this harness-first scope. No XML validation was performed; structural validation alone would not establish factual consistency or completeness.

## Actual test results and execution deviation

This analysis did not run tests, builds, lint, type checks, checkpoints, or other verification commands.

A prior quality worker reported the following **unauthorized execution**, contrary to that stage’s restriction:

```text
.venv311 python -m pytest -q
666 passed, 7 skipped, 1 warning in 268.91 seconds
```

This is preserved solely as a worker-reported execution deviation. It was **not independently verified**, is **not UC8 evidence**, and is **not stage or gate evidence**. It must not be represented as proof that the planned feature tests passed. No feature-specific test result is established here.

## Next actions

1. Preserve the approved linked artifact bytes and use `approval-provenance.md` only within its stated synthetic scope.
2. During implementation, follow the exact citation, canonicalization, manifest, and budget acceptance criteria in the `tasks.md` Implementation Addendum; do not substitute artifact hashes for record/citation digests or treat derived digests as approval.
3. Keep all tasks unchecked until actually completed and tested. Do not convert planned coverage into implementation or test-success claims.
4. Resolve the plan §5 versus tasks Phase 7 diagram status at the appropriate human/conductor review; create and compare the applicable views before claiming diagram review.
5. Preserve the unauthorized worker-reported pytest run only as a deviation; make no verified test, production, Runtime-registration, external-atomicity, or unmeasured success claim.

**Readiness:** Ready to proceed toward the approved synthetic implementation subject to conductor review and applicable lifecycle checks; diagram status is unresolved. Not production-ready, Runtime-complete, implemented, or test-verified.
