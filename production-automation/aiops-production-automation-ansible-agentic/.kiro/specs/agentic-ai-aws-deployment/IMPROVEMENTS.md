# Agentic AI AWS Deployment — Improvement Proposals

## Document Information

| Field | Value |
|-------|-------|
| **Author** | Ravindra Yadav |
| **Date** | August 2026 |
| **Status** | Proposed |
| **Spec** | `.kiro/specs/agentic-ai-aws-deployment` |
| **Informed By** | Amazon Bedrock Intelligent Prompt Routing, Bedrock Prompt Caching, Bedrock AgentCore Runtime, Strands Agents SDK Memory, AWS Well-Architected Agentic AI Lens, LLM Agent Evaluation Frameworks, Multi-Model Routing Research |

---

## Executive Summary

The agentic-ai-aws-deployment spec transforms the rule-based pipeline into an AI-powered
system using Amazon Bedrock. The core implementation (reasoning agent, correlator, SSM
executor, escalation manager) is in place. These improvements address operational gaps
that appear at production scale: cost optimization, reasoning quality evaluation,
multi-model intelligence, and deployment on the new Bedrock AgentCore platform.

### Current State

```
Alert → Normalize → Enrich → Correlate → AI Reason (Bedrock) → Execute (SSM) → Notify
                                              ↓
                                    Fallback chain: Claude → Nova Pro → Haiku → Nova Lite
                                    30s timeout, 2 retries, rule-based fallback
```

### Target State (After Improvements)

```
Alert → Normalize → Enrich → Correlate → [Intelligent Route] → Execute → [Evaluate] → Notify
                                              ↓
                                    Prompt Cache (90% cost reduction on repeated context)
                                    Smart Model Selection (simple→cheap, complex→capable)
                                    Reasoning Quality Scoring (offline evaluation)
                                    AgentCore Runtime (serverless agent hosting)
```

---

## Current Strengths (Already Well-Implemented)

- ✅ AI Reasoning Agent with Bedrock invocation, retry, and 30s timeout
- ✅ 4-model fallback chain (Claude Sonnet → Nova Pro → Haiku → Nova Lite)
- ✅ Structured RemediationPlan output with confidence scoring
- ✅ Alert correlation within configurable time window (30-900s)
- ✅ Historical incident learning from DynamoDB memory store
- ✅ SSM executor with prerequisite checks, sequential steps, output capture
- ✅ Escalation manager with timeout and human response handling
- ✅ Three operating modes (ai_only, rules_only, ai_with_fallback)
- ✅ Token budget management with truncation by recency
- ✅ Sensitive label redaction before storage

---

## Improvement 1: Bedrock Prompt Caching (90% Cost Reduction)

### Priority: P1 — Immediate Cost Savings

### Problem Statement

Every AI reasoning invocation sends the full system prompt (~2000 tokens) plus
historical context to Bedrock. For alerts that share the same alert_name (e.g.,
10 "CPUHigh" alerts in an hour), the system prompt and static instructions are
identical. Without caching, you pay full input token price every time.

### AWS Feature

[Amazon Bedrock Prompt Caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)
can reduce costs by up to 90% and latency by up to 85% for supported models.
Cached input tokens cost ~90% less than standard tokens. The cache persists for
5 minutes after each access.

### Proposed Improvement

```python
# In reasoning_agent.py — structure prompts for cache reuse

# CACHEABLE PREFIX (same across all alerts of same type):
system_prompt = """You are an SRE AI agent analyzing infrastructure alerts.
Given alert context and historical incidents, produce a structured
RemediationPlan with confidence score..."""  # ~1500 tokens, rarely changes

# Mark as cache point
cache_breakpoint = {"type": "cache_control", "cache_type": "ephemeral"}

# VARIABLE SUFFIX (changes per alert):
user_prompt = f"""
Alert: {alert_name} on {host}
Severity: {severity}
Historical: {recent_incidents}
"""

# Bedrock API call with caching enabled
response = bedrock.invoke_model(
    modelId=model_id,
    body={
        "system": [{"text": system_prompt, "cache_control": cache_breakpoint}],
        "messages": [{"role": "user", "content": user_prompt}]
    }
)
```

### Expected Impact

| Metric | Before | After |
|--------|--------|-------|
| Input token cost per invocation | ~$0.003 | ~$0.0003 (90% reduction) |
| Time-to-first-token (TTFT) | ~2-3s | ~0.5-1s (85% reduction) |
| Monthly Bedrock cost (100 alerts/day) | ~$9/month | ~$1.50/month |

### Acceptance Criteria

1. THE system prompt SHALL be structured with a stable prefix that can be cached
2. THE agent SHALL use Bedrock prompt caching API for supported models
3. WHEN the same alert_name fires multiple times within 5 minutes, subsequent
   invocations SHALL benefit from cached prefix (measurable via cache hit metric)
4. THE system SHALL publish `PromptCacheHitRate` CloudWatch metric
5. Fallback: if prompt caching is unavailable, standard invocation proceeds

### Effort Estimate: 1-2 days

---

## Improvement 2: Intelligent Model Routing (Cost-Quality Optimization)

### Priority: P1 — 40-70% Additional Cost Savings

### Problem Statement

The current fallback chain (Claude → Nova Pro → Haiku → Nova Lite) only activates
when a model FAILS. It always starts with the most expensive model (Claude Sonnet)
even for simple, repetitive alerts that a cheaper model handles equally well.
A P3 "DiskFull" alert with 95% historical success rate doesn't need Claude Sonnet's
reasoning power — Nova Lite at 1/10th the cost produces the same answer.

### AWS Feature

[Amazon Bedrock Intelligent Prompt Routing](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-routing.html)
dynamically predicts response quality of each model and routes to the optimal
model based on cost and quality. Can reduce costs by up to 30% without compromising accuracy.

### Proposed Improvement

```
Smart Model Selection based on alert complexity:

SIMPLE alerts (route to CHEAP model — Nova Lite/Haiku):
  - Alert has been seen 5+ times before with same playbook outcome
  - Historical effectiveness > 90% for the likely playbook
  - Single host, single service, P3/P4 severity
  - Estimated: 70% of all alerts

MODERATE alerts (route to MID model — Nova Pro):
  - Alert seen before but with mixed outcomes
  - Correlation group with 2-3 alerts
  - P2 severity
  - Estimated: 20% of all alerts

COMPLEX alerts (route to POWERFUL model — Claude Sonnet):
  - Never-seen-before alert (no history)
  - Correlation group with 4+ alerts
  - P1 severity
  - All past remediation attempts failed
  - Estimated: 10% of all alerts

Cost impact: 70% × cheap + 20% × mid + 10% × expensive = ~60% total cost reduction
```

### Acceptance Criteria

1. THE agent SHALL classify alert complexity BEFORE selecting a model
2. Complexity classification SHALL use: historical frequency, outcome consistency,
   correlation group size, and severity
3. THE system SHALL publish per-model invocation counts and costs as CloudWatch metrics
4. Model routing decisions SHALL be logged in the audit trail
5. IF the cheaper model produces confidence < 0.5, THE system SHALL re-invoke with
   the next-tier model (escalation within routing, not just on failure)

### Effort Estimate: 2-3 days

---

## Improvement 3: Offline Agent Evaluation Framework

### Priority: P2 — Reasoning Quality Assurance

### Problem Statement

The AI agent's reasoning quality is never systematically evaluated. If a model update
degrades performance (e.g., a new Claude version hallucinates more), or if prompt
changes introduce regressions, there's no way to detect this before production impact.

### Industry Precedent

- [LLM Agent Evaluation Frameworks](https://www.braintrust.dev/articles/ai-agent-evaluation-framework):
  "Track performance across every decision the agent makes"
- [Enterprise Agentic AI Benchmarks](https://arxiv.org/html/2511.08042v1):
  "Traditional LLM benchmarks fail to measure agentic capabilities such as
  multi-step tool use and decision-making under uncertainty"

### Proposed Improvement

```
Create an offline evaluation suite that replays historical incidents:

1. GOLDEN DATASET: Curate 50-100 historical incidents with known-good outcomes
   - 20 simple cases (should match existing playbook with high confidence)
   - 20 complex cases (correlation groups requiring root-cause analysis)
   - 10 edge cases (should escalate, not auto-remediate)
   - 10 never-seen cases (should produce reasonable novel suggestions)

2. EVALUATION METRICS:
   - Action correctness: did it select the right playbook/action? (vs. human label)
   - Confidence calibration: are 0.9 confidence predictions 90% correct?
   - Escalation accuracy: does it escalate when it should? (no false negatives)
   - Reasoning quality: does the explanation cite relevant history?
   - Latency: p50/p95 reasoning time
   - Cost: tokens consumed per case

3. CI INTEGRATION:
   - Run evaluation suite on every prompt template change
   - Run weekly against latest model versions
   - Alert if accuracy drops > 5% from baseline
   - Block deployment if escalation accuracy < 95%

4. REPORT:
   Weekly "Agent Health" report showing trending accuracy, cost, and latency
```

### Acceptance Criteria

1. THE evaluation suite SHALL contain ≥ 50 labeled test cases
2. THE suite SHALL be runnable via `pytest -m evaluation` with real Bedrock calls
3. THE suite SHALL produce a JSON report with per-case and aggregate metrics
4. THE CI pipeline SHALL fail if action correctness drops below 80%
5. Evaluation results SHALL be stored in S3 for historical trending

### Effort Estimate: 3-5 days (dataset curation is the hard part)

---

## Improvement 4: Strands Agents SDK Integration (Structured Tool Use)

### Priority: P2 — Better Agent Architecture

### Problem Statement

The current `AIReasoningAgent` is a custom implementation that manually constructs
prompts, parses responses, and manages retries. The Strands Agents SDK provides
production-ready agent infrastructure (tool use, memory management, structured output)
that eliminates custom code and integrates natively with Bedrock AgentCore.

### AWS Feature

[Strands Agents SDK](https://strandsagents.com/docs/user-guide/concepts/memory/overview/)
provides:
- `@tool` decorator for defining agent capabilities
- Built-in memory management (short-term + long-term)
- Structured output via Pydantic models
- Native Bedrock integration with automatic retry/fallback
- AgentCore Runtime deployment support

### Proposed Improvement

```python
from strands import Agent, tool
from strands.models import BedrockModel
from pydantic import BaseModel

class RemediationPlan(BaseModel):
    """Structured output from the agent."""
    selected_action: str
    target_resource: str
    confidence_score: float
    reasoning_explanation: str
    steps: list[dict]

@tool
def query_incident_history(alert_name: str, limit: int = 10) -> str:
    """Query DynamoDB for historical incidents matching this alert."""
    # DynamoDB query logic here
    return formatted_history

@tool
def check_host_health(hostname: str) -> str:
    """Check if target host is reachable via SSM."""
    # SSM prerequisite check
    return health_status

@tool
def execute_remediation(plan: dict) -> str:
    """Execute the remediation plan via SSM RunCommand."""
    # SSM execution logic
    return execution_result

# Agent definition
agent = Agent(
    model=BedrockModel("anthropic.claude-3-sonnet-20240229-v1:0"),
    tools=[query_incident_history, check_host_health, execute_remediation],
    system_prompt="You are an SRE AI agent...",
    output_model=RemediationPlan,
)
```

### Benefits Over Current Custom Implementation

| Aspect | Current Custom | Strands SDK |
|--------|---------------|-------------|
| Prompt construction | Manual string formatting | Automatic from tool schemas |
| Response parsing | Custom JSON parsing with fallbacks | Validated Pydantic model |
| Tool use | Not supported (single-shot) | Multi-step tool calling loop |
| Memory | Custom DynamoDB queries | Built-in memory manager |
| Retry/fallback | Custom async logic | Built-in with model fallback |
| Deployment | ECS Fargate (custom) | AgentCore Runtime (serverless) |

### Effort Estimate: 5-7 days (refactoring existing agent)

---

## Improvement 5: Bedrock AgentCore Runtime Deployment

### Priority: P3 — Serverless Agent Hosting

### Problem Statement

The AI agent currently runs inside the ECS Fargate task alongside the entire
pipeline. This means the agent's compute scales with the pipeline (not independently),
and you pay for agent compute even when no alerts are being processed.

### AWS Feature

[Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
provides serverless, purpose-built hosting for AI agents. It handles container
orchestration, session management, scalability, and security isolation. Zero-cost
when idle.

### Proposed Improvement

```
Split architecture:
  Pipeline (ECS Fargate): normalize → enrich → correlate → [invoke agent] → execute
  Agent (AgentCore Runtime): AI reasoning (scales independently, zero idle cost)

Benefits:
- Agent scales to 0 when no alerts (cost savings during quiet periods)
- Agent can scale independently of pipeline
- Session management handled by AgentCore (not custom code)
- Direct integration with Bedrock (no VPC endpoints needed)
- Built-in observability (traces, metrics)
```

### Effort Estimate: 3-5 days (after Strands SDK migration)

---

## Improvement 6: Confidence Calibration and Self-Assessment

### Priority: P3 — More Trustworthy Decisions

### Problem Statement

The AI agent's confidence scores are uncalibrated. A score of 0.8 doesn't reliably
mean "80% likely to succeed." Studies show LLMs are often overconfident. Without
calibration, the escalation threshold (0.7) may be too low or too high.

### Proposed Improvement

```
Add calibration layer between raw model confidence and decision threshold:

1. Track historical accuracy per confidence band:
   - Raw confidence 0.9-1.0: actual success rate = 78% (overconfident)
   - Raw confidence 0.7-0.9: actual success rate = 65%
   - Raw confidence 0.5-0.7: actual success rate = 40%

2. Apply calibration function:
   calibrated_confidence = calibration_curve(raw_confidence)
   
   Example: raw 0.85 → calibrated 0.72 (based on historical accuracy)

3. Use calibrated confidence for escalation decisions:
   - Escalate if calibrated_confidence < threshold (not raw)
   - This reduces false negatives (failures that weren't escalated)

4. Recalibrate weekly from accumulated outcomes:
   - Fit isotonic regression on (raw_confidence, actual_outcome) pairs
   - Store calibration curve in SSM Parameter Store
   - Apply on next alert cycle
```

### Effort Estimate: 2-3 days

---

## Implementation Plan

### Phase 1: Cost Optimization (Week 1-2)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 1.1 | Implement prompt caching for system prompt | `src/agentic_ai/agents/reasoning_agent.py` | 1d |
| 1.2 | Add cache hit rate CloudWatch metric | `src/agentic_ai/observability/metrics_publisher.py` | 0.5d |
| 1.3 | Implement alert complexity classifier | `src/agentic_ai/agents/model_router.py` | 1.5d |
| 1.4 | Route to appropriate model based on complexity | `src/agentic_ai/agents/reasoning_agent.py` | 1d |
| 1.5 | Add per-model cost tracking metrics | `src/agentic_ai/observability/metrics_publisher.py` | 0.5d |

**Deliverable:** 60-90% Bedrock cost reduction with no accuracy loss on simple alerts.

### Phase 2: Quality Assurance (Week 2-4)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 2.1 | Curate golden dataset (50 labeled cases) | `tests/evaluation/golden_dataset.json` | 2d |
| 2.2 | Build evaluation harness | `tests/evaluation/run_evaluation.py` | 1.5d |
| 2.3 | Define metrics (accuracy, calibration, latency) | `tests/evaluation/metrics.py` | 1d |
| 2.4 | CI integration (fail on regression) | `.github/workflows/ci.yml` | 0.5d |
| 2.5 | Implement confidence calibration | `src/agentic_ai/agents/calibration.py` | 2d |
| 2.6 | Weekly recalibration cron | `scripts/recalibrate.py` | 0.5d |

**Deliverable:** Systematic quality measurement; calibrated confidence reduces false negatives.

### Phase 3: Agent Architecture (Week 4-6)

| Task | Improvement | Files | Effort |
|------|-------------|-------|--------|
| 3.1 | Refactor agent to Strands SDK tools pattern | `src/agentic_ai/agents/reasoning_agent.py` | 3d |
| 3.2 | Define tools (@tool decorators) | `src/agentic_ai/agents/tools/` | 2d |
| 3.3 | Implement structured output model | `src/agentic_ai/models/domain.py` | 0.5d |
| 3.4 | Migrate memory to Strands memory manager | `src/agentic_ai/agents/reasoning_agent.py` | 1d |
| 3.5 | Deploy to AgentCore Runtime (optional) | `src/agentic_ai/infra/stacks/` | 3d |

**Deliverable:** Production-grade agent on AWS-native infrastructure with tool-use loops.

---

## Total Effort Summary

| Phase | Duration | Effort | Key Deliverable |
|-------|----------|--------|-----------------|
| Phase 1: Cost Optimization | Week 1-2 | 4.5 days | 60-90% cost reduction |
| Phase 2: Quality Assurance | Week 2-4 | 7.5 days | Evaluation framework + calibration |
| Phase 3: Agent Architecture | Week 4-6 | 9.5 days | Strands SDK + AgentCore |
| **Total** | **6 weeks** | **~21.5 days** | |

---

## New Files to Create

```
src/agentic_ai/agents/
├── model_router.py            ← Complexity-based model selection
├── calibration.py             ← Confidence score calibration
├── tools/                     ← Strands @tool definitions (Phase 3)
│   ├── __init__.py
│   ├── history_tool.py
│   ├── health_tool.py
│   └── execute_tool.py
└── (existing reasoning_agent.py modified)

tests/evaluation/
├── golden_dataset.json        ← 50+ labeled test cases
├── run_evaluation.py          ← Evaluation harness
├── metrics.py                 ← Accuracy/calibration metrics
└── conftest.py

scripts/
├── recalibrate.py             ← Weekly confidence recalibration

config/
├── model_routing.yml          ← Complexity thresholds for model selection
```

---

## Metrics Impact

| Metric | Description |
|--------|-------------|
| `PromptCacheHitRate` | % of invocations using cached prefix |
| `ModelRoutingDecision` | Which model was selected (dimension: model_id) |
| `CostPerInvocation` | Estimated $ per reasoning call |
| `CalibratedConfidence` | Post-calibration confidence (vs raw) |
| `EvaluationAccuracy` | Weekly accuracy score from golden dataset |
| `ModelEscalationWithinRouting` | Cheap model → expensive model re-invocations |

---

## References

- [Amazon Bedrock Prompt Caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)
- [Amazon Bedrock Intelligent Prompt Routing](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-routing.html)
- [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
- [Strands Agents SDK — Memory & Tools](https://strandsagents.com/docs/user-guide/concepts/memory/overview/)
- [Strands Agents SDK — Structured Output](https://strandsagents.com/docs/examples/structured_output/)
- [AWS Well-Architected GenAI Lens — Prompt Caching](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/gencost03-bp03.html)
- [Bedrock Advanced Operations Playbook](https://repost.aws/articles/ARD6jc9NNrQQ-FAvEpBOWiwA/amazon-bedrock-advanced-operations-playbook-optimizing-performance-cost-and-availability)
- [LLM Agent Evaluation: Practical Framework](https://www.braintrust.dev/articles/ai-agent-evaluation-framework)
- [Enterprise Agentic AI Benchmark Research](https://arxiv.org/html/2511.08042v1)

---

## Future Improvements (Not for Current Implementation)

### Future: Multi-Agent Collaboration

Deploy specialized agents for different domains (network, database, application)
that collaborate via Strands multi-agent patterns. Deferred until single-agent
proves value and complexity warrants specialization.

### Future: Bedrock Knowledge Base for Runbook RAG

Store operational runbooks in a Bedrock Knowledge Base and let the agent retrieve
relevant procedures via RAG. Deferred until runbook corpus is large enough to
benefit from semantic search vs. static playbook matching.

### Future: Model Distillation for Common Alerts

Use Amazon Bedrock Model Distillation to create a smaller, faster, cheaper model
trained specifically on your alert patterns. Deferred until sufficient training
data (>1000 labeled incidents) is accumulated.
