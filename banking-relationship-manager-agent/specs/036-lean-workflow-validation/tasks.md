# Tasks: lean workflow validation

- [x] T001 Add failing acceptance/regression tests for FR-001 FR-002 FR-003: empty/duplicate/unknown trace inputs and diagnostics; exact single-read context/dispatch audit checks; compact plan template invariants.
- [x] T002 Implement shared trace validation and downstream failure diagnostics for FR-001 FR-004; depends on T001.
- [x] T003 Implement fresh single-pass audit snapshots and wire context/dispatch for FR-002 FR-004; depends on T001.
- [x] T004 Simplify plan template and document changed compatibility/measurement scope for FR-003 FR-004; depends on T001.
- [x] T005 Run final affected tests, lifecycle suite, portability, lint/types and configured sensors; record measured audit reads/template bytes for FR-001 FR-002 FR-003 FR-004; depends on T002 T003 T004.

Edits remain sequential; independent validation commands may run concurrently.
No new agents or gates, no commits, deployments or dependency installation.
