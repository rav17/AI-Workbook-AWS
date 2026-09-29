"""Unit tests for CdkContext dataclass and validation."""

import pytest

from src.agentic_ai.infra.context import (
    CdkContext,
    validate_cdk_context,
)


def _valid_context() -> dict:
    """Return a minimal valid CDK context dict."""
    return {
        "environment": "dev",
        "awsAccount": "123456789012",
        "awsRegion": "us-east-1",
        "bedrockModelId": "anthropic.claude-3-sonnet-20240229-v1:0",
        "costCenter": "platform-engineering",
        "costCenterEmail": "platform@example.com",
    }


class TestCdkContextDataclass:
    """Tests for the CdkContext dataclass itself."""

    def test_create_with_required_fields(self):
        ctx = CdkContext(
            environment="dev",
            aws_account="123456789012",
            aws_region="us-east-1",
            bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            cost_center="platform-engineering",
            cost_center_email="platform@example.com",
        )
        assert ctx.environment == "dev"
        assert ctx.aws_account == "123456789012"
        assert ctx.aws_region == "us-east-1"
        assert ctx.bedrock_model_id == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert ctx.cost_center == "platform-engineering"
        assert ctx.cost_center_email == "platform@example.com"

    def test_defaults(self):
        ctx = CdkContext(
            environment="dev",
            aws_account="123456789012",
            aws_region="us-east-1",
            bedrock_model_id="model-id",
            cost_center="engineering",
            cost_center_email="eng@example.com",
        )
        assert ctx.image_tag == "latest-dev"
        assert ctx.vpc_cidr == "10.0.0.0/16"
        assert ctx.monthly_budget_usd == "200"


class TestValidateCdkContext:
    """Tests for validate_cdk_context function."""

    def test_valid_context_returns_cdk_context(self):
        raw = _valid_context()
        result = validate_cdk_context(raw)
        assert isinstance(result, CdkContext)
        assert result.environment == "dev"
        assert result.aws_account == "123456789012"
        assert result.aws_region == "us-east-1"

    def test_valid_context_with_optional_fields(self):
        raw = _valid_context()
        raw["imageTag"] = "abc1234-dev"
        raw["vpcCidr"] = "10.1.0.0/16"
        raw["monthlyBudgetUsd"] = "500"
        result = validate_cdk_context(raw)
        assert result.image_tag == "abc1234-dev"
        assert result.vpc_cidr == "10.1.0.0/16"
        assert result.monthly_budget_usd == "500"

    def test_image_tag_defaults_to_latest_env(self):
        raw = _valid_context()
        raw["environment"] = "prod"
        result = validate_cdk_context(raw)
        assert result.image_tag == "latest-prod"

    def test_invalid_environment_raises_valueerror(self):
        raw = _valid_context()
        raw["environment"] = "test"
        with pytest.raises(ValueError, match="environment"):
            validate_cdk_context(raw)

    def test_missing_environment_raises_valueerror(self):
        raw = _valid_context()
        del raw["environment"]
        with pytest.raises(ValueError, match="environment"):
            validate_cdk_context(raw)

    def test_invalid_aws_account_too_short(self):
        raw = _valid_context()
        raw["awsAccount"] = "12345"
        with pytest.raises(ValueError, match="awsAccount"):
            validate_cdk_context(raw)

    def test_invalid_aws_account_non_numeric(self):
        raw = _valid_context()
        raw["awsAccount"] = "12345678901a"
        with pytest.raises(ValueError, match="awsAccount"):
            validate_cdk_context(raw)

    def test_invalid_aws_account_too_long(self):
        raw = _valid_context()
        raw["awsAccount"] = "1234567890123"
        with pytest.raises(ValueError, match="awsAccount"):
            validate_cdk_context(raw)

    def test_invalid_aws_region(self):
        raw = _valid_context()
        raw["awsRegion"] = "invalid-region"
        with pytest.raises(ValueError, match="awsRegion"):
            validate_cdk_context(raw)

    def test_empty_bedrock_model_id(self):
        raw = _valid_context()
        raw["bedrockModelId"] = ""
        with pytest.raises(ValueError, match="bedrockModelId"):
            validate_cdk_context(raw)

    def test_whitespace_bedrock_model_id(self):
        raw = _valid_context()
        raw["bedrockModelId"] = "   "
        with pytest.raises(ValueError, match="bedrockModelId"):
            validate_cdk_context(raw)

    def test_empty_cost_center(self):
        raw = _valid_context()
        raw["costCenter"] = ""
        with pytest.raises(ValueError, match="costCenter"):
            validate_cdk_context(raw)

    def test_missing_cost_center_email(self):
        raw = _valid_context()
        del raw["costCenterEmail"]
        with pytest.raises(ValueError, match="costCenterEmail"):
            validate_cdk_context(raw)

    def test_empty_cost_center_email(self):
        raw = _valid_context()
        raw["costCenterEmail"] = ""
        with pytest.raises(ValueError, match="costCenterEmail"):
            validate_cdk_context(raw)

    def test_multiple_errors_reported(self):
        """All validation errors are accumulated and reported."""
        raw = {}
        with pytest.raises(ValueError) as exc_info:
            validate_cdk_context(raw)
        error_msg = str(exc_info.value)
        assert "environment" in error_msg
        assert "awsAccount" in error_msg
        assert "awsRegion" in error_msg
        assert "bedrockModelId" in error_msg
        assert "costCenter" in error_msg
        assert "costCenterEmail" in error_msg

    @pytest.mark.parametrize("env", ["dev", "staging", "prod"])
    def test_all_valid_environments(self, env):
        raw = _valid_context()
        raw["environment"] = env
        result = validate_cdk_context(raw)
        assert result.environment == env

    @pytest.mark.parametrize(
        "region",
        ["us-east-1", "eu-west-2", "ap-southeast-1"],
    )
    def test_valid_regions(self, region):
        raw = _valid_context()
        raw["awsRegion"] = region
        result = validate_cdk_context(raw)
        assert result.aws_region == region
