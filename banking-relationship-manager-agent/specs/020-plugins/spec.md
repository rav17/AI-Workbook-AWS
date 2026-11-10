# Feature Specification: Plugin Packs

**Feature**: 020-plugins
**Status**: Implemented

## User Story 1 - Add capabilities from a pack folder (P1)
- **FR-001**: A plugin is a folder `.specify/plugins/<name>/` with `plugin.json` (`name` matching the folder, `version`, optional `description`, optional `enabled`, default true).
- **FR-002**: An enabled plugin MAY contribute `profiles/*.json`, `sensors.json` and `stages.json`, in the same formats as core.
- **FR-003**: Plugins MUST only add: a plugin profile or sensor reusing an existing id MUST be refused; plugin stages follow the custom-stage rules (optional, new id, `after` anchor).
- **FR-004**: Precedence is core, then plugins in name order, then the project overlay in `.specify/custom/`.
- **FR-005**: A disabled plugin MUST contribute nothing.
- **FR-006**: A plugin folder with a missing or invalid manifest MUST fail loudly, never be skipped.

## User Story 2 - Inspect and protect (P2)
- **FR-007**: `plugins list|validate` MUST show each plugin and what it provides, and validate the merged configuration.
- **FR-008**: `doctor` MUST include a plugins check.
- **FR-009**: The guard hook MUST protect `.specify/plugins/` from agent edits.

## Out of scope
Plugin-supplied agents (the roster has fixed role counts and agent files), plugin installation or download, versions or dependency resolution.
