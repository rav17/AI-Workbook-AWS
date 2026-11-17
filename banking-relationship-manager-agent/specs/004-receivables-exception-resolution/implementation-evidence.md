# UC8 bounded implementation evidence - implement-5 / implement-6

Date: 2026-11-11. Actor: `agent:developer`. Delegated stage: **implement only**.
This supersedes stale W11 labeling, fixed-clock demo evidence and earlier verification totals.
It is evidence, not human acceptance or full FR-001 conformance. No workflow transition,
gate/review/rule/state edit, commit, network, real model or AWS operation occurred. Only
approved local synthetic task writes were exercised in isolated test databases.

## Preserved approval bindings

[Approval provenance](approval-provenance.md) is unchanged. Before/after SHA-256 values:

| Artifact | SHA-256 (unchanged) |
|---|---|
| `plan.md` | `3637a2f0f0049a0b7bb9f973352dc181763733c33e4174fd3ac80ab8f51169ae` |
| `quickstart.md` | `110652d9d77360132726c2f2ce55d08c632623d530c257b031384ee9918a6431` |
| `synthetic-policy.md` | `effcaaa811c072e11c3ded05d06648f01f0246fd6c1476fac943d523f7a34734` |
| `synthetic-fixtures.json` | `fa4349323cf23f6ba3d29c0c2b4e1cfa7f0e1144fd0b00ad1c80d768b76dad64` |

No policy value, fixture case, label, denominator or approved command changed. Historical
plan/quickstart proposed/unimplemented prose remains read-only; current status is recorded
here, in tasks.md and in the diagram register.

## Bounded corrections

### Atomic linked revision - T017/T019/T020

`service.decide(REVISE)` first prepares deterministic investigation without persisting an
analyst decision. `store.record_decision(..., revised=...)` validates current version and
exact next-version/payment/exception identity under BEGIN IMMEDIATE. It commits the old
proposal's append-only decision, state revision, immutable new proposal, decision audit
link (old and new IDs in source_refs) and new proposal audit in one transaction. Standalone
REVISE without a prepared proposal is refused.

Investigation/retrieval-audit failure leaves old workflow state untouched. Decision audit,
proposal audit and proposal INSERT failures roll back every revision write; no revision
success is returned/audited. Preparation retrieval/check events may already be durable;
they are not revision success. After failure, retry the same old proposal ID. After a
successful commit, another request against that old ID is rejected as stale, not replayed.
There is one valid revision, no duplicate decision/task, and the new revision needs fresh
approval/confirmation. Previously committed tasks remain immutable/create-only.

Five injected failure cases assert unchanged old state/proposal, no partial revision/link
success, one valid retry, an immutable audited link, stale rejection of repeat and one
created/replayed task after new approval.

### Bounded status output - T007/T008

`get_proposal_status` converts BaseModel/dict/scalar to a result, serializes it and enforces
MAX_TOOL_OUTPUT_CHARS uniformly. A real SDK decorated tool using the scripted model-free
seam checks oversized BaseModel, dictionary and scalar values, JSON escape expansion,
small valid output and zero model calls. No Runtime integration was added.

### Exact W11 and separate retrieval fault - T017/T022/T023

All14 aggregate W11 uses the same real SQLite BEFORE INSERT audit trigger as the separate
transactional regression. It fires on confirmation audit only after the task INSERT and
state change to task_created. Service returns unconfirmed; task/state roll back and no
confirmation/task-result success audit persists. Removing the trigger and retrying the
same displayed binding creates one task; exact replay returns it. W11 measures 21 reads,
32 committed events, one failed audit INSERT attempt and one rolled-back task INSERT.
The failed event did **not** persist.

The original Python retrieval-audit sink failure remains a separately named unit subcase
and `separate_retrieval_audit_failure` in the measured JSON, excluded from all14. At failure
it records 8 reads versus 7 persisted retrieval events, zero tasks and unconfirmed. Its one
rejected payment event remains missing even after retry creates one task. No missing failure
event is claimed persisted. This is not a SQL attempt: the sink fails before SQL execution.

### Interaction diagram - T030

Only [interactions.drawio](architecture/diagrams/interactions.drawio) and
[index.md](architecture/diagrams/index.md) changed. Default demo passes payment_id plus
harness context directly to the deterministic engine; exception_id-only trusted closure
belongs to the separate optional injected Strands child. The view records atomic revision/
retry and existing rollback. Other views are unchanged. Runtime/deployment remain deferred;
atomic external freshness remains unknown. Neutral editable shapes depict local components;
no provider icon is needed or unavailable. XML validation is not semantic/human approval.

### Actual default-composed advancing WSGI journey - T021/T023

The test calls `app.main` with only isolated storage and controllable monotonic time,
intercepting serve_local to avoid starting a listener. It uses the service/context actually
assembled by main and asserts engine/service/store share its LogicalDemoClock, not the
engine fixed-clock default. Requests traverse real WSGI: GET /, POST investigate, approve/
display exact payload and confirm. One second elapses before approval; no task exists until
confirmation. After another 31 minutes, exact committed retry replays the same one task.
Main journey/replay: 14 reads, 23/23 events, 14/14 retrieval matches, 2/2 proposal audits.

Two independently main-composed stores test stale retries: confirmation at 11 minutes
exceeds the approval window; approval at minute 29 then confirmation at minute 31 isolates
original proposal TTL expiry while the 10-minute binding is still live. Each retries twice,
reports no success and creates zero tasks. They are captured separately, not added to main
counters. No sleep, real model, network or AWS is used. This is in-process WSGI coverage,
not browser/HTTP-listener/accessibility certification.

## Final exact approved checks

Seven command strings, exit codes, current source hashes, captured E/W/demo outputs and
intermediate failures: [implementation-measurements.json](implementation-measurements.json).
All commands use `.\.venv311\Scripts\python.exe`; none was edited in quickstart.md.

| Check | Final result |
|---|---|
| Five receivables unit modules | 95 passed in 29.47s |
| Two receivables framework modules | 12 passed in 3.85s |
| Receivables property module | 3 passed in 2.38s |
| Five existing-boundary regression modules | 39 passed in 7.55s; one third-party Pydantic deprecation warning |
| Scoped Ruff lint | All checks passed |
| Scoped Ruff format check | 16 files already formatted |
| Scoped mypy | No issues in 15 source files |
| Diagram validation | 4 draw.io diagram(s) valid |

**149 pytest cases passed.** Intermediate construction checks found a malformed test string,
test import/line formatting and two failing TTL-form attempts (one non-recommending payment,
then missing required exception_type). Those setup defects were corrected; final checks
pass. One documentation-update attempt failed on Windows default cp1252 decoding before
any file write; retry used explicit UTF-8. No unresolved bounded implementation error remains.

## Current measurements and scope limits

E remains 57 cases: 52 catalogue investigations (364 reads) plus five zero-read guards;
four engine guard proposals and one router-only guard. There are 56 returned proposals,
472/472 matching audit events, 939/939 valid citation trace entries and all 102 supplied
reason/variance/duplicate/prior-allocation labels match. Synthetic metric counts remain
SC001 50/50 (two unscored), SC002 13/13, SC003 13/13 (incorrect 0/13), SC004 required 36/36
(false escalation 0/16), SC005 13/13. Dispositions: recommend 13, escalate 36,
no_recommendation 3; errors 0 and abstentions 39. E uses an in-memory sink; SQLite writers
are unexercised in E, not passing zeros.

W now executes the exact 14 scenarios: 189 reads (27 per evidence type), 27/27 proposal
audits, 189/189 retrieval matches, 297/297 committed audit events. All 14 scenario sets
match. Committed rows sum to proposals 15, states 14, decisions 19, bindings 14, tasks 7,
audit 297. DML attempts/returns: 398/395, including two denied task UPDATEs and one failed
audit INSERT; eight returned task INSERTs include one rolled back, leaving seven committed
tasks. SQL returns are not commit counts. W14's extra proposal-TTL subcase remains outside
this main aggregate.

`graphify update .` completed AST-only after final code changes. Last topology:
4702 nodes, 9868 edges, 346 communities; final refresh detected no further topology changes.
Existing community labels remain stale; no model-based relabeling was performed.

All 37 existing tasks remain checked. Harness-only partial FR-001 is the approved scope,
not full Runtime conformance. Freeform rationale remains bounded local synthetic-only text,
without a sensitive-content filtering guarantee. External freshness is not locked with SQLite
commit. Runtime registration, production authority, live integration, deployment, browser/
accessibility certification, security/dependency scanning and global write safety remain
deferred or unmeasured. Conductor handles independent reviews and sensors; only a human
approves gates and learned rules.
