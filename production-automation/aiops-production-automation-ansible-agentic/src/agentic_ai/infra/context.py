"""CDK context validation and dataclass for AIOps deployment configuration."""

from dataclasses import dataclass
import re

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}
REGION_PATTERN = re.compile(r"^[a-z]{2}-[a-z]+-[0-9]$")
# Mirrors VALID_TRIGGERS / DEFAULT_TRIGGERS in src/devops_agent.py (kept literal so
# CDK synthesis does not import application code).
VALID_DEVOPS_AGENT_TRIGGERS = frozenset({"unmatched", "failed", "critical", "resolved"})
DEFAULT_DEVOPS_AGENT_FORWARD_ON = "unmatched,failed,critical"


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
    # AWS DevOps Agent Phase 1: forward selected incidents for investigation
    devops_agent_enabled: bool = False
    # Comma-separated triggers forwarded to DevOps Agent (see src/devops_agent.py)
    devops_agent_forward_on: str = DEFAULT_DEVOPS_AGENT_FORWARD_ON

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

    devops_agent_raw = str(raw.get("devopsAgentEnabled", "false")).strip().lower()
    if devops_agent_raw not in ("true", "false", ""):
        errors.append(f"devopsAgentEnabled must be 'true' or 'false', got '{devops_agent_raw}'")

    forward_on_raw = str(raw.get("devopsAgentForwardOn", "") or "").strip().lower()
    forward_on = DEFAULT_DEVOPS_AGENT_FORWARD_ON
    if forward_on_raw:
        triggers = [t.strip() for t in forward_on_raw.split(",") if t.strip()]
        unknown = sorted(set(triggers) - VALID_DEVOPS_AGENT_TRIGGERS)
        if unknown or not triggers:
            errors.append(
                f"devopsAgentForwardOn must list triggers from "
                f"{sorted(VALID_DEVOPS_AGENT_TRIGGERS)}, got '{forward_on_raw}'"
            )
        else:
            forward_on = ",".join(dict.fromkeys(triggers))

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
        devops_agent_enabled=devops_agent_raw == "true",
        devops_agent_forward_on=forward_on,
    )
