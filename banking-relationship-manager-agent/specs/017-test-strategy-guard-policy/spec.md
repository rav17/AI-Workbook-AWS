# Feature Specification: Test Strategy and Guard Policy

**Feature Branch**: `017-test-strategy-guard-policy`

**Created**: 2026-11-05

**Status**: Implemented

**Input**: Borrow AI-DLC's split of "depth" into independent controls: how strict gates are (guard policy) and how much testing evidence is required (test strategy).

## User Scenarios & Testing

### User Story 1 - Guard policy (Priority: P1)

A profile sets `guard_policy: strict|standard`. Strict requires a current review and no open questions before any gate approval. When unset, `depth: comprehensive` implies strict (backward compatible); an explicit `standard` overrides that.

### User Story 2 - Test strategy (Priority: P2)

A profile sets `test_strategy: standard|required`. Required refuses approval of a `tasks`, `analyze` or `implement` gate while any requirement lacks a test task.

## Requirements

- **FR-001**: Profile validation MUST reject unknown `test_strategy` and `guard_policy` values.
- **FR-002**: Strict policy MUST refuse approval without a current review, with the refusal audited.
- **FR-003**: Strict policy MUST refuse approval while questions are open.
- **FR-004**: `test_strategy: required` MUST refuse approval for tasks, analyze and implement gates when `trace` reports uncovered or untested requirements.
- **FR-005**: Existing profiles without the new fields MUST behave as before.
