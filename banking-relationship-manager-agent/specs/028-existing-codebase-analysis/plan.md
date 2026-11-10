# Implementation Plan: Existing-Codebase Analysis

**Branch**: current branch unchanged | **Date**: 2026-11-09 | **Spec**: [spec.md](./spec.md)

## Summary

Add a disabled `codebase-analysis` plugin defining an optional stage after
specify, led by architect, and a `brownfield` profile. A standard-library scanner
lists recognized source/test/manifest paths without reading application contents.
Stage definitions accept one applicability condition, `existing-codebase`;
starting that optional stage automatically records `stage_skipped` when no
recognized source exists. Conditional stages cannot be gates or required stages.
A Copilot skill and architect/conductor/plan guidance turn the inventory into
feature-local `codebase.md` findings before planning.

## Technical Context

- Python 3.11+, standard library; existing pytest/Ruff/mypy validation.
- Files: `speckit_flow/codebase.py`, stagedefs/models/state/cli integration;
  `.specify/plugins/codebase-analysis/`; `.github/skills/speckit-codebase/`.
- No cloud calls, application execution, dependency additions or source copying.
- Scan at most 10,000 filesystem entries; fail explicitly on access/limit errors.
- Tests use temporary non-banking projects and installed-bundle subprocesses.

## Constitution Check

The Aria constitution is not exported or imposed on other projects. Its applicable
quality/safety rules are respected: typed deterministic code, explicit errors,
bounded work, no secrets/source contents in reports, no approval bypass.
Pre-design and post-design checks: pass.

## Project Structure

```text
specs/028-existing-codebase-analysis/
  spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
  contracts/codebase.md
speckit_flow/codebase.py
.specify/plugins/codebase-analysis/
.github/skills/speckit-codebase/SKILL.md
tests/unit/speckit_flow/test_flow_codebase.py
```

## Compatibility and Validation

Existing stage data has no condition and retains current behavior. No core
stages or profiles are added. Installed plugin manifests remain forced-disabled
by the portable bootstrap. The scanner is reused for automatic skipping and
the public inventory command, so applicability cannot diverge.

The static standard workflow remains unchanged; optional brownfield routes use
the conductor/profile flow. A skipped stage causes the conductor to stop before
dispatching agents or marking it done. Planning uses analysis when present and
labels missing/stale evidence rather than treating inventory as architecture.
