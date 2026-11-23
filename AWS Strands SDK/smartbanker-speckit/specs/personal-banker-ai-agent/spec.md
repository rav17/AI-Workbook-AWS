# Specification: Personal Banker AI Agent

**Created**: 2026-04-04
**Status**: Draft
**Input**: Build a multi-agent financial assistant using Strands Agent SDK, AWS Bedrock, and AgentCore-managed memory for both short-term and long-term storage.

## Domain Context
At HDFC Bank, a private banker is typically a dedicated Relationship Manager (RM) attached to premium programmes such as Imperia, Preferred, Classic, Vishesh, Prime, or Infiniti. Benefits vary by programme and eligibility, and the bank may update programme features or rotate the assigned RM.

Programme Tier Definitions:
- **Classic**: Entry-level premium banking. Eligibility: Minimum balance ₹5 lakh. Benefits: Dedicated RM support for day-to-day banking, preferential loan pricing (up to 0.25% reduction), basic investment guidance for bank products, family extension for 2 members, fee waivers on select services.
- **Preferred**: Mid-tier premium. Eligibility: Minimum balance ₹15 lakh. Benefits: Enhanced RM support with faster coordination, preferential loan pricing (up to 0.5% reduction), wealth guidance for bank-linked investments, family extension for 4 members, premium card benefits, travel perks.
- **Imperia**: Top-tier premium. Eligibility: Minimum balance ₹1 crore. Benefits: Priority RM support with dedicated team, best preferential pricing (up to 1% reduction on loans), comprehensive wealth and investment advice, family extension for 6 members, exclusive lifestyle perks, priority digital channels.

A private banker usually supports:
1) day-to-day banking help and faster service coordination,
2) loan and borrowing support with preferential pricing,
3) investment and wealth guidance for bank-linked products,
4) family banking benefits and membership extension (tier-dependent: Classic=2, Preferred=4, Imperia=6 members),
5) preferential pricing and fee waivers,
6) premium card and spending benefits,
7) lifestyle and travel perks,
8) digital and priority support channels.

The system must model these programme-based benefits while clearly distinguishing what a private banker can do versus what they cannot do.

## User Scenarios & Testing

### User Story 1 - Financial Insight and Spending Analysis (Priority: P1)
A user wants a clear summary of recent spending patterns and high-confidence prioritization for saving opportunities.

**Why this priority**: This is the core value proposition and enables immediate user trust.

**Independent Test**: Run an interaction through the system with a sample transaction history and verify the output JSON contract includes spending insights, risk level, and a recommendation.

**Acceptance Scenarios**:
1. Given a user with recent transactions and no prior bad outcomes, when the user asks "How can I cut discretionary spending this month?", then the system returns a `status: success` recommendation with `confidence` high/medium, `risk_level` low/medium, and supporting `issues` if any.
2. Given a user with a repeated overspending pattern, when the system queries memory, then it retrieves only the last 20 interactions and top K similar financial behavior patterns without full history.

---

### User Story 2 - Savings Strategy and Personalization (Priority: P2)
A user wants personalized savings strategies that account for preference data, account balances, and prior recommendation outcomes.

**Why this priority**: Personalized savings advice increases long-term value and retention.

**Independent Test**: Validate a savings recommendation uses user preferences and does not repeat previously failed recommendations.

**Acceptance Scenarios**:
1. Given a user with low savings and a budget goal, when they ask for a savings plan, then the system returns a step-by-step savings approach with risk labeling and compliance-check disclaimers.
2. Given the system previously recommended a savings action that failed, when asked again, then the planner marks that outcome and avoids repeating the failed pattern.

---

### User Story 3 - Risk-Aware Investment Guidance (Priority: P2)
A user wants investment recommendations that account for risk tolerance, regulatory safety, and portfolio balance.

**Why this priority**: Investment advice is high-value and high-risk; it must be safe and personalized.

**Independent Test**: Send an investment query and verify the worker output contract, risk compliance check, and the presence of a disclaimer when risk is medium/high.

**Acceptance Scenarios**:
1. Given a user with conservative risk tolerance, when they request investment guidance, then the system returns low/medium risk recommendations and includes safety limits.
2. Given a risky request or conflict with compliance, when the system evaluates, then it returns `status: failure` or `confidence: low` with an explicit compliance issue.

---

### User Story 4 - Query Assistant and Financial Q&A (Priority: P3)
A user asks direct financial questions and expects factual, explainable answers.

**Why this priority**: Query assistance improves usability and supports follow-up interactions.

**Independent Test**: Validate that a query returns an explainable answer in the JSON contract and cites whether it used transaction or investment tools.

**Acceptance Scenarios**:
1. Given a user asks "What does my credit utilization mean?", when the system replies, then it includes an explainable recommendation and identifies risk/issue tags.
2. Given no tool data is needed, when the query is answered, then the system still validates the response with compliance rules.

---

### User Story 5 - Reflection and Self-Healing (Priority: P2)
The system must detect repeated poor advice, reflect on past outcomes, and decide if it should retry or finalize.

**Why this priority**: Self-healing prevents repeated mistakes and improves recommendation quality.

**Independent Test**: Simulate two failed advice results and verify the reflection layer flags repeated mistakes and the planner adjusts future recommendations.

**Acceptance Scenarios**:
1. Given two recent failed recommendations stored in short-term memory, when a new request is processed, then the planner retrieves failures and avoids the same pattern.
2. Given a worker returns `confidence: low`, when reflection happens, then the system may retry with a higher-confidence worker or finalize with an explicit risk warning.

**Clarification**: Reflection occurs at the orchestration layer (Coordinator): After a worker returns low confidence or failure, Coordinator retrieves short-term failures and decides to [RETRY with different worker] or [FINALIZE with risk warning]. This is distinct from planner-level outcome tracking: The planner MARKS each recommendation outcome in short-term memory for future retrieval; the Coordinator REFLECTS on patterns to make retry/finalize decisions.

---

### User Story 6 - HDFC Private Banker Programme Guidance (Priority: P3)
A customer wants a clear comparison of premium banker benefits by programme tier and a practical explanation of what the private banker can and cannot do.

**Why this priority**: Accurate programme-level guidance prevents overpromising and aligns the system with HDFC private banker expectations.

**Independent Test**: Verify the system can compare Classic, Preferred, and Imperia tiers and state admission criteria, family extension limits, and RM role boundaries.

**Acceptance Scenarios**:
1. Given a customer asks about Classic vs Preferred, when the system replies, then it explains dedicated RM support, loan help, investment advice, and family extension differences (only describing benefits available for the stated tier and confirming user eligibility first).
2. Given a customer asks what an HDFC private banker cannot do, when the system replies, then it clearly states no guaranteed approvals, no rule bypassing, and no independent fiduciary advice.

---

## Edge Cases
- If memory stores duplicate or noisy entries, the short-term manager must execute deduplication BEFORE prioritization: (1) Remove exact duplicates by interaction ID, (2) Retain unique failures/low-confidence records (canonical = first occurrence by timestamp), (3) Prune older duplicates. Canonical failure record = earliest timestamp for a given error type/pattern.
- If Bedrock is unavailable, the system must fail gracefully and record availability issues.
- If the user asks for prohibited financial advice, the risk agent must return `status: failure` with compliance issues.
- If the customer requests programme-specific benefits, the system must only describe benefits available for the stated tier and eligibility.
- If the customer asks about RM continuity, the system must explain RM rotation and the possibility of changing relationship managers.
- If the long-term memory store returns no matches, the planner must proceed with current facts and not delay recommendation.
- If vector memory returns stale behavioral patterns (older than 365 days), the system must filter and exclude them from long-term retrieval. Timestamp-based filtering is non-negotiable: no patterns >12 months are sent to any worker agent.

## Requirements

### Functional Requirements
- FR-001: The system MUST orchestrate multi-agent workflows using a coordinator, delegator, and worker agents.
- FR-002: The system MUST use AWS Bedrock for reasoning and embeddings.
- FR-003: The system MUST persist short-term memory and long-term semantic memory using AWS AgentCore memory capabilities.
- FR-004: The system MUST define and validate a strict financial tool registry.
- FR-005: The system MUST store only the last N short-term interactions (default 20) and prioritize failed advice and low-confidence outputs. Prioritization is applied AFTER deduplication: pruned list is sorted by (a) failure/low-confidence flag (true first), (b) timestamp (descending). Result: most recent failures surface first.
- FR-006: The system MUST return all worker outputs in the JSON contract: `status`, `confidence`, `recommendation`, `risk_level`, `issues`.
- FR-007: The planner MUST return strict JSON only and avoid sending full history to the LLM.
- FR-008: The system MUST include observability logs for memory pruning, reused patterns, mistake avoidance, planner adjustments, and risk decisions.
- FR-009: The system MUST include financial safety and compliance controls before any final recommendations.
- FR-010: The system MUST model the private banker as a relationship manager attached to premium tier programmes, reflecting tier-based benefits, eligibility requirements (Classic: ₹5L min balance, Preferred: ₹15L, Imperia: ₹1Cr), family extensions (Classic: 2 members, Preferred: 4, Imperia: 6), and changing RM coverage.
- FR-011: The system MUST clearly distinguish what a private banker can do versus what they cannot do, including support boundaries for loans, investments, approvals, compliance, and RM continuity.
- FR-012: The system MUST support learning from prior interactions and avoid repeated poor recommendations.
- FR-013: The system MUST expose all tool integrations via AWS Lambda functions through an AgentCore gateway.
- FR-014: The system MUST include deployment guidance for AWS AgentCore compatibility.
- FR-015: The system MUST include tests for repeated bad investment scenarios, memory pruning, and risk-aware recommendation behavior.

### Non-Functional Requirements
- NFR-001: The system MUST be modular and production-ready, with clear separation of concerns.
- NFR-002: The system MUST be explainable and provide rationale for decisions.
- NFR-003: The system MUST be secure and avoid storing raw sensitive transaction data beyond what is needed for reasoning.
- NFR-004: The system MUST be compatible with enterprise observability and AWS security best practices.
- NFR-005: The system MUST be architected for extensibility in agent roles and connectors.

## Key Entities
- UserProfile: id, risk_tolerance, savings_goal, preferences, account_summary.
- InteractionRecord: id, timestamp, intent, worker, status, confidence, outcome, issue_tags.
- FinancialPattern: semantic embedding, description, outcome, risk_level, timestamp.
- ToolDefinition: name, category, input_schema, output_schema, description, allowed_intents.
- RecommendationReport: status, confidence, recommendation, risk_level, issues, rationale.

## Success Criteria
- SC-001: The system returns structured recommendations consistent with the worker output contract for all primary scenarios.
- SC-002: The planner retrieves at most 20 recent short-term records and top K long-term semantic matches.
- SC-003: The system logs memory pruning and mistake avoidance events in observability output.
- SC-004: The system avoids repeating a failed recommendation pattern in follow-up interactions.
- SC-005: A deployment guide exists that describes AWS Bedrock, AgentCore memory, IAM, and AgentCore runtime steps.

## Assumptions
- The user has an AWS account with Bedrock and AgentCore memory runtime enabled.
- Bank transaction APIs and investment data APIs are available via secure connectors.
- The system runs in an AWS AgentCore-compatible environment with AgentCore memory available and no separate external memory infrastructure required.
- Primary execution happens in Python 3.11+.
- The first release is a backend AI orchestration service; no UI frontend is part of this scope.
- **Term Definitions**: "Priority" in user stories refers to business value ranking (P1 = core, P2 = important, P3 = nice-to-have). "High-confidence" means confidence score ≥ 0.8. "Fast service coordination" means response within 24 hours for premium tiers.
