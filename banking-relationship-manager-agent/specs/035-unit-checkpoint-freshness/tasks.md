# Tasks: checkpoint freshness

- [x] T001 Add failing acceptance/regression tests for FR-001 FR-002 FR-003 FR-004 FR-005 in unit/skeleton tests: reporting shape, source/policy/definition/dependency invalidation, legacy coverage, failed rechecks and in-command mutations.
- [x] T002 Implement shared DAG freshness evaluation and dependency-bound checkpoint records in units.py for FR-001 FR-002 FR-003 FR-004 FR-005; depends on T001.
- [x] T003 Wire CLI verification paths/text reporting, gate enforcement, skeleton reuse and portable regression coverage for FR-001 FR-004 FR-005; depends on T002.
- [x] T004 Run focused tests, final lifecycle suite, portability, Ruff/mypy and configured sensors; update docs and actual validation evidence for FR-001 FR-002 FR-003 FR-004 FR-005; depends on T003.
- [x] T005 Run one separately identified read-only delegated worker trial in an isolated fixture for FR-001 FR-002 FR-003 FR-004 FR-005; report actual invocation, outcomes and custom-agent limitations; depends on T004. Attempt completed with harness/path failure, not successful delegated verification; see plan results.

Execution is sequential; independent checks may run concurrently. No new
dependencies, deployment, application changes, commits or extra review agents.
