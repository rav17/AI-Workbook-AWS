"""Shared CDK test fixtures for infrastructure assertion tests.

Provides pytest fixtures that create CDK App instances, CdkContext objects
for each environment (dev/staging/prod), and helper functions for synthesizing
stack templates for CDK assertions.
"""

import pytest
import aws_cdk as cdk
from aws_cdk.assertions import Template

from src.agentic_ai.infra.context import CdkContext
from src.agentic_ai.infra.stacks.network_stack import NetworkStack
from src.agentic_ai.infra.stacks.data_stack import DataStack
from src.agentic_ai.infra.stacks.compute_stack import ComputeStack
from src.agentic_ai.infra.stacks.observability_stack import ObservabilityStack


# --- Pytest marker: automatically mark all tests in tests/cdk/ with @pytest.mark.cdk ---


def pytest_collection_modifyitems(items):
    """Automatically add the 'cdk' marker to all tests in the tests/cdk/ directory."""
    for item in items:
        if "tests/cdk" in str(item.fspath) or "tests\\cdk" in str(item.fspath):
            item.add_marker(pytest.mark.cdk)


# --- Fixtures ---


@pytest.fixture
def cdk_app():
    """Create a fresh CDK App instance for each test."""
    return cdk.App()


@pytest.fixture(params=["dev", "staging", "prod"])
def env_name(request):
    """Parameterized fixture providing each environment name."""
    return request.param


@pytest.fixture
def dev_context() -> CdkContext:
    """CdkContext configured for the dev environment."""
    return CdkContext(
        environment="dev",
        aws_account="123456789012",
        aws_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        cost_center="platform-engineering",
        cost_center_email="platform@example.com",
        image_tag="abc1234-dev",
    )


@pytest.fixture
def staging_context() -> CdkContext:
    """CdkContext configured for the staging environment."""
    return CdkContext(
        environment="staging",
        aws_account="123456789012",
        aws_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        cost_center="platform-engineering",
        cost_center_email="platform@example.com",
        image_tag="abc1234-staging",
    )


@pytest.fixture
def prod_context() -> CdkContext:
    """CdkContext configured for the prod environment."""
    return CdkContext(
        environment="prod",
        aws_account="123456789012",
        aws_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        cost_center="platform-engineering",
        cost_center_email="platform@example.com",
        image_tag="abc1234-prod",
    )


@pytest.fixture
def cdk_context(env_name) -> CdkContext:
    """Parameterized CdkContext fixture — one per environment (dev/staging/prod)."""
    return CdkContext(
        environment=env_name,
        aws_account="123456789012",
        aws_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        cost_center="platform-engineering",
        cost_center_email="platform@example.com",
        image_tag=f"abc1234-{env_name}",
    )


# --- Stack instantiation fixtures ---


@pytest.fixture
def network_stack(cdk_app, cdk_context) -> NetworkStack:
    """Instantiate a NetworkStack for assertion testing."""
    return NetworkStack(
        cdk_app,
        f"NetworkStack-{cdk_context.environment}",
        context=cdk_context,
        env=cdk.Environment(
            account=cdk_context.aws_account,
            region=cdk_context.aws_region,
        ),
    )


@pytest.fixture
def data_stack(cdk_app, cdk_context) -> DataStack:
    """Instantiate a DataStack for assertion testing."""
    return DataStack(
        cdk_app,
        f"DataStack-{cdk_context.environment}",
        context=cdk_context,
        env=cdk.Environment(
            account=cdk_context.aws_account,
            region=cdk_context.aws_region,
        ),
    )


@pytest.fixture
def compute_stack(cdk_app, cdk_context, network_stack, data_stack) -> ComputeStack:
    """Instantiate a ComputeStack for assertion testing."""
    return ComputeStack(
        cdk_app,
        f"ComputeStack-{cdk_context.environment}",
        context=cdk_context,
        network_stack=network_stack,
        data_stack=data_stack,
        env=cdk.Environment(
            account=cdk_context.aws_account,
            region=cdk_context.aws_region,
        ),
    )


@pytest.fixture
def observability_stack(cdk_app, cdk_context, compute_stack) -> ObservabilityStack:
    """Instantiate an ObservabilityStack for assertion testing."""
    return ObservabilityStack(
        cdk_app,
        f"ObservabilityStack-{cdk_context.environment}",
        context=cdk_context,
        compute_stack=compute_stack,
        env=cdk.Environment(
            account=cdk_context.aws_account,
            region=cdk_context.aws_region,
        ),
    )


# --- Template synthesis helpers ---


@pytest.fixture
def network_template(network_stack) -> Template:
    """Synthesize and return the CloudFormation template for NetworkStack."""
    return Template.from_stack(network_stack)


@pytest.fixture
def data_template(data_stack) -> Template:
    """Synthesize and return the CloudFormation template for DataStack."""
    return Template.from_stack(data_stack)


@pytest.fixture
def compute_template(compute_stack) -> Template:
    """Synthesize and return the CloudFormation template for ComputeStack."""
    return Template.from_stack(compute_stack)


@pytest.fixture
def observability_template(observability_stack) -> Template:
    """Synthesize and return the CloudFormation template for ObservabilityStack."""
    return Template.from_stack(observability_stack)


# --- Helper functions for ad-hoc template synthesis ---


def synthesize_network_stack(
    app: cdk.App, context: CdkContext
) -> Template:
    """Synthesize a NetworkStack template from a given app and context."""
    stack = NetworkStack(
        app,
        f"NetworkStack-{context.environment}",
        context=context,
        env=cdk.Environment(account=context.aws_account, region=context.aws_region),
    )
    return Template.from_stack(stack)


def synthesize_data_stack(
    app: cdk.App, context: CdkContext
) -> Template:
    """Synthesize a DataStack template from a given app and context."""
    stack = DataStack(
        app,
        f"DataStack-{context.environment}",
        context=context,
        env=cdk.Environment(account=context.aws_account, region=context.aws_region),
    )
    return Template.from_stack(stack)


def synthesize_compute_stack(
    app: cdk.App,
    context: CdkContext,
    network_stack: NetworkStack,
    data_stack: DataStack,
) -> Template:
    """Synthesize a ComputeStack template from a given app and context."""
    stack = ComputeStack(
        app,
        f"ComputeStack-{context.environment}",
        context=context,
        network_stack=network_stack,
        data_stack=data_stack,
        env=cdk.Environment(account=context.aws_account, region=context.aws_region),
    )
    return Template.from_stack(stack)


def synthesize_observability_stack(
    app: cdk.App,
    context: CdkContext,
    compute_stack: ComputeStack,
) -> Template:
    """Synthesize an ObservabilityStack template from a given app and context."""
    stack = ObservabilityStack(
        app,
        f"ObservabilityStack-{context.environment}",
        context=context,
        compute_stack=compute_stack,
        env=cdk.Environment(account=context.aws_account, region=context.aws_region),
    )
    return Template.from_stack(stack)
