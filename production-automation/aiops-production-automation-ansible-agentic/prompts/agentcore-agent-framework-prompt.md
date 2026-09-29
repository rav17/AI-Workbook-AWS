# AgentCore + Strands Agent Framework — Reusable Implementation Prompt

Paste this prompt into Claude Code in any new project that uses AWS AgentCore Runtime and
the Strands Agents SDK. It implements a shared agent framework so every agent entrypoint is
~15 lines instead of 1,000–3,000 lines, and all best practices are enforced by code, not
by convention. Built from lessons learned in a production multi-agent system.

---

```
I want to implement a shared agent application framework for AWS AgentCore Runtime + Strands
Agents SDK so that:
- Every agent entrypoint is ~15 lines (imports + one function call)
- All infrastructure boilerplate lives in one shared location
- Best practices for prompt engineering, memory, caching, and observability are enforced by
  the framework and cannot be accidentally skipped
- Adding a new agent requires only creating a directory with YAML + Python files — no changes
  to the framework or CDK

Read all existing code in this project first to understand the naming conventions, SSM prefix,
shared resource names (EventBridge bus, DynamoDB tables, SNS topic), and import paths before
writing anything.

---

## 1. Framework Directory to Create

src/<shared_root>/agent_framework/
  __init__.py         # Public API: export run_agent() and all hook Protocols
  hooks.py            # Protocol (ABC) definitions — the contract for every agent-specific hook
  config.py           # FrameworkConfig dataclass — lazy SSM + env loading, cached
  mcp_factory.py      # SigV4HttpxAuth class + create_mcp_client() — auth lives here only
  memory_manager.py   # load_memory() + flush_memory() — all AgentCore Memory I/O
  prompt_assembler.py # assemble_system_prompt() — Bedrock cache point injection
  model_builder.py    # build_model() — BedrockModel + retry strategy, caching always on
  turn_runner.py      # run_turn() — async thread, turn lock admission, ACK response
  observability.py    # ObservabilityTrace class, token usage EMF metrics, latency, cache rate
  runner.py           # run_agent() — the only function developers call

Adapt <shared_root> to match the existing project's source layout (e.g. shared/, common/).

---

## 2. hooks.py — All Protocol Definitions

Implement these exact Protocols and the ParsedTurn dataclass:

  from typing import Protocol, runtime_checkable, Any
  from dataclasses import dataclass, field

  @dataclass
  class ParsedTurn:
      user_prompt: str                          # Text sent as user message to the agent
      team_id: str                              # Adapt field names to this project's domain
      workflow_id: str
      action: str
      session_id: str                           # Unique per conversation thread
      dynamic_context: dict[str, Any] = field(default_factory=dict)
                                                # Injected after Bedrock cache point

  @runtime_checkable
  class SystemPromptBuilder(Protocol):
      """Required. Called once per turn. Returns the full system prompt string."""
      def __call__(self, **ctx: Any) -> str: ...

  @runtime_checkable
  class SkillsBuilder(Protocol):
      """Optional. Returns Strands Skill list for current + next workflow stage."""
      def __call__(self, current_stage: str | None, next_stage: str | None,
                   payload: dict) -> list: ...

  @runtime_checkable
  class ToolFilter(Protocol):
      """Optional. Receives all MCP-discovered tools; returns the filtered subset."""
      def __call__(self, all_tools: list, payload: dict,
                   current_stage: str | None) -> list: ...

  @runtime_checkable
  class PayloadParser(Protocol):
      """Optional. Converts the raw AgentCore event dict into a ParsedTurn."""
      def __call__(self, raw_payload: dict) -> ParsedTurn: ...

  @runtime_checkable
  class PreInvokeGuard(Protocol):
      """Optional. Runs before any agent work. Return error dict to abort, None to proceed."""
      def __call__(self, payload: dict) -> dict | None: ...

Only SystemPromptBuilder is required. Provide default implementations for ToolFilter
(pass all tools unchanged) and PayloadParser (generic field extraction).

---

## 3. config.py — FrameworkConfig

  @dataclass(frozen=True)
  class FrameworkConfig:
      # Model
      model_id: str                    # SSM: <ssm_prefix>/MODEL_ID
      max_tokens: int                  # SSM: <ssm_prefix>/MAX_TOKENS, default 4096
      model_region: str                # env: MODEL_REGION, default us-east-1
      context_window_tokens: int       # constant: 200_000

      # AgentCore connectivity
      gateway_id: str                  # env: AGENTCORE_GATEWAY_ID
      memory_id: str                   # env: AGENTCORE_MEMORY_ID
      memory_region: str               # env: AGENTCORE_MEMORY_REGION

      # DynamoDB — adapt table names to this project
      dynamodb_workflow_table: str     # env: DYNAMODB_WORKFLOW_TABLE
      dynamodb_conversation_table: str # env: DYNAMODB_CONVERSATION_TABLE

      # Feature flags
      emit_span_metrics: bool          # env: EMIT_SPAN_METRICS, default True
      raw_stm_replay_enabled: bool     # env: RAW_STM_REPLAY_ENABLED, default False

      # Bedrock cost tracking (None if env var absent — do not fail)
      input_price_per_million: float | None    # env: MODEL_INPUT_PRICE_PER_MILLION_TOKENS
      output_price_per_million: float | None   # env: MODEL_OUTPUT_PRICE_PER_MILLION_TOKENS
      cache_read_price_per_million: float | None
      cache_write_price_per_million: float | None

CRITICAL: Load lazily — wrap in @functools.lru_cache(maxsize=1). Never call at module import
time. First call happens inside @app.entrypoint, after AgentCore has resolved env vars and SSM
is reachable. SSM failures at import time will silently kill the runtime process.

---

## 4. mcp_factory.py — Gateway Authentication

Implement SigV4HttpxAuth (httpx.Auth subclass) that signs requests with AWS credentials using
botocore.auth.SigV4Auth. This class must live ONLY in mcp_factory.py — never copy it into
individual agent entrypoints.

  class SigV4HttpxAuth(httpx.Auth):
      """Signs httpx requests for AgentCore Gateway MCP endpoint."""

  def create_mcp_client(cfg: FrameworkConfig) -> MCPClient:
      """Returns a configured (not yet started) MCPClient for the Gateway."""

Callers must call mcp_client.start() before list_tools_sync() and mcp_client.stop() in a
finally block.

---

## 5. memory_manager.py — AgentCore Memory I/O

  def load_memory(
      cfg: FrameworkConfig,
      actor_id: str,
      session_id: str,
      ltm_namespace: str,
      stm_k: int = 4,
      ltm_enabled: bool = True,
  ) -> tuple[list, str]:
      """
      Fetches STM (last stm_k turns) and LTM summary. Run STM + LTM fetches concurrently.
      Returns (stm_messages, ltm_summary_text).
      """

  def flush_memory(
      cfg: FrameworkConfig,
      actor_id: str,
      session_id: str,
      agent_messages: list,
      dynamic_context_marker: str,
  ) -> None:
      """
      Strips DYNAMIC_CONTEXT_MARKER and any system-prompt markers from agent_messages,
      then writes the filtered turn to AgentCore Memory via MemoryClient.create_event().
      Must be called in a finally block — never skip on error.
      """

NEVER use AgentCore SessionManager hook — it injects the full unbounded STM and grows tokens
every turn. Always use manual MemoryClient with stm_k cap.

---

## 6. prompt_assembler.py — Bedrock Cache Point Injection

  def assemble_system_prompt(
      raw_prompt: str,
      dynamic_context_marker: str,
      ltm_summary: str,
      stm_messages: list,
      dynamic_context: dict,
  ) -> str | list:
      """
      If dynamic_context_marker found in raw_prompt:
        Returns [{"text": static_part},
                 {"cachePoint": {"type": "default"}},
                 {"text": dynamic_part + LTM + STM + dynamic_context}]
      If marker absent: logs a WARNING and returns raw_prompt as a plain string.
      Memory injection order (most authoritative last = closest to model):
        LTM summary → STM turns → dynamic_context (current turn state)
      """

The static part (before the marker) is cached by Bedrock — reduces cost by ~90% on repeated
invocations. The dynamic part (after the marker) is never cached — always fresh. Never move
the marker placement.

Each agent's system_prompt.py must define:
  DYNAMIC_CONTEXT_MARKER = "=== DYNAMIC CONTEXT (NOT CACHED) ==="
  def build_system_prompt(**ctx) -> str: ...   # includes the marker string

---

## 7. model_builder.py — BedrockModel Construction

  def build_model(
      cfg: FrameworkConfig,
      temperature: float = 0.0,
      retry_max_attempts: int = 3,
  ) -> tuple[BedrockModel, ModelRetryStrategy]:
      """
      Always sets: cache_tools='default', CacheConfig(strategy='auto').
      Always returns a ModelRetryStrategy (initial_delay=10, max_delay=60).
      Never creates a BedrockModel without caching enabled.
      """

temperature=0 is the default (deterministic outputs). Agents may override via agent.yaml.
retry_max_attempts is per-agent configurable (some agents need 4, not 3).

---

## 8. turn_runner.py — Async Turn Management

  def run_turn(
      app: BedrockAgentCoreApp,
      invoke_impl: Callable[[dict, Any], dict],
      payload: dict,
      context: Any,
      cfg: FrameworkConfig,
      async_turns: bool = True,
  ) -> dict:
      """
      1. Calls add_async_task_or_refuse() — acquires DynamoDB turn lock.
         If duplicate turn: returns ACK immediately (no work done).
      2. If async_turns=True: spawns daemon thread that calls asyncio.run(invoke_impl(...)).
         Returns ACK dict immediately so AgentCore does not time out.
      3. If async_turns=False: calls invoke_impl() directly, returns result.
      4. In thread finally: releases turn lock + emits turn completion EventBridge event.
         These two steps ALWAYS run, even on exception or crash.
      """

Turn lock prevents two concurrent agent turns for the same workflow_id. TTL = 120 seconds.
Background thread must create its own asyncio event loop (asyncio.run()) — never reuse the
entrypoint loop.

---

## 9. observability.py — Standardised Observability

Implement one ObservabilityTrace class used by ALL agents:

  class ObservabilityTrace:
      def add_trace(self, msg: str) -> None: ...
      def start_span(self, name: str) -> ContextManager: ...   # OpenTelemetry span
      def record_tool_call(self, tool_name: str, duration_ms: float) -> None: ...
      def get_trace_summary(self) -> list[str]: ...

  def emit_token_usage(result, agent_name: str, action: str, cfg: FrameworkConfig) -> None:
      """EMF CloudWatch metric: input_tokens, output_tokens, cache_read_tokens,
      cache_write_tokens, estimated_cost_usd (if pricing env vars present)."""

  def emit_turn_latency(start_ns: int, agent_name: str, action: str) -> None:
      """EMF CloudWatch metric: turn_duration_ms."""

  def log_cache_hit_rate(result, log) -> None:
      """Logs cache_read_tokens / (input_tokens + cache_read_tokens).
      Warns if cache_read_tokens == 0 — prompt caching is not working."""

Do NOT let individual agents define their own ObservabilityTrace or duplicate metric emission.
All agents get identical observability depth automatically.

---

## 10. runner.py — run_agent() Orchestrator

  def run_agent(
      agent_name: str,
      system_prompt_builder: SystemPromptBuilder,
      dynamic_context_marker: str,
      skills_builder: SkillsBuilder | None = None,
      tool_filter: ToolFilter | None = None,
      payload_parser: PayloadParser | None = None,
      pre_invoke_guard: PreInvokeGuard | None = None,
  ) -> None

This is the only function agent developers call. It:
1. Creates BedrockAgentCoreApp() and registers @app.entrypoint
2. Reads agent.yaml framework: section (cached) for per-agent tuning
3. Inside every turn, executes this exact order:

   Step  1: pre_invoke_guard(payload)                  → abort if returns dict
   Step  2: payload_parser(payload)                    → ParsedTurn
   Step  3: _load_config()                             → FrameworkConfig [lazy, cached]
   Step  4: _load_agent_yaml_framework_section()       → tuning dict [cached]
   Step  5: build_model(cfg, temperature, retry_max)   → (BedrockModel, RetryStrategy)
   Step  6: create_mcp_client(cfg)                     → MCPClient; call .start()
   Step  7: mcp_client.list_tools_sync()               → all_tools
   Step  8: tool_filter(all_tools, payload, stage)     → filtered_tools [default: pass all]
   Step  9: load_memory(cfg, actor_id, session_id, ...) → (stm_messages, ltm_summary)
   Step 10: system_prompt_builder(**ctx)               → raw prompt string
   Step 11: assemble_system_prompt(raw, marker, ltm, stm, dyn_ctx) → prompt content
   Step 12: skills_builder(stage, next_stage, payload) → skills [if provided]
   Step 13: Agent(model, system_prompt, tools, plugins=[AgentSkills(skills)], retry_strategy)
   Step 14: result = agent(grounded_prompt)            [SYNC — never await agent.arun()]
   Step 15: [FINALLY] flush_memory(cfg, ...)
   Step 16: [FINALLY] write_conversation_turn(...)
   Step 17: emit_token_usage(result, ...)
   Step 18: emit_turn_latency(start_ns, ...)
   Step 19: log_cache_hit_rate(result, log)
   Step 20: [FINALLY] mcp_client.stop()
   Step 21: [FINALLY] emit_turn_completion_event(...)
   Step 22: [FINALLY] release_turn_lock(...)

Soft-fail on max_tokens: if result.stop_reason == "max_tokens" AND
framework.soft_fail_on_max_tokens is True (the default), return a success response with body
"token budget exhausted" instead of raising. Never surface token exhaustion as a hard failure
in production — downstream systems should not treat it as a processing error.

---

## 11. Per-Agent File Contract

Each agent lives in src/<agents_root>/<agent_name>/ with these files:

REQUIRED (framework reads these):
  agent.yaml              — CDK discovery fields + optional framework: tuning section
  system_prompt.py        — ONLY: build_system_prompt(**ctx) -> str + DYNAMIC_CONTEXT_MARKER
  agentcore_entrypoint.py — ~15 lines: import framework hooks, call run_agent()

OPTIONAL (provide only when agent needs to override defaults):
  skills.py       — build_stage_skills(current_stage, next_stage, payload) -> list[Skill]
  tool_filter.py  — select_tools(all_tools, payload, current_stage) -> list
  payload_parser.py — parse_payload(raw_payload: dict) -> ParsedTurn
  guards.py       — a PreInvokeGuard-compatible callable (e.g. team-type check)

AGENT-SPECIFIC BUSINESS LOGIC (framework never touches these):
  workflow.py     — state machine logic, transition validation, business rules
  state.py        — agent-specific state enums and transition maps
  models.py       — Pydantic models for this agent's domain
  templates.py    — message/SMS templates specific to this agent

LOCAL DEV ONLY (not used by agentcore_entrypoint.py at all):
  agent.py        — build_agent() for local harness — imports local tools.py
  main.py         — local entry point
  tools.py        — @tool-decorated functions for local dev (production uses MCP)

Naming rules:
- Skills file MUST be named skills.py (not strands_skills.py, not strand_skills.py)
- All hook files use the names above — never invent alternate names
- agent.yaml top-level keys are fixed (CDK reads them) — do not add new top-level keys;
  put all new config under the framework: subsection

---

## 12. agent.yaml Schema

  # CDK reads ONLY these three fields — do not rename them
  runtime_name_suffix: <suffix>        # Used in CDK stack ID and resource names
  description: <human readable>
  entry_point: src/agents/<name>/agentcore_entrypoint.py

  # Framework reads this optional section at runtime — CDK ignores it entirely
  framework:
    stm_k: 4                       # STM turns to load per turn. Default: 4.
    temperature: 0.0               # Model temperature. Default: 0.0 (deterministic).
    retry_max_attempts: 3          # ModelRetryStrategy max attempts. Default: 3.
    async_turns: true              # Spawn background thread. Default: true.
    prompt_cache: true             # Enable Bedrock prompt caching. Default: true.
    ltm_enabled: true              # Load LTM rolling summary. Default: true.
    soft_fail_on_max_tokens: true  # Return success on max_tokens. Default: true.
    max_tool_timeout: 30           # Per-tool timeout seconds. Default: 30.

CDK auto-discovers agents from agent.yaml (no CDK code changes needed per new agent).

---

## 13. Thin Entrypoint Template (~15 lines)

Every agent's agentcore_entrypoint.py must look like this:

  from src.<shared_root>.agent_framework import run_agent
  from src.agents.<name>.system_prompt import build_system_prompt, DYNAMIC_CONTEXT_MARKER
  # Uncomment only the hooks this agent actually overrides:
  # from src.agents.<name>.skills import build_stage_skills
  # from src.agents.<name>.tool_filter import select_tools
  # from src.agents.<name>.payload_parser import parse_payload
  # from src.agents.<name>.guards import my_guard

  run_agent(
      agent_name="<name>",
      system_prompt_builder=build_system_prompt,
      dynamic_context_marker=DYNAMIC_CONTEXT_MARKER,
      # skills_builder=build_stage_skills,
      # tool_filter=select_tools,
      # payload_parser=parse_payload,
      # pre_invoke_guard=my_guard,
  )

Nothing else. No SSM loading. No model creation. No MCP setup. No memory wiring.
Any boilerplate outside run_agent() is a bug.

---

## 14. What the Framework Must Enforce (Not Document)

Prompt engineering:
- Cache point always placed at DYNAMIC_CONTEXT_MARKER — never at an arbitrary position
- Memory always injected after cache point (dynamic section) — never in the static section
- Memory authority order always: dynamic_context > STM > LTM (injected in this order)
- System prompt markers stripped before memory flush (prevents context pollution across turns)
- Warning logged if DYNAMIC_CONTEXT_MARKER absent (developer forgot it)

Strands Agents SDK:
- agent(prompt) called synchronously — NEVER await agent.arun()
- cache_tools="default" always set on BedrockModel
- CacheConfig(strategy="auto") always set on BedrockModel
- ModelRetryStrategy always applied
- agent.messages captured as list(getattr(agent, "messages", [])) — safe even if attr absent

AgentCore Runtime:
- SessionManager hook NEVER used — unbounded STM growth
- STM always capped at stm_k turns (default 4)
- Memory flush always in finally block — skipping it on error loses conversation history
- Turn lock always acquired before agent work begins
- Turn lock always released in finally — dangling locks block future turns (TTL=120s)
- Turn completion EventBridge event always emitted — both success and failure paths
- Config never loaded at import time — only inside @app.entrypoint callback

Python:
- FrameworkConfig is a frozen dataclass — no mutation after cold start
- All framework functions fully type-annotated
- @runtime_checkable Protocols — wrong hook signatures caught at startup, not runtime
- No bare except: — always except Exception as exc: with logger.exception()
- No secrets or PII in exception messages — use presence markers only

Security:
- SigV4HttpxAuth lives ONLY in mcp_factory.py — agents cannot bypass Gateway auth
- User input checked for prompt injection patterns before being passed to the agent
  (regex patterns: "ignore previous instructions", "system prompt", injection keywords)
- Error messages never include raw secret values — "present" / "missing" markers only

---

## 15. Hard "Never Do" List (Mistakes to Avoid)

NEVER do these — they are the exact mistakes this framework was built to prevent:

1. NEVER copy SigV4HttpxAuth into an agent entrypoint — it belongs in mcp_factory.py only
2. NEVER load SSM parameters at module import time — AgentCore resolves env vars after import;
   SSM calls at import time will fail silently or crash the runtime process
3. NEVER use AgentCore SessionManager hook — injects full unbounded STM history
4. NEVER call await agent.arun() — use agent(prompt) (synchronous callable)
5. NEVER create BedrockModel without cache_tools="default" and CacheConfig(strategy="auto")
6. NEVER skip flushing memory in a finally block — lost turns cannot be recovered
7. NEVER skip releasing the turn lock in a finally block — blocks all future turns for 120s
8. NEVER let two agents share an entrypoint file — one agent.yaml → one entrypoint
9. NEVER put agent-specific business logic (state machines, SMS templates) in the framework
10. NEVER re-implement tools in a second agent's tools.py if those tools already exist in
    another agent's tools.py — import from the source, do not copy
11. NEVER name the skills file anything other than skills.py (not strands_skills.py,
    strand_skills.py, or any other variant — inconsistent naming breaks discovery)
12. NEVER put runtime profile config (vCPU, memory, session limits) in Python code —
    those belong in CDK (fpl_agent_runtime_stack.py or equivalent)
13. NEVER use Fn::ImportValue for cross-stack ARN sharing — construct ARNs deterministically
    from explicit resource names
14. NEVER let opentelemetry-api versions drift between agent requirements.txt files —
    pin all agents to the same version in a shared requirements file or enforce with CI

---

## 16. requirements.txt — Per-Agent Dependencies

Each agent directory has its own requirements.txt for AgentCore packaging.
All must pin the SAME versions (drift causes subtle runtime failures):

  strands-agents==<version>
  bedrock-agentcore==<version>
  boto3==<version>
  pydantic==<version>
  opentelemetry-api==<version>
  aws-opentelemetry-distro==<version>
  pywin32; sys_platform == "win32"

The framework itself (shared/agent_framework/) does NOT have its own requirements.txt —
it is packaged as part of the shared Lambda Layer.

---

## 17. Local Dev Compatibility

The framework's run_agent() calls BedrockAgentCoreApp(), which only works inside an
AgentCore runtime. Local development bypasses the entrypoint entirely:
- agent.py has a build_agent() function that uses src/shared/config.py + local tools.py
- main.py calls build_agent() for interactive local testing
- Neither file imports agentcore_entrypoint.py

This means:
- The framework does not need to support a local dev mode
- The extracted payload_parser.py, tool_filter.py, and skills.py are pure functions with
  no AgentCore imports; local dev can import them directly if needed
- Never add if/else runtime_mode checks inside the framework runner

---

## 18. Implementation Steps

1. Read all existing CDK code (app.py, cdk.json, all stack files) to learn:
   - SSM prefix, project prefix, shared resource names (EventBridge bus, DynamoDB tables)
   - How agent.yaml is discovered (agent_discovery.py pattern)
   - What env vars the CDK sets on the AgentCore runtime container

2. Create src/<shared_root>/agent_framework/ with all 10 modules above.
   Start with hooks.py and config.py — everything else depends on these.

3. Write unit tests for each framework module before writing runner.py.
   Mock: BedrockAgentCoreApp, strands.Agent, boto3.client, MemoryClient.

4. Create the first agent directory using the exact per-agent file contract.
   Implement system_prompt.py with DYNAMIC_CONTEXT_MARKER. Write agentcore_entrypoint.py
   (15 lines). Run cdk synth to confirm CDK discovers the new agent.

5. Verify end-to-end: submit a test event → agent responds → STM written to Memory →
   turn completion event in EventBridge → turn archived in DynamoDB → token usage in CloudWatch.

6. Add each subsequent agent following the same pattern. The framework never changes.

---

## 19. Verification Checklist

After implementing the framework and the first agent:

□ cdk synth -c env=dev --quiet — zero violations, agent stack discovered
□ pytest tests/ -v — all framework unit tests pass with mocked dependencies
□ python -m src.main — local dev agent starts without import errors
□ Turn flow test: one test event → response returned from agent
□ Memory written: STM visible in AgentCore Memory console
□ Turn lock released: no dangling locks in DynamoDB after turn completes
□ Turn completion event: AgentTurnCompleted detail type appears in EventBridge
□ Conversation archived: turn record in DynamoDB conversation table
□ Token usage: CloudWatch EMF metric with input/output/cache token counts
□ Cache hit: cache_read_tokens > 0 in CloudWatch (prompt caching working)
□ New agent test: add a second minimal agent → CDK picks it up, it invokes → delete it
□ Dependency check: all agent requirements.txt pin identical library versions
```
