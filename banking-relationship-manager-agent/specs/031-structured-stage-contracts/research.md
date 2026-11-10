# Research: Structured Stage Contracts

## Decision 1: Keep contracts opt-in and profile-scoped

- **Decision**: Ship a disabled-by-default `stage-contracts` plugin and a
  contract-enabled feature profile. Add an opt-in profile flag, defaulting to
  false, so project profiles can explicitly request contracts without
  hard-coding the plugin's profile name. Existing profiles do not load or
  enforce contracts.
- **Rationale**: Plugin discovery already supports disabled packs and profiles
  added by plugins. This preserves current stage behavior and allows unrelated
  projects to adopt the capability selectively.
- **Alternatives considered**: Adding required contracts to every core stage
  would change default workflows and make adoption non-incremental.

## Decision 2: Use required sensors for current gated-output evidence

- **Decision**: Reuse the sensor lifecycle for stage-contract checks. The
  contract sensor checks required, path-addressable outputs; gate approval
  relies on passing, fresh sensor evidence. Non-gated stages may run the same
  check as advisory feedback.
- **Rationale**: Required sensors already block human gate approval when
  missing, failing or stale, and capture fingerprints without adding artifact
  contents to audit events.
- **Alternatives considered**: A separate gate state machine would duplicate
  existing freshness and audit behavior. Blocking `stage done` would violate
  the agreed human-gates-only policy.

## Decision 3: Keep contract validation deterministic and bounded

- **Decision**: Validate declarations as structured data; check output paths
  relative to the feature directory, reject escapes and symlinks, and limit
  tracked outputs to 100 files of at most 1 MiB each. Check presence and
  non-empty content only.
- **Rationale**: The portable toolkit uses bounded, local checks and already
  applies these file-count and size limits to walking-skeleton evidence.
  Deterministic presence checks avoid model-based content judgments and
  unnecessary reads or external commands.
- **Alternatives considered**: Executing stage-specific commands or applying
  semantic quality scoring would make the contract system less portable and
  could misrepresent human review.

## Decision 4: Permit project-owned contracts for custom stages

- **Decision**: Load plugin-provided contracts and a project-owned override;
  reject duplicate or unknown stages and require a complete contract for each
  stage in an opted-in profile. A required output on a gated stage must have a
  safe relative path so the gate check is actionable.
- **Rationale**: This follows existing plugin and custom-overlay conventions
  while keeping custom workflow policy within its receiving project.
- **Alternatives considered**: Silently synthesizing a contract from a stage
  description would conceal missing acceptance criteria and weaken review.

## Repository evidence

- Stage gates already call `sensors.gate_problems`, which rejects missing,
  failed and stale required sensor results (`speckit_flow/state.py`,
  `speckit_flow/sensors.py`).
- Sensor results store status, reason and fingerprints locally; audit events
  record the sensor ID and result status, not artifact contents
  (`speckit_flow/sensors.py`).
- Plugin packs can contribute profiles, sensors and stages, and are disabled
  through `plugin.json` (`speckit_flow/plugins.py`).
- Profiles are loaded and validated as typed data before workflow state is
  initialized (`speckit_flow/models.py`, `speckit_flow/state.py`).
- Walking-skeleton checks already enforce root-relative bounded file evidence
  (`speckit_flow/units.py`, `.specify/plugins/walking-skeleton/README.md`).
