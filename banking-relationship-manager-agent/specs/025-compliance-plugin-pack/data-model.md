# Data Model: Compliance Plugin Pack

## Plugin manifest (`plugin.json`)

| Field | Value |
|-------|-------|
| name | `compliance` (must equal folder) |
| version | `1.0.0` |
| enabled | `false` by default |

## Profile (`profiles/compliance.json`)

Same schema as core profiles. Stages: specify, clarify, plan, tasks, implement, analyze. Gates: specify, plan. `guard_policy`: strict, so `ceremony.reviews` must stay on.

## Sensor (`sensors.json`)

| Field | Value |
|-------|-------|
| id | `compliance-section` |
| kind | `builtin` |
| builtin | `section` (new) |
| options | `{"heading": "Compliance"}` |
| stages | `specify`, `plan` |
| required | `true` |
| profiles | `["compliance"]` (new optional field) |

### Rules

- `section`: passes when the stage's artifact has a markdown heading whose text starts with `options.heading`, case-insensitive, and at least one non-empty line follows before the next heading.
- `profiles`: must be a non-empty list of strings when present. A sensor with `profiles` runs and is required only for features whose profile is listed.
- Plugin sensors still cannot reuse a core sensor id.

## Agent (`agents.json`)

`compliance-reviewer`: role `domain`, tier `judgment`, no leads, supports `specify` and `plan`, `can_edit` false, file `.github/agents/speckit-compliance-reviewer.agent.md`.

## State transitions

None added. Gate approval is refused while the sensor has not passed, exactly as for existing required sensors.
