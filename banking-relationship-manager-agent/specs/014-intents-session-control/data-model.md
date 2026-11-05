# Data Model

- **Intent summary**: `{name, profile, current_stage, pending_gate, parked, active}` derived from `state.json`, audit and `.specify/feature.json`.
- **Audit events** (all with the acting `human:`/`agent:` id): `intent_switched` (detail `active`), `intent_parked` (detail = reason), `intent_resumed`, `stage_redone` (detail `from=<stage> reset=<a,b> reason=<text>`).
- **Parked**: latest of `intent_parked` / `intent_resumed` is `intent_parked`.
- **Redo reset set**: target stage and every later stage in the route (STAGES order, excluding skipped).
