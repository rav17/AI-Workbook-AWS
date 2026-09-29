#!/usr/bin/env python3
"""CDK App entry point for AIOps Self-Healing Infrastructure."""

import aws_cdk as cdk

from .context import validate_cdk_context
from .tags import apply_standard_tags
from .stacks.network_stack import NetworkStack
from .stacks.data_stack import DataStack
from .stacks.compute_stack import ComputeStack
from .stacks.observability_stack import ObservabilityStack
from .stacks.monitoring_stack import MonitoringStack
from .stacks.simulation_stack import SimulationStack


def main() -> None:
    """Create and synthesize the CDK app with all four stacks."""
    app = cdk.App()

    # Read and validate context (coerce None to empty string for validation)
    raw_context = {
        "environment": app.node.try_get_context("environment") or "",
        "awsAccount": app.node.try_get_context("awsAccount") or "",
        "awsRegion": app.node.try_get_context("awsRegion") or "",
        "bedrockModelId": app.node.try_get_context("bedrockModelId") or "",
        "costCenter": app.node.try_get_context("costCenter") or "",
        "costCenterEmail": app.node.try_get_context("costCenterEmail") or "",
        "imageTag": app.node.try_get_context("imageTag") or "",
        "vpcCidr": app.node.try_get_context("vpcCidr") or "",
        "monthlyBudgetUsd": app.node.try_get_context("monthlyBudgetUsd") or "",
    }
    context = validate_cdk_context(raw_context)

    env = cdk.Environment(account=context.aws_account, region=context.aws_region)
    is_prod = context.environment == "prod"

    # Stack naming convention
    prefix = f"Aiops-{context.environment}"

    # Instantiate stacks with explicit dependencies
    network_stack = NetworkStack(
        app,
        f"{prefix}-Network",
        env=env,
        context=context,
        termination_protection=is_prod,
    )

    data_stack = DataStack(
        app,
        f"{prefix}-Data",
        env=env,
        context=context,
        termination_protection=is_prod,
    )

    compute_stack = ComputeStack(
        app,
        f"{prefix}-Compute",
        env=env,
        context=context,
        network_stack=network_stack,
        data_stack=data_stack,
        termination_protection=is_prod,
    )
    compute_stack.add_dependency(network_stack)
    compute_stack.add_dependency(data_stack)

    observability_stack = ObservabilityStack(
        app,
        f"{prefix}-Observability",
        env=env,
        context=context,
        compute_stack=compute_stack,
        data_stack=data_stack,
        termination_protection=is_prod,
    )
    observability_stack.add_dependency(compute_stack)

    monitoring_stack = MonitoringStack(
        app,
        f"{prefix}-Monitoring",
        env=env,
        context=context,
        network_stack=network_stack,
        termination_protection=is_prod,
    )
    monitoring_stack.add_dependency(compute_stack)

    simulation_stack = SimulationStack(
        app,
        f"{prefix}-Simulation",
        env=env,
        context=context,
        network_stack=network_stack,
        termination_protection=False,  # Never protect simulation resources
    )
    simulation_stack.add_dependency(network_stack)

    # Apply standard tags to all resources
    apply_standard_tags(app, context)

    app.synth()


if __name__ == "__main__":
    main()
