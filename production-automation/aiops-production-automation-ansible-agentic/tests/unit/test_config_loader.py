"""Unit tests for the ConfigLoader class.

Tests cover startup validation, periodic refresh, secrets caching,
and thread-safe behavior.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.agentic_ai.infra.constructs.config_loader import ConfigLoader


def _make_ssm_response(params: dict) -> dict:
    """Helper to build an SSM get_parameters_by_path response."""
    return {
        "Parameters": [
            {"Name": f"/aiops/dev/{k}", "Value": v}
            for k, v in params.items()
        ]
    }


def _valid_params() -> dict:
    """Return a valid set of required SSM parameters."""
    return {
        "operating-mode": "rules_only",
        "escalation-threshold": "0.5",
        "correlation-window-seconds": "300",
        "max-concurrent-pipelines": "50",
        "bedrock-model-id": "anthropic.claude-3-sonnet-20240229-v1:0",
        "sqs-queue-url": "https://sqs.us-east-1.amazonaws.com/123456789012/aiops-main-dev",
        "dynamodb-table-name": "AiopsIncidentMemory-dev",
    }


class TestConfigLoaderInit:
    """Tests for ConfigLoader initialization and parameter clamping."""

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_default_values(self, mock_boto):
        loader = ConfigLoader(environment="dev")
        assert loader.environment == "dev"
        assert loader.refresh_interval == 300
        assert loader.secret_ttl == 3600

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_refresh_interval_clamped_to_min(self, mock_boto):
        loader = ConfigLoader(environment="dev", refresh_interval=10)
        assert loader.refresh_interval == 60

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_refresh_interval_clamped_to_max(self, mock_boto):
        loader = ConfigLoader(environment="dev", refresh_interval=9999)
        assert loader.refresh_interval == 3600

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_secret_ttl_clamped_to_min(self, mock_boto):
        loader = ConfigLoader(environment="dev", secret_ttl=5)
        assert loader.secret_ttl == 60

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_secret_ttl_clamped_to_max(self, mock_boto):
        loader = ConfigLoader(environment="dev", secret_ttl=100000)
        assert loader.secret_ttl == 86400


class TestConfigLoaderStartup:
    """Tests for startup batch SSM fetch and validation."""

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_start_with_valid_params(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        paginator = MagicMock()
        paginator.paginate.return_value = [_make_ssm_response(_valid_params())]
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm
        loader.start()

        # Should be able to get params without error
        assert loader.get("operating-mode") == "rules_only"
        assert loader.get("escalation-threshold") == "0.5"
        assert loader.get("bedrock-model-id") == "anthropic.claude-3-sonnet-20240229-v1:0"

        loader.stop()

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_start_exits_on_missing_param(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        # Missing operating-mode
        params = _valid_params()
        del params["operating-mode"]

        paginator = MagicMock()
        paginator.paginate.return_value = [_make_ssm_response(params)]
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        with pytest.raises(SystemExit) as exc_info:
            loader.start()
        assert exc_info.value.code == 1

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_start_exits_on_invalid_operating_mode(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        params = _valid_params()
        params["operating-mode"] = "invalid_mode"

        paginator = MagicMock()
        paginator.paginate.return_value = [_make_ssm_response(params)]
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        with pytest.raises(SystemExit) as exc_info:
            loader.start()
        assert exc_info.value.code == 1

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_start_exits_on_invalid_escalation_threshold(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        params = _valid_params()
        params["escalation-threshold"] = "1.5"  # Out of range 0.0-1.0

        paginator = MagicMock()
        paginator.paginate.return_value = [_make_ssm_response(params)]
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        with pytest.raises(SystemExit) as exc_info:
            loader.start()
        assert exc_info.value.code == 1

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_start_exits_on_ssm_fetch_exception(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        paginator = MagicMock()
        paginator.paginate.side_effect = Exception("Connection timeout")
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        with pytest.raises(SystemExit) as exc_info:
            loader.start()
        assert exc_info.value.code == 1

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_start_exits_on_empty_bedrock_model_id(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        params = _valid_params()
        params["bedrock-model-id"] = "   "  # Whitespace only

        paginator = MagicMock()
        paginator.paginate.return_value = [_make_ssm_response(params)]
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        with pytest.raises(SystemExit) as exc_info:
            loader.start()
        assert exc_info.value.code == 1


class TestConfigLoaderRefresh:
    """Tests for periodic SSM refresh behavior."""

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_refresh_updates_params(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        initial_params = _valid_params()
        updated_params = _valid_params()
        updated_params["operating-mode"] = "ai_only"

        paginator = MagicMock()
        # First call: initial load, second call: refresh
        paginator.paginate.side_effect = [
            [_make_ssm_response(initial_params)],
            [_make_ssm_response(updated_params)],
        ]
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev", refresh_interval=60)
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        # Manually load startup
        loader._load_and_validate_startup()
        assert loader.get("operating-mode") == "rules_only"

        # Simulate one refresh cycle directly
        path = f"/aiops/{loader.environment}/"
        new_params = loader._fetch_ssm_parameters(path)
        with loader._lock:
            loader._params = new_params
        assert loader.get("operating-mode") == "ai_only"

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_refresh_retains_cached_on_failure(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        paginator = MagicMock()
        paginator.paginate.side_effect = [
            [_make_ssm_response(_valid_params())],  # Startup succeeds
            Exception("Network error"),  # Refresh fails
        ]
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev", refresh_interval=60)
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        loader._load_and_validate_startup()
        original_mode = loader.get("operating-mode")

        # Simulate refresh failure
        try:
            loader._fetch_ssm_parameters(f"/aiops/{loader.environment}/")
        except Exception:
            pass  # Expected to fail

        # Original values should be retained
        assert loader.get("operating-mode") == original_mode


class TestConfigLoaderSecrets:
    """Tests for Secrets Manager caching behavior."""

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_get_secret_fetches_and_caches(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        mock_sm.get_secret_value.return_value = {
            "SecretString": "https://hooks.slack.com/services/T00/B00/xxx"
        }

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        value = loader.get_secret("slack-webhook-url")
        assert value == "https://hooks.slack.com/services/T00/B00/xxx"

        # Second call should use cache (no additional API call)
        value2 = loader.get_secret("slack-webhook-url")
        assert value2 == value
        assert mock_sm.get_secret_value.call_count == 1

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_get_secret_empty_value_disables_channel(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        mock_sm.get_secret_value.return_value = {"SecretString": ""}

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        value = loader.get_secret("slack-webhook-url")
        assert value == ""

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_get_secret_not_found_returns_empty(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        # Simulate ResourceNotFoundException
        mock_sm.exceptions.ResourceNotFoundException = type(
            "ResourceNotFoundException", (Exception,), {}
        )
        mock_sm.get_secret_value.side_effect = (
            mock_sm.exceptions.ResourceNotFoundException("Not found")
        )

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        value = loader.get_secret("pagerduty-routing-key")
        assert value == ""

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_get_secret_retains_cached_on_failure(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        # First call succeeds
        mock_sm.get_secret_value.return_value = {
            "SecretString": "valid-secret-value"
        }

        loader = ConfigLoader(environment="dev", secret_ttl=60)
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        # Load the secret initially
        value = loader.get_secret("slack-webhook-url")
        assert value == "valid-secret-value"

        # Expire the cache manually
        with loader._lock:
            loader._secrets["slack-webhook-url"] = ("valid-secret-value", 0.0)

        # Make next fetch fail
        mock_sm.exceptions.ResourceNotFoundException = type(
            "ResourceNotFoundException", (Exception,), {}
        )
        mock_sm.get_secret_value.side_effect = Exception("Service unavailable")

        # Should retain cached value
        value2 = loader.get_secret("slack-webhook-url")
        assert value2 == "valid-secret-value"


class TestConfigLoaderThreadSafety:
    """Tests for thread-safe access patterns."""

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_get_raises_key_error_for_unknown_param(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        with pytest.raises(KeyError):
            loader.get("nonexistent-param")

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_stop_is_idempotent(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        loader = ConfigLoader(environment="dev")
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        # Stop without start should not raise
        loader.stop()
        loader.stop()

    @patch("src.agentic_ai.infra.constructs.config_loader.boto3.client")
    def test_start_stop_lifecycle(self, mock_boto):
        mock_ssm = MagicMock()
        mock_sm = MagicMock()
        mock_boto.side_effect = lambda service: mock_ssm if service == "ssm" else mock_sm

        paginator = MagicMock()
        paginator.paginate.return_value = [_make_ssm_response(_valid_params())]
        mock_ssm.get_paginator.return_value = paginator

        loader = ConfigLoader(environment="dev", refresh_interval=60)
        loader._ssm_client = mock_ssm
        loader._sm_client = mock_sm

        loader.start()
        assert loader._refresh_thread is not None
        assert loader._refresh_thread.is_alive()

        loader.stop()
        # Give thread time to terminate
        time.sleep(0.1)
        assert not loader._refresh_thread.is_alive()
