# Feature Specification: Clarify Interaction Modes

**Feature**: 021-clarify-interaction-modes
**Status**: Implemented

## User Story 1 - Choose how clarification happens (P1)
- **FR-001**: `speckit-clarify` MUST support three modes: guided (default one-question loop), file (answer in `questions.md`) and discussion (free conversation).
- **FR-002**: In every mode each question MUST be recorded with `questions add`, tagged with the roster role best placed to answer.
- **FR-003**: Agents MUST NOT run `questions answer`; the skill tells the user the exact command, or that editing `questions.md` works.
- **FR-004**: The skill MUST use `questions list --open --role` and `questions check` to show and confirm outstanding questions before reporting completion.
- **FR-005**: The existing guided loop and its 5-question limit MUST be preserved.

## Out of scope
Enforcing the mode in code; the skill is guidance, while the file format, human-only answering and the plan-gate sensor are enforced by features 016-017.
