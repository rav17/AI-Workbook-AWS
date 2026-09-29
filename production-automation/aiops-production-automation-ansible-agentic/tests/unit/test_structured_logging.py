"""Unit tests for structured JSON logging module.

Verifies:
- JSON output format with all 7 required fields
- Secret redaction patterns
- configure_logging sets up the root logger correctly
- LogContext helper attaches structured fields
"""

import json
import logging

from src.agentic_ai.observability.structured_logging import (
    JSONFormatter,
    LogContext,
    REDACTED,
    configure_logging,
    get_logger,
    redact_secrets,
)


REQUIRED_FIELDS = [
    "timestamp",
    "level",
    "incident_id",
    "pipeline_stage",
    "duration_ms",
    "outcome",
    "environment",
]


class TestJSONFormatter:
    """Tests for JSONFormatter output."""

    def setup_method(self):
        """Create a fresh formatter for each test."""
        self.formatter = JSONFormatter(environment="prod")

    def test_output_is_valid_json(self):
        """Log output should be a valid JSON string."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Hello world",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_output_is_single_line(self):
        """Log output should be a single line (no embedded newlines in JSON)."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Multi\nline\nmessage",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        # The JSON itself should be one line (no unescaped newlines)
        assert "\n" not in output

    def test_all_required_fields_present(self):
        """All 7 required fields must be present in every log entry."""
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="Test message",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)

        for field in REQUIRED_FIELDS:
            assert field in parsed, f"Missing required field: {field}"

    def test_required_fields_not_none(self):
        """Required fields should not be None (except duration_ms which can be null)."""
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Error occurred",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)

        # All fields except duration_ms must be non-None
        for field in REQUIRED_FIELDS:
            if field == "duration_ms":
                continue  # duration_ms can be null when not applicable
            assert parsed[field] is not None, f"Field {field} should not be None"

    def test_environment_from_formatter(self):
        """Environment field should come from the formatter configuration."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert parsed["environment"] == "prod"

    def test_level_field_matches_log_level(self):
        """Level field should match the Python log level name."""
        for level, name in [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
        ]:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="",
                lineno=0,
                msg="Test",
                args=None,
                exc_info=None,
            )
            output = self.formatter.format(record)
            parsed = json.loads(output)
            assert parsed["level"] == name

    def test_timestamp_is_iso8601(self):
        """Timestamp field should be a valid ISO 8601 string."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        # Should parse without error; ISO 8601 with timezone info
        from datetime import datetime

        dt = datetime.fromisoformat(parsed["timestamp"])
        assert dt.tzinfo is not None  # Should have timezone

    def test_extra_fields_attached(self):
        """Extra fields (incident_id, pipeline_stage, etc.) should be included."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Processing incident",
            args=None,
            exc_info=None,
        )
        record.incident_id = "INC-12345"
        record.pipeline_stage = "enrichment"
        record.duration_ms = 150.5
        record.outcome = "success"

        output = self.formatter.format(record)
        parsed = json.loads(output)

        assert parsed["incident_id"] == "INC-12345"
        assert parsed["pipeline_stage"] == "enrichment"
        assert parsed["duration_ms"] == 150.5
        assert parsed["outcome"] == "success"

    def test_message_included(self):
        """The log message should be included in the output."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Important event happened",
            args=None,
            exc_info=None,
        )
        output = self.formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "Important event happened"


class TestSecretRedaction:
    """Tests for secret redaction functionality."""

    def test_slack_webhook_url_redacted(self):
        """Slack webhook URLs should be redacted."""
        msg = "Sending to https://hooks.slack.com/services/T01234567/B01234567/abcdefghijklmnopqrstuv"
        result = redact_secrets(msg)
        assert "hooks.slack.com" not in result
        assert REDACTED in result

    def test_bearer_token_redacted(self):
        """Bearer tokens should be redacted."""
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6Ikpv"
        result = redact_secrets(msg)
        assert "eyJhbGci" not in result
        assert REDACTED in result

    def test_api_key_redacted(self):
        """API key values should be redacted."""
        msg = "Using api_key=AKIAIOSFODNN7EXAMPLE12345"
        result = redact_secrets(msg)
        assert "AKIAIOSFODNN7EXAMPLE12345" not in result
        assert REDACTED in result

    def test_token_value_redacted(self):
        """Generic token values should be redacted."""
        msg = "Config loaded: token=abc123def456ghi789jkl012mno"
        result = redact_secrets(msg)
        assert "abc123def456ghi789jkl012mno" not in result
        assert REDACTED in result

    def test_password_redacted(self):
        """Password values should be redacted."""
        msg = "Connection: password=MySuperSecretPassword123"
        result = redact_secrets(msg)
        assert "MySuperSecretPassword123" not in result
        assert REDACTED in result

    def test_aws_secret_key_redacted(self):
        """AWS secret access keys should be redacted."""
        msg = "aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY1"
        result = redact_secrets(msg)
        assert "wJalrXUtnFEMI" not in result
        assert REDACTED in result

    def test_normal_message_unchanged(self):
        """Messages without secrets should pass through unchanged."""
        msg = "Processing incident INC-12345 in stage enrichment"
        result = redact_secrets(msg)
        assert result == msg

    def test_redaction_in_json_formatter(self):
        """Secret redaction should be applied by the JSONFormatter."""
        formatter = JSONFormatter(environment="dev")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Webhook URL: https://hooks.slack.com/services/T01/B02/secretpath123",
            args=None,
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "hooks.slack.com" not in parsed["message"]
        assert REDACTED in parsed["message"]


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def teardown_method(self):
        """Reset the root logger after each test."""
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_configure_sets_handler(self):
        """configure_logging should add a handler to the root logger."""
        configure_logging("staging")
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_configure_sets_level(self):
        """configure_logging should set the specified log level."""
        configure_logging("dev", level=logging.DEBUG)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_clears_existing_handlers(self):
        """configure_logging should remove existing handlers and add exactly one."""
        root = logging.getLogger()
        # Clear any existing handlers first (pytest may add its own)
        root.handlers.clear()
        root.addHandler(logging.StreamHandler())
        root.addHandler(logging.StreamHandler())
        assert len(root.handlers) == 2

        configure_logging("prod")
        assert len(root.handlers) == 1

    def test_environment_propagated_to_formatter(self):
        """The environment should be set on the formatter."""
        configure_logging("staging")
        root = logging.getLogger()
        formatter = root.handlers[0].formatter
        assert isinstance(formatter, JSONFormatter)
        assert formatter.environment == "staging"


class TestLogContext:
    """Tests for LogContext helper class."""

    def setup_method(self):
        """Set up a logger with JSONFormatter for capturing output."""
        self.logger = logging.getLogger("test.context")
        self.logger.handlers.clear()
        self.handler = logging.StreamHandler()
        self.handler.setFormatter(JSONFormatter(environment="dev"))
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)

    def teardown_method(self):
        """Clean up logger."""
        self.logger.handlers.clear()

    def test_log_context_attaches_incident_id(self, capsys):
        """LogContext should attach incident_id to log records."""
        ctx = LogContext(
            logger=self.logger,
            incident_id="INC-999",
            pipeline_stage="triage",
        )
        ctx.info("Test message")

        # Verify via the handler's formatter
        # We need to capture the actual formatted output
        import io

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter(environment="dev"))
        self.logger.handlers = [handler]

        ctx = LogContext(
            logger=self.logger,
            incident_id="INC-999",
            pipeline_stage="triage",
        )
        ctx.info("Test message")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["incident_id"] == "INC-999"
        assert parsed["pipeline_stage"] == "triage"

    def test_log_context_with_duration_and_outcome(self):
        """LogContext should pass duration_ms and outcome."""
        import io

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter(environment="prod"))
        self.logger.handlers = [handler]

        ctx = LogContext(
            logger=self.logger,
            incident_id="INC-001",
            pipeline_stage="remediation",
        )
        ctx.info("Complete", duration_ms=250.0, outcome="success")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["duration_ms"] == 250.0
        assert parsed["outcome"] == "success"

    def test_log_context_levels(self):
        """LogContext should support all log levels."""
        import io

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter(environment="dev"))
        self.logger.handlers = [handler]

        ctx = LogContext(logger=self.logger, incident_id="INC-002")

        ctx.debug("debug msg")
        ctx.info("info msg")
        ctx.warning("warning msg")
        ctx.error("error msg")

        lines = stream.getvalue().strip().split("\n")
        assert len(lines) == 4

        levels = [json.loads(line)["level"] for line in lines]
        assert levels == ["DEBUG", "INFO", "WARNING", "ERROR"]


class TestGetLogger:
    """Tests for get_logger utility function."""

    def test_returns_named_logger(self):
        """get_logger should return a logger with the specified name."""
        logger = get_logger("my.module")
        assert logger.name == "my.module"

    def test_inherits_root_configuration(self):
        """Logger from get_logger should inherit root logger config."""
        configure_logging("staging")
        logger = get_logger("test.inherit")
        # Should be able to log without error
        logger.info("test")
        # Clean up
        logging.getLogger().handlers.clear()
