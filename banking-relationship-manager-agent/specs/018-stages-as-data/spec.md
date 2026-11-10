# Feature Specification: Stages as Data

**Feature**: 018-stages-as-data
**Status**: Implemented

## Problem
Workflow stages were hard-coded in `speckit_flow/models.py`, so adding a stage (for example NFR design or performance validation) required a code change.

## User Story 1 - Core stages come from a data file (P1)
As a maintainer I want stage order, optionality and dependencies defined in `.specify/stages/stages.json`.
- **FR-001**: The system MUST load stage id, phase, optional flag, `requires` and `lead` from `.specify/stages/stages.json`.
- **FR-002**: Profile validation MUST derive ordering, the first required stage and `requires` rules from that data.
- **FR-003**: Behaviour for the existing 9 stages and 9 profiles MUST be unchanged.
- **FR-004**: A malformed stages file MUST fail loudly, never fall back silently.

## User Story 2 - Teams add optional stages without editing core (P2)
- **FR-005**: `.specify/custom/stages.json` MAY add stages, each with `after` naming an existing stage.
- **FR-006**: Custom stages MUST be optional, MUST NOT reuse an existing id, and MUST NOT require a later stage.
- **FR-007**: A custom stage MUST have exactly one lead: a roster agent listing it in `leads`, or the stage's `lead` field. `doctor` reports violations.
- **FR-008**: `stages` CLI command MUST list the effective stages; `doctor` MUST include a stages check.
- **FR-009**: The guard hook MUST protect `.specify/stages/` from agent edits.

## Out of scope
Per-stage templates and custom skills for new stages; plugins (feature 019+).
