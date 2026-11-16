"""CDK assertions for the AWS DevOps Agent task environment (Compute stack)."""

from __future__ import annotations

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

from src.agentic_ai.infra.context import CdkContext
from src.agentic_ai.infra.stacks.compute_stack import ComputeStack
from src.agentic_ai.infra.stacks.data_stack import DataStack
from src.agentic_ai.infra.stacks.network_stack import NetworkStack


def _task_environment(**overrides) -> dict[str, str]:
    """Synthesize ComputeStack and return the app container's environment as a dict."""
    values = dict(
        environment="dev",
        aws_account="123456789012",
        aws_region="us-east-1",
        bedrock_model_id="amazon.nova-pro-v1:0",
        cost_center="platform-engineering",
        cost_center_email="platform@example.com",
        image_tag="abc1234-dev",
    )
    values.update(overrides)
    context = CdkContext(**values)
    env = cdk.Environment(account=context.aws_account, region=context.aws_region)
    app = cdk.App()
    network = NetworkStack(app, "Network", context=context, env=env)
    data = DataStack(app, "Data", context=context, env=env)
    compute = ComputeStack(
        app, "Compute", context=context, network_stack=network, data_stack=data, env=env
    )
    template = Template.from_stack(compute)
    definitions = template.find_resources("AWS::ECS::TaskDefinition")
    assert definitions, "no task definition synthesized"
    containers = next(iter(definitions.values()))["Properties"]["ContainerDefinitions"]
    app_container = next(c for c in containers if c.get("Environment"))
    return {e["Name"]: e["Value"] for e in app_container["Environment"] if "Value" in e}


@pytest.mark.cdk
class TestDevOpsAgentTaskEnvironment:
    def test_defaults_keep_forwarding_off_and_triggers_unchanged(self) -> None:
        env = _task_environment()
        assert env["DEVOPS_AGENT_ENABLED"] == "false"
        assert env["DEVOPS_AGENT_FORWARD_ON"] == "unmatched,failed,critical"
        assert env["DEVOPS_AGENT_MAX_PER_HOUR"] == "20"

    def test_enabled_flag_and_custom_triggers_reach_the_task(self) -> None:
        env = _task_environment(
            devops_agent_enabled=True,
            devops_agent_forward_on="unmatched,failed,critical,resolved",
        )
        assert env["DEVOPS_AGENT_ENABLED"] == "true"
        assert env["DEVOPS_AGENT_FORWARD_ON"] == "unmatched,failed,critical,resolved"
