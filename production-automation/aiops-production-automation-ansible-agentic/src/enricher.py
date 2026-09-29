"""Asset inventory loading and alert enrichment for the self-healing infrastructure system.

This module provides:
- AssetInventory: YAML-based asset inventory with hot-reload support
- Enricher: Augments normalized alerts with environment context from the asset inventory
"""

import logging
import os
import time
import threading
from typing import Optional

import yaml

from src.models import AssetInfo, EnrichedAlert, NormalizedAlert

logger = logging.getLogger(__name__)

# Label priority order for host lookup
LOOKUP_LABEL_PRIORITY = ["instance", "hostname", "job"]

# Maximum time allowed for enrichment per alert (in seconds)
ENRICHMENT_TIMEOUT_SECONDS = 1.0


class AssetInventory:
    """YAML-based asset inventory with hot-reload support.

    Loads asset data from a YAML file and provides lookup by key.
    Supports hot-reload by detecting file modification time changes.

    The YAML file should have the structure:
        assets:
          "host-key":
            hostname: "..."
            ip_address: "..."
            location: "..."
            service_name: "..."
            service_owner: "..."
    """

    def __init__(self, inventory_path: Optional[str] = None):
        """Initialize the AssetInventory.

        Args:
            inventory_path: Path to the YAML asset inventory file.
                           If None, the inventory will be empty.
        """
        self._inventory_path = inventory_path
        self._assets: dict[str, dict[str, str]] = {}
        self._last_modified: float = 0.0
        self._lock = threading.Lock()
        self._loaded = False

        if inventory_path:
            self._load()

    @property
    def is_loaded(self) -> bool:
        """Whether the inventory has been successfully loaded at least once."""
        return self._loaded

    @property
    def asset_count(self) -> int:
        """Number of assets currently in the inventory."""
        with self._lock:
            return len(self._assets)

    def _load(self) -> None:
        """Load or reload the asset inventory from the YAML file.

        On failure, retains the previously loaded data and logs an error.
        """
        if not self._inventory_path:
            logger.warning("No inventory path configured")
            return

        try:
            if not os.path.exists(self._inventory_path):
                logger.error(
                    "Asset inventory file not found: %s", self._inventory_path
                )
                return

            mtime = os.path.getmtime(self._inventory_path)

            with open(self._inventory_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)

            if raw_data is None:
                logger.error(
                    "Asset inventory file is empty: %s", self._inventory_path
                )
                return

            # Support multiple formats:
            # 1. Dict-keyed: {"host-key": {hostname: ..., ...}}
            # 2. Nested dict-keyed: {"assets": {"host-key": {hostname: ..., ...}}}
            # 3. List with lookup_keys: {"assets": [{hostname: ..., lookup_keys: [...]}]}
            if isinstance(raw_data, dict):
                if "assets" in raw_data:
                    assets_raw = raw_data["assets"]
                    if isinstance(assets_raw, dict):
                        assets_data = assets_raw
                    elif isinstance(assets_raw, list):
                        # Convert list format with lookup_keys to dict format
                        assets_data = self._convert_list_format(assets_raw)
                    else:
                        logger.error(
                            "Asset inventory 'assets' key has invalid type: %s",
                            type(assets_raw).__name__,
                        )
                        return
                else:
                    assets_data = raw_data
            else:
                logger.error(
                    "Asset inventory has invalid format (expected dict): %s",
                    self._inventory_path,
                )
                return

            # Validate and store assets
            validated_assets: dict[str, dict[str, str]] = {}
            for key, value in assets_data.items():
                if isinstance(value, dict):
                    validated_assets[str(key)] = {
                        str(k): str(v) if v is not None else ""
                        for k, v in value.items()
                    }
                else:
                    logger.warning(
                        "Skipping invalid asset entry for key '%s': expected dict, got %s",
                        key,
                        type(value).__name__,
                    )

            with self._lock:
                self._assets = validated_assets
                self._last_modified = mtime
                self._loaded = True

            logger.info(
                "Loaded asset inventory with %d entries from %s",
                len(validated_assets),
                self._inventory_path,
            )

        except yaml.YAMLError as e:
            logger.error(
                "Failed to parse asset inventory YAML: %s", e
            )
            # Retain previous data on parse failure
        except OSError as e:
            logger.error(
                "Failed to read asset inventory file: %s", e
            )
            # Retain previous data on I/O failure

    def reload(self) -> bool:
        """Reload the inventory if the file has been modified.

        Returns:
            True if the inventory was reloaded, False otherwise.
        """
        if not self._inventory_path:
            return False

        try:
            if not os.path.exists(self._inventory_path):
                logger.warning(
                    "Asset inventory file not found during reload: %s",
                    self._inventory_path,
                )
                return False

            mtime = os.path.getmtime(self._inventory_path)
            if mtime > self._last_modified:
                self._load()
                return True
        except OSError as e:
            logger.error("Error checking inventory file modification time: %s", e)

        return False

    def lookup(self, key: str) -> Optional[dict[str, str]]:
        """Look up an asset by key.

        Args:
            key: The lookup key (typically derived from alert labels).

        Returns:
            Asset data dictionary if found, None otherwise.
        """
        with self._lock:
            return self._assets.get(key)

    def set_assets(self, assets: dict[str, dict[str, str]]) -> None:
        """Directly set the asset inventory data (useful for testing).

        Args:
            assets: Dictionary mapping lookup keys to asset data.
        """
        with self._lock:
            self._assets = assets
            self._loaded = True

    @staticmethod
    def _convert_list_format(assets_list: list) -> dict[str, dict[str, str]]:
        """Convert list-based asset inventory format to dict-keyed format.

        Handles entries like:
            - hostname: web-server-01.prod.example.com
              ip_address: 10.0.1.10
              service_name: web-frontend
              lookup_keys:
                - web-server-01.prod.example.com
                - 10.0.1.10
                - web-server-01:9090

        Each lookup_key becomes a separate dict entry pointing to the same asset data.
        If no lookup_keys are present, the hostname is used as the key.

        Args:
            assets_list: List of asset dictionaries.

        Returns:
            Dict mapping lookup keys to asset data dicts.
        """
        result: dict[str, dict[str, str]] = {}
        for entry in assets_list:
            if not isinstance(entry, dict):
                continue

            # Extract the asset data (exclude lookup_keys from stored data)
            asset_data = {
                str(k): str(v) if v is not None else ""
                for k, v in entry.items()
                if k != "lookup_keys"
            }

            # Determine lookup keys
            lookup_keys = entry.get("lookup_keys", [])
            if isinstance(lookup_keys, list) and lookup_keys:
                for key in lookup_keys:
                    if key and str(key).strip():
                        result[str(key).strip()] = asset_data
            elif asset_data.get("hostname"):
                # Fallback: use hostname as the lookup key
                result[asset_data["hostname"]] = asset_data
            elif asset_data.get("ip_address"):
                # Fallback: use IP address as the lookup key
                result[asset_data["ip_address"]] = asset_data

        return result


class Enricher:
    """Enriches normalized alerts with asset inventory data.

    Looks up hosts in the asset inventory using label priority order:
    instance → hostname → job. Handles missing assets, timeouts, and
    corrupted data gracefully.
    """

    def __init__(self, asset_inventory: AssetInventory):
        """Initialize the Enricher.

        Args:
            asset_inventory: The asset inventory to use for lookups.
        """
        self.inventory = asset_inventory

    def _derive_lookup_key(self, alert: NormalizedAlert) -> Optional[str]:
        """Derive the lookup key from alert labels using priority order.

        Checks labels in order: instance → hostname → job.
        Uses the first non-empty value found.

        Args:
            alert: The normalized alert to derive the key from.

        Returns:
            The lookup key string, or None if no valid key could be derived.
        """
        for label_name in LOOKUP_LABEL_PRIORITY:
            value = alert.labels.get(label_name, "")
            if value and value.strip():
                return value.strip()
        return None

    def _build_asset_info(self, asset_data: dict[str, str]) -> AssetInfo:
        """Build an AssetInfo from raw asset data, handling missing fields.

        Args:
            asset_data: Raw asset data dictionary from the inventory.

        Returns:
            An AssetInfo instance with available fields populated.

        Raises:
            ValueError: If the asset data is fundamentally corrupted.
        """
        try:
            return AssetInfo(
                hostname=asset_data.get("hostname", ""),
                ip_address=asset_data.get("ip_address", ""),
                location=asset_data.get("location", ""),
                service_name=asset_data.get("service_name", ""),
                service_owner=asset_data.get("service_owner", ""),
            )
        except (TypeError, AttributeError) as e:
            raise ValueError(f"Corrupted asset data: {e}") from e

    def enrich(self, alert: NormalizedAlert) -> EnrichedAlert:
        """Enrich a normalized alert with asset inventory data.

        Looks up the host in the inventory using label priority order
        (instance → hostname → job). Handles missing assets, timeouts,
        and corrupted data.

        Args:
            alert: The normalized alert to enrich.

        Returns:
            An EnrichedAlert with asset data attached if found,
            or marked as unenriched if lookup fails.
        """
        start_time = time.monotonic()

        # Create base enriched alert (unenriched by default)
        enriched = EnrichedAlert(
            incident_id=alert.incident_id,
            alert_name=alert.alert_name,
            severity=alert.severity,
            status=alert.status,
            labels=alert.labels,
            annotations=alert.annotations,
            starts_at=alert.starts_at,
            ends_at=alert.ends_at,
            asset=None,
            is_enriched=False,
        )

        # Derive lookup key from labels
        lookup_key = self._derive_lookup_key(alert)

        if lookup_key is None:
            # Requirement 3.5: No lookup labels present
            logger.warning(
                "No lookup key could be derived for alert '%s' (incident: %s) - "
                "none of the labels [instance, hostname, job] are present or non-empty",
                alert.alert_name,
                alert.incident_id,
            )
            return enriched

        # Check timeout before lookup
        elapsed = time.monotonic() - start_time
        if elapsed >= ENRICHMENT_TIMEOUT_SECONDS:
            # Requirement 3.7: Timeout exceeded
            logger.warning(
                "Enrichment timeout exceeded for alert '%s' (incident: %s) "
                "before lookup could be performed (elapsed: %.3fs)",
                alert.alert_name,
                alert.incident_id,
                elapsed,
            )
            return enriched

        # Perform inventory lookup
        try:
            asset_data = self.inventory.lookup(lookup_key)
        except Exception as e:
            # Requirement 3.6: Inventory unreachable or error
            logger.error(
                "Asset inventory lookup failed for key '%s' (incident: %s): %s",
                lookup_key,
                alert.incident_id,
                e,
            )
            return enriched

        # Check timeout after lookup
        elapsed = time.monotonic() - start_time
        if elapsed >= ENRICHMENT_TIMEOUT_SECONDS:
            # Requirement 3.7: Timeout exceeded during lookup
            logger.warning(
                "Enrichment timeout exceeded for alert '%s' (incident: %s) "
                "after lookup (elapsed: %.3fs)",
                alert.alert_name,
                alert.incident_id,
                elapsed,
            )
            return enriched

        if asset_data is None:
            # Requirement 3.3: No matching asset found
            logger.warning(
                "No matching asset found for lookup key '%s' (incident: %s)",
                lookup_key,
                alert.incident_id,
            )
            return enriched

        # Build AssetInfo from the data
        try:
            asset_info = self._build_asset_info(asset_data)
        except ValueError as e:
            # Requirement 3.4: Corrupted data
            logger.warning(
                "Asset data corrupted for key '%s' (incident: %s): %s",
                lookup_key,
                alert.incident_id,
                e,
            )
            return enriched

        # Final timeout check
        elapsed = time.monotonic() - start_time
        if elapsed >= ENRICHMENT_TIMEOUT_SECONDS:
            logger.warning(
                "Enrichment timeout exceeded for alert '%s' (incident: %s) "
                "after building asset info (elapsed: %.3fs)",
                alert.alert_name,
                alert.incident_id,
                elapsed,
            )
            return enriched

        # Success: attach asset info
        enriched.asset = asset_info
        enriched.is_enriched = True

        return enriched
