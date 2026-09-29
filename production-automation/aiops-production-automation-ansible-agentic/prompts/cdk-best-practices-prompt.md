# CDK Stack Best Practices & Reusable Implementation Prompt

> Derived from `uw017-stormforce-agents` CDK implementation + AWS CDK v2 industry guidance (2025/2026).

---

## Table of Contents

1. [Best Practices Already in This Project](#1-best-practices-already-in-this-project)
2. [Gaps to Add in a New Project](#2-gaps-to-add-in-a-new-project)
3. [Reusable Prompt for a New CDK Project](#3-reusable-prompt-for-a-new-cdk-project)
4. [Verification Checklist](#4-verification-checklist)

---

## 1. Best Practices Already in This Project

### Stack Architecture

| Practice | How it is done |
|---|---|
| Strict deploy order | `stack_b.add_dependency(stack_a)` in `app.py`; 7 stacks deploy in a fixed sequence |
| Blast-radius isolation | Stateful stack (KMS, DynamoDB, Secrets) is fully separate from all compute stacks |
| One stack per concern | stateful / shared-layer / gateway / agent / runtimes / ingest / observability |
| Auto-discovery | New agents discovered by scanning `src/src/agents/*/agent.yaml`; no CDK code change needed |
| Per-agent runtime isolation | One `FplAgentRuntimeStack` per agent; code changes do not trigger other agents' redeployment |
| DataProtectionPolicy serialization | Runtime and Step Function stacks chained with `add_dependency()` to prevent concurrent `PutDataProtectionPolicy` API calls on the shared audit log group |

### Cross-Stack References

| Practice | How it is done |
|---|---|
| SSM as handoff mechanism | Every output (KMS ARN, layer ARN, role ARN, runtime ARN) written to SSM; downstream stacks resolve via `{{resolve:ssm:...}}` |
| No `Fn::ImportValue` | CloudFormation cross-stack exports never used — avoids deployment deadlocks when values change |
| Plain-string ARN construction | Deterministic resource names (IAM roles, Lambda functions) let downstream stacks build ARNs as strings — eliminates circular dependency risk |
| Runtime SSM reads | Non-deterministic ARNs (AgentCore runtime suffix) passed as SSM param *names* in Lambda env vars; Lambda resolves at cold start |

### Security

| Practice | How it is done |
|---|---|
| KMS CMK with key rotation | `enable_key_rotation=True`; 7-day pending window (dev/test), 30-day (qa/prod) |
| CMK alias condition scoping | `kms:ResourceAliases` condition ties `kms:key/*` wildcards to project CMK alias; avoids hardcoding key ARN |
| Lambda env var encryption | `environment_encryption=cmk_key` on every Lambda function |
| Permission boundary on every role | `neeito-app-pb-*` boundary applied to all IAM roles |
| Explicit role names | Contractual names like `{prefix}-agent-role` allow ARN construction as strings |
| Least-privilege by service | Each Lambda's role grants only the actions its handler actually calls |
| CloudWatch Data Protection | PII masked (NAME, PHONENUMBER_US, EMAILADDRESS + EmployeeId regex) in all log groups; always on in qa/prod |
| CDK Nag on every synth | `AwsSolutionsChecks(verbose=True)` blocks CI on violations; all suppressions have documented rationale |
| Documented nag suppressions | `apply_to_children=True`; `reason` string explains *why* (e.g., `kms:ResourceAliases` condition can't work with CreateEventSourceMapping) |
| SQS DLQs everywhere | Every async path (agent, SMS, bulk-SMS splitter/worker, interaction-sync) has a dead-letter queue |
| KMS alias managed in CI/CD | Org SCP blocks `kms:DeleteAlias`; alias created/updated in pipeline, not CloudFormation |

### Environment Management

| Practice | How it is done |
|---|---|
| 4 environments in `cdk.json` | `dev`, `test`, `qa`, `prod` with identical JSON structure, different values |
| Removal policy split | `DESTROY` for dev/test (cheap teardowns), `RETAIN` for qa/prod (protect data) |
| Lambda tuning in `cdk.json` | `lambda_config` block per function per env; never hardcoded in stack files |
| Bedrock model IDs per env | Cheaper/faster model in dev; production model in qa/prod |
| Env override via context | `-c env=dev` selects environment; defaults to `dev` |

### Lambda Packaging

| Practice | How it is done |
|---|---|
| Content-hash gating | SHA256 over `.py`, `.txt`, `.json`; skips pip + repackaging when unchanged |
| Shared Lambda Layer | `src/shared/` packaged once as a Layer; all compute Lambdas reference it |
| Platform-specific packaging | x86_64 for regular Lambdas; aarch64 (Graviton2) for AgentCore Runtimes |
| Smart pip tool selection | Tries `uv` first (faster), falls back to `pip` |
| WSL fallback on Windows | Used for aarch64 cross-compilation on Windows build hosts |

### Naming Conventions (contractual — never change after first deploy)

| Resource | Pattern |
|---|---|
| All resources | `{app_code}-{team_name}-{name}` (dashes) |
| SSM params | `/{app_code}/{team_name}/{param}` |
| KMS alias | `alias/{app_code}-{team_name}-cmk` |
| Log groups | `/{app_code}/{team_name}/{component}` |
| Lambda alias | `live` (no version numbers in function names) |
| AgentCore runtime | `{underscore_prefix}_{agent_name}` (underscores) |

### Observability

| Practice | How it is done |
|---|---|
| Dedicated observability stack | Last to deploy; depends on all other stacks |
| Shared PII audit log group | Created in stateful stack; all compute stacks route data-protection audit events here |
| Alarms on DLQs | Every DLQ has a `MessageCount > 0` alarm wired to SNS ops-alert topic |
| Explicit log groups | Each compute stack creates its own log group (not Lambda auto-created) so retention, encryption, and data protection can be applied |

---

## 2. Gaps to Add in a New Project

| Gap | Why it matters | Recommendation |
|---|---|---|
| No CDK unit tests (`cdk/tests/`) | Refactors can silently change IAM policies, removal policies, or env vars | Add `aws-cdk-lib.assertions` snapshot tests + fine-grained assertions |
| `cdk.context.json` not committed | VPC/subnet lookups differ across machines → non-deterministic synthesis | Commit it; add `--lookups false` to CI `cdk synth` |
| No resource tagging | Cost allocation and compliance audits become painful | `cdk.Tags.of(app).add(...)` at app scope |
| Manual `add_to_policy` dominates | Produces over-scoped `Resource: "*"` implicitly | Prefer L2 grant methods (`table.grant_read_write_data`, `bucket.grant_read`) |
| No `cdk gc` | Bootstrap S3/ECR accumulates unreferenced assets → cost | Schedule `cdk gc` in CI or run manually after deploys |
| No CDK integration tests | Unit tests verify template shape, not deployed behavior | `aws-cdk-lib.integ_tests_alpha.IntegTest` + `integ-runner` in sandbox account |
| CDK Nag suppressions repeated per stack | Boilerplate drifts | Centralize into `apply_common_suppressions(stack)` helper |
| Bootstrap not using custom boundary | CDK-generated roles may not inherit org boundary | `cdk bootstrap --custom-permissions-boundary {BOUNDARY_NAME}` |
| CDK Mixins not used | Duplicated encryption/logging setup across stacks | CDK ≥ 2.175: use `.with()` mixins for cross-cutting concerns |

---

## 3. Reusable Prompt for a New CDK Project

> Copy everything inside the code block. Replace all `{PLACEHOLDER}` values before pasting.

```
You are implementing an AWS CDK v2 infrastructure project for a new application.
Follow ALL rules below exactly. Do not deviate unless I explicitly override a rule.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT IDENTITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
app_code:   {APP_CODE}            # e.g. "uw018"
team_name:  {TEAM_NAME}           # e.g. "my-team"
prefix:     {APP_CODE}-{TEAM_NAME}  — dashes only, e.g. "uw018-my-team"
ssm_prefix: /{APP_CODE}/{TEAM_NAME}  e.g. "/uw018/my-team"
AWS accounts + regions: {FILL IN per environment}
Permission boundary ARN: arn:aws:iam::{account}:policy/{BOUNDARY_NAME}
  → apply to EVERY IAM role created

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 1 — STACK ARCHITECTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Always split into these stacks and deploy in this order:

  1. stateful       — KMS CMK, DynamoDB, Secrets Manager, SNS alert topic, SQS DLQs, EventBridge bus
  2. shared-layer   — Lambda Layer (shared library code + dependencies)
  3. gateway / api  — API-facing Lambdas, API Gateway
  4. compute        — core compute Lambdas + shared IAM role
  5. runtimes       — (optional) one stack per agent/runtime, auto-discovered from YAML
  6. ingest         — entry-point Lambdas triggered by external systems
  7. observability  — CloudWatch dashboard + alarms (always last)

Enforce order with explicit `stack_b.add_dependency(stack_a)` in app.py.
Never rely on implicit dependency ordering.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 2 — STATEFUL vs COMPUTE SEPARATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Never put stateful resources (DynamoDB, Secrets, KMS) in the same stack
as compute resources (Lambda, Step Functions, ECS).

A failed Lambda deploy must NEVER be able to trigger DynamoDB table deletion.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 3 — CROSS-STACK REFERENCES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use SSM Parameter Store for ALL cross-stack output handoff:

  Writing stack:
    ssm.StringParameter(self, "Id", parameter_name=f"{ssm_prefix}/resource-arn", string_value=resource.attr_arn)

  Reading stack (synth time — CloudFormation resolves at changeset creation):
    arn = ssm.StringParameter.value_for_string_parameter(self, f"{ssm_prefix}/resource-arn")

  Reading stack (runtime — use for non-deterministic ARNs):
    Pass the SSM param NAME as a Lambda env var.
    Lambda reads it via ssm.GetParameter() at cold start.

NEVER use Fn::ImportValue / CfnOutput cross-stack exports.
They lock stacks — you cannot rename or delete an export while any stack imports it.

For deterministic names (IAM roles, Lambda functions), PREFER constructing the ARN
as a plain string over creating an L2 cross-stack reference — eliminates circular dependency risk.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 4 — NAMING CONVENTIONS (contractual — never change after first deploy)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All resource names MUST use: {APP_CODE}-{TEAM_NAME}-{name}  (dashes only)

  DynamoDB:       {prefix}-{table-name}
  Lambda:         {prefix}-{function-name}
  IAM role:       {prefix}-{role-name}
  SQS:            {prefix}-{queue-name}
  SNS:            {prefix}-{topic-name}
  EventBridge:    {prefix}-events
  KMS alias:      alias/{prefix}-cmk
  Log group:      /{ssm_prefix}/{component}
  SSM param:      /{ssm_prefix}/{param-name}

Use explicit function_name=, table_name=, role_name= on every resource.
Never rely on CDK auto-generated names — they break on refactor and invalidate scripts/runbooks.

Lambda function aliases: use the name "live" (not version numbers in function names).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 5 — KMS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Create ONE KMS CMK in the stateful stack:
  - enable_key_rotation=True
  - pending_window: 7 days (dev/test), 30 days (qa/prod)
  - Write key ARN to SSM at {ssm_prefix}/kms-key-arn

All other stacks read the key ARN from SSM and apply it as environment_encryption=cmk_key
on every Lambda, SQS encryption, and DynamoDB server-side encryption.

If your org SCP blocks kms:DeleteAlias: manage the alias in CI/CD (create + update only),
not in CloudFormation. Reference the alias by name in CDK; never delete it via CF.

For IAM KMS wildcards (kms:key/*): scope with a kms:ResourceAliases condition tied to
the project CMK alias. Add a comment explaining why the wildcard is unavoidable.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 6 — IAM & PERMISSION BOUNDARIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Apply the permission boundary to every IAM role:
  managed_policies=[
      iam.ManagedPolicy.from_managed_policy_arn(self, "PB",
          f"arn:aws:iam::{account}:policy/{BOUNDARY_NAME}")
  ]

Scope IAM by service: each Lambda role gets only the permissions its handler calls.
Prefer L2 grant methods (table.grant_read_write_data, bucket.grant_read) over
manual add_to_policy wherever L2 grants are available.

Before writing any Resource: "*" in a policy: check the AWS Service Authorization Reference
to confirm the action has no resource-level support. That is the ONLY acceptable reason for "*".

Never use iam:* or s3:* wildcard actions.
For S3 ARNs: always triple-colon — arn:aws:s3:::bucket-name (never arn:aws:s3::*:bucket-name).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 7 — CLOUDWATCH DATA PROTECTION (PII)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enable CloudWatch Logs Data Protection on every log group:
  - Managed identifiers: NAME, PHONENUMBER_US, EMAILADDRESS (add domain-specific ones)
  - Audit destination: shared log group created in the stateful stack
  - Always enabled in qa/prod; configurable in dev/test
  - Serialize ALL stacks that create data-protection policies with add_dependency()
    to prevent concurrent PutDataProtectionPolicy calls on the shared audit log group.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 8 — CDK NAG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enable in app.py:
  from cdk_nag import AwsSolutionsChecks
  cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

Fix all violations before merging.
When a suppression is unavoidable:
  - Apply at resource level (not stack level unless it applies to all resources)
  - Use apply_to_children=True for role suppressions
  - reason= must explain WHY the violation is acceptable — not just "required"

Centralize common suppressions in a helper function apply_common_suppressions(stack)
to avoid repeating the same suppression across every stack.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 9 — ENVIRONMENT CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Define all environments in cdk.json under a top-level "environments" key:
  {
    "environments": {
      "dev":  { "account": "...", "region": "...", "removal_policy": "DESTROY", ... },
      "test": { "account": "...", "region": "...", "removal_policy": "DESTROY", ... },
      "qa":   { "account": "...", "region": "...", "removal_policy": "RETAIN",  ... },
      "prod": { "account": "...", "region": "...", "removal_policy": "RETAIN",  ... }
    }
  }

Per-resource memory, timeout, reserved_concurrency belong in cdk.json under a unified
"resource_config" key (see Rule 17). Never hardcode these in stack files.

Active environment: selected by -c env=dev. Default to dev in cdk.json.

Commit cdk.context.json. Add --lookups false to cdk synth in CI (fails fast on stale cache).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 10 — LAMBDA PACKAGING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Shared Lambda Layer:
  - Package all reused code as a Layer in the shared-layer stack.
  - Write Layer ARN to SSM. All compute stacks reference via layers=[shared_layer].
  - Do NOT bundle shared code into each Lambda.

Content-hash gating (implement in cdk/staging.py):
  - SHA256 over .py, .txt, .json files in the source directory.
  - Skip pip + repackaging when hash matches a cached build in .build/ directory.
  - Add .build/ to .gitignore.

  import hashlib, shutil, subprocess
  from pathlib import Path

  BUILD_DIR = Path(".build")

  def stage_resource_code(resource_name: str, source_dir: Path, requirements: Path | None) -> Path:
      h = hashlib.sha256()
      for f in sorted(source_dir.rglob("*.py")):
          h.update(f.read_bytes())
      digest = h.hexdigest()[:12]
      out = BUILD_DIR / f"{resource_name}-{digest}"
      if out.exists():
          return out                     # Cache hit — skip repackage
      shutil.copytree(source_dir, out)
      if requirements and requirements.exists():
          subprocess.run(
              ["pip", "install", "-r", str(requirements), "-t", str(out), "--quiet"],
              check=True,
          )
      return out

Graviton2 / cost optimization (optional):
  - Use --platform manylinux2014_aarch64 for aarch64 Lambdas.
  - On Windows build hosts, use WSL for cross-compilation.
  - Try uv before falling back to pip.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 11 — CDK CONSTRUCTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Prefer L2 constructs. Drop to L1 (Cfn*) only when:
  - The L2 does not expose the property you need, OR
  - You are working around a documented CDK bug.
  Always add a comment explaining why L1 was necessary.

Create L3 constructs (Construct subclasses in cdk/constructs/) when you copy-paste
the same 2+ resource pattern across 3+ places.

For Lambda invoke permissions from EventBridge rules: use CfnPermission (L1) instead of
lambda.add_permission() — the latter can create circular dependency edges with env var references.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 12 — CDK UNIT TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Write CDK unit tests in cdk/tests/ using aws-cdk-lib.assertions:

  Snapshot tests:
    template = Template.from_stack(stack)
    assert template.to_json() == snapshot

  Fine-grained assertions (examples):
    template.has_resource_properties("AWS::Lambda::Function", {
        "Environment": {"Variables": {"ENV_NAME": "dev"}},
        "KmsKeyArn": Match.any_value(),
    })
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "SSESpecification": {"SSEEnabled": True}
    })

Run tests in CI BEFORE cdk deploy: pytest cdk/tests/ -v --tb=short

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 13 — RESOURCE TAGGING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tag every resource at app scope:
  cdk.Tags.of(app).add("AppCode", app_code)
  cdk.Tags.of(app).add("TeamName", team_name)
  cdk.Tags.of(app).add("Environment", env_name)
  cdk.Tags.of(app).add("ManagedBy", "cdk")

Add cost-center or billing tags as required by your org.
Per-resource tags from resource.yaml (see Rule 17) are merged on top of project-level tags.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 14 — CIRCULAR DEPENDENCY PREVENTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Never let Stack A depend on Stack B AND Stack B depend on Stack A.

Resolve by ONE of:
  a. Moving both resources into the same stack (if they share a lifecycle)
  b. Constructing the ARN as a deterministic string instead of an L2 cross-stack reference
  c. Using SSM as the intermediary (one stack writes, the other reads at changeset time)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 15 — OBSERVABILITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dedicated observability stack (deploy last, depends on all other stacks):
  - CloudWatch Dashboard: Lambda error rate, throttle, duration, DLQ depth
  - Alarms: DLQ MessageCount > 0 for every dead-letter queue
  - Alarm actions: SNS ops-alert topic

Each compute stack creates its own CloudWatch log group explicitly
(not auto-created by Lambda) so retention, encryption, and data protection can be applied.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 16 — CI/CD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CI/CD pipeline must:
  1. pytest cdk/tests/ -v --tb=short        (CDK unit tests)
  2. cdk synth -c env={env} --quiet         (validates + runs CDK Nag)
  3. cdk deploy --all -c env={env} --require-approval never

Never cdk deploy without cdk synth first.

Use a dedicated deploy IAM role (instance profile or OIDC). Never long-lived access keys.
If your org SCP blocks kms:DeleteAlias: manage KMS alias in pipeline, not CDK.

Bootstrap with custom permission boundary so CDK-generated roles inherit it automatically:
  cdk bootstrap --custom-permissions-boundary {BOUNDARY_NAME}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULE 17 — AUTO-DISCOVERY & CONFIGURABLE RESOURCE DEPLOYMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Implement a config-driven, auto-discovery pattern so developers can declare any AWS resource
by dropping a YAML file into a directory — without touching CDK code.

Core concept: one directory per resource, one resource.yaml per directory. A "type" field
in the YAML tells CDK which stack class to instantiate. A central registry maps types to
stack classes. Adding a new resource = add a directory + yaml. Adding a new resource type =
add a stack class + one line in the registry.

── PATTERN A: Universal Directory Convention ──────────────────────────────────

  src/resources/<resource-name>/
    resource.yaml          # Required for ALL types — see schema below
    <type-specific files>  # e.g. handler.py for lambda, definition.asl.json for state_machine

  Rules for <resource-name>:
  - snake_case only (validated at discovery time: ^[a-z][a-z0-9_]*$)
  - Prefix with _ or . to disable without deleting (discovery skips these)
  - Name becomes part of the CloudFormation stack ID and all resource names

── PATTERN B: resource.yaml — Universal Schema + Type-Specific Fields ─────────

  Every resource.yaml base structure (all fields required unless marked Optional):

    type: <resource_type>         # Controls which stack class is used
    description: "..."            # Shown in AWS console and CloudFormation
    tags:                         # Optional — merged with project-level tags
      Component: "my-component"

  Supported types and their extra fields:

  ### type: lambda
    handler: handler.lambda_handler   # module.function (default: handler.lambda_handler)
    runtime: python3.12               # default: python3.12
    memory: 256                       # MB — overridable per env in cdk.json resource_config
    timeout: 30                       # seconds — overridable per env in cdk.json resource_config
    reserved_concurrency: null        # null = unreserved; overridable per env
    environment:                      # Static env vars (KMS-encrypted at rest)
      KEY: value
    iam_statements:
      - actions: ["s3:GetObject"]
        resources: ["arn:aws:s3:::my-bucket/*"]
    event_triggers:                   # EventBridge rules on the shared bus
      - detail_type: MyEvent
        source: com.mycompany.myservice
    schedule: "rate(5 minutes)"       # Optional: EventBridge scheduled rule
    vpc: false                        # true = inject vpc/subnets/security_groups from env_config

  ### type: sqs_queue
    visibility_timeout: 30            # seconds
    retention_period: 345600          # seconds (4 days default)
    max_receive_count: 3              # DLQ redrive policy
    fifo: false
    encryption: kms                   # kms | managed | none

  ### type: dynamodb_table
    partition_key:
      name: pk
      type: S                         # S | N | B
    sort_key:                         # Optional
      name: sk
      type: S
    billing_mode: PAY_PER_REQUEST     # PAY_PER_REQUEST | PROVISIONED
    stream: false                     # true = enable DynamoDB Streams
    ttl_attribute: null               # attribute name for TTL, or null
    global_secondary_indexes:         # Optional list of GSIs
      - name: gsi1
        partition_key: {name: gsi1pk, type: S}
        sort_key: {name: gsi1sk, type: S}

  ### type: sns_topic
    fifo: false
    subscriptions:                    # Optional initial subscriptions
      - protocol: email
        endpoint: "ops@example.com"

  ### type: state_machine
    definition_file: definition.asl.json
    lambdas:                          # Local Lambdas invoked by the state machine
      - key: my_step
        handler: handler.py
        memory: 256
        timeout: 30
    iam_statements:
      - actions: ["dynamodb:GetItem"]
        resources: ["arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/my-table"]
    event_triggers:
      - detail_type: MyEvent
        source: com.mycompany.myservice
        target_lambda: my_step
    execution_time_threshold_ms: 300000

  ### type: agentcore_runtime
    runtime_name_suffix: my_agent_v1
    entry_point: src/agents/my_agent/entrypoint.py   # relative to repo root

  ### type: eventbridge_rule
    bus_name: default                 # or reference the shared project bus
    event_pattern:
      source: ["com.mycompany.myservice"]
      detail_type: ["MyEvent"]
    targets:
      - type: lambda
        resource_name: my-function    # references another discovered resource by name

  ### type: s3_bucket
    versioning: false
    lifecycle_rules:
      - id: expire-old
        expiration_days: 90

  To add a new type: (1) define extra fields here, (2) create a stack class, (3) register it.

── PATTERN C: Discovery Module (cdk/resource_discovery.py) ────────────────────

  import re, yaml
  from pathlib import Path

  RESOURCES_ROOT = Path(__file__).parent.parent / "src" / "resources"
  VALID_TYPES = {
      "lambda", "sqs_queue", "dynamodb_table", "sns_topic",
      "state_machine", "agentcore_runtime", "eventbridge_rule", "s3_bucket",
  }
  NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

  def discover_resources() -> dict[str, dict]:
      result = {}
      for entry in sorted(RESOURCES_ROOT.iterdir()):
          if not entry.is_dir() or entry.name.startswith(("_", ".")):
              continue
          cfg_file = entry / "resource.yaml"
          if not cfg_file.exists():
              continue
          cfg = yaml.safe_load(cfg_file.read_text())
          name = entry.name

          if not NAME_RE.match(name):
              raise ValueError(f"[resource_discovery] '{name}': name must be snake_case")
          for field in ("type", "description"):
              if field not in cfg:
                  raise ValueError(f"[resource_discovery] '{name}/resource.yaml' missing '{field}'")
          if cfg["type"] not in VALID_TYPES:
              raise ValueError(
                  f"[resource_discovery] '{name}': unknown type '{cfg['type']}'. "
                  f"Known: {sorted(VALID_TYPES)}"
              )
          _validate_type_specific(name, cfg, entry)
          cfg["_source_dir"] = entry
          result[name] = cfg
      return result

  def _validate_type_specific(name: str, cfg: dict, entry: Path) -> None:
      t = cfg["type"]
      if t == "lambda":
          if not (entry / "handler.py").exists():
              raise FileNotFoundError(f"[resource_discovery] '{name}/handler.py' not found")
      elif t == "state_machine":
          if "definition_file" not in cfg:
              raise ValueError(f"[resource_discovery] '{name}': state_machine requires 'definition_file'")
          if not (entry / cfg["definition_file"]).exists():
              raise FileNotFoundError(f"[resource_discovery] '{name}/{cfg['definition_file']}' not found")
      elif t == "agentcore_runtime":
          for field in ("runtime_name_suffix", "entry_point"):
              if field not in cfg:
                  raise ValueError(f"[resource_discovery] '{name}': agentcore_runtime requires '{field}'")
          if not Path(cfg["entry_point"]).exists():
              raise FileNotFoundError(f"[resource_discovery] entry_point '{cfg['entry_point']}' not found")

── PATTERN D: Type Registry + Stack Dispatch in app.py ────────────────────────

  from resource_discovery import discover_resources
  from resource_stack_lambda import LambdaResourceStack
  from resource_stack_sqs import SqsQueueResourceStack
  from resource_stack_dynamodb import DynamoDbTableResourceStack
  from resource_stack_sns import SnsTopicResourceStack
  from resource_stack_state_machine import StateMachineResourceStack
  from resource_stack_agentcore import AgentCoreRuntimeResourceStack
  from resource_stack_eventbridge import EventBridgeRuleResourceStack
  from resource_stack_s3 import S3BucketResourceStack

  RESOURCE_TYPE_REGISTRY: dict[str, type] = {
      "lambda":            LambdaResourceStack,
      "sqs_queue":         SqsQueueResourceStack,
      "dynamodb_table":    DynamoDbTableResourceStack,
      "sns_topic":         SnsTopicResourceStack,
      "state_machine":     StateMachineResourceStack,
      "agentcore_runtime": AgentCoreRuntimeResourceStack,
      "eventbridge_rule":  EventBridgeRuleResourceStack,
      "s3_bucket":         S3BucketResourceStack,
  }

  RESOURCES = discover_resources()
  _prev_stack: cdk.Stack | None = None
  for res_name, res_cfg in RESOURCES.items():
      stack_class = RESOURCE_TYPE_REGISTRY[res_cfg["type"]]
      stack = stack_class(
          app,
          f"{prefix}-{res_cfg['type'].replace('_', '-')}-{res_name.replace('_', '-')}",
          resource_name=res_name,
          resource_config=res_cfg,
          env_config=env_config,
          stateful=stateful,
          ...
      )
      # Serialize all discovered stacks to prevent races on shared resources
      # (DataProtectionPolicy on shared audit log group, EventBridge bus targets, etc.)
      if _prev_stack is not None:
          stack.add_dependency(_prev_stack)
      _prev_stack = stack

  # To skip serialization for a type (fully independent stacks), chain only within the same type:
  # _prev_by_type: dict[str, cdk.Stack] = {}

── PATTERN E: What Each Stack Class Must Do ───────────────────────────────────

  Every resource stack class follows this contract:

  class <Type>ResourceStack(cdk.Stack):
      def __init__(self, scope, stack_id, *, resource_name, resource_config, env_config, ...):
          super().__init__(scope, stack_id, ...)

          # 1. Read env overrides — cdk.json resource_config wins over resource.yaml defaults
          overrides = env_config.get("resource_config", {}).get(resource_name, {})

          # 2. Apply project-level tags (project tags + per-resource tags from yaml)
          cdk.Tags.of(self).add("Project", prefix)
          for k, v in resource_config.get("tags", {}).items():
              cdk.Tags.of(self).add(k, v)

          # 3. Create the AWS resource(s) with explicit names
          #    ALWAYS set <resource>_name= so ARNs are deterministic

          # 4. Publish ARN to SSM at {ssm_prefix}/{resource_name}-arn
          ssm.StringParameter(self, "ArnParam",
              parameter_name=f"{ssm_prefix}/{resource_name}-arn",
              string_value=<resource>.attr_arn_or_equivalent,
          )

          # 5. Create CloudWatch alarms routed to the shared ops SNS topic
          #    (type-appropriate: error rate for Lambda, age for SQS, etc.)

── PATTERN F: Environment-Driven Overrides (unified resource_config in cdk.json) ─

  Replace per-type config sections (e.g., "lambda_config") with a single unified section
  under each environment block in cdk.json:

    "resource_config": {
      "<resource-name>": {
        "memory": 512,
        "timeout": 60,
        "reserved_concurrency": 10,
        "retention_period": 86400
      }
    }

  Rules:
  - resource.yaml values are the defaults
  - cdk.json resource_config.<name> values override per environment (env_config wins)
  - Stack reads: env_config.get("resource_config", {}).get(resource_name, {})
  - One pattern handles all resource types — no per-type config keys in cdk.json

── PATTERN G: Deterministic ARN Construction ──────────────────────────────────

  Set explicit names on every resource (function_name, queue_name, table_name, etc.).
  Construct ARNs inline from the name — do NOT use Fn::ImportValue or cross-stack L2 refs:

    f"arn:aws:lambda:{region}:{account}:function:{prefix}-lambda-{name}"
    f"arn:aws:sqs:{region}:{account}:{prefix}-sqs-{name}"
    f"arn:aws:dynamodb:{region}:{account}:table/{prefix}-table-{name}"

  For service-generated ARNs (non-deterministic), write to SSM at creation
  and read at Lambda cold start via env var containing the SSM param name.

── IMPLEMENTATION STEPS ───────────────────────────────────────────────────────

  1. Read ALL existing CDK code (app.py, all stack files, cdk.json) to learn:
     - Naming prefix and SSM prefix
     - What shared resources exist: KMS CMK, SNS ops topic, EventBridge bus, VPC config
     - Current stack dependency patterns and serialization approach
     - CDK nag suppressions already in use

  2. Create src/resources/ directory alongside (or under) the existing src layout.
     Adapt the RESOURCES_ROOT path in resource_discovery.py to match the project layout.

  3. Create cdk/resource_discovery.py per Pattern C.

  4. For each resource type the project actually needs, create one stack class file.
     Start with the type(s) in use today; add others on demand.

  5. Update cdk/app.py:
     - Import discover_resources and the type registry
     - Add the discovery loop and serialization chain from Pattern D
     - Leave all existing hand-coded stacks untouched

  6. Update cdk/cdk.json:
     - Add "resource_config": {} under each environment block (start empty)
     - Migrate any existing per-type keys (e.g. "lambda_config") to resource_config if applicable

  7. Create or extend cdk/staging.py with stage_resource_code() (see Rule 10).

  8. Validate with one example resource per type:
     - Drop a resource.yaml + required files
     - Run cdk synth — new stack must appear, existing stacks must be unchanged
     - Run cdk diff — confirm blast radius is limited to the new stack

  9. Verify CDK nag: cdk synth -c env=dev --quiet with zero new violations.

── EXTENDING TO A NEW RESOURCE TYPE ──────────────────────────────────────────

  To add support for a new AWS resource type (e.g., "kinesis_stream"):

  1. Add the type string to VALID_TYPES in resource_discovery.py
  2. Add type-specific validation in _validate_type_specific()
  3. Create cdk/resource_stack_kinesis.py with a KinesisStreamResourceStack class
  4. Register it in RESOURCE_TYPE_REGISTRY in app.py (one line)
  5. Document the new yaml fields in resource.yaml schema above

  No other changes needed. Existing discovered resources are unaffected.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT NOT TO DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Do NOT use Fn::ImportValue / CloudFormation cross-stack exports.
- Do NOT hardcode account IDs, region strings, or ARNs in stack files.
- Do NOT mix stateful and compute resources in the same stack.
- Do NOT leave CDK Nag violations unsuppressed without a documented reason.
- Do NOT use iam:* or s3:* wildcard actions.
- Do NOT use Resource: "*" unless the AWS auth reference confirms no resource-level support exists.
- Do NOT use ssm.StringParameter.value_for_string_parameter() for params that don't exist yet
  at CDK bootstrap time — generates {{resolve:ssm:...}} which fails when param is absent.
  Pass the param NAME as a Lambda env var and resolve at runtime instead.
- Do NOT use bare wildcards in S3 ARNs — always triple-colon: arn:aws:s3:::bucket-name.
- Do NOT commit .build/ artifacts or cdk.out/ to version control.
- Do NOT share IAM roles across services with different permission requirements.
- Do NOT validate config with str(val or "").strip() — silently coerces int/None to string.
  Always guard with isinstance(val, str) first.
- Do NOT log raw secret values in error messages — they propagate to CloudWatch Logs.
- Do NOT use hardcoded registries for agents/state-machines — use file-driven auto-discovery.
- Do NOT rely on CDK auto-generated resource names — they break on refactor.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXPECTED FILE STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
cdk/
  app.py                        # Stack wiring, deploy order, cdk.Aspects (tags + CDK Nag)
  cdk.json                      # Context: environments{}, resource_config, model IDs
  cdk.context.json              # Committed VPC/subnet lookup cache
  requirements.txt              # aws-cdk-lib, cdk-nag, constructs
  staging.py                    # Content-hash Lambda packaging helper
  resource_discovery.py         # Universal discovery + validation module
  constructs/                   # Reusable L3 constructs
  stacks/
    stateful_stack.py           # KMS, DynamoDB, Secrets, SNS, SQS, EventBridge
    shared_layer_stack.py       # Lambda Layer
    gateway_stack.py            # API-facing Lambdas / API Gateway
    compute_stack.py            # Core compute Lambdas + shared IAM role
    ingest_stack.py             # Entry-point Lambdas
    observability_stack.py      # Dashboard + alarms
    resource_stack_lambda.py    # Auto-discovered Lambda resources
    resource_stack_sqs.py       # Auto-discovered SQS queues
    resource_stack_dynamodb.py  # Auto-discovered DynamoDB tables
    resource_stack_sns.py       # Auto-discovered SNS topics
    resource_stack_state_machine.py
    resource_stack_agentcore.py
    resource_stack_eventbridge.py
    resource_stack_s3.py
  tests/                        # CDK unit tests (assertions + snapshots)
    test_stateful.py
    test_compute.py
    conftest.py

src/
  src/
    lambdas/                    # Hand-coded Lambda handler code
    shared/                     # Packaged into Lambda Layer
    agents/                     # One directory per agent (hand-coded stacks)
  resources/                    # Auto-discovered resources (one directory per resource)
    <resource-name>/
      resource.yaml
      handler.py / definition.asl.json / ...

At the end of your implementation, list every rule above and confirm: APPLIED or SKIPPED (reason).
```

---

## 4. Verification Checklist

Run these after generating or modifying the CDK project:

```bash
# 1. Synthesis + CDK Nag — zero violations
cd cdk && cdk synth -c env=dev --quiet

# 2. CDK unit tests
pytest cdk/tests/ -v --tb=short

# 3. Check for any Fn::ImportValue in synthesized templates (should be zero)
grep -r "ImportValue" cdk.out/

# 4. Confirm every Lambda has environment_encryption set
grep -r "environment_encryption" cdk/

# 5. Confirm every IAM role has the permission boundary
grep -r "permission_boundary\|PB" cdk/stacks/

# 6. Confirm SSM writes happen before SSM reads (review app.py dependency graph)
grep -n "add_dependency\|StringParameter" cdk/app.py

# 7. Preview changeset before deploy
cdk diff -c env=dev

# 8. Auto-discovery smoke test — add a second resource directory, re-synth, new stack appears
#    (no CDK code should be touched)

# 9. Disable a resource by prefixing its directory with _ → re-synth → stack disappears

# 10. Add a resource_config override in cdk.json → re-synth → only that resource's stack changes

# 11. Confirm no CDK auto-generated names — every resource must have explicit name= set
grep -r "function_name\|table_name\|queue_name\|role_name" cdk/stacks/
```

---

*Last updated: 2026-09-05 | Source: `uw017-stormforce-agents` CDK analysis + AWS CDK v2 best practices*
