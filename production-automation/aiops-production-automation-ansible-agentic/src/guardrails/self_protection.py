"""Self-Protection Guard — prevents remediation of the automation host itself.

Loads protected hosts from YAML config and denies any action targeting them.
Supports hot-reload with retention of valid config on invalid reload.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
"""

import logging
import os
import socket
from typing import Optional

import yaml

from src.guardrails.models import CheckResult, CheckResultType, RemediationAction

logger = logging.getLogger(__name__)

MAX_PROTECTED_HOSTS = 50
DEFAULT_CONFIG_PATH = "config/protected_hosts.yml"


class SelfProtectionGuard:
    """Denies remediation actions targeting the automation host or critical dependencies.

    Loads protected hosts from a YAML configuration file. If the config file
    is missing, falls back to the local hostname. Supports hot-reload with
    retention of valid config on invalid reload.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize SelfProtectionGuard.

        Args:
            config_path: Path to the protected hosts YAML config file.
                Defaults to 'config/protected_hosts.yml'.

        Raises:
            SystemExit: If config file exists but is malformed, empty, or schema invalid.
        """
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._protected_hosts: set[str] = set()

        if os.path.isfile(self._config_path):
            hosts = self._load_config(self._config_path)
            if hosts is None:
                logger.critical(
                    "SelfProtectionGuard refusing to start: "
                    "malformed or invalid config at %s",
                    self._config_path,
                )
                raise SystemExit(1)
            self._protected_hosts = hosts
        else:
            # Fallback to local hostname
            local_host = socket.gethostname()
            self._protected_hosts = {local_host.lower()}
            logger.warning(
                "Protected hosts config not found at %s, "
                "falling back to local hostname: %s",
                self._config_path,
                local_host,
            )

    @property
    def name(self) -> str:
        """Unique name identifying this guardrail check."""
        return "self_protection"

    @property
    def protected_hosts(self) -> set[str]:
        """Current set of protected hostnames (lowercase)."""
        return self._protected_hosts.copy()

    async def check(self, action: RemediationAction) -> CheckResult:
        """Check if the action targets a protected host.

        Uses case-insensitive matching against hostname and FQDN.

        Args:
            action: The remediation action to evaluate.

        Returns:
            DENY if target is protected, ALLOW otherwise.
        """
        target = action.target_host.lower().strip()

        if target in self._protected_hosts:
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason=f"Target host '{action.target_host}' is a protected host",
                metadata={"protected_host": target},
            )

        # Also check without domain suffix (FQDN matching)
        target_short = target.split(".")[0]
        for protected in self._protected_hosts:
            protected_short = protected.split(".")[0]
            if target_short == protected_short:
                return CheckResult(
                    result_type=CheckResultType.DENY,
                    check_name=self.name,
                    reason=f"Target host '{action.target_host}' matches protected host '{protected}'",
                    metadata={"protected_host": protected},
                )

        return CheckResult(
            result_type=CheckResultType.ALLOW,
            check_name=self.name,
            reason="Target host is not protected",
        )

    def reload(self) -> bool:
        """Hot-reload the protected hosts configuration.

        Retains the previous valid config if the new config is invalid.

        Returns:
            True if reload succeeded, False if retained previous config.
        """
        if not os.path.isfile(self._config_path):
            logger.warning(
                "Config file not found during reload: %s, retaining current config",
                self._config_path,
            )
            return False

        new_hosts = self._load_config(self._config_path)
        if new_hosts is None:
            logger.warning(
                "Invalid config during reload, retaining previous valid config "
                "(%d hosts)",
                len(self._protected_hosts),
            )
            return False

        self._protected_hosts = new_hosts
        logger.info(
            "SelfProtectionGuard reloaded: %d protected hosts",
            len(self._protected_hosts),
        )
        return True

    def _load_config(self, path: str) -> Optional[set[str]]:
        """Load and validate the protected hosts config file.

        Args:
            path: Path to the YAML config file.

        Returns:
            Set of lowercase hostnames, or None if config is invalid.
        """
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.error("Failed to load protected hosts config: %s", e)
            return None

        if not isinstance(data, dict):
            logger.error("Protected hosts config must be a YAML mapping")
            return None

        hosts_list = data.get("protected_hosts")
        if not isinstance(hosts_list, list):
            logger.error("'protected_hosts' key must be a list")
            return None

        if len(hosts_list) == 0:
            logger.error("Protected hosts list must not be empty")
            return None

        if len(hosts_list) > MAX_PROTECTED_HOSTS:
            logger.error(
                "Protected hosts list exceeds maximum of %d (got %d)",
                MAX_PROTECTED_HOSTS,
                len(hosts_list),
            )
            return None

        # Validate each entry is a non-empty string
        hosts: set[str] = set()
        for entry in hosts_list:
            if not isinstance(entry, str) or not entry.strip():
                logger.error("Each protected host must be a non-empty string")
                return None
            hosts.add(entry.lower().strip())

        return hosts
