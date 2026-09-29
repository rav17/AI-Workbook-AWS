# Design Document — implement-prompts

## Overview

This design closes three implementation gaps in the AIOps Self-Healing Infrastructure project:

1. **AgentCore Agent Framework** (`src/agentic_ai/agent_framework/`) — a shared Python
   package that reduces every AgentCore Runtime entrypoint to ~15 lines by encoding all
   infrastructure boilerplate (memory, caching, observability, turn locking, prompt assembly)
   as framework code rather than per-agent convention.

2. **CDK Best Practices** — fills the remaining gaps in `src/agentic_ai/infra/`: CDK Nag
   compliance, centralised suppressions, SSM-based cross-stack references, CDK unit tests,
   content-hash Lambda packaging, a committed `cdk.context.json`, and auto-discovery of
   resources from YAML files.

3. **CI/CD Replication** — closes the gaps in `.github/workflows/`: a reusable composite
   action, per-job OIDC scoping, concurrency controls, surgical change detection, PR diff
   comments, stuck-stack recovery, a dedicated production workflow, rollback via SHA,
   SHA-gap detection, Secrets Manager pre-flight, post-deploy stack verification, and job
   timeouts.

All code must comply with the project engineering standards: ruff formatting, full type
hints, Google-style docstrings, `JsonFormatter` structured logging, no hardcoded secrets,
least-privilege IAM, and pinned dependency versions.

---

## Architecture

### High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│  AgentCore Runtime Container                                         │
│                                                                      │
│  agentcore_entrypoint.py  (~15 lines)                               │
│         │                                                            │
│         └─► run_agent(hooks, parsed_turn)  [runner.py]             │
│                   │                                                  │
│         ┌─────────┴──────────────────────────────────┐             │
│         │              agent_framework/               │             │
│         │  config.py  hooks.py  mcp_factory.py        │             │
│         │  memory_manager.py  prompt_assembler.py     │             │
│         │  model_builder.py  turn_runner.py           │             │
│         │  observability.py  runner.py                │             │
│         └─────────────────────────────────────────────┘             │
│                   │                                                  │
│    ┌──────────────┼────────────────┐                                │
│    ▼              ▼                ▼                                │
│  DynamoDB      AgentCore         Bedrock                            │
│  (turn lock)   Memory            (model)                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  CDK Infrastructure  (src/agentic_ai/infra/)                        │
│                                                                      │
│  app.py ──► AwsSolutionsChecks (cdk_nag)                           │
│         ──► nag_suppressions.apply_common_suppressions(stack)       │
│         ──► staging.stage_resource_code()                           │
│         ──► resource_discovery.discover_resources()                 │
│         ──► SSM cross-stack references (no Fn::ImportValue)         │
│         ──► tests/cdk/  (pytest -m cdk)                             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  CI/CD  (.github/)                                                   │
│                                                                      │
│  actions/setup-cdk/action.yml  (composite, Python 3.11 + Node 24)  │
│  workflows/ci.yml              (lint → test → cdk-test → docker)    │
│  workflows/cd.yml              (detect-changes → resolve-env → deploy)│
│  workflows/prod-deploy.yml     (approval-gated production)          │
│  workflows/cleanup-stuck-stack.yml  (stuck CloudFormation recovery) │
└─────────────────────────────────────────────────────────────────────┘
```

### Dependency Graph (Agent Framework Modules)

```
runner.py
 ├── hooks.py           (ParsedTurn, Protocols)
 ├── config.py          (FrameworkConfig, lru_cache factory)
 ├── turn_runner.py     (DynamoDB lock, async dispatch)
 ├── mcp_factory.py     (SigV4HttpxAuth, create_mcp_client)
 ├── memory_manager.py  (load_memory, flush_memory)
 ├── prompt_assembler.py (assemble_system_prompt)
 ├── model_builder.py   (build_model)
 └── observability.py   (ObservabilityTrace, EMF metrics)
```

---

## Components and Interfaces

### Area 1: Agent Framework

#### 1.1 Module Layout

```
src/agentic_ai/agent_framework/
  __init__.py
  hooks.py
  config.py
  mcp_factory.py
  memory_manager.py
  prompt_assembler.py
  model_builder.py
  turn_runner.py
  observability.py
  runner.py
```

#### 1.2 `hooks.py` — ParsedTurn and Protocols

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

DYNAMIC_CONTEXT_MARKER = "<!-- DYNAMIC_CONTEXT -->"

@dataclass
class ParsedTurn:
    """Structured fields extracted from a raw AgentCore event."""
    workflow_id: str
    session_id: str
    user_prompt: str
    dynamic_context: str
    raw_event: dict[str, Any]

@runtime_checkable
class SystemPromptBuilder(Protocol):
    def build_system_prompt(self, turn: ParsedTurn, cfg: FrameworkConfig) -> str: ...

@runtime_checkable
class SkillsBuilder(Protocol):
    def build_skills(self, turn: ParsedTurn, cfg: FrameworkConfig) -> list[Any]: ...

@runtime_checkable
class ToolFilter(Protocol):
    def filter_tools(self, tools: list[Any], turn: ParsedTurn) -> list[Any]: ...

@runtime_checkable
class PayloadParser(Protocol):
    def parse(self, raw_event: dict[str, Any]) -> ParsedTurn: ...

@runtime_checkable
class PreInvokeGuard(Protocol):
    def check(self, turn: ParsedTurn, cfg: FrameworkConfig) -> dict[str, Any] | None: ...
```

Protocol validation in `run_agent()`: on startup, before processing any turn, the runner
iterates the five hook slots and calls `isinstance(hook, Protocol)` for the
`@runtime_checkable` check. A `TypeError` is raised if any hook fails the check.

#### 1.3 `config.py` — FrameworkConfig

```python
from __future__ import annotations
import functools
import os
from dataclasses import dataclass
import boto3

SSM_PREFIX = "/aiops/{env}"

@dataclass(frozen=True)
class FrameworkConfig:
    model_id: str
    agentcore_gateway_id: str
    agentcore_memory_id: str
    dynamodb_workflow_table: str
    aws_region: str
    stm_k: int = 4
    temperature: float = 0.2
    retry_max_attempts: int = 3
    async_turns: bool = True
    prompt_cache: bool = True
    ltm_enabled: bool = True
    soft_fail_on_max_tokens: bool = True
    max_tool_timeout: int = 60

@functools.lru_cache(maxsize=1)
def get_framework_config() -> FrameworkConfig:
    """Load FrameworkConfig from SSM and environment variables.

    MUST be called inside @app.entrypoint callback, never at module import.
    Raises:
        ConfigLoadError: If a required SSM parameter is unreachable,
            including the parameter path in the message (never the value).
    """
    env = os.environ["AIOPS_ENVIRONMENT"]
    ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    model_id = _get_ssm(ssm, f"/aiops/{env}/MODEL_ID")
    return FrameworkConfig(
        model_id=model_id,
        agentcore_gateway_id=os.environ["AGENTCORE_GATEWAY_ID"],
        agentcore_memory_id=os.environ["AGENTCORE_MEMORY_ID"],
        dynamodb_workflow_table=os.environ["DYNAMODB_WORKFLOW_TABLE"],
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
    )
```

Key design decisions:
- `frozen=True` prevents accidental mutation anywhere in the call stack.
- `@lru_cache(maxsize=1)` ensures SSM is called exactly once per process lifetime.
- The factory is **never** called at module import time — only inside the AgentCore
  `@app.entrypoint` callback, which runs after the container is fully initialised.
- On SSM failure, `ConfigLoadError` message includes the parameter path but never its value,
  satisfying both debuggability and secret hygiene.

#### 1.4 `mcp_factory.py` — SigV4 Auth and MCP Client

```python
class SigV4HttpxAuth(httpx.Auth):
    """Signs httpx requests with AWS SigV4 credentials.

    This class MUST NOT be imported outside mcp_factory.py.
    """
    def __init__(self, region: str, service: str = "bedrock-agentcore") -> None: ...
    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, ...]: ...

def create_mcp_client(cfg: FrameworkConfig) -> MCPClient:
    """Return a configured, not-yet-started MCP client.

    Caller contract:
        client = create_mcp_client(cfg)
        await client.start()
        try:
            tools = await client.list_tools()
            ...
        finally:
            await client.stop()
    """
```

Design rationale: centralising `SigV4HttpxAuth` in `mcp_factory.py` means there is exactly
one place where gateway authentication is defined. CI enforces this via an import-scan test.
The `not-yet-started` contract is explicit in the docstring and enforced by the runner's
`finally` block.

#### 1.5 `memory_manager.py` — STM and LTM

```python
from concurrent.futures import ThreadPoolExecutor

def load_memory(
    cfg: FrameworkConfig,
    session_id: str,
    actor_id: str,
) -> tuple[list[Event], str]:
    """Concurrently fetch STM (last stm_k events) and LTM (semantic summary).

    Uses ThreadPoolExecutor with two futures — one for list_events (STM)
    and one for retrieve_records (LTM). Both use MemoryClient directly;
    SessionManager is never used.

    Returns:
        Tuple of (stm_events[:stm_k], ltm_summary_text).
    """

def flush_memory(
    cfg: FrameworkConfig,
    session_id: str,
    actor_id: str,
    messages: list[dict],
) -> None:
    """Strip DYNAMIC_CONTEXT_MARKER and system markers, then write to MemoryClient.

    Called inside a finally block in runner.py so conversation history
    is persisted even when the agent turn raises an exception.
    """
```

STM cap invariant: `stm_events[:cfg.stm_k]` guarantees the cap regardless of how many
events `MemoryClient.list_events()` returns. This is the core correctness property for
memory management.

Marker stripping: `flush_memory` calls `message.replace(DYNAMIC_CONTEXT_MARKER, "")` and
strips `<system>…</system>` blocks before writing. This prevents context-cache markers from
being re-ingested as memory on subsequent turns.

#### 1.6 `prompt_assembler.py` — Cache-Point Injection

```python
def assemble_system_prompt(
    raw_prompt: str,
    ltm_summary: str,
    stm_events: list[Event],
    dynamic_context: str,
) -> list[dict] | str:
    """Assemble system prompt with Bedrock cache-point injection.

    If DYNAMIC_CONTEXT_MARKER is present, returns a content list:
        [
            {"text": <static_prefix>},
            {"cachePoint": {"type": "default"}},
            {"text": <ltm_summary> + <stm_turns> + <dynamic_context>},
        ]

    If DYNAMIC_CONTEXT_MARKER is absent, logs WARNING and returns
    raw_prompt as a plain string (graceful degradation).
    """
```

The three-element content list structure is the contract with Bedrock's prompt caching API.
The static prefix (everything before `DYNAMIC_CONTEXT_MARKER`) must be identical across
turns for the cache hit to fire — any per-turn data placed before the marker would break
caching. The `log_cache_hit_rate()` function provides an observable signal when this
contract is violated (cache_read_tokens == 0 warns the operator).

#### 1.7 `model_builder.py` — BedrockModel with Caching Enforced

```python
from strands import BedrockModel, CacheConfig, ModelRetryStrategy

def build_model(cfg: FrameworkConfig) -> BedrockModel:
    """Build BedrockModel with prompt caching and retry always enabled.

    cache_tools="default" and CacheConfig(strategy="auto") are ALWAYS set
    and cannot be overridden by per-agent config. retry_max_attempts,
    initial_delay, and max_delay are configurable via FrameworkConfig.
    """
    return BedrockModel(
        model_id=cfg.model_id,
        temperature=cfg.temperature,
        cache_tools="default",
        cache_config=CacheConfig(strategy="auto"),
        retry_strategy=ModelRetryStrategy(
            retry_max_attempts=cfg.retry_max_attempts,
            initial_delay=10,
            max_delay=60,
        ),
    )
```

Design decision: `cache_tools` and `CacheConfig` are hardcoded in `build_model()` and not
exposed as configurable parameters. This prevents an agent developer from accidentally
disabling prompt caching, which would dramatically increase Bedrock costs. If an agent
genuinely needs different caching behaviour, it must go through a framework PR, not a
per-agent YAML change.

#### 1.8 `turn_runner.py` — DynamoDB Turn Lock

```python
TURN_LOCK_TTL_SECONDS = 120

def run_turn(
    cfg: FrameworkConfig,
    workflow_id: str,
    turn_fn: Callable[[], dict],
    async_turns: bool = True,
) -> dict:
    """Acquire DynamoDB turn lock and dispatch agent work.

    Turn lock schema:
        PK: workflow_id (String)
        ttl: epoch_seconds + 120  (Number, DynamoDB TTL attribute)

    Conditional PutItem expression:
        ConditionExpression="attribute_not_exists(workflow_id)"

    If ConditionalCheckFailedException → lock held → return ACK immediately.
    If async_turns=True → dispatch turn_fn on daemon Thread with own event loop.
    Lock released in finally block via DeleteItem regardless of turn outcome.
    """
```

Turn lock table: The DynamoDB table name comes from `cfg.dynamodb_workflow_table`
(populated from the `DYNAMODB_WORKFLOW_TABLE` env var). The table must have TTL configured
on the `ttl` attribute to auto-expire leaked locks if the process crashes before the
`finally` block executes.

Async dispatch design: when `async_turns=True`, a `threading.Thread(daemon=True)` is
started. The thread calls `asyncio.run(turn_fn())` creating its own event loop. The main
thread returns an ACK response immediately, allowing AgentCore to acknowledge receipt to
the caller without blocking on the turn's completion.

#### 1.9 `observability.py` — EMF Metrics

```python
@dataclass
class ObservabilityTrace:
    agent_name: str
    session_id: str
    workflow_id: str
    turn_start_ns: int = field(default_factory=time.monotonic_ns)

def emit_token_usage(
    trace: ObservabilityTrace,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
) -> None:
    """Emit EMF CloudWatch metric with token counts and optional cost.

    Namespace: AIOps/{environment}
    Metric dimensions: agent_name, session_id
    Metrics emitted:
        - InputTokens, OutputTokens, CacheReadTokens, CacheWriteTokens
        - EstimatedCostUsd (when INPUT_TOKEN_COST_USD and OUTPUT_TOKEN_COST_USD env vars set)
    """

def emit_turn_latency(trace: ObservabilityTrace) -> None:
    """Emit TurnLatencyMs metric from trace.turn_start_ns to now."""

def log_cache_hit_rate(
    trace: ObservabilityTrace,
    cache_read_tokens: int,
    cache_write_tokens: int,
) -> None:
    """Log cache hit rate; emit WARNING when cache_read_tokens == 0."""
```

EMF format is used (not `PutMetricData`) so that metrics are embedded in CloudWatch Logs
without a separate API call, reducing latency and cost. The `log_cache_hit_rate` WARNING
provides an on-call signal when the prompt caching contract is broken.

#### 1.10 `runner.py` — 22-Step Orchestrator

The complete turn lifecycle executed by `run_agent()`:

```
Step  1  pre_invoke_guard      → hooks.PreInvokeGuard.check() — abort if non-None returned
Step  2  payload_parser        → hooks.PayloadParser.parse(raw_event) → ParsedTurn
Step  3  load_config           → config.get_framework_config() (lru_cache)
Step  4  load_agent_yaml       → read + cache agent.yaml framework: section
Step  5  build_model           → model_builder.build_model(cfg) → BedrockModel
Step  6  create_mcp_client     → mcp_factory.create_mcp_client(cfg) → MCPClient
Step  7  list_tools            → await mcp_client.start(); await mcp_client.list_tools()
Step  8  tool_filter           → hooks.ToolFilter.filter_tools(tools, turn)
Step  9  load_memory           → memory_manager.load_memory(cfg, session_id, actor_id)
Step 10  system_prompt_builder → hooks.SystemPromptBuilder.build_system_prompt(turn, cfg)
Step 11  assemble_system_prompt→ prompt_assembler.assemble_system_prompt(raw, ltm, stm, ctx)
Step 12  skills_builder        → hooks.SkillsBuilder.build_skills(turn, cfg)
Step 13  build_agent           → strands.Agent(model, system_prompt, tools, skills)
Step 14  invoke_agent          → result = agent(turn.user_prompt)  ← synchronous, NOT arun
Step 15  flush_memory          → memory_manager.flush_memory(...)  [finally]
Step 16  write_conversation    → MemoryClient.create_event(turn messages) [finally]
Step 17  emit_token_usage      → observability.emit_token_usage(trace, usage)
Step 18  emit_turn_latency     → observability.emit_turn_latency(trace)
Step 19  log_cache_hit_rate    → observability.log_cache_hit_rate(trace, tokens)
Step 20  stop_mcp_client       → await mcp_client.stop()           [finally]
Step 21  emit_turn_completion  → log INFO with stop_reason          [finally]
Step 22  release_turn_lock     → turn_runner.release_lock(workflow_id) [finally]
```

Steps 15, 16, 20, 21, 22 are unconditionally executed in `finally` blocks. This guarantees
that even a crashed turn:
- writes conversation history (steps 15–16),
- stops the MCP client (step 20),
- logs its completion state (step 21),
- releases the turn lock (step 22).

`max_tokens` soft-fail: if `result.stop_reason == "max_tokens"` and
`cfg.soft_fail_on_max_tokens is True` (the default), `run_agent()` returns
`{"status": "ok", "body": "token budget exhausted"}` rather than raising an exception.
This prevents AgentCore from retrying a turn that legitimately exhausted its token budget.

#### 1.11 `__init__.py` — Public API

```python
from .runner import run_agent
from .hooks import (
    ParsedTurn,
    SystemPromptBuilder,
    SkillsBuilder,
    ToolFilter,
    PayloadParser,
    PreInvokeGuard,
    DYNAMIC_CONTEXT_MARKER,
)

__all__ = [
    "run_agent",
    "ParsedTurn",
    "SystemPromptBuilder",
    "SkillsBuilder",
    "ToolFilter",
    "PayloadParser",
    "PreInvokeGuard",
    "DYNAMIC_CONTEXT_MARKER",
]
```

All implementation modules (`config`, `mcp_factory`, etc.) are not re-exported. Agent
entrypoints import only from `agent_framework`, never from sub-modules directly.

#### 1.12 Per-Agent Directory Contract

Each of the three existing agents is migrated to this layout:

```
src/agentic_ai/agents/<name>/
  agent.yaml
  system_prompt.py
  agentcore_entrypoint.py
  # Optional:
  skills.py
  tool_filter.py
  payload_parser.py
  guards.py
```

**`agentcore_entrypoint.py`** (≤ 20 lines, all agents follow this template):

```python
"""AgentCore entrypoint for the <name> agent."""
from __future__ import annotations

from bedrock_agentcore import BedrockAgentCoreApp
from agentic_ai.agent_framework import run_agent

from .system_prompt import build_system_prompt
from .payload_parser import CorrelatorPayloadParser  # agent-specific

app = BedrockAgentCoreApp()

@app.entrypoint
def handler(payload: dict) -> dict:
    """Handle a single AgentCore turn."""
    return run_agent(
        raw_event=payload,
        system_prompt_builder=build_system_prompt,
        payload_parser=CorrelatorPayloadParser(),
    )
```

**`agent.yaml`** `framework:` section (all fields optional with defaults):

```yaml
name: correlator
description: Groups related alerts within a configurable time window.

framework:
  stm_k: 4
  temperature: 0.2
  retry_max_attempts: 3
  async_turns: true
  prompt_cache: true
  ltm_enabled: true
  soft_fail_on_max_tokens: true
  max_tool_timeout: 60
```

**`system_prompt.py`** structure:

```python
from agentic_ai.agent_framework import DYNAMIC_CONTEXT_MARKER

_STATIC_PREFIX = """
You are the AIOps Alert Correlator agent.
[... stable system instructions that benefit from prompt caching ...]
"""

def build_system_prompt(turn, cfg) -> str:
    return _STATIC_PREFIX + DYNAMIC_CONTEXT_MARKER
```

The `DYNAMIC_CONTEXT_MARKER` placement divides the prompt at the boundary between the
cacheable static prefix and the non-cacheable dynamic suffix that `prompt_assembler.py`
will inject with LTM, STM, and per-turn context.

#### 1.13 Agent Migration Map

| Existing file | New location | Notes |
|---|---|---|
| `agents/correlator.py` | `agents/correlator/agent.yaml` + `agentcore_entrypoint.py` + `system_prompt.py` | Business logic stays in `correlator.py`; entry delegates to framework |
| `agents/model_router.py` | `agents/model_router/agent.yaml` + `agentcore_entrypoint.py` + `system_prompt.py` | |
| `agents/reasoning_agent.py` | `agents/reasoning_agent/agent.yaml` + `agentcore_entrypoint.py` + `system_prompt.py` | |

The existing `correlator.py`, `model_router.py`, `reasoning_agent.py` files remain as
business logic modules. The new agent directories add the framework integration layer
without modifying those files. This is a non-breaking migration.

---

### Area 2: CDK Best Practices

#### 2.1 CDK Nag Integration

Add to `app.py` after all stacks are instantiated but before `app.synth()`:

```python
from cdk_nag import AwsSolutionsChecks
from .nag_suppressions import apply_common_suppressions

# Add compliance checks
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

# Apply project-wide suppressions
for stack in [
    network_stack, data_stack, compute_stack,
    observability_stack, monitoring_stack, simulation_stack,
]:
    apply_common_suppressions(stack)
```

#### 2.2 `nag_suppressions.py` — Centralised Suppressions

```python
"""Centralised CDK Nag suppression helper for all stacks.

All suppressions MUST include a reason= string. The presence of a
reason is verified by the CI test suite.
"""
from __future__ import annotations
import aws_cdk as cdk
from cdk_nag import NagSuppressions

def apply_common_suppressions(stack: cdk.Stack) -> None:
    """Apply project-wide nag suppressions to stack.

    Args:
        stack: The CDK stack to apply suppressions to.
    """
    NagSuppressions.add_stack_suppressions(
        stack,
        [
            {
                "id": "AwsSolutions-IAM5",
                "reason": (
                    "bedrock:InvokeModel requires Resource: foundation-model/* "
                    "because the model fallback chain selects the model at runtime. "
                    "AWS does not support per-model ARN scoping for InvokeModel."
                ),
            },
            {
                "id": "AwsSolutions-IAM5",
                "reason": (
                    "logs:CreateLogGroup is AWS-mandated and cannot be scoped to a "
                    "specific log group ARN at the time the Lambda execution role "
                    "is created."
                ),
            },
        ],
    )
```

Design decision: all suppressions are in one file so that a security review can enumerate
every accepted deviation from `AwsSolutions` rules without scanning all stack files.
The CI test (Req 8.3) scans `nag_suppressions.py` and asserts no suppression object lacks
a `reason` key.

#### 2.3 SSM Cross-Stack Reference Pattern

Each stack writes its exported ARNs immediately after resource creation:

```python
# In data_stack.py — write
ssm.StringParameter(
    self, "WorkflowTableArnParam",
    parameter_name=f"/aiops/{context.environment}/workflow-table-arn",
    string_value=self.workflow_table.table_arn,
)

# In compute_stack.py — read (no construct-level cross-stack ref)
workflow_table_arn = ssm.StringParameter.value_for_string_parameter(
    self, "/aiops/{env}/workflow-table-arn".format(env=context.environment),
)
```

The `value_for_string_parameter()` call produces `{{resolve:ssm:/aiops/dev/workflow-table-arn}}`
in the synthesized template. CloudFormation resolves this at changeset creation, not at CDK
synth time, so stacks can be deleted and redeployed independently without breaking the
reference chain.

`CfnOutput` with `export_name` is forbidden for ARN sharing. The CI test (Req 9.3) scans
all synthesized CloudFormation templates for `Fn::ImportValue` and fails if any is found.

#### 2.4 `staging.py` — Content-Hash Lambda Packaging

```python
"""Content-hash-gated Lambda packaging.

Computes a SHA-256 fingerprint over all .py, .txt, and .json files
in a source directory. If a .build/ directory with a matching hash
already exists, returns it immediately (no pip install). Otherwise,
copies source, runs pip install, and returns the new build path.
"""
from __future__ import annotations
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

HASH_LENGTH = 12  # 12 hex chars of SHA-256 = 48 bits, collision-safe for build dirs

def stage_resource_code(
    source_dir: Path,
    resource_name: str,
    build_root: Path | None = None,
) -> Path:
    """Stage Lambda code with content-hash gating.

    Args:
        source_dir: Directory containing Lambda source files.
        resource_name: Logical name of the Lambda resource.
        build_root: Root for .build/ directories (default: repo root / .build).

    Returns:
        Path to the staged build directory ready for aws_lambda.Code.from_asset().

    Raises:
        ValueError: If source_dir does not exist or contains no stageable files.
    """
    content_hash = _compute_hash(source_dir)
    build_dir = (build_root or Path(".build")) / f"{resource_name}-{content_hash}"
    if build_dir.exists():
        return build_dir
    build_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, build_dir / "src", dirs_exist_ok=True)
    req_file = source_dir / "requirements.txt"
    if req_file.exists():
        subprocess.check_call(
            ["pip", "install", "-r", str(req_file), "-t", str(build_dir)],
            timeout=300,
        )
    return build_dir

def _compute_hash(source_dir: Path) -> str:
    hasher = hashlib.sha256()
    for ext in (".py", ".txt", ".json"):
        for path in sorted(source_dir.rglob(f"*{ext}")):
            hasher.update(path.read_bytes())
    return hasher.hexdigest()[:HASH_LENGTH]
```

`.build/` is added to `.gitignore`. The content-hash approach means that if only
`requirements.txt` changes, the hash changes, triggering a rebuild. If only non-code
files change (Markdown, etc.), the hash is unchanged and the cached build is reused.

#### 2.5 `resource_discovery.py` — Auto-Discovery

```python
"""Auto-discovery of resources from src/resources/*/resource.yaml.

Scans for resource.yaml files, validates name patterns and required
fields, and returns a dict keyed by resource name. Used by app.py
to instantiate resource stacks dynamically without hardcoded lists.
"""
from __future__ import annotations
import re
from pathlib import Path
import yaml

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
REQUIRED_FIELDS = ("type", "description")

def discover_resources(resources_root: Path | None = None) -> dict[str, dict]:
    """Discover and validate resource configurations.

    Args:
        resources_root: Path to src/resources/ (default: auto-detected).

    Returns:
        Dict mapping resource_name → parsed resource.yaml content.

    Raises:
        ValueError: If a resource name violates the naming pattern or
            resource.yaml is missing a required field. The offending
            path is included in the error message.
    """
```

**Type registry in `app.py`**:

```python
RESOURCE_TYPE_REGISTRY: dict[str, type[cdk.Stack]] = {
    "lambda": LambdaResourceStack,
    "sqs_queue": SqsQueueResourceStack,
    "dynamodb_table": DynamoDbResourceStack,
    "ecs_service": EcsServiceResourceStack,
}

resources = discover_resources()
resource_stacks: list[cdk.Stack] = []
for name, resource_cfg in resources.items():
    stack_class = RESOURCE_TYPE_REGISTRY.get(resource_cfg["type"])
    if stack_class is None:
        raise ValueError(f"Unknown resource type '{resource_cfg['type']}' in {name}")
    rs = stack_class(app, f"{prefix}-Resource-{name}", ...)
    for dep in resource_stacks:
        rs.add_dependency(dep)  # prevent concurrent CloudFormation mutations
    resource_stacks.append(rs)
```

The `add_dependency()` chain serialises all discovered resource stacks, preventing
concurrent CloudFormation mutations on shared resources (DynamoDB tables, IAM roles).

#### 2.6 CDK Unit Tests in `tests/cdk/`

```
tests/cdk/
  conftest.py           ← shared app/context fixture
  test_network_stack.py
  test_data_stack.py
  test_compute_stack.py
  test_observability_stack.py
  test_monitoring_stack.py
  test_simulation_stack.py
```

Each test file follows this pattern:

```python
import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Template, Match
from agentic_ai.infra.stacks.network_stack import NetworkStack

@pytest.fixture
def template(test_context) -> Template:
    app = cdk.App()
    stack = NetworkStack(app, "TestNetwork", env=..., context=test_context)
    return Template.from_stack(stack)

def test_snapshot(template: Template, snapshot):
    assert template.to_json() == snapshot  # pytest-snapshot

def test_vpc_has_flow_logs(template: Template):
    template.has_resource_properties("AWS::EC2::FlowLog", Match.any_value())

def test_dynamodb_sse_enabled(template: Template):
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {"SSESpecification": {"SSEEnabled": True}},
    )

def test_lambda_kms_key(template: Template):
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"KmsKeyArn": Match.any_value()},
    )

def test_log_group_retention(template: Template):
    template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {"RetentionInDays": Match.not_(Match.absent())},
    )
```

Tests are marked with `@pytest.mark.cdk` and run with `pytest -m cdk`.

---

### Area 3: CI/CD

#### 3.1 Composite Action `.github/actions/setup-cdk/action.yml`

```yaml
name: Setup CDK Environment
description: Installs Python 3.11, Node 24, and the CDK CLI at the pinned version.

inputs:
  install-cdk-python-deps:
    description: Install CDK Python dependencies from pyproject.toml
    default: "true"

runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - uses: actions/setup-node@v4
      with:
        node-version: "24"
    - name: Install CDK CLI (pinned to aws-cdk-lib version)
      shell: bash
      run: npm install -g aws-cdk@2.160.0
    - name: Verify CDK CLI
      shell: bash
      run: cdk --version
    - name: Install CDK Python dependencies
      if: inputs.install-cdk-python-deps == 'true'
      shell: bash
      run: pip install -e ".[dev,cdk]"
```

The CDK CLI version `2.160.0` is pinned to match `aws-cdk-lib==2.160.0` in
`pyproject.toml`. When the library version is bumped, the action version must be
updated in the same PR to keep CLI and library in sync.

#### 3.2 Refactored `ci.yml` Workflow Graph

```
on: push (main, staging, v*.*.*) / pull_request (main)
                    │
        ┌───────────┼───────────────────────────┐
        ▼           ▼                           ▼
     lint        unit-tests                property-tests
  (cancel: true) (needs: lint,             (needs: lint,
  timeout: 15m    cancel: true,             cancel: true,
                  timeout: 15m)             timeout: 15m)
                    │                           │
                    └───────────┬───────────────┘
                                ▼
                           cdk-test
                        (needs: lint,
                         cancel: true,
                         timeout: 15m)
                                │
                   ┌────────────┴────────────┐
                   ▼                         ▼
              [PR only]                 [push only]
              cdk-diff                 docker-build
          (post PR comment)           (timeout: 20m)
                                          │
                                          ▼
                                     ecr-scan-push
                                  (id-token: write,
                                   needs: docker-build,
                                   if: push only)
```

Key changes from current `ci.yml`:
- `id-token: write` removed from workflow-level `permissions`, added only to `ecr-scan-push`.
- `concurrency.cancel-in-progress: true` added to lint, unit-tests, property-tests, cdk-test.
- Node version bumped from 20 to 24 (via composite action).
- All setup steps replaced with `uses: ./.github/actions/setup-cdk`.
- New `cdk-diff` job added (PR only) posting diff as PR comment.

#### 3.3 Refactored `cd.yml` Workflow Graph

```
on: push (main, staging) / workflow_dispatch (commit_sha input)
                              │
              ┌───────────────┼──────────────────┐
              ▼               ▼                  ▼
        detect-changes    resolve-env       (sha-gap check)
        (per-stack flags,  (env_name,        sets FORCE_ALL=true
         force_all)         is_rollback)      if SHA gap found
              │               │
              └───────┬───────┘
                      ▼
               auto-preflight (dev only)
             → calls cleanup-stuck-stack.yml
                      │
                      ▼
                   deploy
              (concurrency: deploy-{env},
               cancel-in-progress: false,
               timeout: 90m)
               Steps:
                1. checkout (or commit_sha checkout for rollback)
                2. ./.github/actions/setup-cdk
                3. OIDC (id-token: write, job-level only)
                4. secrets-check (Secrets Manager pre-flight)
                5. sha-gap detection
                6. cdk synth --lookups false
                7. cdk deploy (surgical if not FORCE_ALL)
                8. post-deploy stack state verification
                9. update LAST_DEPLOYED_SHA env variable
```

**Branch → environment mapping** (in `resolve-env` job):

| Branch / ref | `env_name` | Notes |
|---|---|---|
| `main` | `dev` | |
| `staging` | `staging` | |
| `v*.*.*` tag | `prod` | Routes to `prod-deploy.yml` instead |

**Stack names** (exact CDK IDs from `app.py`):

```
Aiops-{env}-Network
Aiops-{env}-Data
Aiops-{env}-Compute
Aiops-{env}-Observability
Aiops-{env}-Monitoring
Aiops-{env}-Simulation
```

**`detect-changes` output schema**:

```yaml
outputs:
  network: boolean
  data: boolean
  compute: boolean
  observability: boolean
  monitoring: boolean
  simulation: boolean
  force_all: boolean
  any_change: boolean
```

**SHA-gap detection** (step in `deploy` job):

```bash
BRANCH_SLUG="${GITHUB_REF_NAME//\//-}"
LAST_SHA=$(gh variable get "last_deployed_sha_${BRANCH_SLUG}" \
           --env "${ENV_NAME}" 2>/dev/null || echo "")

if [[ -n "$LAST_SHA" && "$LAST_SHA" != "${{ github.event.before }}" ]]; then
  echo "SHA gap detected: last_deployed=$LAST_SHA, event_before=${{ github.event.before }}"
  echo "FORCE_ALL=true" >> $GITHUB_ENV
fi
```

**Secrets Manager pre-flight** (runs before any `cdk deploy`):

```bash
REQUIRED_SECRETS=(
  "/aiops/${ENV_NAME}/api-gateway-key"
  "/aiops/${ENV_NAME}/approval-signing-secret"
)
for SECRET in "${REQUIRED_SECRETS[@]}"; do
  aws secretsmanager describe-secret --secret-id "$SECRET" > /dev/null || {
    echo "::error::Required secret missing: $SECRET"
    exit 1
  }
done
```

**Post-deploy stack verification** (runs after every `cdk deploy`):

```bash
STACKS=(
  "Aiops-${ENV_NAME}-Network"
  "Aiops-${ENV_NAME}-Data"
  "Aiops-${ENV_NAME}-Compute"
)
for STACK in "${STACKS[@]}"; do
  STATUS=$(aws cloudformation describe-stacks \
            --stack-name "$STACK" \
            --query "Stacks[0].StackStatus" --output text 2>/dev/null || echo "NOT_FOUND")
  if [[ "$STATUS" != *_COMPLETE ]]; then
    echo "::error::Stack $STACK is in unexpected state: $STATUS"
    exit 1
  fi
done
```

#### 3.4 `cleanup-stuck-stack.yml` — Stuck-Stack Recovery

```yaml
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      action:
        required: true
        type: string  # "preflight" | "remediate"
```

State-machine logic:

```
For each stack in [Network, Data, Compute, Observability, Monitoring, Simulation]:

  STATUS = aws cloudformation describe-stacks --stack-name Aiops-{env}-{Name}

  ROLLBACK_COMPLETE / CREATE_FAILED:
    → aws cloudformation delete-stack --stack-name ...
    → aws cloudformation wait stack-delete-complete --stack-name ...
    → return success

  ROLLBACK_FAILED / DELETE_FAILED:
    → aws cloudformation delete-stack --stack-name ... \
        --retain-resources $(list_stuck_resources)
    → aws cloudformation wait stack-delete-complete --stack-name ...
    → return success

  *_IN_PROGRESS:
    → echo "::error::Stack {Name} is in {STATUS} — another deployment is in progress."
    → exit 1  ← FAIL IMMEDIATELY, do not attempt deletion

  *_COMPLETE / DOES_NOT_EXIST:
    → no-op, stack is healthy
```

The `*_IN_PROGRESS` early-exit prevents the recovery workflow from interfering with a
legitimate in-flight CloudFormation operation.

#### 3.5 `prod-deploy.yml` — Production Workflow

```
on:
  pull_request:
    types: [closed]
    branches: [main]
    # Only when PR is merged from a release/* branch
  workflow_dispatch:
    inputs:
      commit_sha:
        description: "Commit SHA to deploy (empty = HEAD)"
        type: string
        required: false

jobs:
  validate:       → validate inputs, resolve commit SHA
  python-test:    → pytest -m unit -m property (timeout: 15m)
  cdk-test:       → pytest -m cdk (timeout: 15m)
  prod-approval:  → environment: prod (GitHub Environment with required reviewers)
  deploy:         → checkout commit_sha → setup-cdk → OIDC → secrets-check
                    → sha-gap → cdk synth --lookups false → cdk deploy --all
                    → post-deploy verify → update-sha (timeout: 90m)
  upload-artifact:→ upload cdk.out as workflow artifact (retention: 365d)
```

The `prod-approval` job uses a GitHub Environment named `prod`. Deployment protection
rules on that environment define required reviewers. The job simply displays deployment
metadata (image tag, commit SHA, commit message) and waits for approval.

`commit_sha` rollback input: when populated, `deploy` checks out that SHA via
`actions/checkout@v4 with: ref: ${{ inputs.commit_sha }}`. This enables emergency
rollback to any previously-deployed commit without modifying `main`.

---

## Data Models

### FrameworkConfig Fields

| Field | Source | Default |
|---|---|---|
| `model_id` | SSM `/aiops/{env}/MODEL_ID` | — (required) |
| `agentcore_gateway_id` | env `AGENTCORE_GATEWAY_ID` | — (required) |
| `agentcore_memory_id` | env `AGENTCORE_MEMORY_ID` | — (required) |
| `dynamodb_workflow_table` | env `DYNAMODB_WORKFLOW_TABLE` | — (required) |
| `aws_region` | env `AWS_REGION` | `us-east-1` |
| `stm_k` | `agent.yaml` `framework.stm_k` | `4` |
| `temperature` | `agent.yaml` `framework.temperature` | `0.2` |
| `retry_max_attempts` | `agent.yaml` `framework.retry_max_attempts` | `3` |
| `async_turns` | `agent.yaml` `framework.async_turns` | `True` |
| `prompt_cache` | `agent.yaml` `framework.prompt_cache` | `True` |
| `ltm_enabled` | `agent.yaml` `framework.ltm_enabled` | `True` |
| `soft_fail_on_max_tokens` | `agent.yaml` `framework.soft_fail_on_max_tokens` | `True` |
| `max_tool_timeout` | `agent.yaml` `framework.max_tool_timeout` | `60` |

### DynamoDB Turn Lock Item

```
Table: ${DYNAMODB_WORKFLOW_TABLE}
PK:    workflow_id (String)

Item schema:
{
  "workflow_id": "wf-abc123",           ← partition key
  "ttl":         1717000320,            ← epoch + 120s, Number
  "locked_at":   "2024-05-29T12:00:00Z",
  "agent_name":  "correlator"
}

Write: PutItem with ConditionExpression="attribute_not_exists(workflow_id)"
Delete: DeleteItem with Key={"workflow_id": workflow_id}
```

### AgentCore Memory Schema

**STM** (Short-Term Memory):
- Source: `MemoryClient.list_events(session_id=session_id, actor_id=actor_id)`
- Truncation: take last `stm_k` events sorted by timestamp descending
- Format: list of `{role: user|assistant, content: str}` event payloads

**LTM** (Long-Term Memory):
- Source: `MemoryClient.retrieve_records(namespace=f"{agent_name}/{session_id}", search_query=user_prompt)`
- Format: plain text concatenation of `record.content.text` for top-k results
- Disabled when `cfg.ltm_enabled is False`

### SSM Parameter Naming Convention

```
/aiops/{environment}/MODEL_ID
/aiops/{environment}/workflow-table-arn
/aiops/{environment}/main-queue-arn
/aiops/{environment}/dlq-arn
/aiops/{environment}/log-group-arn
/aiops/{environment}/cluster-arn
/aiops/{environment}/{resource-name}   ← auto-discovered resources
```

### resource.yaml Schema

```yaml
# src/resources/<name>/resource.yaml
type: lambda           # must be a key in RESOURCE_TYPE_REGISTRY
description: "One-line description of what this Lambda does."
# Optional additional fields consumed by the specific stack class:
runtime: python3.11
handler: index.handler
memory_mb: 256
timeout_seconds: 60
```

Validation rules enforced by `resource_discovery.py`:
- Directory name matches `^[a-z][a-z0-9_]*$`
- `type` field present and non-empty
- `description` field present and non-empty

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid
executions of a system — essentially, a formal statement about what the system should
do. Properties serve as the bridge between human-readable specifications and
machine-verifiable correctness guarantees.*

The framework uses **Hypothesis** (already in `pyproject.toml` as `hypothesis==6.112.1`)
for property-based testing. Each property test runs a minimum of 100 iterations.
Tests are tagged `@pytest.mark.property` and reference their design property in a comment.

**Property reflection**: After deriving properties from each acceptance criterion, the
following consolidations were made to eliminate redundancy:

- Properties 1.2 and 6.5 (lru_cache identity) are combined into **Property 2**.
- Properties 4.4 and 4.5 (build_model invariants) are combined into **Property 4** since
  both test return-value invariants of the same function.
- Properties 15.3 (branch→env mapping) and 17.2 (SHA-gap detection) are kept separate
  because they test distinct pure functions with different input domains.

---

### Property 1: STM is always capped at stm_k

*For any* `stm_k` value in the range [1, 20] and any list of memory events of arbitrary
length, calling `load_memory()` with that `stm_k` setting returns a STM list whose length
is at most `stm_k`.

**Validates: Requirements 3.2**

---

### Property 2: Config factory is idempotent (lru_cache identity)

*For any* set of environment variables that produce a valid `FrameworkConfig`, calling
`get_framework_config()` twice in the same process returns the exact same object instance
(Python `is` identity), confirming the `@lru_cache(maxsize=1)` contract holds and SSM is
not called more than once.

**Validates: Requirements 1.2, 6.5**

---

### Property 3: SSM error messages include the parameter path

*For any* SSM parameter path string `p`, when the SSM client raises a `ClientError` for
that path, the resulting `ConfigLoadError` message contains `p` as a substring.

**Validates: Requirements 1.4**

---

### Property 4: build_model always enforces cache_tools and retry strategy

*For any* `FrameworkConfig` with any combination of `model_id`, `temperature`, and
`retry_max_attempts`, calling `build_model(cfg)` returns a `BedrockModel` where:
- `cache_tools` equals `"default"`,
- `cache_config.strategy` equals `"auto"`,
- `retry_strategy.initial_delay` equals `10`,
- `retry_strategy.max_delay` equals `60`.

**Validates: Requirements 4.4, 4.5**

---

### Property 5: assemble_system_prompt preserves content ordering

*For any* raw prompt containing `DYNAMIC_CONTEXT_MARKER`, any LTM summary string, any
STM event list, and any dynamic context string, calling `assemble_system_prompt()` returns
a three-element list where:
- element 0 is `{"text": <static_prefix>}`,
- element 1 is `{"cachePoint": {"type": "default"}}`,
- element 2 is a `{"text": ...}` block containing LTM, then STM, then dynamic_context
  in that order as substrings.

**Validates: Requirements 4.2**

---

### Property 6: flush_memory strips DYNAMIC_CONTEXT_MARKER from all messages

*For any* list of message dicts where one or more `content` fields contain the string
`DYNAMIC_CONTEXT_MARKER`, the payload passed to `MemoryClient.create_event()` by
`flush_memory()` contains no occurrence of `DYNAMIC_CONTEXT_MARKER`.

**Validates: Requirements 3.4**

---

### Property 7: run_turn releases lock even on agent exception

*For any* `workflow_id` string and any agent callback that raises an arbitrary exception,
after `run_turn()` returns (or propagates), the DynamoDB `DeleteItem` call for that
`workflow_id` has been executed exactly once.

**Validates: Requirements 5.4**

---

### Property 8: run_turn returns ACK without executing agent when lock is held

*For any* `workflow_id` string, when the DynamoDB `PutItem` raises
`ConditionalCheckFailedException` (simulating a held lock), `run_turn()` returns an ACK
response and the agent callback is never invoked.

**Validates: Requirements 5.2**

---

### Property 9: emit_token_usage always emits all five metric fields

*For any* combination of non-negative integers for `input_tokens`, `output_tokens`,
`cache_read_tokens`, and `cache_write_tokens`, calling `emit_token_usage()` produces EMF
output that contains all five keys: `InputTokens`, `OutputTokens`, `CacheReadTokens`,
`CacheWriteTokens`, and `EstimatedCostUsd`.

**Validates: Requirements 5.6**

---

### Property 10: run_agent aborts immediately when pre_invoke_guard returns non-None

*For any* non-empty dict `guard_response`, when `pre_invoke_guard.check()` returns
`guard_response`, `run_agent()` returns `guard_response` without invoking any of the
subsequent 21 steps (verified by asserting none of the step mocks are called).

**Validates: Requirements 6.6**

---

### Property 11: Protocol hook validation rejects all non-conforming objects

*For any* object that is missing at least one method required by one of the five Protocol
classes, passing that object to `run_agent()` as the corresponding hook raises `TypeError`
before any agent work is performed.

**Validates: Requirements 1.6**

---

### Property 12: stage_resource_code is content-hash deterministic

*For any* source directory with a fixed set of `.py`, `.txt`, and `.json` files with fixed
content, calling `stage_resource_code()` twice returns the same build path, and the
`pip install` subprocess is invoked at most once (on the first call; the second call
returns the cached path without re-running `pip install`).

**Validates: Requirements 11.1, 11.2**

---

### Property 13: resource_discovery rejects all invalid resource names

*For any* string `s` that does not match the pattern `^[a-z][a-z0-9_]*$`, calling
`discover_resources()` with a resource whose directory is named `s` raises a `ValueError`
whose message includes `s`.

**Validates: Requirements 12.4**

---

### Property 14: detect-changes correctly maps changed files to stack flags

*For any* set of file paths from the git diff output, the `detect-changes` logic sets the
`network` output flag to `True` if and only if at least one path matches the
`src/agentic_ai/infra/stacks/network_stack.py` pattern (and correspondingly for each
other stack), and sets `force_all=True` if and only if the before-SHA is the zero SHA or
a SHA gap is detected.

**Validates: Requirements 15.1, 15.2**

---

### Property 15: resolve-env maps every valid branch ref to the correct environment

*For any* GitHub ref string in the set {`refs/heads/main`, `refs/heads/staging`,
`refs/tags/v*.*.*`, `refs/heads/<other>`}, the `resolve-env` logic maps it to exactly one
of {`dev`, `staging`, `prod`} according to the branch strategy table, with no ref
producing an empty or undefined environment output.

**Validates: Requirements 15.3**

---

### Property 16: cleanup-stuck-stack fails immediately for all IN_PROGRESS states

*For any* CloudFormation stack status string ending in `_IN_PROGRESS`, the
`cleanup-stuck-stack` logic exits with a non-zero status code without calling
`delete_stack`, `delete_stack` with `--retain-resources`, or any other mutating API.

**Validates: Requirements 16.4**

---

### Property 17: cleanup-stuck-stack deletes stacks in all terminal error states

*For any* stack in `ROLLBACK_COMPLETE` or `CREATE_FAILED` state (mocked), the cleanup
logic calls `delete_stack` and waits for `stack-delete-complete` before returning. For
any stack in `ROLLBACK_FAILED` or `DELETE_FAILED` state, it calls `delete_stack` with the
retain-resources flag set.

**Validates: Requirements 16.2, 16.3**

---

### Property 18: SHA-gap detection sets FORCE_ALL for any non-empty SHA divergence

*For any* pair `(last_deployed_sha, event_before_sha)` where both are non-empty strings
and `last_deployed_sha != event_before_sha`, the SHA-gap detection script sets
`FORCE_ALL=true`. When either value is empty or they are equal, `FORCE_ALL` is not set.

**Validates: Requirements 17.2**

---

### Property 19: post-deploy verification fails for any non-COMPLETE stack state

*For any* set of deployed stack names where at least one stack has a status that does not
end in `_COMPLETE` (e.g., `ROLLBACK_IN_PROGRESS`, `UPDATE_ROLLBACK_COMPLETE`,
`DELETE_FAILED`), the post-deploy verification step exits with a non-zero status code and
includes the offending stack name and status in the error output.

**Validates: Requirements 17.4**

---

### Property 20: nag suppressions always include a non-empty reason

*For any* `NagSuppressions.add_*()` call in `nag_suppressions.py`, the dict passed in the
suppression list contains a `reason` key whose value is a non-empty string.

**Validates: Requirements 8.3**

---

## Error Handling

### Agent Framework — Error Taxonomy

| Error | Raised by | Handling |
|---|---|---|
| `ConfigLoadError` | `config.get_framework_config()` | Propagates to AgentCore Runtime; container restarts |
| `TypeError` | `runner.run_agent()` hook validation | Raised at startup before any turn |
| `ConditionalCheckFailedException` | `turn_runner.run_turn()` | Caught, return ACK immediately |
| `botocore.exceptions.ClientError` | Any AWS call | Retry with exponential backoff; log ERROR |
| `asyncio.TimeoutError` | MCP tool call | Log ERROR, set `stop_reason="timeout"`, flush memory |
| `StrandsMaxTokensError` | `agent(prompt)` | Soft-fail to `"token budget exhausted"` if enabled |
| Any uncaught exception | Step 14 agent invocation | Log ERROR; steps 15–22 still run (finally) |

### CDK — Error Taxonomy

| Error | Raised by | Handling |
|---|---|---|
| `ValueError` | `validate_cdk_context()` | CDK app exits non-zero; CI fails |
| `ValueError` | `resource_discovery.discover_resources()` | CDK app exits non-zero; CI fails |
| `ValueError` | `staging.stage_resource_code()` | CDK app exits non-zero; CI fails |
| CDK Nag violation | `AwsSolutionsChecks` | `cdk synth` fails with violation list |
| SSM parameter not found | `value_for_string_parameter()` | CloudFormation deploy fails at changeset |

### CI/CD — Error Taxonomy

| Error | Job | Handling |
|---|---|---|
| Missing secret | secrets-check step | `exit 1` before any CDK deploy |
| SHA gap detected | sha-gap step | Set `FORCE_ALL=true`, continue |
| Stack in `*_IN_PROGRESS` | cleanup-stuck-stack | `exit 1`, block deploy |
| Stack in non-`*_COMPLETE` after deploy | post-deploy verify | `exit 1`, mark run failed |
| `workflow_dispatch` with bad `commit_sha` | validate job | `exit 1` with descriptive message |
| Deploy job timeout (90m) | deploy | GitHub Actions cancels job, concurrency group releases |

### Timeout and Retry Policy

All external service calls in the agent framework use this policy:

```python
# boto3 config pattern
config = botocore.config.Config(
    connect_timeout=5,
    read_timeout=30,
    retries={"max_attempts": 3, "mode": "adaptive"},
)
```

SSM parameter reads: `connect_timeout=5s`, `read_timeout=10s`, `max_attempts=2`.
DynamoDB (turn lock): `connect_timeout=2s`, `read_timeout=5s`, `max_attempts=3`.
MemoryClient (STM/LTM): loaded concurrently with `ThreadPoolExecutor(max_workers=2)`,
each with a 10-second timeout enforced by `Future.result(timeout=10)`.

---

## Testing Strategy

### Test Layout

```
tests/
  unit/
    agent_framework/
      test_hooks.py
      test_config.py
      test_mcp_factory.py
      test_memory_manager.py
      test_prompt_assembler.py
      test_model_builder.py
      test_turn_runner.py
      test_observability.py
      test_runner.py
  property/
    agent_framework/
      test_props_config.py       ← Properties 1, 2, 3
      test_props_model_builder.py← Property 4
      test_props_prompt.py       ← Properties 5, 6
      test_props_turn_runner.py  ← Properties 7, 8
      test_props_observability.py← Property 9
      test_props_runner.py       ← Properties 10, 11
    infra/
      test_props_staging.py      ← Property 12
      test_props_discovery.py    ← Property 13
    cicd/
      test_props_detect_changes.py← Properties 14, 15
      test_props_cleanup_stack.py ← Properties 16, 17
      test_props_sha_gap.py      ← Property 18
      test_props_post_deploy.py  ← Property 19
      test_props_nag.py          ← Property 20
  cdk/
    conftest.py
    test_network_stack.py
    test_data_stack.py
    test_compute_stack.py
    test_observability_stack.py
    test_monitoring_stack.py
    test_simulation_stack.py
```

### Unit Test Mocking Strategy

All AWS service clients are mocked at the boundary, never with live AWS calls in unit tests:

```python
# Standard mock pattern for agent framework tests
@pytest.fixture
def mock_ssm(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("boto3.client", lambda service, **kw: client)
    return client

@pytest.fixture
def mock_dynamodb_table(monkeypatch):
    table = MagicMock()
    table.put_item.return_value = {}
    monkeypatch.setattr(
        "agentic_ai.agent_framework.turn_runner._get_table",
        lambda cfg: table,
    )
    return table

@pytest.fixture
def mock_memory_client(monkeypatch):
    client = MagicMock()
    client.list_events.return_value = {"events": []}
    client.retrieve_records.return_value = {"memoryRecords": []}
    monkeypatch.setattr(
        "agentic_ai.agent_framework.memory_manager._get_memory_client",
        lambda cfg: client,
    )
    return client
```

`BedrockAgentCoreApp` and `strands.Agent` are mocked to isolate framework logic from
AgentCore Runtime and Bedrock SDK behaviour.

### Property-Based Test Configuration

```python
# Example property test for STM cap (Property 1)
from hypothesis import given, settings
from hypothesis import strategies as st

@pytest.mark.property
@settings(max_examples=200, deadline=None)
@given(
    stm_k=st.integers(min_value=1, max_value=20),
    event_count=st.integers(min_value=0, max_value=100),
)
def test_stm_always_capped(
    mock_memory_client,
    stm_k: int,
    event_count: int,
) -> None:
    # Feature: implement-prompts, Property 1: STM is always capped at stm_k
    mock_memory_client.list_events.return_value = {
        "events": [{"role": "user", "content": f"msg {i}"} for i in range(event_count)]
    }
    cfg = make_test_config(stm_k=stm_k)
    stm_events, _ = load_memory(cfg, session_id="s1", actor_id="a1")
    assert len(stm_events) <= stm_k
```

All property tests use `@settings(max_examples=200, deadline=None)` (200 iterations,
no per-example time limit) unless an individual test has justified reason for a lower count.

### CDK Test Configuration

CDK unit tests run with `pytest -m cdk`. Each stack test:
1. Synthesizes the stack with a minimal test context (dev environment, fake account/region).
2. Captures the template with `Template.from_stack(stack)`.
3. Runs snapshot comparison (`pytest-snapshot`).
4. Runs fine-grained assertions for security-critical properties.

Snapshot tests are run in `--snapshot-update` mode only when intentional changes are made.
CI always runs in comparison mode (`pytest -m cdk` without `--snapshot-update`).

### CI Test Gates

| Pytest mark | When runs | Blocks deploy if failing |
|---|---|---|
| `unit` | Every push/PR | Yes |
| `property` | Every push/PR | Yes |
| `cdk` | Every push/PR | Yes |
| `integration` | Post-deploy in dev only | Alerts on failure, does not roll back |

### Import Policy Enforcement

A dedicated test in `tests/unit/agent_framework/test_import_policy.py` enforces that
`SigV4HttpxAuth` is never imported outside `mcp_factory.py`:

```python
import ast
from pathlib import Path

def test_sigv4auth_only_in_mcp_factory():
    # Feature: implement-prompts — enforces Requirement 7.5
    src_root = Path("src")
    violations = []
    for py_file in src_root.rglob("*.py"):
        if py_file.name == "mcp_factory.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        if "SigV4HttpxAuth" in source:
            violations.append(str(py_file))
    assert not violations, (
        f"SigV4HttpxAuth found outside mcp_factory.py: {violations}"
    )
```

This test is marked `@pytest.mark.unit` so it runs on every push and blocks the pipeline
if the import policy is violated.
