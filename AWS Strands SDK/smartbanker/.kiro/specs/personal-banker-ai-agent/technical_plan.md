# SmartBanker Technical Plan

## Architecture Summary

Three-tier agent hierarchy using Strands SDK "agents-as-tools" pattern:
- Coordinator Agent (orchestrator) → owns Delegator + memory + self-healing loop
- Delegator Agent (router) → owns Tool Registry + worker selection
- Worker Agents (specialists) → domain-specific execution with structured output

All agents use `strands.Agent` with `BedrockModel`. Workers are passed as tools to the Delegator via `.as_tool()`. The Delegator is a tool of the Coordinator.

All 12 financial tools are implemented as individual AWS Lambda functions, registered as Lambda targets on AgentCore Gateway. The Gateway exposes them as MCP tools to the agent. A dual execution path (Lambda vs local stubs) supports both production and development/test modes.

## Component → Requirement Mapping

| Component | File | Requirements |
|---|---|---|
| Config & Data Models | `config/settings.py` | R16, R18, R23, R29 |
| Data Models | `config/models.py` | R1, R12, R13, R28 |
| Tool Registry | `tools/registry.py` | R8 |
| Lambda Invoker | `tools/lambda_invoker.py` | R8, R16 |
| Tool Implementations | `tools/financial_tools.py` | R3, R4, R5, R6 |
| Lambda Handlers | `lambdas/*/handler.py` | R8, R16 |
| SAM Template | `deployment/template.yaml` | R16 |
| DynamoDB Memory | `memory/dynamodb_manager.py` | R9, R11 |
| Vector Memory | `memory/vector_memory.py` | R10, R11 |
| Memory Degradation | `memory/degradation.py` | R11 |
| Worker: Spending | `agents/workers/spending_analyzer.py` | R3 |
| Worker: Savings | `agents/workers/savings_advisor.py` | R4 |
| Worker: Investment | `agents/workers/investment_advisor.py` | R5, R21 |
| Worker: Query | `agents/workers/query_assistant.py` | R6 |
| Worker: Risk | `agents/workers/risk_compliance.py` | R7, R34 |
| Delegator | `agents/delegator.py` | R2 |
| Coordinator | `agents/coordinator.py` | R1, R13, R17 |
| Observability | `observability/logger.py` | R14 |
| Compliance | `compliance/disclosure_manager.py` | R15, R31, R33, R35 |
| Entry Point | `main.py` | R16, R17 |
| Worker: KYC/AML | `agents/workers/kyc_aml_agent.py` | R41, R42, R43, R44, R45, R46, R47, R48, R49, R50 |
| KYC Lambda Handlers | `lambdas/document_extractor/`, etc. | R41, R42, R46 |
| Tests | `tests/` | All properties |

## Implementation Order

1. Config + Data Models (foundation)
2. Tool Registry + Lambda Invoker + Tool Implementations (worker dependencies)
3. Lambda Handlers (12 individual Lambda functions)
4. Memory Layer (DynamoDB + Vector + Degradation)
5. Worker Agents (all core + Phase 2 workers)
6. Delegator Agent (routing)
7. Coordinator Agent (orchestration + self-healing)
8. Compliance + Observability
9. Entry Point + SAM Template
10. Tests

## Key Technical Decisions

1. Workers are Strands Agents passed via `.as_tool()` to the Delegator
2. The Delegator is a Strands Agent passed via `.as_tool()` to the Coordinator
3. Memory retrieval happens BEFORE the Coordinator invokes the LLM
4. The self-healing loop is implemented as a Python method, not an agent loop
5. ExecutionResult validation uses Pydantic models
6. DynamoDB uses user_id as partition key, timestamp as sort key
7. Vector memory uses Bedrock Titan embeddings
8. **All 12 tools are Lambda-backed**: Each tool is an individual Lambda function registered as a target on AgentCore Gateway
9. **Dual execution path**: `USE_LAMBDA=true` invokes Lambda via boto3; `USE_LAMBDA=false` runs local stubs for dev/test
10. **Lambda naming convention**: `{LAMBDA_PREFIX}-{tool_name}` (e.g. `smartbanker-transaction_fetcher`)
11. **AgentCore Gateway integration**: All tool Lambdas registered as MCP targets on AgentCore Gateway with OAuth2 auth
12. **IAM scoping**: Agent runtime role includes `lambda:InvokeFunction` for `smartbanker-*` functions only
13. **AgentCore Runtime**: Agent deployed via `BedrockAgentCoreApp` wrapper and `agentcore launch`

## Lambda Tool Architecture

```
tools/financial_tools.py          tools/lambda_invoker.py         lambdas/*/handler.py
┌─────────────────────┐          ┌──────────────────────┐        ┌──────────────────┐
│ @tool                │          │                      │        │                  │
│ transaction_fetcher()│──────────│ _invoke_or_local()   │───────▶│ Lambda handler   │
│                      │          │                      │        │ (production)     │
│ (Strands @tool       │          │ USE_LAMBDA=true?     │        └──────────────────┘
│  decorator)          │          │ ├── yes → boto3.invoke│
│                      │          │ └── no  → local stub │
└─────────────────────┘          └──────────────────────┘

AgentCore Gateway (MCP targets — OAuth2 auth)
├── smartbanker-transaction_fetcher      (Lambda target)
├── smartbanker-balance_checker          (Lambda target)
├── smartbanker-investment_data_api      (Lambda target)
├── smartbanker-budgeting_calculator     (Lambda target)
├── smartbanker-service_request_processor (Lambda target)
├── smartbanker-escalation_tracker       (Lambda target)
├── smartbanker-document_guidance_tool   (Lambda target)
├── smartbanker-loan_product_catalog     (Lambda target)
├── smartbanker-tier_pricing_engine      (Lambda target)
├── smartbanker-activity_analyzer        (Lambda target)
├── smartbanker-tier_benefit_mapper      (Lambda target)
├── smartbanker-compliance_rule_checker  (Lambda target)
├── smartbanker-document_extractor       (Lambda target)
├── smartbanker-identity_verifier        (Lambda target)
├── smartbanker-sanctions_checker        (Lambda target)
├── smartbanker-pep_screener             (Lambda target)
└── smartbanker-risk_scorer              (Lambda target)
```
