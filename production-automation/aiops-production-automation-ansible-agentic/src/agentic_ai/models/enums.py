"""Enums for the Agentic AI system.

Defines operating modes, escalation statuses, and fallback reasons
used throughout the AI-powered remediation pipeline.
"""

from enum import Enum


class OperatingMode(Enum):
    """System operating mode controlling AI vs rule-based behavior.

    - AI_ONLY: AI reasoning only, no rule-based fallback
    - RULES_ONLY: Rule-based matching only, AI agent bypassed
    - AI_WITH_FALLBACK: AI reasoning with rule-based fallback on failure
    """

    AI_ONLY = "ai_only"
    RULES_ONLY = "rules_only"
    AI_WITH_FALLBACK = "ai_with_fallback"


class EscalationStatus(Enum):
    """Escalation lifecycle status tracking human response workflow.

    - PENDING: Awaiting human response
    - APPROVED: Human approved AI-suggested remediation
    - REJECTED: Human rejected the suggestion
    - TIMED_OUT_EXECUTED: Timeout expired, AI remediation auto-executed (confidence > 0.3)
    - TIMED_OUT_UNRESOLVED: Timeout expired, marked unresolved (confidence <= 0.3)
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT_EXECUTED = "timed_out_executed"
    TIMED_OUT_UNRESOLVED = "timed_out_unresolved"


class FallbackReason(Enum):
    """Reason for falling back to rule-based matching.

    - THROTTLING: Bedrock API throttling
    - TIMEOUT: General timeout (e.g., network)
    - SERVICE_ERROR: Bedrock service error
    - REASONING_TIMEOUT: AI reasoning exceeded 30-second limit
    """

    THROTTLING = "throttling"
    TIMEOUT = "timeout"
    SERVICE_ERROR = "service_error"
    REASONING_TIMEOUT = "reasoning_timeout"
