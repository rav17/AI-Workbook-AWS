"""In-memory stand-in for the low-level DynamoDB client, for unit tests.

It enforces the real ``AiopsIncidentMemory`` key schema from ``data_stack.py``:
partition key ``incident_id`` (S), sort key ``timestamp`` (S), and the GSIs
``AlertNameIndex`` (alert_name/timestamp), ``ServiceIndex`` (service_name/timestamp)
and ``OutcomeIndex`` (outcome/timestamp). Writes or queries that do not match the
schema raise ``ValidationException`` the way DynamoDB does, so a schema mismatch in
the store code fails the tests instead of passing silently.

Only the expression forms used by ``IncidentMemoryStore`` are supported.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Optional

from botocore.exceptions import ClientError

TABLE_KEYS = ("incident_id", "timestamp")
GSIS = {
    "AlertNameIndex": ("alert_name", "timestamp"),
    "ServiceIndex": ("service_name", "timestamp"),
    "OutcomeIndex": ("outcome", "timestamp"),
}


def _error(code: str, message: str, op: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, op)


class FakeDynamoDBClient:
    """Subset of ``boto3.client("dynamodb")`` backed by a dict."""

    def __init__(self, table_name: str = "AiopsIncidentMemory-test") -> None:
        self.table_name = table_name
        self.items: dict[tuple[str, str], dict[str, Any]] = {}
        self.calls: list[str] = []

    # --- helpers -------------------------------------------------------

    def _check_table(self, name: str, op: str) -> None:
        if name != self.table_name:
            raise _error("ResourceNotFoundException", f"Table {name} not found", op)

    @staticmethod
    def _key_of(item: dict[str, Any], op: str) -> tuple[str, str]:
        try:
            return item["incident_id"]["S"], item["timestamp"]["S"]
        except (KeyError, TypeError) as e:
            raise _error(
                "ValidationException",
                "The provided key element does not match the schema",
                op,
            ) from e

    @staticmethod
    def _check_index_keys(item: dict[str, Any], op: str) -> None:
        for pk, sk in GSIS.values():
            for attr in (pk, sk):
                if attr in item:
                    value = item[attr]
                    if "S" not in value:
                        raise _error(
                            "ValidationException",
                            f"Type mismatch for Index Key {attr}",
                            op,
                        )
                    if value["S"] == "":
                        raise _error(
                            "ValidationException",
                            f"Index key {attr} cannot be an empty string",
                            op,
                        )

    @staticmethod
    def _sub(expr: str, names: Optional[dict[str, str]]) -> str:
        for alias, real in (names or {}).items():
            expr = expr.replace(alias, real)
        return expr

    @staticmethod
    def _matches(item: dict[str, Any], clause: str, values: dict[str, Any]) -> bool:
        clause = clause.strip()
        m = re.fullmatch(r"begins_with\((\w+),\s*(:\w+)\)", clause)
        if m:
            return (
                item.get(m.group(1), {})
                .get("S", "")
                .startswith(values[m.group(2)]["S"])
            )
        m = re.fullmatch(r"attribute_exists\((\w+)\)", clause)
        if m:
            return m.group(1) in item
        m = re.fullmatch(r"attribute_not_exists\((\w+)\)", clause)
        if m:
            return m.group(1) not in item
        m = re.fullmatch(r"(\w+)\s*=\s*(:\w+)", clause)
        if m:
            return item.get(m.group(1)) == values[m.group(2)]
        raise NotImplementedError(f"Unsupported expression: {clause}")

    def _all(self, item: dict[str, Any], expr: str, values: dict[str, Any]) -> bool:
        return all(self._matches(item, part, values) for part in expr.split(" AND "))

    # --- API -----------------------------------------------------------

    def put_item(
        self, TableName: str, Item: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        """Store an item after validating keys and index keys."""
        self.calls.append("put_item")
        self._check_table(TableName, "PutItem")
        key = self._key_of(Item, "PutItem")
        self._check_index_keys(Item, "PutItem")
        self.items[key] = copy.deepcopy(Item)
        return {}

    def query(
        self,
        TableName: str,
        KeyConditionExpression: str,
        ExpressionAttributeValues: dict[str, Any],
        ExpressionAttributeNames: Optional[dict[str, str]] = None,
        IndexName: Optional[str] = None,
        ScanIndexForward: bool = True,
        Limit: Optional[int] = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Query the table or a GSI; the partition attribute must match the key schema."""
        self.calls.append(f"query:{IndexName or 'table'}")
        self._check_table(TableName, "Query")
        if IndexName is None:
            pk_name, sk_name = TABLE_KEYS
        elif IndexName in GSIS:
            pk_name, sk_name = GSIS[IndexName]
        else:
            raise _error("ValidationException", f"Unknown index {IndexName}", "Query")

        expr = self._sub(KeyConditionExpression, ExpressionAttributeNames)
        parts = [p.strip() for p in expr.split(" AND ")]
        m = re.fullmatch(r"(\w+)\s*=\s*(:\w+)", parts[0])
        if not m or m.group(1) != pk_name:
            raise _error(
                "ValidationException",
                "Query condition missed key schema element",
                "Query",
            )
        for extra in parts[1:]:
            attr = re.search(r"\((\w+),", extra) or re.match(r"(\w+)", extra)
            if attr is None or attr.group(1) != sk_name:
                raise _error(
                    "ValidationException",
                    "Query key condition not supported",
                    "Query",
                )

        found = [
            copy.deepcopy(item)
            for item in self.items.values()
            if pk_name in item
            and sk_name in item  # GSIs are sparse
            and self._all(item, expr, ExpressionAttributeValues)
        ]
        found.sort(key=lambda i: i[sk_name]["S"], reverse=not ScanIndexForward)
        if Limit is not None:
            found = found[:Limit]
        return {"Items": found, "Count": len(found)}

    def update_item(
        self,
        TableName: str,
        Key: dict[str, Any],
        UpdateExpression: str,
        ExpressionAttributeValues: dict[str, Any],
        ExpressionAttributeNames: Optional[dict[str, str]] = None,
        ConditionExpression: Optional[str] = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Apply a ``SET a = :v, ...`` update, honouring an optional condition."""
        self.calls.append("update_item")
        self._check_table(TableName, "UpdateItem")
        if set(Key) != set(TABLE_KEYS):
            raise _error(
                "ValidationException",
                "The provided key element does not match the schema",
                "UpdateItem",
            )
        key = self._key_of(Key, "UpdateItem")
        item = self.items.get(key)
        if ConditionExpression:
            cond = self._sub(ConditionExpression, ExpressionAttributeNames)
            if item is None or not self._all(item, cond, ExpressionAttributeValues):
                raise _error(
                    "ConditionalCheckFailedException",
                    "The conditional request failed",
                    "UpdateItem",
                )
        if item is None:  # DynamoDB upserts when there is no condition
            item = copy.deepcopy(Key)
            self.items[key] = item
        update = self._sub(UpdateExpression, ExpressionAttributeNames)
        if not update.startswith("SET "):
            raise NotImplementedError(update)
        for assignment in update[4:].split(","):
            attr, value = (s.strip() for s in assignment.split("="))
            item[attr] = copy.deepcopy(ExpressionAttributeValues[value])
        self._check_index_keys(item, "UpdateItem")
        return {}

    def scan(
        self,
        TableName: str,
        FilterExpression: str,
        ExpressionAttributeValues: dict[str, Any],
        ExpressionAttributeNames: Optional[dict[str, str]] = None,
        Limit: Optional[int] = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Scan with a filter (Limit applies before filtering, as in DynamoDB)."""
        self.calls.append("scan")
        self._check_table(TableName, "Scan")
        expr = self._sub(FilterExpression, ExpressionAttributeNames)
        candidates = list(self.items.values())
        if Limit is not None:
            candidates = candidates[:Limit]
        found = [
            copy.deepcopy(i)
            for i in candidates
            if self._all(i, expr, ExpressionAttributeValues)
        ]
        return {"Items": found, "Count": len(found)}
