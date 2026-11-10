# Implementation Plan: Structured Stage Contracts

**Branch**: `031-structured-stage-contracts` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/031-structured-stage-contracts/spec.md`

## Summary

Add a disabled-by-default stage-contracts plugin and opt-in `contract-driven`
profile. Contracts describe stage purpose, inputs, outputs, acceptance criteria
and review focus. A deterministic contract sensor checks declared required
outputs at gated stages; existing required-sensor freshness and human approval
remain authoritative. Non-gated checks are advisory.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: Python standard library; existing pytest, Ruff and mypy

**Storage**: Project-local JSON contract definitions and sensor result records; existing append-only audit events

**Testing**: Focused pytest suites for contracts, sensors, state/gates and portable bootstrap

**Target Platform**: Windows, macOS and Linux; local filesystem only

**Project Type**: Portable Python CLI and workflow library

**Performance Goals**: No subprocess or network access; file checks are limited to 100 distinct outputs of at most 1 MiB each

**Constraints**: Contracts are opt-in; required output paths are feature-local; reject symlink traversal, absolute paths and traversal; max 100 distinct outputs and 1 MiB per file; no content in audit records

**Scale/Scope**: Core feature route stages plus project-owned optional/custom stages; no changes to application runtime or banking workflows

## Constitution Check

- **Structured state**: Reuse typed contract/sensor models and persisted sensor results; do not make chat history authoritative. **Pass.**
- **Deterministic safety**: Gate checks validate paths and file presence in application code; agents cannot approve gates. **Pass.**
- **Patch, validate and invalidate**: A changed contract/output changes sensor fingerprints, so stale evidence blocks approval. **Pass.**
- **Bounded context/use**: Checks are local and bounded, with no external commands or content transmission. **Pass.**
- **Durable boundaries/session isolation**: Use feature-local sensor records and existing audit/state boundaries; no cross-project state. **Pass.**
- **Python quality/operations**: Type annotations, explicit I/O errors, deterministic tests and existing linters/type checks. **Pass.**
- **Security/compliance**: Reject paths escaping the feature root and symlinks; audit only safe summaries and hashes. **Pass.**
- **Development gates**: Focused tests and installed non-banking fixture acceptance. Verification command is proposed in `quickstart.md`; obtain human approval before using it for a construction checkpoint. **Pass, pending approval.**

No constitution exceptions are required.

## Design

1. Add an optional `stage_contracts` boolean to `Profile` (default `false`) and
   add `speckit_flow/contracts.py` to load and validate versioned contracts from
   the enabled plugin and `.specify/custom/stage-contracts.json`. Resolve
   project overrides last; reject invalid JSON, duplicate/unknown stages,
   missing contracts in the active contract profile and required gated outputs
   without a machine-checkable path. Validate contract-enabled profiles during
   feature initialization; existing profiles remain unaffected.
2. Add a `contracts` CLI command to list/show contracts for agents and reviewers.
   The command reports configuration errors explicitly and does not alter state.
3. Add a `stage-contract` builtin sensor. It checks safe relative file outputs,
   regular-file status, size and non-empty content; it does not execute code or
   infer semantic correctness. Sensor fingerprints include the resolved
   contract and its declared output files. Existing gate logic blocks on missing,
   failed or stale required evidence and remains human-only.
4. Add a disabled `.specify/plugins/stage-contracts/` pack with a
   `contract-driven` profile, contracts for its route, and a required sensor
   scoped to that profile. Non-gated checks provide advisory feedback only.
5. Add a reusable skill, templates, portable bundle entries and documentation.
   The default profile and all existing packs remain unchanged.

### Project Structure

```text
speckit_flow/
├── contracts.py
├── cli.py
├── models.py
├── plugins.py
├── profiles.py
├── sensors.py
└── state.py
.specify/plugins/stage-contracts/
├── plugin.json
├── profiles/contract-driven.json
├── sensors.json
└── contracts/stages.json
.specify/custom/stage-contracts.json  # project-owned override
tests/unit/speckit_flow/
├── test_flow_contracts.py
├── test_flow_cli_contracts.py
└── test_flow_sensors.py
```

### Documentation (this feature)

```text
specs/031-structured-stage-contracts/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/stage-contract.schema.json
└── tasks.md
```

**Structure Decision**: Extend the existing Python CLI, plugin, sensor and
portable-bundle architecture; add no runtime services or dependencies.

## Validation Strategy

- Contract parser tests: schema fields, duplicates, unknown stages, project
  overrides, active-profile completeness and explicit parse/I/O errors.
- Sensor tests: missing/empty outputs, safe paths, file limits, symlink and
  access failures, contract/output fingerprint invalidation and no subprocess.
- Gate tests: required evidence blocks missing/failed/stale gate checks; a human
  remains the only approver; non-gated completion remains unblocked.
- Installed-project acceptance: enable the pack in a disposable non-banking
  fixture, show a contract, exercise a gated check and confirm disabled defaults
  are unchanged.
- Run focused tests, Ruff, mypy, doctor and `graphify update .` after human
  approval of the proposed verification command.

## Complexity Tracking

No unjustified complexity or constitution violations.
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
