# Quickstart: Future Recovery Contract Validation

**Proposal only.** The approved specification is WHAT; selectors/assertions below are future test proposals, not accepted implementation decisions. Q1/Q2/Q3 are human-answered requirements/disposition as recorded below; exact protocol and fingerprint details are planned designs. The 10s overall status/wait default and 2s per-adapter-call cap are proposed, unmeasured, non-SLO defaults. No tests, builds, installations or construction checks were run in this correction. Commands below are future selectors only; do not run them now. Use synthetic fixtures and pure model/contract fakes or a local SQLite database only; on Windows do not call or spawn any adapter, including a fake worker; no models, live hosts/resources, customer data, secrets, package installation, or receiving-project configuration changes.

## Proposed future prerequisites

Python >=3.11 and already provisioned repo dev dependencies; implemented recovery package and deterministic fake host adapter/clock/SQLite transaction/fencing; isolated temporary test root. SQLite design is a local-filesystem core proposal, not proof of host exclusion. A fake adapter's safe-exclusion result must be distinct from DB generation fencing. `workflow dispatch` is eligibility only, not ownership or execution. Only enrolled callers routing launch and all recovery-relevant mutations through the cooperative core are supported; legacy direct writes and arbitrary CLI/plugin paths are explicitly out of scope, and universal gating is deferred. No real host integration supports safe execution, so all actual transfer is blocked. No live workspace/resource as test target.

## Proposed future focused selectors

These full selectors are not cleared for Windows: use only individually identified pure model/contract tests that never call or spawn an adapter. No Windows adapter execution or real-host test is authorized by this guide.

```powershell
python -m pytest tests/unit/speckit_flow/test_flow_recovery_models.py tests/unit/speckit_flow/test_flow_recovery_service.py tests/unit/speckit_flow/test_flow_recovery_fencing.py tests/unit/speckit_flow/test_flow_recovery_evidence.py tests/unit/speckit_flow/test_flow_recovery_scenarios.py
```

Expected future acceptance: each mapped case gets expected result; at most one effective enrolled core writer; no transfer without a separate durable host exclusion; no transfer from heartbeat/listing/timeout; no invalid checkpoint resume; no uncertain-effect replay. Crash injection covers `TRANSFER_PENDING` commit, host fence/receipt persistence, DB final commit and lost responses. After host fencing but before DB final commit, old generation remains fenced and new remains unlaunched; recovery queries/replays the same transfer ID and never reopens old. Verify receipt binds feature/task, tenant, previous/new generation, execution, exact decision/scope/evidence revision and transfer ID, and that the host enforces it across restart. If that cannot be guaranteed, block. SQLite and host fencing are separate systems, not a cross-system atomic transaction. Corruption/ambiguous commit or receipt blocks. No arbitrary legacy writer or external effect is claimed fenced. Not run; no current pass evidence; no real host integration supports safe execution and all actual transfer is blocked.

### Portable bootstrap / unrelated receiving-project selector (rechecked existing source)

```powershell
python -m pytest tests/unit/test_speckit_bootstrap.py::test_install_preserves_target_governance_and_active_feature tests/unit/test_speckit_bootstrap.py::test_optional_packs_stay_disabled_after_install
```

Future expected assertions, from earlier source inspection at `tests/unit/test_speckit_bootstrap.py:181-196` and `:586-610` (not revalidated in this follow-up; selector remains proposed and unrun):

- The preservation case verifies byte-for-byte preservation of `.specify/memory/constitution.md`, `.specify/feature.json` (active feature pointer), the custom profile, and `.specify/verify.json` (including its configured command).
- The optional-packs case verifies all six manifests (`compliance`, `aidlc-extras`, `codebase-analysis`, `operational-readiness`, `walking-skeleton`, `stage-contracts`) have `enabled: false`; profiles stdout omits only these four names: `nfr-hardening`, `brownfield`, `release-ready`, `skeleton-first`. This does not assert that every optional profile name is absent.
- These are separate existing test cases run together by the exact selector above. The selected source ranges confirm only the assertions stated here; selector is proposed for a future run only and was not executed. Any expansion to additional governance assertions requires separately authorized test changes.

## Proposed future regression selectors (unrun)

```powershell
python -m pytest tests/unit/speckit_flow/test_flow_session.py tests/unit/speckit_flow/test_flow_orchestration.py tests/unit/speckit_flow/test_flow_units.py
```

Expected: intent, eligibility and existing unit-checkpoint behavior remains intact.

## Future scenario checks

1. Future pure model/contract checks (not run): model generic pre-existing parent-owned killable tree containment, termination/wait/reap/no-child proof before guard release, shared deadline accounting, no overlap and durable quarantine. Assert Windows rejects before any adapter child execution or spawn. No Windows adapter call, supervision, status timeout, transfer, qualification or real-host test is in scope. Fake clocks cannot qualify any host or establish OS guarantees; the supported-host set is empty.
2. Concurrent requests across features in the same receiving project use its single local SQLite ledger: `BEGIN IMMEDIATE` serializes writers across features, expected-generation compare-and-update accepts at most one current-generation transition for a composite task key, and stale writes reject. Distinct receiving-project roots have separate databases and no shared store; contention across features is an expected bounded busy outcome, not a distributed lock. Exercise two-phase transfer: pending record first; host durable fence/receipt bound to task, tenant, old/new generations, execution, decision/scope/evidence revision and transfer ID; final DB commit second. Deny launch before both durable receipt and DB commit. Crash after host fence/before DB final commit must leave old fenced/new unlaunched; recovery queries/replays same idempotent transfer ID, never reopens old. Verify durable enforcement/receipt across adapter restart; otherwise block. Do not treat SQLite as worker-death proof or claim cross-system atomicity.
3. Correct, missing, mismatched and spoof-like self identity; unresolved identity blocks ownership action.
4. Resume only from latest unambiguous eligible checkpoint; modify one relevant dependency then one unrelated artifact; verify dependent-only invalidation.
5. Exercise incomplete/torn/corrupt/rollback records, permission denial, ambiguous sequence, missing identity, tenant mismatch, stale/replay/expired authorization and crashes before pending commit, after pending commit, after host fence/before DB final commit, after final commit-before-response. Same-ID recovery only; ambiguity blocks and unknown effects remain unreplayed. Ensure legacy `state.json`/Markdown/`audit.jsonl` and `units.py` checkpoint evidence may be stale and are not used to reconstruct recovery authority; source/revision mismatch blocks resume and status reports stale/unknown.
6. Review keyboard/screen-reader presentation and ensure evidence/provenance/limits precede approval choice, not encoded only by color/link text.
7. Assert receiving-project governance and optional-pack disabled state unchanged; fixtures/records contain only synthetic identifiers/redacted metadata.

## Proposed static/security checks (future only)

```powershell
python -m ruff check speckit_flow/recovery tests/unit/speckit_flow
python -m mypy speckit_flow/recovery
```

Run configured, project-approved dependency/security and secret scanners only after authorization; don't invent or execute an unapproved command. Review local DB/journal permissions, schema/size limits, migration behavior, corruption handling, root/path defenses, no implicit command/plugin execution, redaction, deadlines/hung adapter. No live AWS/CRM tests needed or authorized.

Before future release: attach real command output, selector, adapter/test environment and failures; map 19 classes individually; measure deadline using deterministic fake time; obtain receiving-project auth/tenant/retention/access/integrity decisions. This guide and all selectors are proposals, not test-success evidence.

## Storage scope and durability proposal

Pending human review: one local SQLite file at the receiving-project root, shared across features in that project and never shared across project roots; composite task key `(project_key, feature_dir_key, stage_key, unit_key)`; `journal_mode=DELETE`, `synchronous=FULL`, foreign keys ON per connection, busy timeout <=250ms capped by remaining deadline, and `BEGIN IMMEDIATE` with expected generation/revision checks. Writers serialize across project features; network/synced filesystems and cross-host guarantees are unsupported. Corruption or ambiguous recovery blocks. Use the SQLite online backup API in a quiesced, approved window, not live file copies. Restore fails closed unless a capable host confirms durable fences/revisions against the restored DB watermark and reconciliation completes; no current real host has this capability, so restored DBs cannot authorize transfer meanwhile. Whole-DB rollback cannot be detected from monotonic rows alone. Full assumptions, backup/restore and project/privacy boundaries are in `data-model.md` and the adapter contract.

Final SQLite transfer commit includes only transfer receipt/status, recovery ownership, transition history and `recovery_audit` records. No outbox table/payload/projection/consumer is included. Existing `audit.jsonl` is NOT mirrored or updated by this transaction: it remains a separate lifecycle artifact, not authority for recovery transfer. Removing undefined delivery work avoids an unowned consumer/retry protocol; adding it requires separate review.

## Observability boundary (proposal, not satisfaction)

Use the host `TelemetrySink`/stdlib logging, monotonic timing and context propagation seam defined in `contracts/recovery-adapter.md`: opaque correlation/trace IDs, allowlisted bounded reason/outcome codes, status/deadline/SQLite conflict and duration metrics, and spans for observation, evidence/auth, pending commit, host fence/receipt reconciliation and final commit. Persist correlation IDs in transition and `recovery_audit` records. No payloads, secrets, customer data, raw exceptions or identity/evidence text in telemetry; no identifiers as metric labels. Sink failure never changes ownership or grants launch. Missing metric/trace exporters or cross-host propagation are explicit host limitations and required before production, not constitutional satisfaction. Fake-sink validation is future-only; no execution claim.

## Human answers / stage status

Q1, Q2 and Q3 were answered via the questions CLI by `human:rav17`; the conductor reports `questions check` returned `{"open":[]}` with exit 0. Q1 requires durable host-issued identity/fencing receipts and unsupported hosts to block; its 10-second total wait and 2-second adapter-call cap are proposed, testable defaults, not measured or approved SLOs. Q2 requires matching completion evidence, relevant inputs/dependencies/instructions and verification bindings, invalidating affected dependents, and blocking ambiguous progress or side effects. Q3 is deferred/out of scope; no autonomy grant is approved or implied. Detailed protocol and fingerprint choices remain planned designs, not additional human-selected details. No sensors were rerun in this update; plan remains `in_progress`, with no gate or stage transition.

## Additional future source-design acceptance checks (unrun)

- Inspect effective DELETE/FULL/foreign-key/busy-timeout settings on each connection; fake deadlines and SQLite busy/locked/generation conflicts must return bounded outcomes and corresponding metrics, without takeover. Exercise crash/hot-journal recovery and corruption-block behavior only with disposable local fixtures.
- Validate the project-root online-backup policy across quiesced features; a restored snapshot must fail closed unless a capable host confirms durable fence/revision state against its watermark and receipt reconciliation completes. No current real host supports this, so restored-database transfer authorization remains blocked. No hardware power-loss guarantee is inferred from fake tests.
- Capture fake logs/metrics/spans and SQLite audit correlation; assert bounded labels/codes, redaction, span parentage and safe telemetry failure. Missing host metric/trace sink is a production blocker.
- Assert final commit contains recovery ownership/receipt, transition and recovery_audit only, and leaves lifecycle `audit.jsonl` bytes unchanged; no projection delivery work is defined.

## Plan-10 follow-up: unsupported Windows and generic model checks (unrun)

Windows recovery-adapter execution and supervision are unsupported and out of scope. On Windows only author/review or run pure model/contract tests that neither call nor spawn any adapter, including a fake worker. No Windows status timeout or transfer is supported. Windows qualification and real-host tests are not deliverables of this feature. Any Windows support requires a separate scoped design/feature and independent platform security review covering broker or outer containment, CreateProcess/Job attachment and parent-loss races.

Future pure fake-clock/model checks cover `D=request_start+configured_wait` before admission, `call_end=min(now+configured_adapter_cap,D-R)` and response finalization by `D-R`. Human-proposed 10s/2s and architect-proposed R=250ms/500ms inline cleanup-effort cap remain unmeasured non-SLO defaults; R=250ms is only a candidate for a verified minimum fixed rendering/handoff reserve, not an assumed guarantee, and a platform unable to prove it is unsupported. There is no mandatory cleanup reserve/work cutoff: cleanup uses only remaining call time, never delays response, and may continue secondarily under containment/quarantine. Every admitted supported status operation returns valid current result before D or latest preloaded cache as unavailable/unknown by D. Known inability to sustain responsive foreground supervision rejects platform admission; catastrophic caller-process/OS unavailability is outside operating preconditions, not claimed deadline success.

Model preflight rejection if pre-existing verifiable parent-owned killable tree containment before adapter code is absent, unknown or failed; no uncontained fallback, helper thread or multiprocessing. Model cancellation, termination, wait/reap, no-child proof and resource cleanup before guard release; quarantine blocks work but is not containment. Model durable active guard before spawn, no same-task work across adapters during unresolved cleanup, supervisor loss, and same-ID receipt reconciliation only after local cleanup. Simulate remote outcomes surviving local termination; service-side idempotency/deadlines remain mandatory. These are pure planned checks, not real-host tests or proof that any platform qualifies. The supported-host set is empty and all actual transfers remain blocked. No tests or sensors ran.


## Plan-11 future acceptance: deadline independent of reap (unrun)

- Use future pure model/fake-clock scenarios to assert request clock starts before admission; a fixed bounded empty/unknown response is prepared before request and substitutes for absent/invalid snapshots without DB or logging during handoff. Validate positive finite wait, maximum response size, reserved output capacity, fixed template and nonblocking enqueue/caller return. Reject invalid config/request before status waiting if its configured deadline or actual remaining time at admission cannot accommodate the platform-verified response reserve or capacity cannot be assured; do not count rejection as meeting D. Admission contention, full controller queue and inaccessible publisher return bounded cache without resetting D.
- At invocation admission, cover nonpositive D-R, D-R <= t and remaining time below the verified minimum useful guard/creation/work budget: no invocation guard, no spawn, immediately return the prebuilt cache unavailable/unknown by D. Also model an initially sufficient budget followed by a late guard: no spawn, retain/reconcile any unresolved guard. Reject known blocked, uncontained or non-cooperative adapters before supported admission; never run one inline. Reject Windows before any call/spawn.
- For every admitted supported status request, assert response time <=D: valid current result before D, otherwise latest owner/progress/evidence cache with unavailable/unknown, age/source/revision/uncertainty and safe options. Bound fixed template rendering and nonblocking enqueue/caller return in the platform-verified R, with capacity reserved before admission; do not assume 250ms suffices. Check stale/empty snapshot labels and do not infer death or ownership authority.
- Model adapter spawn/work/IPC hangs, unresolved child termination/reap, ledger lock/write stall, cleanup stall, telemetry sink and logging flush stall independently. Assert no such operation executes/blockingly waits on foreground; response does not require fresh DB write or guard-state persistence at timeout. Delayed cleanup must not prevent return by D.
- Model a status child still alive but under persistent killable containment when status returns. Durable active guard remains a block even if quarantine write fails; no same-task adapter call/retry, ownership mutation, transfer or launch through any adapter until confirmed tree/pending-creation death/cleanup and outcome reconciliation. Cache-only status still returns by D during quarantine, with no child call. Never clear guard on elapsed time or one PID exit.
- Assert 500ms caps inline cleanup effort only within call_end; no cleanup success prerequisite. Safe-read retries are optional, allowed only after confirmed cleanup/reconciled outcome and sufficient budget. Skip all retries when those conditions fail.
- Model fence timeout/late remote effect with unchanged transfer ID, blocked launch and prior fence never reopened. After local cleanup only guarded same-ID reconciliation queries are allowed until outcome confirmed; local kill is not remote cancellation.
- Reject unsupported platform/known nonresponsive-foreground capability before execution, including Windows; never record such rejection or catastrophic caller-process/OS loss/freeze as a supported request meeting D. Fake models cannot qualify any host, prove scheduler behavior or establish real timing. Supported-host set remains empty; real-host qualification is not claimed or run.

These are future assertions, not tests executed or evidence of FR-003 implementation. No sensors, reviewer, gate or transition ran.

**FR-003 / SC-001 mapping (proposal, not execution evidence)**: The 100% SC-001 denominator remains all status inventory classes 1?4, with each required expected status and available owner/progress represented; future cases model admitted supported requests and exercise cache/empty fallback, including hangs and delayed cleanup. Every admitted supported request must return by D independently of adapter behavior and child cleanup. Separately test pre-admission rejections; they are not status waits and must not be counted as deadline successes or used to narrow the specified denominator. Catastrophic caller-process loss or OS freeze is outside ordinary operating preconditions, not an adapter exception. No host is currently qualified and no timing result is claimed.
