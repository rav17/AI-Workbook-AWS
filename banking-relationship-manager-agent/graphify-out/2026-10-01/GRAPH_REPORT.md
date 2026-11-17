# Graph Report - banking-relationship-manager-agent  (2026-10-01)

## Corpus Check
- 184 files · ~111,432 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 2, .kiro 1, .code-workspace 1)

## Summary
- 1509 nodes · 2259 edges · 117 communities (97 shown, 20 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 98 edges (avg confidence: 0.93)
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
- SessionManager
- GuardrailProcessor
- Tasks: [FEATURE NAME]
- .claude/skills/speckit-analyze/SKILL.md
- .github/skills/speckit-analyze/SKILL.md
- Correctness Properties
- User Scenarios & Testing
- StatefulStack
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
- Agent Framework
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
- Data Models
- aria-ai-relationship-manager
- test_agentcore_adapters.py
- Implementation Plan: Dispute Resolution Subagent
- Specification Quality Checklist: Aria AI Relationship Manager
- Data Model: Aria AI Relationship Manager
- Tasks: Aria AI Relationship Manager
- Deployment
- agent.py
- test_foundation.py
- MemoryStore
- Error Handling
- Design Document: Aria — AI Relationship Manager Agent
- test_persistence_and_observability.py
- Implementation Plan: Aria — AI Relationship Manager Agent
- 2. Tools
- agentcore.py
- AgentCoreGatewayAdapter
- AgentCoreMemoryDataPlaneClient
- Decisions
- Tasks: Production Readiness Remediation
- test_mmdsv2_custom_resource.py
- invoke_gateway_tool
- Data Model: Production Readiness Remediation
- Quickstart: Production Readiness Validation
- Components and Interfaces
- Invocation Contracts
- Tasks
- IdempotencyStore
- AriaAgent
- typing
- Implementation Plan: Virtual Account Receivables Exception Resolution Subagent
- test_service_and_compliance.py
- Data Model: Dispute Resolution
- Data Model: Receivables Exception Resolution
- knowledge_tool.py
- test_runtime_coordinator_loads_arn_from_ssm
- Tasks: Account Statement Explainer Subagent
- Tasks: Virtual Account Receivables Exception Resolution Subagent
- Tasks: Dispute Resolution Subagent
- Decisions
- test_framework_contracts.py
- Data Model: Account Statement Explainer
- IdempotencyConflict
- Contract: Receivables Investigation and Analyst Approval
- Contract: Statement Explainer Handoff and Activity Stream
- Quickstart: Account Statement Explainer Prototype
- Quickstart: Receivables Exception Resolution MVP
- Contract: Dispute Investigation and Human Review
- Quickstart: Dispute Resolution MVP
- test_idempotency_store_reclaims_expired_in_progress_claim

## God Nodes (most connected - your core abstractions)
1. `AriaAgent` - 45 edges
2. `SessionManager` - 34 edges
3. `GuardrailProcessor` - 28 edges
4. `IdempotencyStore` - 24 edges
5. `Tasks: Aria AI Relationship Manager` - 24 edges
6. `Observability` - 23 edges
7. `AgentCoreRuntimeAdapter` - 22 edges
8. `Tasks` - 22 edges
9. `Correctness Properties` - 21 edges
10. `StatefulStack` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Current Aria Integration Points` --references--> `RuntimeSessionCoordinator`  [INFERRED]
  specs/003-account-statement-explainer/research.md → aria/api/runtime_session.py
- `Property 10: Interaction Summary Completeness` --references--> `InteractionSummary`  [INFERRED]
  .kiro/specs/ai-relationship-manager/design.md → aria/models/interaction.py
- `Phase 12: User Story 14 - CRM and API Context (Priority: P1)` --references--> `SessionManager`  [INFERRED]
  specs/001-ai-relationship-manager/tasks.md → aria/session/manager.py
- `Phase 4: User Story 5 - Service Query Resolution (Priority: P1)` --references--> `query_product_info()`  [INFERRED]
  specs/001-ai-relationship-manager/tasks.md → aria/tools/knowledge_tool.py
- `StatePatch` --references--> `WorkflowState`  [INFERRED]
  specs/001-ai-relationship-manager/data-model.md → aria/workflow/state.py

## Import Cycles
- None detected.

## Communities (117 total, 20 thin omitted)

### Community 0 - "test_api_and_events.py"
Cohesion: 0.16
Nodes (22): handler(), invoke_agent(), make_response(), parse_body(), Any, handler(), _idempotency_key(), _is_authenticated() (+14 more)

### Community 1 - "test_workflow_risk.py"
Cohesion: 0.11
Nodes (24): assess_risk_appetite(), get_risk_questionnaire(), Any, PatchOperation, Any, StatePatch, WorkflowState, CDK deployment rules (+16 more)

### Community 2 - "aria/agentcore_entrypoint.py"
Cohesion: 0.10
Nodes (23): _build_strands_agent(), invoke(), main(), Any, resolve_runtime_identity(), _response_text(), run_runtime_invocation(), validate_runtime_payload() (+15 more)

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
Cohesion: 0.06
Nodes (32): AgentCore Gateway, AgentCore Memory, AgentCore Runtime, Amazon Bedrock and Guardrails, AWS CDK v2 Decisions, Decision: Centralize cross-agent lifecycle behavior, not domain behavior, Decision: Do not mandate background threads or synchronous invocation, Decision: Enforce boundaries through the supported API (+24 more)

### Community 7 - "SessionManager"
Cohesion: 0.10
Nodes (16): _build_session_id(), Any, Exception, SessionManager, Session, FakeRuntimeClient, test_runtime_adapter_reuses_and_recovers_runtime_session(), test_session_manager_rejects_duplicate_write_lock() (+8 more)

### Community 9 - "GuardrailProcessor"
Cohesion: 0.06
Nodes (38): GuardrailProcessor, GuardrailResult, Protect user input and output from sensitive credential leakage., Observability, Any, escalate_request(), Any, logging (+30 more)

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

### Community 15 - "StatefulStack"
Cohesion: 0.05
Nodes (60): Agent, App, argparse, build_strands_agent(), cancel_strands_agent(), Path, Build a Strands Agent without invoking the model during construction., Request cancellation through the installed Strands Agent API. (+52 more)

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

### Community 42 - "Agent Framework"
Cohesion: 0.29
Nodes (6): Agent Framework, AgentCore boundary, Core contracts, Local development and release evidence, Manifest schema, Supported assumptions

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

### Community 55 - "Data Models"
Cohesion: 0.20
Nodes (10): Client Profile, Data Models, Escalation Ticket, Interaction Summary, Knowledge Base Response, KYC Status, Maturity Event, Risk Assessment (+2 more)

### Community 65 - "test_agentcore_adapters.py"
Cohesion: 0.12
Nodes (10): io, FakeGatewayTransport, FakeMemoryClient, SemanticGatewayTransport, test_agentcore_memory_data_plane_scopes_retrieval_to_authenticated_tenant(), test_gateway_adapter_filters_discovered_tools_through_authorization(), test_gateway_adapter_semantic_discovery_applies_capability_and_backend_auth(), test_memory_adapter_bounds_provider_retrieval_and_preserves_tenant_scope() (+2 more)

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

### Community 72 - "Deployment"
Cohesion: 0.33
Nodes (5): Deployed components, Deployment, GitHub Actions deployment, Required inputs, Synthesis

### Community 73 - "agent.py"
Cohesion: 0.19
Nodes (17): get_client_profile(), _build_reinvestment_options(), check_upcoming_maturities(), detect_large_outflows(), evaluate_maturity_event(), evaluate_outflow_event(), Any, given (+9 more)

### Community 74 - "test_foundation.py"
Cohesion: 0.11
Nodes (20): get_settings(), Settings, ClientProfile, BaseModel, BaseModel, RiskProfile, BaseSettings, CI/CD Integration (+12 more)

### Community 75 - "MemoryStore"
Cohesion: 0.18
Nodes (11): AgentCoreMemoryAdapter, Applies tenant and retrieval bounds around an AgentCore Memory client., ContextBuilder, Any, MemoryEntry, MemoryStore, test_memory_adapter_supports_tenant_scoped_delete_and_retention(), test_context_builder_exposes_memory_without_overriding_current_state() (+3 more)

### Community 76 - "Error Handling"
Cohesion: 0.22
Nodes (9): 1. External Service Failures (CRM, CBS), 2. Knowledge Base Fallback, 3. Guardrail Processing Errors, 4. Session Recovery, Error Categories and Strategies, Error Handling, Error Handling Patterns, Error Response Templates (+1 more)

### Community 77 - "Design Document: Aria — AI Relationship Manager Agent"
Cohesion: 0.25
Nodes (7): Architecture, Design Document: Aria — AI Relationship Manager Agent, High-Level Architecture, Key Design Decisions, Overview, Request Flow, Technology Stack

### Community 79 - "test_persistence_and_observability.py"
Cohesion: 0.10
Nodes (10): Any, StateStore, test_idempotency_store_persists_claims_across_instances_and_releases_for_retry(), test_observability_redacts_and_records_context_metadata(), test_observability_redacts_nested_sensitive_values_and_secret_text(), test_session_manager_supports_revision_and_retries(), test_state_store_applies_idempotent_update_and_runs_side_effect_once(), test_state_store_rejects_duplicate_after_restart_with_dynamodb_idempotency() (+2 more)

### Community 80 - "Implementation Plan: Aria — AI Relationship Manager Agent"
Cohesion: 0.40
Nodes (4): Implementation Plan: Aria — AI Relationship Manager Agent, Notes, Overview, Task Dependency Graph

### Community 81 - "2. Tools"
Cohesion: 0.29
Nodes (7): 2. Tools, Compliance Tool (`aria/tools/compliance_tool.py`), CRM Tool (`aria/tools/crm_tool.py`), Escalation Tool (`aria/tools/escalation_tool.py`), Knowledge Base Tool (`aria/tools/knowledge_tool.py`), Maturity and Retention Tool (`aria/tools/maturity_tool.py`), Risk Assessment Tool (`aria/tools/risk_tool.py`)

### Community 82 - "agentcore.py"
Cohesion: 0.13
Nodes (11): GatewayTransport, MemoryClient, PayloadParser, PreInvocationGuard, PromptBuilder, Any, ToolFilter, dataclasses (+3 more)

### Community 83 - "AgentCoreGatewayAdapter"
Cohesion: 0.27
Nodes (5): AgentCoreGatewayAdapter, AgentCoreRuntimeClient, Any, Invokes an IAM-authorized Runtime with a backend-verified principal., Separates Gateway discovery/tool visibility from authorization.

### Community 84 - "AgentCoreMemoryDataPlaneClient"
Cohesion: 0.27
Nodes (4): AgentCoreMemoryDataPlaneClient, Tenant-bound boto3 client for documented AgentCore Memory data-plane APIs., test_agentcore_memory_data_plane_requires_record_id_for_delete(), test_agentcore_memory_data_plane_writes_tenant_variable_and_rejects_other_tenant()

### Community 85 - "Decisions"
Cohesion: 0.18
Nodes (10): API and Runtime identity, Artifact and release pipeline, Compatibility, Decisions, Gateway Lambda event, KYC source and failures, Memory namespaces/data API, Research: Production Readiness Remediation (+2 more)

### Community 86 - "Tasks: Production Readiness Remediation"
Cohesion: 0.18
Nodes (10): Dependencies and Execution Order, Implementation Strategy, Parallel Opportunities, Phase 1: Setup, Phase 2: Foundational Tests, Phase 3: User Story 1 - Trusted Client Access (Priority: P1), Phase 4: User Story 2 - Deployable and Constrained AWS Artifacts (Priority: P1), Phase 5: User Story 3 - Safe Stateful Agent Execution (Priority: P1) (+2 more)

### Community 87 - "test_mmdsv2_custom_resource.py"
Cohesion: 0.31
Nodes (5): boto3, handler(), test_mmdsv2_custom_resource_delete_is_noop(), test_mmdsv2_custom_resource_preserves_runtime_artifact_and_role(), types

### Community 88 - "invoke_gateway_tool"
Cohesion: 0.32
Nodes (5): handler(), invoke_gateway_tool(), Any, test_gateway_lambda_adapter_allows_only_published_tools(), test_gateway_lambda_uses_agentcore_tool_name_from_lambda_context()

### Community 89 - "Data Model: Production Readiness Remediation"
Cohesion: 0.29
Nodes (6): ConversationState, Data Model: Production Readiness Remediation, IdempotencyRecord, MemoryRecord, ReleaseEvidence, VerifiedPrincipal

### Community 90 - "Quickstart: Production Readiness Validation"
Cohesion: 0.29
Nodes (6): Artifact and full CI checks, Execution Record, Local focused checks, Prerequisites, Quickstart: Production Readiness Validation, Sandbox verification

### Community 91 - "Components and Interfaces"
Cohesion: 0.40
Nodes (5): 1. Aria Agent Core (`aria/agent.py`), 3. Guardrail Configuration (`aria/guardrails/config.py`), 4. Session Manager (`aria/session/manager.py`), 5. Event Handler (`aria/events/handler.py`), Components and Interfaces

### Community 92 - "Invocation Contracts"
Cohesion: 0.40
Nodes (4): AgentCore Gateway Lambda target, AgentCore Runtime invocation, Authenticated API Gateway request, Invocation Contracts

### Community 93 - "Tasks"
Cohesion: 0.11
Nodes (22): FollowUpAction, InteractionSummary, BaseModel, MaturityEvent, OutflowEvent, ReinvestmentOption, ConsolidationOpportunity, Any (+14 more)

### Community 94 - "IdempotencyStore"
Cohesion: 0.15
Nodes (15): _build_runtime_coordinator(), RuntimeSessionBusy, RuntimeSessionCoordinator, AgentCoreRuntimeAdapter, Maps an authenticated conversation to one recoverable Runtime session., RuntimeSession, RuntimeClient, IdempotencyStore (+7 more)

### Community 95 - "AriaAgent"
Cohesion: 0.15
Nodes (11): AriaAgent, Any, test_agent_greets_and_requests_risk_for_market_inquiry(), test_agent_registers_and_dispatches_core_tools(), test_agent_response_is_personalized_empathetic_and_actionable(), test_agent_suggests_family_ctg_for_eligible_accounts(), test_maturity_tool_flags_30_day_maturity(), test_recommend_products_by_risk_profile() (+3 more)

### Community 96 - "typing"
Cohesion: 0.27
Nodes (10): handle_event(), normalize_event(), process_event(), Any, handler(), Any, test_event_handler_passes_normalized_event_to_processor(), test_event_handler_routes_maturity_and_outflow_events() (+2 more)

### Community 97 - "Implementation Plan: Virtual Account Receivables Exception Resolution Subagent"
Cohesion: 0.07
Nodes (26): Financial Safety and Governance, Notes, Requirements and Evaluation, Scope and Aria Fit, Specification Quality Checklist: Virtual Account Receivables Exception Resolution, Complexity Tracking, Constitution Check, Documentation (this feature) (+18 more)

### Community 98 - "test_service_and_compliance.py"
Cohesion: 0.13
Nodes (19): check_kyc_status(), flag_aml_activity(), Any, decimal, Property 15: AML Threshold Flagging, parametrize, Phase 8: User Story 9 - Regulatory Compliance (Priority: P1), test_agent_escalates_unresolved_service_query_with_client_context() (+11 more)

### Community 99 - "Data Model: Dispute Resolution"
Cohesion: 0.16
Nodes (9): Exception, Data Model: Dispute Resolution, DisputeAuditEvent, DisputeCase, DisputeEvidence, DisputeFinding, DisputePolicy, DisputeRecommendation (+1 more)

### Community 100 - "Data Model: Receivables Exception Resolution"
Cohesion: 0.17
Nodes (11): AnalystDecision, ApprovedPolicy, CaseTask, Data Model: Receivables Exception Resolution, InvestigationRecommendation, InvoiceCandidate, MatchingDecision, ReceivablesAuditEvent (+3 more)

### Community 101 - "knowledge_tool.py"
Cohesion: 0.42
Nodes (10): answer_service_query(), extract_source_date(), format_citation(), _normalized_terms(), ProductAnswer, Any, query_product_info(), _score_match() (+2 more)

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

### Community 107 - "test_framework_contracts.py"
Cohesion: 0.31
Nodes (5): ParsedTurn, GatewayClient, Any, test_gateway_client_filters_tools_by_scope(), test_parsed_turn_tracks_session_and_payload()

### Community 108 - "Data Model: Account Statement Explainer"
Cohesion: 0.22
Nodes (8): AgentActivityEvent, Data Model: Account Statement Explainer, StatementAnalysisRequest, StatementAuditRecord, StatementDataset, StatementExplainerSession, StatementToolResult, StatementTransaction

### Community 109 - "IdempotencyConflict"
Cohesion: 0.38
Nodes (5): IdempotencyConflict, Any, RuntimeError, test_duplicate_idempotency_key_returns_conflict(), duplicate_handler()

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

## Knowledge Gaps
- **637 isolated node(s):** `aria-ai-relationship-manager`, `User Input`, `Pre-Execution Checks`, `Goal`, `Operating Constraints` (+632 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 812 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SessionManager` connect `SessionManager` to `test_agentcore_adapters.py`, `Tasks: Aria AI Relationship Manager`, `test_persistence_and_observability.py`, `agentcore.py`, `Tasks`, `IdempotencyStore`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `AriaAgent` connect `AriaAgent` to `test_workflow_risk.py`, `aria/agentcore_entrypoint.py`, `test_service_and_compliance.py`, `agent.py`, `GuardrailProcessor`, `StatefulStack`, `invoke_gateway_tool`, `Tasks`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `Tasks: Aria AI Relationship Manager` connect `Tasks: Aria AI Relationship Manager` to `test_workflow_risk.py`, `test_service_and_compliance.py`, `Tasks`, `001-ai-relationship-manager/tasks.md`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `AriaAgent` (e.g. with `GuardrailProcessor` and `Observability`) actually correct?**
  _`AriaAgent` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `SessionManager` (e.g. with `AgentCoreRuntimeAdapter` and `Tasks`) actually correct?**
  _`SessionManager` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `GuardrailProcessor` (e.g. with `AriaAgent` and `Observability`) actually correct?**
  _`GuardrailProcessor` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `IdempotencyStore` (e.g. with `_build_runtime_coordinator()` and `RuntimeSessionCoordinator`) actually correct?**
  _`IdempotencyStore` has 3 INFERRED edges - model-reasoned connections that need verification._