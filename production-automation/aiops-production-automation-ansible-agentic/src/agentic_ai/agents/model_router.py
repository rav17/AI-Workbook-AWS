"""Intelligent Model Router — routes alerts to cost-optimal models.

Classifies alert complexity and routes to the appropriate Bedrock model:
- SIMPLE (70% of alerts): Nova Lite (~$0.0003/invocation)
- MODERATE (20%): Nova Pro (~$0.001/invocation)
- COMPLEX (10%): Claude Sonnet (~$0.003/invocation)

If the cheaper model produces confidence < 0.5, auto-escalates to
the next-tier model (within the same invocation flow).

Cost reduction: 60-90% compared to always using Claude Sonnet.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AlertComplexity(Enum):
    """Classification of alert complexity for model routing."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class RoutingDecision:
    """Result of model routing decision."""

    complexity: AlertComplexity
    model_id: str
    reason: str
    allow_escalation: bool = True


# Model IDs mapped to complexity tiers
MODEL_TIERS = {
    AlertComplexity.SIMPLE: "amazon.nova-lite-v1:0",
    AlertComplexity.MODERATE: "amazon.nova-pro-v1:0",
    AlertComplexity.COMPLEX: "anthropic.claude-3-sonnet-20240229-v1:0",
}

# Escalation path: SIMPLE → MODERATE → COMPLEX
ESCALATION_PATH = [
    AlertComplexity.SIMPLE,
    AlertComplexity.MODERATE,
    AlertComplexity.COMPLEX,
]


class ModelRouter:
    """Routes alerts to cost-optimal Bedrock models based on complexity.

    Classification criteria:
    - SIMPLE: Seen 5+ times, effectiveness > 90%, single host, P3/P4/P5
    - MODERATE: Seen before with mixed outcomes, 2-3 correlation group, P2
    - COMPLEX: Never seen, 4+ correlated, P1, past failures

    Thread-safe: uses no mutable shared state (classification is pure function
    of input parameters).
    """

    def __init__(
        self,
        simple_model: Optional[str] = None,
        moderate_model: Optional[str] = None,
        complex_model: Optional[str] = None,
    ) -> None:
        """Initialize with configurable model IDs.

        Falls back to defaults if not provided. Can be overridden via
        environment variables MODEL_SIMPLE, MODEL_MODERATE, MODEL_COMPLEX.
        """
        self._models = {
            AlertComplexity.SIMPLE: (
                simple_model
                or os.environ.get("MODEL_SIMPLE", MODEL_TIERS[AlertComplexity.SIMPLE])
            ),
            AlertComplexity.MODERATE: (
                moderate_model
                or os.environ.get("MODEL_MODERATE", MODEL_TIERS[AlertComplexity.MODERATE])
            ),
            AlertComplexity.COMPLEX: (
                complex_model
                or os.environ.get("MODEL_COMPLEX", MODEL_TIERS[AlertComplexity.COMPLEX])
            ),
        }

        self._enabled = os.environ.get(
            "MODEL_ROUTING_ENABLED", "true"
        ).lower() in ("true", "1", "yes")

    @property
    def enabled(self) -> bool:
        """Whether intelligent routing is enabled."""
        return self._enabled

    def classify(
        self,
        alert_name: str,
        severity: str,
        historical_count: int = 0,
        historical_success_rate: float = 0.5,
        correlation_group_size: int = 1,
        all_past_failed: bool = False,
    ) -> RoutingDecision:
        """Classify alert complexity and select optimal model.

        Args:
            alert_name: The alert name.
            severity: Alert severity (P1-P5).
            historical_count: How many times this alert has been seen.
            historical_success_rate: Success rate for past remediations (0.0-1.0).
            correlation_group_size: Number of alerts in the correlation group.
            all_past_failed: Whether all past remediation attempts have failed.

        Returns:
            RoutingDecision with model selection and reasoning.
        """
        if not self._enabled:
            # Routing disabled — always use complex model (safe fallback)
            return RoutingDecision(
                complexity=AlertComplexity.COMPLEX,
                model_id=self._models[AlertComplexity.COMPLEX],
                reason="Model routing disabled — using default model",
                allow_escalation=False,
            )

        # Rule 1: COMPLEX — never seen, P1, all past failed, large correlation
        if severity == "P1":
            return RoutingDecision(
                complexity=AlertComplexity.COMPLEX,
                model_id=self._models[AlertComplexity.COMPLEX],
                reason="P1 severity always uses most capable model",
                allow_escalation=False,
            )

        if all_past_failed:
            return RoutingDecision(
                complexity=AlertComplexity.COMPLEX,
                model_id=self._models[AlertComplexity.COMPLEX],
                reason="All past remediation attempts failed — needs deep analysis",
                allow_escalation=False,
            )

        if historical_count == 0:
            return RoutingDecision(
                complexity=AlertComplexity.COMPLEX,
                model_id=self._models[AlertComplexity.COMPLEX],
                reason="Never-seen alert requires full reasoning",
                allow_escalation=False,
            )

        if correlation_group_size >= 4:
            return RoutingDecision(
                complexity=AlertComplexity.COMPLEX,
                model_id=self._models[AlertComplexity.COMPLEX],
                reason=f"Large correlation group ({correlation_group_size} alerts)",
                allow_escalation=False,
            )

        # Rule 2: SIMPLE — well-known, high success rate, low severity
        if (
            historical_count >= 5
            and historical_success_rate >= 0.9
            and correlation_group_size == 1
            and severity in ("P3", "P4", "P5")
        ):
            return RoutingDecision(
                complexity=AlertComplexity.SIMPLE,
                model_id=self._models[AlertComplexity.SIMPLE],
                reason=(
                    f"Well-known alert (seen {historical_count}x, "
                    f"{historical_success_rate:.0%} success rate, {severity})"
                ),
                allow_escalation=True,
            )

        # Rule 3: MODERATE — everything else
        reason_parts = []
        if historical_count < 5:
            reason_parts.append(f"limited history ({historical_count} occurrences)")
        if historical_success_rate < 0.9:
            reason_parts.append(f"mixed outcomes ({historical_success_rate:.0%} success)")
        if correlation_group_size > 1:
            reason_parts.append(f"correlated ({correlation_group_size} alerts)")
        if severity == "P2":
            reason_parts.append("P2 severity")

        return RoutingDecision(
            complexity=AlertComplexity.MODERATE,
            model_id=self._models[AlertComplexity.MODERATE],
            reason=f"Moderate complexity: {', '.join(reason_parts) or 'default tier'}",
            allow_escalation=True,
        )

    def get_escalation_model(self, current_complexity: AlertComplexity) -> Optional[str]:
        """Get the next-tier model for escalation when confidence is low.

        Args:
            current_complexity: The current complexity tier.

        Returns:
            Model ID for the next tier, or None if already at max.
        """
        current_idx = ESCALATION_PATH.index(current_complexity)
        if current_idx >= len(ESCALATION_PATH) - 1:
            return None  # Already at highest tier
        next_complexity = ESCALATION_PATH[current_idx + 1]
        return self._models[next_complexity]
