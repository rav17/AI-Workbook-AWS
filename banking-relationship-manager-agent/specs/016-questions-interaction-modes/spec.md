# Feature Specification: Questions File and Interaction Modes

**Feature Branch**: `016-questions-interaction-modes`

**Created**: 2026-11-05

**Status**: Implemented

**Input**: Borrow AI-DLC's questions file: clarifying questions live in a file, each labelled with the role who should answer, answerable by guided chat (CLI) or by editing the file.

## User Scenarios & Testing

### User Story 1 - Role-labelled questions (Priority: P1)

1. **Given** a feature, **When** `questions add "text" --role product` runs, **Then** `questions.md` gains `Q1 [role: product]` and a `question_asked` event is audited.
2. **Given** a roster, **Then** unknown roles are refused.
3. `questions list --open [--role R]` shows only matching unanswered questions.

### User Story 2 - Answer by chat or by editing the file (Priority: P1)

1. `questions answer Q1 "text"` requires a `human:` actor, audits `question_answered`, and refuses re-answering.
2. A human may type the answer after `**Answer:**` in `questions.md`; it is recognised as answered.

### User Story 3 - Gate on open questions (Priority: P2)

1. `questions check` exits 1 while questions are open.
2. The `no-open-questions` sensor (stage `plan`) blocks the plan gate while questions are open.

## Requirements

- **FR-001**: Questions MUST be stored in `<feature>/questions.md`, one `## Q<n> [role: <role>]` block each.
- **FR-002**: Answering via CLI MUST be human-only; agents may only ask.
- **FR-003**: Question and answer text MUST pass the audit redaction check and fit on one line (500 chars).
- **FR-004**: A question is answered if and only if its answer text is non-empty.
- **FR-005**: A builtin `questions` sensor MUST fail while any question is open.
- **FR-006**: Malformed question headings MUST be an error, never silently ignored.
