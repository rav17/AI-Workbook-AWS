# Data Model: Memory Context Contract Normalization

## MemoryEntry

Represents one normalized in-process memory value.

| Field | Type | Constraint |
|---|---|---|
| `key` | `str` | Required, non-empty provider/local key |
| `value` | `str` | Required, provider content |
| `tenant_id` | `str` | Required and equal to the requested tenant |
| `expires_at` | `datetime | None` | Existing optional expiry; unchanged by normalization |

## Provider Memory Record

The remote memory client returns mappings containing `key`, `value`, and `tenant_id`. The adapter validates that each is a string and that the tenant equals the request tenant before constructing a `MemoryEntry`. Invalid records fail closed and are not passed to context assembly.

## MemoryRetriever

Consumer-facing capability implemented structurally by the local `MemoryStore` and `AgentCoreMemoryAdapter`. It retrieves a bounded list of `MemoryEntry` values for a tenant. Context assembly may receive no retriever, represented explicitly as `None`.

## Deletion Behavior

When the adapter has a remote client, deletion is delegated only to that client. Local storage is used for deletion only when no remote client is configured.