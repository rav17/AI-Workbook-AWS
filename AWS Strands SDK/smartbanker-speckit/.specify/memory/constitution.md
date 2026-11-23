# Personal Banker AI Agent Constitution

## Core Principles

### I. Safety-First Financial Intelligence
Every recommendation must enforce financial safety checks, risk labeling, disclaimers, and compliance validation before reaching the user.

### II. Memory-Aware Decisioning
Use short-term memory for recent failures and low-confidence outcomes only, and long-term semantic memory for relevant financial behavior patterns. Avoid full history and prevent context bloat.

### III. Modular Multi-Agent Orchestration
Maintain a clear separation between coordinator, delegator, and worker agents, with each role responsible for one layer of reasoning, routing, or execution.

### IV. Explainability and Traceability
All advice must be explainable, with structured output contracts, risk rationale, and observability events for planning, pruning, and mistake avoidance.

### V. Enterprise-Ready AWS Integration
Design for AWS Bedrock, AgentCore-managed memory, IAM guardrails, and AWS AgentCore runtime compatibility.

## Deployment & Security Constraints
- Do not send full user history to any LLM prompt.
- Store only the last N short-term interactions and top K long-term semantic matches.
- Avoid duplicate, noisy, or outdated memory data.
- Do not store sensitive raw credentials or bank payloads in memory.

## Development Workflow
- Define requirements in `specs/<feature>/spec.md`.
- Capture technical architecture in `specs/<feature>/plan.md`.
- Produce executable implementation tasks in `specs/<feature>/tasks.md`.
- Run cross-artifact analysis before implementation.

## Governance
The constitution is authoritative within this project. Changes must be documented, reviewed, and reflected across spec, plan, and task artifacts.

**Version**: 1.0 | **Ratified**: 2026-04-04 | **Last Amended**: 2026-04-04
