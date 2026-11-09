# Quickstart: Production Statement Explainer

## Prerequisites

- Python 3.11 and the repository dev dependencies.
- DynamoDB statement-entitlement and statement-transaction tables synthesized/deployed through CDK.
- A trusted provisioning process that writes both entitlement and transaction records. This feature does not provide a write/import endpoint.
- Bedrock model and existing AgentCore Gateway configuration for the authenticated Runtime.

## Production boundaries

The statement specialist is nested inside Aria's existing Runtime. Its model-visible tools never accept tenant or user identity. Runtime code injects the verified principal into the child wrapper; every statement data operation then calls the AgentCore Gateway Lambda, which checks `StatementEntitlements` before querying `StatementTransactions`.

The Runtime role has Gateway invocation permission only. The Gateway Lambda has read-only DynamoDB permissions. No statement rows are stored in AgentCore Memory or application logs. The feature flag defaults off and must remain off until data and entitlement records are provisioned and authorized-access tests pass.

To synthesize the explicit opt-in without deploying:

```powershell
cd cdk
cdk synth --quiet -c statement_explainer_enabled=true
```

Default synthesis leaves the statement child disabled:

```powershell
cdk synth --quiet
```

## DynamoDB provisioning contract

`StatementEntitlements` items map `principal_scope` (SHA-256 of verified tenant ID, NUL, and user subject) plus opaque `statement_ref` to `access_status`, masked `display_label`, currency, date bounds, and optional opening balance. Only an approved provisioning process may write or revoke these items.

`StatementTransactions` items use `statement_ref` as the partition key and `{value_date}#{trans_id}` as the sort key. Required attributes are `trans_id`, `value_date`, `amount`, `dr_cr_ind`, `narrative`, `category`, `balance_after`, and `currency`. Records must be validated and written by the trusted upstream process. There is no fixture fallback.

## Validate

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_statement_explainer.py tests/unit/test_statement_gateway.py tests/framework/test_statement_subagent.py tests/integration/test_statement_gateway.py cdk/tests/test_security.py
```

The suite uses fake DynamoDB/Gateway clients. It verifies entitlement enforcement, cross-user denial, page bounds, Decimal calculations, nested-child isolation, and CDK permissions. Live AWS tests must run only in an explicitly configured non-production environment with approved data.
