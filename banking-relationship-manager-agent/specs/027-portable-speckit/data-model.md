# Data Model: Portable Spec Kit Setup

## Bundle Entry

Represents one shared source file installed into the target project.

| Field | Description | Validation |
|---|---|---|
| `source` | Repository-relative path to the authoritative workflow asset | Must resolve within the source repository |
| `destination` | Target-relative path | Must be relative, remain within the target, and not be a symlink escape |
| `category` | Shared engine, skill, agent, hook, script, documentation, or neutral seed config | Must be one of the declared categories |
| `include` | Exact files relative to a directory source | Required for directories; no recursive/glob expansion |
| `seed` | Indicates a project-owned default after installation | Boolean; existing seed files are preserved on update |

## Installation Manifest

Records what the installer owns in the target project.

| Field | Description | Validation |
|---|---|---|
| `schema_version` | Manifest format version | Supported version required |
| `bundle_version` | Workflow bundle version or source revision | Non-empty |
| `files` | Installed target paths and recorded hashes | Unique safe relative paths |

Each file record stores the last installed content hash. Updates may replace a file only when its current content still matches the previous installed hash; modified or missing files are reported as conflicts.
Existing seed files are preserved regardless of bundle changes. Identical
preexisting files are not adopted. Manually accepted content matching the new
shared source advances the previously owned file's recorded hash.

## Target Project Configuration

Configuration owned by the receiving project: constitution, active feature pointer, custom profiles/stages/agents/rules/sensors, knowledge, plugin enablement and approved verification command. The installer does not claim ownership of user-created values or overwrite them.

If absent, the installer creates a target-local `.specify/feature.json` pointer to the next available `specs/NNN-new-feature` location. This pointer is not part of the shared-file update manifest.

## Domain Pack

An optional plugin with a manifest and files for domain-specific profiles, stages, agents, sensors, or guidance. It remains disabled until a human opts in. Pack-specific preconditions are checked by the existing plugin validation and doctor commands.
