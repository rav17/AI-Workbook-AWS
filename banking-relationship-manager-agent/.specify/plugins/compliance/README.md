# Compliance plugin pack (example)

Adds, when enabled:

- a `compliance` workflow profile (gates on specify and plan, strict guard);
- a required `compliance-section` sensor that blocks approval of the specify and plan gates unless the artifact has a non-empty `Compliance` section. It applies to the `compliance` profile only;
- a read-only `compliance-reviewer` agent supporting specify and plan.

## Enable

1. Set `"enabled": true` in `plugin.json` (a human edit; the guard hook blocks agents from editing it).
2. Run `python -m speckit_flow plugins validate` and `python -m speckit_flow doctor`.
3. To let the conductor dispatch the reviewer, add `speckit-compliance-reviewer` to the `agents` list in `.github/agents/speckit-conductor.agent.md`.

Disabling the pack removes all three additions; core behaviour is unchanged.

## Adapt

- Change `options.heading` in `sensors.json` to require a different section (for example `Rollback plan`).
- Edit the profile's `stages`, `gates` or `guard_policy`.
- Add regulation-specific guidance to the agent file.
