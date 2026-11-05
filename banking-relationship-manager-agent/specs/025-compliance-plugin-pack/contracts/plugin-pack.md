# Contract: sensor and plugin extensions

## `section` built-in sensor

```json
{"id": "my-check", "kind": "builtin", "builtin": "section",
 "options": {"heading": "Rollback plan", "artifact": "plan.md"},
 "stages": ["plan"], "required": true}
```

- `heading` is required and non-empty. `artifact` is optional and must be one of `spec.md`, `plan.md`, `tasks.md`; the default is `plan.md` for the plan stage and `spec.md` otherwise.
- Fails with `"<artifact> has no '<heading>' section"` or `"<artifact> '<heading>' section is empty"`.

## `profiles` sensor scope

```json
{"id": "my-check", "...": "...", "profiles": ["compliance"]}
```

- Absent: applies to every profile (unchanged).
- Present: applies only to listed profiles. Invalid shape raises a sensor configuration error.

## CLI

No new commands. Existing `plugins list|validate`, `agents list`, `sensors run` and `doctor` are used.
