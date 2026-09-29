# Feature Specification: Aria AI Relationship Manager

**Feature Branch**: `001-ai-relationship-manager`
**Created**: 2026-09-17
**Status**: Draft
**Source**: Migrated from `.kiro/specs/ai-relationship-manager/requirements.md`

## User Scenarios & Testing

### User Story 1 - Personalized Client Profile (Priority: P1)

As a client, I want Aria to understand my financial profile, family structure, risk appetite, and banking goals so that I receive personalized financial advice.

**Why this priority**: Personalization and safe risk assessment are the foundation for every other client journey.

**Independent Test**: Start a client session, provide profile and family information, and verify a named greeting, structured profile update, risk questionnaire before market recommendations, and CTG suggestion when eligible.

**Acceptance Scenarios**:
1. Given a client starts a conversation, when Aria responds, then Aria greets the client by name and acknowledges the stated need.
2. Given a client provides financial profile information, when the information is accepted, then Aria stores it as a structured CRM update.
3. Given a client asks about a market-linked product without an assessed risk appetite, when Aria handles the request, then Aria completes the structured risk questionnaire before recommending a product.
4. Given family members hold eligible bank accounts, when the client profile is evaluated, then Aria suggests CTG enrollment and explains the shared benefits.

### User Story 2 - Wallet Profiling and Consolidation (Priority: P2)

As a client, I want Aria to identify external banking assets and suggest consolidation opportunities so that I can benefit from centralized banking services.

**Independent Test**: Disclose external fixed deposits and Demat accounts and verify that the wallet profile is recorded and suggestions explain benefits without pressure.

**Acceptance Scenarios**:
1. Given a client discloses external assets, when the disclosure is processed, then Aria records a wallet profile in the CRM.
2. Given a wallet profile contains external fixed deposits or Demat accounts, when Aria presents options, then Aria explains the benefits of transferring them to the bank.
3. Given consolidation opportunities exist, when Aria communicates them, then the response is a value proposition and does not use high-pressure sales language.

### User Story 3 - Financial Product Recommendations (Priority: P2)

As a client, I want suitable financial product recommendations based on my needs and activity so that I can grow and protect my wealth effectively.

**Independent Test**: Use clients with different risk profiles and account activity, then verify risk-appropriate recommendations, eligible lending offers, protection products, and value-added benefits.

**Acceptance Scenarios**:
1. Given an investment inquiry and a completed risk profile, when Aria recommends options, then options include suitable Mutual Fund SIPs, Fixed Deposits, or Demat facilities.
2. Given account activity indicates a qualifying balance, when Aria reviews opportunities, then Aria informs the client of eligible loans, overdrafts, or premium cards.
3. Given a client profile indicates a protection need, when Aria recommends services, then relevant insurance, tax payment, and bill pay options are presented.
4. Given products have value-added benefits, when Aria presents them, then fee waivers, preferential rates, and concierge access are highlighted without hard selling.

### User Story 4 - Retention and Maturity Management (Priority: P2)

As a client, I want proactive notifications about upcoming maturities and large outflows so that I can reinvest or rebalance in time.

**Independent Test**: Supply maturity and outflow events at threshold boundaries and verify notifications, reinvestment pathways, and current rate references.

**Acceptance Scenarios**:
1. Given a maturity event is within 30 days, when the event is evaluated, then Aria notifies the client and suggests reinvestment pathways.
2. Given a large outflow is detected, when the event is evaluated, then Aria offers portfolio rebalancing or suitable high-yield options.
3. Given reinvestment options are presented, when rates are shown, then rates come from the current knowledge base.

### User Story 5 - Service Query Resolution (Priority: P1)

As a client, I want accurate answers to banking questions and clear next actions without delay.

**Independent Test**: Ask account, charge, documentation, and transaction questions and verify sourced answers, step-by-step instructions, concise formatting, and escalation when unresolved.

**Acceptance Scenarios**:
1. Given a question about account features, charges, or documents, when Aria answers, then the answer is sourced from the knowledge base.
2. Given a transaction procedure question, when Aria answers, then the response contains clear sequential next actions.
3. Given complex options or steps, when Aria responds, then concise bullet points are used.
4. Given Aria cannot resolve a query, when the response is completed, then the query is escalated to a human RM with full context.

### User Story 6 - CRM Interaction Logging (Priority: P1)

As a human RM, I want key interactions, preferences, and follow-ups logged so that I have a complete engagement record.

**Independent Test**: Complete an interaction with preferences and follow-up actions and verify a structured CRM summary, segment/date tags, and scheduled reminders.

**Acceptance Scenarios**:
1. Given an interaction concludes, when logging runs, then topics, preferences, and follow-up actions are stored in a structured summary.
2. Given a client has segment flags, when a CRM entry is created, then it includes segment flags and interaction date.
3. Given a follow-up action is identified, when logging completes, then a CRM reminder is scheduled.

### User Story 7 - Sensitive Credential Protection (Priority: P1)

As a client, I want protection from sharing sensitive security information.

**Independent Test**: Submit messages containing PINs, CVVs, OTPs, and passwords and verify warning, refusal, non-storage, and redaction before further processing.

**Acceptance Scenarios**:
1. Given a client attempts to share sensitive credentials, when the message is received, then Aria immediately instructs the client to stop and explains the risk.
2. Given sensitive credentials are present, when processing occurs, then Aria refuses to accept, process, or store them.
3. Given credentials appear in a message, when the message enters processing, then the guardrail engine redacts them first.

### User Story 8 - Market Risk Disclosure (Priority: P1)

As a client, I want clear risk disclosures for market-linked products.

**Independent Test**: Request a market-linked recommendation and a fixed-income rate and verify risk language, no guaranteed returns, and current guaranteed-rate sourcing.

**Acceptance Scenarios**:
1. Given a market-linked product is discussed, when Aria responds, then it states that the product is subject to market risks.
2. Given a market-linked product is discussed, when Aria responds, then it does not promise or guarantee a return.
3. Given a fixed-income product is discussed, when Aria responds, then it presents the guaranteed rate from the knowledge base.

### User Story 9 - Regulatory Compliance (Priority: P1)

As a compliance officer, I want KYC and AML standards enforced.

**Independent Test**: Exercise current, missing, and expired KYC states plus AML threshold activity and verify gating, required-document guidance, flagging, and escalation.

**Acceptance Scenarios**:
1. Given a client requests a product or account, when processing begins, then current KYC documentation is verified.
2. Given KYC is missing or expired, when a product request is made, then the request pauses and required documents are explained.
3. Given activity crosses AML monitoring thresholds, when it is evaluated, then it is flagged and escalated to compliance.

### User Story 10 - Human RM Escalation (Priority: P1)

As a client, I want complex or sensitive requests routed to an appropriate human advisor.

**Independent Test**: Submit high-value credit, legal dispute, freeze, complex fraud, estate planning, and treasury requests and verify context, notification, and expected timelines.

**Acceptance Scenarios**:
1. Given a high-value commercial credit request, when classified, then it is escalated to a human RM or credit underwriter.
2. Given a legal dispute, account freeze, or complex fraud case, when reported, then it is escalated with full interaction context.
3. Given estate planning or custom treasury needs, when requested, then it is escalated to a human RM.
4. Given an escalation is created, when Aria responds, then the client receives the escalation status and expected response timeline.

### User Story 11 - Actionable Conversation Style (Priority: P2)

As a client, I want professional, empathetic, personalized, and actionable communication.

**Independent Test**: Run representative conversations and verify the client's name, professional tone, clear next steps, and concise bullets for multiple options.

**Acceptance Scenarios**:
1. Given any client interaction, when Aria responds, then the client is addressed by name.
2. Given an interaction concludes, when Aria responds, then clear next steps are included.
3. Given any response, when tone is evaluated, then it is professional, courteous, and empathetic.
4. Given multiple options are presented, when Aria responds, then concise bullets are used.

### User Story 12 - Prompt Injection Defense (Priority: P1)

As a system administrator, I want prompt injection and adversarial inputs blocked.

**Independent Test**: Submit prompt override attempts and verify detection, blocking, logging, polite refusal, and no system-detail leakage.

**Acceptance Scenarios**:
1. Given an incoming message, when it enters the system, then the guardrail engine checks it for injection patterns before Aria processes it.
2. Given an injection attempt is detected, when the guardrail evaluates it, then the message is blocked and the attempt is logged.
3. Given an instruction attempts to override Aria's role, when Aria handles it, then Aria refuses the override.
4. Given adversarial input is detected, when Aria responds, then the refusal does not reveal internal system details.

### User Story 13 - Knowledge Base Accuracy (Priority: P1)

As a client, I want current product rates and policy information with source dates.

**Independent Test**: Query available and unavailable product information and verify current retrieval, source-date citation, and escalation when no relevant information exists.

**Acceptance Scenarios**:
1. Given a question about rates or terms, when Aria answers, then it retrieves the latest relevant knowledge-base information.
2. Given no relevant information exists, when Aria handles the query, then it informs the client and escalates to a human RM.
3. Given a rate is presented, when the response is generated, then the source date is cited.

### User Story 14 - CRM and API Context (Priority: P1)

As a system administrator, I want CRM context available at session start so service and recommendations match the client tier.

**Independent Test**: Start sessions with available, unavailable, and varied CRM segment data and verify retrieval, personalization, limited-functionality messaging, and incident logging.

**Acceptance Scenarios**:
1. Given a client session begins, when context loads, then segment flags and account summary are retrieved.
2. Given segment flags are available, when recommendations are generated, then product recommendations and service levels match the tier.
3. Given the CRM is unavailable, when a session begins, then the client is informed of limited functionality and the incident is logged.

## Edge Cases

- CRM, knowledge base, core banking, or guardrail services are unavailable or return malformed data.
- KYC is missing or expires during a product request.
- A maturity occurs exactly 30 days away, has already matured, or has a negative day count.
- A client discloses multiple external assets in one message.
- A message contains several credential types or an injection attempt combined with credentials.
- Knowledge-base results have low confidence, stale source dates, or conflicting rates.
- A session is missing or corrupted during load.
- A client requests a high-risk or regulated action outside Aria's authority.

## Requirements

### Functional Requirements

- **FR-001**: Aria MUST load and update structured client profiles, family relationships, risk appetite, preferences, accounts, and wallet profiles.
- **FR-002**: Aria MUST complete risk assessment before market-linked recommendations.
- **FR-003**: Aria MUST provide risk-appropriate product, lending, protection, payment, and value-added recommendations without high-pressure language.
- **FR-004**: Aria MUST detect maturities within 30 days and configured large outflows, then provide retention options using current rates.
- **FR-005**: Aria MUST answer service questions from the knowledge base and provide actionable procedures or escalate unresolved queries.
- **FR-006**: Aria MUST log structured interaction summaries, client preferences, segment flags, dates, and follow-up reminders to the CRM.
- **FR-007**: Aria MUST warn about, reject, and redact sensitive credentials before further processing; credentials MUST never be stored.
- **FR-008**: Aria MUST disclose market risk, avoid guaranteed-return claims, and cite guaranteed fixed-income rates from the knowledge base.
- **FR-009**: Aria MUST enforce current KYC before new products and flag AML threshold activity for compliance review.
- **FR-010**: Aria MUST escalate high-value credit, legal disputes, freezes, complex fraud, estate planning, and custom treasury requests with context and timelines.
- **FR-011**: Aria MUST use the client's name, professional and empathetic language, concise bullets, and clear next steps.
- **FR-012**: The guardrail engine MUST detect, block, log, and safely refuse prompt injection without revealing internal details.
- **FR-013**: Aria MUST retrieve current product and policy information, cite source dates, and escalate when knowledge is unavailable.
- **FR-014**: Aria MUST retrieve CRM segment flags and account summaries at session start and degrade gracefully when CRM is unavailable.
- **FR-015**: The system MUST expose the agent through authenticated chat and administrative API entry points and support scheduled proactive events.
- **FR-016**: The system MUST maintain typed authoritative workflow state independently from conversation history and durable memory.
- **FR-017**: User corrections MUST be represented as atomic state patches with optimistic revision checks; rejected patches MUST preserve the previous valid state.
- **FR-018**: The system MUST maintain declarative transitive dependencies, mark derived values stale after accepted changes, and return the earliest affected workflow step.
- **FR-019**: AgentCore Runtime session IDs MUST be unique per user conversation, reused for related turns, mapped to the authenticated user, and recoverable through durable state after session termination.
- **FR-020**: AgentCore Memory MUST be tenant/user scoped and limited to durable preferences, facts, and summaries; it MUST NOT override current validated workflow state.
- **FR-021**: AgentCore Gateway tool visibility MUST be limited to relevant workflow capabilities, while IAM, Gateway policies, OAuth scopes, and backend authorization enforce access independently.
- **FR-022**: The system MUST apply configured Amazon Bedrock Guardrails to input and output, handle intervention outcomes explicitly, redact protected content, and avoid logging raw protected content.
- **FR-023**: The system MUST enforce bounded timeouts, safe retries, idempotency for side effects, cancellation, concurrency control, structured redacted observability, and environment-specific configuration.
- **FR-024**: Python implementation MUST use typed boundaries, timezone-aware timestamps, dependency pinning, formatting, linting, static type checking, security scanning, and automated tests in CI.
- **FR-025**: Infrastructure MUST be defined with AWS CDK v2 using reusable constructs and a small number of stacks based on deployment and lifecycle boundaries.
- **FR-026**: Stateful infrastructure MUST be isolated from stateless compute, and production data resources MUST use explicit retention, encryption, termination-protection, and backup policies.
- **FR-027**: CDK synthesis MUST be deterministic and free of side effects; lookup context MUST be reviewed and committed when used, and deployment MUST require synthesis and diff validation.
- **FR-028**: CDK IAM roles MUST use the organization-approved permissions boundary and least-privilege grants; resource wildcard permissions require documented service-level justification.
- **FR-029**: Infrastructure MUST use direct CDK references within one app where appropriate and SSM only for independently deployed or runtime-resolved handoffs; physical names MUST be explicit only where contractual stability requires them.
- **FR-030**: CDK MUST include fine-grained assertions, limited snapshots, CDK Nag or equivalent checks, tagging, log retention, alarms, and non-production integration tests before production deployment.
- **FR-031**: Production deployment MUST use a dedicated federated deployment role, reviewed change sets or equivalent approvals, environment-specific configuration, rollback procedures, and no long-lived access keys.
- **FR-032**: Agent entrypoints MUST use a shared framework runner for common configuration, model construction, Gateway client setup, memory/context assembly, lifecycle hooks, and observability; agent-specific modules MUST contain only domain behavior and approved extension hooks.
- **FR-033**: Shared framework extension points MUST use typed, runtime-checkable protocols or equivalent contracts for prompt construction, payload parsing, tool filtering, skills, and pre-invocation guards.
- **FR-034**: Framework configuration MUST be loaded lazily inside the Runtime invocation boundary, cached safely after loading, sourced from approved environment/SSM configuration, and never loaded through network calls at module import time.
- **FR-035**: Gateway authentication, MCP client lifecycle, retries, timeouts, and cleanup MUST be centralized in the shared framework; credentials and raw sensitive payloads MUST not appear in agent entrypoints or logs.
- **FR-036**: Agent-specific system prompts MUST expose a documented dynamic-context boundary, keep stable instructions separate from per-turn state, and use a cache-point strategy only when supported and verified for the pinned model/API version.
- **FR-037**: Memory injection MUST be bounded, scoped, and ordered so current validated workflow state takes precedence over short-term and long-term memory; memory writes MUST occur on success and failure paths without persisting framework markers or secrets.
- **FR-038**: Shared lifecycle hooks MUST provide standardized request, model, tool, guardrail, memory, and completion telemetry, including latency, token usage, cache metrics when available, retries, stop reasons, and redacted error categories.
- **FR-039**: Agent-specific business logic MUST remain outside the shared framework; adding an agent SHOULD require a manifest, prompt builder, entrypoint, and only the optional parser/filter/guard/skills modules it needs.

### Key Entities

- **ClientProfile**: Client identity, segment, flags, risk, family, accounts, wallet, KYC, and preferences.
- **WalletProfile**: External deposits, Demat accounts, insurance, estimated assets, and consolidation opportunities.
- **InteractionSummary**: Topics, preferences, follow-ups, segment flags, date, and context.
- **RiskProfile**: Questionnaire responses, weighted score, risk level, and eligible product categories.
- **KnowledgeResponse**: Product information, confidence, rate, terms, and source date/citation.
- **MaturityEvent** and **OutflowEvent**: Proactive retention triggers and relevant account details.
- **EscalationTicket**: Reason, priority, context, assigned human team, and response timeline.
- **Session**: Client context, messages, state, and lifecycle status.
- **GuardrailResult**: Sanitized content, detection flags, refusal status, and audit information.

## Success Criteria

- **SC-001**: 100% of market-linked recommendations have a completed risk assessment and risk disclosure before recommendation.
- **SC-002**: 100% of detected credential-bearing messages are rejected and redacted before agent processing.
- **SC-003**: 100% of completed interactions produce a structured CRM summary with date and segment flags.
- **SC-004**: 100% of unresolved service queries and regulated escalation categories create a human escalation with context.
- **SC-005**: 100% of displayed rates include a knowledge-base source date.
- **SC-006**: Maturity events at or below 30 days trigger notifications; events beyond 30 days do not.
- **SC-007**: The primary client journey can be exercised independently with mocked external services and automated tests.
- **SC-008**: CRM and knowledge-base outages result in safe limited-functionality behavior without fabricated financial advice.
- **SC-009**: Accepted corrections update one workflow revision atomically and invalidate every direct and transitive dependent value without discarding unrelated valid state.
- **SC-010**: Unauthorized, locked, or invalid updates are rejected deterministically with the prior valid state preserved.
- **SC-011**: A resumed Runtime session reconstructs current workflow state from durable storage and does not rely on ephemeral in-memory state alone.
- **SC-012**: Production CI blocks changes that fail formatting, linting, type checking, security scanning, or the required unit/property/contract test suites.
- **SC-013**: `cdk synth` produces deterministic templates for each configured environment without network or account mutation during synthesis.
- **SC-014**: CDK unit tests detect changes to stateful logical IDs, encryption, permissions boundaries, removal policies, tags, log retention, alarms, and environment configuration.
- **SC-015**: Production deployment cannot proceed without successful CDK tests, synthesis, security checks, diff/change-set review, and an approved deployment role.
- **SC-016**: A new agent can be added without modifying the shared runner or CDK wiring, subject to manifest/schema and framework contract tests.
- **SC-017**: Framework configuration failures are reported at invocation time with safe diagnostics, not as import-time Runtime crashes.
- **SC-018**: Framework tests verify cleanup and telemetry on successful, rejected, interrupted, timed-out, and failed tool/model paths.

## Assumptions

- The initial implementation targets Python 3.11 and AWS services described in the migrated design.
- Salesforce or CRM Next, Amazon Bedrock, Bedrock Guardrails, Bedrock Knowledge Bases, DynamoDB, EventBridge, API Gateway, and CloudWatch access are provisioned separately.
- External service contracts and credentials will be supplied through environment configuration and are not committed to the repository.
- This migration preserves the Kiro scope; detailed service thresholds, response timelines, retention periods, and authentication claims are implementation decisions to confirm during planning.
- `.kiro/specs/ai-relationship-manager/` remains the original source record for the migration.
