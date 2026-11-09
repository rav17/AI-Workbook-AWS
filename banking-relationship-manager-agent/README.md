# Aria AI Relationship Manager

Aria is a Python 3.11 relationship-management agent with guarded workflow state, CRM and knowledge tools, escalation handling, shared framework contracts, and AWS CDK infrastructure.

## Development setup

Use Python 3.11 for local application and Lambda tooling:

```powershell
C:\Python311\python.exe -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv311\Scripts\python.exe -m pip install -r cdk/requirements-dev.txt
uv sync --frozen --all-extras
```

Run the application tests:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q
```

Build service-specific deployment artifacts before synthesis:

```powershell
uv lock --check --python 3.11
uv run python scripts/build_artifacts.py --target all
```

Configure `COGNITO_USER_POOL_ARN`, `COGNITO_APP_CLIENT_ID`, and `BEDROCK_MODEL_ID`, then synthesize:

```powershell
cd cdk
cdk synth --quiet
```

API Gateway verifies Cognito JWTs; the request Lambda invokes AgentCore Runtime with SigV4 under a resource policy restricted to that Lambda role. Runtime packages use Python 3.13 and require MMDSv2. The authenticated API path uses DynamoDB-backed session state; Runtime Memory retrieval is tenant-scoped. Strands connects to the IAM-authorized Gateway through SigV4 MCP, but only the no-argument risk questionnaire tool is exposed. Customer-specific Gateway actions remain disabled until an authoritative user-to-customer mapping is approved. Lambda wheels target Amazon Linux 2 compatibility; Runtime wheels target Amazon Linux 2023 compatibility. No authoritative KYC provider is configured, so protected product recommendations fail closed. Local tests and CDK synthesis do not prove an AWS deployment or successful invocation.

## Project layout

- `aria/`: application, workflow, tools, guards, persistence, and shared framework
- `aria/agents/`: manifest-driven agent entrypoints
- `cdk/`: AWS infrastructure and synthesis tests
- `tests/`: unit and framework tests
- `specs/001-ai-relationship-manager/`: original business feature artifacts
- `specs/002-production-readiness/`: audit remediation specification and validation artifacts
- `docs/`: operational and framework documentation (see also `docs/speckit-profiles.md` for Spec Kit workflow profiles and audit)
