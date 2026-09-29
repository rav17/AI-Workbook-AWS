# Implementation Plan: implement-prompts

## Overview

Three parallel implementation tracks:

1. **Agent Framework** — build `src/agentic_ai/agent_framework/` from scratch (10 modules + per-agent directories for 3 existing agents).
2. **CDK Best Practices** — add CDK Nag, SSM cross-stack refs, content-hash staging, resource discovery, and CDK unit tests.
3. **CI/CD** — reusable composite action, OIDC scoping, concurrency, change detection, stuck-stack recovery, and a dedicated prod workflow.

Each task builds on its predecessors. Optional test sub-tasks are marked `*`. Property test tasks reference the property numbers from the design document.

---

## Tasks

- [ ] 1. Create agent_framework package scaffold
  - Create `src/agentic_ai/agent_framework/__init__.py` as an empty file (exports filled in Task 11)
  - Create stub files for all 10 modules with only the module-level docstring and `from __future__ import annotations`: `hooks.py`, `config.py`, `mcp_factory.py`, `memory_manager.py`, `prompt_assembler.py`, `model_builder.py`, `turn_runner.py`, `observability.py`, `runner.py`
  - Create `tests/unit/agent_framework/__init__.py` and `tests/property/agent_framework/__init__.py`
  - Add `agent_framework` to `[tool.setuptools.packages.find]` include list in `pyproject.toml`
  - _Requirements: 1.5_

  - [ ] 1.1 Create package directory structure and stub modules
    - Create all directories and `__init__.py` files listed above
    - Verify `pip install -e .` succeeds after the change
    - _Requirements: 1.5_

- [ ] 2. Implement hooks.py — ParsedTurn and Protocols
  - [ ] 2.1 Implement `ParsedTurn` dataclass and five Protocol classes
    - Write `ParsedTurn` dataclass with fields: `workflow_id: str`, `session_id: str`, `user_prompt: str`, `dynamic_context: str`, `raw_event: dict[str, Any]`
    - Write five `@runtime_checkable` Protocol classes: `SystemPromptBuilder`, `SkillsBuilder`, `ToolFilter`, `PayloadParser`, `PreInvokeGuard` with exact signatures from design doc
    - Define `DYNAMIC_CONTEXT_MARKER = "<!-- DYNAMIC_CONTEXT -->"` constant
    - Implement `DefaultPayloadParser` that extracts generic fields from a raw event dict
    - Implement `PassthroughToolFilter` that returns the tools list unchanged
    - Use `from __future__ import annotations`, full type hints, Google docstrings, ruff-compliant formatting
    - _Requirements: 1.1, 1.6_

  - [ ]* 2.2 Write unit tests for hooks.py
    - `tests/unit/agent_framework/test_hooks.py`
    - Test that `ParsedTurn` can be constructed and fields are accessible
    - Test that `DefaultPayloadParser.parse()` returns a valid `ParsedTurn`
    - Test that `PassthroughToolFilter.filter_tools()` returns the same list
    - Test that all five Protocol classes are `@runtime_checkable` (use `isinstance`)
    - _Requirements: 1.1_

- [ ] 3. Implement config.py — FrameworkConfig
  - [ ] 3.1 Implement `FrameworkConfig` frozen dataclass and factory
    - Write `FrameworkConfig(frozen=True)` dataclass with all 13 fields from design doc (including defaults for `stm_k=4`, `temperature=0.2`, etc.)
    - Write `ConfigLoadError(Exception)` with message that includes SSM path but never the value
    - Write `_get_ssm(client, path, max_attempts=2, timeout=5)` helper with retry logic and explicit boto3 timeout
    - Write `get_framework_config() -> FrameworkConfig` with `@functools.lru_cache(maxsize=1)` that reads SSM and env vars
    - Factory reads env vars: `AIOPS_ENVIRONMENT`, `AGENTCORE_GATEWAY_ID`, `AGENTCORE_MEMORY_ID`, `DYNAMODB_WORKFLOW_TABLE`, `AWS_REGION`
    - Use `JsonFormatter` structured logging for all log statements
    - _Requirements: 1.2, 1.3, 1.4, 18.2, 18.3_

  - [ ]* 3.2 Write unit tests for config.py
    - `tests/unit/agent_framework/test_config.py`
    - Test that `FrameworkConfig` is immutable (attempt mutation raises `FrozenInstanceError`)
    - Test that `get_framework_config()` returns the same object on repeated calls (cache hit)
    - Test that `ConfigLoadError` message contains SSM path
    - Mock `boto3.client` and `os.environ` for all tests
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ]* 3.3 Write property tests for config.py
    - `tests/property/agent_framework/test_props_config.py`
    - **Property 2: FrameworkConfig immutability — any attempt to set a field on a constructed `FrameworkConfig` raises `FrozenInstanceError` for all valid field values**
    - **Property 3: ConfigLoadError path hygiene — the error message always contains the SSM path string and never contains the SSM value string, for all (path, value) pairs**
    - **Validates: Requirements 1.2, 1.3, 1.4**
    - _Requirements: 1.2, 1.3, 1.4_

- [ ] 4. Implement mcp_factory.py — SigV4Auth and MCP Client
  - [ ] 4.1 Implement `SigV4HttpxAuth` and `create_mcp_client()`
    - Implement `SigV4HttpxAuth(httpx.Auth)` using `botocore.auth.SigV4Auth` to sign `httpx.Request` objects in `auth_flow()`
    - Implement `create_mcp_client(cfg: FrameworkConfig) -> MCPClient` that returns a configured, not-yet-started client pointing at the AgentCore Gateway
    - Add module-level docstring stating `SigV4HttpxAuth` MUST NOT be imported outside this module
    - Use full type hints and Google docstrings
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 4.2 Write unit tests for mcp_factory.py
    - `tests/unit/agent_framework/test_mcp_factory.py`
    - Test that `create_mcp_client()` returns an object with `start`, `stop`, and `list_tools` attributes
    - Test that `SigV4HttpxAuth.auth_flow()` yields a request with an `Authorization` header
    - Mock `botocore.auth.SigV4Auth` and `boto3.Session` for all tests
    - _Requirements: 2.1, 2.2_

- [ ] 5. Implement memory_manager.py — STM/LTM
  - [ ] 5.1 Implement `load_memory()` and `flush_memory()`
    - Implement `load_memory(cfg, session_id, actor_id) -> tuple[list, str]` using `ThreadPoolExecutor(max_workers=2)` to run STM (`MemoryClient.list_events()`) and LTM (`MemoryClient.retrieve_records()`) concurrently
    - Enforce `stm_events = stm_events[:cfg.stm_k]` cap unconditionally after fetching
    - Skip LTM retrieval (return empty string) when `cfg.ltm_enabled is False`
    - Implement `flush_memory(cfg, session_id, actor_id, messages) -> None` that strips `DYNAMIC_CONTEXT_MARKER` and `<system>...</system>` blocks from each message before calling `MemoryClient.create_event()`
    - Import `DYNAMIC_CONTEXT_MARKER` from `hooks.py`; never redefine it
    - Add explicit timeouts on all `MemoryClient` calls; log `WARNING` on any failure but do not re-raise from `flush_memory`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 18.3_

  - [ ]* 5.2 Write unit tests for memory_manager.py
    - `tests/unit/agent_framework/test_memory_manager.py`
    - Test that `load_memory()` caps STM at `stm_k` regardless of how many events the mock returns
    - Test that `load_memory()` returns empty LTM string when `cfg.ltm_enabled is False`
    - Test that `flush_memory()` removes `DYNAMIC_CONTEXT_MARKER` from message content
    - Test that `flush_memory()` strips `<system>...</system>` blocks
    - Mock `MemoryClient` for all tests
    - _Requirements: 3.1, 3.2, 3.4_

  - [ ]* 5.3 Write property tests for memory_manager.py
    - `tests/property/agent_framework/test_props_config.py` (append to existing file)
    - **Property 1: STM cap invariant — for any list of events of arbitrary length N and any `stm_k` in [1, 20], `load_memory()` returns exactly `min(N, stm_k)` events**
    - **Validates: Requirements 3.2**
    - _Requirements: 3.2_

- [ ] 6. Implement prompt_assembler.py — Cache-Point Injection
  - [ ] 6.1 Implement `assemble_system_prompt()`
    - Implement `assemble_system_prompt(raw_prompt, ltm_summary, stm_events, dynamic_context) -> list[dict] | str`
    - When `DYNAMIC_CONTEXT_MARKER` is present: split `raw_prompt` at the marker, return 3-element list: `[{"text": static_prefix}, {"cachePoint": {"type": "default"}}, {"text": dynamic_suffix}]` where `dynamic_suffix` concatenates LTM summary, formatted STM turns, and `dynamic_context`
    - When `DYNAMIC_CONTEXT_MARKER` is absent: log `WARNING` via `JsonFormatter` and return `raw_prompt` as a plain string
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 6.2 Write unit tests for prompt_assembler.py
    - `tests/unit/agent_framework/test_prompt_assembler.py`
    - Test that output is a 3-element list when marker is present
    - Test that the second element is `{"cachePoint": {"type": "default"}}`
    - Test that output is a plain string when marker is absent
    - Test that LTM summary, STM events, and dynamic_context all appear in the dynamic part
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 6.3 Write property tests for prompt_assembler.py
    - `tests/property/agent_framework/test_props_prompt.py`
    - **Property 5: Cache-point presence — for any `raw_prompt` containing `DYNAMIC_CONTEXT_MARKER`, the returned list always has exactly 3 elements with the middle element equal to `{"cachePoint": {"type": "default"}}`**
    - **Property 6: Static/dynamic split correctness — the static text in element 0 equals the substring of `raw_prompt` before `DYNAMIC_CONTEXT_MARKER` for all valid inputs**
    - **Validates: Requirements 4.2**
    - _Requirements: 4.2_

- [ ] 7. Implement model_builder.py — BedrockModel
  - [ ] 7.1 Implement `build_model()`
    - Implement `build_model(cfg: FrameworkConfig) -> BedrockModel`
    - Always set `cache_tools="default"` and `cache_config=CacheConfig(strategy="auto")` — these are not configurable
    - Always set `retry_strategy=ModelRetryStrategy(retry_max_attempts=cfg.retry_max_attempts, initial_delay=10, max_delay=60)`
    - Pass `model_id=cfg.model_id` and `temperature=cfg.temperature` from config
    - Add module docstring explaining that `cache_tools` and `CacheConfig` are intentionally hardcoded and not configurable by agents
    - _Requirements: 4.4, 4.5_

  - [ ]* 7.2 Write unit tests for model_builder.py
    - `tests/unit/agent_framework/test_model_builder.py`
    - Test that returned `BedrockModel` always has `cache_tools="default"` regardless of config values
    - Test that `model_id` and `temperature` are passed from config
    - Test that `retry_max_attempts` from config is forwarded to `ModelRetryStrategy`
    - Mock `strands.BedrockModel` for all tests
    - _Requirements: 4.4, 4.5_

  - [ ]* 7.3 Write property tests for model_builder.py
    - `tests/property/agent_framework/test_props_model_builder.py`
    - **Property 4: Cache enforcement — for all valid `FrameworkConfig` values, `build_model()` always returns a `BedrockModel` constructed with `cache_tools="default"` and `CacheConfig(strategy="auto")`**
    - **Validates: Requirements 4.4**
    - _Requirements: 4.4_

- [ ] 8. Implement observability.py — EMF Metrics
  - [ ] 8.1 Implement `ObservabilityTrace` and metric emission functions
    - Implement `ObservabilityTrace` dataclass with fields: `agent_name: str`, `session_id: str`, `workflow_id: str`, `turn_start_ns: int = field(default_factory=time.monotonic_ns)`
    - Implement `emit_token_usage(trace, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens) -> None` — print EMF JSON to stdout with namespace `AIOps/{environment}`, dimensions `agent_name` and `session_id`; include `EstimatedCostUsd` when `INPUT_TOKEN_COST_USD` and `OUTPUT_TOKEN_COST_USD` env vars are set
    - Implement `emit_turn_latency(trace: ObservabilityTrace) -> None` — compute `(time.monotonic_ns() - trace.turn_start_ns) / 1_000_000` and emit as `TurnLatencyMs` metric
    - Implement `log_cache_hit_rate(trace, cache_read_tokens, cache_write_tokens) -> None` — log `WARNING` via `JsonFormatter` when `cache_read_tokens == 0`
    - _Requirements: 5.5, 5.6, 5.7_

  - [ ]* 8.2 Write unit tests for observability.py
    - `tests/unit/agent_framework/test_observability.py`
    - Test that `emit_token_usage()` prints valid EMF JSON with all four token fields
    - Test that `emit_turn_latency()` emits a non-negative `TurnLatencyMs` value
    - Test that `log_cache_hit_rate()` logs a WARNING when `cache_read_tokens == 0`
    - Test that `log_cache_hit_rate()` does NOT log a WARNING when `cache_read_tokens > 0`
    - _Requirements: 5.5, 5.6, 5.7_

  - [ ]* 8.3 Write property tests for observability.py
    - `tests/property/agent_framework/test_props_observability.py`
    - **Property 9: EMF namespace correctness — for any `ObservabilityTrace` and any non-negative token counts, the emitted JSON always contains a `_aws.CloudWatchMetrics[0].Namespace` matching `AIOps/{environment}`**
    - **Validates: Requirements 5.6**
    - _Requirements: 5.6_

- [ ] 9. Implement turn_runner.py — DynamoDB Turn Lock
  - [ ] 9.1 Implement `run_turn()` with DynamoDB lock
    - Implement `run_turn(cfg, workflow_id, turn_fn, async_turns=True) -> dict`
    - Acquire lock via `dynamodb.put_item()` with `ConditionExpression="attribute_not_exists(workflow_id)"` and `ttl = int(time.time()) + 120`
    - On `ConditionalCheckFailedException`: return `{"status": "ack", "body": "turn already in progress"}` immediately without calling `turn_fn`
    - When `async_turns=True`: start `threading.Thread(target=_run_async, daemon=True)` where `_run_async` calls `asyncio.run(turn_fn())`; return ACK immediately
    - When `async_turns=False`: call `asyncio.run(turn_fn())` directly and return its result
    - Release lock in `finally` block via `dynamodb.delete_item()` — swallow any `ResourceNotFoundException` in the finally cleanup
    - Use `cfg.dynamodb_workflow_table` for table name; add explicit `connect_timeout=5`, `read_timeout=5` to boto3 client
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 18.3_

  - [ ]* 9.2 Write unit tests for turn_runner.py
    - `tests/unit/agent_framework/test_turn_runner.py`
    - Test that `ConditionalCheckFailedException` causes immediate ACK return without calling `turn_fn`
    - Test that the lock is released in the `finally` block even when `turn_fn` raises
    - Test that `async_turns=False` calls `turn_fn` and returns its result synchronously
    - Mock `boto3.client("dynamodb")` for all tests
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 9.3 Write property tests for turn_runner.py
    - `tests/property/agent_framework/test_props_turn_runner.py`
    - **Property 7: Lock-release guarantee — for any turn_fn that either returns normally, raises an exception, or is interrupted, the DynamoDB `delete_item` call is always made exactly once**
    - **Property 8: Idempotent ACK — when `ConditionalCheckFailedException` is raised, `run_turn()` always returns a dict with `status == "ack"` regardless of the workflow_id value**
    - **Validates: Requirements 5.2, 5.4**
    - _Requirements: 5.1, 5.2, 5.4_

- [ ] 10. Implement runner.py — 22-step run_agent() orchestrator
  - [ ] 10.1 Implement `run_agent()` with the full 22-step lifecycle
    - Implement `run_agent(raw_event, system_prompt_builder, payload_parser=None, tool_filter=None, skills_builder=None, pre_invoke_guard=None) -> dict`
    - On entry, validate all non-None hooks via `isinstance(hook, Protocol)` using `@runtime_checkable` checks; raise `TypeError` with the hook name on failure
    - Execute all 22 steps in exact order from the design doc:
      1. `pre_invoke_guard.check()` — if returns non-None, return that dict immediately
      2. `payload_parser.parse(raw_event)` → `ParsedTurn` (use `DefaultPayloadParser` if None)
      3. `config.get_framework_config()` → `cfg`
      4. Load and cache `agent.yaml` `framework:` section using `functools.lru_cache`
      5. `model_builder.build_model(cfg)` → `BedrockModel`
      6. `mcp_factory.create_mcp_client(cfg)` → `mcp_client`
      7. `await mcp_client.start(); tools = await mcp_client.list_tools()`
      8. `tool_filter.filter_tools(tools, turn)` (use `PassthroughToolFilter` if None)
      9. `memory_manager.load_memory(cfg, session_id, actor_id)` → `(stm_events, ltm_summary)`
      10. `system_prompt_builder.build_system_prompt(turn, cfg)` → `raw_prompt`
      11. `prompt_assembler.assemble_system_prompt(raw_prompt, ltm_summary, stm_events, dynamic_context)` → `system_prompt`
      12. `skills_builder.build_skills(turn, cfg)` if provided → `skills`
      13. Construct `strands.Agent(model, system_prompt, tools, skills)`
      14. `result = agent(turn.user_prompt)` (synchronous, NOT `await agent.arun()`)
      15. `memory_manager.flush_memory(...)` [finally]
      16. `MemoryClient.create_event(turn messages)` [finally]
      17. `observability.emit_token_usage(trace, ...)`
      18. `observability.emit_turn_latency(trace)`
      19. `observability.log_cache_hit_rate(trace, ...)`
      20. `await mcp_client.stop()` [finally]
      21. Log INFO with `stop_reason` [finally]
      22. Release turn lock [finally]
    - Implement `max_tokens` soft-fail: when `result.stop_reason == "max_tokens"` and `cfg.soft_fail_on_max_tokens is True`, return `{"status": "ok", "body": "token budget exhausted"}`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 10.2 Write unit tests for runner.py
    - `tests/unit/agent_framework/test_runner.py`
    - Test that `TypeError` is raised at startup when a non-Protocol hook is passed
    - Test that `pre_invoke_guard` returning a non-None dict short-circuits and returns that dict
    - Test that `stop_reason == "max_tokens"` with `soft_fail_on_max_tokens=True` returns the soft-fail response
    - Test that steps 15, 20, 21, 22 (finally steps) are called even when step 14 raises
    - Mock all framework sub-modules; use `unittest.mock.patch` on imports
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.6_

  - [ ]* 10.3 Write property tests for runner.py
    - `tests/property/agent_framework/test_props_runner.py`
    - **Property 10: Finally-block guarantee — for any combination of steps that raise exceptions before step 14, the finally-block steps (15, 20, 21, 22) are always invoked exactly once**
    - **Property 11: Hook type safety — for any object that does not implement the expected Protocol, `run_agent()` raises `TypeError` before executing any turn logic**
    - **Validates: Requirements 6.2, 6.6**
    - _Requirements: 6.2, 6.6_

- [ ] 11. Checkpoint — all agent framework unit + property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Update __init__.py — Public API exports
  - [ ] 12.1 Wire public exports and add import-policy test
    - Update `src/agentic_ai/agent_framework/__init__.py` to export: `run_agent`, `ParsedTurn`, `SystemPromptBuilder`, `SkillsBuilder`, `ToolFilter`, `PayloadParser`, `PreInvokeGuard`, `DYNAMIC_CONTEXT_MARKER`
    - Add `__all__` list containing exactly those 8 names
    - Create `tests/unit/agent_framework/test_import_policy.py` that uses the `ast` module to scan all `.py` files under `src/agentic_ai/agents/` and fails with a descriptive `AssertionError` if `SigV4HttpxAuth` is imported or referenced anywhere outside `mcp_factory.py`
    - _Requirements: 1.5, 2.3, 7.5_

- [ ] 13. Create correlator agent directory
  - [ ] 13.1 Create `src/agentic_ai/agents/correlator/` scaffold
    - Create `src/agentic_ai/agents/correlator/__init__.py` (empty)
    - Create `src/agentic_ai/agents/correlator/agent.yaml` with `name: correlator`, `description:` field, and `framework:` section with all 8 tuning fields set to their defaults
    - Create `src/agentic_ai/agents/correlator/system_prompt.py` with `from agentic_ai.agent_framework import DYNAMIC_CONTEXT_MARKER`, a `_STATIC_PREFIX` string containing the agent's stable instructions, and `def build_system_prompt(turn, cfg) -> str:` that returns `_STATIC_PREFIX + DYNAMIC_CONTEXT_MARKER`
    - Create `src/agentic_ai/agents/correlator/agentcore_entrypoint.py` (≤ 20 lines) importing `BedrockAgentCoreApp`, `run_agent`, and `build_system_prompt`, then registering `@app.entrypoint` that calls `run_agent(raw_event=payload, system_prompt_builder=build_system_prompt)`
    - Do NOT modify the existing `correlator.py` business logic file
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 14. Create model_router agent directory
  - [ ] 14.1 Create `src/agentic_ai/agents/model_router/` scaffold
    - Same structure as Task 13 for the `model_router` agent
    - `agent.yaml`: `name: model_router`, appropriate `description:`
    - `system_prompt.py`: stable model-routing instructions before `DYNAMIC_CONTEXT_MARKER`
    - `agentcore_entrypoint.py`: ≤ 20 lines, delegates to `run_agent()`
    - Do NOT modify the existing `model_router.py` business logic file
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 15. Create reasoning_agent agent directory
  - [ ] 15.1 Create `src/agentic_ai/agents/reasoning_agent/` scaffold
    - Same structure as Task 13 for the `reasoning_agent` agent
    - `agent.yaml`: `name: reasoning_agent`, appropriate `description:`
    - `system_prompt.py`: stable reasoning instructions before `DYNAMIC_CONTEXT_MARKER`
    - `agentcore_entrypoint.py`: ≤ 20 lines, delegates to `run_agent()`
    - Do NOT modify the existing `reasoning_agent.py` business logic file
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 16. Add pyproject.toml dependencies for agent framework
  - [ ] 16.1 Pin new dependencies in pyproject.toml
    - Add `[project.optional-dependencies]` section `agentcore` with pinned exact versions (`==`): `bedrock-agentcore`, `strands-agents`, `httpx`, `botocore`
    - Add `cdk-nag==2.28.196` (or latest stable at time of implementation) to the `cdk` extras list
    - Verify `pip install -e ".[agentcore,cdk]"` succeeds with no version conflicts
    - _Requirements: 8.1, 18.1_

- [ ] 17. Create nag_suppressions.py
  - [ ] 17.1 Implement `apply_common_suppressions()` helper
    - Create `src/agentic_ai/infra/nag_suppressions.py`
    - Implement `apply_common_suppressions(stack: cdk.Stack) -> None` using `NagSuppressions.add_stack_suppressions()`
    - Include at minimum the `AwsSolutions-IAM5` suppressions for Bedrock `foundation-model/*` and `logs:CreateLogGroup` — each with a full `reason=` string explaining why it is acceptable
    - Every suppression dict MUST have a non-empty `reason` key (enforced by Task 20 property test)
    - _Requirements: 8.2, 8.3_

  - [ ]* 17.2 Write property test for nag_suppressions.py
    - `tests/property/infra/test_props_nag.py`
    - **Property 20: Suppression reason enforcement — parse `nag_suppressions.py` as AST and assert that every dict literal passed to `NagSuppressions.add_stack_suppressions()` or `add_resource_suppressions()` contains a `"reason"` key with a non-empty string value**
    - **Validates: Requirements 8.3**
    - _Requirements: 8.3_

- [ ] 18. Add CDK Nag to app.py
  - [ ] 18.1 Integrate `AwsSolutionsChecks` into `app.py`
    - Add `from cdk_nag import AwsSolutionsChecks` import to `src/agentic_ai/infra/app.py`
    - Add `from .nag_suppressions import apply_common_suppressions` import
    - After all stack instantiations but before `app.synth()`, add `cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))`
    - Call `apply_common_suppressions(stack)` for each of the six stacks in a loop
    - Verify `cdk synth --context environment=dev` (with all required context values) produces zero unresolved violations
    - _Requirements: 8.1, 8.4_

- [ ] 19. Migrate cross-stack references to SSM
  - [ ] 19.1 Add SSM writes in data_stack.py and observability_stack.py
    - In `data_stack.py`: add `ssm.StringParameter` writes immediately after creating the DynamoDB workflow table and SQS main queue, using paths `/aiops/{environment}/workflow-table-arn` and `/aiops/{environment}/main-queue-arn`
    - In `observability_stack.py`: write log group ARNs to SSM under `/aiops/{environment}/`
    - In `monitoring_stack.py`: write any shared ARNs to SSM
    - Import `aws_cdk.aws_ssm as ssm` in each affected stack file
    - _Requirements: 9.1_

  - [ ] 19.2 Replace constructor ARN params with SSM reads in compute_stack.py
    - In `compute_stack.py`: replace any constructor-passed ARN parameters (previously from `data_stack`) with `ssm.StringParameter.value_for_string_parameter()` calls using the same SSM paths written in 19.1
    - Verify no `Fn::ImportValue` exists in the synthesised template by running `cdk synth` and grepping the JSON output
    - _Requirements: 9.2, 9.3_

- [ ] 20. Implement staging.py — Content-Hash Packaging
  - [ ] 20.1 Implement `stage_resource_code()` and `_compute_hash()`
    - Create `src/agentic_ai/infra/staging.py`
    - Implement `_compute_hash(source_dir: Path) -> str` — SHA-256 over sorted `.py`, `.txt`, `.json` files, return first 12 hex chars
    - Implement `stage_resource_code(source_dir, resource_name, build_root=None) -> Path`:
      - Compute hash; if `.build/{name}-{hash12}/` exists, return it immediately
      - Otherwise: `shutil.copytree` + conditional `subprocess.check_call(["pip", "install", "-r", ...])` when `requirements.txt` exists
    - Add `.build/` to `.gitignore` if not already present
    - Raise `ValueError` when `source_dir` does not exist or has no stageable files
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

  - [ ]* 20.2 Write unit tests for staging.py
    - `tests/unit/infra/test_staging.py`
    - Use `tmp_path` pytest fixture to create real temp directories
    - Test cache hit: calling `stage_resource_code()` twice on same source returns same path without re-running pip
    - Test cache miss: modifying a `.py` file produces a different hash and a new build directory
    - Test `ValueError` on empty or nonexistent source directory
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ]* 20.3 Write property tests for staging.py
    - `tests/property/infra/test_props_staging.py`
    - **Property 12: Hash determinism — for any set of file contents, `_compute_hash()` always returns the same 12-character hex string regardless of iteration order**
    - **Validates: Requirements 11.1**
    - _Requirements: 11.1_

- [ ] 21. Implement resource_discovery.py
  - [ ] 21.1 Implement `discover_resources()` with validation
    - Create `src/agentic_ai/infra/resource_discovery.py`
    - Implement `discover_resources(resources_root: Path | None = None) -> dict[str, dict]` that scans `src/resources/*/resource.yaml`
    - Validate directory name against `^[a-z][a-z0-9_]*$`; raise `ValueError` with offending path if it fails
    - Validate that each `resource.yaml` contains both `type` and `description` fields; raise `ValueError` with offending path if either is missing
    - Return validated dict keyed by resource name
    - Create placeholder `src/resources/.gitkeep` (empty file in the resources directory)
    - Add `RESOURCE_TYPE_REGISTRY: dict[str, type[cdk.Stack]]` stub dict to `app.py` and wire in the `discover_resources()` call with the `add_dependency()` chain
    - _Requirements: 12.3, 12.4, 12.5_

  - [ ]* 21.2 Write unit tests for resource_discovery.py
    - `tests/unit/infra/test_resource_discovery.py`
    - Test that valid resource directories are discovered and returned
    - Test that invalid name patterns raise `ValueError` with the offending path in the message
    - Test that missing `type` field raises `ValueError`
    - Test that missing `description` field raises `ValueError`
    - Use `tmp_path` fixture for all file-system interactions
    - _Requirements: 12.3, 12.4_

  - [ ]* 21.3 Write property tests for resource_discovery.py
    - `tests/property/infra/test_props_discovery.py`
    - **Property 13: Name validation completeness — for any string that does not match `^[a-z][a-z0-9_]*$`, `discover_resources()` raises `ValueError` containing the offending directory path**
    - **Validates: Requirements 12.4**
    - _Requirements: 12.4_

- [ ] 22. CDK unit tests — conftest + network + data stacks
  - [ ] 22.1 Create CDK test fixtures and first two stack tests
    - Create `tests/cdk/__init__.py`
    - Create `tests/cdk/conftest.py` with a shared `test_context` pytest fixture providing a valid `CdkContext` with `environment="dev"`, fake account `"123456789012"`, fake region `"us-east-1"`, and all other required fields
    - Create `tests/cdk/test_network_stack.py`:
      - Snapshot test capturing full synthesised template
      - Assert VPC flow logs are enabled
      - Assert CloudWatch log group has a non-zero `RetentionInDays`
    - Create `tests/cdk/test_data_stack.py`:
      - Snapshot test
      - Assert DynamoDB table has `SSESpecification.SSEEnabled: true`
      - Assert SQS queue has `SqsManagedSseEnabled: true` or `KmsMasterKeyId` set
    - _Requirements: 10.1, 10.2, 10.3_

- [ ] 23. CDK unit tests — remaining stacks
  - [ ] 23.1 Create tests for compute, observability, monitoring, and simulation stacks
    - Create `tests/cdk/test_compute_stack.py`:
      - Snapshot test
      - Assert all Lambda functions have `KmsKeyArn` set
      - Assert all Lambda log groups have a non-zero `RetentionInDays`
    - Create `tests/cdk/test_observability_stack.py`:
      - Snapshot test
      - Assert at least one CloudWatch Alarm resource exists in the template
    - Create `tests/cdk/test_monitoring_stack.py`:
      - Snapshot test
    - Create `tests/cdk/test_simulation_stack.py`:
      - Snapshot test
      - Assert `TerminationProtection` is `false` on the stack
    - Run `pytest -m cdk` and fix any failures before closing this task
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ] 24. Checkpoint — CDK synth and CDK tests pass
  - Ensure `cdk synth --context environment=dev` succeeds with zero nag violations, and `pytest -m cdk` passes with zero failures. Ask the user if questions arise.

- [ ] 25. Create .github/actions/setup-cdk/action.yml
  - [ ] 25.1 Implement composite setup action
    - Create `.github/actions/setup-cdk/action.yml`
    - Define `inputs.install-cdk-python-deps` with `default: 'true'`
    - Steps in order:
      1. `uses: actions/setup-python@v5` with `python-version: '3.11'`
      2. `uses: actions/setup-node@v4` with `node-version: '24'`
      3. `run: npm install -g aws-cdk@2.160.0`
      4. `run: cdk --version` (verification step)
      5. `if: inputs.install-cdk-python-deps == 'true'` → `run: pip install -e ".[dev,cdk]"`
    - Pin all action versions at `@v5` / `@v4` as appropriate
    - _Requirements: 13.1, 13.2, 13.3_

- [ ] 26. Refactor ci.yml — OIDC scoping + concurrency + composite action + cdk-diff
  - [ ] 26.1 Apply security and reliability improvements to ci.yml
    - Remove `id-token: write` from workflow-level `permissions` block; add it only to the `ecr-scan-push` job's permissions
    - Replace inline Python/Node/CDK setup steps in `lint`, `unit-tests`, `property-tests`, `cdk-synth`, and `cdk-tests` jobs with `uses: ./.github/actions/setup-cdk` (where Node/CDK are not needed, pass `install-cdk-python-deps: 'false'` and use the action only for Python setup, or keep setup-python inline for lint-only jobs)
    - Add `concurrency: {group: "${{ github.workflow }}-<jobname>-${{ github.ref }}", cancel-in-progress: true}` to `lint`, `unit-tests`, `property-tests`, `cdk-synth`, and `cdk-tests` jobs
    - Add `timeout-minutes: 15` to `lint`, `unit-tests`, and `property-tests` jobs; `timeout-minutes: 20` to `docker-build`
    - Add `--lookups false` flag to the `cdk synth` command in the `cdk-synth` job
    - Bump `NODE_VERSION` env var from `"20"` to `"24"`
    - Add new `cdk-diff` job:
      - `if: github.event_name == 'pull_request'`
      - `needs: [unit-tests, property-tests]`
      - `permissions: id-token: write, contents: read, pull-requests: write`
      - Steps: `uses: ./.github/actions/setup-cdk`, configure OIDC with read-only role, `cdk diff --all --context environment=dev --lookups false`, post diff output as PR comment via `actions/github-script@v8`
    - _Requirements: 13.3, 14.1, 14.2, 15.4, 17.5_

- [ ] 27. Create .github/workflows/cleanup-stuck-stack.yml
  - [ ] 27.1 Implement stuck-stack recovery workflow
    - Create `.github/workflows/cleanup-stuck-stack.yml` with `on: workflow_call` trigger
    - Inputs: `environment` (type: string, required), `action` (type: string, required, description: "preflight|remediate")
    - For each of the six stacks `[Network, Data, Compute, Observability, Monitoring, Simulation]`:
      - Query stack status via `aws cloudformation describe-stacks --stack-name Aiops-{env}-{Stack}`
      - `ROLLBACK_COMPLETE` or `CREATE_FAILED` → `aws cloudformation delete-stack` + `aws cloudformation wait stack-delete-complete`
      - `ROLLBACK_FAILED` or `DELETE_FAILED` → `aws cloudformation delete-stack --retain-resources` (best-effort)
      - Any `*_IN_PROGRESS` state → `exit 1` with message "Another deployment is in progress for {stack}"
      - `*_COMPLETE` or stack `NOT_FOUND` → skip with info log
    - Job must have `timeout-minutes: 30`
    - _Requirements: 16.1, 16.2, 16.3, 16.4_

  - [ ]* 27.2 Write property tests for cleanup-stuck-stack logic
    - Extract the stack-status → action mapping as a pure Python function in `scripts/cfn_cleanup.py`
    - `tests/property/cicd/test_props_cleanup_stack.py`
    - **Property 16: IN_PROGRESS always exits with error — for any stack name and any status matching `*_IN_PROGRESS`, the cleanup function raises or returns an error indicator**
    - **Property 17: Safe states are always skipped — for any status in `{CREATE_COMPLETE, UPDATE_COMPLETE, NOT_FOUND}`, the cleanup function returns a skip indicator without calling delete**
    - **Validates: Requirements 16.2, 16.3, 16.4**
    - _Requirements: 16.2, 16.4_

- [ ] 28. Refactor cd.yml — detect-changes + resolve-env + OIDC + concurrency + rollback + SHA-gap + secrets-check + post-verify
  - [ ] 28.1 Add `detect-changes` and `resolve-env` jobs
    - Add `workflow_dispatch.inputs.commit_sha` (type: string, required: false, description: "Commit SHA for rollback deployment")
    - Remove `id-token: write` from workflow-level permissions; it will be added per-job below
    - Add `detect-changes` job (runs only when `github.event_name != 'workflow_dispatch'`):
      - Step: `git diff --name-only ${{ github.event.before }} HEAD` captured to variable
      - When `github.event.before` is all-zeros (force-push): set `force_all=true` output
      - Map changed paths to boolean outputs: `network_changed`, `data_changed`, `compute_changed`, `observability_changed`, `monitoring_changed`, `simulation_changed`, `force_all`, `any_change`
    - Add `resolve-env` job (non-PR only):
      - Map `refs/heads/main` → `dev`, `refs/heads/staging` → `staging`, `refs/tags/v*.*.*` → `prod`
      - Output: `env_name`, `is_rollback` (true when `inputs.commit_sha` is set)
    - _Requirements: 15.1, 15.2, 15.3, 17.1_

  - [ ] 28.2 Add OIDC per-job, concurrency, timeouts, auto-preflight, SHA-gap, secrets-check, and post-verify
    - Add `id-token: write` only to the individual deploy jobs that call `configure-aws-credentials`
    - Replace inline Python/Node/CDK setup in all deploy jobs with `uses: ./.github/actions/setup-cdk`
    - Add `concurrency: {group: "deploy-${{ needs.resolve-env.outputs.env_name }}", cancel-in-progress: false}` to all deploy jobs
    - Add `timeout-minutes: 90` to all deploy jobs
    - Add `auto-preflight` job (runs only when `env_name == 'dev'`): calls `uses: ./.github/workflows/cleanup-stuck-stack.yml` with `action: preflight`
    - Add SHA-gap detection step at the start of the first deploy job: compare `github.event.before` to the last-deployed SHA stored in GitHub Actions environment variable `LAST_DEPLOYED_SHA_{ENV}`; if gap, log warning and set `FORCE_ALL=true` in the step env
    - Add Secrets Manager pre-flight step before first `cdk deploy`: run `aws secretsmanager describe-secret` for each required secret; fail with descriptive message if any secret is missing or inaccessible
    - Add post-deploy stack state verification step after the last `cdk deploy`: query `aws cloudformation describe-stacks` for each deployed stack and assert status is `*_COMPLETE`; fail and surface stack name + status if any is in error state
    - Update `LAST_DEPLOYED_SHA_{ENV}` GitHub Actions environment variable after a successful full deploy
    - Add `--lookups false` to all `cdk synth` and `cdk diff` commands
    - _Requirements: 14.1, 14.3, 14.4, 15.1, 15.2, 17.1, 17.2, 17.3, 17.4, 17.5_

- [ ] 29. Create .github/workflows/prod-deploy.yml
  - [ ] 29.1 Implement dedicated production workflow
    - Create `.github/workflows/prod-deploy.yml`
    - Triggers: `pull_request` with types `[closed]` filtered to `release/**` → `main` merges (`if: github.event.pull_request.merged == true`), plus `workflow_dispatch` with optional `commit_sha` input
    - Workflow-level permissions: `contents: read` only
    - Jobs in order:
      1. `validate` — run `pytest -m unit -m property` (uses composite action, no AWS)
      2. `cdk-test` — run `pytest -m cdk` (uses composite action, no AWS)
      3. `prod-approval` — uses GitHub Environment `prod` (manual approval gate with required reviewers)
      4. `deploy` — `id-token: write` at job level; checkout at `inputs.commit_sha` if provided; `uses: ./.github/actions/setup-cdk`; Secrets Manager pre-flight; `cdk synth --lookups false --context environment=prod`; `cdk deploy --all --require-approval never --context environment=prod`; post-deploy stack state verification; update `LAST_DEPLOYED_SHA_PROD`
      5. `upload-cdk-out-artifact` — upload `cdk.out/` with `retention-days: 365`
    - Add `timeout-minutes: 90` to the `deploy` job
    - Add `concurrency: {group: "deploy-prod", cancel-in-progress: false}`
    - _Requirements: 16.5, 16.6, 16.7, 17.1, 17.2, 17.3, 17.4, 17.5_

- [ ] 30. Property tests for CI/CD helper scripts
  - [ ] 30.1 Extract and test pure-function CI/CD logic
    - Create `scripts/detect_changes.py` with a pure Python function `map_changed_files_to_stacks(changed_files: list[str]) -> dict[str, bool]` that replicates the detect-changes path mapping logic (returns dict with one bool per stack plus `force_all` and `any_change`)
    - Create `scripts/sha_gap.py` with a pure Python function `detect_sha_gap(before_sha: str, last_deployed_sha: str) -> bool` (returns True when `before_sha` is all-zeros or differs from `last_deployed_sha`)
    - Create `scripts/post_deploy_verify.py` with a pure Python function `check_stack_states(stack_statuses: dict[str, str]) -> list[str]` that returns a list of stack names not in a `*_COMPLETE` state
    - Create `scripts/resolve_env.py` with a pure Python function `resolve_env(ref: str) -> str` mapping branch/tag patterns to environment names
    - _Requirements: 15.1, 15.2, 15.3, 17.2, 17.4_

  - [ ]* 30.2 Write property tests for CI/CD scripts
    - `tests/property/cicd/test_props_detect_changes.py`
      - **Property 14: Stack flag completeness — for any list of changed file paths, `map_changed_files_to_stacks()` always returns a dict with exactly the expected boolean keys**
      - **Property 15: Branch→env mapping exhaustiveness — for any string matching `refs/heads/main`, `refs/heads/staging`, or `refs/tags/v*.*.*`, `resolve_env()` returns the correct environment string**
    - `tests/property/cicd/test_props_sha_gap.py`
      - **Property 18: Zero-SHA always triggers gap — for any `last_deployed_sha`, when `before_sha` is 40 zeros, `detect_sha_gap()` always returns True**
    - `tests/property/cicd/test_props_post_deploy.py`
      - **Property 19: Non-COMPLETE always fails — for any stack name and any status not ending in `_COMPLETE`, `check_stack_states()` includes that stack name in the returned failure list**
    - **Validates: Requirements 15.1, 15.2, 17.2, 17.4**
    - _Requirements: 15.1, 15.2, 17.2, 17.4_

- [ ] 31. Final checkpoint — all tests pass, cdk synth clean
  - Ensure `pytest -m unit`, `pytest -m property`, `pytest -m cdk` all pass with zero failures, `ruff check .` reports zero errors, and `cdk synth --context environment=dev` succeeds with zero nag violations. Ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All Python must pass `ruff check` and `ruff format --check` with zero violations before merging
- All new public functions need Google-style docstrings and full type annotations
- External service calls (SSM, DynamoDB, MemoryClient, Bedrock) need explicit timeouts, retries, and structured exception handling — never bare `except:`
- Use `JsonFormatter` for all logging; include `incident_id` in log records where an incident context is available
- All new dependencies pinned with `==` exact versions in `pyproject.toml`
- The `SigV4HttpxAuth` import-policy test (Task 12) runs as part of the unit test suite and will catch violations automatically in CI
- CDK stacks must never use `Fn::ImportValue` — verify via `grep -r "ImportValue" cdk.out/` after synth
- `.build/` directory must be in `.gitignore`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "16.1"] },
    { "id": 1, "tasks": ["2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "3.3", "4.1"] },
    { "id": 3, "tasks": ["4.2", "5.1", "6.1", "7.1", "8.1", "9.1"] },
    { "id": 4, "tasks": ["5.2", "5.3", "6.2", "6.3", "7.2", "7.3", "8.2", "8.3", "9.2", "9.3"] },
    { "id": 5, "tasks": ["10.1"] },
    { "id": 6, "tasks": ["10.2", "10.3"] },
    { "id": 7, "tasks": ["12.1"] },
    { "id": 8, "tasks": ["13.1", "14.1", "15.1"] },
    { "id": 9, "tasks": ["17.1", "18.1", "19.1", "20.1", "21.1", "25.1"] },
    { "id": 10, "tasks": ["17.2", "19.2", "20.2", "20.3", "21.2", "21.3"] },
    { "id": 11, "tasks": ["22.1"] },
    { "id": 12, "tasks": ["23.1"] },
    { "id": 13, "tasks": ["26.1", "27.1"] },
    { "id": 14, "tasks": ["27.2", "28.1"] },
    { "id": 15, "tasks": ["28.2", "29.1"] },
    { "id": 16, "tasks": ["30.1"] },
    { "id": 17, "tasks": ["30.2"] }
  ]
}
```
