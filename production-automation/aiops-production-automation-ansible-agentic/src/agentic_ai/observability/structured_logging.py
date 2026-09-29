"""Structured JSON logging for the AIOps system.

Emits single-line JSON log entries to stdout/stderr with all required fields.
Implements secret redaction to ensure no raw credentials appear in logs.

Required fields on every log entry:
  - timestamp (ISO 8601)
  - level (INFO/WARN/ERROR)
  - incident_id
  - pipeline_stage
  - duration_ms
  - outcome
  - environment

Requirements: 9.6
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any


# Secret redaction patterns — match common secret formats
SECRET_PATTERNS: list[re.Pattern[str]] = [
    # Slack webhook URLs
    re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/+_-]+", re.IGNORECASE),
    # Generic API keys (alphanumeric strings of 20+ chars often prefixed with key identifiers)
    re.compile(r"(?:api[_-]?key|apikey|api_token)[\"'\s:=]+[A-Za-z0-9_\-]{16,}", re.IGNORECASE),
    # Bearer tokens
    re.compile(r"Bearer\s+[A-Za-z0-9_\-.~+/]+=*", re.IGNORECASE),
    # AWS secret access keys (40 char base64-like)
    re.compile(r"(?:aws[_-]?secret[_-]?access[_-]?key|secret_access_key)[\"'\s:=]+[A-Za-z0-9/+=]{40}", re.IGNORECASE),
    # Generic token patterns (token= or token: followed by long alphanumeric)
    re.compile(r"(?:token|secret|password|passwd|credential)[\"'\s:=]+[^\s\"',}{]{8,}", re.IGNORECASE),
    # PagerDuty routing keys (32 hex chars)
    re.compile(r"(?:pagerduty[_-]?routing[_-]?key|routing_key)[\"'\s:=]+[a-f0-9]{32}", re.IGNORECASE),
]

REDACTED = "***REDACTED***"


def redact_secrets(message: str) -> str:
    """Redact secret values from a log message.

    Scans the message against known secret patterns and replaces
    matched values with a redaction placeholder.

    Args:
        message: The raw log message string.

    Returns:
        The message with secret values replaced by REDACTED.
    """
    result = message
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


class JSONFormatter(logging.Formatter):
    """Custom logging formatter that outputs single-line JSON objects.

    Every log entry contains the 7 required fields as specified by
    Requirement 9.6. Fields not explicitly provided in the log record
    default to empty string to ensure they are always present.
    """

    def __init__(self, environment: str = "dev") -> None:
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a single-line JSON object.

        Args:
            record: The logging.LogRecord to format.

        Returns:
            A single-line JSON string with all required fields.
        """
        # Build the base message (apply formatting if args present)
        message = record.getMessage()

        # Apply secret redaction to the message
        message = redact_secrets(message)

        # Extract extra fields from the record, with defaults
        incident_id = getattr(record, "incident_id", "") or ""
        pipeline_stage = getattr(record, "pipeline_stage", "") or ""
        duration_ms = getattr(record, "duration_ms", None)
        outcome = getattr(record, "outcome", "") or ""

        # Ensure duration_ms is numeric or None
        if duration_ms is not None:
            try:
                duration_ms = float(duration_ms)
            except (TypeError, ValueError):
                duration_ms = None

        # Build the structured log entry
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "incident_id": incident_id,
            "pipeline_stage": pipeline_stage,
            "duration_ms": duration_ms,
            "outcome": outcome,
            "environment": self.environment,
            "message": message,
            "logger": record.name,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Output as single-line JSON
        return json.dumps(log_entry, default=str, ensure_ascii=False)


def configure_logging(environment: str, level: int = logging.INFO) -> None:
    """Configure the root logger for structured JSON output.

    Sets up the root logger with the JSONFormatter so all log output
    from the application is emitted as single-line JSON objects with
    the required fields.

    Args:
        environment: The deployment environment (dev, staging, prod).
        level: The logging level (default: INFO).
    """
    root_logger = logging.getLogger()

    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    # Create a StreamHandler (stdout) with the JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter(environment=environment))
    handler.setLevel(level)

    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger for use in application modules.

    The returned logger inherits the JSON formatting from the root
    logger configured by configure_logging().

    Args:
        name: The logger name (typically __name__).

    Returns:
        A configured logging.Logger instance.
    """
    return logging.getLogger(name)


class LogContext:
    """Context manager for structured log fields.

    Provides a convenient way to log with the required structured fields
    (incident_id, pipeline_stage, duration_ms, outcome) attached to each
    log record via the `extra` parameter.

    Usage:
        ctx = LogContext(
            logger=logger,
            incident_id="INC-12345",
            pipeline_stage="enrichment",
        )
        ctx.info("Processing started")
        ctx.info("Processing complete", duration_ms=150.0, outcome="success")
    """

    def __init__(
        self,
        logger: logging.Logger,
        incident_id: str = "",
        pipeline_stage: str = "",
    ) -> None:
        self.logger = logger
        self.incident_id = incident_id
        self.pipeline_stage = pipeline_stage

    def _extra(self, **kwargs: Any) -> dict[str, Any]:
        """Build the extra dict for structured log fields."""
        return {
            "incident_id": kwargs.get("incident_id", self.incident_id),
            "pipeline_stage": kwargs.get("pipeline_stage", self.pipeline_stage),
            "duration_ms": kwargs.get("duration_ms"),
            "outcome": kwargs.get("outcome", ""),
        }

    def info(self, message: str, **kwargs: Any) -> None:
        """Log at INFO level with structured fields."""
        self.logger.info(message, extra=self._extra(**kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log at WARNING level with structured fields."""
        self.logger.warning(message, extra=self._extra(**kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        """Log at ERROR level with structured fields."""
        self.logger.error(message, extra=self._extra(**kwargs))

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log at DEBUG level with structured fields."""
        self.logger.debug(message, extra=self._extra(**kwargs))
