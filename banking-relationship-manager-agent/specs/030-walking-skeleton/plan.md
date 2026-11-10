# Implementation Plan: Walking Skeleton

**Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

## Summary

Disabled `walking-skeleton` pack adds optional stage `walking-skeleton` after
analyze (and therefore tasks) before implement, led by developer. Profile
`skeleton-first`: specify, plan, tasks, walking-skeleton, implement; gates
specify, plan, walking-skeleton. Assign quality support to the skeleton stage.
No automatic skip or new approval mechanism.

## Technical Context

Python 3.11 standard library, existing pytest/Ruff/mypy. Extend `units add` with
optional `--files` root-relative comma-separated paths; old units omit it.
Tracked unit checkpoint captures SHA-256 snapshots before/after approved verify.
Invalidate its prior checkpoint before attempting revalidation, including
unapproved-command/access failures. Preserve checkpoints when adding new units.

Add a `skeleton` builtin, scoped to the opt-in profile, requiring reserved unit
`walking-skeleton`, actual task references, at least three tracked files
(implementation/test/journey report), and current passing checkpoint. Required
feature-local `skeleton.md` is one of those files; humans judge meaningful scope.
Sensor fingerprints include units metadata, verification policy and declared
files; gate freshness does not execute verification. Guidance and templates
define observable input/output, boundaries, mocks, acceptance and limitations.

## Constitution Check

Use engine-standard explicit typed boundary validation and dependency-free
stdlib rather than introduce Pydantic into the portable toolkit. Preserve
authoritative persisted state, human gates, bounded checks and explicit errors.
No banking policies exported, live services used or approvals granted.
Pre/post-design: pass. Human approved focused tests, lint/types, doctor and
disposable-fixture-only simulated approvals.

## Files and Safety

`speckit_flow/units.py`, cli/sensors integration; optional plugin and
`speckit-skeleton` skill, developer/conductor guidance, portable exact allowlist.
No source scanning: only declared files, at most 100 unique paths, each <=1 MiB.
Paths use canonical relative POSIX spelling in stored data; CLI accepts Windows
separators and normalizes them. Reject absolute/drive/traversal paths, aliases,
symlink/reparse ancestors, non-regular/missing files and access errors.
Snapshots store hashes only, not source content. Declared file mutations during
verification fail; untracked files are not covered. Nonzero/timeout runs cannot
reuse old success. Regular units without files retain existing behavior.

## Validation

Tests first in `test_flow_skeleton.py`: path limits/errors, unchanged/modified
files, command reapproval, failure invalidation, metadata/task checks, checkpoint
preservation, sensor freshness. Installed fixture: entry CLI reads JSON and
passes through application logic to exact output checked by a standard-library
test. Verify is human-approved only within fixture. Fail gate before checkpoint,
after changes and for agents, then human fixture approval allows implement.
Core stage/profile counts and disabled packs stay unchanged.
