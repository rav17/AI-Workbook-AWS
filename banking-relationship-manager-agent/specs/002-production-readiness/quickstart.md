# Quickstart: Production Readiness Validation

## Prerequisites

- Python 3.11 with project dependencies installed from the supported lock/requirements inputs.
- The artifact builder uses uv-managed Python 3.13 for Runtime wheel selection; it installs that interpreter if it is not already available.
- Node.js/CDK CLI version pinned by the repository.
- Docker only if the selected CDK asset bundler requires it.
- No AWS credentials are required for local tests or synthesis.
- A non-production AWS account, configured identity provider, KYC provider contract, and protected GitHub Environment are required for deployment/invocation checks; without them those outcomes remain `not_run`.

## Local focused checks

From the repository root:

```powershell
python -m pytest tests/unit/test_api_and_events.py tests/framework/test_agentcore_entrypoint.py tests/framework/test_agentcore_adapters.py tests/framework/test_strands_runtime.py
python -m pytest cdk/tests/test_security.py
python -m ruff check aria cdk tests
python -m mypy aria
```

Expected: invalid/unauthenticated events are rejected before Runtime/session setup; payload identity cannot replace verified claims; the deployed Lambda handler reaches the mocked AgentCore Runtime through the durable coordinator; request Lambda/API Gateway timeouts synthesize as 28/29 seconds; repeated `Idempotency-Key` values are rejected and failed Runtime calls can be retried; entrypoint validates prompt and routes through safety/runner dependencies; Strands registers only the explicitly allowlisted client-independent Gateway tool; Gateway malformed/unsafe arguments and results are rejected or sanitized; Memory writes fail without calling the provider, and user erasure paginates through only the authenticated actor namespace; CDK assertions verify Cognito API auth, Runtime caller policy, package exclusions/platforms, explicit protected log retention, audit/masking identifiers, API/Lambda/findings alarms, SNS alarm actions, safe Gateway schema, and environment settings.

## Artifact and full CI checks

```powershell
uv run python -m pytest --cov=aria --cov-report=term-missing --cov-fail-under=70
uv run python scripts/build_artifacts.py --target all
uv run pip-audit -r requirements.txt -r requirements-dev.txt -r cdk/requirements.txt -r cdk/requirements-dev.txt
cd cdk
cdk synth --context environment=dev
```

CI inspects built asset file lists, target-platform metadata, and uncompressed sizes; Lambda must be below 250 MB uncompressed and contain no `.venv*`, local session, test, cache, or secret artifacts. Lambda wheels must target `x86_64-manylinux2014`; Runtime wheels must target `x86_64-manylinux_2_28`.

For production workflow validation, configure `CDK_PERMISSIONS_BOUNDARY_ARN` in the selected GitHub environment and verify the variable is available before synth, diff, and deploy. Confirm the AWS OIDC trust policy restricts the repository/environment subject, and the GitHub production environment has required reviewers and branch restrictions; these settings cannot be proven by local tests.

## Sandbox verification

1. Configure issuer/user-pool ARN, audience, tenant claim, authoritative KYC provider, AWS account/region, scoped deployment role, and protected environment approval.
2. Review `cdk diff`/change set and deploy only to the designated sandbox.
3. Invoke API with missing, invalid, and valid identities; verify tenant isolation and KYC fail-closed behavior.
4. Invoke Runtime with invalid prompt shape and valid prompt; verify MMDSv2-required runtime starts and input/output checks execute.
5. Verify Memory writes are denied until owner approval. In a non-production account, exercise tenant/user namespace listing and deletion across all pages; do not treat the 30-day event expiry as extracted-record retention. Invoke the safe Gateway risk-questionnaire tool and verify customer-specific tools are unavailable; test state recovery after Runtime/session restart.
6. Record deployment and invocation outcomes separately. Do not mark either successful without captured service evidence.

## Execution Record

- Initial remediation baseline (2026-10-01): application tests `passed` (128 tests); CDK tests `passed` (8 tests); synth passed with CDK deprecation and AgentCore Memory schema warnings.
- Follow-up local validation (2026-10-02): application tests `passed` (168 tests); CDK tests `passed` (8 tests); strict mypy, Ruff format/lint, `uv lock --check --python 3.11`, pip-audit, and secret scan passed. Pip-audit reported no known vulnerabilities; the secret scan passed with 27 plugins.
- Follow-up artifact build: `passed`; Lambda `62,597,510` bytes and Runtime `62,760,243` bytes uncompressed. Lambda used `x86_64-manylinux2014` with a CPython 3.11 extension; Runtime used `x86_64-manylinux_2_28` with a CPython 3.13 extension.
- Follow-up CDK synthesis: dev synth `passed` using the pinned `.venv311` environment. Existing CDK deprecation, AgentCore Memory schema/namespace, and cross-stack-reference warnings remain.
- Linux container import smoke test: `not_run`; Docker is not installed in this environment. Artifact platform selection and extension interpreter tags were inspected locally.
- AWS sandbox deployment, API/Runtime invocation, and rollback: `not_run`; no sandbox credentials, configured KYC provider, or deployment evidence is available in this workspace.
- GitHub OIDC role trust and environment reviewers: `not_verified`; these controls are configured outside the repository.
- Customer-specific Gateway operations: intentionally disabled until an authoritative user-to-customer mapping contract is approved.
- T020/T025 local implementation: Memory writes remain fail-closed; user-scoped erasure lists and deletes records page by page; application/Gateway/workflow log groups have seven-day retention and audit/masking; API, Lambda, and sensitive-finding alarms publish to an encrypted SNS topic. Proposed 99.9% monthly availability and p95 latency below 1,000 ms plus alert thresholds are provisional and not owner-approved.
- Operations follow-up: subscribe the encrypted SNS topic to an approved on-call endpoint and review thresholds against representative traffic before production. Data-owner approval for Memory categories, notice/consent, source-event/extracted-record retention, and erasure SLA remains required before enabling writes.
- T020/T025 local validation (2026-10-02): application tests `passed` (171 tests); CDK tests `passed` (10 tests); Memory adapter tests `passed` (20 tests); mypy `passed`; scoped Ruff lint/format `passed`; `uv lock --check --python 3.11` `passed`; dev CDK synth `passed` with existing deprecation, AgentCore Memory schema/namespace, and cross-stack-reference warnings.
- Alarm-delivery policy verification: synthesized SNS topic policy permits `cloudwatch.amazonaws.com` to publish only from this account's CloudWatch alarm ARNs; the customer-managed KMS key grants that service only `kms:Decrypt` and `kms:GenerateDataKey*` for the same alarm scope. Actual AWS notification delivery remains `not_run`.
- Deployment-readiness scan (2026-10-03): full application suite `passed` (175 tests, 81.14% coverage); CDK suite `passed` (11 tests); both deployable artifacts built (`62,601,002` Lambda and `62,763,734` Runtime uncompressed bytes); global Ruff lint/format, mypy, `uv lock --check --python 3.11`, secret scan, and pip-audit `passed`; pip-audit found no known vulnerabilities. Dev CDK synthesis passed with explicit 28-second request Lambda and 29-second API integration timeouts.
- Ruff excludes only `docs/architecture/generate_diagrams.py`, whose generated XML/diagram labels intentionally exceed Python line-length rules; all 203 other Python files pass formatting and repository-wide lint.
- CloudFormation schema validation limitation: `cfn-lint` is not installed and the AWS IaC MCP validation tool is unavailable in this session. CDK synthesis emits AgentCore Memory `NamespaceKeys`/namespace-template schema warnings; current AWS CloudFormation documentation lists `NamespaceKeys` and custom namespace variables, so these appear to be stale local CDK schema warnings, but the resource still requires a non-production deployment check.
- AWS deployment, CloudFormation change-set execution, API/Runtime invocation, alarm delivery, rollback, service quota/model access, Cognito/OIDC trust, production permissions boundary, and SNS on-call subscription remain `not_run` or `not_verified`; local tests and synthesis cannot prove account-level configuration.
