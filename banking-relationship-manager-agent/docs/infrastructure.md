# Infrastructure

This project includes a minimal CDK foundation for the Aria workflow layer.

## Local synthesis

The CDK application is pinned to `aws-cdk-lib==2.270.0` and `constructs==10.8.1`.
From the repository root, install `cdk/requirements-dev.txt`, then run:

```powershell
cd cdk
cdk synth --quiet
```

Synthesis uses the checked-in `cdk/cdk.json` context and does not call AWS APIs or
mutate an account.

Non-development synthesis requires an organization permissions boundary:

```powershell
$env:CDK_PERMISSIONS_BOUNDARY_ARN = "arn:aws:iam::<account>:policy/<boundary>"
cdk synth --context environment=prod
```

Development synthesis does not require this ARN. Production deployments must provide
the approved boundary through CI or the deployment environment rather than committing
it to source control.

## Current stack

- The stateful stack provisions a DynamoDB session table, KMS key, encrypted provider
	secret, SQS workflow queue with a dead-letter queue, an environment-scoped EventBridge
	bus, and a retained workflow log group.
- Encryption, point-in-time recovery, retention, and removal policies are configured at
	the resource level with explicit lifecycle settings.
- No synthesis-time network or account mutation is performed during normal CI synthesis.

## Important notes

- The stack is intentionally minimal and should be extended only when lifecycle or deployment boundaries justify a larger structure.
- Generated physical names are preferred. The workflow event bus has an explicit
	environment-scoped name because it is an operational integration boundary.
- Production-grade security and cross-stack handoff logic should be added after the MVP framework and application contracts are stable.
