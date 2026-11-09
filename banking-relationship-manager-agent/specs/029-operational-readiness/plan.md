# Implementation Plan: Operational Readiness

**Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

## Summary

Add a disabled `operational-readiness` plugin with a `release-ready` profile,
using existing stages specify -> plan -> tasks -> implement -> deploy -> operate.
Gate specify, plan, implement, deploy and operate. Reuse existing sensor audit,
profile scoping and human gates; no new stage, agent or deployment commands.
Add a `readiness` builtin that checks feature-local `release.md` and `runbook.md`.

## Technical Context

- Python 3.11 standard library; existing pytest, Ruff and mypy.
- `speckit_flow/readiness.py`: bounded UTF-8 reads, required Markdown sections,
  explicit evidence lines, template/unchecked-item rejection.
- `speckit_flow/sensors.py`: register builtin; readiness-specific fingerprints
  include the two records in addition to the existing spec/plan/tasks artifacts.
- Fixed filenames only; reject symlinks/reparse points, non-files, invalid text
  and records larger than 256 KiB. No reading/executing referenced evidence.
- `.specify/plugins/operational-readiness/`: disabled manifest, profile, scoped
  required sensor, release/runbook templates, README.
- `.github/skills/speckit-readiness/`: how to prepare/review records; deploy,
  operations and conductor guidance consume it for the opted-in profile.
- Portable bundle allowlist includes the module, skill and plugin files.

## Constitution Check

Applicable workflow principles: authoritative persisted state, bounded work,
typed deterministic checks, invalidation and no approval bypass. Existing
engine conventions use dataclasses and explicit validation rather than adding
Pydantic to the dependency-free portable engine; tests cover all boundary checks.
Do not export the Aria constitution or its banking/AWS policies.
Pre-design and post-design: pass. No external calls or infrastructure mutations.

## Design and Evidence

Existing `sensors.run_stage` persists audited results; `gate_problems` compares
artifact hashes and `state.decide_gate` enforces human actors. Existing `section`
only checks heading presence in spec/plan/tasks; extending it broadly would not
reject incomplete operational templates. A small dedicated builtin avoids
changing existing section behavior or global fingerprint scope.

The checker validates exact level-two headings (case insensitive), substantive
body content and a standalone `- Evidence: ...` line in every required section.
Ignore fenced examples and HTML comments. Reject common TODO/TBD/placeholders
and unchecked tasks in visible text. Duplicate required headings fail.
Evidence truth is a human review responsibility; a pass means structure only.

Only readiness results fingerprint release/runbook. Fixed artifact failures
yield a failing result or gate diagnostic, never a success-shaped empty snapshot.
Edits, deletion or unreadable records prevent reuse of passing results. External
references are not fingerprinted; immutable references and human rechecks are
required by guidance. No automatic stage or gate approvals.

## Structure and Validation

Unit tests in `tests/unit/speckit_flow/test_flow_readiness.py` cover each required
section/evidence, templates, malformed/unreadable/oversized/symlink records,
scoping and stale results. Installed-project subprocess test in
`tests/unit/test_speckit_bootstrap.py` enables the pack in a non-banking fixture,
walks the route, rejects missing/stale records and agent gate attempts, and
verifies human decisions and audit integrity.

User approved workflow/bootstrap pytest, Ruff/mypy and doctor; fixture-only
simulated human approvals are allowed. Live deployment and AI generation are
not part of verification.
