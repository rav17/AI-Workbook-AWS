#!/usr/bin/env python
from __future__ import annotations

import os

from aws_cdk import App, Environment, Tags
from aws_cdk import aws_iam as iam

try:
    from cdk.stacks.stateful_stack import StatefulStack
except ModuleNotFoundError:
    from .stacks.stateful_stack import StatefulStack


def build_app(context: dict[str, str] | None = None) -> App:
    app = App(context=context)

    env_name = app.node.try_get_context("environment") or "dev"
    account = (
        app.node.try_get_context("account")
        or os.environ.get("CDK_DEFAULT_ACCOUNT")
        or "000000000000"
    )
    region = (
        app.node.try_get_context("region")
        or os.environ.get("CDK_DEFAULT_REGION")
        or "us-east-1"
    )
    permissions_boundary_arn = (
        app.node.try_get_context("permissions_boundary_arn")
        or os.environ.get("CDK_PERMISSIONS_BOUNDARY_ARN")
    )

    if env_name != "dev" and not permissions_boundary_arn:
        raise ValueError("CDK permissions boundary ARN is required outside dev")
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

    StatefulStack(app, "AriaStatefulStack", env=env, env_name=env_name)
    return app


if __name__ == "__main__":
    build_app().synth()
