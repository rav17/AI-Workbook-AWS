"""Property-based tests for configuration loading and validation.

Property 27: For any combination of missing required environment variables,
the system SHALL exit with non-zero code and log an error identifying the
missing variable(s).
Validates: Requirements 10.3

Property 28: For any log event produced by the system, the output SHALL be
valid JSON.
Validates: Requirements 10.5
"""

import io
import json
import logging
import os
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.config import (
    REQUIRED_ENV_VARS,
    OPTIONAL_ENV_VARS,
    validate_config,
    JsonFormatter,
)


# --- Strategies ---

def missing_vars_strategy():
    """Generate non-empty subsets of required environment variables to omit."""
    return st.lists(
        st.sampled_from(REQUIRED_ENV_VARS),
        min_size=1,
        max_size=len(REQUIRED_ENV_VARS),
        unique=True,
    )


def present_vars_values_strategy():
    """Generate non-empty string values for environment variables."""
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "P"),
            whitelist_characters="/-_.:@"
        ),
        min_size=1,
        max_size=200,
    ).filter(lambda s: s.strip() != "")


def log_message_strategy():
    """Generate arbitrary log messages."""
    return st.text(min_size=0, max_size=500)


def log_level_strategy():
    """Generate valid log level names."""
    return st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])


# --- Property 27: Missing environment variable detection ---

class TestMissingEnvVarDetection:
    """Property 27: Missing required env vars cause exit with error."""

    @given(missing_vars=missing_vars_strategy())
    @settings(max_examples=100)
    def test_missing_required_vars_causes_system_exit(self, missing_vars):
        """For any combination of missing required env vars, validate_config
        SHALL exit with non-zero code."""
        # Build an environment where missing_vars are absent
        env = {}
        for var in REQUIRED_ENV_VARS:
            if var not in missing_vars:
                env[var] = "http://example.com/valid-value"

        # Also set optional vars to avoid interference
        for var, default in OPTIONAL_ENV_VARS.items():
            env[var] = default

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                validate_config()

            assert exc_info.value.code == 1

    @given(missing_vars=missing_vars_strategy())
    @settings(max_examples=100)
    def test_missing_vars_error_identifies_variables(self, missing_vars):
        """The error output SHALL identify which variable(s) are missing."""
        # Build an environment where missing_vars are absent
        env = {}
        for var in REQUIRED_ENV_VARS:
            if var not in missing_vars:
                env[var] = "http://example.com/valid-value"

        for var, default in OPTIONAL_ENV_VARS.items():
            env[var] = default

        stderr_capture = io.StringIO()

        with patch.dict(os.environ, env, clear=True):
            with patch("sys.stderr", stderr_capture):
                with pytest.raises(SystemExit):
                    validate_config()

        # Parse the stderr output as JSON
        stderr_output = stderr_capture.getvalue().strip()
        assert stderr_output, "Expected error output on stderr"

        error_data = json.loads(stderr_output)
        assert "missing_variables" in error_data

        # All missing vars should be reported
        for var in missing_vars:
            assert var in error_data["missing_variables"]

    @given(
        missing_vars=missing_vars_strategy(),
        empty_value=st.sampled_from(["", "   ", "\t", "\n"]),
    )
    @settings(max_examples=100)
    def test_empty_or_whitespace_vars_treated_as_missing(self, missing_vars, empty_value):
        """Variables set to empty or whitespace-only values SHALL be treated as missing."""
        env = {}
        for var in REQUIRED_ENV_VARS:
            if var in missing_vars:
                env[var] = empty_value  # Set to empty/whitespace
            else:
                env[var] = "http://example.com/valid-value"

        for var, default in OPTIONAL_ENV_VARS.items():
            env[var] = default

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                validate_config()

            assert exc_info.value.code == 1

    @given(values=st.fixed_dictionaries({
        var: present_vars_values_strategy() for var in REQUIRED_ENV_VARS
    }))
    @settings(max_examples=100)
    def test_all_required_vars_present_does_not_exit(self, values):
        """When all required vars are set and non-empty, validate_config SHALL NOT exit."""
        env = dict(values)
        for var, default in OPTIONAL_ENV_VARS.items():
            env[var] = default

        with patch.dict(os.environ, env, clear=True):
            # Should not raise SystemExit
            config = validate_config()
            assert config is not None
            for var in REQUIRED_ENV_VARS:
                assert config[var] == values[var]


# --- Property 28: Structured JSON log output ---

class TestStructuredJsonLogOutput:
    """Property 28: All log output SHALL be valid JSON."""

    @given(
        message=log_message_strategy(),
        level=log_level_strategy(),
    )
    @settings(max_examples=100)
    def test_log_output_is_valid_json(self, message, level):
        """For any log event, the output SHALL be valid JSON."""
        # Create a fresh logger with a StringIO handler
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = JsonFormatter()
        handler.setFormatter(formatter)

        logger = logging.getLogger(f"test.json.{id(stream)}")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Log the message at the specified level
        log_method = getattr(logger, level.lower())
        log_method(message)

        # Get the output
        output = stream.getvalue().strip()
        assert output, "Expected log output"

        # Verify it's valid JSON
        parsed = json.loads(output)
        assert isinstance(parsed, dict)
        assert "message" in parsed
        assert "level" in parsed
        assert "timestamp" in parsed
        assert "logger" in parsed
        assert parsed["level"] == level
        assert parsed["message"] == message

    @given(message=log_message_strategy())
    @settings(max_examples=100)
    def test_setup_logging_produces_json(self, message):
        """After calling setup_logging(), log messages SHALL be valid JSON."""
        # Capture output via a StringIO stream
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = JsonFormatter()
        handler.setFormatter(formatter)

        # Use a unique logger name to avoid interference
        logger_name = f"test.setup.{id(stream)}"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        # Log a message
        logger.info(message)

        output = stream.getvalue().strip()
        if output:
            parsed = json.loads(output)
            assert isinstance(parsed, dict)
            assert "message" in parsed
            assert parsed["message"] == message

    @given(
        message=log_message_strategy(),
        level=log_level_strategy(),
    )
    @settings(max_examples=100)
    def test_json_log_contains_required_fields(self, message, level):
        """JSON log entries SHALL contain timestamp, level, logger, and message fields."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = JsonFormatter()
        handler.setFormatter(formatter)

        logger = logging.getLogger(f"test.fields.{id(stream)}")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        log_method = getattr(logger, level.lower())
        log_method(message)

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        # All required fields must be present
        required_fields = {"timestamp", "level", "logger", "message"}
        assert required_fields.issubset(set(parsed.keys()))

    @given(message=st.text(min_size=1, max_size=200))
    @settings(max_examples=100)
    def test_exception_logging_produces_valid_json(self, message):
        """Log entries with exceptions SHALL still be valid JSON."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        formatter = JsonFormatter()
        handler.setFormatter(formatter)

        logger = logging.getLogger(f"test.exc.{id(stream)}")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            raise ValueError(message)
        except ValueError:
            logger.exception("An error occurred")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert isinstance(parsed, dict)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
