# Data Model

## Inventory

- `sources`: sorted relative paths with recognized application source extensions.
- `tests`: source paths whose path/name follows documented test conventions.
- `manifests`: known dependency/build manifest paths.
- `examined_entries`: filesystem entries considered, bounded to 10,000.
- `existing`: true when at least one source is recognized.

No file contents, credentials or inferred dependency versions are stored.
Generated/dependency/toolkit directories and symlink entries are not traversed.
Scan failures raise a user-facing error; no partial report is returned as success.

## Stage condition

`StageDef.condition`: empty (unconditional) or `existing-codebase`.
Only optional stages may declare it; profiles cannot gate a conditional stage.
When false at `stage start`, record a `stage_skipped` audit event and transition
pending -> skipped, advancing the current stage with no gate.

## Analysis artifact

`<feature>/codebase.md`: scope, inventory evidence, architecture, dependencies,
interfaces, tests, impact and unknowns. Architect-produced findings cite paths;
inventory-only output is clearly identified as a starting point, not findings.
