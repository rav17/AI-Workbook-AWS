# Ideation Brief: Reliable Worker Recovery

**Date**: 2026-11-11  
**Selected increment**: Reliable worker recovery, with portable tests and approval evidence  
**Route**: `full-lifecycle` (confirmed; this brief is ideation only)

## Problem

A workflow session and the worker executing it are different things. Existing session continuity and workflow-state facilities can park/unpark or redo an intent, report stage/gate/lead status, dispatch an eligible stage, and checkpoint construction units. They do not establish which worker currently owns execution, prove that a worker is alive or stopped, or make state and audit/checkpoint writes a single transaction. A repeated dispatch or an expired heartbeat therefore cannot safely be treated as permission to take over.

The reported incident is user-reported, not independently verified: during a prior UC8 session, the conductor disappeared and `read_agent` found no agent; a replacement misidentified its own ID as another owner and paused; work eventually resumed from saved files. This is a motivating example, not a basis for hardcoding agent IDs or assuming a particular host's semantics.

Users are workflow operators, human approvers, and workers operating through different host environments. They need to recover from interruption without losing verified progress, silently waiting forever, treating uncertainty as proof of failure, or allowing two workers to make conflicting writes. The accepted synthetic UC8 increment is not a request to deploy, commit, or alter live resources; UC8 remains untouched.

## Desired outcome

An operator can inspect durable ownership and progress, get a bounded and useful report when execution is running, delayed, unavailable, or unknown, and continue only from verified saved progress under an explicit recovery boundary. A worker can identify itself correctly. Uncertain liveness or host capability never authorizes automatic ownership theft or concurrent execution. A human can read the complete evidence package before deciding what recovery or other action to authorize.

Keep the recovery contract portable: a neutral core with thin host-capability adapters, demonstrable in unrelated projects without models or cloud/live services. Receiving projects retain their own constitutions, commands, policies, and governance; optional packs remain disabled unless separately chosen.

### Proposed success signals (targets, not measured results)

- Every model-free incident-replay case exposes owner/progress and an explicit running, delayed, unavailable, or unknown result; waits terminate within an agreed bound with a useful report.
- Self-identity cases never classify the current worker as a different owner. Duplicate dispatch/recovery and simultaneous-recovery cases never produce more than one effective writer.
- Heartbeat expiry, adapter failure, or ambiguous cessation yields uncertainty and no automatic reassignment. Continuation is allowed only after the agreed host boundary establishes safe exclusion/cessation or an explicitly human-directed alternative.
- Interruption/restart cases resume only from the latest checkpoint whose completion and evidence remain verifiable; invalid, stale, changed-file, changed-command, or dependency-invalidated evidence is not reported as complete, and unrelated edits are preserved.
- Every recovery approval presents, before the form, the decision/scope, artifact content or links, actual reviews/tests/sensors and their status, unknowns/limits, and exactly what approval allows and excludes. The package is readable without relying on color or links alone and supports keyboard and screen-reader use.
- A reproducible portable-package check and unrelated-project model-free scenarios demonstrate that host governance is preserved and optional packs do not become active implicitly.

These are candidate acceptance directions, not results from tests. No duration threshold, test execution, or implementation is asserted here.

## Options considered

| Option | Pros | Cons |
|--------|------|------|
| Keep manual saved-file recovery only | Minimal change; avoids unsafe automatic takeover | No durable owner/progress contract, bounded status, or repeatable proof against self-misidentification and duplicate work |
| Treat timeout/heartbeat expiry as worker death and reassign | Simple mental model; prompt recovery when the worker is truly gone | A timeout is diagnostic, not proof; may create concurrent writers, lost work, or corrupted state |
| Neutral recovery contract with thin host adapters and explicit uncertainty (recommended) | Portable; separates session continuity from ownership; supports bounded reporting and safe, evidence-backed continuation | Requires a trustworthy host contract for identity, execution exclusion, and human authorization; some hosts may only support a blocked/manual outcome |
| Expand immediately to parallel swarm and multiple orchestration harnesses | Broad future flexibility | Unneeded scope, more coordination and failure modes, and not required for this recovery increment |

## Recommendation

Explore the narrowly scoped neutral recovery contract with thin host adapters. Preserve useful existing foundations: session intent controls, read-only workflow dispatch, structured state, dependency-aware checkpoints, and approved verification, while making their limits explicit. Recovery must not be inferred from session continuity, repeated dispatch, timeout, or a worker's absence from a host listing. If a host cannot establish identity or safe exclusion, report the limitation and require a human-directed safe path rather than silently taking ownership.

Borrow concepts, not code, from prior parent research about `awslabs/aidlc-workflows`: a neutral core with thin harness adapters, bounded engine wait/report, construction dependency DAGs with explicit human autonomy grants, two-tier shared/role knowledge, and reproducible harness package checks. This provenance is conceptual and not fresh verified upstream research. No upstream code is copied, and this feature does not claim to implement all those ideas. Reuse the existing dependency/checkpoint foundation and narrow the package check to portability; defer knowledge restructuring and broader orchestration.

Recovery and approval information should distinguish **existing**, **proposed**, **verified**, and **unknown/deferred** facts. A human-readable review package must precede any approval form; a status message, actor string, or link list alone is not evidence that a human saw or authorized a decision. Any autonomy grant must be explicit, bounded, and revocable; its authority and provenance remain open questions.

## Scope and boundaries

**In scope for this increment:** durable worker ownership/progress and explicit uncertainty; correct current-worker identification; bounded wait/report; safe duplicate prevention and crash recovery; verified-checkpoint resume; host capability boundaries; model-free portable scenarios and package check; and evidence-first human approval presentation.

**Out of scope:** timeout-based automatic stealing; proceeding with concurrent writers under uncertainty; model invocation by the recovery engine; live-resource changes, deployment, or commit; advanced parallel swarm/multi-harness breadth; broad knowledge-system redesign; and claiming that current code or tests already provide the proposed guarantees. Existing project policies and the UC8 increment are not to be broadened or altered by this ideation.

## Existing evidence and assumptions

The repository currently has session intent operations in [`session.py`](../../speckit_flow/session.py) (park/unpark/redo and intent listing); workflow eligibility dispatch in [`orchestration.py`](../../speckit_flow/orchestration.py); atomically replaced individual state files in [`state.py`](../../speckit_flow/state.py); and dependency, approved-command, tracked-file stability, audit, and checkpoint handling in [`units.py`](../../speckit_flow/units.py). Individual atomic replacement does not establish mutual exclusion or a transaction spanning state, audit, and checkpoint files. Actor labels do not authenticate a human or prove that an approval package was seen. The portable bundle has an explicit allowlist and seeds optional plugins disabled in [`speckit-portable-bundle.json`](../../scripts/speckit-portable-bundle.json).

Related existing tests are [`test_flow_session.py`](../../tests/unit/speckit_flow/test_flow_session.py), [`test_flow_orchestration.py`](../../tests/unit/speckit_flow/test_flow_orchestration.py), [`test_flow_units.py`](../../tests/unit/speckit_flow/test_flow_units.py), and [`test_speckit_bootstrap.py`](../../tests/unit/test_speckit_bootstrap.py). Their existence is not evidence that they were run or that they cover these proposed guarantees; no tests were run for this ideation stage. No worker-ownership or liveness contract has been verified here.

Assumptions for discussion: recovery should prefer safety over availability when ownership or cessation is uncertain; a host adapter may be unable to provide required capabilities; verified progress is distinct from merely saved files; and unrelated receiving projects must retain local governance. A filesystem/process boundary, safe retention period, human-authorization provenance, and any host-specific identity/exclusion guarantees remain unestablished.

## Open questions and risks

- **role: question** - What host evidence and execution-exclusion boundary can be trusted to distinguish running, delayed, unavailable, and unknown from safely ceased, and what maximum wait/report bound should operators expect?
- **role: question** - What exact evidence makes a saved checkpoint verified and resumable, and which changes (artifacts, dependencies, commands, or reviews) must invalidate it?
- **role: question** - Which recovery actions, if any, may proceed under a human autonomy grant without per-action approval, how is the human's authorization provenance established, and how can that grant be bounded and revoked?

Other unresolved risks include host support for single-writer enforcement, interruption between separate state/audit/checkpoint writes, preserving unrelated user edits, and retention/privacy of worker identity and progress. Where a safe answer is unavailable, the expected direction is an explicit blocked/unknown state, not an invented capability or automatic takeover.

Ideation is not an approved design, specification, implementation, or lifecycle gate. No concept diagram was created because prose is sufficient to compare the options and record the unresolved host boundaries.
