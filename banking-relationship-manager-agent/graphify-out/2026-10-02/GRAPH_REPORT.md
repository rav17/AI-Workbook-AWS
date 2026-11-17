# Graph Report - banking-relationship-manager-agent  (2026-10-02)

## Corpus Check
- 207 files · ~126,668 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 2, .kiro 1, .code-workspace 1)

## Summary
- 1813 nodes · 2865 edges · 137 communities (115 shown, 22 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 155 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b3ba468c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_api_and_events.py
- test_workflow_risk.py
- aria/agentcore_entrypoint.py
- Implementation Plan: Production Readiness Remediation
- FrameworkRunner
- Requirements
- Research: Aria AI Relationship Manager
- FakeSessionTable
- GuardrailProcessor
- Tasks: [FEATURE NAME]
- .claude/skills/speckit-analyze/SKILL.md
- .github/skills/speckit-analyze/SKILL.md
- Correctness Properties
- User Scenarios & Testing
- typing
- Execution Steps
- Execution Steps
- common.ps1
- Feature Specification: [FEATURE NAME]
- Implementation Plan: Account Statement Explainer Subagent
- WorkflowValidator
- Aria AI Relationship Manager
- Core Principles
- .claude/skills/speckit-plan/SKILL.md
- .claude/skills/speckit-specify/SKILL.md
- .claude/skills/speckit-tasks/SKILL.md
- .github/skills/speckit-plan/SKILL.md
- .github/skills/speckit-specify/SKILL.md
- .github/skills/speckit-tasks/SKILL.md
- Core Principles
- Implementation Plan: [FEATURE]
- WorkflowDependencyGraph
- .claude/skills/speckit-checklist/SKILL.md
- .github/skills/speckit-checklist/SKILL.md
- Quickstart: Aria AI Relationship Manager
- .claude/skills/speckit-clarify/SKILL.md
- .claude/skills/speckit-implement/SKILL.md
- .github/skills/speckit-clarify/SKILL.md
- .github/skills/speckit-implement/SKILL.md
- [PROJECT NAME] Development Guidelines
- .claude/skills/speckit-constitution/SKILL.md
- build_artifacts.py
- .github/skills/speckit-constitution/SKILL.md
- create-new-feature.ps1
- Claude Code Project Instructions
- .claude/skills/speckit-taskstoissues/SKILL.md
- Infrastructure
- GitHub Copilot Project Instructions
- .github/skills/speckit-taskstoissues/SKILL.md
- [CHECKLIST TYPE] Checklist: [FEATURE NAME]
- framework/__init__.py
- aria/__init__.py
- IdempotencyStore
- aria-ai-relationship-manager
- AgentCoreMemoryDataPlaneClient
- Implementation Plan: Dispute Resolution Subagent
- Specification Quality Checklist: Aria AI Relationship Manager
- Data Model: Aria AI Relationship Manager
- Tasks: Aria AI Relationship Manager
- test_foundation.py
- test_agentcore_adapters.py
- Observability
- test_context_builder_accepts_remote_adapter_records_in_normalized_shape
- knowledge_tool.py
- Decisions
- test_strands_runtime.py
- Tasks
- Data Models
- agentcore.py
- AgentCoreGatewayAdapter
- Feature Specification: Memory Context Contract Normalization
- Decisions
- Tasks: Production Readiness Remediation
- test_mmdsv2_custom_resource.py
- invoke_gateway_tool
- Data Model: Production Readiness Remediation
- Quickstart: Production Readiness Validation
- Implementation Plan: KYC/AML Verification Subagent
- Agent Framework
- aria/agent.py
- AgentCoreRuntimeAdapter
- AriaAgent
- ComplianceVerifier
- Implementation Plan: Virtual Account Receivables Exception Resolution Subagent
- test_service_and_compliance.py
- Tasks: KYC/AML Verification Subagent
- Data Model: Receivables Exception Resolution
- Data Model: KYC/AML Verification
- AgentCoreMemoryAdapter
- Tasks: Account Statement Explainer Subagent
- Tasks: Virtual Account Receivables Exception Resolution Subagent
- Tasks: Dispute Resolution Subagent
- Decisions
- Decisions
- Data Model: Account Statement Explainer
- test_persistence_and_observability.py
- Contract: Receivables Investigation and Analyst Approval
- Contract: Statement Explainer Handoff and Activity Stream
- Quickstart: Account Statement Explainer Prototype
- Quickstart: Receivables Exception Resolution MVP
- Contract: Dispute Investigation and Human Review
- Quickstart: Dispute Resolution MVP
- Implementation Plan: Aria AI Relationship Manager
- MemoryEntry
- Decisions
- Data Model: Dispute Resolution
- .process_input
- SessionManager
- Error Handling
- KYCStatusProvider
- Quickstart: KYC/AML Verification Subagent
- Design Document: Aria — AI Relationship Manager Agent
- Implementation Plan: Memory Context Contract Normalization
- 2. Tools
- Tasks: Memory Context Contract Normalization
- processor.py
- Components and Interfaces
- Deployment
- Quickstart: Memory Context Contract Normalization
- FollowUpAction
- Invocation Contracts
- test_idempotency_store_reclaims_expired_in_progress_claim
- test_idempotency_store_persists_claims_across_instances_and_releases_for_retry

## God Nodes (most connected - your core abstractions)
1. `AriaAgent` - 48 edges
2. `SessionManager` - 34 edges
3. `ComplianceVerifier` - 32 edges
4. `GuardrailProcessor` - 31 edges
5. `Observability` - 26 edges
6. `IdempotencyStore` - 24 edges
7. `Tasks: Aria AI Relationship Manager` - 24 edges
8. `MemoryEntry` - 23 edges
9. `AgentCoreRuntimeAdapter` - 22 edges
10. `Tasks` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Deployed API Runtime routing` --references--> `handler()`  [INFERRED]
  specs/002-production-readiness/research.md → aria/api/rest_handler.py
- `Current Aria Integration Points` --references--> `RuntimeSessionCoordinator`  [INFERRED]
  specs/003-account-statement-explainer/research.md → aria/api/runtime_session.py
- `Decision: A configured remote backend must own deletion` --references--> `MemoryClient`  [INFERRED]
  specs/007-memory-context-contract/research.md → aria/framework/contracts.py
- `Constitution Check` --references--> `MemoryEntry`  [INFERRED]
  specs/007-memory-context-contract/plan.md → aria/framework/memory.py
- `Summary` --references--> `MemoryEntry`  [INFERRED]
  specs/007-memory-context-contract/plan.md → aria/framework/memory.py

## Import Cycles
- None detected.

## Communities (137 total, 22 thin omitted)

### Community 0 - "test_api_and_events.py"
Cohesion: 0.06
Nodes (50): handler(), invoke_agent(), make_response(), parse_body(), Any, handler(), _idempotency_key(), _is_authenticated() (+42 more)

### Community 1 - "test_workflow_risk.py"
Cohesion: 0.19
Nodes (14): assess_risk_appetite(), get_risk_questionnaire(), Any, PatchOperation, Any, StatePatch, WorkflowState, Design Summary (+6 more)

### Community 2 - "aria/agentcore_entrypoint.py"
Cohesion: 0.08
Nodes (22): _build_strands_agent(), invoke(), main(), _ManagedStrandsInvocation, Any, resolve_runtime_identity(), _response_text(), run_runtime_invocation() (+14 more)

### Community 3 - "Implementation Plan: Production Readiness Remediation"
Cohesion: 0.07
Nodes (26): Content Quality, Feature Readiness, Notes, Requirement Completeness, Specification Quality Checklist: Production Readiness Remediation, Constitution Check, Design, Implementation Plan: Production Readiness Remediation (+18 more)

### Community 4 - "FrameworkRunner"
Cohesion: 0.13
Nodes (17): FrameworkConfig, load_framework_config(), Any, ParsedTurn, GatewayClient, FrameworkRunner, Any, asyncio (+9 more)

### Community 5 - "Requirements"
Cohesion: 0.06
Nodes (32): Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria (+24 more)

### Community 6 - "Research: Aria AI Relationship Manager"
Cohesion: 0.06
Nodes (32): AgentCore Gateway, AgentCore Memory, AgentCore Runtime, Amazon Bedrock and Guardrails, AWS CDK v2 Decisions, Decision: Centralize cross-agent lifecycle behavior, not domain behavior, Decision: Do not mandate background threads or synchronous invocation, Decision: Enforce boundaries through the supported API (+24 more)

### Community 7 - "FakeSessionTable"
Cohesion: 0.33
Nodes (3): FakeConditionalFailure, FakeSessionTable, Exception

### Community 9 - "GuardrailProcessor"
Cohesion: 0.23
Nodes (11): GuardrailProcessor, Protect user input and output from sensitive credential leakage., escalate_request(), Any, test_escalation_emits_structured_operation(), test_escalation_tool_routes_to_correct_team(), test_guardrail_blocks_sensitive_credentials_and_injection(), test_guardrail_processor_blocks_prompt_injection_and_returns_structured_result() (+3 more)

### Community 10 - "Tasks: [FEATURE NAME]"
Cohesion: 0.07
Nodes (26): Dependencies & Execution Order, Format: `[ID] [P?] [Story] Description`, Implementation for User Story 1, Implementation for User Story 2, Implementation for User Story 3, Implementation Strategy, Incremental Delivery, MVP First (User Story 1 Only) (+18 more)

### Community 11 - ".claude/skills/speckit-analyze/SKILL.md"
Cohesion: 0.08
Nodes (25): 1. Initialize Analysis Context, 2. Load Artifacts (Progressive Disclosure), 3. Build Semantic Models, 4. Detection Passes (Token-Efficient Analysis), 5. Severity Assignment, 6. Produce Compact Analysis Report, 7. Provide Next Actions, 8. Offer Remediation (+17 more)

### Community 12 - ".github/skills/speckit-analyze/SKILL.md"
Cohesion: 0.08
Nodes (25): 1. Initialize Analysis Context, 2. Load Artifacts (Progressive Disclosure), 3. Build Semantic Models, 4. Detection Passes (Token-Efficient Analysis), 5. Severity Assignment, 6. Produce Compact Analysis Report, 7. Provide Next Actions, 8. Offer Remediation (+17 more)

### Community 13 - "Correctness Properties"
Cohesion: 0.11
Nodes (19): Correctness Properties, Property 10: Interaction Summary Completeness, Property 11: Follow-Up Reminder Creation, Property 12: Sensitive Credential Detection and Rejection, Property 13: Market Risk Disclosure Compliance, Property 14: KYC Gating for New Products, Property 16: Escalation for Sensitive/Complex Requests, Property 17: Adversarial Input Handling (+11 more)

### Community 14 - "User Scenarios & Testing"
Cohesion: 0.09
Nodes (22): Assumptions, Edge Cases, Feature Specification: Aria AI Relationship Manager, Functional Requirements, Key Entities, Requirements, Success Criteria, User Scenarios & Testing (+14 more)

### Community 15 - "typing"
Cohesion: 0.08
Nodes (50): Alarm, App, main(), Any, aws_cdk, build_app(), _add_alarm(), add_api_alarms() (+42 more)

### Community 16 - "Execution Steps"
Cohesion: 0.12
Nodes (15): 1. Initialize Convergence Context, 2. Load Artifacts (Progressive Disclosure), 3. Build the Intent Inventory, 4. Assess the Codebase and Classify Findings, 5. Assign Severity, 6. Present the In-Session Findings Summary, 7. Append Convergence Tasks (or report converged), 8. Provide Next Actions (Handoff) (+7 more)

### Community 17 - "Execution Steps"
Cohesion: 0.12
Nodes (15): 1. Initialize Convergence Context, 2. Load Artifacts (Progressive Disclosure), 3. Build the Intent Inventory, 4. Assess the Codebase and Classify Findings, 5. Assign Severity, 6. Present the In-Session Findings Summary, 7. Append Convergence Tasks (or report converged), 8. Provide Next Actions (Handoff) (+7 more)

### Community 18 - "common.ps1"
Cohesion: 0.23
Nodes (13): Find-SpecifyRoot(), Format-SpecKitCommand(), Get-CurrentBranch(), Get-FeaturePathsEnv(), Get-InvokeSeparator(), Get-NormalizedPriority(), Get-Python3Command(), Get-RepoRoot() (+5 more)

### Community 19 - "Feature Specification: [FEATURE NAME]"
Cohesion: 0.15
Nodes (12): Assumptions, Edge Cases, Feature Specification: [FEATURE NAME], Functional Requirements, Key Entities *(include if feature involves data)*, Measurable Outcomes, Requirements *(mandatory)*, Success Criteria *(mandatory)* (+4 more)

### Community 20 - "Implementation Plan: Account Statement Explainer Subagent"
Cohesion: 0.06
Nodes (29): Content Quality, Notes, Project Fit and Safety, Requirement Completeness, Specification Quality Checklist: Account Statement Explainer Subagent, Complexity Tracking, Constitution Check, Design Decisions (+21 more)

### Community 21 - "WorkflowValidator"
Cohesion: 0.24
Nodes (8): WorkflowResult, Any, WorkflowValidator, test_validator_rejects_locked_field_updates(), test_workflow_result_records_patch_outcome(), test_validator_allows_valid_profile_update(), test_validator_blocks_invalid_payload(), test_validator_blocks_unauthorized_confirmation_and_compliance_failures()

### Community 22 - "Aria AI Relationship Manager"
Cohesion: 0.50
Nodes (3): Aria AI Relationship Manager, Development setup, Project layout

### Community 23 - "Core Principles"
Cohesion: 0.17
Nodes (11): Aria AI Relationship Manager Constitution, Core Principles, Development and Verification Gates, Governance, I. Structured State Is Authoritative, II. Deterministic Safety and Authorization, III. Patch, Validate, and Invalidate, IV. Bounded Context and Tool Use (+3 more)

### Community 24 - ".claude/skills/speckit-plan/SKILL.md"
Cohesion: 0.18
Nodes (10): Completion Report, Done When, Key rules, Mandatory Post-Execution Hooks, Outline, Phase 0: Outline & Research, Phase 1: Design & Contracts, Phases (+2 more)

### Community 25 - ".claude/skills/speckit-specify/SKILL.md"
Cohesion: 0.18
Nodes (10): Completion Report, Done When, For AI Generation, Mandatory Post-Execution Hooks, Outline, Pre-Execution Checks, Quick Guidelines, Section Requirements (+2 more)

### Community 26 - ".claude/skills/speckit-tasks/SKILL.md"
Cohesion: 0.18
Nodes (10): Checklist Format (REQUIRED), Completion Report, Done When, Mandatory Post-Execution Hooks, Outline, Phase Structure, Pre-Execution Checks, Task Generation Rules (+2 more)

### Community 27 - ".github/skills/speckit-plan/SKILL.md"
Cohesion: 0.18
Nodes (10): Completion Report, Done When, Key rules, Mandatory Post-Execution Hooks, Outline, Phase 0: Outline & Research, Phase 1: Design & Contracts, Phases (+2 more)

### Community 28 - ".github/skills/speckit-specify/SKILL.md"
Cohesion: 0.18
Nodes (10): Completion Report, Done When, For AI Generation, Mandatory Post-Execution Hooks, Outline, Pre-Execution Checks, Quick Guidelines, Section Requirements (+2 more)

### Community 29 - ".github/skills/speckit-tasks/SKILL.md"
Cohesion: 0.18
Nodes (10): Checklist Format (REQUIRED), Completion Report, Done When, Mandatory Post-Execution Hooks, Outline, Phase Structure, Pre-Execution Checks, Task Generation Rules (+2 more)

### Community 30 - "Core Principles"
Cohesion: 0.18
Nodes (10): Core Principles, Governance, [PRINCIPLE_1_NAME], [PRINCIPLE_2_NAME], [PRINCIPLE_3_NAME], [PRINCIPLE_4_NAME], [PRINCIPLE_5_NAME], [PROJECT_NAME] Constitution (+2 more)

### Community 31 - "Implementation Plan: [FEATURE]"
Cohesion: 0.22
Nodes (8): Complexity Tracking, Constitution Check, Documentation (this feature), Implementation Plan: [FEATURE], Project Structure, Source Code (repository root), Summary, Technical Context

### Community 32 - "WorkflowDependencyGraph"
Cohesion: 0.40
Nodes (5): WorkflowDependencyGraph, next_step_after_change(), test_dependency_graph_resolves_transitive_invalidation_and_reason(), test_dependency_graph_tracks_transitive_invalidations(), test_next_step_selects_earliest_affected_step()

### Community 33 - ".claude/skills/speckit-checklist/SKILL.md"
Cohesion: 0.25
Nodes (7): Anti-Examples: What NOT To Do, Checklist Purpose: "Unit Tests for English", Example Checklist Types & Sample Items, Execution Steps, Post-Execution Checks, Pre-Execution Checks, User Input

### Community 34 - ".github/skills/speckit-checklist/SKILL.md"
Cohesion: 0.25
Nodes (7): Anti-Examples: What NOT To Do, Checklist Purpose: "Unit Tests for English", Example Checklist Types & Sample Items, Execution Steps, Post-Execution Checks, Pre-Execution Checks, User Input

### Community 35 - "Quickstart: Aria AI Relationship Manager"
Cohesion: 0.25
Nodes (7): Commands, Local setup, Multi-turn correction checks, Prerequisites, Production safety checks, Quickstart: Aria AI Relationship Manager, Validation scenarios

### Community 36 - ".claude/skills/speckit-clarify/SKILL.md"
Cohesion: 0.29
Nodes (6): Completion Report, Done When, Mandatory Post-Execution Hooks, Outline, Pre-Execution Checks, User Input

### Community 37 - ".claude/skills/speckit-implement/SKILL.md"
Cohesion: 0.29
Nodes (6): Completion Report, Done When, Mandatory Post-Execution Hooks, Outline, Pre-Execution Checks, User Input

### Community 38 - ".github/skills/speckit-clarify/SKILL.md"
Cohesion: 0.29
Nodes (6): Completion Report, Done When, Mandatory Post-Execution Hooks, Outline, Pre-Execution Checks, User Input

### Community 39 - ".github/skills/speckit-implement/SKILL.md"
Cohesion: 0.29
Nodes (6): Completion Report, Done When, Mandatory Post-Execution Hooks, Outline, Pre-Execution Checks, User Input

### Community 40 - "[PROJECT NAME] Development Guidelines"
Cohesion: 0.29
Nodes (6): Active Technologies, Code Style, Commands, [PROJECT NAME] Development Guidelines, Project Structure, Recent Changes

### Community 41 - ".claude/skills/speckit-constitution/SKILL.md"
Cohesion: 0.33
Nodes (5): Outline, Post-Execution Checks, Pre-Execution Checks, Scope Guard, User Input

### Community 42 - "build_artifacts.py"
Cohesion: 0.12
Nodes (21): argparse, fixture, pytest, build_target(), main(), Path, _python_platform(), _run() (+13 more)

### Community 43 - ".github/skills/speckit-constitution/SKILL.md"
Cohesion: 0.33
Nodes (5): Outline, Post-Execution Checks, Pre-Execution Checks, Scope Guard, User Input

### Community 45 - "Claude Code Project Instructions"
Cohesion: 0.40
Nodes (4): Agent-Specific Spec Kit Integration, Claude Code Project Instructions, Feature Development Process, Graphify

### Community 46 - ".claude/skills/speckit-taskstoissues/SKILL.md"
Cohesion: 0.40
Nodes (4): Outline, Post-Execution Checks, Pre-Execution Checks, User Input

### Community 47 - "Infrastructure"
Cohesion: 0.40
Nodes (4): Current stack, Important notes, Infrastructure, Local synthesis

### Community 48 - "GitHub Copilot Project Instructions"
Cohesion: 0.40
Nodes (4): Agent-Specific Spec Kit Integration, Feature Development Process, GitHub Copilot Project Instructions, Graphify

### Community 49 - ".github/skills/speckit-taskstoissues/SKILL.md"
Cohesion: 0.40
Nodes (4): Outline, Post-Execution Checks, Pre-Execution Checks, User Input

### Community 50 - "[CHECKLIST TYPE] Checklist: [FEATURE NAME]"
Cohesion: 0.40
Nodes (4): [Category 1], [Category 2], [CHECKLIST TYPE] Checklist: [FEATURE NAME], Notes

### Community 55 - "IdempotencyStore"
Cohesion: 0.33
Nodes (4): _build_runtime_coordinator(), IdempotencyStore, Exception, test_idempotency_store_from_environment_uses_configured_dynamodb_table()

### Community 65 - "AgentCoreMemoryDataPlaneClient"
Cohesion: 0.10
Nodes (8): AgentCoreMemoryDataPlaneClient, Tenant-bound boto3 client for documented AgentCore Memory data-plane APIs., test_agentcore_memory_data_plane_deletes_all_actor_records_across_pages(), test_agentcore_memory_data_plane_requires_record_id_for_delete(), test_agentcore_memory_data_plane_scopes_retrieval_to_authenticated_tenant(), test_agentcore_memory_data_plane_writes_tenant_variable_and_rejects_other_tenant(), test_agentcore_memory_user_erasure_fails_incomplete_for_out_of_scope_record(), test_agentcore_memory_user_erasure_propagates_delete_failure()

### Community 68 - "Implementation Plan: Dispute Resolution Subagent"
Cohesion: 0.06
Nodes (29): Aria Integration and Scope, Decision Safety and Governance, Notes, Requirements and Evaluation, Specification Quality Checklist: Dispute Resolution Subagent, Complexity Tracking, Constitution Check, Design Decisions (+21 more)

### Community 69 - "Specification Quality Checklist: Aria AI Relationship Manager"
Cohesion: 0.25
Nodes (8): Content Quality, Feature Readiness, Infrastructure Readiness, Notes, Production AI Application Readiness, Requirement Completeness, Shared Agent Framework Readiness, Specification Quality Checklist: Aria AI Relationship Manager

### Community 70 - "Data Model: Aria AI Relationship Manager"
Cohesion: 0.12
Nodes (17): AgentManifest, AuthorizationContext, ClientProfile, Data Model: Aria AI Relationship Manager, DependencyRule, EscalationTicket, FrameworkConfig, GuardrailResult (+9 more)

### Community 71 - "Tasks: Aria AI Relationship Manager"
Cohesion: 0.10
Nodes (21): Dependencies and Execution Order, MVP Scope, Parallel Opportunities, Phase 10: User Story 12 - Prompt Injection Defense (Priority: P1), Phase 11: User Story 13 - Knowledge Base Accuracy (Priority: P1), Phase 12: User Story 14 - CRM and API Context (Priority: P1), Phase 13: User Story 2 - Wallet Profiling and Consolidation (Priority: P2), Phase 14: User Story 3 - Financial Product Recommendations (Priority: P2) (+13 more)

### Community 72 - "test_foundation.py"
Cohesion: 0.11
Nodes (20): get_settings(), Settings, ClientProfile, BaseModel, BaseModel, RiskProfile, BaseSettings, CI/CD Integration (+12 more)

### Community 73 - "test_agentcore_adapters.py"
Cohesion: 0.09
Nodes (20): AgentCoreGatewaySigV4Auth, create_gateway_mcp_client(), filter_allowed_gateway_tools(), gateway_mcp_url(), Any, dataclasses, httpx, io (+12 more)

### Community 74 - "Observability"
Cohesion: 0.32
Nodes (6): Observability, Any, test_escalation_route_handles_high_value_credit(), test_observability_emits_json_for_cloudwatch(), test_observability_records_metrics_without_sensitive_data(), test_observability_records_structured_operation_metadata()

### Community 76 - "knowledge_tool.py"
Cohesion: 0.49
Nodes (9): answer_service_query(), extract_source_date(), format_citation(), _normalized_terms(), ProductAnswer, Any, query_product_info(), _score_match() (+1 more)

### Community 77 - "Decisions"
Cohesion: 0.20
Nodes (9): Analyst approval and permitted write, Aria integration, Audit and evaluation, Current Aria Integration Points, Decisions, Deterministic rules and confidence, Evidence sources and adapters, Research: Receivables Exception Resolution Subagent (+1 more)

### Community 79 - "test_strands_runtime.py"
Cohesion: 0.18
Nodes (13): Agent, build_strands_agent(), cancel_strands_agent(), Path, Build a Strands Agent without invoking the model during construction., Request cancellation through the installed Strands Agent API., strands, strands_agent_conversation_manager (+5 more)

### Community 80 - "Tasks"
Cohesion: 0.15
Nodes (12): MaturityEvent, OutflowEvent, ReinvestmentOption, ConsolidationOpportunity, Any, WalletProfile, Property 5: Wallet Profile Persistence, Implementation Plan: Aria — AI Relationship Manager Agent (+4 more)

### Community 81 - "Data Models"
Cohesion: 0.20
Nodes (10): Client Profile, Data Models, Escalation Ticket, Interaction Summary, Knowledge Base Response, KYC Status, Maturity Event, Risk Assessment (+2 more)

### Community 82 - "agentcore.py"
Cohesion: 0.11
Nodes (10): GatewayTransport, MemoryClient, PayloadParser, PreInvocationGuard, PromptBuilder, Any, Protocol, RuntimeClient (+2 more)

### Community 83 - "AgentCoreGatewayAdapter"
Cohesion: 0.23
Nodes (6): AgentCoreGatewayAdapter, AgentCoreRuntimeClient, Any, Invokes an IAM-authorized Runtime with a backend-verified principal., Separates Gateway discovery/tool visibility from authorization., test_runtime_client_invokes_scoped_runtime_with_verified_principal()

### Community 84 - "Feature Specification: Memory Context Contract Normalization"
Cohesion: 0.11
Nodes (15): Content Quality, Feature Readiness, Notes, Requirement Completeness, Specification Quality Checklist: Memory Context Contract Normalization, Assumptions, Edge Cases, Feature Specification: Memory Context Contract Normalization (+7 more)

### Community 85 - "Decisions"
Cohesion: 0.11
Nodes (17): API and Runtime identity, Artifact and release pipeline, Compatibility, Decisions, Deployed API Runtime routing, Deployment workflow trust and configuration, Gateway Lambda event, Gateway tool safety (+9 more)

### Community 86 - "Tasks: Production Readiness Remediation"
Cohesion: 0.14
Nodes (13): Dependencies and Execution Order, Implementation Strategy, Parallel Opportunities, Phase 10: T025 Follow-up - Operational Alarms and Log Data Protection, Phase 1: Setup, Phase 2: Foundational Tests, Phase 4: User Story 2 - Deployable and Constrained AWS Artifacts (Priority: P1), Phase 5: User Story 3 - Safe Stateful Agent Execution (Priority: P1) (+5 more)

### Community 87 - "test_mmdsv2_custom_resource.py"
Cohesion: 0.31
Nodes (5): boto3, handler(), test_mmdsv2_custom_resource_delete_is_noop(), test_mmdsv2_custom_resource_preserves_runtime_artifact_and_role(), types

### Community 88 - "invoke_gateway_tool"
Cohesion: 0.23
Nodes (7): handler(), invoke_gateway_tool(), Any, _serialized_payload(), test_gateway_lambda_adapter_allows_only_published_tools(), test_gateway_lambda_rejects_arguments_and_blocks_sensitive_results(), test_gateway_lambda_uses_agentcore_tool_name_from_lambda_context()

### Community 89 - "Data Model: Production Readiness Remediation"
Cohesion: 0.29
Nodes (6): ConversationState, Data Model: Production Readiness Remediation, IdempotencyRecord, MemoryRecord, ReleaseEvidence, VerifiedPrincipal

### Community 90 - "Quickstart: Production Readiness Validation"
Cohesion: 0.29
Nodes (6): Artifact and full CI checks, Execution Record, Local focused checks, Prerequisites, Quickstart: Production Readiness Validation, Sandbox verification

### Community 91 - "Implementation Plan: KYC/AML Verification Subagent"
Cohesion: 0.07
Nodes (26): Aria Integration and Scope, Notes, Requirements and Testing, Safety and Governance, Specification Quality Checklist: KYC/AML Verification Subagent, Complexity Tracking, Constitution Check, Implementation Plan: KYC/AML Verification Subagent (+18 more)

### Community 92 - "Agent Framework"
Cohesion: 0.29
Nodes (6): Agent Framework, AgentCore boundary, Core contracts, Local development and release evidence, Manifest schema, Supported assumptions

### Community 93 - "aria/agent.py"
Cohesion: 0.17
Nodes (18): InteractionSummary, create_followup_reminder(), get_client_profile(), log_interaction(), Any, update_client_profile(), check_upcoming_maturities(), detect_large_outflows() (+10 more)

### Community 94 - "AgentCoreRuntimeAdapter"
Cohesion: 0.12
Nodes (17): Any, RuntimeSessionBusy, RuntimeSessionCoordinator, AgentCoreRuntimeAdapter, Maps an authenticated conversation to one recoverable Runtime session., RuntimeSession, hashlib, importlib (+9 more)

### Community 95 - "AriaAgent"
Cohesion: 0.20
Nodes (7): AriaAgent, Any, test_maturity_tool_flags_30_day_maturity(), test_recommend_products_by_risk_profile(), test_recommend_products_highlights_protection_and_credit_benefits(), test_wallet_profile_builds_consolidation_opportunities(), test_wallet_profile_detects_external_assets()

### Community 96 - "ComplianceVerifier"
Cohesion: 0.07
Nodes (55): aria_agents_aria_kyc_aml, build_kyc_aml_subagent_tool(), Any, Bind a child specialist to a parent-verified subject; the model cannot choose…, AMLAssessment, AMLFinding, ComplianceAssessment, ComplianceAuditEvent (+47 more)

### Community 97 - "Implementation Plan: Virtual Account Receivables Exception Resolution Subagent"
Cohesion: 0.07
Nodes (26): Financial Safety and Governance, Notes, Requirements and Evaluation, Scope and Aria Fit, Specification Quality Checklist: Virtual Account Receivables Exception Resolution, Complexity Tracking, Constitution Check, Documentation (this feature) (+18 more)

### Community 98 - "test_service_and_compliance.py"
Cohesion: 0.12
Nodes (20): check_kyc_status(), flag_aml_activity(), Any, decimal, Property 15: AML Threshold Flagging, parametrize, Phase 8: User Story 9 - Regulatory Compliance (Priority: P1), test_agent_escalates_unresolved_service_query_with_client_context() (+12 more)

### Community 99 - "Tasks: KYC/AML Verification Subagent"
Cohesion: 0.18
Nodes (10): Dependencies and Execution Order, Implementation Strategy, Parallel Opportunities, Phase 1: Setup, Phase 2: Foundational Contracts and Safety, Phase 3: User Story 1 - Extract and Verify Identity Evidence (Priority: P1), Phase 4: User Story 2 - Assess Risk and Escalate (Priority: P1), Phase 5: User Story 3 - Integrate Through Aria Parent (Priority: P1) (+2 more)

### Community 100 - "Data Model: Receivables Exception Resolution"
Cohesion: 0.17
Nodes (11): AnalystDecision, ApprovedPolicy, CaseTask, Data Model: Receivables Exception Resolution, InvestigationRecommendation, InvoiceCandidate, MatchingDecision, ReceivablesAuditEvent (+3 more)

### Community 101 - "Data Model: KYC/AML Verification"
Cohesion: 0.20
Nodes (9): AMLAssessment, ComplianceAssessment, ComplianceAuditEvent, CompliancePolicy, Data Model: KYC/AML Verification, DocumentReference, ExtractedFieldObservation, VerificationObservation (+1 more)

### Community 102 - "AgentCoreMemoryAdapter"
Cohesion: 0.10
Nodes (10): AgentCoreMemoryAdapter, Applies tenant and retrieval bounds around an AgentCore Memory client., Decision: A configured remote backend must own deletion, Decision: Keep `MemoryEntry` as the canonical in-process value, Decision: Preserve policy and provider boundaries, Decision: Use a narrow structural retrieval protocol for context assembly, Research: Memory Context Contract Normalization, test_memory_adapter_does_not_delete_locally_when_remote_delete_is_unsupported() (+2 more)

### Community 103 - "Tasks: Account Statement Explainer Subagent"
Cohesion: 0.18
Nodes (10): Dependencies and Execution Order, Implementation Strategy, Parallel Opportunities, Phase 1: Setup, Phase 2: Foundational Data and Validation, Phase 3: User Story 1 - Aria Specialist Handoff (Priority: P1), Phase 4: User Story 2 - Deterministic Statement Analysis (Priority: P1), Phase 5: User Story 3 - Safe Activity Trace (Priority: P1) (+2 more)

### Community 104 - "Tasks: Virtual Account Receivables Exception Resolution Subagent"
Cohesion: 0.18
Nodes (10): Dependencies and Execution Order, Implementation Strategy, Parallel Opportunities, Phase 1: Setup, Phase 2: Foundational Models, Sources, and Rules, Phase 3: User Story 1 - Bounded Aria Subagent Investigation (Priority: P1), Phase 4: User Story 2 - Deterministic, Evidence-Backed Recommendation (Priority: P1), Phase 5: User Story 3 - Analyst Approval and Sole Permitted Write (Priority: P1) (+2 more)

### Community 105 - "Tasks: Dispute Resolution Subagent"
Cohesion: 0.18
Nodes (10): Dependencies and Execution Order, Implementation Strategy, Parallel Opportunities, Phase 1: Setup, Phase 2: Foundational Evidence and Rules, Phase 3: User Story 1 - Aria Dispute Specialist Handoff (Priority: P1), Phase 4: User Story 2 - Explainable Dispute Recommendation (Priority: P1), Phase 5: User Story 3 - Human Decision and Simulated Action Gate (Priority: P1) (+2 more)

### Community 106 - "Decisions"
Cohesion: 0.20
Nodes (9): Current Aria Integration Points, Decisions, Demo web surface, Deterministic analysis tools, Parent-to-specialist handoff, Research: Account Statement Explainer Subagent, Risks and Open Boundaries, Streaming and visible trace (+1 more)

### Community 107 - "Decisions"
Cohesion: 0.20
Nodes (9): Aria integration, Aria Integration Points, Audit and escalation, Decisions, Document extraction, External Decisions Required, Multi-source verification, Research: KYC/AML Verification Subagent (+1 more)

### Community 108 - "Data Model: Account Statement Explainer"
Cohesion: 0.22
Nodes (8): AgentActivityEvent, Data Model: Account Statement Explainer, StatementAnalysisRequest, StatementAuditRecord, StatementDataset, StatementExplainerSession, StatementToolResult, StatementTransaction

### Community 109 - "test_persistence_and_observability.py"
Cohesion: 0.13
Nodes (9): Any, StateStore, test_observability_redacts_and_records_context_metadata(), test_observability_redacts_nested_sensitive_values_and_secret_text(), test_session_manager_supports_revision_and_retries(), test_state_store_applies_idempotent_update_and_runs_side_effect_once(), test_state_store_rejects_duplicate_after_restart_with_dynamodb_idempotency(), test_state_store_rejects_stale_revision_and_keeps_idempotency() (+1 more)

### Community 110 - "Contract: Receivables Investigation and Analyst Approval"
Cohesion: 0.29
Nodes (6): Analyst decision, Aria parent-to-specialist handoff, Audit contract, Contract: Receivables Investigation and Analyst Approval, Investigation result, Permitted write contract

### Community 111 - "Contract: Statement Explainer Handoff and Activity Stream"
Cohesion: 0.33
Nodes (5): Aria parent-to-specialist handoff, Contract: Statement Explainer Handoff and Activity Stream, Local demo request, Server-Sent Events, Tool failures

### Community 112 - "Quickstart: Account Statement Explainer Prototype"
Cohesion: 0.33
Nodes (5): Performance evidence, Prerequisites, Quickstart: Account Statement Explainer Prototype, Run the local demo, Validate

### Community 113 - "Quickstart: Receivables Exception Resolution MVP"
Cohesion: 0.33
Nodes (5): Demo acceptance, Investigation walkthrough, Local validation, Prerequisites, Quickstart: Receivables Exception Resolution MVP

### Community 114 - "Contract: Dispute Investigation and Human Review"
Cohesion: 0.33
Nodes (5): Aria parent-to-specialist handoff, Contract: Dispute Investigation and Human Review, Human decision, Safe activity and audit events, Specialist result

### Community 115 - "Quickstart: Dispute Resolution MVP"
Cohesion: 0.33
Nodes (5): Controlled walkthrough, Local validation, MVP acceptance evidence, Prerequisites, Quickstart: Dispute Resolution MVP

### Community 116 - "Implementation Plan: Aria AI Relationship Manager"
Cohesion: 0.20
Nodes (10): CDK deployment rules, Constitution Check, Implementation Phases, Implementation Plan: Aria AI Relationship Manager, Infrastructure Plan: AWS CDK v2, Project Structure, Risks and Open Decisions, Shared Agent Framework (+2 more)

### Community 117 - "MemoryEntry"
Cohesion: 0.15
Nodes (16): ContextBuilder, Any, MemoryRetriever, MemoryEntry, MemoryStore, Data Model: Memory Context Contract Normalization, Deletion Behavior, MemoryEntry (+8 more)

### Community 118 - "Decisions"
Cohesion: 0.20
Nodes (9): Aria subagent shape, Current Aria Integration Points, Decisioning and actions, Decisions, Evaluation, Evidence and source access, Human approval and audit, Research: Dispute Resolution Subagent (+1 more)

### Community 119 - "Data Model: Dispute Resolution"
Cohesion: 0.22
Nodes (8): Data Model: Dispute Resolution, DisputeAuditEvent, DisputeCase, DisputeEvidence, DisputeFinding, DisputePolicy, DisputeRecommendation, HumanDecision

### Community 121 - "SessionManager"
Cohesion: 0.19
Nodes (9): _build_session_id(), Any, Exception, SessionManager, Session, test_dynamodb_session_manager_recovers_state_and_rejects_stale_revision(), test_session_manager_recovers_existing_session_state(), test_session_manager_tracks_lock_and_release() (+1 more)

### Community 122 - "Error Handling"
Cohesion: 0.22
Nodes (9): 1. External Service Failures (CRM, CBS), 2. Knowledge Base Fallback, 3. Guardrail Processing Errors, 4. Session Recovery, Error Categories and Strategies, Error Handling, Error Handling Patterns, Error Response Templates (+1 more)

### Community 123 - "KYCStatusProvider"
Cohesion: 0.33
Nodes (5): KYCStatusProvider, Protocol, Callable contract for an authoritative KYC status source., Phase 3: User Story 1 - Trusted Client Access (Priority: P1), Design Decisions

### Community 124 - "Quickstart: KYC/AML Verification Subagent"
Cohesion: 0.40
Nodes (4): Local validation, Prerequisites, Quickstart: KYC/AML Verification Subagent, Walkthrough

### Community 125 - "Design Document: Aria — AI Relationship Manager Agent"
Cohesion: 0.25
Nodes (7): Architecture, Design Document: Aria — AI Relationship Manager Agent, High-Level Architecture, Key Design Decisions, Overview, Request Flow, Technology Stack

### Community 126 - "Implementation Plan: Memory Context Contract Normalization"
Cohesion: 0.25
Nodes (8): Complexity Tracking, Constitution Check, Documentation (this feature), Implementation Plan: Memory Context Contract Normalization, Project Structure, Source Code (repository root), Summary, Technical Context

### Community 127 - "2. Tools"
Cohesion: 0.29
Nodes (7): 2. Tools, Compliance Tool (`aria/tools/compliance_tool.py`), CRM Tool (`aria/tools/crm_tool.py`), Escalation Tool (`aria/tools/escalation_tool.py`), Knowledge Base Tool (`aria/tools/knowledge_tool.py`), Maturity and Retention Tool (`aria/tools/maturity_tool.py`), Risk Assessment Tool (`aria/tools/risk_tool.py`)

### Community 128 - "Tasks: Memory Context Contract Normalization"
Cohesion: 0.29
Nodes (6): Dependencies and Execution Order, Implementation Strategy, Phase 1: Setup, Phase 2: User Story 1 - Consistent Memory Context (Priority: P1), Tasks: Memory Context Contract Normalization, Tests

### Community 129 - "processor.py"
Cohesion: 0.43
Nodes (3): logging, re, uuid

### Community 130 - "Components and Interfaces"
Cohesion: 0.40
Nodes (5): 1. Aria Agent Core (`aria/agent.py`), 3. Guardrail Configuration (`aria/guardrails/config.py`), 4. Session Manager (`aria/session/manager.py`), 5. Event Handler (`aria/events/handler.py`), Components and Interfaces

### Community 131 - "Deployment"
Cohesion: 0.29
Nodes (6): Deployed components, Deployment, GitHub Actions deployment, Memory and observability policy, Required inputs, Synthesis

### Community 132 - "Quickstart: Memory Context Contract Normalization"
Cohesion: 0.40
Nodes (4): Focused Validation, Prerequisites, Quickstart: Memory Context Contract Normalization, Validation Results (2026-10-02)

### Community 133 - "FollowUpAction"
Cohesion: 0.40
Nodes (4): FollowUpAction, BaseModel, datetime, field_validator

### Community 134 - "Invocation Contracts"
Cohesion: 0.40
Nodes (4): AgentCore Gateway Lambda target, AgentCore Runtime invocation, Authenticated API Gateway request, Invocation Contracts

## Knowledge Gaps
- **714 isolated node(s):** `aria-ai-relationship-manager`, `User Input`, `Pre-Execution Checks`, `Goal`, `Operating Constraints` (+709 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 954 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AriaAgent` connect `AriaAgent` to `test_api_and_events.py`, `test_workflow_risk.py`, `aria/agentcore_entrypoint.py`, `test_service_and_compliance.py`, `GuardrailProcessor`, `Observability`, `test_strands_runtime.py`, `Tasks`, `invoke_gateway_tool`, `KYCStatusProvider`, `aria/agent.py`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `SessionManager` connect `SessionManager` to `Tasks: Aria AI Relationship Manager`, `test_agentcore_adapters.py`, `test_persistence_and_observability.py`, `Tasks`, `agentcore.py`, `IdempotencyStore`, `AgentCoreRuntimeAdapter`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `Tasks: Aria AI Relationship Manager` connect `Tasks: Aria AI Relationship Manager` to `test_workflow_risk.py`, `test_service_and_compliance.py`, `aria/agent.py`, `001-ai-relationship-manager/tasks.md`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `AriaAgent` (e.g. with `GuardrailProcessor` and `Observability`) actually correct?**
  _`AriaAgent` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `SessionManager` (e.g. with `AgentCoreRuntimeAdapter` and `Tasks`) actually correct?**
  _`SessionManager` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `ComplianceVerifier` (e.g. with `build_kyc_aml_subagent_tool()` and `AMLAssessment`) actually correct?**
  _`ComplianceVerifier` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `GuardrailProcessor` (e.g. with `AriaAgent` and `Observability`) actually correct?**
  _`GuardrailProcessor` has 5 INFERRED edges - model-reasoned connections that need verification._