# Agent Framework

This project separates the shared runtime framework from the business-specific agent behavior.

## Core contracts

- A framework runner is responsible for execution mode selection, state patch handoff, cleanup, and safe error handling.
- Runtime-checkable provider contracts and adapters isolate AgentCore Runtime session mapping,
  tenant-bounded Memory retrieval, and Gateway discovery/authorization from business logic.
- An agent manifest defines runtime and framework tuning values without allowing unsafe or unknown fields.
- Business-specific logic remains in the agent entrypoint and system prompt instead of the shared framework layer.

## AgentCore boundary

`aria/framework/agentcore.py` provides injectable adapters for local tests and approved
provider clients. The local fallback is deterministic and bounded; it is not a claim that
AgentCore services have been deployed. Live Runtime, Memory, and Gateway clients must be
provided by the deployment layer after the pinned SDK/API contracts and IAM policies are approved.

## Manifest schema

Each agent under `aria/agents/<agent_name>/agent.yaml` contains:

- `name`: the logical agent name
- `version`: the agent version
- `entrypoint`: Python callable path used at runtime
- `system_prompt`: prompt factory path
- `runtime`: execution mode and limits
- `framework`: framework tuning and environment settings
- `allowed_tools`: tool names allowed for that agent
- `unsafe_fields`: explicit disallowed workflow fields

## Local development boundary

The framework is intentionally thin. It provides orchestration, context redaction, and state guardrails, but does not hard-code business product logic or enforcement rules in the shared layer.

## Supported assumptions

- Framework support is for sync, async, and stream-style execution patterns.
- The implementation is designed to be deterministic and testable in a local environment.
- Provider-specific SDK tuning remains intentionally deferred until compatibility tests are in place.
