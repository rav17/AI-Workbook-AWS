# Plan: Plugin Packs (020)

- New `speckit_flow/plugins.py` discovers and validates manifests (FR-001, FR-005, FR-006).
- `profiles.load_profiles`, `sensors.load_sensors` and `stagedefs.load_stage_defs` merge plugin items before the project overlay, add-only (FR-002, FR-003, FR-004).
- `cli.py` adds `plugins list|validate`; `doctor.py` adds a plugins check; guard protects `.specify/plugins/` (FR-007 to FR-009).
- Decision: plugins cannot override, so a pack can never weaken a required core sensor or change a core profile. Teams override via the project overlay, which is explicit and reviewed.
- Alternative rejected: plugin-supplied agents now; roster validation depends on fixed counts and agent files, so it needs its own design.
