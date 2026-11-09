# Implementation Plan: Portable Spec Kit Setup

**Branch**: `027-portable-speckit` | **Date**: 2026-11-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-portable-speckit/spec.md`

## Summary

Provide a repeatable, safe way to install the reusable Spec Kit lifecycle into another GitHub Copilot project. The installed default must exclude banking application code, the banking constitution and knowledge, and project-specific check commands. Shared workflow code is selected through an explicit manifest; receiving-project configuration is seeded from neutral defaults, while optional domain packs remain opt-in. The installer reports file conflicts and never silently replaces destination content.

## Technical Context

**Language/Version**: Python 3.11+ for the installer and existing lifecycle package
**Primary Dependencies**: Python standard library for installation; existing Spec Kit and Copilot project integration
**Storage**: Files in the receiving project's repository
**Testing**: pytest with temporary Git project fixtures; existing focused `speckit_flow` tests
**Target Platform**: Windows, macOS and Linux developer environments
**Project Type**: Repository bootstrap utility and reusable workflow files
**Performance Goals**: Install and diagnose a clean sample project within the 10-minute user outcome
**Constraints**: No network install, no project runtime dependency changes, no overwriting user-owned files, no banking configuration in the default bundle; first release supports Copilot/Spec Kit only
**Scale/Scope**: One installer, a source manifest, neutral seed configuration, and documentation for a single receiving project

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution is for the Aria banking application and does not govern the reusable workflow product. The feature must explicitly avoid copying it to a receiving project. Applicable constraints are safe file operations, explicit conflict reporting, no automatic approval of a verification command, and tests that isolate the destination from the banking repository. **Pass**.

## Project Structure

### Documentation (this feature)

```text
specs/027-portable-speckit/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
scripts/speckit_bootstrap.py              # installs the declared reusable file set
speckit_flow/                             # shared lifecycle engine
.specify/speckit-portable-manifest.json   # installed-file ownership and hashes
.specify/templates/portable/              # neutral seed configuration
tests/unit/test_speckit_bootstrap.py      # isolated install/conflict/update tests
docs/speckit-portability.md               # setup, customization and update guide
```

**Structure Decision**: Keep the installer in the current repository and define an allow-listed portable bundle. It copies shared workflow assets and neutral seed configuration only; it does not clone the banking application, its constitution or knowledge, dependencies, tests, or command sensors. Domain-specific additions are explicitly opt-in. A destination manifest records installed ownership for safe updates.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations.

## Portability acceptance hardening

Directory entries enumerate exact files rather than recursively copying future
project additions. Neutral seed rules and initialization settings replace live
project values. Seed configuration and plugins are project-owned after install;
updates preserve them even if the bundle defaults change. Shared-code updates
remain hash-checked and all conflicts are preflighted before writing. Aliasing
destination paths, file/directory collisions, and source/target overlap are
rejected.

The acceptance test installs into a temporary non-banking Git repository,
creates sample specification/plan/tasks artifacts, builds and tests a small
non-banking function, runs sensors and traceability, simulates human decisions
only in that fixture, and verifies a construction checkpoint and final audit.
This proves the installed CLI lifecycle, not live LLM skill generation or a
Spec Kit workflow-engine integration test. The missing `specify_cli` engine
integration remains an explicitly reported skip.

The user approved the targeted pytest command plus Ruff/mypy and simulated
fixture gate decisions on 2026-11-09. No real project approvals are granted.
