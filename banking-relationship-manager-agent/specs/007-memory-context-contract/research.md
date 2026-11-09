# Research: Memory Context Contract Normalization

## Decision: Keep `MemoryEntry` as the canonical in-process value

**Rationale**: The local store already returns `MemoryEntry`, and the context builder consumes its `key` and `value`. The remote data-plane client's dictionaries are provider-shaped and should be normalized at the existing `AgentCoreMemoryAdapter` boundary.

**Alternatives considered**: Teach `ContextBuilder` to branch between dictionaries and objects. Rejected because it would leak provider representation into a consumer and preserve multiple contracts.

## Decision: Use a narrow structural retrieval protocol for context assembly

**Rationale**: Context assembly needs only retrieval of normalized entries. Python's `typing.Protocol` supports structural static typing without requiring concrete stores to inherit from a framework base class. An explicit `None` represents the no-memory case.

**Alternatives considered**: Keep `object` and probe with `hasattr`. Rejected because unsupported objects silently behave like an empty store and typing cannot verify the contract. Use an ABC. Rejected because there is no shared retrieval implementation or need for runtime-enforced inheritance.

## Decision: A configured remote backend must own deletion

**Rationale**: Falling back to local deletion when a remote client lacks `delete` can report success without deleting remote records. The existing `MemoryClient` protocol already requires deletion, so the adapter should delegate directly whenever a remote client is configured.

**Alternatives considered**: Introduce a separate optional deletion protocol immediately. Deferred because the current adapter contract exposes retrieval, add, and delete and its declared client protocol requires all three; an absent method is a contract violation and should fail rather than silently change storage targets.

## Decision: Preserve policy and provider boundaries

**Rationale**: AgentCore data-plane retrieval may continue returning dictionaries, and its write operation remains denied pending data-owner approval. This fix changes only the in-process adapter result contract and context dependency.

**Alternatives considered**: Change AWS data-plane parsing and write policy together. Rejected as unrelated and higher risk.