# Tasks: Memory Context Contract Normalization

**Input**: Design documents from `/specs/007-memory-context-contract/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`

## Phase 1: Setup

No dependency, infrastructure, or new-module setup is needed; the implementation reuses existing framework modules.

## Phase 2: User Story 1 - Consistent Memory Context (Priority: P1)

**Goal**: Make local and remote memory interchangeable at the context boundary and prevent a remote deletion failure from affecting local storage.

**Independent Test**: Context assembly succeeds for local and remote entries, rejects malformed or cross-tenant remote records, supports an absent backend, and never falls back to local deletion when a remote client is configured.

### Tests

- [x] T001 [P] [US1] Add explicit no-backend and typed-memory context tests in `tests/framework/test_context_builder.py`.
- [x] T002 [P] [US1] Add remote normalization, malformed/cross-tenant record, and no-local-delete-fallback tests in `tests/framework/test_agentcore_adapters.py`.

### Implementation

- [x] T003 [US1] Define the narrow `MemoryRetriever` protocol and type the optional context dependency in `aria/framework/contracts.py` and `aria/framework/context.py`.
- [x] T004 [US1] Normalize remote provider mappings to `MemoryEntry` and delegate configured-remote deletion without local fallback in `aria/framework/agentcore.py`.
- [x] T005 [US1] Run focused framework tests, strict mypy, and Ruff checks for the changed framework modules.

## Dependencies and Execution Order

- T001 and T002 are independent test-first tasks and must fail against the current implementation before T003 and T004 begin.
- T003 and T004 touch separate implementation modules and may proceed independently after the regression tests are in place.
- T005 follows both implementation tasks.

## Implementation Strategy

Complete the P1 story as one independently verifiable increment. Preserve the provider-facing data-plane contract and the existing no-write policy; do not include the AriaAgent dispatcher refactor.