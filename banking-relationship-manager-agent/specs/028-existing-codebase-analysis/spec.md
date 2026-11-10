# Feature Specification: Existing-Codebase Analysis

**Created**: 2026-11-09
**Status**: Draft
**Input**: Add reusable existing-codebase analysis before planning, with explicit greenfield skipping.

## User Scenarios & Testing

### User Story 1 - Understand an existing project (Priority: P1)

A developer changing an established project needs evidence of its architecture,
dependencies, interfaces and tests before choosing a design.

**Why this priority**: Grounding plans in actual code prevents unnecessary replacements and missed integrations.

**Independent Test**: Analyze a small non-banking sample with source and test
files and verify the resulting inventory cites real paths without executing application code.

**Acceptance Scenarios**:
1. Given existing application sources, when analysis is requested, then a bounded inventory identifies source, test and dependency-manifest locations for architecture review.
2. Given that inventory, when the architect completes the analysis stage, then the feature has evidence-backed architecture, interface, dependency, test and change-impact findings with unknowns called out.

### User Story 2 - Avoid unnecessary greenfield ceremony (Priority: P2)

A developer starting a new project should not need reverse-engineering work.

**Independent Test**: Run the optional analysis route in a repository containing
only workflow tooling and documentation; the analysis stage is skipped with an audited reason.

**Acceptance Scenarios**:
1. Given no recognized application sources, when the optional stage starts, then it is skipped automatically and the next stage remains available.
2. Given unreadable sources or a scan limit exceeded, when detection runs, then it reports an error instead of classifying the project as greenfield.

### User Story 3 - Reuse the capability elsewhere (Priority: P3)

A team can opt into this capability in another project without banking assumptions.

**Independent Test**: Install the portable bundle, enable its optional analysis pack,
and validate the route and stage lead in a separate non-banking project.

**Acceptance Scenarios**:
1. Given the pack is disabled, existing routes and stage counts remain unchanged.
2. Given the pack is enabled, the analysis stage precedes planning and is assigned to the architect.

### Edge Cases

- Tooling-only repositories, infrastructure source and unfamiliar file extensions.
- Symlinked directories, generated files, large trees and inaccessible directories.
- Conditional stages configured as mandatory or human approval gates.
- Analysis artifacts becoming outdated after subsequent source changes.

## Requirements

### Functional Requirements

- **FR-001**: Provide a read-only, bounded inventory of recognized source files, test locations and dependency manifests without executing the target application or copying source contents.
- **FR-002**: Analysis guidance MUST cover architecture, dependencies, interfaces, tests and change impact with file evidence and explicit unknowns.
- **FR-003**: The optional analysis stage MUST run after specification and before planning, led by the architect, without changing default routes.
- **FR-004**: A project without recognized application source MUST automatically skip this optional stage with an audited reason; this heuristic MUST be documented.
- **FR-005**: Detection MUST exclude installed toolkit files, generated/dependency directories and symlink traversal, and report access/limit errors rather than silently skipping.
- **FR-006**: Conditional skipping MUST NOT bypass a required stage or a human approval gate.
- **FR-007**: The stage, guidance and scanner MUST be included in the portable toolkit, with the example pack disabled by default.
- **FR-008**: Planning and conductor guidance MUST consume the analysis when present and never claim an inventory alone proves architecture or test results.

### Key Entities

- **Inventory**: Recognized sources, test files, manifests, scan limits and detection outcome.
- **Analysis**: Feature-local, human-reviewable architecture and change-impact evidence.
- **Conditional Stage**: Optional route step with a deterministic applicability condition.

## Success Criteria

- **SC-001**: Existing-source and tooling-only fixtures are correctly distinguished in all acceptance tests.
- **SC-002**: An enabled non-banking sample route completes or skips analysis without bypassing pending human gates.
- **SC-003**: Default profiles and optional pack enablement remain unchanged after delivery.
- **SC-004**: Reports contain paths and findings, not raw application source or unverified test-success claims.

## Assumptions

- Initial detection uses a documented source-extension allowlist, not complete language understanding.
- Generated/dependency folders are excluded by known names; project-specific scope is explained in the report.
- Semantic interpretation remains the architect's responsibility. The scan is not an authoritative dependency or call graph.
- No live application execution, cloud access or new mandatory workflow stage is introduced.
