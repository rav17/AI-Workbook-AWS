# Requirements Document

## Introduction

This spec covers three complementary areas that together close all implementation gaps in the
AIOps Self-Healing Infrastructure project as described in the three `prompts/` documents:

1. **AgentCore Agent Framework** — a shared Python framework under
   `src/agentic_ai/agent_framework/` so every AgentCore Runtime entrypoint is ~15 lines, with
   all infrastructure boilerplate (memory, caching, observability, turn locking) enforced by
   code and not by convention.

2. **CDK Best Practices** — filling the remaining gaps in the existing
   `src/agentic_ai/infra/` CDK code: CDK Nag compliance checks, centralised nag suppressions,
   SSM-based cross-stack reference migration, CDK unit tests, content-hash Lambda packaging,
   committed `cdk.context.json`, and an auto-discovery resource pattern.

3. **CI/CD Replication** — closing the gaps in `.github/workflows/`: a reusable composite
   action, per-job OIDC scoping, concurrency controls, surgical change detection, PR diff
   comments, stuck-stack recovery, a dedicated production workflow, rollback inputs, SHA-gap
   detection, Secrets Manager pre-flight, post-deploy verification, and job timeouts.

All implementation must follow the project's engineering standards: ruff formatting, full
type hints, Google-style docstrings, structured JSON logging, no hardcoded secrets, and
least-privilege IAM.

---

## Glossary

- **Agent_Framework**: The shared Python package at `src/agentic_ai/agent_framework/`
  implementing all AgentCore Runtime boilerplate.
- **AgentCore_Runtime**: AWS Bedrock AgentCore Runtime container hosting a single agent.
- **ParsedTurn**: Dataclass carrying the structured fields extracted from a raw AgentCore
  event (user prompt, session ID, dynamic context, etc.).
- **DYNAMIC_CONTEXT_MARKER**: A sentinel string in each agent's `system_prompt.py` that
  separates the cacheable static prompt prefix from the non-cacheable dynamic suffix.
- **STM**: Short-Term Memory — the last *stm_k* conversation turns loaded from AgentCore
  Memory per turn.
- **LTM**: Long-Term Memory — the rolling semantic summary loaded from AgentCore Memory.
- **Turn_Lock**: A DynamoDB item with a 120-second TTL used to prevent two concurrent agent
  turns from executing for the same workflow.
- **CDK_Nag**: The `cdk-nag` library's `AwsSolutionsChecks` that enforces security best
  practices during `cdk synth`.
- **CDK_Context**: The `cdk.json` / `cdk.context.json` files driving environment-specific
  configuration.
- **Staging**: A GitHub Actions step that packages Lambda code into a `.build/` directory
  using content-hash gating to skip unchanged packages.
- **OIDC**: OpenID Connect — the credential mechanism for GitHub Actions to assume AWS IAM
  roles without static access keys.
- **SHA_Gap**: A condition where one or more commits were pushed to the branch since the
  last successfully deployed SHA, requiring a full-stack deploy to ensure none are missed.
- **Stuck_Stack**: A CloudFormation stack in a terminal error state
  (`ROLLBACK_COMPLETE`, `CREATE_FAILED`, `ROLLBACK_FAILED`, `DELETE_FAILED`) that blocks
  further deploys until remediated.

---

## Requirements

### Requirement 1: Agent Framework — Core Protocols and Configuration

**User Story:** As an agent developer, I want a shared set of typed hook Protocols and a
lazy-loaded configuration object, so that every agent entrypoint can rely on a stable,
type-checked contract from the first line of code.

#### Acceptance Criteria

1. THE Agent_Framework SHALL provide a `hooks.py` module that defines the `ParsedTurn`
   dataclass and five `@runtime_checkable` Protocol classes: `SystemPromptBuilder`,
   `SkillsBuilder`, `ToolFilter`, `PayloadParser`, and `PreInvokeGuard`.
2. THE Agent_Framework SHALL provide a `config.py` module that defines a frozen
   `FrameworkConfig` dataclass whose factory function is decorated with
   `@functools.lru_cache(maxsize=1)`.
3. WHEN `FrameworkConfig` is instantiated, THE Agent_Framework SHALL read SSM parameters
   and environment variables only inside the `@app.entrypoint` callback, never at module
   import time.
4. IF any required SSM parameter is unreachable at instantiation time, THE Agent_Framework
   SHALL raise a descriptive exception that includes the parameter path but not its value.
5. THE Agent_Framework SHALL export `run_agent()` and all five Protocol classes from its
   `__init__.py` as the sole public API.
6. WHEN a hook argument passed to `run_agent()` does not satisfy the corresponding
   `@runtime_checkable` Protocol, THE Agent_Framework SHALL raise a `TypeError` at startup
   before processing any turn.

---

### Requirement 2: Agent Framework — MCP Gateway Client Factory

**User Story:** As an agent developer, I want MCP client creation and SigV4 authentication
to live in a single shared module, so that agents cannot accidentally bypass gateway
authentication or duplicate auth logic.

#### Acceptance Criteria

1. THE Agent_Framework SHALL provide a `mcp_factory.py` module containing a
   `SigV4HttpxAuth(httpx.Auth)` class that signs httpx requests with AWS SigV4 credentials.
2. THE Agent_Framework SHALL provide a `create_mcp_client(cfg: FrameworkConfig) -> MCPClient`
   function in `mcp_factory.py` that returns a configured, not-yet-started MCP client.
3. THE `SigV4HttpxAuth` class SHALL NOT appear in any agent entrypoint or any module outside
   `mcp_factory.py`.
4. WHEN an MCP client is created, THE Agent_Framework SHALL require callers to call
   `mcp_client.start()` before listing tools and `mcp_client.stop()` inside a `finally`
   block.

---

### Requirement 3: Agent Framework — Memory Management

**User Story:** As an agent developer, I want memory load and flush to be handled by the
framework in a safe, bounded way, so that STM never grows unboundedly and conversation
history is never silently lost on errors.

#### Acceptance Criteria

1. THE Agent_Framework SHALL provide a `memory_manager.py` module with `load_memory()` and
   `flush_memory()` functions.
2. WHEN `load_memory()` is called, THE Agent_Framework SHALL fetch STM and LTM concurrently
   and cap STM at `stm_k` turns (default 4).
3. THE Agent_Framework SHALL NEVER use the AgentCore `SessionManager` hook; all memory I/O
   SHALL go through `MemoryClient` directly.
4. WHEN `flush_memory()` is called, THE Agent_Framework SHALL strip the
   `DYNAMIC_CONTEXT_MARKER` and any system-prompt markers from agent messages before writing
   to AgentCore Memory.
5. THE `run_agent()` orchestrator SHALL call `flush_memory()` inside a `finally` block so
   that conversation history is written even when the agent turn raises an exception.

---

### Requirement 4: Agent Framework — Prompt Assembly and Model Building

**User Story:** As an agent developer, I want the framework to automatically inject Bedrock
prompt caching and memory into the system prompt, so that I cannot accidentally disable
prompt caching or corrupt the memory injection order.

#### Acceptance Criteria

1. THE Agent_Framework SHALL provide a `prompt_assembler.py` module with an
   `assemble_system_prompt()` function.
2. WHEN a `DYNAMIC_CONTEXT_MARKER` is present in the raw prompt, THE Agent_Framework SHALL
   return a content list with a static part, a Bedrock cache point
   (`{"cachePoint": {"type": "default"}}`), and a dynamic part containing LTM summary, STM
   turns, and `dynamic_context` in that order.
3. WHEN a `DYNAMIC_CONTEXT_MARKER` is absent from the raw prompt, THE Agent_Framework SHALL
   log a WARNING and return the raw prompt as a plain string without raising an exception.
4. THE Agent_Framework SHALL provide a `model_builder.py` module with a `build_model()`
   function that always sets `cache_tools="default"` and `CacheConfig(strategy="auto")` on
   the returned `BedrockModel`.
5. THE `build_model()` function SHALL always return a `ModelRetryStrategy` with configurable
   `retry_max_attempts` (default 3), `initial_delay=10`, and `max_delay=60`.

---

### Requirement 5: Agent Framework — Turn Runner and Observability

**User Story:** As a platform engineer, I want every agent turn to acquire a distributed
lock, emit standardised metrics, and dispatch asynchronously, so that concurrent duplicate
turns are rejected and every turn's latency and token usage are visible in CloudWatch.

#### Acceptance Criteria

1. THE Agent_Framework SHALL provide a `turn_runner.py` module with a `run_turn()` function
   that acquires a DynamoDB turn lock before executing agent work.
2. WHEN a turn lock is already held for the same `workflow_id`, THE Agent_Framework SHALL
   return an ACK response immediately without executing the agent.
3. WHEN `async_turns=True` (default), THE Agent_Framework SHALL dispatch agent work on a
   daemon thread that creates its own `asyncio` event loop, returning an ACK to AgentCore
   immediately.
4. THE Agent_Framework SHALL release the turn lock inside a `finally` block so that a
   crashed or excepted turn never leaves a dangling lock beyond the 120-second TTL.
5. THE Agent_Framework SHALL provide an `observability.py` module with an
   `ObservabilityTrace` class, `emit_token_usage()`, `emit_turn_latency()`, and
   `log_cache_hit_rate()` functions.
6. WHEN `emit_token_usage()` is called, THE Agent_Framework SHALL emit an EMF CloudWatch
   metric containing `input_tokens`, `output_tokens`, `cache_read_tokens`,
   `cache_write_tokens`, and `estimated_cost_usd` (when pricing env vars are present).
7. WHEN `log_cache_hit_rate()` detects `cache_read_tokens == 0`, THE Agent_Framework SHALL
   log a WARNING indicating that Bedrock prompt caching is not working.

---

### Requirement 6: Agent Framework — Orchestrator (run_agent)

**User Story:** As an agent developer, I want a single `run_agent()` call to handle the
complete 22-step turn lifecycle, so that I only need to provide a system prompt builder and
the framework handles everything else safely.

#### Acceptance Criteria

1. THE Agent_Framework SHALL provide a `runner.py` module with a `run_agent()` function as
   the sole function that agent entrypoints call.
2. WHEN `run_agent()` processes a turn, THE Agent_Framework SHALL execute the 22 steps in
   this order: pre_invoke_guard → payload_parser → load_config → load_agent_yaml →
   build_model → create_mcp_client → list_tools → tool_filter → load_memory →
   system_prompt_builder → assemble_system_prompt → skills_builder → build Agent →
   invoke agent synchronously → flush_memory (finally) → write_conversation_turn (finally)
   → emit_token_usage → emit_turn_latency → log_cache_hit_rate → stop_mcp_client (finally)
   → emit_turn_completion_event (finally) → release_turn_lock (finally).
3. THE `run_agent()` function SHALL call the Strands `Agent` synchronously using
   `agent(prompt)` and SHALL NOT call `await agent.arun()`.
4. WHEN the agent result's `stop_reason` equals `"max_tokens"` and
   `framework.soft_fail_on_max_tokens` is `True` (default), THE Agent_Framework SHALL
   return a success response with body `"token budget exhausted"` instead of raising.
5. THE Agent_Framework SHALL read per-agent tuning from the `framework:` section of the
   agent's `agent.yaml` file and cache the parsed result for the lifetime of the process.
6. WHEN `pre_invoke_guard` returns a non-`None` dict, THE Agent_Framework SHALL abort the
   turn and return that dict as the response without executing any further steps.

---

### Requirement 7: Agent Framework — Per-Agent File Contract

**User Story:** As an agent developer, I want a well-defined, minimal file contract per
agent directory, so that adding a new agent requires only creating a directory with YAML and
Python files and no changes to the framework or CDK code.

#### Acceptance Criteria

1. THE Agent_Framework SHALL require each agent directory to contain `agent.yaml`,
   `system_prompt.py` (with `DYNAMIC_CONTEXT_MARKER` and `build_system_prompt()`), and
   `agentcore_entrypoint.py`.
2. THE `agentcore_entrypoint.py` for any agent SHALL contain no more than 20 lines and SHALL
   consist solely of imports and a single `run_agent()` call.
3. THE `agent.yaml` SHALL support a `framework:` subsection for per-agent tuning fields:
   `stm_k`, `temperature`, `retry_max_attempts`, `async_turns`, `prompt_cache`,
   `ltm_enabled`, `soft_fail_on_max_tokens`, and `max_tool_timeout`.
4. THE Agent_Framework SHALL migrate the three existing agents (`correlator.py`,
   `model_router.py`, `reasoning_agent.py`) to the new per-agent file contract by creating
   agent directories with the required files, preserving all existing business logic.
5. WHEN the Agent_Framework discovers an agent entrypoint that imports or instantiates
   `SigV4HttpxAuth` outside of `mcp_factory.py`, THE CI test suite SHALL fail with a
   descriptive assertion error.

---

### Requirement 8: CDK Nag and Centralised Suppressions

**User Story:** As a platform engineer, I want every `cdk synth` to run compliance checks
and report all violations, so that security regressions are caught before they reach AWS.

#### Acceptance Criteria

1. THE CDK_App (`src/agentic_ai/infra/app.py`) SHALL invoke
   `cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))` before `app.synth()`.
2. THE CDK infrastructure SHALL provide an `apply_common_suppressions(stack)` helper
   function in `src/agentic_ai/infra/` that applies all project-wide nag suppressions in one
   place.
3. WHEN a nag suppression is added, THE `apply_common_suppressions()` helper SHALL include
   a `reason` string that explains why the violation is acceptable for this project.
4. WHEN `cdk synth` is run with `AwsSolutionsChecks` enabled, THE CDK stacks SHALL produce
   zero unresolved violations that block synthesis.

---

### Requirement 9: CDK Cross-Stack Reference Migration

**User Story:** As a platform engineer, I want cross-stack ARN sharing to use SSM Parameter
Store instead of CloudFormation constructor parameters where feasible, so that stacks can be
deployed and deleted independently without circular dependency locks.

#### Acceptance Criteria

1. THE CDK stacks SHALL write ARNs of shared resources (e.g., DynamoDB table ARN, SQS queue
   ARN, log group ARN) to SSM parameters under `/aiops/{environment}/` immediately after
   creating each resource.
2. WHEN a downstream stack reads a cross-stack ARN, THE CDK stack SHALL resolve it via
   `ssm.StringParameter.value_for_string_parameter()` using `{{resolve:ssm:...}}` so
   CloudFormation resolves the value at changeset creation rather than synth time.
3. THE CDK stacks SHALL NEVER use `CfnOutput` cross-stack exports (`Fn::ImportValue`) for
   ARN sharing between stacks.
4. FOR deterministic resource names (IAM roles, Lambda functions), THE CDK stacks SHALL
   construct ARNs as plain strings rather than creating L2 cross-stack references, to
   eliminate circular dependency risk.

---

### Requirement 10: CDK Unit Tests

**User Story:** As a platform engineer, I want CDK unit tests to run in CI before every
deploy, so that stack refactors cannot silently change IAM policies, removal policies,
environment variables, or encryption settings.

#### Acceptance Criteria

1. THE CDK codebase SHALL provide unit tests in `tests/cdk/` using
   `aws_cdk.assertions.Template`.
2. THE CDK unit tests SHALL include at least one snapshot test per stack that captures the
   synthesised CloudFormation template as a JSON snapshot.
3. THE CDK unit tests SHALL include fine-grained assertions verifying that each Lambda
   function has `KmsKeyArn` set, that each DynamoDB table has `SSESpecification.SSEEnabled`
   set to `True`, and that each log group has a non-zero retention setting.
4. WHEN the CDK unit tests are run with `pytest -m cdk`, THE test suite SHALL pass with
   zero failures before any stack is deployed.

---

### Requirement 11: CDK Lambda Content-Hash Packaging

**User Story:** As a developer, I want Lambda code packages to be rebuilt only when their
source changes, so that CI deployments are faster and do not redeploy unchanged functions.

#### Acceptance Criteria

1. THE CDK infrastructure SHALL implement a `stage_resource_code()` function in
   `src/agentic_ai/infra/staging.py` that computes a SHA-256 hash over all `.py`, `.txt`,
   and `.json` files in the source directory.
2. WHEN `stage_resource_code()` is called and a build directory with a matching hash already
   exists under `.build/`, THE function SHALL return the cached build path without running
   `pip install` again.
3. WHEN `stage_resource_code()` is called and no matching build directory exists, THE
   function SHALL copy the source, run `pip install -r requirements.txt -t <out>`, and return
   the new build path.
4. THE `.build/` directory SHALL be listed in `.gitignore` so cached build artefacts are
   never committed.

---

### Requirement 12: CDK Context File and Auto-Discovery

**User Story:** As a developer, I want `cdk.context.json` committed to the repository and
auto-discovery of resources from YAML files, so that VPC/subnet lookups are deterministic
across machines and new resources can be added without touching CDK stack code.

#### Acceptance Criteria

1. THE CDK repository SHALL contain a committed `cdk.context.json` populated with the
   resolved VPC, subnet, and availability-zone lookup values for all configured environments.
2. WHEN `cdk synth` is run in CI, THE CI workflow SHALL pass `--lookups false` to prevent
   the synth from making live AWS API calls that would diverge from the committed context.
3. THE CDK infrastructure SHALL implement a `resource_discovery.py` module in
   `src/agentic_ai/infra/` that scans `src/resources/*/resource.yaml` files and returns a
   validated dictionary of resource configurations.
4. THE `resource_discovery.py` module SHALL reject any resource whose directory name does
   not match the pattern `^[a-z][a-z0-9_]*$` or whose `resource.yaml` is missing the `type`
   or `description` fields, raising a `ValueError` with the offending path.
5. THE CDK `app.py` SHALL iterate the discovered resources and instantiate the correct stack
   class using a type registry dictionary, applying `add_dependency()` between discovered
   resource stacks to prevent concurrent CloudFormation mutations on shared resources.

---

### Requirement 13: CI/CD — Reusable Composite Action

**User Story:** As a developer, I want a single composite GitHub Actions action that installs
Python, Node.js, and the CDK CLI, so that all workflow jobs use identical toolchain versions
without duplicating setup steps.

#### Acceptance Criteria

1. THE CI/CD system SHALL provide a composite action at
   `.github/actions/setup-cdk/action.yml` that installs Python 3.11, Node.js 24, and the
   CDK CLI at the version matching `pyproject.toml`'s `aws-cdk-lib` dependency.
2. WHEN the composite action is used in a workflow job, THE action SHALL install CDK Python
   dependencies from `pyproject.toml` (or a requirements file) and verify the CDK CLI
   version is available.
3. THE CI/CD workflows SHALL reference the composite action via
   `./.github/actions/setup-cdk` instead of duplicating Python, Node, and CDK installation
   steps inline.

---

### Requirement 14: CI/CD — OIDC Scoping and Concurrency Controls

**User Story:** As a security engineer, I want `id-token: write` granted only to jobs that
actually assume an AWS role, and deploy jobs to never cancel mid-flight, so that the
principle of least privilege is enforced and torn infrastructure is impossible.

#### Acceptance Criteria

1. THE CI/CD workflows SHALL remove `id-token: write` from workflow-level `permissions`
   blocks and SHALL add it only to the individual jobs that call
   `aws-actions/configure-aws-credentials`.
2. THE CI/CD workflows SHALL add `concurrency.cancel-in-progress: true` to lint, unit-test,
   property-test, CDK-synth, and CDK-test jobs.
3. THE CI/CD workflows SHALL add `concurrency.cancel-in-progress: false` to all deploy jobs
   and all preflight/cleanup jobs, with one concurrency group per environment (e.g.,
   `deploy-dev`, `deploy-staging`, `deploy-prod`).
4. WHEN two deploy runs for the same environment are triggered concurrently, THE CI/CD
   system SHALL queue the second run and wait for the first to finish rather than cancelling
   either.

---

### Requirement 15: CI/CD — Change Detection and Environment Resolution

**User Story:** As a developer, I want the pipeline to detect which CDK stacks changed and
which environment to target, so that only affected stacks are redeployed on each push and
the correct AWS account is targeted without manual input.

#### Acceptance Criteria

1. THE CI/CD workflow SHALL include a `detect-changes` job (non-PR only) that runs
   `git diff --name-only` between `github.event.before` and `HEAD` and outputs one boolean
   flag per CDK stack plus an aggregate `any_change` flag.
2. WHEN `github.event.before` is the zero SHA (force-push or initial push), THE
   `detect-changes` job SHALL set `force_all=true` and treat all stacks as changed.
3. THE CI/CD workflow SHALL include a `resolve-env` job (non-PR only) that maps the triggering
   branch (`main` → `dev`, `staging` → `staging`, `v*.*.*` tags → `prod`) to an
   `env_name` output and a boolean `is_rollback` output based on whether a
   `commit_sha` input was provided.
4. THE CI/CD workflow SHALL include a `cdk-diff` job that runs on pull requests only, posts
   the `cdk diff --all` output as a PR comment using `actions/github-script`, and requires
   only read-only AWS credentials.

---

### Requirement 16: CI/CD — Stuck-Stack Recovery and Production Workflow

**User Story:** As a platform engineer, I want automatic stuck-stack recovery for non-prod
environments and a separate, approval-gated production workflow, so that stale CloudFormation
states never block developer pushes and production changes always require human sign-off.

#### Acceptance Criteria

1. THE CI/CD system SHALL provide a callable workflow at
   `.github/workflows/cleanup-stuck-stack.yml` that accepts `environment` and `action`
   (`preflight` | `remediate`) inputs.
2. WHEN `cleanup-stuck-stack.yml` is triggered and a stack is in `ROLLBACK_COMPLETE` or
   `CREATE_FAILED` state, THE workflow SHALL delete the stack and wait for deletion to
   complete before returning success.
3. WHEN `cleanup-stuck-stack.yml` encounters a stack in `ROLLBACK_FAILED` or `DELETE_FAILED`
   state, THE workflow SHALL attempt deletion with `--retain-resources` for stuck resources.
4. WHEN `cleanup-stuck-stack.yml` encounters a stack in any `*_IN_PROGRESS` state, THE
   workflow SHALL fail immediately with a message indicating that another deployment is in
   progress.
5. THE CI/CD system SHALL provide a dedicated production workflow at
   `.github/workflows/prod-deploy.yml` triggered on merged pull requests from `release/*`
   branches to `main` and on `workflow_dispatch`.
6. THE `prod-deploy.yml` workflow SHALL include a manual approval gate via a GitHub
   Environment with required reviewers before executing any CDK deploy commands.
7. THE `prod-deploy.yml` workflow SHALL upload the `cdk.out` directory as a workflow
   artifact for audit purposes after every production deployment.

---

### Requirement 17: CI/CD — Rollback, SHA-Gap Detection, and Pre-Flight Checks

**User Story:** As a platform engineer, I want the pipeline to detect missed commits, verify
secrets before deploying, validate stack states after deploying, and support emergency
rollback to any known-good SHA, so that gaps in deployment history are caught and
deployments are safe end-to-end.

#### Acceptance Criteria

1. THE CI/CD workflows SHALL add a `workflow_dispatch` input named `commit_sha` to both
   `cd.yml` and `prod-deploy.yml` that, when provided, checks out that specific commit for
   deployment (enabling emergency rollback).
2. WHEN the deploy job starts, THE CI/CD workflow SHALL compare `github.event.before` to the
   last successfully deployed SHA stored as a GitHub Actions environment variable; IF a gap
   exists, THE workflow SHALL set `FORCE_ALL=true` to trigger a full-stack deploy.
3. BEFORE executing `cdk deploy`, THE CI/CD workflow SHALL query AWS Secrets Manager to
   verify that all required secrets exist and are accessible; IF any secret is missing, THE
   workflow SHALL fail with a descriptive error message before any infrastructure changes are
   made.
4. AFTER `cdk deploy` completes, THE CI/CD workflow SHALL query AWS CloudFormation and verify
   that every deployed stack is in a `*_COMPLETE` state; IF any stack is in an error or
   rollback state, THE workflow SHALL fail and surface the stack name and status.
5. ALL jobs in the CI/CD workflows SHALL have a `timeout-minutes` value set; lint and test
   jobs SHALL time out after 15 minutes and deploy jobs after 90 minutes.

---

### Requirement 18: Engineering Standards Compliance

**User Story:** As a team member, I want all new code to comply with the project's
engineering standards, so that the codebase remains consistent and maintainable.

#### Acceptance Criteria

1. ALL Python modules introduced by this spec SHALL pass `ruff check` and `ruff format
   --check` with zero violations.
2. ALL public functions and classes introduced by this spec SHALL have Google-style
   docstrings and full type annotations on every parameter and return value.
3. ALL external service calls (SSM, DynamoDB, AgentCore Memory, Bedrock) introduced by this
   spec SHALL have explicit timeouts, retries, and structured exception handling using
   `except Exception as exc:` (no bare `except:` clauses).
4. ALL new Python modules SHALL use structured JSON logging via the project's
   `JsonFormatter` and SHALL include `incident_id` in log records where an incident context
   is available.
5. NO new code introduced by this spec SHALL hardcode AWS account IDs, region strings,
   secret values, or SSM parameter paths as string literals outside of configuration objects
   or test fixtures.
