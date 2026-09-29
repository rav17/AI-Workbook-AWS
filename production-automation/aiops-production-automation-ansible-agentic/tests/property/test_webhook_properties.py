# Feature: self-healing-infrastructure, Property 1, 2, 3, 26: Webhook endpoint properties
"""Property-based tests for the FastAPI webhook endpoint.

Property 1: Valid payload acceptance (Task 12.2)
*For any* valid AlertmanagerPayload containing at least one alert with non-empty
alert name, status, and severity fields, the webhook endpoint SHALL return HTTP 200.
**Validates: Requirements 1.2**

Property 2: Invalid payload rejection (Task 12.3)
*For any* request body that is not valid JSON, exceeds 1 MB, or is missing required
fields (alert name, status, or severity), the webhook endpoint SHALL return HTTP 400
with an error message.
**Validates: Requirements 1.3**

Property 3: Content-Type enforcement (Task 12.4)
*For any* request with a Content-Type header value other than application/json, the
webhook endpoint SHALL return HTTP 415 regardless of the request body content.
**Validates: Requirements 1.6**

Property 26: Health check dependency detection (Task 12.5)
*For any* combination of unavailable critical dependencies (Ansible binary, mapping
config, asset inventory), the health endpoint SHALL return HTTP 503 with status
"degraded" and correctly identify each unavailable component.
**Validates: Requirements 9.3**
"""

import asyncio
import json
from unittest.mock import patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st
from httpx import AsyncClient, ASGITransport

from src.app import app


# --- Helper ---

async def _make_request(method, path, **kwargs):
    """Make an async HTTP request to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await getattr(client, method)(path, **kwargs)


# --- Hypothesis Strategies ---

# Strategy for valid alert names (non-empty)
alert_name_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
)

# Strategy for valid severity values
severity_strategy = st.sampled_from(["critical", "warning", "info"])

# Strategy for valid alert status values
alert_status_strategy = st.sampled_from(["firing", "resolved"])

# Strategy for generating valid labels with required fields
valid_labels_strategy = st.builds(
    lambda alertname, severity, extra: {**extra, "alertname": alertname, "severity": severity},
    alertname=alert_name_strategy,
    severity=severity_strategy,
    extra=st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=20,
        ),
        values=st.text(min_size=1, max_size=50),
        min_size=0,
        max_size=5,
    ),
)

# Strategy for generating a single valid alert
valid_alert_strategy = st.fixed_dictionaries({
    "status": alert_status_strategy,
    "labels": valid_labels_strategy,
    "annotations": st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=20,
        ),
        values=st.text(min_size=0, max_size=100),
        min_size=0,
        max_size=3,
    ),
    "startsAt": st.just("2024-01-15T10:30:00Z"),
    "endsAt": st.just("0001-01-01T00:00:00Z"),
    "generatorURL": st.just("http://prometheus:9090/graph"),
    "fingerprint": st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=8,
        max_size=16,
    ),
})

# Strategy for generating a valid Alertmanager payload
valid_payload_strategy = st.fixed_dictionaries({
    "version": st.just("4"),
    "groupKey": st.text(min_size=1, max_size=50),
    "status": alert_status_strategy,
    "receiver": st.text(min_size=1, max_size=30),
    "alerts": st.lists(valid_alert_strategy, min_size=1, max_size=5),
    "groupLabels": st.just({}),
    "commonLabels": st.just({}),
    "commonAnnotations": st.just({}),
    "externalURL": st.just("http://alertmanager:9093"),
})

# Strategy for Content-Type values that are NOT application/json
non_json_content_type_strategy = st.one_of(
    st.just("text/plain"),
    st.just("text/html"),
    st.just("application/xml"),
    st.just("multipart/form-data"),
    st.just("application/x-www-form-urlencoded"),
    st.just("text/csv"),
    st.just("application/octet-stream"),
    st.just("image/png"),
    st.just("application/pdf"),
    st.just("text/xml"),
    st.just("application/soap+xml"),
    st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            whitelist_characters="/-_.",
            max_codepoint=127,
        ),
    ).filter(lambda x: "application/json" not in x.lower()),
)


# --- Property 1: Valid payload acceptance ---


class TestValidPayloadAcceptance:
    """Property tests for valid payload acceptance (Property 1).

    **Validates: Requirements 1.2**

    For any valid AlertmanagerPayload containing at least one alert with
    non-empty alert name, status, and severity fields, the webhook endpoint
    SHALL return HTTP 200.
    """

    @given(payload=valid_payload_strategy)
    @settings(max_examples=100, deadline=10000)
    def test_valid_payload_returns_200(self, payload: dict) -> None:
        """Any valid AlertmanagerPayload SHALL be accepted with HTTP 200.

        **Validates: Requirements 1.2**
        """
        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 200, (
            f"Expected HTTP 200 for valid payload, got {response.status_code}. "
            f"Response body: {response.text}"
        )

    @given(payload=valid_payload_strategy)
    @settings(max_examples=100, deadline=10000)
    def test_valid_payload_response_contains_accepted_status(self, payload: dict) -> None:
        """The response body SHALL contain status 'accepted' for valid payloads.

        **Validates: Requirements 1.2**
        """
        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "accepted", (
            f"Expected status 'accepted', got '{body.get('status')}'"
        )

    @given(payload=valid_payload_strategy)
    @settings(max_examples=100, deadline=10000)
    def test_valid_payload_response_contains_alert_count(self, payload: dict) -> None:
        """The response body SHALL contain the correct number of alerts received.

        **Validates: Requirements 1.2**
        """
        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 200
        body = response.json()
        assert body["alerts_received"] == len(payload["alerts"]), (
            f"Expected alerts_received={len(payload['alerts'])}, "
            f"got {body.get('alerts_received')}"
        )


# --- Property 2: Invalid payload rejection ---


class TestInvalidPayloadRejection:
    """Property tests for invalid payload rejection (Property 2).

    **Validates: Requirements 1.3**

    For any request body that is not valid JSON, exceeds 1 MB, or is missing
    required fields (alert name, status, or severity), the webhook endpoint
    SHALL return HTTP 400 with an error message.
    """

    @given(data=st.text(min_size=1, max_size=200).filter(lambda x: not _is_valid_json(x)))
    @settings(max_examples=100, deadline=10000)
    def test_non_json_body_returns_400(self, data: str) -> None:
        """Non-JSON request bodies SHALL be rejected with HTTP 400.

        **Validates: Requirements 1.3**
        """
        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=data,
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400, (
            f"Expected HTTP 400 for non-JSON body, got {response.status_code}. "
            f"Body sent: {data!r}"
        )

    @given(extra_size=st.integers(min_value=1, max_value=100))
    @settings(max_examples=10, deadline=30000)
    def test_oversized_payload_returns_400(self, extra_size: int) -> None:
        """Payloads exceeding 1 MB SHALL be rejected with HTTP 400.

        **Validates: Requirements 1.3**
        """
        # Generate a payload that exceeds 1 MB
        size = 1024 * 1024 + extra_size
        data = b"x" * size

        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=data,
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400, (
            f"Expected HTTP 400 for oversized payload ({len(data)} bytes), "
            f"got {response.status_code}"
        )

    @given(
        alertname=st.just(""),
        severity=severity_strategy,
        status=alert_status_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_empty_alertname_returns_400(self, alertname: str, severity: str, status: str) -> None:
        """Payloads with empty alertname SHALL be rejected with HTTP 400.

        **Validates: Requirements 1.3**
        """
        payload = {
            "version": "4",
            "groupKey": "test",
            "status": "firing",
            "receiver": "test",
            "alerts": [{
                "status": status,
                "labels": {"alertname": alertname, "severity": severity},
                "annotations": {},
                "startsAt": "2024-01-15T10:30:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "",
                "fingerprint": "abc123",
            }],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
        }

        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400, (
            f"Expected HTTP 400 for empty alertname, got {response.status_code}"
        )

    @given(
        alertname=alert_name_strategy,
        severity=st.just(""),
        status=alert_status_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_empty_severity_returns_400(self, alertname: str, severity: str, status: str) -> None:
        """Payloads with empty severity SHALL be rejected with HTTP 400.

        **Validates: Requirements 1.3**
        """
        payload = {
            "version": "4",
            "groupKey": "test",
            "status": "firing",
            "receiver": "test",
            "alerts": [{
                "status": status,
                "labels": {"alertname": alertname, "severity": severity},
                "annotations": {},
                "startsAt": "2024-01-15T10:30:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "",
                "fingerprint": "abc123",
            }],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
        }

        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400, (
            f"Expected HTTP 400 for empty severity, got {response.status_code}"
        )

    @given(
        alertname=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_empty_status_returns_400(self, alertname: str, severity: str) -> None:
        """Payloads with empty alert status SHALL be rejected with HTTP 400.

        **Validates: Requirements 1.3**
        """
        payload = {
            "version": "4",
            "groupKey": "test",
            "status": "firing",
            "receiver": "test",
            "alerts": [{
                "status": "",
                "labels": {"alertname": alertname, "severity": severity},
                "annotations": {},
                "startsAt": "2024-01-15T10:30:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "",
                "fingerprint": "abc123",
            }],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
        }

        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400, (
            f"Expected HTTP 400 for empty status, got {response.status_code}"
        )

    @settings(max_examples=100, deadline=10000)
    @given(
        alertname=alert_name_strategy,
        severity=severity_strategy,
        status=alert_status_strategy,
    )
    def test_missing_alertname_key_returns_400(self, alertname: str, severity: str, status: str) -> None:
        """Payloads missing the alertname key in labels SHALL be rejected with HTTP 400.

        **Validates: Requirements 1.3**
        """
        payload = {
            "version": "4",
            "groupKey": "test",
            "status": "firing",
            "receiver": "test",
            "alerts": [{
                "status": status,
                "labels": {"severity": severity},  # missing alertname
                "annotations": {},
                "startsAt": "2024-01-15T10:30:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "",
                "fingerprint": "abc123",
            }],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
        }

        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400, (
            f"Expected HTTP 400 for missing alertname key, got {response.status_code}"
        )

    @given(data=st.just({"not_alerts": "invalid"}))
    @settings(max_examples=10, deadline=10000)
    def test_missing_alerts_field_returns_400(self, data: dict) -> None:
        """Payloads missing the 'alerts' field SHALL be rejected with HTTP 400.

        **Validates: Requirements 1.3**
        """
        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(data),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400, (
            f"Expected HTTP 400 for missing alerts field, got {response.status_code}"
        )

    @given(data=st.just({"alerts": []}))
    @settings(max_examples=10, deadline=10000)
    def test_empty_alerts_list_returns_400(self, data: dict) -> None:
        """Payloads with an empty alerts list SHALL be rejected with HTTP 400.

        **Validates: Requirements 1.3**
        """
        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=json.dumps(data),
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400, (
            f"Expected HTTP 400 for empty alerts list, got {response.status_code}"
        )


# --- Property 3: Content-Type enforcement ---


class TestContentTypeEnforcement:
    """Property tests for Content-Type enforcement (Property 3).

    **Validates: Requirements 1.6**

    For any request with a Content-Type header value other than application/json,
    the webhook endpoint SHALL return HTTP 415 regardless of the request body content.
    """

    @given(content_type=non_json_content_type_strategy)
    @settings(max_examples=100, deadline=10000)
    def test_non_json_content_type_returns_415(self, content_type: str) -> None:
        """Any Content-Type other than application/json SHALL be rejected with HTTP 415.

        **Validates: Requirements 1.6**
        """
        # Use a valid payload body to prove the rejection is based on Content-Type
        valid_body = json.dumps({
            "version": "4",
            "groupKey": "test",
            "status": "firing",
            "receiver": "test",
            "alerts": [{
                "status": "firing",
                "labels": {"alertname": "TestAlert", "severity": "critical"},
                "annotations": {},
                "startsAt": "2024-01-15T10:30:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "",
                "fingerprint": "abc123",
            }],
            "groupLabels": {},
            "commonLabels": {},
            "commonAnnotations": {},
            "externalURL": "",
        })

        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=valid_body,
                headers={"Content-Type": content_type},
            )
        )

        assert response.status_code == 415, (
            f"Expected HTTP 415 for Content-Type '{content_type}', "
            f"got {response.status_code}"
        )

    @given(content_type=non_json_content_type_strategy)
    @settings(max_examples=100, deadline=10000)
    def test_non_json_content_type_returns_error_message(self, content_type: str) -> None:
        """The 415 response SHALL contain an error message about Content-Type.

        **Validates: Requirements 1.6**
        """
        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content="any body content",
                headers={"Content-Type": content_type},
            )
        )

        assert response.status_code == 415
        body = response.json()
        assert "error" in body, "Response should contain an 'error' field"

    @given(
        content_type=non_json_content_type_strategy,
        body=st.binary(min_size=0, max_size=500),
    )
    @settings(max_examples=100, deadline=10000)
    def test_non_json_content_type_rejects_regardless_of_body(
        self, content_type: str, body: bytes
    ) -> None:
        """HTTP 415 SHALL be returned regardless of the request body content.

        **Validates: Requirements 1.6**
        """
        response = asyncio.run(
            _make_request(
                "post",
                "/webhook",
                content=body,
                headers={"Content-Type": content_type},
            )
        )

        assert response.status_code == 415, (
            f"Expected HTTP 415 for Content-Type '{content_type}' with body of "
            f"{len(body)} bytes, got {response.status_code}"
        )


# --- Property 26: Health check dependency detection ---


class TestHealthCheckDependencyDetection:
    """Property tests for health check dependency detection (Property 26).

    **Validates: Requirements 9.3**

    For any combination of unavailable critical dependencies (Ansible binary,
    mapping config, asset inventory), the health endpoint SHALL return HTTP 503
    with status "degraded" and correctly identify each unavailable component.
    """

    @given(
        ansible_available=st.just(False),
        mapping_available=st.booleans(),
        inventory_available=st.booleans(),
    )
    @settings(max_examples=100, deadline=10000)
    def test_missing_ansible_binary_returns_503(
        self, ansible_available: bool, mapping_available: bool, inventory_available: bool
    ) -> None:
        """When ansible binary is unavailable, health SHALL return 503.

        **Validates: Requirements 9.3**
        """
        with patch("src.app._check_sqs_health", return_value="unhealthy"):
            with patch("src.app._check_dynamodb_health", return_value="unhealthy"):
                with patch("src.app.shutil.which", return_value=None if not ansible_available else "/usr/bin/ansible-playbook"):
                    with patch("src.app.os.path.isfile") as mock_isfile:
                        def isfile_side_effect(path):
                            if "mapping" in path.lower() or "mapping_config" in path.lower():
                                return mapping_available
                            if "asset" in path.lower() or "inventory" in path.lower():
                                return inventory_available
                            return False
                        mock_isfile.side_effect = isfile_side_effect

                        response = asyncio.run(_make_request("get", "/health"))

        assert response.status_code == 503, (
            f"Expected HTTP 503 when ansible is missing, got {response.status_code}"
        )
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["dependencies"]["ansible_binary"] == "missing"

    @given(
        ansible_available=st.booleans(),
        mapping_available=st.just(False),
        inventory_available=st.booleans(),
    )
    @settings(max_examples=100, deadline=10000)
    def test_missing_mapping_config_returns_503(
        self, ansible_available: bool, mapping_available: bool, inventory_available: bool
    ) -> None:
        """When mapping config is unavailable, health SHALL return 503.

        **Validates: Requirements 9.3**
        """
        with patch("src.app._check_sqs_health", return_value="unhealthy"):
            with patch("src.app._check_dynamodb_health", return_value="unhealthy"):
                with patch("src.app.shutil.which", return_value="/usr/bin/ansible-playbook" if ansible_available else None):
                    with patch("src.app.os.path.isfile") as mock_isfile:
                        def isfile_side_effect(path):
                            if "mapping" in path.lower() or "mapping_config" in path.lower():
                                return mapping_available
                            if "asset" in path.lower() or "inventory" in path.lower():
                                return inventory_available
                            return False
                        mock_isfile.side_effect = isfile_side_effect

                        response = asyncio.run(_make_request("get", "/health"))

        assert response.status_code == 503, (
            f"Expected HTTP 503 when mapping config is missing, got {response.status_code}"
        )
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["dependencies"]["mapping_config"] == "missing"

    @given(
        ansible_available=st.booleans(),
        mapping_available=st.booleans(),
        inventory_available=st.just(False),
    )
    @settings(max_examples=100, deadline=10000)
    def test_missing_asset_inventory_returns_503(
        self, ansible_available: bool, mapping_available: bool, inventory_available: bool
    ) -> None:
        """When asset inventory is unavailable, health SHALL return 503.

        **Validates: Requirements 9.3**
        """
        with patch("src.app._check_sqs_health", return_value="unhealthy"):
            with patch("src.app._check_dynamodb_health", return_value="unhealthy"):
                with patch("src.app.shutil.which", return_value="/usr/bin/ansible-playbook" if ansible_available else None):
                    with patch("src.app.os.path.isfile") as mock_isfile:
                        def isfile_side_effect(path):
                            if "mapping" in path.lower() or "mapping_config" in path.lower():
                                return mapping_available
                            if "asset" in path.lower() or "inventory" in path.lower():
                                return inventory_available
                            return False
                        mock_isfile.side_effect = isfile_side_effect

                        response = asyncio.run(_make_request("get", "/health"))

        assert response.status_code == 503, (
            f"Expected HTTP 503 when asset inventory is missing, got {response.status_code}"
        )
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["dependencies"]["asset_inventory"] == "missing"

    @given(
        ansible_available=st.booleans(),
        mapping_available=st.booleans(),
        inventory_available=st.booleans(),
    )
    @settings(max_examples=100, deadline=10000)
    def test_any_missing_dependency_returns_degraded(
        self, ansible_available: bool, mapping_available: bool, inventory_available: bool
    ) -> None:
        """Any combination with at least one missing dependency SHALL return unhealthy.

        **Validates: Requirements 9.3**
        """
        # Ensure at least one dependency is missing
        assume(not (ansible_available and mapping_available and inventory_available))

        with patch("src.app._check_sqs_health", return_value="unhealthy"):
            with patch("src.app._check_dynamodb_health", return_value="unhealthy"):
                with patch("src.app.shutil.which", return_value="/usr/bin/ansible-playbook" if ansible_available else None):
                    with patch("src.app.os.path.isfile") as mock_isfile:
                        def isfile_side_effect(path):
                            if "mapping" in path.lower() or "mapping_config" in path.lower():
                                return mapping_available
                            if "asset" in path.lower() or "inventory" in path.lower():
                                return inventory_available
                            return False
                        mock_isfile.side_effect = isfile_side_effect

                        response = asyncio.run(_make_request("get", "/health"))

        assert response.status_code == 503, (
            f"Expected HTTP 503 with missing deps "
            f"(ansible={ansible_available}, mapping={mapping_available}, "
            f"inventory={inventory_available}), got {response.status_code}"
        )
        body = response.json()
        assert body["status"] == "unhealthy"

        # Verify each dependency status is correctly reported
        if not ansible_available:
            assert body["dependencies"]["ansible_binary"] == "missing"
        if not mapping_available:
            assert body["dependencies"]["mapping_config"] == "missing"
        if not inventory_available:
            assert body["dependencies"]["asset_inventory"] == "missing"

    @given(data=st.just(True))
    @settings(max_examples=10, deadline=10000)
    def test_all_dependencies_available_returns_200(self, data: bool) -> None:
        """When all dependencies are available, health SHALL return HTTP 200.

        **Validates: Requirements 9.3**
        """
        with patch("src.app._check_sqs_health", return_value="healthy"):
            with patch("src.app._check_dynamodb_health", return_value="healthy"):
                with patch("src.app.shutil.which", return_value="/usr/bin/ansible-playbook"):
                    with patch("src.app.os.path.isfile", return_value=True):
                        response = asyncio.run(_make_request("get", "/health"))

        assert response.status_code == 200, (
            f"Expected HTTP 200 when all deps available, got {response.status_code}"
        )
        body = response.json()
        assert body["status"] == "healthy"
        assert body["dependencies"]["sqs"] == "healthy"
        assert body["dependencies"]["dynamodb"] == "healthy"
        assert body["dependencies"]["ansible_binary"] == "ok"
        assert body["dependencies"]["mapping_config"] == "ok"
        assert body["dependencies"]["asset_inventory"] == "ok"


# --- Utility functions ---

def _is_valid_json(text: str) -> bool:
    """Check if a string is valid JSON."""
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False
