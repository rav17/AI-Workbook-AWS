# Implementation Plan: AWS Service Icons in Architecture Diagram

**Branch**: `008-aws-service-icons` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-aws-service-icons/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Use Draw.io's native AWS resource icons for AWS-managed services in the end-state architecture diagram. Add a generator helper that places an icon within the existing labeled service card, leaving card IDs and connectors intact. Use a broad AWS category icon or the current generic card when no matching stencil is available.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: Python standard library; Draw.io native AWS4 stencil library

**Storage**: Editable `.drawio` XML artifact

**Testing**: Run the focused generator and parse the output XML; assert icon references, connector endpoints, and page bounds

**Target Platform**: Draw.io / diagrams.net

**Project Type**: Architecture documentation and diagram generator

**Performance Goals**: Diagram generation completes in the existing local workflow

**Constraints**: Use only verified AWS4 stencil IDs; preserve labels, edges, and current page geometry; do not modify runtime behavior

**Scale/Scope**: One end-state diagram and its existing generator

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Pass**: This change is a visual documentation improvement only. It does not change transactional state, authorization, client data, or runtime configuration. Existing architecture boundaries and readable labels remain in place.

## Project Structure

### Documentation (this feature)

```text
specs/008-aws-service-icons/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md
```

### Source Code (repository root)
```text
docs/architecture/generate_diagrams.py
docs/architecture/08_Aria_End_State_Architecture.drawio
```

**Structure Decision**: Extend the existing Draw.io generator and regenerate the current end-state diagram. No new runtime modules, interfaces, dependencies, or tests are required.
