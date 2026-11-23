# SmartBanker AI Constitution

## Core Principles

### I. Specification-First
Every feature starts from a requirement in the spec. No code is written without a traced requirement. The spec is the single source of truth.

### II. Agent-Driven Architecture
All behavior is dynamic and model-driven via Strands SDK. No hardcoded decision trees or static workflows. Agents reason, plan, and route using LLM inference.

### III. Memory-Aware Design
Every agent interaction is memory-informed. Short-term memory (DynamoDB) provides recency. Long-term semantic memory (vector store) provides pattern learning. Memory degradation control prevents context bloat.

### IV. Financial Safety (NON-NEGOTIABLE)
All recommendations pass through Risk & Compliance validation. Non-fiduciary disclaimers are mandatory on investment advice. No guarantee language on loan facilitation. Compliance rules cannot be bypassed.

### V. Structured Contracts
Every worker returns a strict ExecutionResult JSON. Every plan is strict JSON. Schema violations are treated as failures. No unstructured agent outputs reach the user.

### VI. Self-Healing Loop
Every request follows: retrieve memory → plan → delegate → execute → introspect → reflect → retry if needed → persist learnings. No step is skipped.

### VII. Observability
All events are logged with correlation IDs. Memory pruning, pattern reuse, avoided mistakes, escalations, and compliance blocks are all observable.

### VIII. Minimal Implementation
Write only the code needed to satisfy the requirement. No speculative features. No over-engineering. YAGNI applies.

## Technology Constraints

- Runtime: Python 3.11+
- Agent SDK: Strands Agents SDK (strands-agents)
- LLM: AWS Bedrock (Claude Sonnet for reasoning, Titan for embeddings)
- Short-Term Memory: DynamoDB via AgentCore Memory
- Long-Term Memory: OpenSearch Serverless via AgentCore Memory
- Deployment: AWS AgentCore compatible
- Testing: pytest + hypothesis for property-based tests

## Development Workflow

1. Trace requirement → design component → implement → test → validate
2. Every PR must reference requirement IDs
3. Property-based tests for all correctness properties
4. Integration tests for all end-to-end flows

## Governance

This constitution supersedes all other practices. Amendments require documentation and approval. All code reviews must verify compliance with these principles.

**Version**: 1.0.0 | **Ratified**: 2025-07-18
