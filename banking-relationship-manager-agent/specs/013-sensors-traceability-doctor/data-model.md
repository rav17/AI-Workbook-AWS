# Data Model: Sensors, Traceability and Doctor

## sensors.json

```json
{"sensors": [
  {"id": "consistency", "description": "...", "kind": "builtin", "builtin": "consistency",
   "stages": ["specify", "plan", "tasks"], "required": true},
  {"id": "lint", "kind": "command", "argv": ["ruff", "check", "."], "timeout": 120,
   "stages": ["implement"], "required": true}
]}
```

Validation: unique ids matching `^[a-z][a-z0-9-]*$`; kind `builtin` needs `builtin` in {consistency, traceability} and optional `options` object; kind `command` needs a non-empty `argv` list of strings and `timeout` 1-600 (default 120); `stages` subset of known stages; `required` boolean.

## Result file `<feature>/sensors/<stage>.json`

`{"results": {"<sensor-id>": {"status": "pass|fail", "ts": "...", "reason": "...", "fingerprints": {"spec.md": "<sha256>"}}}}`

A result is stale when any recorded fingerprint differs from the current file (or a tracked artifact appeared or disappeared).

## Trace matrix

`requirements: {FR-001: {tasks: [T001], tests: [T002]}}`, `uncovered`, `untested`, `unknown_refs`, `orphan_tasks`.
