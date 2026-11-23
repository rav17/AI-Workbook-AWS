# Technical Plan: Personal Banker AI Agent

**Branch**: `main` | **Date**: 2026-04-04 | **Spec**: `spec.md`

## Summary
Build a production-grade Python backend for a Strands-compatible personal banker AI system. The implementation uses AWS Bedrock for reasoning and embeddings, AgentCore-managed memory for both short-term and semantic persistence, and AWS Lambda gateways for tool exposure. The system is designed to model relationship manager behavior, tier-based premium banking benefits, and financial safety controls.

## Technical Context
- Language/Version: Python 3.11+
- Primary Dependencies: `boto3`, `pydantic`, `pytest`, `botocore`, `typing_extensions`
- Runtime: AWS AgentCore-compatible container
- Memory: AgentCore-managed short-term and semantic memory
- Tool Gateway: AWS Lambda functions exposed through AgentCore gateway
- Testing: `pytest`
- Project Type: Backend AI orchestration service
- Scale/Scope: enterprise-grade financial AI with extensible plugin-based tools
- Performance Goals: low-latency planning, bounded memory retrieval, rapid tool invocation
- Constraints: strict JSON planner contract, no full-history context leaks, memory size bounds, compliance gating on all recommendations

## Architecture

### Core Agent Roles
- **Coordinator Agent**: orchestrates memory retrieval, planner prompt generation, reflection, and final recommendation delivery.
- **Delegator Agent**: validates intent, selects the correct worker, resolves tool compatibility, and enforces the worker output contract.
- **Worker Agents**:
  - `SpendingAnalyzerAgent`: spending and transaction trend analysis.
  - `SavingsAdvisorAgent`: personalized savings actions and buffer recommendations.
  - `InvestmentAdvisorAgent`: risk-aware investment guidance and portfolio suitability.
  - `QueryAssistantAgent`: direct financial Q&A and explainability.
  - `RiskComplianceAgent`: safety gating, program eligibility validation, and compliance issue detection.

### Memory and Reflection
- **Short-Term Memory**: `AgentCoreMemoryManager` stores the last N interaction summaries, prioritizing failures and low-confidence outputs. It prunes duplicates and removes outdated entries automatically. Workflow: (1) Store interaction outcome (planner marks), (2) On next request, retrieve top failures/patterns (coordinator reflects).
- **Long-Term Semantic Memory**: `AgentCoreMemoryManager` stores embeddings for behavior patterns, past recommendations, and outcomes. It returns top-K similarity results and filters stale matches (>365 days). Long-term context sent to workers is capped: top-K matches only, no full embedding DB.
- **Reflection Flow**:
  1. Retrieve short-term failures and relevant semantic patterns (capped at top-K matches, max context window).
  2. Generate a strict JSON plan that factors in prior failures.
  3. Execute a worker and validate the JSON output contract.
  4. If low confidence or failure occurs, reflect and conditionally retry or finalize with an explicit risk warning.

**Clarification on "Marking" vs "Reflection"**: 
- Planner-level MARKING: Record each recommendation outcome in short-term memory (status, confidence, outcome, issue_tags) after worker completes. This is synchronous and immediate.
- Coordinator-level REFLECTION: On next user request, Coordinator retrieves marked failures and decides to [RETRY with alternate worker] or [FINALIZE with risk warning]. This is asynchronous (cross-request) and strategic.

### Tooling
- Define a strict tool registry in `src/tools/registry.py` for:
  - `transaction_fetcher`
  - `balance_checker`
  - `investment_data_api`
  - `budgeting_calculator`
- Expose all tools via AWS Lambda functions behind an AgentCore gateway.
- Validate tool usage by intent and input/output schema before invocation.

### Risk, Safety, and Compliance
- Enforce financial safety rules before any recommendation is returned.
- Model private banker capabilities and limitations, including tier-based benefits and RM eligibility.
- Avoid overpromising loan approvals, independent fiduciary advice, or bank policy overrides.
- Require explicit disclaimers on medium/high-risk guidance and when recommending bank-partner products.

### Observability
- Emit structured logs for:
  - memory pruning events
  - reused financial patterns
  - avoided repeated mistakes
  - planner adjustments
  - risk decisions and compliance determinations
- Centralize logging in `src/observability/logger.py`.

## Implementation Phases

### Phase 1: Foundation
- Implement environment and configuration management in `src/config/settings.py`.
- Build `src/tools/registry.py` with strict schema validation.
- Build `src/llm/bedrock_client.py` for Bedrock text and embedding calls.
- Build `src/memory/agentcore_memory.py` for AgentCore STM/LTM interfaces.
- Add structured logging utilities.

### Phase 2: Core Agents
- Implement `src/agents/coordinator.py` for orchestration and reflection.
- Implement `src/agents/delegator.py` for intent routing and tool validation.
- Implement worker agents in `src/agents/workers/`.
- Create `src/agents/agent_runner.py` as an entrypoint.

### Phase 3: Tool Gateway Integration
- Define Lambda wrapper contracts for each tool.
- Document AgentCore gateway endpoints for tool invocation.
- Ensure all tool traffic is validated and logged.

### Phase 4: Safety and Personal Banker Modeling
- Add tier-based program modeling, RM behavior, and eligibility logic to the planner.
- Implement `RiskComplianceAgent` for bank policy and benefit caveat checks.
- Ensure the system frames private banker advantages as programme-dependent and conditional.

### Phase 5: Testing and Deployment
- Add unit tests for memory pruning, low-confidence handling, and repeated-bad-advice avoidance.
- Add contract tests for the worker JSON response shape.
- Document AWS AgentCore deployment, tool gateway setup, and IAM requirements.

## Project Structure

```text
src/
├── agents/
│   ├── __init__.py
│   ├── agent_runner.py
│   ├── coordinator.py
│   ├── delegator.py
│   └── workers/
│       ├── __init__.py
│       ├── investment_advisor.py
│       ├── query_assistant.py
│       ├── risk_compliance.py
│       ├── savings_advisor.py
│       └── spending_analyzer.py
├── llm/
│   ├── __init__.py
│   └── bedrock_client.py
├── memory/
│   ├── __init__.py
│   └── agentcore_memory.py
├── observability/
│   ├── __init__.py
│   └── logger.py
├── tools/
│   ├── __init__.py
│   └── registry.py
└── config/
    ├── __init__.py
    └── settings.py

tests/
├── test_memory_pruning.py
├── test_risk_recommendation.py
└── test_repeated_bad_advice_learning.py

deployment/
├── aws_deployment.md
└── agentcore_compatibility.md
```

## Key Gates
- No implementation until the spec and this plan are aligned.
- Memory must use AgentCore-managed STM/LTM only.
- Tool integrations must be exposed via Lambda gateway.
- Worker outputs must always conform to the JSON response contract.
- All financial advice must include safety and eligibility caveats.

## Next Step
Implement the foundation phase files and validate the plan by creating `src/tools/registry.py`, `src/llm/bedrock_client.py`, and `src/memory/agentcore_memory.py` first.
