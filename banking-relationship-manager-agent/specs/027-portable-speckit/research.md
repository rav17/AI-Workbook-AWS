# Research: Portable Spec Kit Setup

## Decision 1: Install an allow-listed workflow bundle from this repository

- **Decision**: Provide a Python standard-library bootstrap command that targets another repository and installs only files listed in a maintained bundle manifest.
- Directory entries enumerate exact included files, not recursive copies of future local additions.
- **Rationale**: This supports repeatable installation from a clone of this repository, works across Windows/macOS/Linux, and avoids a second source of truth for most workflow assets.
- **Alternatives considered**: Copy the entire repository (would copy banking app code and project policy); publish a standalone package now (requires release/versioning and distribution infrastructure not requested); document manual copying (not reliably repeatable).

## Decision 2: Separate shared workflow assets from target-project configuration

- **Decision**: Seed neutral profiles, stages, sensors and templates from dedicated portable defaults. Do not copy `.specify/feature.json`, the banking constitution, banking knowledge, application tests, or command sensors that invoke this repository's test/lint commands.
- **Rationale**: Target repositories must use their own governance and validation commands. The project's verify command remains unapproved until a human approves it.
- **Alternatives considered**: Copy current `.specify/` as-is (imports a banking-specific constitution/knowledge and unrelated test commands); copy no configuration (leaves first-time setup incomplete).

## Decision 3: Preserve user files and record ownership for updates

- **Decision**: On install, create missing files, skip byte-identical files, and stop/report if a destination file already differs. Record installed paths and source hashes in a manifest under `.specify/`. Updates replace a destination only if it still matches the previously installed hash; otherwise they report a conflict without writing.
- Seed configuration, templates and plugins remain project-owned after installation and are preserved on update, even if the source defaults change. Identical preexisting files are never adopted as shared installer-owned files.
- **Rationale**: This provides a conservative update path and protects local instructions, rules and config.
- **Alternatives considered**: Force-copy (can destroy project policy); silently skip all existing files (cannot deliver shared updates); attempt automatic three-way merges (unnecessary complexity and difficult to validate for agent instructions).

## Decision 4: Keep domain additions opt-in

- **Decision**: Install the generic lifecycle engine and shared AI-DLC-inspired capabilities, but do not enable domain plugins by default. Document enabling and adapting a plugin as a human action and run doctor afterward.
- **Rationale**: Stages, profiles, sensors, agents, source-bound review evidence, audit, rules, knowledge, and verification behavior should travel across projects, while domain policy must be selected by the receiving team.
- **Alternatives considered**: Enable every plugin by default (adds irrelevant gates and agents); remove all plugin examples (loses useful examples).
- The portable roster includes the AWS-platform and compliance specialists as available agents but clears their default stage support so unrelated projects do not auto-dispatch them.

## Decision 5: Scope the first portable target to GitHub Copilot and Spec Kit

- **Decision**: The bootstrap guide and tests target repositories using the Copilot integration; other harnesses are not promised by this feature.
- **Rationale**: The workflow skills and agent definitions are currently installed under `.github/`.
- **Alternatives considered**: Multi-harness packaging (out of scope and would require parallel skill/agent projections).

## Repository findings

- `speckit_flow` uses the Python standard library and can be copied without importing the banking application package.
- The current repository's core sensors include Ruff and pytest commands bound to this repository's paths; these must not be in the portable defaults.
- `.specify/memory/constitution.md` and `.specify/knowledge/banking-compliance.md` are project-owned domain content and must be excluded.
- Existing extension mechanisms cover profiles, stages, agents, rules, sensors, plugins and knowledge. The installer should preserve project-created files rather than flatten them.
- `.specify/feature.json` currently points to this repository's feature and must be initialized empty or to a target-local default, never copied verbatim.
