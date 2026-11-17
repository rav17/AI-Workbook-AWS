# Graph Report - banking-relationship-manager-agent  (2026-10-03)

## Corpus Check
- 232 files · ~144,167 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: .drawio 14, (none) 4, .kiro 1)

## Summary
- 2049 nodes · 3375 edges · 143 communities (119 shown, 24 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 197 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b3ba468c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- rest_handler.py
- test_workflow_risk.py
- statement_explainer/app.py
- Implementation Plan: Production Readiness Remediation
- FrameworkRunner
- Requirements
- Research: Aria AI Relationship Manager
- SessionManager
- Specification Quality Checklist: AWS Service Icons in Architecture Diagram
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
- GuardrailProcessor
- aria/agentcore_entrypoint.py
- knowledge_tool.py
- Decisions
- test_statement_subagent.py
- test_strands_runtime.py
- Tasks
- AriaAgent
- agentcore.py
- AgentCoreGatewayAdapter
- Feature Specification: Memory Context Contract Normalization
- Decisions
- Tasks: Production Readiness Remediation
- test_mmdsv2_custom_resource.py
- Observability
- Data Model: Production Readiness Remediation
- Quickstart: Production Readiness Validation
- Implementation Plan: KYC/AML Verification Subagent
- Agent Framework
- aria/agent.py
- AgentCoreRuntimeAdapter
- .__init__
- ComplianceVerifier
- Implementation Plan: Virtual Account Receivables Exception Resolution Subagent
- test_service_and_compliance.py
- Tasks: KYC/AML Verification Subagent
- Diagram
- Data Model: KYC/AML Verification
- MemoryEntry
- Tasks: Account Statement Explainer Subagent
- Tasks: Virtual Account Receivables Exception Resolution Subagent
- Tasks: Dispute Resolution Subagent
- Decisions
- KYCStatusProvider
- app.js
- test_persistence_and_observability.py
- Contract: Receivables Investigation and Analyst Approval
- Data Model: Receivables Exception Resolution
- test_rest_handler_accepts_verified_tenant_and_subject_claims
- Quickstart: Receivables Exception Resolution MVP
- Contract: Dispute Investigation and Human Review
- Quickstart: Dispute Resolution MVP
- Implementation Plan: Aria AI Relationship Manager
- ContextBuilder
- Decisions
- InteractionSummary
- Research: AWS Service Icons in Architecture Diagram
- Tasks: AWS Service Icons in Architecture Diagram
- Shared Framework Decisions
- Production Best Practices
- Quickstart: KYC/AML Verification Subagent
- ._sanitize
- Implementation Plan: Memory Context Contract Normalization
- Data Models
- Tasks: Memory Context Contract Normalization
- status
- test_api_and_events.py
- Deployment
- Quickstart: Memory Context Contract Normalization
- get_risk_questionnaire
- Contract: Statement Explainer Handoff and Activity Stream
- Aria Statement Explainer Demo
- test_memory_adapter_rejects_invalid_or_cross_tenant_remote_records
- Research: Memory Context Contract Normalization
- demo/__init__.py
- contracts/README.md
- 008-aws-service-icons/data-model.md
- 008-aws-service-icons/quickstart.md

## God Nodes (most connected - your core abstractions)
1. `AriaAgent` - 57 edges
2. `GuardrailProcessor` - 34 edges
3. `SessionManager` - 34 edges
4. `ComplianceVerifier` - 32 edges
5. `Observability` - 26 edges
6. `Diagram` - 26 edges
7. `IdempotencyStore` - 24 edges
8. `Tasks: Aria AI Relationship Manager` - 24 edges
9. `MemoryEntry` - 23 edges
10. `AgentCoreRuntimeAdapter` - 22 edges

## Surprising Connections (you probably didn't know these)
- `StatementDataset` --references--> `StatementTransaction`  [INFERRED]
  specs/003-account-statement-explainer/data-model.md → aria/agents/aria/statement_explainer/models.py
- `Phase 5: User Story 3 - Safe Activity Trace (Priority: P1)` --references--> `AgentActivityEvent`  [INFERRED]
  specs/003-account-statement-explainer/tasks.md → aria/agents/aria/statement_explainer/models.py
- `Deployed API Runtime routing` --references--> `handler()`  [INFERRED]
  specs/002-production-readiness/research.md → aria/api/rest_handler.py
- `Current Aria Integration Points` --references--> `RuntimeSessionCoordinator`  [INFERRED]
  specs/003-account-statement-explainer/research.md → aria/api/runtime_session.py
- `Decision: A configured remote backend must own deletion` --references--> `MemoryClient`  [INFERRED]
  specs/007-memory-context-contract/research.md → aria/framework/contracts.py

## Import Cycles
- None detected.

## Communities (143 total, 24 thin omitted)

### Community 0 - "rest_handler.py"
Cohesion: 0.21
Nodes (19): handler(), invoke_agent(), make_response(), parse_body(), Any, _build_runtime_coordinator(), handler(), _idempotency_key() (+11 more)

### Community 1 - "test_workflow_risk.py"
Cohesion: 0.30
Nodes (8): PatchOperation, Any, StatePatch, WorkflowState, Design Summary, test_workflow_state_applies_multiple_operations_atomically(), test_workflow_state_patch_applies_revision(), test_workflow_state_rejects_stale_or_locked_atomic_patches()

### Community 2 - "statement_explainer/app.py"
Cohesion: 0.05
Nodes (73): build_statement_explainer_tool(), Any, route_statement_question(), should_route_statement_question(), _default_dataset(), _load_fixture_file(), load_statement_dataset(), normalize_activity_event() (+65 more)

### Community 3 - "Implementation Plan: Production Readiness Remediation"
Cohesion: 0.07
Nodes (26): Content Quality, Feature Readiness, Notes, Requirement Completeness, Specification Quality Checklist: Production Readiness Remediation, Constitution Check, Design, Implementation Plan: Production Readiness Remediation (+18 more)

### Community 4 - "FrameworkRunner"
Cohesion: 0.17
Nodes (13): FrameworkConfig, load_framework_config(), Any, FrameworkRunner, Any, asyncio, test_framework_config_has_safe_defaults(), test_framework_config_loads_environment_overrides_and_rejects_invalid_limits() (+5 more)

### Community 5 - "Requirements"
Cohesion: 0.06
Nodes (32): Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria (+24 more)

### Community 6 - "Research: Aria AI Relationship Manager"
Cohesion: 0.13
Nodes (15): AWS CDK v2 Decisions, Decision: Enforce boundaries through the supported API, Decision: Make synthesis deterministic and deployment controlled, Decision: Prefer direct references inside one CDK app, Decision: Separate typed domain models from provider tools, Decision: Start with mocked external-service tests, Decision: Test infrastructure contracts, Decision: Treat auto-discovery as opt-in (+7 more)

### Community 7 - "SessionManager"
Cohesion: 0.12
Nodes (14): _build_session_id(), Any, Exception, SessionManager, Session, test_session_manager_rejects_duplicate_write_lock(), test_session_manager_reuses_conversation_session(), FakeConditionalFailure (+6 more)

### Community 9 - "Specification Quality Checklist: AWS Service Icons in Architecture Diagram"
Cohesion: 0.08
Nodes (22): Content Quality, Feature Readiness, Notes, Requirement Completeness, Specification Quality Checklist: AWS Service Icons in Architecture Diagram, Constitution Check, Documentation (this feature), Implementation Plan: AWS Service Icons in Architecture Diagram (+14 more)

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
Nodes (19): Correctness Properties, Property 11: Follow-Up Reminder Creation, Property 12: Sensitive Credential Detection and Rejection, Property 13: Market Risk Disclosure Compliance, Property 14: KYC Gating for New Products, Property 15: AML Threshold Flagging, Property 16: Escalation for Sensitive/Complex Requests, Property 17: Adversarial Input Handling (+11 more)

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
Cohesion: 0.08
Nodes (27): argparse, fastapi_testclient, pytest, build_target(), main(), Path, _python_platform(), _run() (+19 more)

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
Cohesion: 0.15
Nodes (5): IdempotencyStore, Exception, test_idempotency_store_from_environment_uses_configured_dynamodb_table(), test_idempotency_store_persists_claims_across_instances_and_releases_for_retry(), test_idempotency_store_reclaims_expired_in_progress_claim()

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
Cohesion: 0.15
Nodes (13): AgentManifest, AuthorizationContext, ClientProfile, Data Model: Aria AI Relationship Manager, DependencyRule, FrameworkConfig, GuardrailResult, InteractionSummary (+5 more)

### Community 71 - "Tasks: Aria AI Relationship Manager"
Cohesion: 0.10
Nodes (21): Dependencies and Execution Order, MVP Scope, Parallel Opportunities, Phase 10: User Story 12 - Prompt Injection Defense (Priority: P1), Phase 11: User Story 13 - Knowledge Base Accuracy (Priority: P1), Phase 12: User Story 14 - CRM and API Context (Priority: P1), Phase 13: User Story 2 - Wallet Profiling and Consolidation (Priority: P2), Phase 14: User Story 3 - Financial Product Recommendations (Priority: P2) (+13 more)

### Community 72 - "test_foundation.py"
Cohesion: 0.17
Nodes (12): get_settings(), Settings, ClientProfile, BaseModel, BaseModel, RiskProfile, BaseSettings, pydantic (+4 more)

### Community 73 - "test_agentcore_adapters.py"
Cohesion: 0.10
Nodes (16): handler(), invoke_gateway_tool(), Any, _serialized_payload(), io, json, FakeGatewayTransport, FakeMemoryClient (+8 more)

### Community 74 - "GuardrailProcessor"
Cohesion: 0.21
Nodes (9): GuardrailProcessor, GuardrailResult, Protect user input and output from sensitive credential leakage., test_escalation_emits_structured_operation(), test_escalation_tool_routes_to_correct_team(), test_guardrail_blocks_sensitive_credentials_and_injection(), test_guardrail_processor_blocks_prompt_injection_and_returns_structured_result(), test_guardrail_processor_sanitizes_output_before_returning_to_client() (+1 more)

### Community 75 - "aria/agentcore_entrypoint.py"
Cohesion: 0.05
Nodes (37): _build_strands_agent(), invoke(), main(), _ManagedStrandsInvocation, Any, resolve_runtime_identity(), _response_text(), run_runtime_invocation() (+29 more)

### Community 76 - "knowledge_tool.py"
Cohesion: 0.49
Nodes (9): answer_service_query(), extract_source_date(), format_citation(), _normalized_terms(), ProductAnswer, Any, query_product_info(), _score_match() (+1 more)

### Community 77 - "Decisions"
Cohesion: 0.20
Nodes (9): Analyst approval and permitted write, Aria integration, Audit and evaluation, Current Aria Integration Points, Decisions, Deterministic rules and confidence, Evidence sources and adapters, Research: Receivables Exception Resolution Subagent (+1 more)

### Community 78 - "test_statement_subagent.py"
Cohesion: 0.10
Nodes (14): normalize_strands_event(), Map known Strands lifecycle envelopes; never forward arbitrary event data., test_parent_blocks_unsafe_statement_question_before_handoff(), test_parent_bounds_follow_up_context_before_handoff(), test_parent_delegates_statement_question_with_active_statement_scope(), statement_tool(), test_parent_does_not_delegate_unrelated_question(), test_parent_does_not_route_generic_wire_transfer_question_to_statement_tool() (+6 more)

### Community 79 - "test_strands_runtime.py"
Cohesion: 0.18
Nodes (13): Agent, build_strands_agent(), cancel_strands_agent(), Path, Build a Strands Agent without invoking the model during construction., Request cancellation through the installed Strands Agent API., strands, strands_agent_conversation_manager (+5 more)

### Community 80 - "Tasks"
Cohesion: 0.15
Nodes (13): MaturityEvent, OutflowEvent, ReinvestmentOption, ConsolidationOpportunity, Any, WalletProfile, Property 5: Wallet Profile Persistence, Property-Based Testing (+5 more)

### Community 81 - "AriaAgent"
Cohesion: 0.21
Nodes (6): AriaAgent, Any, test_recommend_products_by_risk_profile(), test_recommend_products_highlights_protection_and_credit_benefits(), test_wallet_profile_builds_consolidation_opportunities(), test_wallet_profile_detects_external_assets()

### Community 82 - "agentcore.py"
Cohesion: 0.15
Nodes (9): GatewayTransport, MemoryClient, PayloadParser, PreInvocationGuard, PromptBuilder, Any, Protocol, ToolFilter (+1 more)

### Community 83 - "AgentCoreGatewayAdapter"
Cohesion: 0.21
Nodes (6): AgentCoreGatewayAdapter, AgentCoreRuntimeClient, Any, Invokes an IAM-authorized Runtime with a backend-verified principal., Separates Gateway discovery/tool visibility from authorization., test_runtime_client_invokes_scoped_runtime_with_verified_principal()

### Community 84 - "Feature Specification: Memory Context Contract Normalization"
Cohesion: 0.11
Nodes (15): Content Quality, Feature Readiness, Notes, Requirement Completeness, Specification Quality Checklist: Memory Context Contract Normalization, Assumptions, Edge Cases, Feature Specification: Memory Context Contract Normalization (+7 more)

### Community 85 - "Decisions"
Cohesion: 0.11
Nodes (17): API and Runtime identity, Artifact and release pipeline, Compatibility, Decisions, Deployed API Runtime routing, Deployment workflow trust and configuration, Gateway Lambda event, Gateway tool safety (+9 more)

### Community 86 - "Tasks: Production Readiness Remediation"
Cohesion: 0.13
Nodes (14): Dependencies and Execution Order, Implementation Strategy, Parallel Opportunities, Phase 10: T025 Follow-up - Operational Alarms and Log Data Protection, Phase 11: Synchronous API Timeout Budget, Phase 12: Repository CI Formatting Scope, Phase 1: Setup, Phase 2: Foundational Tests (+6 more)

### Community 87 - "test_mmdsv2_custom_resource.py"
Cohesion: 0.31
Nodes (5): boto3, handler(), test_mmdsv2_custom_resource_delete_is_noop(), test_mmdsv2_custom_resource_preserves_runtime_artifact_and_role(), types

### Community 88 - "Observability"
Cohesion: 0.26
Nodes (10): Observability, escalate_request(), Any, logging, re, test_escalation_route_handles_high_value_credit(), test_observability_emits_json_for_cloudwatch(), test_observability_records_metrics_without_sensitive_data() (+2 more)

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
Cohesion: 0.14
Nodes (12): Account statement explainer prototype, Agent Framework, AgentCore boundary, Core contracts, Local development and release evidence, Manifest schema, Supported assumptions, Performance evidence (+4 more)

### Community 93 - "aria/agent.py"
Cohesion: 0.16
Nodes (18): create_followup_reminder(), get_client_profile(), log_interaction(), Any, update_client_profile(), assess_risk_appetite(), Any, Phase 5: User Story 6 - CRM Interaction Logging (Priority: P1) (+10 more)

### Community 94 - "AgentCoreRuntimeAdapter"
Cohesion: 0.14
Nodes (16): IdempotencyConflict, Any, RuntimeSessionBusy, RuntimeSessionCoordinator, AgentCoreRuntimeAdapter, Maps an authenticated conversation to one recoverable Runtime session., RuntimeSession, RuntimeClient (+8 more)

### Community 95 - ".__init__"
Cohesion: 0.18
Nodes (17): _build_reinvestment_options(), check_upcoming_maturities(), detect_large_outflows(), evaluate_maturity_event(), evaluate_outflow_event(), Any, hypothesis, given (+9 more)

### Community 96 - "ComplianceVerifier"
Cohesion: 0.07
Nodes (54): aria_agents_aria_kyc_aml, build_kyc_aml_subagent_tool(), Any, Bind a child specialist to a parent-verified subject; the model cannot choose…, AMLAssessment, AMLFinding, ComplianceAssessment, ComplianceAuditEvent (+46 more)

### Community 97 - "Implementation Plan: Virtual Account Receivables Exception Resolution Subagent"
Cohesion: 0.07
Nodes (26): Financial Safety and Governance, Notes, Requirements and Evaluation, Scope and Aria Fit, Specification Quality Checklist: Virtual Account Receivables Exception Resolution, Complexity Tracking, Constitution Check, Documentation (this feature) (+18 more)

### Community 98 - "test_service_and_compliance.py"
Cohesion: 0.14
Nodes (18): check_kyc_status(), flag_aml_activity(), Any, Phase 8: User Story 9 - Regulatory Compliance (Priority: P1), parametrize, test_agent_escalates_unresolved_service_query_with_client_context(), test_agent_routes_resolvable_service_query_to_knowledge_answer(), test_aml_activity_does_not_flag_zero_activity_with_positive_threshold() (+10 more)

### Community 99 - "Tasks: KYC/AML Verification Subagent"
Cohesion: 0.18
Nodes (10): Dependencies and Execution Order, Implementation Strategy, Parallel Opportunities, Phase 1: Setup, Phase 2: Foundational Contracts and Safety, Phase 3: User Story 1 - Extract and Verify Identity Evidence (Priority: P1), Phase 4: User Story 2 - Assess Risk and Escalate (Priority: P1), Phase 5: User Story 3 - Integrate Through Aria Parent (Priority: P1) (+2 more)

### Community 100 - "Diagram"
Cohesion: 0.07
Nodes (35): aop(), component_model(), deployment_units(), Diagram, end_state_architecture(), legend(), location_model(), lom() (+27 more)

### Community 101 - "Data Model: KYC/AML Verification"
Cohesion: 0.20
Nodes (9): AMLAssessment, ComplianceAssessment, ComplianceAuditEvent, CompliancePolicy, Data Model: KYC/AML Verification, DocumentReference, ExtractedFieldObservation, VerificationObservation (+1 more)

### Community 102 - "MemoryEntry"
Cohesion: 0.14
Nodes (15): AgentCoreMemoryAdapter, Applies tenant and retrieval bounds around an AgentCore Memory client., ParsedTurn, MemoryEntry, MemoryStore, Data Model: Memory Context Contract Normalization, Deletion Behavior, MemoryEntry (+7 more)

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

### Community 107 - "KYCStatusProvider"
Cohesion: 0.12
Nodes (14): KYCStatusProvider, Protocol, Callable contract for an authoritative KYC status source., Phase 3: User Story 1 - Trusted Client Access (Priority: P1), Design Decisions, Aria integration, Aria Integration Points, Audit and escalation (+6 more)

### Community 108 - "app.js"
Cohesion: 0.35
Nodes (10): appendActivity(), appendMessage(), currencyFormat(), elements, highlightTransactions(), initialize(), renderEvent(), renderTransactions() (+2 more)

### Community 109 - "test_persistence_and_observability.py"
Cohesion: 0.10
Nodes (14): Any, StateStore, hashlib, importlib, os, test_observability_redacts_and_records_context_metadata(), test_observability_redacts_nested_sensitive_values_and_secret_text(), test_session_manager_supports_revision_and_retries() (+6 more)

### Community 110 - "Contract: Receivables Investigation and Analyst Approval"
Cohesion: 0.29
Nodes (6): Analyst decision, Aria parent-to-specialist handoff, Audit contract, Contract: Receivables Investigation and Analyst Approval, Investigation result, Permitted write contract

### Community 111 - "Data Model: Receivables Exception Resolution"
Cohesion: 0.18
Nodes (10): AnalystDecision, ApprovedPolicy, CaseTask, Data Model: Receivables Exception Resolution, InvestigationRecommendation, InvoiceCandidate, MatchingDecision, ReceivablesException (+2 more)

### Community 112 - "test_rest_handler_accepts_verified_tenant_and_subject_claims"
Cohesion: 0.20
Nodes (4): FakeRuntimeClient, test_runtime_adapter_reuses_and_recovers_runtime_session(), test_deployed_lambda_handler_routes_authenticated_request_to_runtime(), test_rest_handler_accepts_verified_tenant_and_subject_claims()

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

### Community 117 - "ContextBuilder"
Cohesion: 0.20
Nodes (8): ContextBuilder, Any, MemoryRetriever, test_context_builder_accepts_an_absent_memory_backend(), test_context_builder_accepts_remote_adapter_records_in_normalized_shape(), test_context_builder_exposes_memory_without_overriding_current_state(), test_context_builder_prefers_current_workflow_state_over_memory(), test_context_builder_redacts_sensitive_values_and_provides_fallback_text()

### Community 118 - "Decisions"
Cohesion: 0.20
Nodes (9): Aria subagent shape, Current Aria Integration Points, Decisioning and actions, Decisions, Evaluation, Evidence and source access, Human approval and audit, Research: Dispute Resolution Subagent (+1 more)

### Community 119 - "InteractionSummary"
Cohesion: 0.33
Nodes (6): FollowUpAction, InteractionSummary, BaseModel, datetime, field_validator, Property 10: Interaction Summary Completeness

### Community 120 - "Research: AWS Service Icons in Architecture Diagram"
Cohesion: 0.33
Nodes (5): Alternatives Considered, Decision: Keep Service Cards and Connector Anchors, Decision: Use Draw.io Native AWS4 Resource Icons, Decision: Use Specific or Broad Icons Conservatively, Research: AWS Service Icons in Architecture Diagram

### Community 121 - "Tasks: AWS Service Icons in Architecture Diagram"
Cohesion: 0.40
Nodes (4): Dependencies & Execution Order, Implementation Strategy, Phase 1: User Story 1 - Recognize AWS Services at a Glance (Priority: P1), Tasks: AWS Service Icons in Architecture Diagram

### Community 122 - "Shared Framework Decisions"
Cohesion: 0.22
Nodes (9): Decision: Centralize cross-agent lifecycle behavior, not domain behavior, Decision: Do not mandate background threads or synchronous invocation, Decision: Keep context and memory strategy provider-compatible, Decision: Load configuration lazily and cache immutable settings, Decision: Standardize agent manifests with framework tuning separated, Decision: Use shared hooks for observability and safety, Decision: Use typed extension contracts, Evidence (+1 more)

### Community 123 - "Production Best Practices"
Cohesion: 0.25
Nodes (8): AgentCore Gateway, AgentCore Memory, AgentCore Runtime, Amazon Bedrock and Guardrails, Production Best Practices, Python engineering baseline, Strands context management, Strands state and structured output

### Community 124 - "Quickstart: KYC/AML Verification Subagent"
Cohesion: 0.40
Nodes (4): Local validation, Prerequisites, Quickstart: KYC/AML Verification Subagent, Walkthrough

### Community 126 - "Implementation Plan: Memory Context Contract Normalization"
Cohesion: 0.25
Nodes (8): Complexity Tracking, Constitution Check, Documentation (this feature), Implementation Plan: Memory Context Contract Normalization, Project Structure, Source Code (repository root), Summary, Technical Context

### Community 127 - "Data Models"
Cohesion: 0.04
Nodes (45): 1. Aria Agent Core (`aria/agent.py`), 1. External Service Failures (CRM, CBS), 2. Knowledge Base Fallback, 2. Tools, 3. Guardrail Configuration (`aria/guardrails/config.py`), 3. Guardrail Processing Errors, 4. Session Manager (`aria/session/manager.py`), 4. Session Recovery (+37 more)

### Community 128 - "Tasks: Memory Context Contract Normalization"
Cohesion: 0.25
Nodes (7): Dependencies and Execution Order, Implementation, Implementation Strategy, Phase 1: Setup, Phase 2: User Story 1 - Consistent Memory Context (Priority: P1), Tasks: Memory Context Contract Normalization, Tests

### Community 129 - "status"
Cohesion: 0.33
Nodes (6): get_demo_summary(), status(), EscalationTicket, MaturityEvent and OutflowEvent, Session, WorkflowState

### Community 130 - "test_api_and_events.py"
Cohesion: 0.23
Nodes (10): handle_event(), normalize_event(), process_event(), Any, handler(), Any, test_event_handler_passes_normalized_event_to_processor(), test_event_handler_routes_maturity_and_outflow_events() (+2 more)

### Community 131 - "Deployment"
Cohesion: 0.29
Nodes (6): Deployed components, Deployment, GitHub Actions deployment, Memory and observability policy, Required inputs, Synthesis

### Community 132 - "Quickstart: Memory Context Contract Normalization"
Cohesion: 0.40
Nodes (4): Focused Validation, Prerequisites, Quickstart: Memory Context Contract Normalization, Validation Results (2026-10-02)

### Community 134 - "get_risk_questionnaire"
Cohesion: 0.20
Nodes (9): get_risk_questionnaire(), Phase 3: User Story 1 - Personalized Client Profile (Priority: P1), AgentCore Gateway Lambda target, AgentCore Runtime invocation, Authenticated API Gateway request, Invocation Contracts, Strands to Gateway integration and tool scope, Phase 7: User Story 2 and 3 Follow-up - Runtime Routing, Safe Gateway Tools, and Artifact Compatibility (+1 more)

### Community 135 - "Contract: Statement Explainer Handoff and Activity Stream"
Cohesion: 0.33
Nodes (5): Aria parent-to-specialist handoff, Contract: Statement Explainer Handoff and Activity Stream, Local demo request, Server-Sent Events, Tool failures

### Community 136 - "Aria Statement Explainer Demo"
Cohesion: 0.40
Nodes (4): Aria Statement Explainer Demo, Review scenarios, Run, Tests

### Community 138 - "Research: Memory Context Contract Normalization"
Cohesion: 0.40
Nodes (4): Decision: A configured remote backend must own deletion, Decision: Preserve policy and provider boundaries, Decision: Use a narrow structural retrieval protocol for context assembly, Research: Memory Context Contract Normalization

## Knowledge Gaps
- **730 isolated node(s):** `state`, `elements`, `aria-ai-relationship-manager`, `User Input`, `Pre-Execution Checks` (+725 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1010 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AriaAgent` connect `AriaAgent` to `test_workflow_risk.py`, `statement_explainer/app.py`, `test_service_and_compliance.py`, `test_agentcore_adapters.py`, `GuardrailProcessor`, `KYCStatusProvider`, `aria/agentcore_entrypoint.py`, `test_statement_subagent.py`, `test_strands_runtime.py`, `Tasks`, `Observability`, `aria/agent.py`, `.__init__`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `Tasks: Aria AI Relationship Manager` connect `Tasks: Aria AI Relationship Manager` to `test_service_and_compliance.py`, `aria/agent.py`, `001-ai-relationship-manager/tasks.md`, `get_risk_questionnaire`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `SessionManager` connect `SessionManager` to `rest_handler.py`, `Tasks: Aria AI Relationship Manager`, `test_agentcore_adapters.py`, `test_persistence_and_observability.py`, `Tasks`, `test_rest_handler_accepts_verified_tenant_and_subject_claims`, `agentcore.py`, `AgentCoreRuntimeAdapter`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `AriaAgent` (e.g. with `StatementAnalysisRequest` and `GuardrailProcessor`) actually correct?**
  _`AriaAgent` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `GuardrailProcessor` (e.g. with `AriaAgent` and `Observability`) actually correct?**
  _`GuardrailProcessor` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `SessionManager` (e.g. with `AgentCoreRuntimeAdapter` and `Tasks`) actually correct?**
  _`SessionManager` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `ComplianceVerifier` (e.g. with `build_kyc_aml_subagent_tool()` and `AMLAssessment`) actually correct?**
  _`ComplianceVerifier` has 14 INFERRED edges - model-reasoned connections that need verification._