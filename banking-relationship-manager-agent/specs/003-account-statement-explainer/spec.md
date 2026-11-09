# Feature Specification: Account Statement Explainer Subagent

**Feature Branch**: `003-account-statement-explainer`
**Created**: 2026-10-01
**Status**: Draft
**Input**: Requirements from `Uc6_Account_Statement_Explainer_Agent_Requirements_Summary.docx`, adapted to the existing Aria agent as a specialist subagent.

## User Scenarios & Testing

### User Story 1 - Aria Hands Off Statement Questions (Priority: P1)

As a relationship manager using the authenticated Aria API, I want Aria to hand statement-specific questions to a focused specialist so that authorized transaction analysis stays bounded and does not disrupt existing banking workflows.

**Why this priority**: The specialist must be reachable from the existing parent agent while preserving Aria's identity, session, guardrails, and tool boundaries.

**Independent Test**: Invoke the parent Aria agent with a statement question and verify one explicit handoff to the specialist; invoke it with a non-statement question and verify existing behavior is unchanged.

**Acceptance Scenarios**:

1. **Given** a statement assigned to the verified relationship manager, **When** the user asks Aria about its transactions, **Then** Aria delegates to the statement subagent and returns an answer grounded in Gateway-retrieved rows.
2. **Given** a question unrelated to the loaded statement, **When** the user asks Aria, **Then** the statement subagent is not invoked.
3. **Given** statement data is unavailable or invalid, **When** a statement question is delegated, **Then** the specialist reports that limitation without inventing transactions or changing Aria's session identity.
4. **Given** the production Runtime has not explicitly enabled statement analysis, **When** Aria is deployed, **Then** the statement child is not registered; when explicitly enabled, all statement reads still pass through the authorized Gateway backend.

### User Story 2 - Analyze Statement Activity (Priority: P1)

As a relationship manager, I want deterministic tools to find, summarize, categorize, compare, and explain statement entries so that answers are grounded in authorized statement records.

**Why this priority**: The specialist's value depends on reliable transaction-level calculations, not model-generated arithmetic.

**Independent Test**: Run each analysis tool against an isolated DynamoDB test table with known rows and verify exact rows, aggregates, category totals, comparisons, and transaction explanations.

**Acceptance Scenarios**:

1. **Given** a transaction ID or date range, **When** the specialist searches or explains it, **Then** the answer cites matching transaction IDs, value dates, debit/credit direction, amount, and narrative from the authorized backend.
2. **Given** a multi-hop question about a balance drop, **When** Aria delegates it, **Then** the specialist summarizes the month, checks anomalies, retrieves contributing debits, and explains only those results.
3. **Given** a category comparison question, **When** the specialist compares current and prior periods, **Then** it reports both totals, the difference, and the transactions that drive the change.

### User Story 3 - Follow the Analysis Safely (Priority: P1)

As a relationship manager, I want safe status and cited transaction references so that I can follow the result without exposing private model reasoning or unnecessary statement data.

**Why this priority**: A visible, trustworthy explanation is central to safe financial-data access, while hidden chain-of-thought and raw financial data must remain private.

**Independent Test**: Observe a multi-tool request and verify ordered safe status/tool events, a final answer, and no hidden reasoning, credentials, or unnecessary statement rows.

**Acceptance Scenarios**:

1. **Given** a query requiring multiple tools, **When** processing begins, **Then** the response and protected operational trace contain safe tool status, completion summaries, and cited transaction IDs.
2. **Given** tool inputs or results contain data beyond what is needed for the answer, **When** events are emitted or audited, **Then** only bounded, redacted summaries are exposed.
3. **Given** a tool fails or returns malformed data, **When** the specialist continues or stops, **Then** a safe failure event is shown and unsupported conclusions are omitted.

### User Story 4 - Access Only Assigned Statements (Priority: P1)

As a relationship manager, I want the statement service to return only statements assigned to my verified identity so that I cannot access another tenant's or user's financial data.

**Why this priority**: Statement confidentiality depends on backend authorization, not model instructions or caller-supplied identifiers.

**Independent Test**: Gateway contract tests verify authorized reads succeed, unassigned statement references fail closed, and raw statement tools are not exposed directly to the Runtime parent.

**Acceptance Scenarios**:

1. **Given** a verified tenant/user principal, **When** the specialist requests available statements, **Then** the Gateway returns only active statement references mapped to that principal.
2. **Given** an unknown, expired, or unassigned statement reference, **When** the Gateway is called, **Then** it returns a generic denial without querying or exposing transaction rows.
3. **Given** an analysis request, **When** the child invokes Gateway tools, **Then** verified identity is injected by trusted Runtime code and cannot be chosen or overridden by the model.

### Edge Cases

- No statement is selected, the selected statement has fewer than the required rows, or date coverage is shorter than three months.
- A transaction ID is absent or duplicated; dates are invalid or reversed; amounts are malformed; debit/credit indicator is unknown.
- A query refers to a category with zero baseline activity or to a period outside the fixture's date range.
- A transaction narrative contains prompt-injection text or credential-like strings.
- A tool times out, returns no rows, returns malformed values, or produces an unsupported category.
- A user switches statements during a conversation or submits a follow-up after the statement context expires.
- The model attempts to answer from prior knowledge or emits a statement not supported by tool outputs.

## Requirements

### Functional Requirements

- **FR-001**: The statement explainer MUST be an Aria-owned specialist subagent exposed to the parent through a single bounded handoff tool; it MUST NOT create a separately deployed AgentCore Runtime.
- **FR-002**: Aria MUST delegate statement-related questions to the specialist and retain existing behavior for unrelated questions.
- **FR-003**: The specialist MUST use a deterministic tool suite with the capabilities `get_transactions`, `summarise_period`, `detect_anomalies`, `categorise_spend`, and `explain_transaction`.
- **FR-004**: Transaction filtering MUST support date range, debit/credit direction, minimum amount, and narrative keyword; transaction explanation MUST resolve a unique transaction ID and return the source row fields.
- **FR-005**: Period summaries MUST report debit totals, credit totals, net movement, average transaction size, and category totals derived from matching rows.
- **FR-006**: Category comparisons MUST identify both periods, their totals, the absolute change, and contributing transaction IDs.
- **FR-007**: Anomaly analysis MUST compare a selected current period with the preceding three complete months for the same category and return its baseline, deviation, and contributing transactions.
- **FR-008**: The specialist MUST answer only from validated tool results; if the result is absent, ambiguous, malformed, or insufficient, it MUST state the limitation and not fabricate data.
- **FR-009**: The parent and specialist MUST preserve the authenticated Aria tenant/user/session context; statement rows MUST remain scoped to authorized statement references and MUST NOT enter long-term AgentCore Memory.
- **FR-010**: Production statement records MUST be stored in DynamoDB using the source fields `TRANS.ID`, `VALUE.DATE`, `AMOUNT`, `DR.CR.IND`, `NARRATIVE`, `CATEGORY`, and `BALANCE.AFTER`. Records MUST be populated only by a trusted administrative/source process; no model-callable write tool is permitted.
- **FR-011**: Every statement data read MUST go through the AgentCore Gateway Lambda target. The Gateway MUST verify the injected verified-principal scope against an active statement entitlement before reading transaction rows.
- **FR-012**: Operational traces MUST contain correlation IDs, ordered tool names, bounded sanitized summaries, and cited transaction IDs; they MUST NOT contain private chain-of-thought, credentials, raw prompts, or unnecessary full statement payloads.
- **FR-013**: Final answers MUST cite source transaction IDs and report only values derived from authorized Gateway results.
- **FR-014**: Follow-up questions MUST retain only an opaque active statement reference and bounded conversation context; every subsequent Gateway read MUST re-check the current entitlement.
- **FR-015**: The production feature MUST use the existing authenticated Aria API and Runtime, with no local statement API, real statement upload endpoint, or separately deployed statement Runtime.
- **FR-016**: Tool failures MUST be visible as safe activity events and MUST NOT be silently converted into successful or unsupported answers.
- **FR-017**: Existing Aria Cognito authentication, KYC/AML policy, tenant authorization, and deployment boundaries MUST NOT be weakened or bypassed by the demo handoff.
- **FR-018**: Production Runtime registration of the statement child MUST be controlled by an explicit deployment setting that defaults to disabled. When enabled, the child MUST remain inside the existing authenticated Aria Runtime and MUST access statements only through Gateway; it MUST NOT change Cognito, tenant, KYC/AML, Gateway authorization, or session controls.

### Key Entities

- **StatementTransaction**: One validated synthetic ledger row with unique transaction ID, value date, decimal amount, debit/credit direction, narrative, category, and balance-after value.
- **StatementEntitlement**: A trusted mapping from a hashed verified tenant/user principal to an opaque statement reference and safe display metadata.
- **StatementRecord**: One normalized DynamoDB transaction row retrieved only after the entitlement check.
- **StatementAnalysisRequest**: A user question plus the active statement/session reference and validated date/category filters.
- **StatementToolResult**: A deterministic result containing operation, bounded values, source transaction IDs, and a safe summary.
- **AgentActivityEvent**: An ordered, user-safe status/tool/result event; it is not model private reasoning.
- **StatementExplainerSession**: A session binding the parent Aria identity to one opaque authorized statement reference and bounded follow-up context.
- **StatementAuditRecord**: A safe operational record of the sanitized question, tool sequence, bounded summaries, and cited IDs; it excludes raw statement rows.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All five analysis tools return exact expected results for deterministic fixtures, including debit/credit and date-boundary cases.
- **SC-002**: All five analysis tools return exact results from Gateway-retrieved rows, with multi-hop scenarios invoking the expected tools in order.
- **SC-003**: Every amount, date, category total, anomaly, and cited transaction in the final response is traceable to tool output; tests detect unsupported values.
- **SC-004**: The activity trace shows ordered safe events for every tool call and never contains hidden chain-of-thought or unredacted credential-like data.
- **SC-005**: Gateway reads succeed only for active statement entitlements and fail closed for unassigned or revoked references.
- **SC-006**: Single-tool queries complete within 10 seconds and three-tool queries within 20 seconds in the configured demo environment; the first safe activity event appears within 3 seconds when the configured model service is available.
- **SC-007**: Existing Aria authentication, KYC fail-closed behavior, and unrelated parent-agent tests remain unchanged and pass.
- **SC-008**: Infrastructure synthesis proves the statement child setting is disabled by default and is enabled only by explicit operator configuration, without adding a Runtime or granting DynamoDB access to the Runtime role.

## Assumptions

- Statement and entitlement records are provisioned into DynamoDB by a trusted administrative or source-system process; the agent and Gateway expose no write operation.
- The statement specialist is a child Strands Agent exposed to the existing Aria parent as a tool. It reuses the parent request identity and model configuration and is not independently deployed or externally authenticated.
- The three-month anomaly baseline uses the preceding three complete calendar months. For this prototype, an anomaly is category spend at least 50% above the baseline monthly average, with the calculation and threshold visible in the result; threshold tuning is not a production risk policy.
- Transaction calculations use decimal arithmetic. `net movement` means credits minus debits during the selected period, not a claim about the core account's authoritative balance.
- Category comes from the synthetic row when supplied; deterministic narrative mapping is a fallback, and unknown narratives remain `uncategorized` rather than being guessed by the model.
- The relationship-manager assignment table is the authorization source; it is maintained outside the model/runtime request path and indexed by a hash of the verified tenant/user identity.
- Production Runtime registration remains operator-controlled and defaults off until DynamoDB data and entitlement records are provisioned and integration tests pass.
- Raw transactions are not persisted in AgentCore Memory or application logs; DynamoDB retention and deletion follow the bank's approved data policy.
