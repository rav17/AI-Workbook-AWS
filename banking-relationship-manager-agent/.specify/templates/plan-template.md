# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

[Primary requirement, proposed change and technical approach; cite existing evidence.]

## Technical Context

<!-- Replace examples with actual project details; mark material unknowns explicitly. -->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]

**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]

**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]

**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]

**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]

**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

## Project Structure

### Documentation (this feature)

Core artifacts: `spec.md`, this `plan.md`, then `tasks.md` from `/speckit-tasks`.

For the confirmed `quick` profile, keep decisions, affected interfaces/data,
risks and exact acceptance/regression commands here. Add `research.md`,
`data-model.md`, `quickstart.md` or `contracts/` only when the change or project
policy needs them. Other profiles retain their stage/policy-required artifacts.
List only actual documents and explain any required artifact still missing.

### Source Code (repository root)
[List actual affected source/test paths and reusable components. For brownfield
work describe the delta, compatibility and unchanged behavior, not a generic
architecture tree. Include command working directories and expected outcomes.]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [Actual violation, if any] | [Current need] | [Why simpler choices fail] |
