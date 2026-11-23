# Contract: AgentCore Memory API

## Overview
AgentCore provides managed short-term and long-term memory interfaces for storing interaction records and semantic patterns.

## Short-Term Memory Interface
- **Purpose**: Store recent interaction summaries with automatic pruning.
- **Key**: Interaction ID or user ID.
- **Value**: JSON object with interaction details.

### Store Operation
```json
{
  "operation": "store_stm",
  "key": "interaction_123",
  "value": {
    "user_id": "user_456",
    "timestamp": "2023-01-01T10:00:00Z",
    "outcome": "success",
    "confidence": 0.9
  },
  "ttl_seconds": 604800
}
```

### Retrieve Operation
```json
{
  "operation": "retrieve_stm",
  "user_id": "user_456",
  "limit": 20,
  "filter": {
    "status": "failure"
  }
}
```

**Response:**
```json
{
  "records": [
    {
      "key": "interaction_123",
      "value": {...},
      "timestamp": "2023-01-01T10:00:00Z"
    }
  ]
}
```

## Long-Term Semantic Memory Interface
- **Purpose**: Store and retrieve embeddings for pattern matching.
- **Key**: Pattern ID.
- **Value**: Embedding vector + metadata.

### Store Operation
```json
{
  "operation": "store_ltm",
  "key": "pattern_789",
  "embedding": [0.1, 0.2, ...],
  "metadata": {
    "description": "Overspending pattern",
    "outcome": "failure"
  }
}
```

### Search Operation
```json
{
  "operation": "search_ltm",
  "query_embedding": [0.1, 0.2, ...],
  "top_k": 5,
  "filter": {
    "timestamp_after": "2023-01-01"
  }
}
```

**Response:**
```json
{
  "matches": [
    {
      "key": "pattern_789",
      "similarity": 0.95,
      "metadata": {...}
    }
  ]
}
```

## Error Handling
- **InvalidKey**: Key format error.
- **StorageFull**: Memory limit exceeded.
- **ServiceUnavailable**: AgentCore service down.

## Integration Notes
- Automatic deduplication and pruning.
- No direct access to raw data; all operations through AgentCore SDK.