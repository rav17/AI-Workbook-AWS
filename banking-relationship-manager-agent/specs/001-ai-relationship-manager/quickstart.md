# Quickstart: Aria AI Relationship Manager

## Prerequisites

- Python 3.11
- AWS credentials for a non-production test account when running provider integration tests
- Configured Bedrock model, Guardrails, and Knowledge Base identifiers
- A test CRM adapter or mocked CRM fixture

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

The project must also define reproducible tooling in `pyproject.toml` and lock or pin production dependencies. Use the exact pinned Strands and AgentCore SDK versions documented by the implementation.

Create local environment configuration without committing secrets:

```text
AWS_REGION=<test-region>
BEDROCK_MODEL_ID=<test-model-id>
BEDROCK_GUARDRAIL_ID=<test-guardrail-id>
BEDROCK_KNOWLEDGE_BASE_ID=<test-knowledge-base-id>
CRM_API_BASE_URL=<test-crm-url>
DYNAMODB_SESSION_TABLE=<test-session-table>
```

## Validation scenarios

1. Run the unit suite with provider clients mocked. Verify client profile loading, risk scoring, CRM logging, escalation, and credential redaction.
2. Submit a message containing a PIN, CVV, OTP, or password. Verify a refusal is returned and the raw credential is absent from tool calls, logs, and session storage.
3. Submit a prompt injection attempt. Verify it is blocked, logged, and answered without internal details.
4. Submit an investment request without a risk profile. Verify the risk questionnaire precedes any recommendation.
5. Submit a rate query. Verify the result contains a knowledge-base citation and source date; force low confidence and verify escalation.
6. Run maturity boundary cases at 30 and 31 days and verify only the 30-day case triggers notification.
7. Run current, expired, and missing KYC cases and verify product requests are gated until documentation is current.
8. Run CRM-unavailable and session-recovery cases and verify limited functionality, incident logging, and safe recovery.
9. Run API handler tests for authenticated WebSocket and REST flows, unauthorized requests, rate limiting, and malformed EventBridge events.

## Commands

```powershell
pytest
pytest tests/unit
pytest tests/property
ruff check .
ruff format --check .
mypy aria
pip-audit
```

Infrastructure validation after the CDK application exists:

```powershell
pytest cdk/tests -v --tb=short
cdk synth -c env=dev --quiet
cdk diff -c env=dev
```

Production deployment is gated by CI, security checks, an approved federated deployment role, and reviewed change-set or diff output. Do not use `--require-approval never` as the production default.

Live AWS and CRM integration tests must be explicitly selected and run only in a provisioned test environment.

## Multi-turn correction checks

- Submit a normal workflow and verify state revision increments once per accepted patch.
- Change one earlier field and verify only declared dependent values become stale.
- Change two fields in one message and verify one atomic patch is applied.
- Attempt to change a locked or unauthorized field and verify the previous state remains unchanged.
- Send concurrent writes for one session and verify one succeeds while the other receives a retryable conflict.
- Restart the Runtime session and verify workflow state is reconstructed from durable storage.

## Production safety checks

- Verify Runtime session IDs are unique, reused for one conversation, and mapped to the authenticated user.
- Verify AgentCore Memory retrieval is tenant-scoped, bounded, and never overrides current workflow state.
- Verify Gateway exposes only the capability set needed for the current workflow step while backend authorization still rejects unauthorized calls.
- Verify Bedrock Guardrails handle input and output intervention without persisting raw protected content.
- Verify logs contain correlation, session, revision, tool, model, and latency metadata but no credentials or unnecessary client data.
