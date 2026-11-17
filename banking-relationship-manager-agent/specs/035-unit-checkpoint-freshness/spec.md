# Specification: checkpoint freshness and ready-unit reporting

## Scope and user scenario

A developer resumes construction, lists units, and sees which units are ready,
blocked, stale or verified without running commands or spawning workers.
Changing a tracked dependency invalidates dependent evidence before a new
checkpoint or implementation approval can rely on it.

## Requirements

- FR-001: Read-only unit listing reports status, reasons, direct blockers,
  checkpoint presence and verification coverage; preserve the units array and
  checkpointed field, with checkpointed meaning currently verified.
- FR-002: Detect changed/missing tracked files, changed unit definitions,
  changed/unapproved commands and stale/missing dependency evidence.
- FR-003: Bind new checkpoints to dependencies' exact evidence revisions;
  invalidate failed rechecks for tracked and untracked units. Reject changes
  during verification, including dependency changes.
- FR-004: Use the same freshness assessment for dependency checkpoint admission,
  unchecked-unit enforcement and walking-skeleton checks. Never execute commands
  while reporting status; propagate custom CLI verify paths consistently.
- FR-005: Keep untracked-unit support, explicitly label command-only coverage,
  and require refresh for legacy evidence missing freshness metadata. No
  automated scheduling, test-result caching or new workflow stages.

## Acceptance

Tests cover independent units, dependency chains and diamonds, file/definition/
command changes, policy/access errors, legacy evidence, failed rechecks,
concurrent mutation during verification, CLI JSON/text and implementation gates.
Existing skeleton behavior and portable installs remain supported.

## Exclusions

No automatic concurrency, graph-wide source discovery, external test freshness
guarantee, deployment, application changes or perfect-review loops. Actual
custom-agent dispatch is a separate trial, not implied by unit reporting.
