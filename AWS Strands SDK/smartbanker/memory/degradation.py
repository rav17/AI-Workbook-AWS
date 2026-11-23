"""Memory degradation control — filters memory before LLM context. Traces: R11."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Union

from config.models import InteractionRecord, MemoryContext, SimilarPattern
from config.settings import MemoryConfig


class MemoryDegradationControl:
    """Filters memory before sending to LLM to preserve context window efficiency.

    Ensures the system NEVER sends full interaction history to the LLM (R11.5).
    Instead, it retrieves only the last N failures from STM and top K similar
    patterns from LTM, filters by intent, deduplicates, and excludes outdated
    records.

    Traces: R11.
    """

    def __init__(self, config: MemoryConfig) -> None:
        self.max_failures = config.max_failures_in_context  # from STM (R11.1)
        self.max_patterns = config.max_patterns_in_context  # from LTM (R11.1)
        self.max_age_days = config.max_context_age_days

    def prepare_context(
        self,
        failures: list[InteractionRecord],
        patterns: list[SimilarPattern],
        current_intent: str,
    ) -> MemoryContext:
        """Filter, deduplicate, and assemble relevant memory context.

        Pipeline: filter by intent → exclude outdated → remove duplicates → cap to N.
        Never returns more than max_failures failures or max_patterns patterns (R11.5).

        Traces: R11.1, R11.5.
        """
        filtered_failures = self.filter_by_intent(failures, current_intent)
        filtered_failures = self.exclude_outdated(filtered_failures)
        filtered_failures = self.remove_duplicates(filtered_failures)
        # R11.1: only last N failures
        filtered_failures = filtered_failures[: self.max_failures]

        # Filter patterns by intent relevance, then cap to K (R11.1)
        filtered_patterns = [
            p for p in patterns if self._pattern_matches_intent(p, current_intent)
        ]
        filtered_patterns = filtered_patterns[: self.max_patterns]

        return MemoryContext(
            failures=filtered_failures,
            patterns=filtered_patterns,
            intent=current_intent,
        )

    def filter_by_intent(
        self,
        records: list[InteractionRecord],
        intent: str,
    ) -> list[InteractionRecord]:
        """Remove records not relevant to current intent.

        A record is considered relevant if:
        - No intent filter is provided (empty string keeps all records).
        - The record has no intent set (assumed broadly relevant).
        - The record's intent matches the current intent exactly.
        - The record's worker_domain is contained in the intent string
          (e.g. intent "investment_advice" matches worker_domain "investment").

        Traces: R11.2.
        """
        if not intent:
            return list(records)

        intent_lower = intent.lower()
        relevant: list[InteractionRecord] = []
        for r in records:
            if not r.intent:
                # Records without an intent tag are kept (broadly relevant)
                relevant.append(r)
            elif r.intent.lower() == intent_lower:
                relevant.append(r)
            elif r.worker_domain and r.worker_domain.lower() in intent_lower:
                relevant.append(r)
            elif r.worker_domain and intent_lower in r.worker_domain.lower():
                relevant.append(r)
        return relevant

    def remove_duplicates(
        self,
        records: list[InteractionRecord],
    ) -> list[InteractionRecord]:
        """Deduplicate failure records based on input+output content.

        Preserves the first occurrence of each unique (input, output) pair.

        Traces: R11.3.
        """
        seen: set[str] = set()
        unique: list[InteractionRecord] = []
        for r in records:
            key = f"{r.input}|{r.output}"
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def exclude_outdated(
        self,
        records: list[InteractionRecord],
    ) -> list[InteractionRecord]:
        """Remove records older than the configured age threshold.

        Traces: R11.4.
        """
        cutoff = (datetime.utcnow() - timedelta(days=self.max_age_days)).isoformat()
        return [r for r in records if r.timestamp >= cutoff]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pattern_matches_intent(pattern: SimilarPattern, intent: str) -> bool:
        """Check whether a pattern is relevant to the current intent.

        A pattern matches if:
        - No intent filter is provided.
        - The pattern metadata contains a matching intent.
        - The pattern has a high similarity score (> 0.7), indicating
          strong semantic relevance regardless of intent tag.
        """
        if not intent:
            return True
        metadata = pattern.metadata or {}
        pattern_intent = metadata.get("intent", "")
        if pattern_intent and pattern_intent.lower() == intent.lower():
            return True
        return pattern.similarity_score > 0.7
