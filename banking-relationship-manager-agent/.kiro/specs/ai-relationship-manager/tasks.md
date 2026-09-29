# Implementation Plan: Aria — AI Relationship Manager Agent

## Overview

This plan implements the Aria AI Relationship Manager agent using the Strands Agents SDK (Python) with Amazon Bedrock as the foundation model provider. The implementation is structured in incremental steps: project scaffolding, data models, tools, agent core, guardrails, session management, event handling, API integration, and testing.

## Tasks

- [ ] 1. Set up project structure, dependencies, and core interfaces
  - [ ] 1.1 Initialize Python project with directory structure and dependencies
    - Create `aria/` package with `__init__.py` files for subpackages: `tools/`, `guardrails/`, `session/`, `events/`, `models/`, `api/`
    - Create `pyproject.toml` with dependencies: `strands-agents`, `strands-agents-tools`, `boto3`, `pydantic`, `httpx`, `python-dateutil`
    - Create `requirements.txt` and `requirements-dev.txt` (pytest, hypothesis, moto, pytest-asyncio, ruff)
    - Create `tests/` directory with `property/`, `unit/`, `integration/` subdirectories and `conftest.py`
    - _Requirements: 14.1, 14.2_

  - [ ] 1.2 Define core data models and enums
    - Create `aria/models/client.py` with `ClientProfile`, `Segment`, `RiskLevel`, `FamilyMember`, `AccountSummary`, `ClientPreferences` dataclasses
    - Create `aria/models/wallet.py` with `WalletProfile`, `ExternalDeposit`, `ExternalDematAccount`, `ExternalInsurance`, `ConsolidationOpportunity` dataclasses
    - Create `aria/models/interaction.py` with `InteractionSummary`, `FollowUpAction`, `Message` dataclasses
    - Create `aria/models/maturity.py` with `MaturityEvent`, `ReinvestmentOption`, `OutflowEvent` dataclasses
    - Create `aria/models/risk.py` with `RiskQuestion`, `RiskOption`, `QuestionnaireResponse`, `RiskProfile` dataclasses
    - Create `aria/models/compliance.py` with `KYCStatus`, `AMLFlag`, `TransactionActivity` dataclasses
    - Create `aria/models/escalation.py` with `EscalationTicket`, `EscalationReason`, `InteractionContext` dataclasses
    - Create `aria/models/session.py` with `Session`, `AgentResponse` dataclasses
    - Create `aria/models/knowledge.py` with `KBResponse`, `Citation` dataclasses
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 4.1, 6.1, 9.1, 10.1_

  - [ ] 1.3 Define configuration and constants
    - Create `aria/config.py` with `AriaConfig` class holding model ID, guardrail ID, DynamoDB table names, CRM API endpoints, confidence thresholds, maturity notification days, outflow thresholds
    - Create `aria/constants.py` with risk-to-product mappings, escalation reason enums, segment tier configurations, and error message templates
    - _Requirements: 3.1, 4.1, 4.2, 14.2_

- [ ] 2. Implement CRM Tool
  - [ ] 2.1 Implement CRM tool functions
    - Create `aria/tools/crm_tool.py` with Strands `@tool` decorated functions
    - Implement `read_client_profile(client_id: str) -> ClientProfile` — calls CRM API to retrieve client profile including segment flags, accounts, and preferences
    - Implement `update_client_profile(client_id: str, updates: ProfileUpdate) -> bool` — sends structured updates to CRM API
    - Implement `log_interaction(client_id: str, summary: InteractionSummary) -> bool` — logs interaction summary with topics, preferences, follow-ups
    - Implement `create_followup_reminder(client_id: str, reminder: FollowUpReminder) -> bool` — schedules follow-up in CRM
    - Include retry logic with exponential backoff for CRM API calls
    - Include graceful degradation when CRM is unavailable (return cached/default data and log incident)
    - _Requirements: 1.1, 1.2, 6.1, 6.2, 6.3, 14.1, 14.3_

  - [ ]* 2.2 Write unit tests for CRM tool
    - Test `read_client_profile` with mocked CRM API responses (valid profile, empty profile, API error)
    - Test `update_client_profile` with valid and invalid update payloads
    - Test `log_interaction` with complete and partial interaction summaries
    - Test `create_followup_reminder` with valid due dates and assigned_to values
    - Test retry logic and graceful degradation on CRM unavailability
    - _Requirements: 6.1, 6.2, 6.3, 14.1, 14.3_

- [ ] 3. Implement Knowledge Base Tool
  - [ ] 3.1 Implement Knowledge Base tool function
    - Create `aria/tools/knowledge_tool.py` with Strands `@tool` decorated function
    - Implement `query_product_info(query: str, product_category: str | None = None) -> KBResponse` — calls Amazon Bedrock Knowledge Bases API to retrieve product rates, terms, and policies
    - Include source date extraction and citation formatting from KB response
    - Include confidence score evaluation against threshold
    - Handle KB unavailability by returning empty response with zero confidence (signals escalation needed)
    - _Requirements: 5.1, 8.3, 13.1, 13.2, 13.3_

  - [ ]* 3.2 Write unit tests for Knowledge Base tool
    - Test successful KB retrieval with citations and source dates
    - Test low-confidence response handling (below threshold)
    - Test KB unavailability fallback behavior
    - Test product_category filtering
    - _Requirements: 13.1, 13.2, 13.3_

- [ ] 4. Implement Risk Assessment Tool
  - [ ] 4.1 Implement risk assessment tool functions
    - Create `aria/tools/risk_tool.py` with Strands `@tool` decorated functions
    - Implement `get_risk_questionnaire() -> list[RiskQuestion]` — returns structured risk assessment questions with weighted options
    - Implement `assess_risk_appetite(responses: list[QuestionnaireResponse]) -> RiskProfile` — calculates risk level from weighted questionnaire responses, maps to suitable product categories
    - Include scoring logic: sum(option.score * question.weight) mapped to CONSERVATIVE/MODERATE/AGGRESSIVE thresholds
    - _Requirements: 1.3, 3.1_

  - [ ]* 4.2 Write unit tests for Risk Assessment tool
    - Test questionnaire structure validity (all questions have options, weights > 0)
    - Test risk scoring with all-conservative, all-aggressive, and mixed responses
    - Test product category mapping for each risk level
    - _Requirements: 1.3, 3.1_

- [ ] 5. Checkpoint - Core tools implemented
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement Maturity and Retention Tool
  - [ ] 6.1 Implement maturity and retention tool functions
    - Create `aria/tools/maturity_tool.py` with Strands `@tool` decorated functions
    - Implement `check_upcoming_maturities(client_id: str, days_ahead: int = 30) -> list[MaturityEvent]` — queries core banking system for upcoming maturities within timeframe
    - Implement `detect_large_outflows(client_id: str, threshold_amount: float) -> list[OutflowEvent]` — detects account outflows above configured threshold
    - Include reinvestment option population with current rates from Knowledge Base
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 6.2 Write unit tests for Maturity tool
    - Test maturity detection within 30-day window (boundary: exactly 30 days, 31 days, 0 days)
    - Test outflow detection above and below threshold
    - Test reinvestment option formatting
    - _Requirements: 4.1, 4.2_

- [ ] 7. Implement Compliance Tool
  - [ ] 7.1 Implement compliance tool functions
    - Create `aria/tools/compliance_tool.py` with Strands `@tool` decorated functions
    - Implement `check_kyc_status(client_id: str) -> KYCStatus` — verifies client's KYC documentation currency, returns status with missing documents list
    - Implement `flag_aml_activity(client_id: str, activity: TransactionActivity) -> AMLFlag` — flags suspicious activity for AML review, creates escalation to compliance team
    - Include KYC gating logic: if not current, return missing documents and pause product requests
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 7.2 Write unit tests for Compliance tool
    - Test KYC current/expired/missing scenarios
    - Test AML flag creation with threshold breach scenarios
    - Test missing documents list population
    - _Requirements: 9.1, 9.2, 9.3_

- [ ] 8. Implement Escalation Tool
  - [ ] 8.1 Implement escalation tool function
    - Create `aria/tools/escalation_tool.py` with Strands `@tool` decorated function
    - Implement `escalate_to_human_rm(client_id: str, reason: EscalationReason, context: InteractionContext) -> EscalationTicket` — creates escalation ticket with full interaction history, assigned priority, and expected response timeline
    - Include priority assignment logic based on escalation reason type
    - Include response timeline mapping (HIGH_VALUE_CREDIT → 4 hours, LEGAL_DISPUTE → 2 hours, etc.)
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 8.2 Write unit tests for Escalation tool
    - Test escalation ticket creation for each EscalationReason enum value
    - Test priority assignment logic
    - Test response timeline mapping
    - Test interaction context inclusion
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 9. Implement Guardrail Configuration
  - [ ] 9.1 Implement Amazon Bedrock Guardrails integration
    - Create `aria/guardrails/config.py` with `GuardrailConfig` class defining content filters, denied topics, sensitive info filters, word filters, and prompt attack filter settings
    - Create `aria/guardrails/processor.py` with `process_with_guardrails(message: str, guardrail_id: str) -> GuardrailResult` function
    - Implement input guardrail check: detect prompt injection, redact sensitive credentials (PINs, CVVs, OTPs, passwords), filter denied topics
    - Implement output guardrail check: ensure no internal system details leak, redact any residual PII
    - Implement fail-closed behavior: if guardrail processing fails, block the message and log
    - _Requirements: 7.1, 7.2, 7.3, 12.1, 12.2, 12.3, 12.4_

  - [ ]* 9.2 Write unit tests for Guardrail configuration
    - Test credential pattern detection (4-digit PIN, 3-digit CVV, 6-digit OTP, password strings)
    - Test prompt injection detection patterns
    - Test fail-closed behavior on guardrail processing error
    - Test output sanitization (no system prompt leakage)
    - _Requirements: 7.1, 7.2, 7.3, 12.1, 12.2, 12.3, 12.4_

- [ ] 10. Implement Session Manager
  - [ ] 10.1 Implement DynamoDB-backed session management
    - Create `aria/session/manager.py` with `SessionManager` class
    - Implement `create_session(client_id: str) -> Session` — creates new session with client context loaded from CRM
    - Implement `load_session(session_id: str) -> Session` — loads session state from DynamoDB
    - Implement `save_session(session: Session) -> None` — persists session state to DynamoDB
    - Implement `end_session(session_id: str, summary: InteractionSummary) -> None` — ends session, logs interaction to CRM, cleans up
    - Include session recovery: on corrupt/missing state, create fresh session and warn client
    - _Requirements: 14.1, 6.1_

  - [ ]* 10.2 Write unit tests for Session Manager
    - Test session creation with CRM profile loading
    - Test session persistence round trip (save then load)
    - Test session recovery on corrupted state
    - Test session end with CRM interaction logging
    - _Requirements: 14.1, 6.1_

- [ ] 11. Checkpoint - Infrastructure components complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement Aria Agent Core
  - [ ] 12.1 Implement Aria agent with Strands SDK
    - Create `aria/agent.py` with `AriaAgent` class using Strands Agent SDK
    - Define system prompt incorporating: personalization by name, professional/empathetic tone, segment-aware behavior, risk disclosure requirements, escalation rules, CTG suggestion triggers
    - Register all tools: `read_client_profile`, `update_client_profile`, `log_interaction`, `create_followup_reminder`, `query_product_info`, `get_risk_questionnaire`, `assess_risk_appetite`, `check_upcoming_maturities`, `detect_large_outflows`, `check_kyc_status`, `flag_aml_activity`, `escalate_to_human_rm`
    - Implement `handle_message(session_id: str, message: str) -> AgentResponse` — orchestrates input guardrails → session load → agent reasoning → output guardrails → session save → CRM log
    - Implement `handle_proactive_event(event: MaturityEvent) -> None` — handles EventBridge maturity notifications and initiates proactive outreach
    - Include error handling: retry on model errors, graceful degradation on tool failures
    - _Requirements: 1.1, 1.3, 1.4, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 5.1, 5.2, 5.3, 5.4, 8.1, 8.2, 10.4, 11.1, 11.2, 11.3, 11.4_

  - [ ]* 12.2 Write unit tests for Aria Agent Core
    - Test message handling with mocked tools and model (greeting flow, query flow, cross-sell flow)
    - Test proactive event handling
    - Test tool selection logic for different query types
    - Test error recovery on tool failures
    - _Requirements: 1.1, 5.1, 11.1, 11.2_

- [ ] 13. Implement Event Handler for EventBridge
  - [ ] 13.1 Implement EventBridge maturity notification handler
    - Create `aria/events/handler.py` with `EventHandler` class
    - Implement `handle_maturity_notification(event: MaturityEvent) -> None` — processes EventBridge scheduled event, loads client session, triggers proactive notification via agent
    - Implement `handle_outflow_alert(event: OutflowEvent) -> None` — processes outflow alert, triggers retention workflow
    - Create `aria/events/lambda_handler.py` with AWS Lambda entry point that parses EventBridge event payloads and delegates to `EventHandler`
    - _Requirements: 4.1, 4.2_

  - [ ]* 13.2 Write unit tests for Event Handler
    - Test maturity notification processing with valid event payload
    - Test outflow alert processing
    - Test Lambda handler event parsing
    - Test error handling for malformed events
    - _Requirements: 4.1, 4.2_

- [ ] 14. Implement API Gateway Integration
  - [ ] 14.1 Implement WebSocket and REST API handlers
    - Create `aria/api/websocket_handler.py` with WebSocket connection management (connect, message, disconnect) for real-time chat
    - Create `aria/api/rest_handler.py` with REST endpoints for admin operations (session management, health check)
    - Create `aria/api/lambda_entry.py` with Lambda handler that routes API Gateway events to appropriate handler
    - Implement authentication validation from API Gateway authorizer context
    - Include rate limiting response (429) with retry-after header
    - _Requirements: 14.1, 14.2, 14.3_

  - [ ]* 14.2 Write unit tests for API handlers
    - Test WebSocket connect/message/disconnect lifecycle
    - Test REST health check and session management endpoints
    - Test authentication failure handling (401 response)
    - Test rate limiting response
    - _Requirements: 14.1, 14.2, 14.3_

- [ ] 15. Checkpoint - Full agent assembled
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 16. Property-based tests
  - [ ]* 16.1 Write property test for client name personalization
    - **Property 1: Client Name Personalization**
    - For any client profile with a non-empty name, all agent responses during that session SHALL contain the client's name at least once
    - Create Hypothesis strategy: `client_profile_strategy()` generating valid ClientProfile instances
    - **Validates: Requirements 1.1, 11.1**

  - [ ]* 16.2 Write property test for profile update round trip
    - **Property 2: Profile Update Serialization Round Trip**
    - For any valid financial profile information, serializing into ProfileUpdate and deserializing back SHALL produce equivalent data
    - Create Hypothesis strategy for generating ProfileUpdate instances
    - **Validates: Requirements 1.2**

  - [ ]* 16.3 Write property test for risk assessment precedes recommendations
    - **Property 3: Risk Assessment Precedes Market Recommendations**
    - For any interaction resulting in a Market_Linked_Product recommendation, risk assessment tool SHALL have been invoked prior
    - Mock agent tool call sequence and verify ordering
    - **Validates: Requirements 1.3**

  - [ ]* 16.4 Write property test for CTG suggestion for family accounts
    - **Property 4: CTG Suggestion for Family Accounts**
    - For any client with non-empty family_members holding active accounts, agent SHALL include CTG enrollment suggestion
    - **Validates: Requirements 1.4**

  - [ ]* 16.5 Write property test for wallet profile persistence
    - **Property 5: Wallet Profile Persistence**
    - For any external asset disclosure, WalletProfile SHALL contain corresponding entry and CRM update SHALL include all disclosed details
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 16.6 Write property test for product recommendations match risk profile
    - **Property 6: Product Recommendations Match Client Profile**
    - For any client with determined risk appetite, recommended products SHALL belong to appropriate risk-level categories
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [ ]* 16.7 Write property test for maturity notification threshold
    - **Property 7: Maturity Notification Threshold**
    - For any maturity event, notification SHALL be triggered if and only if days_until_maturity <= 30
    - Create Hypothesis strategy: `maturity_event_strategy()` with varying days_until_maturity
    - **Validates: Requirements 4.1**

  - [ ]* 16.8 Write property test for outflow detection threshold
    - **Property 8: Outflow Detection Threshold**
    - For any account transaction, retention workflow SHALL trigger if and only if amount exceeds configured threshold
    - Create Hypothesis strategy: `transaction_strategy()` with varying amounts
    - **Validates: Requirements 4.2**

  - [ ]* 16.9 Write property test for unresolvable query escalation
    - **Property 9: Unresolvable Query Escalation**
    - For any query where KB returns confidence_score below threshold and agent cannot resolve, escalation tool SHALL be called
    - **Validates: Requirements 5.4, 13.2**

  - [ ]* 16.10 Write property test for interaction summary completeness
    - **Property 10: Interaction Summary Completeness**
    - For any completed interaction, logged InteractionSummary SHALL have non-empty topics_discussed, segment_flags, and valid timestamp
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 16.11 Write property test for follow-up reminder creation
    - **Property 11: Follow-Up Reminder Creation**
    - For any interaction with non-empty follow_up_actions, a CRM reminder SHALL be created for each action with valid due_date and assigned_to
    - **Validates: Requirements 6.3**

  - [ ]* 16.12 Write property test for sensitive credential detection
    - **Property 12: Sensitive Credential Detection and Rejection**
    - For any input containing credential patterns (PINs, CVVs, OTPs, passwords), system SHALL refuse, warn, and redact
    - Create Hypothesis strategy: `credential_bearing_message_strategy()` embedding credential patterns
    - **Validates: Requirements 7.1, 7.2, 7.3**

  - [ ]* 16.13 Write property test for market risk disclosure
    - **Property 13: Market Risk Disclosure Compliance**
    - For any response mentioning Market_Linked_Product, response SHALL include risk disclosure AND SHALL NOT guarantee returns
    - **Validates: Requirements 8.1, 8.2**

  - [ ]* 16.14 Write property test for KYC gating
    - **Property 14: KYC Gating for New Products**
    - For any new product request, KYC check SHALL occur first; if not current, request SHALL be paused with missing_documents listed
    - **Validates: Requirements 9.1, 9.2**

  - [ ]* 16.15 Write property test for AML threshold flagging
    - **Property 15: AML Threshold Flagging**
    - For any activity breaching AML thresholds, flag_aml_activity SHALL be called producing AMLFlag with FLAGGED status
    - **Validates: Requirements 9.3**

  - [ ]* 16.16 Write property test for escalation routing
    - **Property 16: Escalation for Sensitive/Complex Requests**
    - For any request classified as high-value credit, legal dispute, account freeze, complex fraud, estate planning, or custom treasury, escalation tool SHALL be invoked with matching reason and response SHALL contain timeline
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4**

  - [ ]* 16.17 Write property test for adversarial input handling
    - **Property 17: Adversarial Input Handling**
    - For any detected prompt injection, system SHALL block, log, and return polite refusal without revealing internal details
    - Create Hypothesis strategy: `injection_attempt_strategy()` generating injection patterns
    - **Validates: Requirements 12.2, 12.3, 12.4**

  - [ ]* 16.18 Write property test for rate source date citation
    - **Property 18: Rate Source Date Citation**
    - For any response presenting product rate information from KB, response SHALL include source_date
    - **Validates: Requirements 13.3**

  - [ ]* 16.19 Write property test for segment-based recommendation tailoring
    - **Property 19: Segment-Based Recommendation Tailoring**
    - For two clients with different segments given the same query, recommendations and service language SHALL differ per segment tier
    - **Validates: Requirements 14.2**

  - [ ]* 16.20 Write property test for CRM unavailability graceful degradation
    - **Property 20: CRM Unavailability Graceful Degradation**
    - For any session where CRM returns error, agent SHALL inform client, log incident, and continue without crashing
    - **Validates: Requirements 14.3**

- [ ] 17. Integration tests
  - [ ]* 17.1 Write integration tests for CRM and DynamoDB flows
    - Test CRM read/write with realistic payloads using moto mocks
    - Test DynamoDB session persistence round trips
    - Test interaction logging end-to-end (session → agent → CRM log)
    - _Requirements: 6.1, 6.2, 14.1_

  - [ ]* 17.2 Write integration tests for guardrail pipeline
    - Test full input → guardrails → agent → guardrails → output flow
    - Test prompt injection blocking with realistic adversarial inputs
    - Test credential redaction in persisted logs
    - _Requirements: 7.1, 7.2, 7.3, 12.1, 12.2_

  - [ ]* 17.3 Write integration tests for EventBridge and end-to-end flows
    - Test EventBridge maturity event triggering and Lambda handler
    - Test multi-turn conversation flows (greeting → query → cross-sell → escalation)
    - Test Knowledge Base retrieval with source attribution
    - _Requirements: 4.1, 4.2, 5.1, 13.1_

- [ ] 18. Final checkpoint - All tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using Hypothesis (minimum 100 iterations)
- Unit tests validate specific examples, edge cases, and integration points using pytest
- Integration tests use moto for AWS service mocking
- The Strands Agents SDK `@tool` decorator is used for all tool implementations
- Amazon Bedrock Guardrails handle input/output filtering (no custom guardrail code needed)
- All external service calls use retry with exponential backoff and graceful degradation

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "3.1", "4.1"] },
    { "id": 3, "tasks": ["2.2", "3.2", "4.2", "6.1", "7.1", "8.1"] },
    { "id": 4, "tasks": ["6.2", "7.2", "8.2", "9.1", "10.1"] },
    { "id": 5, "tasks": ["9.2", "10.2", "12.1"] },
    { "id": 6, "tasks": ["12.2", "13.1"] },
    { "id": 7, "tasks": ["13.2", "14.1"] },
    { "id": 8, "tasks": ["14.2", "16.1", "16.2", "16.7", "16.8", "16.12", "16.17"] },
    { "id": 9, "tasks": ["16.3", "16.4", "16.5", "16.6", "16.9", "16.10", "16.11"] },
    { "id": 10, "tasks": ["16.13", "16.14", "16.15", "16.16", "16.18", "16.19", "16.20"] },
    { "id": 11, "tasks": ["17.1", "17.2", "17.3"] }
  ]
}
```
