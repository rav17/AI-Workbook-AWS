# Implementation Plan: bedrock-guardrails-config

## Overview

Provision Amazon Bedrock Guardrails through a new `BedrockGuardrailsStack`, drive its
content-filtering policy from a versioned YAML file (`config/guardrails.yml`), and
automatically inject the guardrail ID and version into the ECS task environment so
`reasoning_agent.py` picks them up with zero application code changes.

All changes are confined to CDK infrastructure files and the new YAML configuration.
`reasoning_agent.py` is not modified.

---

## Tasks

- [ ] 1. Create `config/guardrails.yml` with per-environment policy
  - [ ] 1.1 Write `config/guardrails.yml` with `defaults`, `environments` top-level keys
    - Define `defaults.blocked_topics` with at least one entry (name, definition, examples, type: DENY)
    - Define `defaults.content_filters` for all six categories: HATE, INSULTS, SEXUAL, VIOLENCE, MISCONDUCT, PROMPT_ATTACK
    - Define `defaults.word_policy` with `managed_lists: [PROFANITY]` and optional `custom_words`
    - Define `defaults.sensitive_info_types` with EMAIL, PHONE, AWS_ACCESS_KEY entries (action: ANONYMIZE or BLOCK)
    - Add `environments.dev` overrides setting all content filter strengths to `LOW`
    - Add `environments.staging` overrides setting all content filter strengths to `MEDIUM`
    - Add `environments.prod` overrides setting all content filter strengths to `HIGH` and enabling full blocked-topics and word-policy lists
    - Follow the same file structure as `config/denied_commands.yml` for consistency
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3_

- [ ] 2. Extend `CdkContext` with `guardrails_enabled` flag
  - [ ] 2.1 Add `guardrails_enabled: bool = True` field to `CdkContext` dataclass in `src/agentic_ai/infra/context.py`
    - Add the field after `monthly_budget_usd` with default `True`
    - Update `validate_cdk_context` to read the optional `guardrailsEnabled` key from `raw`
    - Coerce string values ("false", "0", "no") to `False`; treat absence/`None` as `True`
    - No validation error when the key is absent
    - Pass `guardrails_enabled` through in the `CdkContext(...)` constructor call at the end of `validate_cdk_context`
    - _Requirements: 6.1, 6.2, 6.4_

  - [ ]* 2.2 Write unit tests for `CdkContext` guardrails_enabled extension in `tests/unit/test_guardrails_config_loader.py`
    - `test_cdk_context_guardrails_enabled_default` — assert `CdkContext(...).guardrails_enabled is True` (default)
    - `test_validate_cdk_context_missing_guardrails_key` — call `validate_cdk_context` without `guardrailsEnabled`; assert no exception and result has `guardrails_enabled=True`
    - `test_validate_cdk_context_guardrails_false` — pass `guardrailsEnabled=False`; assert `guardrails_enabled=False`
    - _Requirements: 6.1, 6.4_

- [ ] 3. Implement `BedrockGuardrailsStack` with `_load_guardrails_config`
  - [ ] 3.1 Create `src/agentic_ai/infra/stacks/bedrock_guardrails_stack.py` with the `_load_guardrails_config` pure function
    - Resolve path to `config/guardrails.yml` relative to repository root (two levels above the stack file)
    - Raise `FileNotFoundError` with message `"Guardrails config file not found: {path}"` when file absent
    - Raise `ValueError` wrapping `yaml.YAMLError` message when YAML is unparseable
    - Raise `ValueError` with `"config/guardrails.yml must contain a 'defaults' section"` when `defaults` key missing
    - Implement deep-merge: scalars and lists in `environments[env]` replace defaults; nested dicts merge recursively
    - Lists in override section replace the corresponding default list entirely (not appended)
    - Validate content filter strength values; raise `ValueError` for invalid strengths naming the category and value
    - Validate sensitive info type actions; raise `ValueError` for values outside `ANONYMIZE` and `BLOCK`
    - Add Google-style docstring as specified in design
    - _Requirements: 1.2, 1.7, 1.8, 5.4_

  - [ ]* 3.2 Write property test for `_load_guardrails_config` deep-merge in `tests/property/test_guardrails_config_properties.py`
    - **Property 1: Deep-merge preserves defaults and applies environment overrides**
    - Use `st.fixed_dictionaries` to generate arbitrary `defaults` and partial `env_overrides` dicts
    - Assert: for every key in defaults, the merged result has `env_overrides[key]` if key is in overrides, else `defaults[key]`
    - Tag: `# Feature: bedrock-guardrails-config, Property 1: deep-merge preserves defaults and applies overrides`
    - Decorate with `@settings(max_examples=100)`
    - **Validates: Requirements 1.2, 5.4**

  - [ ] 3.3 Implement `BedrockGuardrailsStack` class body in `bedrock_guardrails_stack.py`
    - Call `_load_guardrails_config(context.environment)` in `__init__`
    - Construct `aws_bedrock.CfnGuardrail` named `aiops-guardrail-{env_name}` with all four policy config sections mapped from the YAML dict per the CfnGuardrail property mapping table in the design
    - Set `blocked_input_messaging` and `blocked_outputs_messaging` to a generic safe-messaging string
    - Create `ssm.StringParameter` for `/aiops/{env}/bedrock-guardrail-id` with value `guardrail.ref`
    - Create `ssm.StringParameter` for `/aiops/{env}/bedrock-guardrail-version` with value `"DRAFT"`
    - Set `termination_protection=True` in the `cdk.Stack` super call when `context.environment == "prod"`
    - Call `apply_standard_tags(self, context)` at the end of `__init__`
    - Implement `guardrail_id`, `guardrail_version`, and `guardrail_arn` Python properties
    - Use stack naming convention `Aiops-{environment}-BedrockGuardrails`
    - Follow all IAM least-privilege and naming conventions from `engineering-standards.md`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 7.1_

  - [ ]* 3.4 Write unit tests for `_load_guardrails_config` error paths in `tests/unit/test_guardrails_config_loader.py`
    - `test_load_guardrails_config_file_not_found` — patch `open()` to raise `FileNotFoundError`; assert re-raised with path in message
    - `test_load_guardrails_config_yaml_error` — pass invalid YAML content; assert `ValueError` raised
    - `test_load_guardrails_config_missing_defaults` — YAML with no `defaults` key; assert `ValueError`
    - `test_load_guardrails_config_dev_strengths` — load actual `config/guardrails.yml` for `dev`; assert all six categories are `LOW`
    - `test_load_guardrails_config_staging_strengths` — same for `staging`; assert `MEDIUM`
    - `test_load_guardrails_config_prod_strengths` — same for `prod`; assert `HIGH`
    - _Requirements: 1.7, 1.8, 5.1, 5.2, 5.3_

  - [ ]* 3.5 Write property test for content filter completeness in `tests/property/test_guardrails_config_properties.py`
    - **Property 2: Loaded config contains all required content filter categories with valid strengths**
    - Generate valid guardrails YAML strings using `st.builds` with varying strength values for all six categories
    - Assert: loaded config always has all six keys (`HATE`, `INSULTS`, `SEXUAL`, `VIOLENCE`, `MISCONDUCT`, `PROMPT_ATTACK`) each with a value in `{"NONE", "LOW", "MEDIUM", "HIGH"}`
    - Tag: `# Feature: bedrock-guardrails-config, Property 2: loaded config contains all required content filter categories`
    - Decorate with `@settings(max_examples=100)`
    - **Validates: Requirements 1.4, 5.1, 5.2, 5.3**

  - [ ]* 3.6 Write property test for sensitive info type actions in `tests/property/test_guardrails_config_properties.py`
    - **Property 3: All sensitive_info_types entries have a valid action**
    - Generate valid guardrails config dicts with one or more `sensitive_info_types` entries using `st.lists(st.fixed_dictionaries({...}), min_size=1)`
    - Assert: for every entry in `config["sensitive_info_types"]`, `entry["action"]` is in `{"ANONYMIZE", "BLOCK"}`
    - Tag: `# Feature: bedrock-guardrails-config, Property 3: all sensitive_info_types entries have valid action`
    - Decorate with `@settings(max_examples=100)`
    - **Validates: Requirements 1.6**

- [ ] 4. Checkpoint — Ensure all unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Extend `ComputeStack` to accept optional guardrails stack
  - [ ] 5.1 Add `guardrails_stack` optional parameter to `ComputeStack.__init__` in `src/agentic_ai/infra/stacks/compute_stack.py`
    - Import `BedrockGuardrailsStack` using `TYPE_CHECKING` guard to avoid circular imports
    - Add `guardrails_stack: "BedrockGuardrailsStack | None" = None` to the constructor signature after `data_stack`
    - Build `container_env` dict first, then conditionally add `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` from `guardrails_stack.guardrail_id` and `guardrails_stack.guardrail_version` when `guardrails_stack is not None`
    - Pass the merged `container_env` dict to `task_def.add_container(..., environment=container_env, ...)`
    - When `guardrails_stack is None`, omit both guardrail env vars (preserving backwards compatibility)
    - _Requirements: 3.3, 3.4, 8.1_

  - [ ] 5.2 Add `bedrock:ApplyGuardrail` IAM permission to the ECS task role in `compute_stack.py`
    - Add the policy statement on `self.task_role` only when `guardrails_stack is not None`
    - Scope `resources` to `[guardrails_stack.guardrail_arn]` — never `Resource: "*"`
    - Add inline comment: `# bedrock:ApplyGuardrail — scoped to specific guardrail ARN (Req 4.4)`
    - Place this statement immediately after the existing `bedrock:InvokeModel` statement
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ] 6. Wire `BedrockGuardrailsStack` into `app.py`
  - [ ] 6.1 Update `src/agentic_ai/infra/app.py` to import and instantiate `BedrockGuardrailsStack`
    - Import `BedrockGuardrailsStack` from `.stacks.bedrock_guardrails_stack`
    - Read `guardrailsEnabled` from CDK context (default `True`) and include it in `raw_context`
    - Conditionally instantiate `guardrails_stack` after `data_stack` and before `compute_stack` when `context.guardrails_enabled` is `True`
    - Call `guardrails_stack.add_dependency(data_stack)` when the stack is instantiated
    - Pass `guardrails_stack=guardrails_stack` (or `None`) to `ComputeStack`
    - Add `compute_stack.add_dependency(guardrails_stack)` when `guardrails_stack is not None`
    - Follow the existing stack naming convention: `f"{prefix}-BedrockGuardrails"`
    - _Requirements: 3.1, 3.2, 3.5, 6.2, 6.3_

- [ ] 7. Write CDK assertion tests
  - [ ] 7.1 Create `tests/cdk/test_bedrock_guardrails_stack.py` with stack resource and SSM parameter assertions
    - Mirror fixture patterns from `tests/cdk/conftest.py`
    - Add fixtures for `BedrockGuardrailsStack` instances for each environment using the existing `cdk_context` fixture
    - `TestBedrockGuardrailsStackResource`: assert `resource_count_is("AWS::Bedrock::Guardrail", 1)` for each env; assert guardrail `Name` property equals `f"aiops-guardrail-{env}"`
    - `TestBedrockGuardrailsStackSSMParams`: assert `AWS::SSM::Parameter` resources exist with names `/aiops/{env}/bedrock-guardrail-id` and `/aiops/{env}/bedrock-guardrail-version`; assert version parameter `Value` is `"DRAFT"`
    - `TestBedrockGuardrailsStackTerminationProtection`: assert `prod_stack.termination_protection is True`; assert dev and staging stacks have it False/absent
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 7.1, 7.3, 7.4_

  - [ ] 7.2 Add `ComputeStack` guardrails integration and disabled-flag assertions to `tests/cdk/test_bedrock_guardrails_stack.py`
    - `TestComputeStackWithGuardrails`: synthesize a `ComputeStack` with a real `BedrockGuardrailsStack` passed as `guardrails_stack`; assert container env contains `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` via `Match.array_with`; assert `AWS::IAM::Policy` contains `bedrock:ApplyGuardrail` action; assert the resource ARN is not `"*"`
    - `TestComputeStackWithoutGuardrails`: synthesize `ComputeStack` with `guardrails_stack=None`; assert `BEDROCK_GUARDRAIL_ID` is absent from all container environments in the template; assert `bedrock:ApplyGuardrail` is absent from all IAM policies
    - `TestGuardrailsDisabledFlag`: use a `CdkContext` with `guardrails_enabled=False`; assert `resource_count_is("AWS::Bedrock::Guardrail", 0)` on the app-level template
    - _Requirements: 3.3, 3.4, 4.2, 6.3, 7.3, 7.5_

- [ ] 8. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass (`pytest -m "unit or cdk or property"`), ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- `_load_guardrails_config` is a pure function — test it without CDK; CDK stacks are covered by assertion tests
- `BedrockGuardrailsStack` must not modify `reasoning_agent.py` or any other runtime Python file
- Use `TYPE_CHECKING` guard in `compute_stack.py` for the `BedrockGuardrailsStack` import to avoid circular imports
- The `guardrails_stack=None` default in `ComputeStack` preserves full backward compatibility with existing deployments
- `bedrock:ApplyGuardrail` must never use `Resource: "*"` — always scope to the specific guardrail ARN per engineering-standards.md
- All new files must pass `ruff check` and `ruff format`; docstrings required on all public classes and functions

---

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["2.2", "3.1"] },
    { "id": 2, "tasks": ["3.2", "3.3", "3.4"] },
    { "id": 3, "tasks": ["3.5", "3.6", "5.1"] },
    { "id": 4, "tasks": ["5.2"] },
    { "id": 5, "tasks": ["6.1"] },
    { "id": 6, "tasks": ["7.1"] },
    { "id": 7, "tasks": ["7.2"] }
  ]
}
```
