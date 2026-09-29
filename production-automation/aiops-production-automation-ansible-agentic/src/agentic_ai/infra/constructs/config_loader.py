"""ConfigLoader: Runtime configuration from AWS SSM Parameter Store and Secrets Manager.

This is a RUNTIME class used by the ECS application at task startup.
It loads configuration from AWS SSM and Secrets Manager, validates required parameters,
and refreshes them periodically in a background thread.

Requirements: 4.3, 4.4, 4.5, 4.7
"""

import logging
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

import boto3

logger = logging.getLogger(__name__)

# Validation rules for required SSM parameters
REQUIRED_PARAMS: Dict[str, Callable[[str], bool]] = {
    "operating-mode": lambda v: v in {"rules_only", "ai_only", "ai_with_fallback"},
    "escalation-threshold": lambda v: 0.0 <= float(v) <= 1.0,
    "correlation-window-seconds": lambda v: 1 <= int(v) <= 86400,
    "max-concurrent-pipelines": lambda v: 1 <= int(v) <= 500,
    "bedrock-model-id": lambda v: bool(v.strip()),
    "sqs-queue-url": lambda v: bool(v.strip()),
    "dynamodb-table-name": lambda v: bool(v.strip()),
}


@dataclass
class ConfigLoader:
    """Loads and caches configuration from AWS SSM Parameter Store and Secrets Manager.

    Features:
    - Startup batch SSM fetch with validation of required parameters
    - Periodic background refresh of SSM parameters (thread-safe)
    - Secrets Manager caching with configurable TTL
    - Thread-safe access via threading.Lock

    Usage:
        loader = ConfigLoader(environment="prod", refresh_interval=300, secret_ttl=3600)
        loader.start()  # loads params and begins background refresh
        value = loader.get("operating-mode")
        secret = loader.get_secret("slack-webhook-url")
        loader.stop()  # stops background refresh thread
    """

    environment: str
    refresh_interval: int = 300
    secret_ttl: int = 3600

    # Internal state (not constructor params)
    _ssm_client: Any = field(default=None, init=False, repr=False)
    _sm_client: Any = field(default=None, init=False, repr=False)
    _params: Dict[str, str] = field(default_factory=dict, init=False)
    _secrets: Dict[str, Tuple[str, float]] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _refresh_thread: Optional[threading.Thread] = field(default=None, init=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)

    def __post_init__(self) -> None:
        """Validate constructor arguments and initialize boto3 clients."""
        # Validate refresh_interval: min 60s, max 3600s
        if self.refresh_interval < 60:
            self.refresh_interval = 60
        elif self.refresh_interval > 3600:
            self.refresh_interval = 3600

        # Validate secret_ttl: min 60s, max 86400s
        if self.secret_ttl < 60:
            self.secret_ttl = 60
        elif self.secret_ttl > 86400:
            self.secret_ttl = 86400

        self._ssm_client = boto3.client("ssm")
        self._sm_client = boto3.client("secretsmanager")

    def start(self) -> None:
        """Load parameters, validate, and begin background refresh thread.

        On validation failure: logs specific parameter name and error, then sys.exit(1).
        """
        self._load_and_validate_startup()
        self._stop_event.clear()
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop, daemon=True, name="config-refresh"
        )
        self._refresh_thread.start()
        logger.info(
            "ConfigLoader started: environment=%s, refresh_interval=%ds, secret_ttl=%ds",
            self.environment,
            self.refresh_interval,
            self.secret_ttl,
        )

    def stop(self) -> None:
        """Stop the background refresh thread."""
        self._stop_event.set()
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=5.0)
        logger.info("ConfigLoader stopped")

    def get(self, param_name: str) -> str:
        """Get current parameter value (thread-safe).

        Args:
            param_name: The parameter name (without path prefix).

        Returns:
            The parameter value as a string.

        Raises:
            KeyError: If the parameter name is not found in the cache.
        """
        with self._lock:
            return self._params[param_name]

    def get_secret(self, secret_name: str) -> str:
        """Get cached secret value, re-fetching if TTL has expired.

        On re-fetch failure: retains cached value, logs warning.
        Empty secret value: disables channel, logs warning.

        Args:
            secret_name: The secret name (without path prefix).

        Returns:
            The secret value as a string, or empty string if not found/empty.
        """
        with self._lock:
            cached = self._secrets.get(secret_name)

        # Check if cached value is still valid
        if cached:
            value, fetched_at = cached
            if time.time() - fetched_at < self.secret_ttl:
                return value

        # Fetch from Secrets Manager
        secret_id = f"/aiops/{self.environment}/{secret_name}"
        try:
            response = self._sm_client.get_secret_value(SecretId=secret_id)
            value = response.get("SecretString", "")

            if not value:
                logger.warning(
                    "Secret '%s' has empty value — corresponding channel disabled",
                    secret_name,
                )

            with self._lock:
                self._secrets[secret_name] = (value, time.time())
            return value

        except self._sm_client.exceptions.ResourceNotFoundException:
            logger.warning(
                "Secret not found: %s — corresponding channel disabled", secret_id
            )
            with self._lock:
                self._secrets[secret_name] = ("", time.time())
            return ""

        except Exception as exc:
            if cached:
                logger.warning(
                    "Secrets Manager re-fetch failed for '%s', using cached value: %s",
                    secret_name,
                    exc,
                )
                return cached[0]
            logger.warning(
                "Secrets Manager fetch failed for '%s' with no cached value: %s — channel disabled",
                secret_name,
                exc,
            )
            with self._lock:
                self._secrets[secret_name] = ("", time.time())
            return ""

    def _load_and_validate_startup(self) -> None:
        """Batch-fetch all SSM params and validate required ones.

        On failure: logs specific parameter name and error, then sys.exit(1).
        """
        path = f"/aiops/{self.environment}/"
        try:
            params = self._fetch_ssm_parameters(path)
        except Exception as exc:
            logger.error("SSM startup fetch failed: %s", exc)
            sys.exit(1)

        # Validate required parameters
        errors: list = []
        for name, validator in REQUIRED_PARAMS.items():
            value = params.get(name)
            if value is None:
                errors.append(f"missing required parameter: {name}")
                continue
            try:
                if not validator(value):
                    errors.append(f"invalid value for {name}: '{value}'")
            except (ValueError, TypeError) as exc:
                errors.append(f"invalid value for {name}: '{value}' ({exc})")

        if errors:
            for err in errors:
                logger.error("Config validation error — %s", err)
            sys.exit(1)

        with self._lock:
            self._params = params

        logger.info("SSM parameters loaded and validated: %d keys", len(params))

    def _refresh_loop(self) -> None:
        """Background thread: periodically re-fetch SSM parameters.

        On fetch failure: retains last valid values, logs warning, retries next interval.
        """
        while not self._stop_event.is_set():
            # Wait for the refresh interval or until stop is signaled
            if self._stop_event.wait(timeout=self.refresh_interval):
                break  # Stop event was set

            path = f"/aiops/{self.environment}/"
            try:
                new_params = self._fetch_ssm_parameters(path)
                with self._lock:
                    self._params = new_params
                logger.info("SSM parameters refreshed: %d keys", len(new_params))
            except Exception as exc:
                logger.warning(
                    "SSM refresh failed, retaining cached values: %s", exc
                )

    def _fetch_ssm_parameters(self, path: str) -> Dict[str, str]:
        """Fetch all SSM parameters under the given path using pagination.

        Args:
            path: The SSM parameter path prefix (e.g., /aiops/prod/).

        Returns:
            Dictionary mapping parameter names (without path prefix) to values.
        """
        params: Dict[str, str] = {}
        paginator = self._ssm_client.get_paginator("get_parameters_by_path")

        for page in paginator.paginate(
            Path=path, WithDecryption=True, Recursive=False
        ):
            for param in page.get("Parameters", []):
                # Extract parameter name from full path
                name = param["Name"].split("/")[-1]
                params[name] = param["Value"]

        return params
