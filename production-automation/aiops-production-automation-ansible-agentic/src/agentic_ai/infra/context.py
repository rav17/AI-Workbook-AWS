"""CDK context validation and dataclass for AIOps deployment configuration."""

from dataclasses import dataclass
import re

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}
REGION_PATTERN = re.compile(r"^[a-z]{2}-[a-z]+-[0-9]$")


@dataclass
class CdkContext:
    """Validated CDK deployment context values."""

    environment: str
    aws_account: str
    aws_region: str
    bedrock_model_id: str
    cost_center: str
    cost_center_email: str
    image_tag: str = "latest-dev"
    vpc_cidr: str = "10.0.0.0/16"
    monthly_budget_usd: str = "200"


def validate_cdk_context(raw: dict) -> CdkContext:
    """Validate CDK context values; raise ValueError naming the first invalid key."""
    errors: list[str] = []

    env = raw.get("environment", "")
    if env not in VALID_ENVIRONMENTS:
        errors.append(f"environment must be one of {VALID_ENVIRONMENTS}, got '{env}'")

    account = raw.get("awsAccount", "")
    if not re.fullmatch(r"\d{12}", account):
        errors.append(f"awsAccount must be a 12-digit numeric string, got '{account}'")

    region = raw.get("awsRegion", "")
    if not REGION_PATTERN.match(region):
        errors.append(
            f"awsRegion must match pattern [a-z]{{2}}-[a-z]+-[0-9], got '{region}'"
        )

    if not raw.get("bedrockModelId", "").strip():
        errors.append("bedrockModelId must be a non-empty string")

    if not raw.get("costCenter", "").strip():
        errors.append("costCenter must be a non-empty string")

    if not raw.get("costCenterEmail", "").strip():
        errors.append("costCenterEmail is required for budget alerts")

    if errors:
        raise ValueError(f"CDK context validation failed: {'; '.join(errors)}")

    return CdkContext(
        environment=env,
        aws_account=account,
        aws_region=region,
        bedrock_model_id=raw["bedrockModelId"],
        cost_center=raw.get("costCenter", "platform-engineering"),
        cost_center_email=raw["costCenterEmail"],
        image_tag=raw.get("imageTag", f"latest-{env}"),
        vpc_cidr=raw.get("vpcCidr", "10.0.0.0/16"),
        monthly_budget_usd=raw.get("monthlyBudgetUsd", "200"),
    )
