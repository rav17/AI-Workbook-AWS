# Implementation Plan: Layered Rules and Customization Overlay

**Spec**: [spec.md](./spec.md) | **Branch**: `015-layered-rules-customization`

## Technical Context

Python 3.11, stdlib only, extending `speckit_flow`. Tests with pytest, ruff and mypy as configured.

## Design

- Layers are files beside the project rules file: `org.json`, `team.json`, `rules.json` (project). `rules.effective_rules()` merges active rules, reusing the polarity matcher for overrides.
- Overlay lives in `.specify/custom/`: `profiles/*.json` (merged in `load_profiles`) and `sensors.json` (merged in `load_sensors`). Overlay location is derived from the core path so test directories stay isolated.
- A required core sensor can only be replaced by a sensor that stays required and covers every original stage.
- CLI: `rules list --effective`, `custom list|validate`; `doctor` gains a `custom` check; the guard protects the new paths.

## Constitution Check

No new dependencies, no secrets, human-only decisions unchanged. Pass.

## Decisions

- Decision: overlay merges by id with core validators. Alternative: separate overlay schema (rejected, duplicates validation).
- Decision: custom roster/stages out of scope; roster counts and stages are code-validated.
