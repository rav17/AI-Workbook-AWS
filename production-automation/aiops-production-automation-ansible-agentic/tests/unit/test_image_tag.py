"""Unit tests for image tag builder and canary decision functions."""

import pytest

from src.agentic_ai.infra.constructs.image_tag import build_image_tag, canary_decision


class TestBuildImageTag:
    """Tests for the build_image_tag function."""

    def test_valid_sha_and_env_dev(self):
        result = build_image_tag("abc1234def5678", "dev")
        assert result == "abc1234-dev"

    def test_valid_sha_and_env_staging(self):
        result = build_image_tag("1234567890abcdef", "staging")
        assert result == "1234567-staging"

    def test_valid_sha_and_env_prod(self):
        result = build_image_tag("deadbeefcafe123", "prod")
        assert result == "deadbee-prod"

    def test_exactly_7_char_sha(self):
        result = build_image_tag("abc1234", "dev")
        assert result == "abc1234-dev"

    def test_long_sha_truncated_to_7(self):
        sha = "a" * 40
        result = build_image_tag(sha, "prod")
        assert result == "aaaaaaa-prod"

    def test_invalid_env_raises_value_error(self):
        with pytest.raises(ValueError, match="env must be one of"):
            build_image_tag("abc1234", "production")

    def test_empty_env_raises_value_error(self):
        with pytest.raises(ValueError, match="env must be one of"):
            build_image_tag("abc1234", "")

    def test_sha_too_short_raises_value_error(self):
        with pytest.raises(ValueError, match="at least 7 characters"):
            build_image_tag("abc12", "dev")

    def test_empty_sha_raises_value_error(self):
        with pytest.raises(ValueError, match="at least 7 characters"):
            build_image_tag("", "dev")

    def test_sha_with_uppercase_raises_value_error(self):
        with pytest.raises(ValueError, match="lowercase hex"):
            build_image_tag("ABC1234", "dev")

    def test_sha_with_non_hex_chars_raises_value_error(self):
        with pytest.raises(ValueError, match="lowercase hex"):
            build_image_tag("xyz1234", "dev")

    def test_sha_with_spaces_raises_value_error(self):
        with pytest.raises(ValueError, match="lowercase hex"):
            build_image_tag("abc 123 4", "dev")


class TestCanaryDecision:
    """Tests for the canary_decision function."""

    def test_proceed_when_both_below_thresholds(self):
        assert canary_decision(error_rate=2.0, latency_p95=10000) == "PROCEED"

    def test_proceed_at_zero_values(self):
        assert canary_decision(error_rate=0.0, latency_p95=0.0) == "PROCEED"

    def test_rollback_when_error_rate_at_threshold(self):
        assert canary_decision(error_rate=5.0, latency_p95=10000) == "ROLLBACK"

    def test_rollback_when_error_rate_above_threshold(self):
        assert canary_decision(error_rate=10.0, latency_p95=5000) == "ROLLBACK"

    def test_rollback_when_latency_at_threshold(self):
        assert canary_decision(error_rate=2.0, latency_p95=15000) == "ROLLBACK"

    def test_rollback_when_latency_above_threshold(self):
        assert canary_decision(error_rate=1.0, latency_p95=20000) == "ROLLBACK"

    def test_rollback_when_both_above_thresholds(self):
        assert canary_decision(error_rate=10.0, latency_p95=20000) == "ROLLBACK"

    def test_proceed_just_below_thresholds(self):
        assert canary_decision(error_rate=4.99, latency_p95=14999) == "PROCEED"
