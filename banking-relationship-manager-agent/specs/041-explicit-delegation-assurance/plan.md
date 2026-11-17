# Implementation Plan: Explicit Delegation Assurance

**Feature**: `041-explicit-delegation-assurance` | **Date**: 2026-11-17
**Spec**: [spec.md](spec.md)
**Route**: Human-confirmed selective; inline stages, independent architecture
plan review, human specification and plan gates.

## Summary

Add a small, human-only acceptance operation and read-only assurance inspection
for ordinary development delegation. Bind acceptance to the existing audit
history, stage, host/session and configured named workers. Amend the conductor
to allow the accepted missing-evidence case, without claiming verified isolation
or changing tool permissions. Defaults remain fail-closed at invocation.

### Observed root cause and reusable components

- Feature 039 dispatch returned `ready`, `implement`, `pending`, with no human
  gate. Ordinary dispatch checks eligibility, not runtime host permissions:
  [orchestration.py](../../speckit_flow/orchestration.py), `dispatch`.
- The present blanket stop is in the conductor's Worker tool compatibility
  diagnostics and its matching profile guide. Feature 040 deliberately retained
  it; changing diagnostics alone cannot unblock 039.
- [agents.py](../../speckit_flow/agents.py), `_check_agent_file`, validates that
  only the conductor declares the delegation tool. Reuse its roster validation
  and assignment resolution, not a parallel agent registry.
- [host.py](../../speckit_flow/host.py), `authorize_source` and
  `has_no_tool_capability`, are hybrid-only. Do not repurpose that adapter or
  access raw host logs for this change.
- [audit.py](../../speckit_flow/audit.py), `append_event`/`snapshot`, provides
  bounded, redacted, hash-chained operational records. Reuse this history
  without adding a separate mutable acceptance file.

## Technical Context

**Language/Version**: Existing Python 3.11+ CLI; no new dependencies.
**Storage**: One new event type in the existing feature audit, not a new store.
**Testing**: Existing pytest, Ruff and mypy; focused behavior/regression cases.
**Target Platform**: Existing Windows/PowerShell project and portable CLI.
**Scope**: CLI, assurance evaluation, inspection output, guard, conductor/docs,
audit schema and portable inclusion list. No application or IAM changes.
**Performance**: Local file reads only; no network, polling or background service.

## Design

1. Add `speckit_flow/assurance.py` to centralize scope construction, acceptance
   validation and read-only status. Reuse effective profiles, roster assignments,
   frontmatter validation and the existing audit stream.
2. Expose `workflow assurance accept` (human terminal only) and
   `workflow assurance status` (read-only). Both require an explicit stage,
   non-sensitive host label and session id. Acceptance additionally requires a
   bounded rationale and explicit confirmation that the work is ordinary and
   does not require verified isolation.
3. Store only a bounded acceptance event: host/session identifiers, grouped
   scope digest, short rationale, sanitized observation, missing-evidence text,
   residual-risk text and schema version. Its stage and actor use
   existing event fields. The digest covers the resolved feature, effective
   profile/assignments and full assigned-agent/conductor definitions. The
   current redo/reset boundary participates; normal pending-to-started movement
   must not invalidate an acceptance recorded before starting the stage.
4. Status validates the audit and current scope before returning
   `unverified_accepted`. Missing/stale acceptance is non-authorizing and
   explicit; malformed events or corrupt audit raise standard errors. Never
   produce a `verified` result from this operation.
5. Restrict eligibility to ordinary work on `feature`, `bugfix`, `refactor` and
   `selective`, and their core pre-release stages through implementation.
   Strict modes, deployment/operations and unknown/custom profiles cannot use
   the exception. Profile membership never replaces human risk assessment.
6. Dispatch/next inspection exposes a non-authorizing assurance summary.
   Inspection without current host/session input must say context checking is
   required, never imply that a stored acceptance is currently valid.
   Keep existing dispatch eligibility semantics: `ready` is not invocation
   permission or evidence of host enforcement.
7. Before delegated invocation, the conductor checks assurance using the actual
   current host/session metadata. A current acceptance may replace only the
   missing-runtime-proof stop. Known unavailable capabilities, failed named
   selection, observed forbidden delegation, gates, call failures/budgets,
   reviews and required checks remain separate stops. No generic substitution.
8. Extend the guard's human-decision detection to the acceptance operation;
   agents may inspect status but cannot record acceptance. Update the audit
   event enum/schema and portable module list. No agent frontmatter changes.

### Freshness, compatibility and limitations

Acceptance is scoped consent, not host authentication or a sandbox. Host/session
identifiers come from disclosed host metadata, not raw-log inspection. For this
Copilot SDK session, the host supplies the exact SDK conversation identifier in
session context; preserve that identifier rather than substituting a protocol,
editor, cloud-history or newest-on-disk id. The human acceptance package states
that source. Other hosts must expose their own current identity; if the current
context cannot be identified, stop rather than inventing it. Equality checks
validate only the disclosed/attested context, not an authenticated host identity
or an independently detected session change. A changed
scope or retry/reset requires new acceptance. Existing stage history/routes are
not migrated, rewritten, approved or resumed. The new event is ignored by state
projection except for assurance inspection; existing event meanings stay intact.

### Bootstrap and decision trust model

Feature 041 does not use its own new exception. Its implementation stage runs
entirely in the inline host with no assigned support or reviewer calls:
see the confirmed `selective-route.json` and the existing selective procedure
in [the profile guide](../../docs/speckit-profiles.md#opt-in-selective-execution-and-engine-directives).
There is no implementation worker boundary or conductor invocation to waive.
The one named plan reviewer uses the already-existing selective operational
review contract, which explicitly does not certify host tool enforcement.
If an actual capability required by that route is unavailable, stop; do not
treat a plan approval as isolation acceptance or an authorization to substitute.

The acceptance operation uses the repository's existing human-terminal decision
trust model, not a new identity/authentication claim. The human personally
executes it after the review package; the host checks the persisted result.
Reject explicit agent actors and deny this decision through agent tools in the
guard, regardless of a forged `human:` argument. Those controls cover the normal
supported workflow, not adversarial processes or concealed shell execution.
Actor labels alone cannot prove who ran a command. A compromised host, arbitrary
local process or dishonest metadata is outside this operational audit model;
work needing authenticated decisions or verified isolation remains ineligible.
Do not present any test of actor validation as authenticated-human evidence.

Observed tool violations remain operational stops, not something the new module
can reliably detect without host evidence. The policy must state this limitation.
Known failures cannot be erased by issuing acceptance; normal dispatch/recovery
preflight and the host's observed-failure stop precede any exception.

## Constitution Check

Pre-research and post-design: no application-authorization exception. Principles
I/III retain authoritative lifecycle state and patch semantics. Principle II
is preserved: neither visible tools nor acceptance is treated as an application
security boundary. Principle IV retains bounded calls. Principles V/VI retain
session scope, explicit errors, typed code, redaction and focused verification.
This plan is the relevant architecture record for the workflow-assurance
trade-off; the assigned reviewer must independently assess that boundary.

## Project Structure

- New: `speckit_flow/assurance.py`; `tests/unit/speckit_flow/test_flow_assurance.py`.
- Update: `speckit_flow/cli.py`, `orchestration.py`, `models.py`,
  `scripts/speckit_guard.py`, `scripts/speckit-portable-bundle.json`, and
  `specs/009-workflow-profiles-audit/contracts/audit-event.schema.json`.
- Update guidance: `.github/agents/speckit-conductor.agent.md`,
  `.github/skills/speckit-workflow/SKILL.md`, `docs/speckit-profiles.md`.
- Focused existing tests: `test_flow_orchestration.py`, `test_flow_guard.py`;
  use existing audit/agent/bootstrap suites for compatibility.
- Design artifacts: [research.md](research.md), [data-model.md](data-model.md),
  [CLI contract](contracts/assurance-cli.md), [quickstart.md](quickstart.md).
  `tasks.md` will be generated only after human plan approval.

## Project Practices and Verification Proposal

Root: `C:\Users\RavindraYadav\Documents\AI-Workbook-AWS\banking-relationship-manager-agent`.
Practices fingerprint: `7991a8ad9448a559fcca3356e346903c6f4069ac4231fba6af5b8c6fb698c5fc`.
Sources: [pyproject.toml](../../pyproject.toml), lines 5, 40-63 (Python floor,
pytest root, 100-column Ruff and strict mypy);
[quality.yml](../../.github/workflows/quality.yml), lines 43-50 (existing
format/lint/type/test commands). Reuse typed, explicit-error CLI patterns.
Do not install tooling without a missing-dependency failure.

Proposed focused commands, from that root, subject to human verification approval:

```powershell
python -m pytest tests\unit\speckit_flow\test_flow_assurance.py tests\unit\speckit_flow\test_flow_orchestration.py tests\unit\speckit_flow\test_flow_guard.py tests\unit\speckit_flow\test_flow_audit.py tests\unit\speckit_flow\test_flow_agents.py tests\unit\test_speckit_bootstrap.py -q
python -m ruff check speckit_flow\assurance.py speckit_flow\cli.py speckit_flow\orchestration.py speckit_flow\models.py scripts\speckit_guard.py tests\unit\speckit_flow\test_flow_assurance.py tests\unit\speckit_flow\test_flow_orchestration.py tests\unit\speckit_flow\test_flow_guard.py
python -m ruff format --check speckit_flow\assurance.py speckit_flow\cli.py speckit_flow\orchestration.py speckit_flow\models.py scripts\speckit_guard.py tests\unit\speckit_flow\test_flow_assurance.py tests\unit\speckit_flow\test_flow_orchestration.py tests\unit\speckit_flow\test_flow_guard.py
python -m mypy speckit_flow\assurance.py
```

Also run required stage sensors, Pylance syntax validation on changed Python,
and AST-only `graphify update .` after implementation. No live host isolation
test, raw logs, external package assembly or deployment is included.

### Acceptance mapping and known baseline

FR-001--FR-004: human-only acceptance, scoped status and eligibility tests.
FR-005--FR-007: strict/excluded modes, human-decision guard, unchanged hybrid,
gate/accounting and actual-failure regression cases.
FR-008--FR-010: honest inspection and conditional conductor guidance, no
automatic changes to initialized features.

No new implementation tests have run. The prior 040 affected-file suite passed
76 with 2 skips; formatting and wider lint/unit sensors failed. Those historical
results are not validation of 041, and their causes are not all established.
Preserve unrelated dirty-worktree edits and report baseline failures separately.
