# Design Document — bedrock-guardrails-config

## Overview

This feature adds repository-managed Amazon Bedrock Guardrails to the AIOps self-healing
infrastructure. Currently the guardrail resource is created manually outside the repository
and its ID/version are wired in by hand. This design provisions the Bedrock Guardrail
through a new `BedrockGuardrailsStack`, drives its content-filtering policy from a
versioned YAML file (`config/guardrails.yml`), and automatically injects the guardrail
ID and version into the ECS task's environment so `reasoning_agent.py` picks them up
with zero application code changes.

The guardrail provides defense-in-depth content filtering across three enforcement points,
forming a three-layer safety model:

1. **Model layer** — `invoke_model` with `guardrailIdentifier`/`guardrailVersion` blocks
   dangerous content before the model response is returned (existing code, no change).
2. **Execution layer** — `PlanValidator` screens the AI-generated remediation plan against
   regex-based denied-command patterns before SSM execution.
3. **Tool I/O layer** — `BedrockToolGuardrail` calls the standalone `ApplyGuardrail` API
   to screen the serialised plan text before SSM execution (INPUT) and SSM command output
   before storage (OUTPUT), catching PII leakage and policy-violating content at the tool
   boundary using the same provisioned guardrail resource.

`reasoning_agent.py` is not modified. The new `BedrockToolGuardrail` module integrates
into the existing `GuardrailEngine` pipeline as an additional `GuardrailCheck`.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│  Repository                                                         │
│                                                                     │
│  config/guardrails.yml  ──────────────────────────────────────┐    │
│                                                               │    │
│  src/agentic_ai/infra/                                        │    │
│  ├── context.py  (CdkContext + guardrails_enabled)            │    │
│  ├── app.py  (stack wiring)                                   │    │
│  └── stacks/                                                  │    │
│      ├── bedrock_guardrails_stack.py  ◄─────────────────────┘    │
│      └── compute_stack.py  (extended)                             │
│                                                                     │
│  src/guardrails/                                                    │
│  └── bedrock_tool_guardrail.py  (new — Req 9)                      │
└─────────────────────────────────────────────────────────────────────┘
         │ cdk synth
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CloudFormation                                                     │
│                                                                     │
│  Aiops-{env}-BedrockGuardrails                                      │
│  ├── AWS::Bedrock::Guardrail  (aiops-guardrail-{env})               │
│  ├── AWS::SSM::Parameter  (/aiops/{env}/bedrock-guardrail-id)       │
│  └── AWS::SSM::Parameter  (/aiops/{env}/bedrock-guardrail-version)  │
│                                                                     │
│  Aiops-{env}-Compute  (extended)                                    │
│  ├── AWS::ECS::TaskDefinition                                       │
│  │   └── Container env: BEDROCK_GUARDRAIL_ID, _VERSION             │
│  └── AWS::IAM::Policy  (+ bedrock:ApplyGuardrail)                  │
└─────────────────────────────────────────────────────────────────────┘
         │ deploy
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ECS Fargate Task                                                   │
│                                                                     │
│  reasoning_agent.py                                                 │
│  └── AgentConfig reads BEDROCK_GUARDRAIL_ID, _VERSION from env     │
│      └── _invoke_model() passes guardrailIdentifier + Version       │
│          to bedrock-runtime.invoke_model()                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
config/guardrails.yml
        │
        │  yaml.safe_load() at CDK synth time
        ▼
_load_guardrails_config(env: str) → dict
        │
        │  deep-merge: defaults + environments[env]
        ▼
BedrockGuardrailsStack.__init__()
        │
        │  CfnGuardrail(blocked_topics_config, content_policy_config,
        │               word_policy_config, sensitive_info_policy_config)
        ▼
AWS::Bedrock::Guardrail  (deploy time)
        │
        ├─► SSM /aiops/{env}/bedrock-guardrail-id   = guardrail.ref
        └─► SSM /aiops/{env}/bedrock-guardrail-version = "DRAFT"
                │
                │  stack.guardrail_id, stack.guardrail_version properties
                ▼
        ComputeStack (extended)
                │
                │  environment={BEDROCK_GUARDRAIL_ID: ..., BEDROCK_GUARDRAIL_VERSION: ...}
                ▼
        AWS::ECS::TaskDefinition container
                │
                │  os.environ read at container startup
                ▼
        ┌──────────────────────────────────────────────────────────┐
        │  Three enforcement points share the same guardrail resource │
        │                                                            │
        │  1. reasoning_agent.py                                     │
        │     └── invoke_model(guardrailIdentifier, guardrailVersion)│
        │         → Bedrock enforces at model inference time         │
        │                                                            │
        │  2. GuardrailEngine → PlanValidator                        │
        │     └── regex-based denied-command screening               │
        │                                                            │
        │  3. GuardrailEngine → BedrockToolGuardrail (new)           │
        │     ├── ApplyGuardrail(source=INPUT, plan text)            │
        │     │   → blocks if GUARDRAIL_INTERVENED                   │
        │     ├── SSMExecutor.execute(plan)                          │
        │     └── ApplyGuardrail(source=OUTPUT, ssm stdout)          │
        │         → redacts if GUARDRAIL_INTERVENED                  │
        └──────────────────────────────────────────────────────────┘
```

### Deployment Order

```
NetworkStack  →  DataStack  →  BedrockGuardrailsStack  →  ComputeStack
                                      ↑
                              (new, inserted here)
                              compute_stack.add_dependency(guardrails_stack)
```

---

## Components and Interfaces

### 1. `config/guardrails.yml`

A new YAML configuration file following the structure of `config/denied_commands.yml`.
Ops engineers edit this file to tune guardrail policy per environment without touching
CDK Python code.

**Schema:**

```yaml
defaults:
  blocked_topics:
    - name: string          # Short identifier
      definition: string    # Plain-English description for Bedrock
      examples:             # List of example phrases
        - string
      type: DENY            # Always DENY per the Bedrock API

  content_filters:
    HATE:         NONE | LOW | MEDIUM | HIGH
    INSULTS:      NONE | LOW | MEDIUM | HIGH
    SEXUAL:       NONE | LOW | MEDIUM | HIGH
    VIOLENCE:     NONE | LOW | MEDIUM | HIGH
    MISCONDUCT:   NONE | LOW | MEDIUM | HIGH
    PROMPT_ATTACK: NONE | LOW | MEDIUM | HIGH

  word_policy:
    managed_lists:
      - PROFANITY           # At minimum; PROFANITY is always present
    custom_words:           # Optional additional blocked words
      - string

  sensitive_info_types:
    - type: string          # Bedrock PII entity type (e.g. EMAIL, PHONE, AWS_ACCESS_KEY)
      action: ANONYMIZE | BLOCK

environments:
  dev:
    content_filters:        # Only keys that differ from defaults
      HATE: LOW
      ...
  staging:
    content_filters:
      HATE: MEDIUM
      ...
  prod:
    content_filters:
      HATE: HIGH
      ...
```

**Per-environment policy strengths:**

| Environment | Content Filter Strength | Purpose                              |
|-------------|------------------------|--------------------------------------|
| `dev`       | `LOW` for all          | Permissive — developer iteration     |
| `staging`   | `MEDIUM` for all       | Realistic pre-production policy      |
| `prod`      | `HIGH` for all         | Strictest safe-messaging enforcement |

The `blocked_topics` and `word_policy` sections are defined in `defaults` and inherit
to all environments unless overridden. The `prod` environment override enables the full
blocked-topics and word-policy lists.

---

### 2. `_load_guardrails_config(env: str) -> dict`

A pure function defined at module level inside `bedrock_guardrails_stack.py`. It has
no CDK dependencies and can be tested independently of CDK stack synthesis.

```python
def _load_guardrails_config(env: str) -> dict:
    """Load and deep-merge guardrails configuration for the given environment.

    Reads config/guardrails.yml relative to the repository root (two levels
    above this file's location), validates it can be parsed, and deep-merges
    the environment-specific overrides over the defaults section.

    Args:
        env: Deployment environment name (dev, staging, prod).

    Returns:
        Merged configuration dict for the given environment.

    Raises:
        FileNotFoundError: If config/guardrails.yml does not exist.
        ValueError: If the YAML file cannot be parsed.
    """
```

**Deep-merge semantics:**
- Scalar values in `environments[env]` replace the same key in `defaults`.
- Nested dicts are merged recursively: only the keys present in the override section
  are replaced; all other keys inherit from `defaults`.
- Lists in the override section **replace** the corresponding default list entirely
  (not appended). This matches the Bedrock API model where the full policy is sent
  on each deploy.

**Error handling:**
- `FileNotFoundError`: raised when `config/guardrails.yml` is absent, with a message
  naming the missing path so the operator knows immediately during `cdk synth`.
- `ValueError`: raised when the YAML content is syntactically invalid (wraps
  `yaml.YAMLError` with the original parse error message).

---

### 3. `BedrockGuardrailsStack`

**File:** `src/agentic_ai/infra/stacks/bedrock_guardrails_stack.py`

```python
class BedrockGuardrailsStack(cdk.Stack):
    """Provisions the Amazon Bedrock Guardrail and related SSM parameters.

    Reads config/guardrails.yml at synth time, deep-merges the
    environment-specific policy, and provisions a CfnGuardrail resource
    named aiops-guardrail-{environment}.

    Exports (via Python properties, NOT Fn::ImportValue):
        guardrail_id: str    — CDK token resolved to the guardrail physical ID
        guardrail_version: str — Always "DRAFT" for the active version
        guardrail_arn: str   — CDK token for the full guardrail ARN
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        context: CdkContext,
        **kwargs: Any,
    ) -> None:
        ...

    @property
    def guardrail_id(self) -> str: ...

    @property
    def guardrail_version(self) -> str: ...

    @property
    def guardrail_arn(self) -> str: ...
```

**Resource provisioning inside `__init__`:**

1. Call `_load_guardrails_config(context.environment)` to get the merged policy dict.
2. Construct `CfnGuardrail` with:
   - `name=f"aiops-guardrail-{env_name}"`
   - `blocked_topics_config` from `config["blocked_topics"]`
   - `content_policy_config` from `config["content_filters"]`
   - `word_policy_config` from `config["word_policy"]`
   - `sensitive_information_policy_config` from `config["sensitive_info_types"]`
   - `blocked_input_messaging` and `blocked_outputs_messaging` set to a generic
     safe-messaging response string.
3. Create two `ssm.StringParameter` resources:
   - `Name=/aiops/{env}/bedrock-guardrail-id`, `Value=guardrail.ref`
   - `Name=/aiops/{env}/bedrock-guardrail-version`, `Value="DRAFT"`
4. Set `termination_protection=True` when `context.environment == "prod"` (passed
   via `**kwargs` to the `cdk.Stack` super constructor).
5. Call `apply_standard_tags(self, context)`.

**Property implementations:**

```python
@property
def guardrail_id(self) -> str:
    return self._guardrail.ref

@property
def guardrail_version(self) -> str:
    return "DRAFT"

@property
def guardrail_arn(self) -> str:
    return self._guardrail.attr_guardrail_arn
```

---

### 4. `CdkContext` extension (`context.py`)

Add `guardrails_enabled: bool = True` to the `CdkContext` dataclass.

Update `validate_cdk_context` to read the optional `guardrailsEnabled` key:

```python
guardrails_enabled = raw.get("guardrailsEnabled", True)
# Coerce truthy values to bool; treat None/missing as True
if isinstance(guardrails_enabled, str):
    guardrails_enabled = guardrails_enabled.lower() not in ("false", "0", "no")
```

No validation error is raised when the key is absent. Absence is treated as `True`.

---

### 5. `app.py` wiring

Insert `BedrockGuardrailsStack` between `DataStack` and `ComputeStack`:

```python
# Read guardrails_enabled flag (new)
raw_context["guardrailsEnabled"] = app.node.try_get_context("guardrailsEnabled") or True
context = validate_cdk_context(raw_context)

guardrails_stack: BedrockGuardrailsStack | None = None
if context.guardrails_enabled:
    guardrails_stack = BedrockGuardrailsStack(
        app,
        f"{prefix}-BedrockGuardrails",
        env=env,
        context=context,
        termination_protection=is_prod,
    )
    guardrails_stack.add_dependency(data_stack)

compute_stack = ComputeStack(
    app,
    f"{prefix}-Compute",
    env=env,
    context=context,
    network_stack=network_stack,
    data_stack=data_stack,
    guardrails_stack=guardrails_stack,   # new optional param
    termination_protection=is_prod,
)
compute_stack.add_dependency(network_stack)
compute_stack.add_dependency(data_stack)
if guardrails_stack:
    compute_stack.add_dependency(guardrails_stack)
```

---

### 6. `ComputeStack` extension (`compute_stack.py`)

Add an optional `guardrails_stack` parameter to the constructor signature:

```python
def __init__(
    self,
    scope: Construct,
    construct_id: str,
    *,
    context: CdkContext,
    network_stack: NetworkStack,
    data_stack: DataStack,
    guardrails_stack: "BedrockGuardrailsStack | None" = None,   # new
    **kwargs: Any,
) -> None:
```

**Container environment injection** (added to the `environment={}` dict passed to
`task_def.add_container(...)`):

```python
container_env: dict[str, str] = {
    "ENVIRONMENT": env_name,
    ...existing keys...
}
if guardrails_stack is not None:
    container_env["BEDROCK_GUARDRAIL_ID"] = guardrails_stack.guardrail_id
    container_env["BEDROCK_GUARDRAIL_VERSION"] = guardrails_stack.guardrail_version
```

**IAM permission** (added after the existing `bedrock:InvokeModel` statement):

```python
if guardrails_stack is not None:
    # bedrock:ApplyGuardrail — scoped to the specific guardrail ARN (Req 4.4)
    self.task_role.add_to_policy(
        iam.PolicyStatement(
            actions=["bedrock:ApplyGuardrail"],
            resources=[guardrails_stack.guardrail_arn],
        )
    )
```

This follows the existing least-privilege pattern in `ComputeStack` and avoids
`Resource: "*"` per engineering standards.

---

### 7. `src/guardrails/bedrock_tool_guardrail.py` (new — Requirement 9)

**File:** `src/guardrails/bedrock_tool_guardrail.py`

This module implements the `GuardrailCheck` interface (from `src/guardrails/interfaces.py`)
and uses the standalone `ApplyGuardrail` API to screen SSM tool call inputs and outputs.
It reuses the same guardrail resource provisioned by `BedrockGuardrailsStack` — no new
CDK or YAML changes are required.

```python
class BedrockToolGuardrail(GuardrailCheck):
    """Screens SSM tool call inputs and outputs via the ApplyGuardrail API.

    Calls bedrock-runtime:ApplyGuardrail with source=INPUT before each SSM
    SendCommand and with source=OUTPUT after each SendCommand completes.

    When BEDROCK_GUARDRAIL_ID or BEDROCK_GUARDRAIL_VERSION env vars are absent,
    all checks are no-ops — existing deployments without guardrails are unaffected.

    Timeout: 5 seconds per ApplyGuardrail call. On timeout or any exception,
    logs a WARNING and falls through so guardrail API failures never block
    remediation execution.
    """

    APPLY_GUARDRAIL_TIMEOUT_SECONDS: float = 5.0

    def __init__(self, bedrock_client=None) -> None: ...

    @property
    def name(self) -> str:
        return "bedrock_tool_guardrail"

    async def check(self, action: RemediationAction) -> CheckResult:
        """Screen the serialised plan (INPUT) before SSM execution.

        Called by GuardrailEngine before the executor runs.
        Returns DENY if the guardrail intervenes, ALLOW otherwise.
        """

    async def screen_output(self, output: str, incident_id: str) -> str:
        """Screen SSM command output (OUTPUT) after execution.

        Called by SSMExecutor after SendCommand completes.
        Returns the guardrail-returned text if intervened, raw output otherwise.
        This is a separate method (not check()) because it operates on output,
        not on a RemediationAction.
        """
```

**`check()` logic — INPUT screening:**

1. If `BEDROCK_GUARDRAIL_ID` or `BEDROCK_GUARDRAIL_VERSION` env vars are absent/empty →
   return `CheckResult(ALLOW, reason="guardrails not configured — no-op")`.
2. Serialise `action` to a single text string: `f"{action.action_name} {action.playbook_path} {json.dumps(action.extra_vars)}"`.
3. Call `bedrock-runtime:apply_guardrail` with `source="INPUT"` and the text content,
   wrapped in `asyncio.wait_for(..., timeout=5.0)`.
4. If `response["action"] == "GUARDRAIL_INTERVENED"`:
   - Extract the canned output text from `response["outputs"][0]["text"]` (or use a
     default message if absent).
   - Log `WARNING` with `incident_id`.
   - Return `CheckResult(DENY, check_name="bedrock_tool_guardrail", reason=output_text)`.
5. On `asyncio.TimeoutError` or any `Exception`:
   - Log `WARNING` with exception details (no raw exception message in production — use
     `type(e).__name__` only, per engineering standards).
   - Return `CheckResult(ALLOW, reason="guardrail check failed — falling through")`.
6. Otherwise return `CheckResult(ALLOW, reason="guardrail INPUT check passed")`.

**`screen_output()` logic — OUTPUT screening:**

1. Same no-op guard on missing env vars.
2. Call `bedrock-runtime:apply_guardrail` with `source="OUTPUT"` and the output text.
3. If `response["action"] == "GUARDRAIL_INTERVENED"`:
   - Log `WARNING` with `incident_id`.
   - Return the guardrail-returned output text (the redacted/replaced content).
4. On timeout or exception: log `WARNING`, return the original `output` unchanged.
5. Otherwise return the original `output`.

**Integration into `GuardrailEngine`:**

`BedrockToolGuardrail` is added to the `checks` list passed to `GuardrailEngine` in
`src/app.py` (or wherever the engine is wired). It runs as check #8 — after all existing
7 checks. Because it implements `GuardrailCheck`, `GuardrailEngine` requires no changes.

`screen_output()` is called directly by `SSMExecutor._send_command()` after the command
result is received, before the `StepResult` is constructed. `SSMExecutor` receives the
`BedrockToolGuardrail` instance as an optional constructor parameter
(`tool_guardrail: BedrockToolGuardrail | None = None`); when `None`, output screening
is skipped.

---

### 8. `tests/cdk/test_bedrock_guardrails_stack.py`

New CDK assertion test file. Test classes:

- `TestBedrockGuardrailsStackResource` — asserts `AWS::Bedrock::Guardrail` resource
  properties (name, content filters present in template) across all three environments.
- `TestBedrockGuardrailsStackSSMParams` — asserts two `AWS::SSM::Parameter` resources
  with correct names per environment.
- `TestBedrockGuardrailsStackTerminationProtection` — asserts termination protection
  is True for prod, absent/False for dev and staging.
- `TestComputeStackWithGuardrails` — asserts container env vars are injected and IAM
  permission is present when `guardrails_stack` is provided.
- `TestComputeStackWithoutGuardrails` — asserts env vars and IAM permission are absent
  when `guardrails_stack=None` (backwards compatibility).
- `TestGuardrailsDisabledFlag` — asserts no `AWS::Bedrock::Guardrail` resource exists
  when `guardrails_enabled=False`.

---

## Data Models

### `CdkContext` (updated)

```python
@dataclass
class CdkContext:
    environment: str
    aws_account: str
    aws_region: str
    bedrock_model_id: str
    cost_center: str
    cost_center_email: str
    image_tag: str = "latest-dev"
    vpc_cidr: str = "10.0.0.0/16"
    monthly_budget_usd: str = "200"
    guardrails_enabled: bool = True     # new
```

### Guardrails Config Dict (runtime type after `_load_guardrails_config`)

```python
{
    "blocked_topics": [
        {
            "name": str,
            "definition": str,
            "examples": list[str],
            "type": "DENY",
        },
        ...
    ],
    "content_filters": {
        "HATE": "NONE" | "LOW" | "MEDIUM" | "HIGH",
        "INSULTS": ...,
        "SEXUAL": ...,
        "VIOLENCE": ...,
        "MISCONDUCT": ...,
        "PROMPT_ATTACK": ...,
    },
    "word_policy": {
        "managed_lists": ["PROFANITY", ...],
        "custom_words": [...],          # optional; may be empty list
    },
    "sensitive_info_types": [
        {"type": str, "action": "ANONYMIZE" | "BLOCK"},
        ...
    ],
}
```

### CfnGuardrail property mapping

| YAML key | CfnGuardrail property |
|---|---|
| `blocked_topics[].name` | `blockedTopicsConfig[].name` |
| `blocked_topics[].definition` | `blockedTopicsConfig[].definition` |
| `blocked_topics[].examples` | `blockedTopicsConfig[].examples` |
| `blocked_topics[].type` | `blockedTopicsConfig[].type` |
| `content_filters.{CATEGORY}` | `contentPolicyConfig.filtersConfig[].type` + `.inputStrength` + `.outputStrength` |
| `word_policy.managed_lists` | `wordPolicyConfig.managedWordListsConfig[].type` |
| `word_policy.custom_words` | `wordPolicyConfig.wordsConfig[].text` |
| `sensitive_info_types[].type` | `sensitiveInformationPolicyConfig.piiEntitiesConfig[].type` |
| `sensitive_info_types[].action` | `sensitiveInformationPolicyConfig.piiEntitiesConfig[].action` |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions
of a system — essentially, a formal statement about what the system should do. Properties
serve as the bridge between human-readable specifications and machine-verifiable correctness
guarantees.*

The `_load_guardrails_config` function is a pure function with clear input/output semantics:
it takes a YAML file and an environment name and returns a merged configuration dict.
This makes it the natural target for property-based testing. CDK stack synthesis (the remaining
surface area) is better covered by `aws_cdk.assertions.Template` snapshot tests, which is
why PBT is scoped to the config loader only.

**Property Reflection:** Three candidates emerged from prework analysis:
- Config deep-merge preserves defaults / applies overrides (from criteria 1.2 and 5.4 —
  these both test the same merge function; 5.4 subsumes 1.2 so they collapse to one property).
- Content filters completeness and validity (from criteria 1.4).
- Sensitive info types action validity (from criteria 1.6).

These three properties are non-redundant: they test different invariants on the loader output.

---

### Property 1: Deep-merge preserves defaults and applies environment overrides

*For any* valid guardrails config dict with a `defaults` section and an `environments`
section, `_load_guardrails_config(env)` must return a merged dict where every key present
in `environments[env]` has the environment-specific value, and every key present in
`defaults` but absent from `environments[env]` retains the default value.

**Validates: Requirements 1.2, 5.4**

---

### Property 2: Loaded config contains all required content filter categories with valid strengths

*For any* environment name in `{dev, staging, prod}`, the dict returned by
`_load_guardrails_config(env)` must contain a `content_filters` key whose value is a dict
containing exactly the six keys `HATE`, `INSULTS`, `SEXUAL`, `VIOLENCE`, `MISCONDUCT`,
`PROMPT_ATTACK`, with each value in the set `{NONE, LOW, MEDIUM, HIGH}`.

**Validates: Requirements 1.4, 5.1, 5.2, 5.3**

---

### Property 3: All sensitive_info_types entries have a valid action

*For any* valid guardrails config, the `sensitive_info_types` list returned by
`_load_guardrails_config(env)` must contain only entries where `action` is one of
`ANONYMIZE` or `BLOCK`. No other action values are permitted.

**Validates: Requirements 1.6**

---

### Property 4: BedrockToolGuardrail never blocks execution on API failure

*For any* `RemediationAction`, if the `bedrock-runtime:apply_guardrail` call raises
any exception or exceeds the 5-second timeout, `BedrockToolGuardrail.check()` must
return a `CheckResult` with `result_type=ALLOW` (not `DENY`). Guardrail API failures
must never prevent remediation execution.

**Validates: Requirement 9.5**

---

## Error Handling

### `_load_guardrails_config` — synth-time errors

| Condition | Exception | Message format |
|---|---|---|
| `config/guardrails.yml` absent | `FileNotFoundError` | `"Guardrails config file not found: {path}"` |
| YAML parse error | `ValueError` | `"Failed to parse config/guardrails.yml: {yaml_error}"` |
| `defaults` key missing | `ValueError` | `"config/guardrails.yml must contain a 'defaults' section"` |
| Invalid content filter strength | `ValueError` | `"Invalid content filter strength '{value}' for category '{cat}'; must be one of NONE, LOW, MEDIUM, HIGH"` |
| Invalid sensitive info action | `ValueError` | `"Invalid action '{action}' for sensitive_info_type '{type}'; must be ANONYMIZE or BLOCK"` |

All errors are raised at CDK synth time, which causes `cdk synth` to exit with a non-zero
return code and surfaces the error to the CI operator before any deployment is attempted
(Requirement 7.2).

### `BedrockGuardrailsStack` — deploy-time considerations

- `CfnGuardrail` does not support `UpdateReplacePolicy` natively; changes to the guardrail
  policy produce an in-place update to the existing guardrail resource (Bedrock Guardrail
  updates are non-destructive by default).
- Termination protection on prod stacks ensures the `AWS::Bedrock::Guardrail` resource
  cannot be deleted without disabling protection first.
- If Bedrock Guardrails is not available in the target region, CloudFormation will fail
  the deployment with a `ResourceNotFoundException`. The CI `cdk synth` step passes in all
  regions (synth is region-agnostic); the error surfaces only at deploy time.

### `ComputeStack` — backward compatibility

When `guardrails_stack=None` is passed:
- No `BEDROCK_GUARDRAIL_ID` or `BEDROCK_GUARDRAIL_VERSION` keys are added to the container
  environment. The `AgentConfig.__post_init__` will find empty strings via
  `os.environ.get(...)` and skip the guardrails parameters on `invoke_model` — this is the
  existing behavior, unchanged.
- No `bedrock:ApplyGuardrail` IAM statement is added. Existing deployments that do not use
  the guardrails stack are not affected.

### `BedrockToolGuardrail` — runtime error handling

| Condition | Behaviour |
|---|---|
| `BEDROCK_GUARDRAIL_ID` or `BEDROCK_GUARDRAIL_VERSION` absent/empty | No-op; return `ALLOW` without calling the API |
| `apply_guardrail` call exceeds 5-second timeout | Log `WARNING`, return `ALLOW` (fall-through) |
| `apply_guardrail` raises `ClientError` or any exception | Log `WARNING` with `type(e).__name__`, return `ALLOW` (fall-through) |
| `response["action"] == "GUARDRAIL_INTERVENED"` on INPUT | Return `DENY` with guardrail output text as reason; log `WARNING` with `incident_id` |
| `response["action"] == "GUARDRAIL_INTERVENED"` on OUTPUT | Replace output with guardrail text; log `WARNING` with `incident_id`; return replaced text |
| `response["outputs"]` list empty when intervened | Use fallback message `"Content blocked by guardrail"` |

The 5-second timeout and universal fall-through on error ensure that guardrail API
degradation (throttling, regional outage, misconfiguration) never blocks the remediation
pipeline. This is consistent with the engineering-standard principle of graceful degradation.

---

## Testing Strategy

### Unit tests (`tests/unit/`)

Focused on `_load_guardrails_config`, the `validate_cdk_context` extension, and `BedrockToolGuardrail`:

- **`test_load_guardrails_config_file_not_found`** — patches `open()` to raise
  `FileNotFoundError`; asserts the function re-raises with the file path in the message.
- **`test_load_guardrails_config_yaml_error`** — passes a string of invalid YAML;
  asserts `ValueError` is raised with the parse error.
- **`test_load_guardrails_config_missing_defaults`** — YAML with no `defaults` key;
  asserts `ValueError`.
- **`test_load_guardrails_config_dev_strengths`** — loads actual `config/guardrails.yml`
  for `dev`; asserts all content filter strengths are `LOW`.
- **`test_load_guardrails_config_staging_strengths`** — same for `staging`, asserts `MEDIUM`.
- **`test_load_guardrails_config_prod_strengths`** — same for `prod`, asserts `HIGH`.
- **`test_cdk_context_guardrails_enabled_default`** — `CdkContext()` without the field;
  asserts `guardrails_enabled is True`.
- **`test_validate_cdk_context_missing_guardrails_key`** — calls `validate_cdk_context`
  without `guardrailsEnabled` in the raw dict; asserts no exception and result has
  `guardrails_enabled=True`.
- **`test_validate_cdk_context_guardrails_false`** — `guardrailsEnabled=False` in raw dict;
  asserts result has `guardrails_enabled=False`.

**`BedrockToolGuardrail` unit tests** (`tests/unit/test_bedrock_tool_guardrail.py`):

- **`test_check_noop_when_guardrail_id_absent`** — env vars not set; assert `check()` returns `ALLOW` without calling `apply_guardrail`.
- **`test_check_noop_when_guardrail_version_absent`** — only ID set; assert no-op.
- **`test_check_allow_when_no_intervention`** — mock `apply_guardrail` returns `{"action": "NONE", "outputs": []}`; assert `check()` returns `ALLOW`.
- **`test_check_deny_when_guardrail_intervened`** — mock returns `{"action": "GUARDRAIL_INTERVENED", "outputs": [{"text": "Blocked"}]}`; assert `check()` returns `DENY` with `reason="Blocked"`.
- **`test_check_allow_on_timeout`** — mock raises `asyncio.TimeoutError`; assert `check()` returns `ALLOW` (fall-through).
- **`test_check_allow_on_client_error`** — mock raises `ClientError`; assert `check()` returns `ALLOW`.
- **`test_screen_output_returns_original_when_no_intervention`** — assert unchanged output returned.
- **`test_screen_output_returns_guardrail_text_when_intervened`** — mock intervenes; assert guardrail text returned, not original.
- **`test_screen_output_returns_original_on_timeout`** — mock times out; assert original output returned.

### Property tests (`tests/property/`) — uses Hypothesis

Property-based tests using [Hypothesis](https://hypothesis.readthedocs.io/en/latest/)
(`from hypothesis import given, settings; from hypothesis import strategies as st`).

Each test runs a minimum of 100 iterations (`@settings(max_examples=100)`).

**`test_property_deep_merge_preserves_defaults`**
- Tag: `# Feature: bedrock-guardrails-config, Property 1: deep-merge preserves defaults and applies overrides`
- Strategy: generate a `defaults` dict and a partial `env_overrides` dict using
  `st.fixed_dictionaries` with `st.one_of(st.none(), st.from_regex(...))` for override
  presence/absence.
- Assertion: for every key in `defaults`, if the key is in `env_overrides`, the merged
  result has the `env_overrides` value; otherwise it has the `defaults` value.

**`test_property_content_filters_completeness`**
- Tag: `# Feature: bedrock-guardrails-config, Property 2: loaded config contains all required content filter categories`
- Strategy: generate valid guardrails YAML strings (using `st.builds`) with varying strength
  values for each of the six categories.
- Assertion: the loaded config always contains all six categories, each with a value in
  `{"NONE", "LOW", "MEDIUM", "HIGH"}`.

**`test_property_sensitive_info_types_valid_actions`**
- Tag: `# Feature: bedrock-guardrails-config, Property 3: all sensitive_info_types entries have valid action`
- Strategy: generate valid guardrails config dicts with one or more `sensitive_info_types`
  entries using `st.lists(st.fixed_dictionaries({...}), min_size=1)`.
- Assertion: for every entry in `config["sensitive_info_types"]`, `entry["action"]` is in
  `{"ANONYMIZE", "BLOCK"}`.

### CDK assertion tests (`tests/cdk/`)

Uses `aws_cdk.assertions.Template`. Mirrors the pattern in `tests/cdk/conftest.py`.

**`test_bedrock_guardrails_stack.py`**

```
TestBedrockGuardrailsStackResource
  test_guardrail_resource_exists[dev/staging/prod]
    → template.resource_count_is("AWS::Bedrock::Guardrail", 1)
  test_guardrail_resource_name[dev/staging/prod]
    → template.has_resource_properties("AWS::Bedrock::Guardrail",
        {"Name": f"aiops-guardrail-{env}"})

TestBedrockGuardrailsStackSSMParams
  test_ssm_guardrail_id_parameter[dev/staging/prod]
    → template.has_resource_properties("AWS::SSM::Parameter",
        {"Name": f"/aiops/{env}/bedrock-guardrail-id"})
  test_ssm_guardrail_version_parameter[dev/staging/prod]
    → template.has_resource_properties("AWS::SSM::Parameter",
        {"Name": f"/aiops/{env}/bedrock-guardrail-version",
         "Value": "DRAFT"})

TestBedrockGuardrailsStackTerminationProtection
  test_termination_protection_prod
    → assert prod_stack.termination_protection is True
  test_no_termination_protection_dev
    → assert dev_stack.termination_protection is False

TestComputeStackWithGuardrails
  test_container_env_has_guardrail_id
    → template.has_resource_properties("AWS::ECS::TaskDefinition",
        {"ContainerDefinitions": [{"Environment":
          Match.array_with([{"Name": "BEDROCK_GUARDRAIL_ID", ...}])}]})
  test_container_env_has_guardrail_version
    → same pattern for BEDROCK_GUARDRAIL_VERSION
  test_iam_apply_guardrail_permission
    → template.has_resource_properties("AWS::IAM::Policy",
        {"PolicyDocument": {"Statement": [{"Action": "bedrock:ApplyGuardrail",
          "Resource": Match.any_value()}]}})
  test_iam_apply_guardrail_not_wildcard_resource
    → assert resource ARN is not "*"

TestComputeStackWithoutGuardrails
  test_container_env_no_guardrail_id
    → confirm BEDROCK_GUARDRAIL_ID absent from template
  test_iam_no_apply_guardrail_permission
    → confirm bedrock:ApplyGuardrail absent from IAM policies

TestGuardrailsDisabledFlag
  test_no_guardrail_resource_when_disabled
    → context.guardrails_enabled=False;
       template.resource_count_is("AWS::Bedrock::Guardrail", 0)
```

### Integration tests (`tests/integration/`)

The following integration tests verify end-to-end behavior after a real deployment:

- Verify that the deployed `AWS::Bedrock::Guardrail` resource exists in the target account
  and region with the expected name.
- Invoke `bedrock-runtime:ApplyGuardrail` against the deployed guardrail with a known
  benign input; assert no error is returned.
- Verify the SSM parameters exist and hold non-empty values after deployment.

These tests require AWS credentials and a deployed stack; they are gated behind the
`@pytest.mark.integration` marker and run only in the CD pipeline after deployment.
