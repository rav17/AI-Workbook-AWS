"""DynamoDB-backed store for historical incident records and outcomes.

Provides methods to record incidents, query history by various attributes,
and record remediation outcomes. All operations handle DynamoDB unreachability
gracefully by logging warnings and proceeding without error.

Requirements: 3.1, 3.2, 3.4, 3.5, 11.1
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from src.agentic_ai.models.domain import IncidentRecord
from src.agentic_ai.models.enums import EscalationStatus

logger = logging.getLogger(__name__)

# Timeout configuration for DynamoDB operations
_QUERY_TIMEOUT_SECONDS = 5
_RECORD_TIMEOUT_SECONDS = 5
_MAX_QUERY_RESULTS = 10


class IncidentMemoryStore:
    """DynamoDB-backed store for historical incident records and outcomes.

    Persists incident records with TTL-based expiry and supports querying
    by alert_name, severity, or service ordered by recency.

    All methods handle DynamoDB unreachability gracefully: log a warning
    and return empty results or proceed without error.

    Attributes:
        table_name: Name of the DynamoDB table.
        retention_days: Number of days to retain records (7-365).
    """

    def __init__(
        self,
        table_name: str,
        retention_days: int = 90,
        dynamodb_client=None,
        region_name: Optional[str] = None,
    ) -> None:
        """Initialize the IncidentMemoryStore.

        Args:
            table_name: Name of the DynamoDB table to use.
            retention_days: Days to retain incident records (7-365, default 90).
            dynamodb_client: Optional pre-configured boto3 DynamoDB client.
                If not provided, a new client is created.
            region_name: AWS region for the DynamoDB client (used only if
                dynamodb_client is not provided).
        """
        self.table_name = table_name
        self.retention_days = max(7, min(365, retention_days))

        if dynamodb_client is not None:
            self._client = dynamodb_client
        else:
            config = Config(
                connect_timeout=_QUERY_TIMEOUT_SECONDS,
                read_timeout=_QUERY_TIMEOUT_SECONDS,
                retries={"max_attempts": 1},
            )
            kwargs = {"config": config}
            if region_name:
                kwargs["region_name"] = region_name
            self._client = boto3.client("dynamodb", **kwargs)

    def _calculate_expiry_timestamp(self, completion_timestamp: datetime) -> int:
        """Calculate the TTL expiry timestamp.

        expiry_timestamp = completion_timestamp + (retention_days × 86400)

        Args:
            completion_timestamp: When the remediation completed.

        Returns:
            Unix epoch integer for DynamoDB TTL.
        """
        epoch = int(completion_timestamp.timestamp())
        return epoch + (self.retention_days * 86400)

    def _record_to_item(self, record: IncidentRecord) -> dict:
        """Convert an IncidentRecord to a DynamoDB item dict.

        Args:
            record: The incident record to convert.

        Returns:
            DynamoDB-formatted item dictionary.
        """
        item = {
            "incident_id": {"S": record.incident_id},
            "timestamp_completed": {"N": str(int(record.timestamp_completed.timestamp()))},
            "alert_name": {"S": record.alert_name},
            "severity": {"S": record.severity},
            "affected_service": {"S": record.affected_service},
            "affected_resource": {"S": record.affected_resource},
            "remediation_action": {"S": record.remediation_action},
            "outcome": {"S": record.outcome},
            "execution_duration_seconds": {"N": str(record.execution_duration_seconds)},
            "expiry_timestamp": {"N": str(record.expiry_timestamp)},
            "fallback_used": {"BOOL": record.fallback_used},
            "reasoning_summary": {"S": record.reasoning_summary},
        }

        # Optional fields
        if record.model_id is not None:
            item["model_id"] = {"S": record.model_id}
        if record.input_token_count is not None:
            item["input_token_count"] = {"N": str(record.input_token_count)}
        if record.output_token_count is not None:
            item["output_token_count"] = {"N": str(record.output_token_count)}
        if record.reasoning_latency_ms is not None:
            item["reasoning_latency_ms"] = {"N": str(record.reasoning_latency_ms)}
        if record.confidence_score is not None:
            item["confidence_score"] = {"N": str(record.confidence_score)}
        if record.escalation_status is not None:
            item["escalation_status"] = {"S": record.escalation_status.value}
        if record.escalation_responder is not None:
            item["escalation_responder"] = {"S": record.escalation_responder}
        if record.escalation_response_timestamp is not None:
            item["escalation_response_timestamp"] = {
                "N": str(int(record.escalation_response_timestamp.timestamp()))
            }
        if record.fallback_reason is not None:
            item["fallback_reason"] = {"S": record.fallback_reason}

        return item

    def _item_to_record(self, item: dict) -> IncidentRecord:
        """Convert a DynamoDB item dict to an IncidentRecord.

        Args:
            item: DynamoDB-formatted item dictionary.

        Returns:
            IncidentRecord instance.
        """
        escalation_status = None
        if "escalation_status" in item:
            try:
                escalation_status = EscalationStatus(item["escalation_status"]["S"])
            except (ValueError, KeyError):
                escalation_status = None

        escalation_response_timestamp = None
        if "escalation_response_timestamp" in item:
            escalation_response_timestamp = datetime.fromtimestamp(
                int(item["escalation_response_timestamp"]["N"]),
                tz=timezone.utc,
            )

        return IncidentRecord(
            incident_id=item["incident_id"]["S"],
            alert_name=item["alert_name"]["S"],
            severity=item["severity"]["S"],
            affected_service=item["affected_service"]["S"],
            affected_resource=item["affected_resource"]["S"],
            remediation_action=item["remediation_action"]["S"],
            outcome=item["outcome"]["S"],
            execution_duration_seconds=float(item["execution_duration_seconds"]["N"]),
            timestamp_completed=datetime.fromtimestamp(
                int(item["timestamp_completed"]["N"]),
                tz=timezone.utc,
            ),
            expiry_timestamp=int(item["expiry_timestamp"]["N"]),
            model_id=item.get("model_id", {}).get("S"),
            input_token_count=(
                int(item["input_token_count"]["N"])
                if "input_token_count" in item
                else None
            ),
            output_token_count=(
                int(item["output_token_count"]["N"])
                if "output_token_count" in item
                else None
            ),
            reasoning_latency_ms=(
                float(item["reasoning_latency_ms"]["N"])
                if "reasoning_latency_ms" in item
                else None
            ),
            confidence_score=(
                float(item["confidence_score"]["N"])
                if "confidence_score" in item
                else None
            ),
            reasoning_summary=item.get("reasoning_summary", {}).get("S", ""),
            escalation_status=escalation_status,
            escalation_responder=item.get("escalation_responder", {}).get("S"),
            escalation_response_timestamp=escalation_response_timestamp,
            fallback_used=item.get("fallback_used", {}).get("BOOL", False),
            fallback_reason=item.get("fallback_reason", {}).get("S"),
        )

    def record_incident(self, record: IncidentRecord) -> bool:
        """Write an incident record to DynamoDB with TTL-based expiry.

        Calculates the expiry_timestamp based on the configured retention_days
        and writes the record to the table. If the store is unreachable,
        logs a warning and returns False.

        Args:
            record: The incident record to store.

        Returns:
            True if the record was successfully written, False otherwise.
        """
        try:
            # Calculate TTL if not already set
            if record.expiry_timestamp == 0:
                record.expiry_timestamp = self._calculate_expiry_timestamp(
                    record.timestamp_completed
                )

            item = self._record_to_item(record)

            self._client.put_item(
                TableName=self.table_name,
                Item=item,
            )
            logger.info(
                "Recorded incident %s in memory store", record.incident_id
            )
            return True

        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as e:
            logger.warning(
                "Incident Memory Store unreachable when recording incident %s: %s",
                record.incident_id,
                str(e),
            )
            return False
        except (ClientError, BotoCoreError) as e:
            logger.warning(
                "Failed to record incident %s in memory store: %s",
                record.incident_id,
                str(e),
            )
            return False

    def query_history(
        self,
        alert_name: Optional[str] = None,
        severity: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = _MAX_QUERY_RESULTS,
    ) -> list[IncidentRecord]:
        """Query historical incidents ordered by recency.

        Matches on at least one of: alert_name, severity, or service.
        Returns up to `limit` records, most recent first.
        Times out after 5 seconds.

        If the store is unreachable or does not respond within 5 seconds,
        logs a warning and returns an empty list.

        Args:
            alert_name: Filter by exact alert name (uses GSI-1).
            severity: Filter by severity level.
            service: Filter by affected service (uses GSI-2).
            limit: Maximum number of results to return (default 10).

        Returns:
            List of matching IncidentRecord instances, ordered by
            timestamp_completed descending (most recent first).
        """
        if not any([alert_name, severity, service]):
            return []

        limit = min(limit, _MAX_QUERY_RESULTS)
        start_time = time.monotonic()

        try:
            results: list[IncidentRecord] = []

            # Query by alert_name using GSI-1 (AlertNameIndex)
            if alert_name:
                if time.monotonic() - start_time >= _QUERY_TIMEOUT_SECONDS:
                    logger.warning(
                        "Query timeout reached before completing alert_name query"
                    )
                    return results[:limit]

                response = self._client.query(
                    TableName=self.table_name,
                    IndexName="AlertNameIndex",
                    KeyConditionExpression="alert_name = :an",
                    ExpressionAttributeValues={":an": {"S": alert_name}},
                    ScanIndexForward=False,  # Descending order (most recent first)
                    Limit=limit,
                )
                for item in response.get("Items", []):
                    results.append(self._item_to_record(item))

            # Query by service using GSI-2 (ServiceIndex)
            if service and len(results) < limit:
                if time.monotonic() - start_time >= _QUERY_TIMEOUT_SECONDS:
                    logger.warning(
                        "Query timeout reached before completing service query"
                    )
                    return results[:limit]

                response = self._client.query(
                    TableName=self.table_name,
                    IndexName="ServiceIndex",
                    KeyConditionExpression="affected_service = :svc",
                    ExpressionAttributeValues={":svc": {"S": service}},
                    ScanIndexForward=False,
                    Limit=limit,
                )
                for item in response.get("Items", []):
                    record = self._item_to_record(item)
                    # Avoid duplicates
                    if record.incident_id not in {r.incident_id for r in results}:
                        results.append(record)

            # Query by severity - scan with filter (no dedicated GSI for severity alone)
            # GSI-1 has severity as sort key, so we can query if alert_name is known
            # For severity-only queries, use a scan with filter
            if severity and not alert_name and len(results) < limit:
                if time.monotonic() - start_time >= _QUERY_TIMEOUT_SECONDS:
                    logger.warning(
                        "Query timeout reached before completing severity query"
                    )
                    return results[:limit]

                response = self._client.scan(
                    TableName=self.table_name,
                    FilterExpression="severity = :sev",
                    ExpressionAttributeValues={":sev": {"S": severity}},
                    Limit=limit * 5,  # Scan more to account for filtering
                )
                for item in response.get("Items", []):
                    record = self._item_to_record(item)
                    if record.incident_id not in {r.incident_id for r in results}:
                        results.append(record)

            # Sort all results by timestamp descending and limit
            results.sort(
                key=lambda r: r.timestamp_completed,
                reverse=True,
            )
            return results[:limit]

        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as e:
            logger.warning(
                "Incident Memory Store unreachable during history query: %s",
                str(e),
            )
            return []
        except (ClientError, BotoCoreError) as e:
            logger.warning(
                "Failed to query incident history: %s",
                str(e),
            )
            return []

    def record_outcome(
        self,
        incident_id: str,
        outcome: str,
        execution_duration_seconds: float,
        timestamp_completed: Optional[datetime] = None,
    ) -> bool:
        """Record remediation outcome for an existing incident.

        Updates the incident record with outcome data within 5 seconds
        of completion. If the store is unreachable, logs a warning
        and returns False.

        Args:
            incident_id: The incident ID to update.
            outcome: Result of remediation (success, failure, timeout).
            execution_duration_seconds: Duration of execution in seconds.
            timestamp_completed: When the remediation completed.
                Defaults to current UTC time.

        Returns:
            True if the outcome was successfully recorded, False otherwise.
        """
        if timestamp_completed is None:
            timestamp_completed = datetime.now(timezone.utc)

        try:
            expiry_timestamp = self._calculate_expiry_timestamp(timestamp_completed)

            self._client.update_item(
                TableName=self.table_name,
                Key={
                    "incident_id": {"S": incident_id},
                    "timestamp_completed": {
                        "N": str(int(timestamp_completed.timestamp()))
                    },
                },
                UpdateExpression=(
                    "SET outcome = :outcome, "
                    "execution_duration_seconds = :dur, "
                    "expiry_timestamp = :ttl"
                ),
                ExpressionAttributeValues={
                    ":outcome": {"S": outcome},
                    ":dur": {"N": str(execution_duration_seconds)},
                    ":ttl": {"N": str(expiry_timestamp)},
                },
            )
            logger.info(
                "Recorded outcome '%s' for incident %s", outcome, incident_id
            )
            return True

        except (
            EndpointConnectionError,
            ConnectTimeoutError,
            ReadTimeoutError,
        ) as e:
            logger.warning(
                "Incident Memory Store unreachable when recording outcome "
                "for incident %s: %s",
                incident_id,
                str(e),
            )
            return False
        except (ClientError, BotoCoreError) as e:
            logger.warning(
                "Failed to record outcome for incident %s: %s",
                incident_id,
                str(e),
            )
            return False
