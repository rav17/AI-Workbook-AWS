"""DynamoDB-backed store for historical incident records and outcomes.

Provides methods to record incidents, query history by various attributes,
and record remediation outcomes. All operations handle DynamoDB unreachability
gracefully by logging warnings and proceeding without error.

Table layout (``AiopsIncidentMemory-{env}``, shared with approval tokens, locks and
deferred actions):

* Partition key ``incident_id`` (string), sort key ``timestamp`` (string).
* Incident items use the sort key ``INCIDENT#<UTC ISO-8601>`` so they never collide with
  approval items (``APPROVAL#<token>``) that share the partition key and the
  ``alert_name`` attribute.
* GSIs used here: ``AlertNameIndex`` (``alert_name`` / ``timestamp``) and
  ``ServiceIndex`` (``service_name`` / ``timestamp``). Both project all attributes.

Outcome values: ``pending`` (plan produced, nothing decided yet), then one of the
terminal values ``success``, ``failure`` or ``timeout``. The model router counts
terminal outcomes only.

Requirements: 3.1, 3.2, 3.4, 3.5, 11.1
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

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
_MAX_QUERY_RESULTS = 50

# Sort-key prefix for incident items (approval items use "APPROVAL#").
INCIDENT_SK_PREFIX = "INCIDENT#"

# Outcome values.
OUTCOME_PENDING = "pending"
TERMINAL_OUTCOMES = frozenset({"success", "failure", "timeout"})

# Unresolved incidents older than this are not matched by a "resolved" signal.
DEFAULT_RESOLUTION_MAX_AGE_SECONDS = 6 * 3600

_NETWORK_ERRORS = (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError)


def _iso(moment: datetime) -> str:
    """Format a datetime as a sortable UTC ISO-8601 string (millisecond precision)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _parse_iso(value: str) -> Optional[datetime]:
    """Parse a string produced by :func:`_iso`; return None if it is malformed."""
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _non_empty(value: str, default: str = "unknown") -> str:
    """Return ``value`` or ``default``; DynamoDB rejects empty strings in index keys."""
    return value if value else default


def _is_conditional_failure(error: ClientError) -> bool:
    """Return True if the error is a failed ConditionExpression."""
    return (
        error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"
    )


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
        dynamodb_client: Any = None,
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
                retries={"max_attempts": 2},
            )
            kwargs: dict[str, Any] = {"config": config}
            if region_name:
                kwargs["region_name"] = region_name
            self._client = boto3.client("dynamodb", **kwargs)

    # ------------------------------------------------------------------
    # Item conversion
    # ------------------------------------------------------------------

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

    def _record_to_item(self, record: IncidentRecord) -> dict[str, Any]:
        """Convert an IncidentRecord to a DynamoDB item dict.

        Args:
            record: The incident record to convert.

        Returns:
            DynamoDB-formatted item dictionary.
        """
        item: dict[str, Any] = {
            "incident_id": {"S": record.incident_id},
            "timestamp": {
                "S": f"{INCIDENT_SK_PREFIX}{_iso(record.timestamp_completed)}"
            },
            "timestamp_completed": {
                "N": str(int(record.timestamp_completed.timestamp()))
            },
            "alert_name": {"S": _non_empty(record.alert_name)},
            "severity": {"S": _non_empty(record.severity)},
            "affected_service": {"S": record.affected_service},
            # service_name is the ServiceIndex partition key (must not be empty).
            "service_name": {"S": _non_empty(record.affected_service)},
            "affected_resource": {"S": record.affected_resource},
            "remediation_action": {"S": record.remediation_action},
            "outcome": {"S": _non_empty(record.outcome, OUTCOME_PENDING)},
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

    def _item_to_record(self, item: dict[str, Any]) -> IncidentRecord:
        """Convert a DynamoDB item dict to an IncidentRecord.

        Args:
            item: DynamoDB-formatted item dictionary.

        Returns:
            IncidentRecord instance.

        Raises:
            KeyError: If ``incident_id`` is missing.
            ValueError: If a numeric attribute is malformed.
        """

        def text(key: str, default: str = "") -> str:
            return item.get(key, {}).get("S", default)

        def number(key: str) -> Optional[str]:
            return item.get(key, {}).get("N")

        escalation_status = None
        if "escalation_status" in item:
            try:
                escalation_status = EscalationStatus(item["escalation_status"]["S"])
            except (ValueError, KeyError):
                escalation_status = None

        escalation_response_timestamp = None
        if number("escalation_response_timestamp") is not None:
            escalation_response_timestamp = datetime.fromtimestamp(
                int(number("escalation_response_timestamp") or 0),
                tz=timezone.utc,
            )

        completed_raw = number("timestamp_completed")
        if completed_raw is not None:
            completed = datetime.fromtimestamp(int(completed_raw), tz=timezone.utc)
        else:
            completed = _parse_iso(
                text("timestamp").removeprefix(INCIDENT_SK_PREFIX)
            ) or datetime.now(timezone.utc)

        duration = number("execution_duration_seconds")
        expiry = number("expiry_timestamp")
        latency = number("reasoning_latency_ms")
        confidence = number("confidence_score")
        input_tokens = number("input_token_count")
        output_tokens = number("output_token_count")

        return IncidentRecord(
            incident_id=item["incident_id"]["S"],
            alert_name=text("alert_name"),
            severity=text("severity"),
            affected_service=text("affected_service"),
            affected_resource=text("affected_resource"),
            remediation_action=text("remediation_action"),
            outcome=text("outcome", OUTCOME_PENDING),
            execution_duration_seconds=float(duration) if duration is not None else 0.0,
            timestamp_completed=completed,
            expiry_timestamp=int(expiry) if expiry is not None else 0,
            model_id=item.get("model_id", {}).get("S"),
            input_token_count=int(input_tokens) if input_tokens is not None else None,
            output_token_count=int(output_tokens)
            if output_tokens is not None
            else None,
            reasoning_latency_ms=float(latency) if latency is not None else None,
            confidence_score=float(confidence) if confidence is not None else None,
            reasoning_summary=text("reasoning_summary"),
            escalation_status=escalation_status,
            escalation_responder=item.get("escalation_responder", {}).get("S"),
            escalation_response_timestamp=escalation_response_timestamp,
            fallback_used=item.get("fallback_used", {}).get("BOOL", False),
            fallback_reason=item.get("fallback_reason", {}).get("S"),
        )

    def _items_to_records(self, items: list[dict[str, Any]]) -> list[IncidentRecord]:
        """Convert items to records, skipping (and logging) any malformed item."""
        records: list[IncidentRecord] = []
        for item in items:
            try:
                records.append(self._item_to_record(item))
            except (KeyError, ValueError) as e:
                logger.warning("Skipping malformed incident item: %s", e)
        return records

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

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
                "Recorded incident %s in memory store",
                record.incident_id,
                extra={"incident_id": record.incident_id},
            )
            return True

        except _NETWORK_ERRORS as e:
            logger.warning(
                "Incident Memory Store unreachable when recording incident %s: %s",
                record.incident_id,
                str(e),
                extra={"incident_id": record.incident_id},
            )
            return False
        except (ClientError, BotoCoreError) as e:
            logger.warning(
                "Failed to record incident %s in memory store: %s",
                record.incident_id,
                str(e),
                extra={"incident_id": record.incident_id},
            )
            return False

    def _find_item(self, incident_id: str) -> Optional[dict[str, Any]]:
        """Return the raw incident item for ``incident_id`` (approval items are ignored).

        Raises:
            ClientError, BotoCoreError: On DynamoDB errors (callers handle them).
        """
        response = self._client.query(
            TableName=self.table_name,
            KeyConditionExpression="incident_id = :id AND begins_with(#ts, :p)",
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={
                ":id": {"S": incident_id},
                ":p": {"S": INCIDENT_SK_PREFIX},
            },
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def get_incident(self, incident_id: str) -> Optional[IncidentRecord]:
        """Fetch one incident record by id.

        Args:
            incident_id: The incident to look up.

        Returns:
            The record, or None if it does not exist or the store is unreachable.
        """
        try:
            item = self._find_item(incident_id)
            if item is None:
                return None
            return self._item_to_record(item)
        except (ClientError, BotoCoreError, KeyError, ValueError) as e:
            logger.warning(
                "Failed to read incident %s: %s",
                incident_id,
                e,
                extra={"incident_id": incident_id},
            )
            return None

    def record_outcome(
        self,
        incident_id: str,
        outcome: str,
        execution_duration_seconds: float,
        timestamp_completed: Optional[datetime] = None,
        *,
        source: Optional[str] = None,
        only_if_pending: bool = False,
    ) -> bool:
        """Record remediation outcome for an existing incident.

        Updates the incident record with outcome data. If the store is unreachable,
        logs a warning and returns False.

        Args:
            incident_id: The incident ID to update.
            outcome: Result of remediation (success, failure, timeout).
            execution_duration_seconds: Duration of execution in seconds.
            timestamp_completed: When the remediation completed.
                Defaults to current UTC time.
            source: Optional origin of the outcome (for example ``human_feedback``).
            only_if_pending: If True, apply only while the outcome is still ``pending``.
                This makes the first writer win, so a feedback link works once.

        Returns:
            True if the outcome was recorded; False if the incident does not exist, the
            outcome was already decided (``only_if_pending``), or the store failed.
        """
        if timestamp_completed is None:
            timestamp_completed = datetime.now(timezone.utc)

        try:
            item = self._find_item(incident_id)
            if item is None:
                logger.warning(
                    "No incident record for %s; outcome '%s' not recorded",
                    incident_id,
                    outcome,
                    extra={"incident_id": incident_id},
                )
                return False

            expiry_timestamp = self._calculate_expiry_timestamp(timestamp_completed)
            update = (
                "SET #o = :outcome, execution_duration_seconds = :dur, "
                "timestamp_completed = :tc, expiry_timestamp = :ttl"
            )
            values: dict[str, Any] = {
                ":outcome": {"S": outcome},
                ":dur": {"N": str(execution_duration_seconds)},
                ":tc": {"N": str(int(timestamp_completed.timestamp()))},
                ":ttl": {"N": str(expiry_timestamp)},
            }
            if source:
                update += ", outcome_source = :src"
                values[":src"] = {"S": source}
            kwargs: dict[str, Any] = {}
            if only_if_pending:
                kwargs["ConditionExpression"] = "#o = :pending"
                values[":pending"] = {"S": OUTCOME_PENDING}

            self._client.update_item(
                TableName=self.table_name,
                Key={
                    "incident_id": {"S": incident_id},
                    "timestamp": item["timestamp"],
                },
                UpdateExpression=update,
                ExpressionAttributeNames={"#o": "outcome"},
                ExpressionAttributeValues=values,
                **kwargs,
            )
            logger.info(
                "Recorded outcome '%s' for incident %s",
                outcome,
                incident_id,
                extra={"incident_id": incident_id},
            )
            return True

        except ClientError as e:
            if _is_conditional_failure(e):
                logger.info(
                    "Outcome for incident %s was already decided",
                    incident_id,
                    extra={"incident_id": incident_id},
                )
                return False
            logger.warning(
                "Failed to record outcome for incident %s: %s",
                incident_id,
                str(e),
                extra={"incident_id": incident_id},
            )
            return False
        except _NETWORK_ERRORS as e:
            logger.warning(
                "Incident Memory Store unreachable when recording outcome "
                "for incident %s: %s",
                incident_id,
                str(e),
                extra={"incident_id": incident_id},
            )
            return False
        except BotoCoreError as e:
            logger.warning(
                "Failed to record outcome for incident %s: %s",
                incident_id,
                str(e),
                extra={"incident_id": incident_id},
            )
            return False

    def record_resolution_for_alert(
        self,
        alert_name: str,
        resource: str,
        max_age_seconds: int = DEFAULT_RESOLUTION_MAX_AGE_SECONDS,
    ) -> Optional[str]:
        """Mark the newest unresolved incident for an alert and resource as resolved.

        Sets ``resolution_status = resolved`` and ``resolved_at``. The ``outcome`` is not
        changed: an alert clearing on its own does not show that the AI advice worked.
        The lookup goes through DynamoDB, so it works when the "resolved" notification
        reaches a different ECS task than the one that handled the firing alert.

        Args:
            alert_name: The alert that resolved.
            resource: The affected resource (instance) that resolved.
            max_age_seconds: Ignore incidents created longer ago than this.

        Returns:
            The incident_id that was marked resolved, or None if nothing matched.
        """
        try:
            response = self._client.query(
                TableName=self.table_name,
                IndexName="AlertNameIndex",
                KeyConditionExpression="alert_name = :an AND begins_with(#ts, :p)",
                ExpressionAttributeNames={"#ts": "timestamp"},
                ExpressionAttributeValues={
                    ":an": {"S": alert_name},
                    ":p": {"S": INCIDENT_SK_PREFIX},
                },
                ScanIndexForward=False,
                Limit=25,
            )
            now = datetime.now(timezone.utc)
            for item in response.get("Items", []):
                created = _parse_iso(
                    item.get("timestamp", {})
                    .get("S", "")
                    .removeprefix(INCIDENT_SK_PREFIX)
                )
                if (
                    created is not None
                    and (now - created).total_seconds() > max_age_seconds
                ):
                    break  # Newest first: everything after this is older still.
                if item.get("affected_resource", {}).get("S") != resource:
                    continue
                if "resolution_status" in item:
                    continue
                incident_id = item["incident_id"]["S"]
                try:
                    self._client.update_item(
                        TableName=self.table_name,
                        Key={
                            "incident_id": item["incident_id"],
                            "timestamp": item["timestamp"],
                        },
                        UpdateExpression=(
                            "SET resolution_status = :r, resolved_at = :t"
                        ),
                        ConditionExpression=(
                            "attribute_exists(incident_id) "
                            "AND attribute_not_exists(resolution_status)"
                        ),
                        ExpressionAttributeValues={
                            ":r": {"S": "resolved"},
                            ":t": {"N": str(int(time.time()))},
                        },
                    )
                except ClientError as e:
                    if _is_conditional_failure(e):
                        continue  # Another task resolved it first; try the next one.
                    raise
                logger.info(
                    "Marked incident %s resolved (%s on %s)",
                    incident_id,
                    alert_name,
                    resource,
                    extra={"incident_id": incident_id},
                )
                return incident_id
            return None
        except _NETWORK_ERRORS as e:
            logger.warning("Incident Memory Store unreachable during resolution: %s", e)
            return None
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to record resolution for %s: %s", alert_name, e)
            return None

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def query_history(
        self,
        alert_name: Optional[str] = None,
        severity: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 10,
    ) -> list[IncidentRecord]:
        """Query historical incidents ordered by recency.

        Matches on at least one of: alert_name, severity, or service.
        Returns up to `limit` records, most recent first. Only incident items are
        returned (approval items in the same table are excluded by the sort-key prefix).
        Times out after 5 seconds.

        If the store is unreachable or does not respond within 5 seconds,
        logs a warning and returns an empty list.

        Args:
            alert_name: Filter by exact alert name (uses AlertNameIndex).
            severity: Filter by severity level (scan; used only without alert_name).
            service: Filter by affected service (uses ServiceIndex).
            limit: Maximum number of results to return (default 10, max 50).

        Returns:
            List of matching IncidentRecord instances, ordered by creation time
            descending (most recent first).
        """
        if not any([alert_name, severity, service]):
            return []

        limit = max(1, min(limit, _MAX_QUERY_RESULTS))
        start_time = time.monotonic()
        names = {"#ts": "timestamp"}
        prefix = {":p": {"S": INCIDENT_SK_PREFIX}}

        try:
            results: list[IncidentRecord] = []

            if alert_name:
                response = self._client.query(
                    TableName=self.table_name,
                    IndexName="AlertNameIndex",
                    KeyConditionExpression="alert_name = :an AND begins_with(#ts, :p)",
                    ExpressionAttributeNames=names,
                    ExpressionAttributeValues={":an": {"S": alert_name}, **prefix},
                    ScanIndexForward=False,  # Descending order (most recent first)
                    Limit=limit,
                )
                results.extend(self._items_to_records(response.get("Items", [])))

            if service and len(results) < limit:
                if time.monotonic() - start_time >= _QUERY_TIMEOUT_SECONDS:
                    logger.warning(
                        "Query timeout reached before completing service query"
                    )
                    return results[:limit]

                response = self._client.query(
                    TableName=self.table_name,
                    IndexName="ServiceIndex",
                    KeyConditionExpression="service_name = :svc AND begins_with(#ts, :p)",
                    ExpressionAttributeNames=names,
                    ExpressionAttributeValues={":svc": {"S": service}, **prefix},
                    ScanIndexForward=False,
                    Limit=limit,
                )
                seen = {r.incident_id for r in results}
                for record in self._items_to_records(response.get("Items", [])):
                    if record.incident_id not in seen:
                        results.append(record)

            # Severity-only: there is no dedicated GSI, so scan with a filter.
            if severity and not alert_name and not service and len(results) < limit:
                if time.monotonic() - start_time >= _QUERY_TIMEOUT_SECONDS:
                    logger.warning(
                        "Query timeout reached before completing severity query"
                    )
                    return results[:limit]

                response = self._client.scan(
                    TableName=self.table_name,
                    FilterExpression="begins_with(#ts, :p) AND severity = :sev",
                    ExpressionAttributeNames=names,
                    ExpressionAttributeValues={":sev": {"S": severity}, **prefix},
                    Limit=limit * 5,  # Scan more to account for filtering
                )
                seen = {r.incident_id for r in results}
                for record in self._items_to_records(response.get("Items", [])):
                    if record.incident_id not in seen:
                        results.append(record)

            results.sort(key=lambda r: r.timestamp_completed, reverse=True)
            return results[:limit]

        except _NETWORK_ERRORS as e:
            logger.warning(
                "Incident Memory Store unreachable during history query: %s", str(e)
            )
            return []
        except (ClientError, BotoCoreError) as e:
            logger.warning("Failed to query incident history: %s", str(e))
            return []
