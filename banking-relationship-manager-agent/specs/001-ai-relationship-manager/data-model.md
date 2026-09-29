# Data Model: Aria AI Relationship Manager

## ClientProfile

Represents the client context loaded at session start and updated during conversation.

- `client_id`: required stable identifier.
- `name`: required non-empty display name.
- `segment`: `PREMIER` or `IMPERIA`.
- `segment_flags`: list of tier and eligibility flags.
- `risk_appetite`: nullable until assessment; `CONSERVATIVE`, `MODERATE`, or `AGGRESSIVE`.
- `family_members`: related eligible family accounts.
- `accounts`: account summaries and qualifying balances.
- `wallet_profile`: nullable external-asset profile.
- `kyc_status`: current, expired, missing, and missing-document details.
- `preferences`: client communication and product preferences.
- `created_at`, `updated_at`: timestamps.

## WalletProfile

Represents external assets and consolidation opportunities.

- `external_fds`: external fixed deposits.
- `external_demat`: external Demat accounts.
- `external_insurance`: external insurance holdings.
- `estimated_external_assets`: estimated external value.
- `consolidation_opportunities`: asset type, institution, value, and benefit explanation.
- `last_updated`: timestamp.

## RiskProfile

Represents a completed risk questionnaire.

- `responses`: question, selected option, score, and weight.
- `weighted_score`: deterministic total.
- `risk_level`: conservative, moderate, or aggressive.
- `eligible_product_categories`: products allowed for the level.
- `assessed_at`: timestamp.

Validation: no market-linked recommendation may be emitted without a current risk profile.

## InteractionSummary

Represents the CRM record for a completed interaction.

- `client_id`, `session_id`: required identifiers.
- `topics_discussed`: non-empty list for completed interactions.
- `client_preferences`: captured preferences.
- `follow_up_actions`: action, due date, and assignee.
- `segment_flags`: copied from client context.
- `interaction_date`: required timestamp.
- `escalation_id`: optional related ticket.

## KnowledgeResponse

Represents retrieved rate, policy, or product information.

- `content`: answerable source content.
- `product_category`: optional category.
- `confidence_score`: numeric confidence.
- `source_date`: required when presenting a rate.
- `citations`: source identifiers and locations.

Validation: low-confidence or absent results must trigger limited functionality and escalation, not invented content.

## MaturityEvent and OutflowEvent

- `client_id`, `account_id`: required identifiers.
- `event_date` or `detected_at`: timestamp.
- `days_until_maturity`: notification when `<= 30`.
- `amount`: event amount.
- `threshold`: configured outflow threshold.
- `status`: pending, notified, handled, or escalated.

## EscalationTicket

- `ticket_id`, `client_id`: required identifiers.
- `reason`: high-value credit, legal dispute, freeze, fraud, estate planning, treasury, unresolved query, or compliance.
- `priority`: derived from reason.
- `context`: interaction history, client profile summary, and relevant evidence.
- `assigned_team`: human RM, credit underwriting, or compliance.
- `response_timeline`: client-visible expected response.
- `status`: open, assigned, resolved.

## Session

- `session_id`, `client_id`: required identifiers.
- `profile_snapshot`: client context at session start.
- `messages`: sanitized inbound and outbound messages.
- `status`: active, ended, or recovery-required.
- `created_at`, `updated_at`: timestamps.

Validation: raw sensitive credentials must never enter a persisted session.

## GuardrailResult

- `sanitized_message`: redacted message safe for downstream processing.
- `credential_detected`: boolean.
- `injection_detected`: boolean.
- `blocked`: boolean.
- `reason`: safe user-facing category.
- `audit_id`: structured log reference.

## WorkflowState

Authoritative current state for one workflow instance. This entity is persisted independently of conversation history and AgentCore Memory.

- `workflow_name`: stable workflow identifier.
- `workflow_instance_id`: unique business workflow identifier.
- `revision`: monotonically increasing optimistic-concurrency version.
- `status`: `not_started`, `in_progress`, `blocked`, `awaiting_confirmation`, `complete`, or `cancelled`.
- `current_step`: current validated workflow step.
- `known`: field values accepted by validation.
- `missing`: required fields not yet available.
- `invalid`: fields rejected by validation with safe reason codes.
- `stale`: accepted values invalidated by a dependency change.
- `confirmed`: fields explicitly confirmed by the user or authorized process.
- `locked`: fields that cannot be changed at the current stage.
- `updated_at`: timezone-aware UTC timestamp.

## StatePatch

Model-proposed changes to `WorkflowState`.

- `operations`: ordered `set` or `clear` operations with field names and values.
- `reason`: concise user-intent explanation.
- `requires_confirmation`: true for irreversible or externally visible actions.
- `source_message_id`: traceable input identifier.

Validation rules:

- Unknown fields are rejected.
- Locked or unauthorized fields are rejected.
- Patches are validated atomically; partial application is not allowed.
- Accepted patches increment `revision` exactly once.
- A stale revision causes a retryable conflict, not an overwrite.
- Accepted changes trigger transitive dependency invalidation.

## DependencyRule

Declarative mapping from changed fields to dependent derived fields and earliest affected workflow step.

- `source_field`: field whose change triggers invalidation.
- `dependent_fields`: directly dependent fields.
- `affected_step`: earliest workflow step that must be revisited.
- `reason_code`: safe explanation shown to the agent and audit record.

## AuthorizationContext

Request-scoped identity and permissions used outside the model.

- `user_id`, `tenant_id`, `session_id`, `correlation_id`: required identifiers.
- `scopes`: approved capabilities.
- `client_id`: CRM subject authorized for this request.
- `allowed_tools`: capability-level allowlist, never the sole authorization boundary.
- `request_source`: API, event, or internal workflow.

## AgentManifest

Deployment and framework configuration for one independently discoverable agent.

- `agent_name`: stable identifier validated against repository naming rules.
- `runtime_name_suffix`: deployment/runtime suffix owned by CDK.
- `description`: human-readable capability description.
- `entry_point`: repository-root-relative Runtime entrypoint path.
- `framework`: namespaced tuning for model, context, memory, tool limits, retries, and feature flags.

Validation: deployment fields and framework fields are schema-separated; unknown fields, unsafe paths, invalid numeric bounds, and unapproved model or tool values are rejected before synthesis or Runtime startup.

## FrameworkConfig

Validated immutable configuration loaded lazily within the Runtime invocation boundary.

- `model_id`, `model_region`, `max_tokens`, `temperature`: model controls.
- `gateway_id`, `memory_id`, `memory_region`: AgentCore integration identifiers.
- `workflow_table`, `conversation_table`: durable persistence identifiers.
- `context_strategy`, `memory_top_k`, `tool_timeout_seconds`, `retry_max_attempts`: bounded operation controls.
- `feature_flags`: environment-specific behavior switches.

Validation: configuration is never fetched from SSM or another network service at module import time; secrets and raw credentials are not represented in logs or prompt context.

## ObservabilityEvent

Redacted telemetry emitted by the shared framework.

- `correlation_id`, `runtime_session_id`, `workflow_instance_id`, `revision`: request identity.
- `agent_name`, `action`, `current_step`, `stop_reason`: execution outcome.
- `selected_tools`, `tool_latency_ms`, `model_latency_ms`, `total_latency_ms`, `retry_count`: performance metadata.
- `validation_result`, `invalidated_fields`, `error_category`: safe diagnostics.

Validation: event payloads exclude secrets, raw credentials, raw prompts, and unnecessary client data.
