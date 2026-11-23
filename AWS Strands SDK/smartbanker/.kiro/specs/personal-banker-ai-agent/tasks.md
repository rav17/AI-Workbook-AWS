# Task Breakdown

## T1: Config & Data Models
- [x] T1.1: Create `config/settings.py` with AgentConfig, MemoryConfig, PriorityConfig
- [x] T1.2: Create `config/models.py` with ExecutionResult, Plan, InteractionRecord, MemoryContext Pydantic models

## T2: Tool Registry, Lambda Invoker & Tools
- [x] T2.1: Create `tools/registry.py` with ToolRegistry class and schema validation
- [x] T2.2: Create `tools/financial_tools.py` with @tool decorated functions for all 12 tools (dual execution path: Lambda + local stubs)
- [x] T2.3: Create `tools/lambda_invoker.py` with generic Lambda invocation layer (USE_LAMBDA env var control)
- [x] T2.4: Create `lambdas/*/handler.py` — 12 individual Lambda handlers for all financial tools
- [x] T2.5: Create `deployment/template.yaml` — CloudFormation template deploying all 12 Lambdas (exposed via AgentCore Gateway as MCP targets)

## T3: Memory Layer
- [x] T3.1: Create `memory/dynamodb_manager.py` with DynamoDB short-term memory (store, retrieve, prune, deduplicate)
- [x] T3.2: Create `memory/vector_memory.py` with vector store long-term memory (store_pattern, search_patterns)
- [x] T3.3: Create `memory/degradation.py` with MemoryDegradationControl (filter, deduplicate, exclude outdated)

## T4: Worker Agents
- [x] T4.1: Create `agents/workers/base.py` with WorkerAgent base class
- [x] T4.2: Create `agents/workers/spending_analyzer.py`
- [x] T4.3: Create `agents/workers/savings_advisor.py`
- [x] T4.4: Create `agents/workers/investment_advisor.py`
- [x] T4.5: Create `agents/workers/query_assistant.py`
- [x] T4.6: Create `agents/workers/risk_compliance.py`

## T5: Delegator Agent
- [x] T5.1: Create `agents/delegator.py` with intent routing, tool validation, worker dispatch

## T6: Coordinator Agent
- [x] T6.1: Create `agents/coordinator.py` with self-healing loop, planning, reflection, introspection

## T7: Compliance & Observability
- [x] T7.1: Create `compliance/disclosure_manager.py`
- [x] T7.2: Create `observability/logger.py` with CorrelatedLogger

## T8: Entry Point & Deployment
- [x] T8.1: Create `main.py` with AgentCore-compatible handler
- [x] T8.2: Create `requirements.txt`
- [x] T8.3: Create `deployment/` configs

## T9: Tests
- [x] T9.1: Create `tests/test_models.py` for schema validation properties
- [x] T9.2: Create `tests/test_memory.py` for memory properties
- [x] T9.3: Create `tests/test_self_healing.py` for end-to-end flow
- [x] T9.4: Create `tests/test_compliance.py` for safety properties

---

# Phase 2: Advanced Features (R18–R39)

## T10: Phase 2 Config Extensions & Data Models
- [x] T10.1: Extend `config/settings.py` with ComplianceConfig and ScopeLimitationConfig
  - Add ComplianceConfig with mandatory_checks and non_waivable_rules lists
  - Add ScopeLimitationConfig with out_of_scope_services list
  - _Requirements: R34, R36_

- [x] T10.2: Create Programme Tier data models in `config/models.py`
  - Add ProgrammeTier Pydantic model with tier name, eligibility criteria (min balance, salary credit), and benefit definitions
  - Add FamilyGroup model with primary holder, linked members, max group size
  - Add FeeWaiverMatrix model mapping tiers to fee waivers and preferential pricing
  - Add ServiceRequest, EscalationResult, ProactiveNotification, ValueAssessmentResult Pydantic models
  - Extend ExecutionResult with recommendation_source, non_fiduciary_disclaimer, scope_limitation, facilitation_summary, priority_level, estimated_processing_time, tracking_reference, commission_disclosure fields
  - _Requirements: R18.1, R18.4, R22.1, R23.1, R28, R29, R30, R31.2, R33.4, R35, R36.4, R39_

- [ ]* T10.3: Write unit tests for Phase 2 config and data models
  - Test ProgrammeTier eligibility criteria validation
  - Test FamilyGroup max size constraint
  - Test FeeWaiverMatrix tier lookup
  - Test extended ExecutionResult field validation
  - _Requirements: R18.1, R22.3, R23.1_

## T11: Service Request Handler Agent
- [x] T11.1: Create `agents/workers/service_request_handler.py`
  - Implement ServiceRequestHandlerAgent extending WorkerAgent
  - Implement handle_service_request(request, user_tier) with tier-based priority assignment
  - Implement escalate(request) returning EscalationResult with tracking reference and estimated timeline
  - Register tools: service_request_processor, escalation_tracker, document_guidance_tool
  - _Requirements: R28.1, R28.2, R28.3, R28.5, R28.6, R29.1, R32.1_

- [ ]* T11.2: Write property test for service request routing (P22)
  - **Property 22: Service Request Routing**
  - For any Service_Request with a known request type, verify routing to ServiceRequestHandler or escalation path
  - **Validates: Requirements R28.1**

- [ ]* T11.3: Write property test for escalation tracking (P23)
  - **Property 23: Escalation Tracking and Logging**
  - For any escalated service request, verify non-empty tracking reference, estimated timeline, and log entry
  - **Validates: Requirements R28.2, R28.3**

- [ ]* T11.4: Write property test for service request persistence (P24)
  - **Property 24: Service Request Persistence Round-Trip**
  - Store and retrieve a ServiceRequest, verify field identity preservation
  - **Validates: Requirements R28.4**

## T12: Priority Manager
- [x] T12.1: Create `priority/priority_manager.py`
  - Implement PriorityManager with assign_priority(user_tier), get_estimated_time(priority_level), enrich_result(result, user_tier), validate_priority_ordering(tier_a, tier_b)
  - Use PriorityConfig for tier-to-priority mapping and estimated processing times
  - _Requirements: R29.1, R29.2, R29.4, R29.5_

- [ ]* T12.2: Write property test for tier-based priority assignment (P25)
  - **Property 25: Tier-Based Priority Assignment**
  - For any user tier, verify assigned priority matches configured mapping and appears in logs
  - **Validates: Requirements R29.1, R29.3**

- [ ]* T12.3: Write property test for priority estimated processing time (P26)
  - **Property 26: Priority Task Estimated Processing Time**
  - For any priority-enriched ExecutionResult, verify non-empty estimated_processing_time
  - **Validates: Requirements R29.4**

## T13: Loan Advisor Agent
- [x] T13.1: Create `agents/workers/loan_advisor.py`
  - Implement LoanAdvisorAgent extending WorkerAgent
  - Implement facilitate_loan(task, context) with tier-specific facilitation strategies
  - Register tools: loan_product_catalog, tier_pricing_engine
  - Support personal loans, auto loans, property-backed loans, working capital facilities
  - Attach mandatory loan approval limitation disclaimer to all results
  - _Requirements: R20.1, R20.2, R20.3, R20.5, R20.6, R30.1, R30.2, R30.3, R30.4, R30.5, R35.1, R35.2, R35.3, R35.4_

- [ ]* T13.2: Write property test for loan facilitation tier monotonicity (P27)
  - **Property 27: Loan Facilitation Tier Monotonicity**
  - For any two users with different tiers requesting the same loan, higher tier gets superset of facilitation benefits
  - **Validates: Requirements R30.1, R30.3**

- [ ]* T13.3: Write property test for loan facilitation disclaimer (P28)
  - **Property 28: Loan Facilitation Disclaimer**
  - For any loan facilitation ExecutionResult, verify disclaimer and issues field contain approval limitation language
  - **Validates: Requirements R30.4, R35.1, R35.2, R35.3, R35.4**

- [ ]* T13.4: Write property test for loan facilitation result schema (P29)
  - **Property 29: Loan Facilitation Result Schema**
  - For any loan facilitation result, verify facilitation_summary is present and non-empty, all required fields valid
  - **Validates: Requirements R30.2, R30.5**

## T14: Checkpoint - Phase 2 Core Agents
- [x] T14: Ensure all tests pass, ask the user if questions arise.

## T15: Disclosure Manager Extensions
- [x] T15.1: Extend `compliance/disclosure_manager.py` with Phase 2 disclosures
  - Implement attach_non_fiduciary(result) for non-fiduciary disclaimer on investment/product advice
  - Implement attach_product_catalog_disclosure(result) for Product_Catalog sourcing disclosure
  - Implement attach_loan_disclaimer(result) for loan approval limitation disclaimer
  - Implement attach_scope_limitation(result, request_context) for out-of-scope request notices
  - Implement attach_commission_disclosure(result) for commission/incentive transparency
  - Update apply_disclosures(result, worker_domain) to route to all applicable disclosure methods
  - _Requirements: R31.1, R31.3, R33.1, R33.2, R33.3, R33.4, R35.2, R36.2, R36.3, R36.4_

- [ ]* T15.2: Write property test for product recommendation disclosures (P30)
  - **Property 30: Product Recommendation Disclosures**
  - For any product recommendation ExecutionResult, verify recommendation_source="product_catalog", catalog disclosure, non-independent statement, and commission_disclosure if applicable
  - **Validates: Requirements R31.1, R31.2, R31.3, R33.2**

- [ ]* T15.3: Write property test for investment non-fiduciary disclaimer (P31)
  - **Property 31: Investment Non-Fiduciary Disclaimer and Verification Advice**
  - For any investment/product advice ExecutionResult, verify non_fiduciary_disclaimer is present and non-empty, plus verification advice
  - **Validates: Requirements R31.4, R31.5, R33.1, R33.3, R33.4**

- [ ]* T15.4: Write property test for compliance enforcement (P34)
  - **Property 34: Compliance Enforcement (Cannot Bypass)**
  - For any request requiring compliance bypass, verify status="failure" with compliance constraint in issues
  - **Validates: Requirements R34.1, R34.2, R34.3, R34.4**

- [ ]* T15.5: Write property test for scope limitation (P35)
  - **Property 35: Portfolio Management Scope Limitation**
  - For any out-of-scope request, verify scope_limitation field is present and non-empty
  - **Validates: Requirements R36.1, R36.2, R36.4**

## T16: Value Assessor Agent
- [x] T16.1: Create `agents/workers/value_assessor.py`
  - Implement ValueAssessorAgent extending WorkerAgent
  - Implement assess_value(user_id, tier, activity) returning value summary with utilized/unused benefits, value_score, tier_recommendation
  - Register tools: activity_analyzer, tier_benefit_mapper
  - Honestly recommend downgrade when basic self-service is sufficient
  - _Requirements: R39.1, R39.2, R39.3, R39.4, R39.5_

- [ ]* T16.2: Write property test for value assessment benefit partitioning (P39)
  - **Property 39: Value Assessment Benefit Partitioning**
  - For any user with tier and activity, verify utilized_benefits ∪ unused_benefits = all tier benefits and intersection = ∅
  - **Validates: Requirements R39.1, R39.2, R39.5**

- [ ]* T16.3: Write property test for value assessment tier recommendation (P40)
  - **Property 40: Value Assessment Tier Recommendation**
  - For any user with activity/tier mismatch, verify tier_recommendation with non-empty rationale; low-activity premium users get honest downgrade suggestion
  - **Validates: Requirements R39.3, R39.4**

## T17: Proactive Engagement Engine
- [x] T17.1: Create `engagement/proactive_engine.py`
  - Implement ProactiveEngagementEngine with scan_for_opportunities(user_id, tier), generate_notification(opportunity, user_id), detect_patterns(interactions, patterns)
  - Detect fee waiver expiry, investment maturity, tier upgrade eligibility, promotional offers, tier downgrade risk, savings opportunities
  - _Requirements: R37.1, R37.2, R37.3, R37.4_

- [ ]* T17.2: Write property test for proactive engagement generation (P36)
  - **Property 36: Proactive Engagement Generation**
  - For any user with sufficient history containing detectable opportunities, verify at least one ProactiveNotification is generated
  - **Validates: Requirements R37.1, R37.4**

- [ ]* T17.3: Write property test for proactive engagement tier independence (P37)
  - **Property 37: Proactive Engagement Tier Independence**
  - For any two users with identical histories but different tiers, verify equal notification count
  - **Validates: Requirements R37.3**

## T18: Checkpoint - Phase 2 Engines & Disclosures
- [x] T18: Ensure all tests pass, ask the user if questions arise.

## T19: Programme Tier, Family Group & Fee Waiver Logic
- [x] T19.1: Implement Programme Tier management logic
  - Add tier retrieval and eligibility evaluation to Coordinator flow
  - Filter available products and benefits based on user tier
  - Detect tier upgrade/downgrade opportunities
  - Store tier definitions in configurable data store
  - _Requirements: R18.1, R18.2, R18.3, R18.4, R18.5_

- [x] T19.2: Implement Family Group account benefits
  - Implement FamilyGroup creation, membership tracking, and max size validation
  - Extend tier benefit application to linked family members
  - Propagate primary holder tier changes to all group members
  - Log membership change events
  - _Requirements: R22.1, R22.2, R22.3, R22.4, R22.5, R22.6_

- [x] T19.3: Implement Fee Waiver Matrix and preferential pricing
  - Implement FeeWaiverMatrix lookup by tier for service charges, annual fees, transaction fees, forex rates
  - Proactively surface applicable waivers when interaction context is relevant
  - Include specific waiver/rate in explainability summary
  - Support matrix updates without code changes
  - _Requirements: R23.1, R23.2, R23.3, R23.4, R23.5_

## T20: Programme Eligibility Tracking
- [x] T20.1: Implement programme eligibility monitoring
  - Monitor user account metrics (balance, salary credits, transaction volume) against tier criteria
  - Generate proactive alerts for tier downgrade risk
  - Recommend corrective actions to maintain tier status
  - Notify users of upgrade opportunities
  - Configurable evaluation frequency (default: monthly)
  - _Requirements: R27.1, R27.2, R27.3, R27.4, R27.5_

## T21: Multi-Channel Support & Relationship Manager
- [x] T21.1: Implement multi-channel support coordination
  - Add channel_id to interaction records in STM
  - Maintain context continuity across web, mobile, messaging channels
  - Apply tier-aware priority to support request routing
  - Ensure recommendation consistency across channels for same user session
  - _Requirements: R26.1, R26.2, R26.3, R26.4, R26.5_

- [x] T21.2: Implement relationship manager assignment and continuity
  - Store dedicated relationship manager assignment in user profile
  - Coordinator acts as virtual relationship manager (single point of contact)
  - Route requests based on tier with priority handling for higher tiers
  - Maintain history of relationship manager interactions for service continuity
  - _Requirements: R19.1, R19.2, R19.3, R19.4, R19.5_

## T22: Complex Banking Operations & Card/Lifestyle Benefits
- [x] T22.1: Implement complex banking assistance in Coordinator and workers
  - Support large-value transaction coordination, forex transfer assistance, multi-product investment coordination, documentation guidance
  - Decompose complex operations into multi-worker sub-tasks
  - Apply enhanced compliance checks via Risk_Compliance_Agent for complex operations
  - Identify required documents and provide preparation guidance
  - _Requirements: R32.1, R32.2, R32.3, R32.4_

- [ ]* T22.2: Write property test for complex operation decomposition (P32)
  - **Property 32: Complex Operation Multi-Agent Decomposition**
  - For any complex operation, verify Plan has ≥2 sub-tasks on different workers and includes Risk_Compliance_Agent task
  - **Validates: Requirements R32.2, R32.3**

- [ ]* T22.3: Write property test for complex operation documentation (P33)
  - **Property 33: Complex Operation Documentation Guidance**
  - For any complex operation with regulatory doc requirements, verify non-empty document list and guidance in result
  - **Validates: Requirements R32.4**

- [x] T22.4: Implement premium card and spending benefits
  - Recommend tier-appropriate debit/credit card products
  - Include enhanced transaction limits per tier
  - Identify reward point optimization opportunities in Spending_Analyzer
  - Detect card upgrade opportunities
  - _Requirements: R24.1, R24.2, R24.3, R24.4, R24.5_

- [x] T22.5: Implement lifestyle and travel perks awareness
  - Maintain configurable tier-to-lifestyle benefits mapping (lounge access, dining, cashback, reward acceleration)
  - Proactively surface perks when interaction context is relevant to travel/lifestyle
  - Support configuration updates without code changes
  - _Requirements: R25.1, R25.2, R25.3, R25.4_

## T23: Investment Advisor Extensions
- [x] T23.1: Extend `agents/workers/investment_advisor.py` for wealth management
  - Add support for demat account management, trading support, forex advisory, wealth management recommendations
  - Tailor product recommendations to tier-eligible product set
  - Include sophisticated products (structured products, portfolio management services, alternative investments) for higher tiers
  - Include tier-specific preferential forex rate information
  - _Requirements: R21.1, R21.2, R21.3, R21.4, R21.5_

## T24: Service Continuity & Observability Extensions
- [x] T24.1: Implement service continuity guarantee
  - Ensure full context continuity across sessions via STM+LTM
  - Persist all interaction history, preferences, and learnings across sessions
  - Retrieve and apply historical context at start of every new interaction
  - Handle user references to prior interactions without re-explanation
  - _Requirements: R38.1, R38.2, R38.3, R38.4_

- [ ]* T24.2: Write property test for service continuity round-trip (P38)
  - **Property 38: Service Continuity Round-Trip**
  - For any persisted interaction, verify retrieval in a subsequent session returns original data
  - **Validates: Requirements R38.2**

- [x] T24.3: Extend `observability/logger.py` with Phase 2 log events
  - Add log_escalation(user_id, service_request_id, tracking_ref, estimated_timeline)
  - Add log_priority_assignment(user_id, task_id, priority_level, tier)
  - Add log_compliance_block(user_id, request_context, compliance_rule)
  - Add log_scope_limitation(user_id, request_context, scope_boundary)
  - Add log_proactive_engagement(user_id, opportunity_type, notification_id)
  - _Requirements: R14, R28.3, R29.3, R34.2, R36.2, R37.4_

## T25: Phase 2 Wiring & Integration
- [x] T25.1: Wire Phase 2 components into Coordinator and Delegator
  - Register ServiceRequestHandlerAgent, LoanAdvisorAgent, ValueAssessorAgent with Delegator
  - Initialize PriorityManager in Coordinator
  - Initialize ProactiveEngagementEngine in Coordinator with memory reference
  - Add handle_service_request and escalate methods to Coordinator
  - Add check_proactive_opportunities to Coordinator
  - Update Delegator dispatch to accept priority_level parameter
  - _Requirements: R19.2, R20.4, R28.1, R29.1, R37.1, R39_

- [x] T25.2: Register Phase 2 tools in Tool Registry
  - Register service_request_processor, escalation_tracker, document_guidance_tool for service_request domain
  - Register loan_product_catalog, tier_pricing_engine for loan_advice domain
  - Register activity_analyzer, tier_benefit_mapper for value_assessment domain
  - Register compliance_rule_checker for risk_compliance domain
  - _Requirements: R8.1_

- [x] T25.3: Update `main.py` to initialize Phase 2 agents and engines
  - Register new workers in create_app: loan_advice, service_request, value_assessment
  - Initialize ProactiveEngagementEngine with memory
  - Load Phase 2 configs (ComplianceConfig, ScopeLimitationConfig, PriorityConfig)
  - _Requirements: R16.4_

## T26: Final Checkpoint - Phase 2 Complete
- [x] T26: Ensure all tests pass, ask the user if questions arise.

## T27: Streamlit UI (R40)
- [x] T27.1: Create `ui/app.py` with Streamlit chat interface
  - Chat input with conversation history
  - Structured recommendation cards (status, confidence, risk, disclaimers, explainability)
  - Color-coded status indicators (success=green, partial=yellow, failure=red)
  - System metadata display (correlation ID, retries, warnings)
  - _Requirements: R40.1, R40.2, R40.3, R40.4, R40.7, R40.8_

- [x] T27.2: Add sidebar configuration and execution mode toggle
  - AgentCore Gateway endpoint URL input
  - User ID and AWS region configuration
  - Local/Remote mode toggle
  - _Requirements: R40.5, R40.6_

- [x] T27.3: Add proactive notifications panel and service request form
  - Proactive notifications display panel
  - Service request submission form with request type and description
  - _Requirements: R40.9, R40.10_

- [x] T27.4: Add `streamlit` to `requirements.txt` and create `ui/README.md` with usage instructions

## T28: KYC/AML Agent — Data Models & Tools (R41-R50)
- [ ] T28.1: Add KYC/AML data models to `config/models.py`
  - KYCExtractionResult (extracted fields with confidence scores, source attribution, format validation)
  - VerificationResult, VerificationSummary (multi-source verification with sanctions/PEP flags)
  - ConflictResolutionReport (reasoning chain for mismatches, fraud indicators)
  - RiskAssessment (composite score, risk band, contributing factors, historical comparison, context factors)
  - EscalationDecision (decision, reasoning chain, explainability, monitoring flag, sanctions match flag)
  - KYCAuditRecord (immutable audit record with data lineage, PII masking, retention policy)
  - _Requirements: R41.3, R42.3, R42.4, R43.4, R44.4, R45.2, R47.1, R47.3_

- [ ] T28.2: Create KYC/AML tool stubs in `tools/financial_tools.py`
  - document_extractor: OCR + extraction from identity documents (Textract + Nova)
  - identity_verifier: Cross-verify against government databases, CRM, credit bureaus
  - sanctions_checker: Check against OFAC, UN, EU sanctions lists (blocks on unavailability)
  - pep_screener: Check against PEP databases
  - risk_scorer: Compute composite risk score (deterministic weighted model)
  - _Requirements: R41.1, R42.1, R42.6, R44.1_

- [ ] T28.3: Create Lambda handlers for KYC/AML tools in `lambdas/`
  - lambdas/document_extractor/handler.py
  - lambdas/identity_verifier/handler.py
  - lambdas/sanctions_checker/handler.py
  - lambdas/pep_screener/handler.py
  - lambdas/risk_scorer/handler.py
  - _Requirements: R41.1, R42.1, R42.6_

## T29: KYC/AML Agent — Core Implementation (R41-R50)
- [ ] T29.1: Create `agents/workers/kyc_aml_agent.py`
  - Implement KYCAgent extending WorkerAgent with domain "kyc_aml"
  - Implement extract_document() — intelligent document understanding with integrity validation, format rule cross-validation, hallucination detection (R41)
  - Implement verify_identity() — multi-source parallel verification with exponential backoff, sanctions blocking, source unavailability handling (R42)
  - Implement resolve_conflicts() — intelligent reasoning about mismatches, 2+ source consultation, fraud pattern detection, date format reasoning (R43)
  - Implement assess_risk() — context-aware composite risk scoring with configurable weights, historical comparison, FATF jurisdiction awareness (R44)
  - Implement decide_escalation() — smart escalation with explainability, sanctions hard rule, fraud indicator handling, monitoring flags (R45)
  - Implement run_full_kyc() — end-to-end orchestration with agent reasoning
  - _Requirements: R41, R42, R43, R44, R45_

- [ ] T29.2: Wire KYC Agent into Coordinator and Delegator
  - Register KYCAgent with Delegator as "kyc_aml" domain
  - Register KYC tools in Tool Registry
  - Add KYC domain keywords to Delegator routing
  - _Requirements: R45.6_

- [ ] T29.3: Update Streamlit UI with KYC/AML document upload
  - Add document upload widget in sidebar
  - Display KYC assessment results (extraction, verification, risk score, decision)
  - Show reasoning chain and explainability for escalation decisions
  - Mask Aadhaar numbers in UI display (last 4 digits only)
  - _Requirements: R41.1, R45.3, R47.6_

## T29A: KYC/AML Audit, Compliance & Exception Handling (R46-R50)
- [ ] T29A.1: Implement KYC audit trail and compliance logging
  - Produce immutable KYC_Audit_Record for every assessment with all required fields
  - Implement data lineage tracking (source attribution for every data point)
  - Implement PII masking (Aadhaar last 4 digits in logs and UI)
  - Implement SAR draft generation for escalated/rejected cases
  - Record LLM extraction confidence and verification confidence separately
  - Log all retry attempts with attempt number, error, and outcome
  - _Requirements: R47.1, R47.2, R47.3, R47.4, R47.5, R47.6, R47.7, R47.8, R47.9_

- [ ] T29A.2: Implement KYC exception and failure handling
  - Handle blurry/unreadable documents (confidence < 0.5, re-upload request)
  - Handle partial OCR extraction (proceed with available, flag missing)
  - Handle sanctions API timeout (block, retry 3x, pending_sanctions state)
  - Handle duplicate customer detection (flag both, escalate)
  - Handle tampered document detection (immediate reject, fraud escalation)
  - Handle LLM hallucination detection (cross-validate OCR, re-extract)
  - Handle unsupported language detection
  - Handle government API errors (retry with backoff, source_unavailable)
  - _Requirements: R48.1, R48.2, R48.3, R48.4, R48.5, R48.6, R48.7, R48.8_

- [ ] T29A.3: Implement human-in-the-loop review routing
  - Route low-confidence extractions to human reviewer
  - Present full assessment package for manual_review decisions
  - Route escalate_to_compliance cases to senior compliance officer
  - Require human confirmation for partial sanctions matches
  - Implement 5% random sampling of auto-approved cases for QA
  - _Requirements: R49.1, R49.2, R49.3, R49.4, R49.5, R49.6_

- [ ] T29A.4: Implement periodic re-KYC assessment and monitoring
  - Support configurable re-KYC intervals (annual for high-risk, 3-year for low-risk)
  - Trigger immediate re-assessment on significant events (large transactions, address change, sanctions update)
  - Apply Enhanced Due Diligence for FATF high-risk jurisdictions
  - Compare risk scores against historical profile, alert on significant changes (delta > 0.2)
  - _Requirements: R50.1, R50.2, R50.3, R50.4, R50.5, R50.6_

- [ ] T29A.5: Extend observability for KYC/AML
  - Add log_kyc_assessment(customer_id, decision, risk_score, correlation_id)
  - Add log_sanctions_check(customer_id, match_status, source)
  - Add log_conflict_resolution(customer_id, conflict_type, determination)
  - Add log_audit_record_created(audit_id, customer_id)
  - Add per-step latency metrics (extract, verify, reason, assess, decide)
  - Add escalation rate tracking (% per decision type)
  - _Requirements: R46, R47.9_

## T30: KYC/AML Agent — Tests
- [ ]* T30.1: Write property test for KYC extraction confidence flagging (P41)
  - **Property 41: KYC Extraction Confidence Threshold Flagging**
  - For any KYCExtractionResult, fields below threshold appear in low_confidence_fields, fields above do not
  - _Requirements: R41.4, R49.1_

- [ ]* T30.2: Write property test for sanctions match never auto-approved (P42)
  - **Property 42: KYC Sanctions Match Never Auto-Approved**
  - For any EscalationDecision with sanctions_match=true, decision is never auto_approve
  - _Requirements: R45.7, R46.6_

- [ ]* T30.3: Write property test for conflict resolution source consultation (P43)
  - **Property 43: KYC Conflict Resolution Source Consultation**
  - For any conflict in ConflictResolutionReport, sources_consulted has 2+ entries
  - _Requirements: R43.3_

- [ ]* T30.4: Write property test for risk score determinism (P44)
  - **Property 44: KYC Risk Score Determinism**
  - For identical inputs, composite_score is identical across invocations
  - _Requirements: R44.7_

- [ ]* T30.5: Write property test for risk band classification (P45)
  - **Property 45: KYC Risk Band Classification Correctness**
  - For any RiskAssessment, risk_band matches composite_score ranges
  - _Requirements: R44.3_

- [ ]* T30.6: Write property test for audit record completeness (P46)
  - **Property 46: KYC Audit Record Completeness**
  - For any completed assessment, KYC_Audit_Record has all required fields non-empty
  - _Requirements: R47.1, R47.3_

- [ ]* T30.7: Write property test for escalation explainability (P47)
  - **Property 47: KYC Escalation Decision Explainability**
  - For any EscalationDecision, reasoning_chain non-empty, evidence non-empty, explainability_summary non-empty
  - _Requirements: R45.2, R45.3_

- [ ]* T30.8: Write property test for PII masking (P48)
  - **Property 48: KYC PII Masking in Logs**
  - For any audit record or log entry, Aadhaar numbers masked to last 4 digits
  - _Requirements: R47.6_

- [ ]* T30.9: Write unit tests for KYC document extraction edge cases
  - Test extraction from PAN, Passport, DL, Aadhaar document types
  - Test auto-detection of document type
  - Test blurry document handling (all fields < 0.5 confidence)
  - Test expired document flagging
  - Test tampered document immediate rejection
  - Test LLM hallucination detection via format cross-validation
  - Test unsupported language detection
  - _Requirements: R41.2, R41.4, R41.5, R41.6, R41.7, R41.8, R48.1, R48.5, R48.7_

- [ ]* T30.10: Write unit tests for multi-source verification
  - Test parallel verification orchestration
  - Test sanctions list matching (exact and partial)
  - Test source unavailability handling with exponential backoff
  - Test all-sources-down pending state
  - Test duplicate customer detection
  - _Requirements: R42.2, R42.5, R42.6, R42.7, R48.4_

- [ ]* T30.11: Write unit tests for conflict resolution reasoning
  - Test minor discrepancy auto-resolution (name transliteration, address format, date format)
  - Test genuine risk escalation (DOB mismatch, document number mismatch)
  - Test agent reasoning (checking 2+ additional sources before deciding)
  - Test fraud pattern detection (document reuse, synthetic identity)
  - _Requirements: R43.1, R43.3, R43.5, R43.7_

- [ ]* T30.12: Write unit tests for risk scoring and escalation
  - Test composite risk score calculation with configurable weights
  - Test risk band classification boundaries
  - Test escalation decisions (auto_approve, manual_review, escalate, reject)
  - Test sanctions match always blocks auto-approve
  - Test medium-risk auto-approve with monitoring flag
  - Test new customer neutral history handling
  - Test FATF high-risk jurisdiction enhanced due diligence
  - _Requirements: R44.1, R44.3, R44.8, R45.1, R45.7, R45.9, R50.3_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (P22–P40)
- Unit tests validate specific examples and edge cases
- Phase 2 builds on Phase 1 foundation — all Phase 1 tasks (T1–T9) should be complete before starting Phase 2
