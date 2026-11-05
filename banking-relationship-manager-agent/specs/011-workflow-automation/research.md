# Research: Spec Kit Workflow Automation

## Workflow engine capabilities

**Decision**: Use the existing workflow engine's `shell`, `gate`, and `if` steps. Shell steps capture stdout/stderr and fail when their process returns non-zero; conditional expressions can inspect a gate's `steps.<id>.output.choice`.

**Rationale**: These are already supported by the installed engine and avoid modifying or wrapping Spec Kit's dispatch engine. The `gate` step's `on_reject: skip` mode allows a following conditional branch to record the rejection in `speckit_flow` before a deliberate non-zero exit stops the workflow.

**Alternatives considered**:
- Continue using only conversational gates: rejected because decisions would not be recorded in the lifecycle audit trail.
- Modify the Spec Kit engine: rejected because it is an external dependency and would break the shared deterministic workflow.
- Make every orchestration action a new agent command: rejected because the lifecycle transitions are deterministic local operations and should remain in the existing CLI.

## New-feature bootstrap

**Decision**: Begin lifecycle initialization in a workflow shell step immediately after `speckit.specify` returns, then start and complete `specify` before the first approval gate. Later stages are wrapped directly in `workflow.yml`.

**Rationale**: The feature directory does not exist until the specify command runs, so a workflow shell step before that command cannot resolve the current feature safely. Once the command returns, `.specify/feature.json` points to the new feature and the workflow can safely initialize tracking before planning.

**Alternatives considered**:
- Initialize the current feature before running specify: rejected because `.specify/feature.json` may still point to the previously active feature.
- Modify the specify skill to start tracking before authoring: rejected because that would make tracking apply to direct skill invocations and could conflict with non-default profiles managed through `speckit-profile`.
- Leave specify untracked: rejected because it would make the audit trail incomplete.

## Idempotent workflow preparation

**Decision**: Add `python -m speckit_flow workflow begin --stages ... --gates ...`, which initializes the default feature profile only when no state exists. On existing state it verifies the audit chain and requires the profile's route and gates to match the workflow's declared route. It does not repair or overwrite corrupt/incompatible state.

**Rationale**: A single deterministic command safely handles first use and prevents the static standard workflow from silently tracking a different profile.

**Alternatives considered**:
- Make `init` overwrite or silently accept existing state: rejected because that could lose recorded progress.
- Attempt to dispatch arbitrary profile routes from the static workflow: rejected because the workflow's agent-command sequence is fixed to specify, plan, tasks and implement.

## Gate integration

**Decision**: Configure engine gates with `on_reject: skip`, then branch on the captured choice. Approval calls the existing lifecycle gate-approval command; rejection calls the existing gate-rejection command and then exits non-zero so later stage commands cannot run. Gate prompts tell users to record a review first where comprehensive depth requires it.

**Rationale**: The engine's default abort behavior prevents downstream audit of rejection; the skip-and-branch pattern records the decision before halting. Existing state validation remains the source of truth for review freshness and block overrides.

**Alternatives considered**:
- Keep `on_reject: abort`: rejected because the lifecycle would remain at a pending gate with no `gate_rejected` event.
- Treat the engine's gate choice as approval without calling `speckit_flow`: rejected because the persisted state and hash-chained audit would become inconsistent.

## Portability and scope

**Decision**: Use `python -m speckit_flow` commands with fixed arguments in shell steps; do not interpolate free-text user inputs into shell commands. Restrict automatic route matching to the standard `feature` profile. Other profiles continue to be orchestrated by `speckit-profile` and are rejected by the standard workflow with an actionable error.

**Rationale**: Python module invocation is portable across Windows and POSIX, fixed shell arguments avoid injection through workflow interpolation, and the static route can be validated deterministically.

**Alternatives considered**:
- Dynamically build shell commands from route values or human-provided gate reasons: rejected because shell quoting differs by platform and can introduce command injection.
- Change the standard workflow to select any profile: rejected because no generic stage-dispatch mechanism exists for variable routes.

## Review requirement handling

**Decision**: Keep review creation in the existing `speckit-review` skill, and make the human gate prompt instruct contributors to run it before approval for comprehensive profiles. The lifecycle approval command remains authoritative and rejects absent/stale reviews or blocked reviews without a human override reason.

**Rationale**: Reviewer behavior is already harness-skill-specific, while the review record and gate checks are deterministic shared code. The workflow should not imply a reviewer ran if it did not.

**Alternatives considered**:
- Automatically invoke the custom review skill from the generic workflow: rejected because the command is not guaranteed to be available in every declared integration.
