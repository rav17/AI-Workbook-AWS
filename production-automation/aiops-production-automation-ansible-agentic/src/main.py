"""Application entrypoint for the AIOps self-healing infrastructure service.

Wires all components together, handles signal-based lifecycle management,
and starts the uvicorn server programmatically.

Signal handling:
- SIGTERM: Graceful shutdown - stops accepting new alerts, waits up to 25s
           for in-progress pipelines to drain, releases DynamoDB locks, exits.
- SIGHUP:  Configuration reload - reloads playbook mapping and asset inventory
           without restarting the process.

The graceful shutdown handler ensures DynamoDB locks are released before
ECS kills the container, preventing lock leaks during deployments.
"""

import logging
import signal
import sys
import threading
import time

import uvicorn

from src.config import validate_config, setup_logging
from src.concurrency.graceful_shutdown import GracefulShutdownHandler

logger = logging.getLogger(__name__)

# Shutdown coordination
_shutdown_flag = threading.Event()
_active_pipelines: int = 0
_pipeline_lock = threading.Lock()

DRAIN_TIMEOUT_SECONDS = 25  # Reduced from 30 to leave 5s buffer for lock release

# Module-level graceful shutdown handler (used by app.py to check draining state)
_graceful_handler = GracefulShutdownHandler()


def get_shutdown_flag() -> threading.Event:
    """Return the shutdown flag for use by other modules."""
    return _shutdown_flag


def get_graceful_handler() -> GracefulShutdownHandler:
    """Return the graceful shutdown handler for use by other modules."""
    return _graceful_handler


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


def _validate_playbook_accessibility(playbook_mapper) -> None:
    """Validate that all configured playbooks are accessible on disk.

    Logs warnings for any playbook paths that don't exist. This catches
    misconfigurations early (e.g., wrong WORKDIR in container).
    """
    import os
    missing = []
    for rule in playbook_mapper.rules:
        if not os.path.isfile(rule.playbook_path):
            missing.append(f"  - {rule.name}: {rule.playbook_path}")

    if missing:
        logger.warning(
            "The following configured playbooks are NOT accessible on disk:\n%s\n"
            "Alerts matching these rules will fail to execute. "
            "Check that playbook files are correctly mounted/copied in the container.",
            "\n".join(missing),
        )
    else:
        logger.info(
            "All %d configured playbook paths verified accessible",
            len(playbook_mapper.rules),
        )


def main() -> None:
    """Application entrypoint.

    1. Validates configuration from environment variables.
    2. Sets up structured JSON logging.
    3. Registers signal handlers for SIGTERM and SIGHUP.
    4. Wires the graceful shutdown handler to the concurrency manager.
    5. Starts uvicorn with the FastAPI app.
    """
    config = validate_config()
    setup_logging(config.get("LOG_LEVEL", "INFO"))

    logger.info("Starting AIOps self-healing infrastructure service")

    # Import app components after config validation
    from src.app import app, playbook_mapper, asset_inventory  # noqa: F401

    # Startup validation: check all configured playbooks are accessible
    _validate_playbook_accessibility(playbook_mapper)

    def handle_sigterm(signum, frame):
        """Handle SIGTERM: graceful shutdown with pipeline draining and lock release."""
        logger.info("SIGTERM received, initiating graceful shutdown")
        _shutdown_flag.set()

        # Flush tracing spans before shutdown
        try:
            from src.tracing import shutdown as tracing_shutdown
            tracing_shutdown()
        except Exception:
            pass

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
                    "Drain timeout exceeded, %d pipeline(s) still active. "
                    "Releasing locks and forcing exit.",
                    remaining,
                )
        else:
            logger.info("No active pipelines, shutting down immediately")

        # The GracefulShutdownHandler will release DynamoDB locks
        # via its own signal handling if a concurrency manager is attached.
        sys.exit(0)

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
