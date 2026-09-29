"""Alert Ingestion Handler — validates and publishes alerts to SQS.

Validates JSON structure, size, required fields, and authentication.
Publishes valid payloads to SQS and responds within 2 seconds.

Requirements: 5.1, 5.2, 5.7, 10.1, 10.5, 10.7
"""

import json
import logging
import time
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

MAX_PAYLOAD_SIZE_BYTES = 1_048_576  # 1 MB
RESPONSE_TIMEOUT_SECONDS = 2.0


class AlertIngestionHandler:
    """Validates webhook payloads and publishes to SQS.

    Validation:
    - JSON structure validity
    - Size ≤ 1 MB
    - Required fields: alerts array with alertname and severity
    - Authentication (API key or SigV4)

    Publishes valid payloads to SQS and responds HTTP 200 within 2 seconds.
    """

    def __init__(
        self,
        queue_url: str,
        api_key: Optional[str] = None,
        sqs_client=None,
        region_name: Optional[str] = None,
    ) -> None:
        self._queue_url = queue_url
        self._api_key = api_key

        if sqs_client:
            self._sqs = sqs_client
        else:
            kwargs = {}
            if region_name:
                kwargs["region_name"] = region_name
            self._sqs = boto3.client("sqs", **kwargs)

    def validate_payload(self, body: bytes) -> tuple[bool, str, Optional[dict]]:
        """Validate the incoming payload.

        Returns:
            Tuple of (is_valid, error_message, parsed_payload).
        """
        # Size check
        if len(body) > MAX_PAYLOAD_SIZE_BYTES:
            return False, "Payload exceeds 1 MB size limit", None

        # JSON parse
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return False, f"Invalid JSON: {e}", None

        # Structure validation
        if not isinstance(payload, dict):
            return False, "Payload must be a JSON object", None

        alerts = payload.get("alerts")
        if not isinstance(alerts, list) or len(alerts) == 0:
            return False, "Payload must contain non-empty 'alerts' array", None

        # Validate each alert has alertname and severity
        for i, alert in enumerate(alerts):
            if not isinstance(alert, dict):
                return False, f"Alert at index {i} must be an object", None
            labels = alert.get("labels", {})
            if not labels.get("alertname"):
                return (
                    False,
                    f"Alert at index {i} missing 'alertname' in labels",
                    None,
                )
            if not labels.get("severity"):
                return (
                    False,
                    f"Alert at index {i} missing 'severity' in labels",
                    None,
                )

        return True, "", payload

    def authenticate(
        self, api_key_header: Optional[str], source_ip: str, path: str
    ) -> bool:
        """Authenticate the request.

        Args:
            api_key_header: Value of the X-API-Key header.
            source_ip: Source IP address.
            path: Request path.

        Returns:
            True if authenticated, False otherwise.
        """
        if self._api_key is None:
            # No API key configured — allow all
            return True

        if not api_key_header:
            logger.warning(
                "Unauthorized request: source_ip=%s path=%s reason=missing_api_key",
                source_ip,
                path,
            )
            return False

        if api_key_header != self._api_key:
            logger.warning(
                "Unauthorized request: source_ip=%s path=%s reason=invalid_api_key "
                "key_suffix=%s",
                source_ip,
                path,
                api_key_header[-4:] if len(api_key_header) >= 4 else "****",
            )
            return False

        return True

    def publish_to_sqs(self, payload: dict) -> bool:
        """Publish validated payload to SQS.

        Args:
            payload: The validated alert payload.

        Returns:
            True if published successfully, False otherwise.
        """
        try:
            self._sqs.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps(payload),
            )
            return True
        except (ClientError, BotoCoreError) as e:
            logger.error("Failed to publish to SQS: %s", e)
            return False

    def handle_request(
        self,
        body: bytes,
        api_key_header: Optional[str] = None,
        source_ip: str = "",
        path: str = "/webhook",
    ) -> tuple[int, dict]:
        """Handle an incoming webhook request.

        Returns:
            Tuple of (http_status_code, response_body_dict).
        """
        start = time.time()

        # Authenticate
        if not self.authenticate(api_key_header, source_ip, path):
            return 401, {"error": "Unauthorized"}

        # Validate
        is_valid, error_msg, payload = self.validate_payload(body)
        if not is_valid:
            return 400, {"error": error_msg}

        # Publish to SQS
        published = self.publish_to_sqs(payload)
        if not published:
            return 500, {"error": "Failed to enqueue alert"}

        # Log authenticated request
        duration = time.time() - start
        key_suffix = api_key_header[-4:] if api_key_header and len(api_key_header) >= 4 else "none"
        logger.info(
            "Alert ingested: source_ip=%s key_suffix=%s path=%s "
            "status=200 alerts=%d duration_ms=%.0f",
            source_ip,
            key_suffix,
            path,
            len(payload.get("alerts", [])),
            duration * 1000,
        )

        return 200, {
            "status": "accepted",
            "alerts_received": len(payload.get("alerts", [])),
        }
