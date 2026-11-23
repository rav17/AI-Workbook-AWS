"""Thin DynamoDB wrapper for workflow state with TTL and conditional updates."""

import time
from typing import Any


class DynamoDBStateManager:
    """Shared wrapper for DynamoDB state operations.

    Each agent instantiates with its own table name and key schema.
    Handles TTL calculation, conditional updates, and boto3 boilerplate.
    """

    def __init__(self, dynamodb_resource: Any, table_name: str, ttl_days: int = 90):
        self._table = dynamodb_resource.Table(table_name)
        self._ttl_days = ttl_days

    def _ttl_epoch(self) -> int:
        return int(time.time()) + (self._ttl_days * 86400)

    def get_state(self, team_id: str, work_order_id: str) -> dict[str, Any] | None:
        """Retrieve workflow state by composite key."""
        response = self._table.get_item(
            Key={"team_id": team_id, "work_order_id": work_order_id}
        )
        return response.get("Item")

    def put_state(self, item: dict[str, Any]) -> bool:
        """Write a new workflow state item with automatic TTL."""
        item["ttl_epoch"] = self._ttl_epoch()
        self._table.put_item(Item=item)
        return True

    def update_state(
        self,
        team_id: str,
        work_order_id: str,
        updates: dict[str, Any],
        condition_expression: str | None = None,
    ) -> bool:
        """Conditional update for concurrency safety.

        Builds an UpdateExpression from the updates dict.
        """
        expr_parts: list[str] = []
        attr_names: dict[str, str] = {}
        attr_values: dict[str, Any] = {}

        updates["ttl_epoch"] = self._ttl_epoch()

        for i, (key, val) in enumerate(updates.items()):
            placeholder_name = f"#k{i}"
            placeholder_val = f":v{i}"
            expr_parts.append(f"{placeholder_name} = {placeholder_val}")
            attr_names[placeholder_name] = key
            attr_values[placeholder_val] = val

        update_expr = "SET " + ", ".join(expr_parts)

        kwargs: dict[str, Any] = {
            "Key": {"team_id": team_id, "work_order_id": work_order_id},
            "UpdateExpression": update_expr,
            "ExpressionAttributeNames": attr_names,
            "ExpressionAttributeValues": attr_values,
        }
        if condition_expression:
            kwargs["ConditionExpression"] = condition_expression

        self._table.update_item(**kwargs)
        return True

    def query_by_team(self, team_id: str) -> list[dict[str, Any]]:
        """Get all workflow states for a given team."""
        response = self._table.query(
            KeyConditionExpression="team_id = :tid",
            ExpressionAttributeValues={":tid": team_id},
        )
        return response.get("Items", [])
