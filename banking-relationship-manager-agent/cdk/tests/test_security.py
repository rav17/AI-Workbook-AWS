from __future__ import annotations

import pytest
from aws_cdk import App

from cdk.app import build_app
from cdk.stacks.stateful_stack import StatefulStack


def test_stateful_stack_synthesizes_without_unsupported_security_configuration() -> None:
    app = App(context={"environment": "dev", "region": "us-east-1", "account": "111111111111"})
    StatefulStack(
        app,
        "AriaStatefulStack",
        env_name="dev",
        env={"account": "111111111111", "region": "us-east-1"},
    )

    template = app.synth().get_stack_by_name("AriaStatefulStack").template
    assert template["Resources"]
    resource_names = tuple(template["Resources"].keys())
    assert any(name.startswith("SessionTable") for name in resource_names)
    assert any(name.startswith("WorkflowQueue") for name in resource_names)
    assert any(name.startswith("ProviderSecret") for name in resource_names)
    assert any(name.startswith("WorkflowEventBus") for name in resource_names)

    table_resource = next(
        resource
        for name, resource in template["Resources"].items()
        if name.startswith("SessionTable")
    )
    assert table_resource["Properties"]["SSESpecification"]["SSEEnabled"] is True


def test_non_dev_stateful_stack_retains_resources_and_enables_termination_protection() -> None:
    app = App(context={"environment": "prod", "region": "us-east-1", "account": "111111111111"})
    stack = StatefulStack(
        app,
        "AriaProdStatefulStack",
        env_name="prod",
        env={"account": "111111111111", "region": "us-east-1"},
    )

    template = app.synth().get_stack_by_name("AriaProdStatefulStack").template
    table_resource = next(
        resource
        for name, resource in template["Resources"].items()
        if name.startswith("SessionTable")
    )
    assert table_resource["DeletionPolicy"] == "Retain"
    assert stack.termination_protection is True


def test_non_dev_app_requires_permissions_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CDK_PERMISSIONS_BOUNDARY_ARN", raising=False)
    monkeypatch.setenv("CDK_DEFAULT_ACCOUNT", "111111111111")
    monkeypatch.setenv("CDK_DEFAULT_REGION", "us-east-1")

    with pytest.raises(ValueError, match="permissions boundary"):
        build_app(
            context={
                "environment": "prod",
                "account": "111111111111",
                "region": "us-east-1",
            }
        )
