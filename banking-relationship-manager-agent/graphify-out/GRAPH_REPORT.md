# Graph Report - baking-relationship-manager-agent  (2026-09-18)

## Corpus Check
- 130 files · ~75,452 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .kiro 1, .code-workspace 1)

## Summary
- 892 nodes · 1123 edges · 68 communities (50 shown, 18 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2bf4a2bc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AriaAgent
- Data Models
- agentcore.py
- Data Model: Aria AI Relationship Manager
- test_framework_contracts.py
- Requirements
- Research: Aria AI Relationship Manager
- Tasks: Aria AI Relationship Manager
- FrameworkRunner
- test_foundation.py
- Tasks: [FEATURE NAME]
- .claude/skills/speckit-analyze/SKILL.md
- .github/skills/speckit-analyze/SKILL.md
- Correctness Properties
- User Scenarios & Testing
- test_security.py
- Execution Steps
- Execution Steps
- common.ps1
- Feature Specification: [FEATURE NAME]
- test_agent_manifest.py
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
- aria-ai-relationship-manager

## God Nodes (most connected - your core abstractions)
1. `Tasks: Aria AI Relationship Manager` - 24 edges
2. `SessionManager` - 22 edges
3. `Correctness Properties` - 21 edges
4. `AriaAgent` - 20 edges
5. `Data Model: Aria AI Relationship Manager` - 17 edges
6. `Requirements` - 15 edges
7. `User Scenarios & Testing` - 15 edges
8. `Tasks` - 13 edges
9. `Tasks: [FEATURE NAME]` - 13 edges
10. `invoke_agent()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `StatePatch` --references--> `WorkflowState`  [INFERRED]
  specs/001-ai-relationship-manager/data-model.md → aria/workflow/state.py
- `Design Summary` --references--> `AriaAgent`  [INFERRED]
  specs/001-ai-relationship-manager/plan.md → aria/agent.py
- `Property-Based Testing` --references--> `ClientProfile`  [INFERRED]
  .kiro/specs/ai-relationship-manager/design.md → aria/models/client.py
- `Tasks` --references--> `ClientProfile`  [INFERRED]
  .kiro/specs/ai-relationship-manager/tasks.md → aria/models/client.py
- `Tasks` --references--> `RiskProfile`  [INFERRED]
  .kiro/specs/ai-relationship-manager/tasks.md → aria/models/risk.py

## Import Cycles
- None detected.

## Communities (68 total, 18 thin omitted)

### Community 0 - "AriaAgent"
Cohesion: 0.06
Nodes (44): AriaAgent, main(), invoke_agent(), make_response(), parse_body(), Any, handler(), Any (+36 more)

### Community 1 - "Data Models"
Cohesion: 0.04
Nodes (45): 1. Aria Agent Core (`aria/agent.py`), 1. External Service Failures (CRM, CBS), 2. Knowledge Base Fallback, 2. Tools, 3. Guardrail Configuration (`aria/guardrails/config.py`), 3. Guardrail Processing Errors, 4. Session Manager (`aria/session/manager.py`), 4. Session Recovery (+37 more)

### Community 2 - "agentcore.py"
Cohesion: 0.06
Nodes (24): AgentCoreGatewayAdapter, AgentCoreMemoryAdapter, AgentCoreRuntimeAdapter, Any, Maps an authenticated conversation to one recoverable Runtime session., Applies tenant and retrieval bounds around an AgentCore Memory client., Separates Gateway discovery/tool visibility from authorization., RuntimeSession (+16 more)

### Community 3 - "Data Model: Aria AI Relationship Manager"
Cohesion: 0.05
Nodes (35): Content Quality, Feature Readiness, Infrastructure Readiness, Notes, Production AI Application Readiness, Requirement Completeness, Shared Agent Framework Readiness, Specification Quality Checklist: Aria AI Relationship Manager (+27 more)

### Community 4 - "test_framework_contracts.py"
Cohesion: 0.12
Nodes (17): FrameworkConfig, load_framework_config(), Any, ContextBuilder, ParsedTurn, GatewayClient, Any, MemoryEntry (+9 more)

### Community 5 - "Requirements"
Cohesion: 0.06
Nodes (32): Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria, Acceptance Criteria (+24 more)

### Community 6 - "Research: Aria AI Relationship Manager"
Cohesion: 0.06
Nodes (32): AgentCore Gateway, AgentCore Memory, AgentCore Runtime, Amazon Bedrock and Guardrails, AWS CDK v2 Decisions, Decision: Centralize cross-agent lifecycle behavior, not domain behavior, Decision: Do not mandate background threads or synchronous invocation, Decision: Enforce boundaries through the supported API (+24 more)

### Community 7 - "Tasks: Aria AI Relationship Manager"
Cohesion: 0.05
Nodes (32): IdempotencyStore, StateStore, _build_session_id(), SessionManager, Dependencies and Execution Order, MVP Scope, Parallel Opportunities, Phase 10: User Story 12 - Prompt Injection Defense (Priority: P1) (+24 more)

### Community 8 - "FrameworkRunner"
Cohesion: 0.30
Nodes (5): FrameworkRunner, Any, asyncio, test_framework_runner_cleanup_runs_in_finally_block(), test_framework_runner_supports_sync_and_async_modes()

### Community 9 - "test_foundation.py"
Cohesion: 0.08
Nodes (23): get_settings(), Settings, GuardrailProcessor, Protect user input and output from sensitive credential leakage., ClientProfile, BaseModel, BaseModel, RiskProfile (+15 more)

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
Cohesion: 0.07
Nodes (39): check_kyc_status(), flag_aml_activity(), answer_service_query(), ProductAnswer, Any, query_product_info(), StatePatch, WorkflowState (+31 more)

### Community 14 - "User Scenarios & Testing"
Cohesion: 0.09
Nodes (22): Assumptions, Edge Cases, Feature Specification: Aria AI Relationship Manager, Functional Requirements, Key Entities, Requirements, Success Criteria, User Scenarios & Testing (+14 more)

### Community 15 - "test_security.py"
Cohesion: 0.15
Nodes (15): App, aws_cdk, build_app(), Any, StatefulStack, test_non_dev_app_requires_permissions_boundary(), test_non_dev_stateful_stack_retains_resources_and_enables_termination_protection(), test_stateful_stack_synthesizes_without_unsupported_security_configuration() (+7 more)

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

### Community 20 - "test_agent_manifest.py"
Cohesion: 0.24
Nodes (6): build_system_prompt(), main(), pathlib, test_system_prompt_builds_nonempty_prompt(), test_smoke_agent_entrypoint_runs_and_returns_state(), yaml

### Community 21 - "WorkflowValidator"
Cohesion: 0.27
Nodes (6): WorkflowResult, WorkflowValidator, test_validator_rejects_locked_field_updates(), test_workflow_result_records_patch_outcome(), test_validator_allows_valid_profile_update(), test_validator_blocks_invalid_payload()

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
Cohesion: 0.54
Nodes (4): WorkflowDependencyGraph, next_step_after_change(), test_dependency_graph_tracks_transitive_invalidations(), test_next_step_selects_earliest_affected_step()

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
Nodes (6): Agent Framework, AgentCore boundary, Core contracts, Local development boundary, Manifest schema, Supported assumptions

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

## Knowledge Gaps
- **429 isolated node(s):** `aria-ai-relationship-manager`, `User Input`, `Pre-Execution Checks`, `Goal`, `Operating Constraints` (+424 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 523 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SessionManager` connect `Tasks: Aria AI Relationship Manager` to `AriaAgent`, `agentcore.py`?**
  _High betweenness centrality (0.080) - this node is a cross-community bridge._
- **Why does `Tasks: Aria AI Relationship Manager` connect `Tasks: Aria AI Relationship Manager` to `AriaAgent`, `Data Model: Aria AI Relationship Manager`, `Correctness Properties`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `Tasks` connect `AriaAgent` to `test_foundation.py`, `Correctness Properties`, `Tasks: Aria AI Relationship Manager`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `SessionManager` (e.g. with `AgentCoreRuntimeAdapter` and `Tasks`) actually correct?**
  _`SessionManager` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `AriaAgent` (e.g. with `Tasks` and `Design Summary`) actually correct?**
  _`AriaAgent` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `aria-ai-relationship-manager`, `User Input`, `Pre-Execution Checks` to the rest of the system?**
  _429 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `AriaAgent` be split into smaller, more focused modules?**
  _Cohesion score 0.061955965181771634 - nodes in this community are weakly interconnected._