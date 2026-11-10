# CLI Contract: `python -m speckit_flow`

All commands take `--feature-dir <path>` (default: from `.specify/feature.json`) and exit non-zero with a one-line error on failure. `--json` prints machine-readable output.

| Command | Behavior |
|---|---|
| `profiles list` | List valid profiles with stages and depth. |
| `profiles validate [id]` | Validate one or all profile files; non-zero on invalid. |
| `profiles suggest "<description>"` | Print the suggested profile id and why; never writes. |
| `init --profile <id> [--actor A]` | Create `state.json`/`state.md`, mark omitted stages skipped, emit `profile_selected` and `stage_skipped` events. Unknown id lists valid profiles and exits non-zero. Default profile is `feature`. |
| `switch --profile <id> --confirm [--actor A]` | Change profile at a stage boundary; rejected if a stage is in progress or `--confirm` is absent. |
| `stage start <stage>` | Mark in progress; rejects stages not in the route or out of order. |
| `stage done <stage>` | Mark done; sets `pending_gate` if the profile gates it. |
| `gate approve|reject <stage> [--reason R]` | Record decision; reject leaves the stage pending re-work. |
| `status` | Print profile, current stage, next stage, pending gate; verifies the audit hash chain. |
| `resume` | Like `status`; if `state.json` is missing or corrupt, reports it and offers `rebuild`. |
| `rebuild` | Reconstruct state from existing artifacts (`spec.md`, `plan.md`, `tasks.md`) and audit it. |

State write and audit append happen together: audit is appended first; if it fails the state is not changed and the command fails (spec edge case).

Schemas: [profile.schema.json](./profile.schema.json), [audit-event.schema.json](./audit-event.schema.json).
