# Feature Specification: AWS Service Icons in Architecture Diagram

**Feature Branch**: `008-aws-service-icons`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "can you ensure that you use aws icons whereever possible in architecture diagram ?"

## User Scenarios & Testing

### User Story 1 - Recognize AWS Services at a Glance (Priority: P1)

As an architecture-diagram reader, I want AWS-managed services represented with recognizable AWS icons so that I can scan the system and distinguish AWS resources from people, external providers, and application components.

**Why this priority**: The architecture view is intended to communicate the system boundary and AWS service composition quickly.

**Independent Test**: Open the generated end-state Draw.io file and confirm supported AWS services have native AWS icons, while component names and flows remain readable.

**Acceptance Scenarios**:

1. **Given** an AWS-managed service has a matching icon in the diagram library, **When** the architecture diagram is generated, **Then** that service uses its AWS icon and keeps its identifying label.
2. **Given** a service has no specific matching icon, **When** the diagram is generated, **Then** it uses a relevant supported AWS category icon where appropriate or remains a clearly labeled generic component.
3. **Given** AWS icons are added, **When** the diagram is regenerated, **Then** all existing architecture connections remain attached to the same service cards.

### Edge Cases

- A service has no dedicated icon in the available Draw.io AWS library.
- A long service label must remain legible beside or below its icon.
- A component is not an AWS-managed service and must not be given a misleading AWS icon.

## Requirements

### Functional Requirements

- **FR-001**: The architecture diagram MUST use the matching native AWS icon for each AWS-managed service represented when that icon is available.
- **FR-002**: Each iconized service MUST retain a readable service label.
- **FR-003**: Components without a suitable AWS service icon MUST remain clearly labeled and MUST NOT be assigned a misleading icon.
- **FR-004**: Icon additions MUST preserve existing node relationships, edge endpoints, and page bounds.
- **FR-005**: The generated diagram MUST remain editable in Draw.io.

### Key Entities

- **AWS service node**: A labeled AWS-managed service and its diagram-library icon mapping.
- **Architecture flow**: A directed relationship between existing architecture components.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every AWS-managed service with a matching available library icon is rendered with that icon in the end-state diagram.
- **SC-002**: All service labels and all existing architecture connections are retained after regeneration.
- **SC-003**: The regenerated diagram is valid Draw.io XML and every connector references an existing node.

## Assumptions

- The current Draw.io AWS icon library used by the reference diagram remains available to readers.
- Existing architecture facts and system boundaries do not change as part of this visual update.
- Non-AWS providers, human roles, and custom application components continue to use the current generic visual styles.
