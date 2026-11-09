# Feature Specification: Memory Context Contract Normalization

**Feature Branch**: `007-memory-context-contract`
**Created**: 2026-10-02
**Status**: Draft
**Input**: Follow-up to the Python design audit: normalize local and remote memory results before context construction and make remote deletion capability failures explicit.

## User Scenarios & Testing

### User Story 1 - Consistent Memory Context (Priority: P1)

As a client whose conversation uses memory, I need locally stored and remotely retrieved memories to be interpreted consistently so context assembly works regardless of the configured backend.

**Why this priority**: Remote provider results currently have a different shape from local entries, causing context construction to fail when a remote-backed adapter is supplied.

**Independent Test**: Pass local and remote-backed adapters to the context builder and verify both produce equivalent history and memory values while current workflow state remains authoritative.

**Acceptance Scenarios**:

1. Given a remote provider returns valid tenant-scoped records, when the adapter retrieves them for context, then each result has the same key, value, and tenant fields as a local memory entry.
2. Given a memory key is also present in current workflow state, when context is built, then the current workflow value takes precedence.
3. Given a provider returns a malformed record or a record for another tenant, when the adapter normalizes it, then the invalid result is rejected and is not included in context.
4. Given no memory backend is configured, when context is built, then the existing no-memory fallback is returned without probing for methods dynamically.
5. Given a remote client is configured but does not support deletion, when deletion is requested, then the operation fails explicitly and does not delete from local fallback storage.

## Edge Cases

- A provider record omits or has a non-string key, value, or tenant identifier.
- A provider record tenant identifier differs from the tenant requested by the caller.
- An empty record set is returned by either backend.
- A remote client lacks a required deletion method while a local fallback store contains records.

## Requirements

### Functional Requirements

- **FR-001**: Memory values supplied to context assembly MUST have a consistent key, value, and tenant identity regardless of whether they originated from local storage or a remote provider.
- **FR-002**: Context assembly MUST depend on an explicit retrieval contract and MUST accept an absent memory backend without treating an incompatible object as an empty backend.
- **FR-003**: Remote records MUST be validated and tenant-checked before they are exposed to context assembly.
- **FR-004**: A configured remote backend MUST NOT silently route an unsupported deletion to local storage; the deletion capability failure MUST be visible to the caller.
- **FR-005**: Current workflow state MUST continue to take precedence over memory values, and existing sensitive-text redaction MUST remain unchanged.

### Key Entities

- **MemoryEntry**: A tenant-scoped memory item with a key, value, and optional expiry.
- **MemoryRetriever**: A consumer-facing capability that retrieves normalized memory entries for a tenant.
- **Provider Memory Record**: A remote result containing provider fields that must be validated and mapped to a MemoryEntry.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All valid local and remote records produce context with the same entry shape and no attribute errors.
- **SC-002**: Tests prove zero cross-tenant or malformed records are included in assembled context.
- **SC-003**: Tests prove a configured remote client's missing delete capability never triggers local deletion.
- **SC-004**: Existing workflow-state precedence, redaction, and empty-memory fallback tests continue to pass.

## Assumptions

- The existing MemoryEntry is the canonical in-process memory value; no new domain entity is needed.
- The remote AgentCore data-plane client may continue returning provider-shaped dictionaries; normalization belongs in AgentCoreMemoryAdapter.
- This change does not enable AgentCore Memory writes or alter the existing data-owner approval policy.
- The dispatcher refactor and broader AriaAgent decomposition remain out of scope.