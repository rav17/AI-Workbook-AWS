"""DynamoDB short-term memory manager. Traces: R9, R11."""
from __future__ import annotations

import boto3
from boto3.dynamodb.conditions import Key

from config.models import InteractionRecord, PruneEvent
from config.settings import MemoryConfig
from observability.logger import CorrelatedLogger

logger = CorrelatedLogger()


class DynamoDBShortTermMemory:
    """Manages short-term memory in DynamoDB.

    Uses *user_id* as partition key and *timestamp* as sort key.
    Traces: R9, R11.
    """

    def __init__(self, config: MemoryConfig, table_name: str = "smartbanker_stm"):
        self.max_interactions: int = config.max_interactions  # default 20
        self.table_name = table_name
        self.dynamodb = boto3.resource("dynamodb", region_name=config.aws_region)
        self.table = self.dynamodb.Table(table_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store_interaction(self, user_id: str, record: InteractionRecord) -> None:
        """Store an interaction record to DynamoDB.

        Before writing, checks for duplicates (R9.5) and after writing
        prunes excess records (R9.2, R9.3, R9.4).
        Traces: R9.1, R9.2, R9.5.
        """
        # Remove any existing duplicate (R9.5) — the new record replaces it
        self.deduplicate(user_id, record)

        self.table.put_item(Item=record.model_dump())
        self.prune(user_id)

    def retrieve_interactions(
        self, user_id: str, limit: int | None = None
    ) -> list[InteractionRecord]:
        """Retrieve recent interactions ordered by timestamp (newest first).

        Traces: R9.1.
        """
        query_kwargs: dict = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
            "ScanIndexForward": False,  # newest first
        }
        effective_limit = limit if limit is not None else self.max_interactions
        query_kwargs["Limit"] = effective_limit

        resp = self.table.query(**query_kwargs)
        return [InteractionRecord(**item) for item in resp.get("Items", [])]

    def get_failures(
        self, user_id: str, limit: int | None = None
    ) -> list[InteractionRecord]:
        """Retrieve failed interactions from STM, ordered by recency.

        Traces: R9.4.
        """
        all_records = self.retrieve_interactions(user_id, limit=self.max_interactions)
        failures = [r for r in all_records if r.status == "failure"]
        if limit is not None:
            failures = failures[:limit]
        return failures

    def prune(self, user_id: str) -> list[PruneEvent]:
        """Remove oldest non-failure, non-low-confidence records when exceeding
        ``max_interactions``.

        Pruning priority (removed first → last):
        1. Oldest *successful, high-confidence* records
        2. Oldest *successful, medium-confidence* records
        3. Oldest *low-confidence* records (retained longer per R9.4)
        4. *Failed* records are never pruned (R9.3)

        Returns a list of :class:`PruneEvent` for each removed record.
        Traces: R9.2, R9.3, R9.4, R14.1.
        """
        # Fetch slightly more than max to find candidates
        records = self.retrieve_interactions(user_id, limit=self.max_interactions + 50)

        if len(records) <= self.max_interactions:
            return []

        excess = len(records) - self.max_interactions

        # Sort oldest-first for pruning candidates
        sorted_records = sorted(records, key=lambda r: r.timestamp)

        # Partition into priority buckets (lower bucket index = pruned first)
        buckets: list[list[InteractionRecord]] = [[], [], []]
        for r in sorted_records:
            if r.status == "failure":
                continue  # never prune failures
            if r.confidence == "low":
                buckets[2].append(r)  # pruned last among non-failures
            elif r.confidence == "medium":
                buckets[1].append(r)
            else:
                buckets[0].append(r)  # high-confidence pruned first

        to_remove: list[InteractionRecord] = []
        for bucket in buckets:
            for r in bucket:
                if len(to_remove) >= excess:
                    break
                to_remove.append(r)
            if len(to_remove) >= excess:
                break

        prune_events: list[PruneEvent] = []
        for r in to_remove:
            self.table.delete_item(
                Key={"user_id": r.user_id, "timestamp": r.timestamp}
            )
            event = PruneEvent(
                user_id=r.user_id,
                pruned_timestamp=r.timestamp,
                reason="exceeded_max_interactions",
            )
            prune_events.append(event)
            logger.log_memory_prune(r.user_id, r.timestamp, event.reason)

        return prune_events

    def deduplicate(self, user_id: str, record: InteractionRecord) -> bool:
        """Check for and remove duplicate entries based on matching input AND
        output content.

        Returns ``True`` if a duplicate was found (and removed), ``False``
        otherwise.
        Traces: R9.5.
        """
        recent = self.retrieve_interactions(user_id, limit=10)
        for existing in recent:
            if existing.input == record.input and existing.output == record.output:
                # Remove the older duplicate
                self.table.delete_item(
                    Key={
                        "user_id": existing.user_id,
                        "timestamp": existing.timestamp,
                    }
                )
                return True
        return False
