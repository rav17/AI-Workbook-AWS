# Feature Specification: Construction Units and Verification Command

**Feature**: 019-construction-units-verification
**Status**: Implemented

## User Story 1 - Human-approved verification command (P1)
- **FR-001**: An agent or human MAY propose a verification command (argv list) in `.specify/verify.json`.
- **FR-002**: Only a `human:` actor MAY approve it; approval stores the approver, time and a digest of the command.
- **FR-003**: Running an unapproved command, or one changed since approval, MUST be refused.
- **FR-004**: The guard hook MUST block agents from `verify approve` and from editing `.specify/verify.json`.

## User Story 2 - Units with a dependency graph and checkpoints (P1)
- **FR-005**: A feature MAY define units (id, title, `depends_on`, task ids) in `units.json`; duplicate ids, unknown dependencies and cycles MUST be refused.
- **FR-006**: `units checkpoint <id>` MUST require all dependencies checkpointed, run the approved command, and record the checkpoint only when it passes.
- **FR-007**: Unit definition and every checkpoint attempt MUST be audited (`unit_defined`, `unit_checkpoint`).
- **FR-008**: The `implement` gate MUST NOT be approved while a defined unit lacks a checkpoint.

## Out of scope
Parallel (swarm) execution of units; automatic unit generation from `tasks.md`.
