# Tasks: AWS Service Icons in Architecture Diagram

**Input**: Design documents from `/specs/008-aws-service-icons/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

## Phase 1: User Story 1 - Recognize AWS Services at a Glance (Priority: P1)

**Goal**: Render available AWS4 icons in AWS-managed service cards while preserving readable labels and architecture flows.

**Independent Test**: Regenerate the end-state diagram, parse the XML, and verify icon stencil mappings, labels, connector endpoints, and page bounds.

- [X] T001 [US1] Add an AWS resource-card helper to `docs/architecture/generate_diagrams.py` that embeds an AWS4 icon and preserves the card node ID.
- [X] T002 [US1] Apply verified AWS4 icon mappings to AWS-managed services in `docs/architecture/generate_diagrams.py` and regenerate `docs/architecture/08_Aria_End_State_Architecture.drawio`.
- [X] T003 [US1] Validate icon mappings, labels, connector endpoints, and page bounds in `docs/architecture/08_Aria_End_State_Architecture.drawio`.

## Dependencies & Execution Order

- T001 precedes T002 because the service-card helper is required by the node mappings.
- T002 precedes T003 because validation requires the regenerated artifact.
- No independent parallel tasks are identified; the generator and generated diagram are one sequential deliverable.

## Implementation Strategy

Implement the icon helper, map only verified AWS4 stencil IDs, regenerate the end-state diagram, and validate its XML structure and geometry. No runtime or business-logic code changes are in scope.
