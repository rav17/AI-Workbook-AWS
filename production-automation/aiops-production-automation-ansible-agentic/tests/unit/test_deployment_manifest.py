"""Unit tests for deployment manifest store and rollback trigger scripts.

Tests the store_manifest.py and rollback_trigger.py scripts that manage
deployment manifests in SSM Parameter Store with a sliding-window rotation.

Validates: Requirements 7.1, 7.2, 7.3
"""

import json
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Add scripts to path for imports
sys.path.insert(0, ".")

from scripts.store_manifest import (
    MAX_MANIFESTS,
    build_manifest,
    get_existing_manifest,
    get_parameter_name,
    rotate_manifests,
    store_manifest,
)
from scripts.rollback_trigger import get_manifest


pytestmark = pytest.mark.unit


class TestGetParameterName:
    """Tests for SSM parameter name generation."""

    def test_returns_correct_path_for_dev(self):
        assert get_parameter_name("dev", 1) == "/aiops/dev/deployment-history/1"

    def test_returns_correct_path_for_staging(self):
        assert get_parameter_name("staging", 3) == "/aiops/staging/deployment-history/3"

    def test_returns_correct_path_for_prod(self):
        assert get_parameter_name("prod", 5) == "/aiops/prod/deployment-history/5"


class TestBuildManifest:
    """Tests for manifest construction."""

    def test_contains_required_fields(self):
        manifest = build_manifest(
            image_tag="abc1234-dev",
            commit_sha="abc1234",
            cdk_stack_versions='{"NetworkStack": "cs-123", "DataStack": "cs-456"}',
            health_gate_result="passed",
        )
        assert "image_tag" in manifest
        assert "commit_sha" in manifest
        assert "cdk_stack_versions" in manifest
        assert "deployment_timestamp" in manifest
        assert "health_gate_result" in manifest

    def test_image_tag_matches_input(self):
        manifest = build_manifest(
            image_tag="def5678-prod",
            commit_sha="def5678",
            cdk_stack_versions="{}",
            health_gate_result="passed",
        )
        assert manifest["image_tag"] == "def5678-prod"

    def test_commit_sha_matches_input(self):
        manifest = build_manifest(
            image_tag="abc1234-dev",
            commit_sha="abc1234abcdef",
            cdk_stack_versions="{}",
            health_gate_result="passed",
        )
        assert manifest["commit_sha"] == "abc1234abcdef"

    def test_cdk_stack_versions_parsed_as_dict(self):
        versions_json = '{"NetworkStack": "cs-111", "ComputeStack": "cs-222"}'
        manifest = build_manifest(
            image_tag="abc1234-dev",
            commit_sha="abc1234",
            cdk_stack_versions=versions_json,
            health_gate_result="passed",
        )
        assert manifest["cdk_stack_versions"] == {
            "NetworkStack": "cs-111",
            "ComputeStack": "cs-222",
        }

    def test_empty_cdk_stack_versions_gives_empty_dict(self):
        manifest = build_manifest(
            image_tag="abc1234-dev",
            commit_sha="abc1234",
            cdk_stack_versions="",
            health_gate_result="passed",
        )
        assert manifest["cdk_stack_versions"] == {}

    def test_deployment_timestamp_is_iso_format(self):
        manifest = build_manifest(
            image_tag="abc1234-dev",
            commit_sha="abc1234",
            cdk_stack_versions="{}",
            health_gate_result="passed",
        )
        # Should parse without error
        ts = datetime.fromisoformat(manifest["deployment_timestamp"])
        assert ts.tzinfo is not None

    def test_health_gate_result_matches_input(self):
        manifest = build_manifest(
            image_tag="abc1234-dev",
            commit_sha="abc1234",
            cdk_stack_versions="{}",
            health_gate_result="failed",
        )
        assert manifest["health_gate_result"] == "failed"


class TestGetExistingManifest:
    """Tests for retrieving existing manifests from SSM."""

    def test_returns_value_when_found(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": '{"image_tag": "abc-dev"}'}
        }
        result = get_existing_manifest(mock_ssm, "dev", 1)
        assert result == '{"image_tag": "abc-dev"}'
        mock_ssm.get_parameter.assert_called_once_with(
            Name="/aiops/dev/deployment-history/1"
        )

    def test_returns_none_when_not_found(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )
        result = get_existing_manifest(mock_ssm, "dev", 3)
        assert result is None

    def test_raises_on_other_client_errors(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
            "GetParameter",
        )
        with pytest.raises(ClientError):
            get_existing_manifest(mock_ssm, "dev", 1)


class TestRotateManifests:
    """Tests for manifest rotation logic."""

    def test_rotates_single_manifest_from_1_to_2(self):
        mock_ssm = MagicMock()
        # Only slot 1 exists
        def get_param(Name):
            if Name == "/aiops/dev/deployment-history/1":
                return {"Parameter": {"Value": '{"image_tag": "v1"}'}}
            raise ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": ""}},
                "GetParameter",
            )

        mock_ssm.get_parameter.side_effect = get_param
        rotate_manifests(mock_ssm, "dev")

        # Slot 1 should be moved to slot 2
        mock_ssm.put_parameter.assert_called_once_with(
            Name="/aiops/dev/deployment-history/2",
            Value='{"image_tag": "v1"}',
            Type="String",
            Overwrite=True,
        )

    def test_rotates_multiple_manifests(self):
        mock_ssm = MagicMock()
        # Slots 1, 2, 3 exist
        manifests = {
            "/aiops/prod/deployment-history/1": '{"image_tag": "v1"}',
            "/aiops/prod/deployment-history/2": '{"image_tag": "v2"}',
            "/aiops/prod/deployment-history/3": '{"image_tag": "v3"}',
        }

        def get_param(Name):
            if Name in manifests:
                return {"Parameter": {"Value": manifests[Name]}}
            raise ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": ""}},
                "GetParameter",
            )

        mock_ssm.get_parameter.side_effect = get_param
        rotate_manifests(mock_ssm, "prod")

        # Should rotate 4→5 (not found), 3→4, 2→3, 1→2
        put_calls = mock_ssm.put_parameter.call_args_list
        # Should have 3 calls (for slots 3, 2, 1)
        assert len(put_calls) == 3

    def test_caps_at_max_manifests(self):
        """When all 5 slots are full, slot 4 overwrites slot 5 (oldest is lost)."""
        mock_ssm = MagicMock()
        # All 4 slots 1-4 exist (we only rotate 1 through MAX_MANIFESTS-1)
        manifests = {
            f"/aiops/dev/deployment-history/{i}": f'{{"image_tag": "v{i}"}}'
            for i in range(1, MAX_MANIFESTS)
        }

        def get_param(Name):
            if Name in manifests:
                return {"Parameter": {"Value": manifests[Name]}}
            raise ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": ""}},
                "GetParameter",
            )

        mock_ssm.get_parameter.side_effect = get_param
        rotate_manifests(mock_ssm, "dev")

        # Should produce 4 put_parameter calls (slots 4→5, 3→4, 2→3, 1→2)
        assert mock_ssm.put_parameter.call_count == MAX_MANIFESTS - 1


class TestStoreManifest:
    """Tests for the full store operation."""

    def test_stores_at_slot_1(self):
        mock_ssm = MagicMock()
        # No existing manifests
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": ""}},
            "GetParameter",
        )
        manifest = {"image_tag": "abc-dev", "commit_sha": "abc"}
        store_manifest(mock_ssm, "dev", manifest)

        # Should store at slot 1
        put_calls = mock_ssm.put_parameter.call_args_list
        final_call = put_calls[-1]
        assert final_call.kwargs["Name"] == "/aiops/dev/deployment-history/1"
        stored_value = json.loads(final_call.kwargs["Value"])
        assert stored_value["image_tag"] == "abc-dev"

    def test_rotates_before_storing(self):
        mock_ssm = MagicMock()
        # Slot 1 exists
        def get_param(Name):
            if Name == "/aiops/staging/deployment-history/1":
                return {"Parameter": {"Value": '{"image_tag": "old"}'}}
            raise ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": ""}},
                "GetParameter",
            )

        mock_ssm.get_parameter.side_effect = get_param
        manifest = {"image_tag": "new-staging", "commit_sha": "new"}
        store_manifest(mock_ssm, "staging", manifest)

        put_calls = mock_ssm.put_parameter.call_args_list
        # First call: rotate slot 1 to slot 2
        assert put_calls[0].kwargs["Name"] == "/aiops/staging/deployment-history/2"
        # Second call: store new at slot 1
        assert put_calls[1].kwargs["Name"] == "/aiops/staging/deployment-history/1"


class TestGetManifestRollback:
    """Tests for rollback_trigger.get_manifest function."""

    def test_returns_manifest_when_found(self):
        mock_ssm = MagicMock()
        manifest_data = {"image_tag": "abc-prod", "commit_sha": "abc"}
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": json.dumps(manifest_data)}
        }
        result = get_manifest("prod", 1, ssm_client=mock_ssm)
        assert result == manifest_data

    def test_returns_none_when_not_found(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )
        result = get_manifest("prod", 3, ssm_client=mock_ssm)
        assert result is None

    def test_raises_on_other_errors(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Error"}},
            "GetParameter",
        )
        with pytest.raises(ClientError):
            get_manifest("dev", 1, ssm_client=mock_ssm)

    def test_queries_correct_parameter_path(self):
        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": '{"image_tag": "test"}'}
        }
        get_manifest("staging", 2, ssm_client=mock_ssm)
        mock_ssm.get_parameter.assert_called_once_with(
            Name="/aiops/staging/deployment-history/2"
        )


class TestMainStoreManifest:
    """Tests for store_manifest.py main() function."""

    @patch("scripts.store_manifest.boto3")
    def test_exits_if_environment_missing(self, mock_boto3):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.store_manifest import main
                main()
            assert exc_info.value.code == 1

    @patch("scripts.store_manifest.boto3")
    def test_exits_if_image_tag_missing(self, mock_boto3):
        with patch.dict("os.environ", {"ENVIRONMENT": "dev"}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.store_manifest import main
                main()
            assert exc_info.value.code == 1

    @patch("scripts.store_manifest.boto3")
    def test_exits_if_environment_invalid(self, mock_boto3):
        with patch.dict(
            "os.environ", {"ENVIRONMENT": "invalid", "IMAGE_TAG": "abc-dev"}, clear=True
        ):
            with pytest.raises(SystemExit) as exc_info:
                from scripts.store_manifest import main
                main()
            assert exc_info.value.code == 1


class TestMainRollbackTrigger:
    """Tests for rollback_trigger.py main() via CLI simulation."""

    @patch("scripts.rollback_trigger.boto3")
    def test_exits_1_when_manifest_not_found(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )
        with patch.dict("os.environ", {"ENVIRONMENT": "dev", "MANIFEST_SLOT": "1"}):
            with patch("sys.argv", ["rollback_trigger.py"]):
                with pytest.raises(SystemExit) as exc_info:
                    from scripts.rollback_trigger import main
                    main()
                assert exc_info.value.code == 1
