#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path

from aws_cdk import App, Environment, Tags
from aws_cdk import aws_iam as iam

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from cdk.stacks.application_stack import ApplicationStack
    from cdk.stacks.gateway_stack import GatewayStack
    from cdk.stacks.runtime_stack import RuntimeStack
    from cdk.stacks.stateful_stack import StatefulStack
except ModuleNotFoundError:
    from stacks.application_stack import ApplicationStack
    from stacks.gateway_stack import GatewayStack
    from stacks.runtime_stack import RuntimeStack
    from stacks.stateful_stack import StatefulStack


def _context_bool(app: App, key: str, *, default: bool = False) -> bool:
    value = app.node.try_get_context(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError(f"CDK context '{key}' must be true or false")


def build_app(context: dict[str, str] | None = None) -> App:
    app = App(context=context)

    env_name = app.node.try_get_context("environment") or "dev"
    account = (
        os.environ.get("CDK_DEFAULT_ACCOUNT")
        or app.node.try_get_context("account")
        or "000000000000"
    )
    region = (
        os.environ.get("CDK_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or app.node.try_get_context("region")
        or "us-east-1"
    )
    permissions_boundary_arn = app.node.try_get_context(
        "permissions_boundary_arn"
    ) or os.environ.get("CDK_PERMISSIONS_BOUNDARY_ARN")
    user_pool_arn = app.node.try_get_context("cognito_user_pool_arn") or os.environ.get(
        "COGNITO_USER_POOL_ARN"
    )
    tenant_claim_name = (
        app.node.try_get_context("tenant_claim_name")
        or os.environ.get("TENANT_CLAIM_NAME")
        or "custom:tenant_id"
    )
    model_id = app.node.try_get_context("bedrock_model_id") or os.environ.get("BEDROCK_MODEL_ID")
    cognito_app_client_id = app.node.try_get_context("cognito_app_client_id") or os.environ.get(
        "COGNITO_APP_CLIENT_ID"
    )
    statement_explainer_enabled = _context_bool(app, "statement_explainer_enabled")
    idempotency_ttl_value = app.node.try_get_context("idempotency_ttl_seconds") or os.environ.get(
        "IDEMPOTENCY_TTL_SECONDS"
    )
    idempotency_ttl_seconds = None
    if idempotency_ttl_value:
        try:
            idempotency_ttl_seconds = int(idempotency_ttl_value)
        except ValueError as exc:
            raise ValueError("IDEMPOTENCY_TTL_SECONDS must be a positive integer") from exc
        if idempotency_ttl_seconds < 1:
            raise ValueError("IDEMPOTENCY_TTL_SECONDS must be a positive integer")

    if env_name != "dev" and not permissions_boundary_arn:
        raise ValueError("CDK permissions boundary ARN is required outside dev")
    if not user_pool_arn:
        raise ValueError("Cognito user pool ARN is required for authenticated API access")
    if not model_id:
        raise ValueError("Bedrock model ID is required for the AgentCore Runtime")
    if not cognito_app_client_id:
        raise ValueError("Cognito app client ID is required for authenticated Runtime access")
    user_pool_id = app.node.try_get_context("cognito_user_pool_id") or os.environ.get(
        "COGNITO_USER_POOL_ID"
    )
    if not user_pool_id:
        user_pool_id = user_pool_arn.rsplit("/", maxsplit=1)[-1]
    if permissions_boundary_arn:
        boundary = iam.ManagedPolicy.from_managed_policy_arn(
            app,
            "OrganizationPermissionsBoundary",
            permissions_boundary_arn,
        )
        iam.PermissionsBoundary.of(app).apply(boundary)

    env = Environment(account=account, region=region)
    Tags.of(app).add("project", "aria-ai-relationship-manager")
    Tags.of(app).add("environment", env_name)

    stateful_stack = StatefulStack(app, "AriaStatefulStack", env=env, env_name=env_name)
    application_stack = ApplicationStack(
        app,
        "AriaApplicationStack",
        env=env,
        env_name=env_name,
        stateful_stack=stateful_stack,
        user_pool_arn=user_pool_arn,
        tenant_claim_name=tenant_claim_name,
        idempotency_ttl_seconds=idempotency_ttl_seconds,
    )
    gateway_stack = GatewayStack(
        app,
        "AriaGatewayStack",
        env=env,
        env_name=env_name,
        stateful_stack=stateful_stack,
        application_stack=application_stack,
    )
    gateway_stack.add_dependency(application_stack)
    gateway_stack.add_dependency(stateful_stack)
    runtime_stack = RuntimeStack(
        app,
        "AriaRuntimeStack",
        env=env,
        env_name=env_name,
        stateful_stack=stateful_stack,
        gateway_stack=gateway_stack,
        application_stack=application_stack,
        model_id=model_id,
        cognito_user_pool_id=user_pool_id,
        cognito_app_client_id=cognito_app_client_id,
        tenant_claim_name=tenant_claim_name,
        statement_explainer_enabled=statement_explainer_enabled,
    )
    runtime_stack.add_dependency(gateway_stack)
    return app


if __name__ == "__main__":
    build_app().synth()
