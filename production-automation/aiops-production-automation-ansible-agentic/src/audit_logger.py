"""Audit Logger component for persisting structured audit records.

Records audit trail entries in JSON Lines format with file rotation
and retry logic for write failures.
"""

import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler

from src.models import AuditRecord

logger = logging.getLogger(__name__)

# Constants
MAX_OUTPUT_SUMMARY_LENGTH = 2048
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
ROTATED_FILE_COUNT = 7
MAX_WRITE_RETRIES = 3


class AuditLogger:
    """Records audit trail entries in JSON Lines format.

    The AuditLogger persists structured audit records to a log file,
    one JSON object per line. It handles:
    - Output summary truncation to 2,048 characters
    - Retry logic (3 attempts) on write failure with stderr fallback
    - File rotation at 100 MB with 7 rotated files retention
    """

    def __init__(self, log_file_path: str = "audit.log"):
        """Initialize the AuditLogger with the specified log file path.

        Args:
            log_file_path: Path to the audit log file. Defaults to 'audit.log'.
        """
        self._log_file_path = log_file_path
        self._handler = self._create_rotating_handler()

    def _create_rotating_handler(self) -> RotatingFileHandler:
        """Create a RotatingFileHandler for the audit log file.

        Configures rotation at 100 MB with 7 backup files retained.

        Returns:
            A configured RotatingFileHandler instance.
        """
        # Ensure the parent directory exists
        log_dir = os.path.dirname(self._log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        handler = RotatingFileHandler(
            filename=self._log_file_path,
            maxBytes=MAX_FILE_SIZE_BYTES,
            backupCount=ROTATED_FILE_COUNT,
            encoding="utf-8",
        )
        # No formatter needed - we write raw JSON lines
        handler.setFormatter(logging.Formatter("%(message)s"))
        return handler

    def log_incident(self, record: AuditRecord) -> None:
        """Write an audit record to the log file.

        Truncates the output_summary field to 2,048 characters before writing.
        Retries up to 3 times on write failure. If all retries fail, logs the
        failure to stderr and continues without blocking the pipeline.

        Args:
            record: The AuditRecord to persist.
        """
        # Truncate output_summary to maximum allowed length
        if record.output_summary and len(record.output_summary) > MAX_OUTPUT_SUMMARY_LENGTH:
            record.output_summary = record.output_summary[:MAX_OUTPUT_SUMMARY_LENGTH]

        # Serialize to JSON line
        json_line = record.to_json_line()

        # Attempt to write with retry logic
        self._write_with_retry(json_line)

    def _write_with_retry(self, json_line: str) -> None:
        """Write a JSON line to the audit log with retry logic.

        Attempts to write up to MAX_WRITE_RETRIES times. If all attempts
        fail, logs the failure to stderr as a fallback.

        Args:
            json_line: The serialized JSON string to write.
        """
        last_error: Exception | None = None

        for attempt in range(1, MAX_WRITE_RETRIES + 1):
            try:
                # Create a LogRecord to pass through the handler
                log_record = logging.LogRecord(
                    name="audit",
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg=json_line,
                    args=None,
                    exc_info=None,
                )
                self._handler.emit(log_record)
                return  # Success
            except Exception as e:
                last_error = e
                logger.warning(
                    "Audit log write attempt %d/%d failed: %s",
                    attempt,
                    MAX_WRITE_RETRIES,
                    str(e),
                )
                if attempt < MAX_WRITE_RETRIES:
                    time.sleep(0.1 * attempt)  # Brief backoff between retries

        # All retries exhausted - fallback to stderr
        print(
            f"AUDIT_LOG_FAILURE: Failed to write audit record after "
            f"{MAX_WRITE_RETRIES} attempts. Last error: {last_error}. "
            f"Record: {json_line}",
            file=sys.stderr,
        )
        logger.error(
            "Failed to persist audit record after %d attempts: %s",
            MAX_WRITE_RETRIES,
            str(last_error),
        )

    def close(self) -> None:
        """Close the audit log handler and release file resources."""
        self._handler.close()

    @property
    def log_file_path(self) -> str:
        """Return the path to the audit log file."""
        return self._log_file_path
