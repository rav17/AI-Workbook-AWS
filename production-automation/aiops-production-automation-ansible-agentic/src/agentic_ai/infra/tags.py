"""Standard tagging utility for all CDK resources.

Applies required resource tags to ensure cost tracking, environment identification,
and resource ownership across all deployed infrastructure.
"""

from aws_cdk import Tags
from constructs import Construct

from .context import CdkContext


def apply_standard_tags(scope: Construct, context: CdkContext) -> None:
    """Apply required resource tags to all resources in scope.

    Tags applied:
        - project: aiops-self-healing
        - environment: The deployment environment (dev/staging/prod)
        - managed-by: cdk
        - cost-center: The cost center from CDK context

    Args:
        scope: The CDK construct scope to apply tags to.
        context: Validated CdkContext with deployment configuration.

    Raises:
        ValueError: If cost_center is empty or whitespace-only.
    """
    if not context.cost_center or not context.cost_center.strip():
        raise ValueError(
            "cost-center tag cannot be empty. "
            "Ensure 'costCenter' is set in CDK context."
        )

    Tags.of(scope).add("project", "aiops-self-healing")
    Tags.of(scope).add("environment", context.environment)
    Tags.of(scope).add("managed-by", "cdk")
    Tags.of(scope).add("cost-center", context.cost_center)
