"""Application entrypoint for the AIOps self-healing infrastructure service.

Wires all components together, handles signal-based lifecycle management,
and starts the uvicorn server programmatically.

Signal handling:
- SIGTERM: Graceful shutdown - stops accepting new alerts, waits up to 30s
           for in-progress pipelines to drain, then exits.
- SIGHUP:  Configuration reload - reloads playbook mapping and asset inventory
           without restarting the process.
"""

import asyncio
import logging
import signal
import sys
import threading
import time

import uvicorn

from src.config import validate_config, setup_logging

logger = logging.getLogger(__name__)

# Shutdown coordination
_shutdown_flag = threading.Event()
_active_pipelines: int = 0
_pipeline_lock = threading.Lock()

DRAIN_TIMEOUT_SECONDS = 30


def get_shutdown_flag() -> threading.Event:
    """Return the shutdown flag for use by other modules."""
    return _shutdown_flag


def register_pipeline_start() -> None:
    """Register that a new pipeline has started processing."""
    global _active_pipelines
    with _pipeline_lock:
        _active_pipelines += 1


def register_pipeline_end() -> None:
    """Register that a pipeline has finished processing."""
    global _active_pipelines
    with _pipeline_lock:
        _active_pipelines -= 1


def _wait_for_drain(timeout: float = DRAIN_TIMEOUT_SECONDS) -> bool:
    """Wait for all in-progress pipelines to complete.

    Args:
        timeout: Maximum seconds to wait for pipelines to drain.

    Returns:
        True if all pipelines drained within timeout, False otherwise.
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        with _pipeline_lock:
            if _active_pipelines <= 0:
                return True
        time.sleep(0.5)
    return False


def main() -> None:
    """Application entrypoint.

    1. Validates configuration from environment variables.
    2. Sets up structured JSON logging.
    3. Registers signal handlers for SIGTERM and SIGHUP.
    4. Starts uvicorn with the FastAPI app.
    """
    config = validate_config()
    setup_logging(config.get("LOG_LEVEL", "INFO"))

    logger.info("Starting AIOps self-healing infrastructure service")

    # Import app components after config validation
    from src.app import app, playbook_mapper, asset_inventory  # noqa: F401

    def handle_sigterm(signum, frame):
        """Handle SIGTERM: graceful shutdown with pipeline draining.

        Requirement 10.6:
        - Stop accepting new alerts
        - Allow in-progress pipelines up to 30 seconds to complete
        - Exit with code 0 if all pipelines drained successfully
        - Exit with non-zero code if drain timeout exceeded
        """
        logger.info("SIGTERM received, initiating graceful shutdown")
        _shutdown_flag.set()

        # Wait for in-progress pipelines to drain
        with _pipeline_lock:
            active = _active_pipelines

        if active > 0:
            logger.info(
                "Waiting up to %ds for %d in-progress pipeline(s) to drain",
                DRAIN_TIMEOUT_SECONDS,
                active,
            )
            drained = _wait_for_drain(DRAIN_TIMEOUT_SECONDS)
            if not drained:
                with _pipeline_lock:
                    remaining = _active_pipelines
                logger.warning(
                    "Drain timeout exceeded, %d pipeline(s) still active. Forcing exit.",
                    remaining,
                )
                sys.exit(1)  # Non-zero exit: incomplete shutdown
        else:
            logger.info("No active pipelines, shutting down immediately")

        sys.exit(0)  # Clean shutdown: all pipelines drained

    def handle_sighup(signum, frame):
        """Handle SIGHUP: reload configuration files."""
        logger.info("SIGHUP received, reloading configuration")
        try:
            playbook_mapper.reload()
            logger.info("Playbook mapping configuration reloaded successfully")
        except Exception as e:
            logger.error("Failed to reload playbook mapping: %s", e)

        try:
            asset_inventory.reload()
            logger.info("Asset inventory reloaded successfully")
        except Exception as e:
            logger.error("Failed to reload asset inventory: %s", e)

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_sigterm)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, handle_sighup)

    # Start uvicorn
    port = int(config.get("PORT", "8080"))
    logger.info("Starting uvicorn on 0.0.0.0:%d", port)

    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",
        port=port,
        log_level=config.get("LOG_LEVEL", "INFO").lower(),
    )


if __name__ == "__main__":
    main()
