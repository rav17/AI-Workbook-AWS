"""Configuration dataclasses for the Agentic AI system.

Contains AgentConfig and OrchestratorConfig with validation
for configurable ranges as specified in the design document.
"""

from dataclasses import dataclass, field

from src.agentic_ai.models.enums import OperatingMode


@dataclass
class AgentConfig:
    """Configuration for the AI Reasoning Agent.

    Attributes:
        model_id: Amazon Bedrock model identifier (required).
        max_input_tokens: Maximum input tokens per invocation (1000-16000, default 4000).
        max_output_tokens: Maximum output tokens per invocation (200-4000, default 1000).
        reasoning_timeout_seconds: Max seconds for AI reasoning (default 30).
        retry_count: Number of retries on Bedrock failure (default 2).
        retry_backoff_base_seconds: Base seconds for exponential backoff (default 1.0).
        escalation_threshold: Confidence below which escalation is triggered (0.1-0.9, default 0.5).
        p1_minimum_confidence: Minimum confidence for P1 alerts (default 0.8).
        correlation_window_seconds: Alert correlation window (30-900, default 300).
        history_retention_days: Days to retain incident history (7-365, default 90).
    """

    model_id: str
    max_input_tokens: int = 4000
    max_output_tokens: int = 1000
    reasoning_timeout_seconds: int = 30
    retry_count: int = 2
    retry_backoff_base_seconds: float = 1.0
    escalation_threshold: float = 0.5
    p1_minimum_confidence: float = 0.8
    correlation_window_seconds: int = 300
    history_retention_days: int = 90

    def __post_init__(self) -> None:
        """Validate configurable ranges after initialization."""
        if not self.model_id:
            raise ValueError("model_id must be a non-empty string")

        if not (1000 <= self.max_input_tokens <= 16000):
            raise ValueError(
                f"max_input_tokens must be between 1000 and 16000, "
                f"got {self.max_input_tokens}"
            )

        if not (200 <= self.max_output_tokens <= 4000):
            raise ValueError(
                f"max_output_tokens must be between 200 and 4000, "
                f"got {self.max_output_tokens}"
            )

        if not (0.1 <= self.escalation_threshold <= 0.9):
            raise ValueError(
                f"escalation_threshold must be between 0.1 and 0.9, "
                f"got {self.escalation_threshold}"
            )

        if not (30 <= self.correlation_window_seconds <= 900):
            raise ValueError(
                f"correlation_window_seconds must be between 30 and 900, "
                f"got {self.correlation_window_seconds}"
            )

        if not (7 <= self.history_retention_days <= 365):
            raise ValueError(
                f"history_retention_days must be between 7 and 365, "
                f"got {self.history_retention_days}"
            )


@dataclass
class OrchestratorConfig:
    """Configuration for the AWS Orchestrator.

    Attributes:
        operating_mode: System operating mode (default RULES_ONLY).
        sqs_queue_url: URL of the SQS main queue.
        sqs_visibility_timeout: SQS visibility timeout in seconds (default 60).
        escalation_timeout_minutes: Minutes before escalation times out (5-120, default 30).
        health_check_interval_seconds: Interval for health checks (default 30).
        redaction_patterns: Patterns to redact from stored data.
    """

    operating_mode: OperatingMode = OperatingMode.RULES_ONLY
    sqs_queue_url: str = ""
    sqs_visibility_timeout: int = 60
    escalation_timeout_minutes: int = 30
    health_check_interval_seconds: int = 30
    redaction_patterns: list[str] = field(
        default_factory=lambda: ["password", "secret", "token", "key"]
    )

    def __post_init__(self) -> None:
        """Validate configurable ranges after initialization."""
        if not (5 <= self.escalation_timeout_minutes <= 120):
            raise ValueError(
                f"escalation_timeout_minutes must be between 5 and 120, "
                f"got {self.escalation_timeout_minutes}"
            )
