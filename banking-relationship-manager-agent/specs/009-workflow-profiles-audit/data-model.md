# Data Model

## Profile (`.specify/profiles/<id>.json`)
| Field | Type | Rules |
|---|---|---|
| id | string | matches filename, `[a-z][a-z0-9-]*` |
| description | string | required |
| stages | list of stage | non-empty, no duplicates, canonical order, from `specify, clarify, plan, tasks, analyze, implement` |
| depth | enum | `minimal`, `standard`, `comprehensive` |
| gates | list of stage | each must be in `stages` |
| exemptions | list of string | optional; e.g. `implement-without-tasks` |

Validation: `specify` is first; `plan` requires `specify`; `implement` requires `tasks` unless exempted; unknown fields rejected.

## FeatureState (`<feature>/state.json`)
| Field | Type | Notes |
|---|---|---|
| feature | string | directory name |
| profile | string | profile id |
| depth | enum | copied from profile |
| current_stage | string or null | null when finished |
| stages | map stage → `{status, reason?, updated_at}` | status: `pending`, `in_progress`, `done`, `skipped` |
| pending_gate | string or null | stage awaiting approval |
| revision | int | incremented on each write |
| updated_at | ISO-8601 UTC | |

Transitions: pending → in_progress → done; pending → skipped (profile omits stage, with reason); a gated stage sets `pending_gate` on done until approved. Profile change allowed only when `current_stage` is not `in_progress` (stage boundary); done stages are kept, remaining stages are recomputed.

## AuditEvent (`<feature>/audit.jsonl`)
| Field | Type | Notes |
|---|---|---|
| seq | int | starts at 1, strictly increasing |
| ts | ISO-8601 UTC | |
| type | enum | `profile_selected`, `profile_changed`, `stage_started`, `stage_completed`, `stage_skipped`, `gate_approved`, `gate_rejected`, `failure` |
| stage | string or null | |
| actor | string | `human:<label>` or `agent:<label>` |
| detail | string | short reason or decision; redaction-checked |
| prev_hash | string | SHA-256 of the previous line (empty for first) |

The writer reads only the last line to compute `seq` and `prev_hash`, and never rewrites the file.
