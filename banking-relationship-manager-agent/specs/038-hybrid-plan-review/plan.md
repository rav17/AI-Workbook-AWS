# Implementation Plan: Hybrid Plan Review

**Feature**: 038-hybrid-plan-review | **Date**: 2026-11-14 | **Spec**: [spec.md](./spec.md)

## Summary

Add a separate, opt-in hybrid route: a host performs the plan stage inline,
then invokes the operator-selected eligible independent reviewer. Keep all
existing profiles and their execution, gates, sensors and review behavior
unchanged. This feature is being developed using the separately confirmed
`quick` profile; that does not change the intended hybrid route's gates.

The existing dispatcher chooses a profile-wide execution mode, and
`calls.py` requires a delegated lead. Extend those existing mechanisms rather
than creating a second orchestrator. Human confirmation and approved gates
remain authoritative.

## Technical Context

- Python 3.11+, existing standard-library CLI and pytest; no new dependency.
- Project root: `banking-relationship-manager-agent`; Copilot host with named
  agents. Other host adapters and automatic risk selection are out of scope.
- State, route, call and review evidence are feature-local files and
  hash-chained audit events; store safe metadata, not raw prompts or plans.
- No live services, deployment, customer-record changes, payment actions, or
  retention/access-policy changes.
- Preserve unrelated existing work. Treat host capability, invocation evidence,
  permissions and accessibility as separate claims requiring actual evidence.

## Constitution Check

- Persist workflow decisions and evidence in typed structures; fail explicitly
  on invalid, missing, stale, unavailable or contradictory evidence.
- Restrict reviewer to an eligible, separately invoked worker; actor strings,
  a successful reservation and prompt instructions are not authentication or
  proof of execution, tool enforcement, private reasoning or input delivery.
- Keep audit data minimal and redact secrets; tests use synthetic fixtures.
- Maintain bounded calls, no automatic retries or concurrent overlapping writers.
- Run focused deterministic tests; use a real host smoke test to validate
  invocation rather than treating mock/CLI results as host evidence.

Post-design check: no intentional constitutional violation. The host boundary
is a constraint, not a security guarantee; fail closed if the required
observable input/invocation evidence cannot be established.

## Design and Decisions

1. **Opt-in route and selection (FR-001, FR-002, FR-008).** Introduce a new
   explicit hybrid configuration/profile without modifying the existing
   feature, bugfix or quick defaults. Preserve specify and plan human gates.
   The operator selects one configured plan-reviewer from the eligible roster
   before initialization; missing, ineligible and author selections fail
   explicitly. Persist the confirmed choice and route so resume and later
   configuration changes cannot silently change the selection. Do not select
   or replace a reviewer automatically.
2. **Stage execution (FR-002, FR-007).** Extend profile parsing and
   `workflow dispatch` so the plan lead can execute inline while the selected
   reviewer remains a separately assigned worker. Other stages keep their
   explicitly declared behavior. Have the top-level host invoke the selected
   reviewer directly without requiring nested agent invocation. Preserve
   existing stage ordering, locks, bounded calls, actual invocation outcome,
   failure handling and audit integrity. Extend the ledger only as needed for
   an inline lead; no synthetic worker call for the main assistant.
3. **Input and result evidence (FR-003--FR-005, FR-009--FR-011).** Associate
   the real reviewer invocation with the selected reviewer, reviewed plan
   fingerprint and a minimal safe manifest of supplied input references and
   fingerprints. Only the plan and expressly approved stage context are
   eligible; author notes and verdict are excluded. Compare the manifest to
   the host-observable invocation input. Missing, inconsistent or unverifiable
   evidence fails closed. Do not claim that a self-reported manifest proves
   what the host actually delivered or what the reviewer privately reasoned.
   If this host cannot expose the required invocation-input evidence, report
   the limitation and do not claim a successful hybrid review.
   The approved read-only named-worker smoke test established local Copilot
   invocation, child-user-input and completion events. The `copilot-events-v1`
   adapter correlates these records, permits only the observed timestamp
   expansion, and requires zero observed worker tools. It stores source and
   reservation references plus fingerprints, not raw conversation contents.
   Source selection requires an actual human decision and is audit-bound.
   Verification re-reads the source at completion and gate; no new retention
   rule or authentication guarantee is introduced. Host-managed system
   instructions and private model context are outside this observable boundary.
4. **Review and gate validation (FR-004, FR-005).** Reuse the current
   source-bound review records and `reviews.py` validation. Accepted verdicts
   are the existing `pass`, `concerns` and `block`; anything else or an
   incomplete result is invalid. An invocation's `succeeded`/`failed` status
   is separate from the verdict. At stage completion and again at the plan
   gate, require the selected invocation and a valid current review bound to
   the exact plan fingerprint and input evidence. `concerns` remains visible
   to the human; `block` follows existing human override policy. A later plan
   edit invalidates the review. Existing sensors and human decisions remain
   required.
5. **Status and accessibility (FR-006).** Expose distinct, plain-text status,
   failure reason and next action for the ten specified cases; include invocation
   outcome, verdict, findings/location and freshness when applicable. Verify
   keyboard and screen-reader access in the actual host where available.
   CLI/unit output alone is not evidence that assistive-technology checks passed.
6. **Host protocol and portability.** Update the workflow skill and conductor
   instructions so the host invokes only the selected reviewer with a
   self-contained minimal brief and records actual outcomes. Keep existing
   permission restrictions and failure stops. Update the portable bundle and
   guide for any added configuration files; do not export project-specific
   approvals, rules, or sensitive data.

## Project Structure and Practices

- Engine: `speckit_flow/models.py`, `orchestration.py`, `calls.py`, `state.py`,
  `reviews.py`, and `cli.py`; reuse the roster in `agents.py`.
- Integration: `.github/skills/speckit-workflow/SKILL.md`, relevant reviewer
  instructions, `.specify/profiles/`, `docs/speckit-profiles.md`, and portable
  bundle manifest where needed.
- Tests: existing `tests/unit/speckit_flow/test_flow_orchestration.py`,
  `test_flow_calls.py`, profile, review and gate tests; portable installer
  tests if the bundle changes.
- `codebase practices` source fingerprint:
  `c15e2429aed98c551e2d3fa157c3c9b6463366938d760b26ef2b0912817df391`.
  This is a fingerprint, not validation. `pyproject.toml:5,20-25,38-54`
  declares Python and test/lint tools; `.github/workflows/quality.yml:34-40`
  documents project CI checks. Project conventions use typed Python,
  explicit `FlowError` failures and pytest temporary-path fixtures.

## Verification Plan

From the project root, run focused tests for profile/dispatch, call accounting,
review and gate paths in one pytest invocation; add precise selectors for any
changed portability tests. Run affected-file Ruff checks and formatting checks.
Run broader affected checks if shared behavior fails. Exact proposed command:

```powershell
python -m pytest tests\unit\speckit_flow\test_flow_orchestration.py tests\unit\speckit_flow\test_flow_calls.py tests\unit\speckit_flow\test_flow_profiles.py tests\unit\speckit_flow\test_flow_reviews.py -q
```

Tests must cover opt-in and unchanged existing routes; selection errors;
unavailable, failed, duplicate and interrupted workers; missing/unverified/
inconsistent input evidence; malformed results; current and stale review;
gate behavior; actual call outcome versus verdict; safe metadata; and resume.
Before any construction checkpoint executes a verification command, separately
obtain human approval for the exact command under the existing verify policy.

For live host evidence, obtain permission for a read-only named-reviewer smoke
test against synthetic fixtures. Inspect actual tool activity, supplied inputs,
result and host restrictions. If unavailable, explicitly report unverified
host behavior and block the hybrid success claim. Evaluate keyboard and screen
reader checks against the actual host when available; otherwise report them as
not verified. No tests or smoke checks are claimed as passed by this plan.

## Risks and Boundaries

- A host may not expose independent proof of supplied inputs or enforced tool
  restrictions. The engine is not a host interceptor; do not weaken FR-003 to
  a self-attestation or claim a security boundary.
- `reviewer` in existing review records is a category, not worker identity;
  bind the selected worker and real invocation separately.
- Existing checkpoint/call ledger and workflow files contain uncommitted user
  changes; integrate them and do not reset or overwrite them.
- No independent plan review is claimed for this feature's `quick` workflow.
  Separate research, data-model, contract and quickstart artifacts are omitted
  for quick; the design and validation contract are recorded here.
