# Quickstart: Workflow Automation

## Prerequisites

- Run from the repository root.
- Use a supported Spec Kit integration and ensure `python -m speckit_flow` is available.
- The standard workflow route is the `feature` profile.

## Validate workflow definition

```powershell
python -m pytest tests/unit/speckit_flow/test_flow_workflow.py -q
```

Expected: the test verifies the YAML structure and, when `specify_cli` is installed in the active Python environment, validates it with the installed engine. The workflow engine validation used during implementation returned no errors.

## Run a standard workflow

1. Start the `speckit` workflow with a feature description.
2. The specify command creates the feature directory and spec. On return, workflow preflight initializes lifecycle state and records `specify` start/completion before the first approval gate.
3. Approve or reject the specification gate. For a comprehensive profile, first save a current review with `/speckit-review specify`.
4. The workflow records the gate choice. Rejection stops the run; approval continues to plan.
5. Plan, task generation and implementation are each started and completed through lifecycle CLI calls around their Spec Kit commands.

## Verify persisted state

```powershell
python -m speckit_flow status
python -m speckit_flow resume
```

Expected: the state summary shows the profile, current stage and any pending gate; both commands verify the audit hash chain.

## Verify review-aware approval

For a comprehensive profile, attempt to approve a gate without a current review. Expected: the workflow fails at lifecycle approval with an explicit missing-review error and does not start the next stage. Save a review and resume the workflow. A blocked review still requires a human to explicitly run `gate approve <stage> --override-reason "<reason>"`; continue manually with `speckit-profile` after resolving the gate.

## Verify rejection

Reject a gate. Expected: the workflow records `gate_rejected`, leaves the gated stage pending, exits unsuccessfully with a rejection message, and does not dispatch later stage commands.

See [CLI contract](./contracts/cli.md) and [workflow contract](./contracts/workflow.md).
