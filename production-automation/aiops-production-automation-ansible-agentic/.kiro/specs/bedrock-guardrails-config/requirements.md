# Requirements Document

## Introduction

This feature adds repository-managed Amazon Bedrock Guardrails to the AIOps self-healing
infrastructure. Today the guardrail resource does not exist in CDK — it must be created
manually outside the repo and its ID/version wired in by hand. This feature provisions
the Bedrock Guardrail via a new `BedrockGuardrailsStack`, drives its policy from a
versioned YAML file (`config/guardrails.yml`), and automatically injects the guardrail
ID and version as environment variables on the ECS task so `reasoning_agent.py` picks
them up with zero code change.

The guardrail provides defense-in-depth content filtering: it complements — and does not
replace — the existing `PlanValidator` / `config/denied_commands.yml` layer by enforcing
Bedrock-native topic denials and content filters on every model invocation.

## Glossary

- **BedrockGuardrailsStack**: New CDK stack (`Aiops-{env}-BedrockGuardrails`) that owns
  the `AWS::Bedrock::Guardrail` resource and related SSM parameters.
- **Guardrail**: An Amazon Bedrock Guardrail resource that enforces topic denials, content
  filters, word-level blocks, and sensitive-information redaction on model invocations.
- **GuardrailsConfig**: The YAML document at `config/guardrails.yml` that ops teams edit
  to tune guardrail policy per environment without touching CDK Python code.
- **CdkContext**: The validated `CdkContext` dataclass in `src/agentic_ai/infra/context.py`
  that carries all deployment-time settings consumed by every stack.
- **ComputeStack**: The existing CDK stack that owns the ECS Fargate service and task
  definition where `BEDROCK_GUARDRAIL_ID` / `BEDROCK_GUARDRAIL_VERSION` env vars must appear.
- **SSM_GUARDRAIL_ID**: SSM parameter `/aiops/{environment}/bedrock-guardrail-id` that
  holds the guardrail's physical resource ID post-deploy.
- **SSM_GUARDRAIL_VERSION**: SSM parameter `/aiops/{environment}/bedrock-guardrail-version`
  that holds the guardrail's active version (initially `"DRAFT"`).
- **BEDROCK_GUARDRAIL_ID**: ECS container environment variable read by `AgentConfig` in
  `reasoning_agent.py` at runtime.
- **BEDROCK_GUARDRAIL_VERSION**: ECS container environment variable read by `AgentConfig`
  in `reasoning_agent.py` at runtime.
- **PlanValidator**: The existing runtime safety layer in `src/guardrails/plan_validator.py`
  that blocks dangerous commands; the Guardrail is a complementary Bedrock-native layer.
- **BedrockToolGuardrail**: New runtime module (`src/guardrails/bedrock_tool_guardrail.py`)
  that calls the standalone `ApplyGuardrail` API to screen SSM tool call inputs and outputs.
- **ApplyGuardrail API**: The `bedrock-runtime` API that evaluates arbitrary text against a
  pre-configured guardrail resource without invoking a foundation model. `source=INPUT`
  screens content going into a tool; `source=OUTPUT` screens content coming back from a tool.

---

## Requirements

### Requirement 1: YAML-Driven Guardrail Configuration File

**User Story:** As an ops engineer, I want to tune the Bedrock Guardrail policy by editing a
YAML file in the repository, so that I can adjust denied topics and content filter strengths
per environment without modifying CDK Python code.

#### Acceptance Criteria

1. THE GuardrailsConfig SHALL define a `config/guardrails.yml` file in the repository root
   `config/` directory, following the same structure as `config/denied_commands.yml`.

2. THE GuardrailsConfig SHALL support an `environments` top-level key with per-environment
   overrides for `dev`, `staging`, and `prod`, merged over a `defaults` section.

3. THE GuardrailsConfig SHALL define a `blocked_topics` section where each entry specifies
   a `name`, `definition` (plain-English description), a list of `examples`, and a
   `type` of `DENY`.

4. THE GuardrailsConfig SHALL define a `content_filters` section with a `strength` value
   for each of the categories `HATE`, `INSULTS`, `SEXUAL`, `VIOLENCE`, `MISCONDUCT`,
   and `PROMPT_ATTACK`; accepted values are `NONE`, `LOW`, `MEDIUM`, and `HIGH`.

5. THE GuardrailsConfig SHALL define a `word_policy` section with a `managed_lists` key
   that includes at minimum `PROFANITY`, and an optional `custom_words` list.

6. THE GuardrailsConfig SHALL define a `sensitive_info_types` section listing PII entity
   types (e.g., `EMAIL`, `PHONE`, `AWS_ACCESS_KEY`) with an `action` of `ANONYMIZE`
   or `BLOCK`.

7. WHEN the `config/guardrails.yml` file is absent at CDK synth time, THE
   BedrockGuardrailsStack SHALL raise a `FileNotFoundError` with a message naming the
   missing file, so the operator is informed immediately.

8. WHEN the `config/guardrails.yml` file contains a YAML syntax error, THE
   BedrockGuardrailsStack SHALL raise a `ValueError` with the parse error message, so
   the operator can fix the file before deployment.

---

### Requirement 2: BedrockGuardrailsStack CDK Stack

**User Story:** As a platform engineer, I want a dedicated CDK stack that provisions the
Bedrock Guardrail resource, so that the guardrail lifecycle (create, update, delete) is
fully managed by CDK and tracked in version control.

#### Acceptance Criteria

1. THE BedrockGuardrailsStack SHALL provision one `aws_bedrock.CfnGuardrail` resource per
   deployment, named `aiops-guardrail-{environment}`.

2. THE BedrockGuardrailsStack SHALL accept a validated `CdkContext` instance as a
   constructor parameter and derive all environment-specific values from it.

3. THE BedrockGuardrailsStack SHALL read `config/guardrails.yml` at synth time, merge the
   environment-specific overrides over the defaults section, and apply the merged policy
   to the `CfnGuardrail` resource properties.

4. THE BedrockGuardrailsStack SHALL follow the stack naming convention
   `Aiops-{environment}-BedrockGuardrails`.

5. WHEN `context.environment == "prod"`, THE BedrockGuardrailsStack SHALL set
   `termination_protection=True` to prevent accidental deletion.

6. THE BedrockGuardrailsStack SHALL publish two SSM `StringParameter` resources:
   - `/aiops/{environment}/bedrock-guardrail-id` with the guardrail's logical resource ID
     token (resolved at deploy time)
   - `/aiops/{environment}/bedrock-guardrail-version` with the string `"DRAFT"`

7. THE BedrockGuardrailsStack SHALL expose `guardrail_id` and `guardrail_version` as
   Python properties so the `ComputeStack` can reference them without `Fn::ImportValue`.

8. THE BedrockGuardrailsStack SHALL apply the project's standard resource tags
   (cost center, environment) via the existing `apply_standard_tags` mechanism.

---

### Requirement 3: CDK App Wiring

**User Story:** As a platform engineer, I want the `BedrockGuardrailsStack` wired into the
existing CDK app so that it deploys alongside the other stacks in the correct order, and
the `ComputeStack` receives the guardrail ID and version automatically.

#### Acceptance Criteria

1. THE CDK_App SHALL instantiate `BedrockGuardrailsStack` in `src/agentic_ai/infra/app.py`
   after `DataStack` and before `ComputeStack`, passing the validated `CdkContext` and the
   same `env` object used by all other stacks.

2. THE CDK_App SHALL declare `compute_stack.add_dependency(guardrails_stack)` so CDK
   deploys `BedrockGuardrailsStack` before `ComputeStack`.

3. THE ComputeStack SHALL accept an optional `guardrails_stack` parameter of type
   `BedrockGuardrailsStack | None`; WHEN the parameter is provided, THE ComputeStack SHALL
   add `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` to the ECS container's
   `environment` dict using the stack's `guardrail_id` and `guardrail_version` properties.

4. WHEN `guardrails_stack` is `None`, THE ComputeStack SHALL omit
   `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` from the container environment,
   preserving backwards compatibility with deployments that skip the guardrails stack.

5. THE CDK_App SHALL pass `guardrails_stack` to `ComputeStack` so that `reasoning_agent.py`
   receives the correct env vars with no application code changes.

---

### Requirement 4: IAM Permissions for Bedrock ApplyGuardrail

**User Story:** As a security engineer, I want the ECS task role to have the minimum IAM
permissions required to use the guardrail, so that the principle of least privilege is
maintained.

#### Acceptance Criteria

1. THE ComputeStack SHALL add an IAM policy statement granting `bedrock:ApplyGuardrail`
   to the ECS task role, scoped to the specific guardrail ARN constructed as
   `arn:aws:bedrock:{region}:{account}:guardrail/{guardrail_id}`.

2. THE ComputeStack SHALL add the `bedrock:ApplyGuardrail` permission only WHEN a
   `guardrails_stack` is provided, so the statement is absent when the stack is not deployed.

3. THE BedrockGuardrailsStack SHALL expose a `guardrail_arn` property that returns the
   ARN of the provisioned guardrail, allowing `ComputeStack` to scope the IAM statement
   without constructing the ARN by hand.

4. THE ComputeStack SHALL NOT grant `bedrock:ApplyGuardrail` with `Resource: "*"`;
   the resource MUST be scoped to the specific guardrail ARN.

---

### Requirement 5: Per-Environment Policy Strictness

**User Story:** As an ops engineer, I want each deployment environment (dev, staging, prod)
to enforce a different level of content filter strictness, so that dev remains permissive for
testing while prod enforces the strictest safe-messaging policy.

#### Acceptance Criteria

1. THE GuardrailsConfig SHALL define `dev` overrides that set all content filter strengths
   to `LOW` and blocked topics to a minimal set, providing a permissive policy for
   developer iteration.

2. THE GuardrailsConfig SHALL define `staging` overrides that set content filter strengths
   to `MEDIUM`, matching a realistic pre-production policy.

3. THE GuardrailsConfig SHALL define `prod` overrides that set content filter strengths
   to `HIGH` for all categories and enable the full blocked-topics and word-policy lists,
   enforcing the strictest safe-messaging policy.

4. WHEN the `BedrockGuardrailsStack` reads `config/guardrails.yml`, THE
   BedrockGuardrailsStack SHALL deep-merge the environment-specific overrides over the
   `defaults` section so that only the keys present in the override section are replaced,
   and all other keys inherit from `defaults`.

---

### Requirement 6: CdkContext Extension

**User Story:** As a platform engineer, I want the `CdkContext` dataclass to carry a flag
controlling whether the guardrails stack is enabled, so that teams can opt out via
`cdk.json` without modifying Python code.

#### Acceptance Criteria

1. THE CdkContext SHALL include an optional boolean field `guardrails_enabled` that
   defaults to `True`.

2. THE CDK_App SHALL read `guardrailsEnabled` from the CDK context (default `True`) and
   pass it through the validated `CdkContext` to the app wiring logic.

3. WHEN `context.guardrails_enabled` is `False`, THE CDK_App SHALL skip instantiating
   `BedrockGuardrailsStack` and SHALL pass `guardrails_stack=None` to `ComputeStack`.

4. THE `validate_cdk_context` function SHALL accept a missing or empty `guardrailsEnabled`
   key without raising a validation error, treating absence as `True`.

---

### Requirement 7: CDK Synth Validation (CI Gate)

**User Story:** As a CI/CD engineer, I want CDK synth to fail fast when the guardrails
configuration is invalid or the guardrail resource cannot be synthesised, so that broken
guardrail configs are caught before any deployment.

#### Acceptance Criteria

1. WHEN `cdk synth` is run and `config/guardrails.yml` is present, THE CDK_App SHALL
   synthesise a CloudFormation template that contains an `AWS::Bedrock::Guardrail` resource
   with `Name` equal to `aiops-guardrail-{environment}`.

2. WHEN `cdk synth` is run and `config/guardrails.yml` is absent, THE CDK_App SHALL exit
   with a non-zero return code so the CI `cdk_synth` step fails.

3. THE CDK assertion tests SHALL assert that the synthesised template for each environment
   contains exactly one `AWS::Bedrock::Guardrail` resource when `guardrails_enabled` is
   `True`.

4. THE CDK assertion tests SHALL assert that the synthesised template contains two SSM
   parameters with names matching `/aiops/{env}/bedrock-guardrail-id` and
   `/aiops/{env}/bedrock-guardrail-version`.

5. THE CDK assertion tests SHALL assert that the ECS task definition's container
   environment includes `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` when
   `guardrails_enabled` is `True`.

---

### Requirement 8: No Application Code Changes to reasoning_agent.py

**User Story:** As a developer, I want the guardrail to be available to `reasoning_agent.py`
through the existing env-var mechanism, so that no application code changes are required
and the risk of regression is minimised.

#### Acceptance Criteria

1. THE BedrockGuardrailsStack SHALL provision the guardrail such that its physical resource
   ID is surfaced as the value of `BEDROCK_GUARDRAIL_ID` and `"DRAFT"` as
   `BEDROCK_GUARDRAIL_VERSION` in the ECS container environment.

2. THE Guardrail provisioned by BedrockGuardrailsStack SHALL be compatible with the
   existing `invoke_model` call in `AIReasoningAgent._invoke_model`, which passes
   `guardrailIdentifier` and `guardrailVersion` directly to `bedrock-runtime`.

3. THE BedrockGuardrailsStack SHALL NOT modify `src/agentic_ai/agents/reasoning_agent.py`
   or any other runtime Python file; all changes are confined to CDK infrastructure files
   and the new `config/guardrails.yml`.

---

### Requirement 9: Guardrail Enforcement on Tool Call Inputs and Outputs

**User Story:** As a security engineer, I want the Bedrock guardrail applied to AI-generated
SSM command inputs before execution and to SSM command outputs before storage, so that
dangerous or policy-violating content is caught at the tool boundary — providing a third
safety layer beyond model-level guardrails and the existing regex-based PlanValidator.

#### Acceptance Criteria

1. THE BedrockToolGuardrail SHALL call `bedrock-runtime:ApplyGuardrail` with
   `source="INPUT"` and the serialised AI-generated remediation plan text as the content
   payload before each SSM `SendCommand` invocation.

2. WHEN the `ApplyGuardrail` INPUT call returns `action == "GUARDRAIL_INTERVENED"`, THE
   BedrockToolGuardrail SHALL abort the SSM execution and return a `CheckResult` with
   `result_type=DENY`, `check_name="bedrock_tool_guardrail"`, and `reason` set to the
   guardrail-returned output text.

3. THE BedrockToolGuardrail SHALL call `bedrock-runtime:ApplyGuardrail` with
   `source="OUTPUT"` and the SSM command output text as the content payload after each
   `SendCommand` invocation completes.

4. WHEN the `ApplyGuardrail` OUTPUT call returns `action == "GUARDRAIL_INTERVENED"`, THE
   BedrockToolGuardrail SHALL replace the raw SSM output with the guardrail-returned
   output text before the result is stored or returned to the caller, and SHALL log a
   WARNING including the `incident_id`.

5. THE BedrockToolGuardrail SHALL complete each `ApplyGuardrail` API call within a
   5-second timeout; IF the call exceeds 5 seconds or raises any exception, THE
   BedrockToolGuardrail SHALL log a WARNING and allow execution to proceed unchanged
   (fall-through), so guardrail API failures never block remediation.

6. WHEN either `BEDROCK_GUARDRAIL_ID` or `BEDROCK_GUARDRAIL_VERSION` environment
   variables are absent or empty at runtime, THE BedrockToolGuardrail SHALL skip all
   `ApplyGuardrail` calls and operate as a no-op, preserving backward compatibility with
   deployments that do not configure guardrails.

7. THE BedrockToolGuardrail SHALL be implemented in a new module
   `src/guardrails/bedrock_tool_guardrail.py`, following the existing `GuardrailCheck`
   interface defined in `src/guardrails/interfaces.py`, so it integrates into the
   `GuardrailEngine` pipeline without changes to the engine itself.
