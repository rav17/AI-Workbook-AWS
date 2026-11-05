# CLI Contract: Workflow Preflight

## `python -m speckit_flow workflow begin`

### Options

- `--stages <csv>`: required ordered route expected by the caller.
- `--gates <csv>`: required ordered gate positions expected by the caller; an empty value means no gates.
- Standard global options: `--feature-dir`, `--profiles-dir`, `--actor`, `--json`.

The workflow resolves the feature directory from `--feature-dir` or `.specify/feature.json`.

### Success

- Initializes the default `feature` profile only if state does not yet exist.
- For existing state, verifies the audit chain and never reinitializes or modifies the state.
- If the state file is missing but the audit file exists, refuses to initialize and requires explicit `rebuild`.
- Confirms the profile's ordered stages and gates exactly equal the expected route.
- Prints state summary (or JSON summary) and exits with status 0.

### Failure

Exits non-zero and prints a specific error for a missing feature directory, missing state with an existing audit, unreadable state, invalid audit chain, or mismatched route. It does not repair or overwrite invalid state.

## Existing stage and gate commands

- `stage start <stage> --actor agent:workflow`: before plan, tasks and implement skill steps; specify is recorded immediately after the feature-creating specify command returns.
- `stage done <stage> --actor agent:workflow`: after a successful skill step only; specify is marked done before its approval gate.
- `gate approve <stage>`: records the engine's human approval; review freshness and blocked verdict rules remain enforced.
- `gate reject <stage> --reason "rejected in workflow"`: records rejection before the workflow stops.

No human-provided free text is interpolated into workflow shell commands. A blocked review requiring an override must be handled through the explicit `gate approve <stage> --override-reason <reason>` CLI flow.
