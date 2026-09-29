"""Configuration loading and environment variable validation.

Provides:
- Configuration loading from environment variables
- Validation of required variables
- Structured JSON logging setup

Requirements: 10.2, 10.3, 10.5
"""

import json
import logging
import os
import sys
from typing import Optional


# Required environment variables
REQUIRED_ENV_VARS = [
    "SES_FROM_ADDRESS",
    "OPERATOR_EMAIL",
    "ASSET_INVENTORY_PATH",
    "MAPPING_CONFIG_PATH",
]

# Optional environment variables with defaults
OPTIONAL_ENV_VARS = {
    "AUDIT_LOG_PATH": "audit.log",
    "PORT": "8080",
    "LOG_LEVEL": "INFO",
    "SERVICE_BASE_URL": "http://localhost:8080",
    "APPROVAL_EXPIRY_SECONDS": "1800",
}


class JsonFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def load_config() -> dict:
    """Load configuration from environment variables.

    Returns a dictionary with all configuration values, using defaults
    for optional variables that are not set.
    """
    config = {}

    # Load required variables (may be None if not set)
    for var in REQUIRED_ENV_VARS:
        config[var] = os.environ.get(var)

    # Load optional variables with defaults
    for var, default in OPTIONAL_ENV_VARS.items():
        config[var] = os.environ.get(var, default)

    return config


def validate_config() -> dict:
    """Validate that all required environment variables are set and non-empty.

    If any required variable is missing or empty, prints a structured JSON
    error to stderr and exits with code 1.

    Returns:
        dict: The validated configuration dictionary.
    """
    config = load_config()
    missing = []

    for var in REQUIRED_ENV_VARS:
        value = config.get(var)
        if not value or value.strip() == "":
            missing.append(var)

    if missing:
        error_msg = {
            "error": "missing_required_configuration",
            "missing_variables": missing,
            "message": f"Required environment variable(s) not set: {', '.join(missing)}",
        }
        print(json.dumps(error_msg), file=sys.stderr)
        sys.exit(1)

    return config


def setup_logging(level: Optional[str] = None) -> None:
    """Configure Python logging to output structured JSON.

    Sets up the root logger with a StreamHandler that outputs JSON-formatted
    log messages to stdout.

    Args:
        level: Log level string (e.g., "INFO", "DEBUG"). If None, reads
               from LOG_LEVEL environment variable or defaults to "INFO".
    """
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO")

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create JSON formatter
    formatter = JsonFormatter()

    # Configure stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(stdout_handler)
