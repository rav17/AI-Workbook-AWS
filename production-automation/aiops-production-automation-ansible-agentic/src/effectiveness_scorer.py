"""Playbook Effectiveness Scoring — closes the MAPE-K feedback loop.

Tracks success/failure/ineffective outcomes per (alert_name, playbook_path)
pair and uses the score to:
1. Break ties in PlaybookMapper when multiple rules match
2. Route low-scoring playbooks to the AI agent instead of rule-based
3. Provide weekly health digests on declining playbooks

Score formula: effectiveness = successes / (successes + failures + ineffectives)

Storage: in-memory with periodic persistence to JSON file (can be swapped
for DynamoDB in production with the same interface).
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_SCORE = 0.5  # Cold-start: unknown playbooks get neutral score
LOW_SCORE_THRESHOLD = 0.3  # Below this → route to AI agent
PERSISTENCE_PATH = os.environ.get(
    "EFFECTIVENESS_STORE_PATH", "data/playbook_effectiveness.json"
)


@dataclass
class EffectivenessRecord:
    """Tracks outcomes for a single (alert, playbook) pair."""

    alert_name: str
    playbook_path: str
    successes: int = 0
    failures: int = 0
    ineffectives: int = 0
    last_updated: float = 0.0

    @property
    def total_executions(self) -> int:
        return self.successes + self.failures + self.ineffectives

    @property
    def score(self) -> float:
        """Effectiveness score (0.0 - 1.0). Returns DEFAULT_SCORE if no data."""
        total = self.total_executions
        if total == 0:
            return DEFAULT_SCORE
        return self.successes / total

    @property
    def is_low_score(self) -> bool:
        """Whether this playbook should be routed to AI instead."""
        return self.total_executions >= 3 and self.score < LOW_SCORE_THRESHOLD


@dataclass
class ScoringDecision:
    """Result of querying effectiveness for playbook selection."""

    score: float
    should_use_ai: bool = False
    reason: str = ""
    executions: int = 0


class EffectivenessScorer:
    """In-memory effectiveness scoring with JSON persistence.

    Thread-safe. Used by PlaybookMapper for tie-breaking and by the
    orchestrator to decide whether to route to AI agent.
    """

    def __init__(self, persistence_path: Optional[str] = None) -> None:
        self._lock = Lock()
        self._records: dict[str, EffectivenessRecord] = {}
        self._persistence_path = persistence_path or PERSISTENCE_PATH
        self._load()

    def _make_key(self, alert_name: str, playbook_path: str) -> str:
        """Create a composite key for the record store."""
        return f"{alert_name}##{playbook_path}"

    def get_score(self, alert_name: str, playbook_path: str) -> ScoringDecision:
        """Get effectiveness score for a (alert, playbook) pair.

        Args:
            alert_name: The alert being matched.
            playbook_path: The candidate playbook.

        Returns:
            ScoringDecision with score and AI routing recommendation.
        """
        key = self._make_key(alert_name, playbook_path)
        with self._lock:
            record = self._records.get(key)

        if record is None:
            return ScoringDecision(
                score=DEFAULT_SCORE,
                should_use_ai=False,
                reason="No historical data (cold start)",
                executions=0,
            )

        should_ai = record.is_low_score
        reason = ""
        if should_ai:
            reason = (
                f"Low effectiveness ({record.score:.2f}) after "
                f"{record.total_executions} executions — routing to AI"
            )

        return ScoringDecision(
            score=record.score,
            should_use_ai=should_ai,
            reason=reason,
            executions=record.total_executions,
        )

    def select_best_playbook(
        self, alert_name: str, candidates: list[str]
    ) -> Optional[str]:
        """Select the best playbook from candidates using effectiveness scores.

        Used for tie-breaking when multiple rules match with equal specificity.

        Args:
            alert_name: The alert being matched.
            candidates: List of playbook paths that all match.

        Returns:
            The playbook with highest effectiveness score, or None if empty.
        """
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        best_path = candidates[0]
        best_score = -1.0

        for path in candidates:
            decision = self.get_score(alert_name, path)
            if decision.score > best_score:
                best_score = decision.score
                best_path = path

        return best_path

    def record_success(self, alert_name: str, playbook_path: str) -> None:
        """Record a successful remediation outcome."""
        self._update(alert_name, playbook_path, "success")

    def record_failure(self, alert_name: str, playbook_path: str) -> None:
        """Record a failed remediation outcome."""
        self._update(alert_name, playbook_path, "failure")

    def record_ineffective(self, alert_name: str, playbook_path: str) -> None:
        """Record an ineffective outcome (baking period showed no improvement)."""
        self._update(alert_name, playbook_path, "ineffective")

    def get_all_scores(self) -> list[dict]:
        """Get all scores for reporting/health digest."""
        with self._lock:
            results = []
            for record in self._records.values():
                results.append({
                    "alert_name": record.alert_name,
                    "playbook_path": record.playbook_path,
                    "score": round(record.score, 3),
                    "successes": record.successes,
                    "failures": record.failures,
                    "ineffectives": record.ineffectives,
                    "total": record.total_executions,
                    "low_score": record.is_low_score,
                })
            return sorted(results, key=lambda x: x["score"])

    def get_low_scoring(self) -> list[dict]:
        """Get playbooks with effectiveness below threshold."""
        return [r for r in self.get_all_scores() if r["low_score"]]

    def persist(self) -> None:
        """Persist current scores to JSON file."""
        with self._lock:
            data = {}
            for key, record in self._records.items():
                data[key] = {
                    "alert_name": record.alert_name,
                    "playbook_path": record.playbook_path,
                    "successes": record.successes,
                    "failures": record.failures,
                    "ineffectives": record.ineffectives,
                    "last_updated": record.last_updated,
                }

        try:
            os.makedirs(os.path.dirname(self._persistence_path), exist_ok=True)
            with open(self._persistence_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("Effectiveness scores persisted (%d records)", len(data))
        except Exception as e:
            logger.warning("Failed to persist effectiveness scores: %s", e)

    def _update(self, alert_name: str, playbook_path: str, outcome: str) -> None:
        """Update a record with a new outcome."""
        key = self._make_key(alert_name, playbook_path)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                record = EffectivenessRecord(
                    alert_name=alert_name,
                    playbook_path=playbook_path,
                )
                self._records[key] = record

            if outcome == "success":
                record.successes += 1
            elif outcome == "failure":
                record.failures += 1
            elif outcome == "ineffective":
                record.ineffectives += 1

            record.last_updated = time.time()

    def _load(self) -> None:
        """Load persisted scores from JSON file."""
        if not os.path.isfile(self._persistence_path):
            return

        try:
            with open(self._persistence_path, "r") as f:
                data = json.load(f)

            for key, entry in data.items():
                self._records[key] = EffectivenessRecord(
                    alert_name=entry.get("alert_name", ""),
                    playbook_path=entry.get("playbook_path", ""),
                    successes=entry.get("successes", 0),
                    failures=entry.get("failures", 0),
                    ineffectives=entry.get("ineffectives", 0),
                    last_updated=entry.get("last_updated", 0),
                )
            logger.info(
                "Loaded %d effectiveness records from %s",
                len(self._records),
                self._persistence_path,
            )
        except Exception as e:
            logger.warning("Failed to load effectiveness scores: %s", e)
