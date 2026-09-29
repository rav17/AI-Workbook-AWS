"""Unit tests for the /health endpoint with AWS dependency checks.

Tests verify:
- SQS health check returns "healthy" when GetQueueAttributes succeeds
- SQS health check returns "unhealthy" when GetQueueAttributes fails
- DynamoDB health check returns "unhealthy" when DescribeTable fails
- DynamoDB health check returns "healthy" when DescribeTable succeeds
- Overall endpoint returns HTTP 200 when both SQS and DynamoDB are healthy
- Overall endpoint returns HTTP 503 when any AWS dependency is unhealthy
- Missing environment variables result in "unhealthy" status

**Validates: Requirements 6.1**
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError, BotoCoreError

from src.app import _check_sqs_health, _check_dynamodb_health


pytestmark = pytest.mark.unit


class TestCheckSqsHealth:
    """Tests for _check_sqs_health function."""

    def test_returns_healthy_when_queue_reachable(self) -> None:
        """SQS returns healthy when GetQueueAttributes succeeds."""
        mock_client = MagicMock()
        mock_client.get_queue_attributes.return_value = {
            "Attributes": {"QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue"}
        }
        with patch("src.app.SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"):
            with patch("src.app.boto3.client", return_value=mock_client):
                result = _check_sqs_health()
        assert result == "healthy"

    def test_returns_unhealthy_when_client_error(self) -> None:
        """SQS returns unhealthy when ClientError occurs."""
        mock_client = MagicMock()
        mock_client.get_queue_attributes.side_effect = ClientError(
            {"Error": {"Code": "AWS.SimpleQueueService.NonExistentQueue", "Message": "Queue not found"}},
            "GetQueueAttributes",
        )
        with patch("src.app.SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"):
            with patch("src.app.boto3.client", return_value=mock_client):
                result = _check_sqs_health()
        assert result == "unhealthy"

    def test_returns_unhealthy_when_botocore_error(self) -> None:
        """SQS returns unhealthy when BotoCoreError occurs (e.g., network issue)."""
        mock_client = MagicMock()
        mock_client.get_queue_attributes.side_effect = BotoCoreError()
        with patch("src.app.SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"):
            with patch("src.app.boto3.client", return_value=mock_client):
                result = _check_sqs_health()
        assert result == "unhealthy"

    def test_returns_unhealthy_when_queue_url_empty(self) -> None:
        """SQS returns unhealthy when SQS_QUEUE_URL env var is not set."""
        with patch("src.app.SQS_QUEUE_URL", ""):
            result = _check_sqs_health()
        assert result == "unhealthy"

    def test_returns_unhealthy_on_unexpected_exception(self) -> None:
        """SQS returns unhealthy on any unexpected exception."""
        mock_client = MagicMock()
        mock_client.get_queue_attributes.side_effect = RuntimeError("unexpected")
        with patch("src.app.SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"):
            with patch("src.app.boto3.client", return_value=mock_client):
                result = _check_sqs_health()
        assert result == "unhealthy"


class TestCheckDynamodbHealth:
    """Tests for _check_dynamodb_health function."""

    def test_returns_healthy_when_table_reachable(self) -> None:
        """DynamoDB returns healthy when DescribeTable succeeds."""
        mock_client = MagicMock()
        mock_client.describe_table.return_value = {
            "Table": {"TableName": "test-table", "TableStatus": "ACTIVE"}
        }
        with patch("src.app.DYNAMODB_TABLE_NAME", "test-table"):
            with patch("src.app.boto3.client", return_value=mock_client):
                result = _check_dynamodb_health()
        assert result == "healthy"

    def test_returns_unhealthy_when_client_error(self) -> None:
        """DynamoDB returns unhealthy when ClientError occurs."""
        mock_client = MagicMock()
        mock_client.describe_table.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
            "DescribeTable",
        )
        with patch("src.app.DYNAMODB_TABLE_NAME", "test-table"):
            with patch("src.app.boto3.client", return_value=mock_client):
                result = _check_dynamodb_health()
        assert result == "unhealthy"

    def test_returns_unhealthy_when_botocore_error(self) -> None:
        """DynamoDB returns unhealthy when BotoCoreError occurs (e.g., network issue)."""
        mock_client = MagicMock()
        mock_client.describe_table.side_effect = BotoCoreError()
        with patch("src.app.DYNAMODB_TABLE_NAME", "test-table"):
            with patch("src.app.boto3.client", return_value=mock_client):
                result = _check_dynamodb_health()
        assert result == "unhealthy"

    def test_returns_unhealthy_when_table_name_empty(self) -> None:
        """DynamoDB returns unhealthy when DYNAMODB_TABLE_NAME env var is not set."""
        with patch("src.app.DYNAMODB_TABLE_NAME", ""):
            result = _check_dynamodb_health()
        assert result == "unhealthy"

    def test_returns_unhealthy_on_unexpected_exception(self) -> None:
        """DynamoDB returns unhealthy on any unexpected exception."""
        mock_client = MagicMock()
        mock_client.describe_table.side_effect = RuntimeError("unexpected")
        with patch("src.app.DYNAMODB_TABLE_NAME", "test-table"):
            with patch("src.app.boto3.client", return_value=mock_client):
                result = _check_dynamodb_health()
        assert result == "unhealthy"


class TestHealthEndpointIntegration:
    """Tests for the full /health endpoint response structure."""

    def test_returns_200_when_all_aws_deps_healthy(self) -> None:
        """HTTP 200 when both SQS and DynamoDB are healthy."""
        from httpx import AsyncClient, ASGITransport
        from src.app import app

        async def _call():
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/health")

        with patch("src.app._check_sqs_health", return_value="healthy"):
            with patch("src.app._check_dynamodb_health", return_value="healthy"):
                with patch("src.app.shutil.which", return_value="/usr/bin/ansible-playbook"):
                    with patch("src.app.os.path.isfile", return_value=True):
                        response = asyncio.run(_call())

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["dependencies"]["sqs"] == "healthy"
        assert body["dependencies"]["dynamodb"] == "healthy"

    def test_returns_503_when_sqs_unhealthy(self) -> None:
        """HTTP 503 when SQS is unhealthy (even if DynamoDB is healthy)."""
        from httpx import AsyncClient, ASGITransport
        from src.app import app

        async def _call():
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/health")

        with patch("src.app._check_sqs_health", return_value="unhealthy"):
            with patch("src.app._check_dynamodb_health", return_value="healthy"):
                with patch("src.app.shutil.which", return_value="/usr/bin/ansible-playbook"):
                    with patch("src.app.os.path.isfile", return_value=True):
                        response = asyncio.run(_call())

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["dependencies"]["sqs"] == "unhealthy"
        assert body["dependencies"]["dynamodb"] == "healthy"

    def test_returns_503_when_dynamodb_unhealthy(self) -> None:
        """HTTP 503 when DynamoDB is unhealthy (even if SQS is healthy)."""
        from httpx import AsyncClient, ASGITransport
        from src.app import app

        async def _call():
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/health")

        with patch("src.app._check_sqs_health", return_value="healthy"):
            with patch("src.app._check_dynamodb_health", return_value="unhealthy"):
                with patch("src.app.shutil.which", return_value="/usr/bin/ansible-playbook"):
                    with patch("src.app.os.path.isfile", return_value=True):
                        response = asyncio.run(_call())

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["dependencies"]["sqs"] == "healthy"
        assert body["dependencies"]["dynamodb"] == "unhealthy"

    def test_response_contains_all_dependency_keys(self) -> None:
        """Response JSON contains sqs and dynamodb keys in dependencies."""
        from httpx import AsyncClient, ASGITransport
        from src.app import app

        async def _call():
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/health")

        with patch("src.app._check_sqs_health", return_value="healthy"):
            with patch("src.app._check_dynamodb_health", return_value="healthy"):
                with patch("src.app.shutil.which", return_value="/usr/bin/ansible-playbook"):
                    with patch("src.app.os.path.isfile", return_value=True):
                        response = asyncio.run(_call())

        body = response.json()
        assert "sqs" in body["dependencies"]
        assert "dynamodb" in body["dependencies"]
        assert body["dependencies"]["sqs"] in ("healthy", "unhealthy")
        assert body["dependencies"]["dynamodb"] in ("healthy", "unhealthy")
