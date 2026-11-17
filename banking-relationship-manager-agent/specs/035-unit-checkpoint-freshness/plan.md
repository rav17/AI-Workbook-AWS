# Plan: freshness-aware construction units

## Design and compatibility

Extend units.py rather than adding a scheduler/service. Evaluate the validated
dependency DAG in dependency order, memoizing one assessment per unit. A unit
with missing/unverified dependencies is blocked; existing evidence with changed
inputs is stale; a pending unit with satisfied dependencies is ready; matching
evidence is verified. Reasons and blocked_by remain available when stale takes
precedence over blocked.

Checkpoint records retain at/actor/command/files/definition and add dependency
evidence digests and an audit-sequence revision. Always save definition, files
(possibly empty) and dependency snapshots. Legacy records without these fields
are stale until recheckpointed; no silent metadata upgrade. Untracked units
remain supported but coverage is explicitly command-only, not source freshness.
Report policy failures as reasons and file-access problems explicitly. Malformed
unit/checkpoint containers and invalid DAGs fail with FlowError, not raw crashes.

Before any recheck, remove old evidence. Require dependencies currently verified,
snapshot their revisions, run the existing approved command, then reassess inputs
and dependencies. Failure never preserves the old pass. Implementation gates
use default project verification policy; custom paths apply to explicit unit
CLI commands and reporting only. No required sensor or final test is skipped.

## Change surfaces

speckit_flow/units.py, CLI unit listing, state gate error handling, unit/skeleton/
gate regression tests, portable smoke test and docs/speckit-profiles.md.
Reuse _file_paths, tracked_fingerprints, _definition and approved_command.
Do not change profiles, prompts, application code or existing initialized work.

## Project practices

Root: banking-relationship-manager-agent
Fingerprint: fbc67b2038985355d110429bd692be8683bbd463d79b93770f5c40098c4f6e08

Evidence: pyproject.toml Python 3.11+, Ruff E/F/I/UP and strict mypy configuration;
existing tests/unit/speckit_flow/test_flow_units.py and test_flow_skeleton.py
provide pytest/temporary-project patterns. Existing dictionaries are retained
for compatible metadata; explicit boundary validation and deterministic tests
compensate rather than introducing a new model framework into this engine.
The application constitution's safety, boundedness and invalidation principles
are preserved; no banking data or services are involved.

Run from project root:
- python -m pytest tests/unit/speckit_flow/test_flow_units.py tests/unit/speckit_flow/test_flow_skeleton.py -q
- python -m pytest tests/unit/speckit_flow -q
- python -m pytest tests/unit/test_speckit_bootstrap.py::test_install_is_portable_and_target_doctor_passes -q
- python -m ruff check speckit_flow scripts
- python -m mypy speckit_flow/units.py speckit_flow/cli.py speckit_flow/state.py --follow-imports=silent

Configured implementation sensors also run Ruff and tests/unit. Disclose
pre-existing unrelated failures rather than editing unrelated code.

## Separate delegated trial

After implementation use one actual read-only subagent on an isolated fixture
to exercise verified/ready/stale/blocked states and report concrete outputs.
Invoke a configured custom conductor only if supported by the host. Otherwise
label this an ordinary delegated worker trial, not a lifecycle/custom-agent
orchestration test. One invocation, no retries or recursive delegation.

## Risks

Freshness covers only declared files/dependencies/commands, not external service
state or an unchanged command's undeclared scripts. Old evidence becomes stale
intentionally. Status is advisory readiness, not permission to bypass gates or
edit shared files concurrently. Independent review is not enabled for quick.

## Actual implementation and validation results

- Implemented shared DAG freshness evaluation in units.py; CLI reporting,
  dependency admission, skeleton checks and implementation gates use it.
- New checkpoints store definition, file hashes, approved command, dependency
  evidence digests and audit-sequence revision. Failed rechecks invalidate old
  evidence, including command-only units; no test cache or scheduler added.
- Lifecycle suite and portable installation smoke test: **485 passed, 8 skipped**
  (Windows symlink privileges and unavailable specify_cli integration imports).
- Ruff over engine/scripts/changed tests passed; mypy over units/CLI/state passed.
- Configured implementation sensors: lint **pass**, full tests/unit **pass**,
  both exit 0. The sensor wrapper does not return the full unit-test count.
- Graphify AST-only update succeeded; no remote semantic extraction was used.
- Direct inspection found no additional discrepancy with the declared scope;
  this was self-review, not independent review.
- Final task checkbox/result annotations were added after sensor execution;
  those annotations are not a fresh sensor pass and implementation code did
  not change afterward.

### Separate delegated worker trial: failed harness execution

Invoked a generic `task` worker named `freshness-trial`, synchronously.
Session-log inspection subsequently showed that it launched another task worker
despite the no-nesting instruction. The earlier claim of no recursive delegation
was incorrect. There were two worker invocations, with no retry after failure.
The brief requested execution of four
temporary-fixture scenarios from test_flow_units.py:

1. test_ready_reporting_is_read_only_and_never_executes
2. test_stale_source_propagates_and_requires_dependent_recheck
3. test_dependency_must_be_fresh_before_command_runs
4. test_cli_custom_policy_json_and_text

The worker reported **exit 4, zero tests run, 0.77 seconds**, with a test-path-not-
found error. Its returned command used relative paths; it did not demonstrate
successful execution from the requested working directory. The innermost shell
command omitted Set-Location and used relative test paths. No review loop
occurred, but the unexpected second worker violated the bounded trial brief.

The parent ran exactly those four scenarios after explicit Set-Location to
the project root: **4 passed in 4.41 seconds**. This confirms those assertions
directly, not successful delegated execution. Fixtures and verification
approvals are synthetic and temporary; no real project verification policy
was approved by a worker.

The host exposes generic worker invocation but no configured custom-agent
invocation tool. Neither speckit-conductor/nested roster-agent dispatch nor
independent review was verified. Thus T005 records a completed bounded trial
attempt with a failed outcome, not successful delegated verification. Token/
time savings remain unmeasured; no production/application behavior was changed.

### User-requested correction and successful worker rerun

After the user asked to fix the path/nesting failure:

- Dispatch now includes absolute project_root and feature_dir. The conductor
  contract requires explicit cwd in every shell invocation, test-file existence
  checks, direct configured-worker selection and preservation of tool restrictions.
  The existing roster validator rejects the agent tool on non-conductor workers;
  regression coverage checks all current roster workers retain that restriction.
- Generic task-runner wrappers are explicitly not substitutes for custom
  lifecycle dispatch. Generic trials require direct execution and tool-call
  inspection; a prompt prohibition alone is not hard enforcement.
- Orchestration and portable-install regressions: **50 passed, 2 skipped**
  (unavailable specify_cli imports). Ruff and mypy passed for changed Python.
- A new, explicitly user-authorized trial used a direct general-purpose worker,
  not the previous task-runner wrapper. Its single PowerShell call contained
  Set-Location -LiteralPath with ErrorAction Stop and an absolute Test-Path guard,
  then ran the same four synthetic-fixture tests: **4 passed in 4.81 seconds,
  exit 0**.
- Session-log inspection confirmed **one worker identity, one shell invocation,
  zero nested delegation calls** for the corrected trial. The actual command
  and output confirmed the intended project directory. This is observed evidence
  for this run, not a guarantee about future unrestricted generic workers.

This corrects the earlier failed-trial result without rewriting its history.
Full configured speckit-conductor/nested roster-agent execution remains untested
because this host does not expose custom-agent selection. The successful generic
worker rerun is not independent review or validation of that unavailable path.
These follow-up checks occurred after the earlier implementation sensor run;
the earlier sensor passes are not claimed as verification of the follow-up.
