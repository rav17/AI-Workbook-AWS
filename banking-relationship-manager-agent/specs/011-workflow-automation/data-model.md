# Data Model: Workflow Automation

This feature reuses the 009/010 lifecycle entities and introduces no new persisted records.

## Workflow Preflight

The workflow preflight request is transient:

| Field | Type | Constraints |
|---|---|---|
| expected_stages | ordered list of stage names | Must exactly match the standard workflow's command stages: `specify, plan, tasks, implement` |
| expected_gates | ordered list of stage names | Must exactly match the standard workflow's gate positions: `specify, plan` |

Preflight resolves the feature directory from `.specify/feature.json`.

### Behavior

- If state exists, read it without overwriting it and verify the audit hash chain.
- If `state.json` is missing while `audit.jsonl` exists, stop and require explicit `rebuild`.
- If both state and audit files are absent, initialize the default `feature` profile.
- Resolve the stored profile and compare its ordered stages and gates to the supplied expected route.
- Reject a route mismatch, corrupt state, or broken audit chain with an actionable error.
- Preflight does not start, complete, approve, reject, or reset any stage.

## Workflow Stage Transition

The existing `FeatureState` and `StageRecord` are authoritative:

```text
pending -> in_progress -> done
                         -> pending (gate rejected)
```

For plan, tasks and implement, `stage start <name>` is called before each skill command and `stage done <name>` is called only after the skill command succeeds. Since the specify command creates the feature directory and `.specify/feature.json`, the workflow initializes, starts and completes `specify` immediately after that command returns and before the first gate. A gate decision updates the existing `pending_gate` and stage record through `decide_gate`.

The directory cannot be addressed by lifecycle commands before it exists. Workflow engine resume resumes its recorded workflow step; a new workflow invocation must not reset or reinterpret existing lifecycle state.

## Gate Decision

An engine gate yields an ephemeral `approve` or `reject` choice. The workflow consumes it immediately:

- `approve`: invoke the existing review-aware `gate approve <stage>` operation.
- `reject`: invoke `gate reject <stage>` with a fixed, non-sensitive workflow reason, then stop the workflow with a non-zero shell exit.

The gate choice itself is not a persisted entity. The lifecycle audit event and state transition are the durable decision record. Existing `Review` files remain the evidence consulted by comprehensive gates.
