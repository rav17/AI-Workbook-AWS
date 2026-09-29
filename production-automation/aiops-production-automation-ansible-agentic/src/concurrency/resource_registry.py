"""YAML-configured registry of action-to-resource mappings for conflict detection."""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import yaml

from src.concurrency.enums import ConflictResolutionStrategy
from src.concurrency.models import ResourceConflict

logger = logging.getLogger(__name__)

_MAX_RESOURCES_PER_ACTION = 20
_MAX_RESOURCE_CATEGORY_LENGTH = 128
_RELOAD_CHECK_INTERVAL = 30  # seconds


@dataclass
class ActionResourceConfig:
    """Configuration for a single action's resource declarations."""

    resources: list[str] = field(default_factory=list)
    strategies: dict[str, ConflictResolutionStrategy] = field(default_factory=dict)


class ResourceConflictRegistry:
    """YAML-configured registry of action-to-resource mappings.

    Supports runtime reload within 30 seconds of file modification.
    """

    def __init__(self) -> None:
        self._actions: dict[str, ActionResourceConfig] = {}
        self._config_path: Optional[str] = None
        self._last_loaded_mtime: float = 0.0
        self._last_check_time: float = 0.0

    def load_from_yaml(self, path: str) -> None:
        """Load resource conflict configuration from a YAML file.

        If the file is malformed or fails validation, retains the
        previous valid configuration.
        """
        self._config_path = path

        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            logger.error("Failed to load resource conflict config from %s: %s", path, e)
            return

        if not isinstance(data, dict) or "actions" not in data:
            logger.error(
                "Invalid resource conflict config: missing 'actions' key in %s", path
            )
            return

        new_actions: dict[str, ActionResourceConfig] = {}

        for action_name, action_data in data["actions"].items():
            if not isinstance(action_data, dict):
                logger.error(
                    "Invalid config for action '%s': expected dict", action_name
                )
                return

            resources = action_data.get("resources", [])
            if not isinstance(resources, list):
                logger.error(
                    "Invalid 'resources' for action '%s': expected list", action_name
                )
                return

            if len(resources) > _MAX_RESOURCES_PER_ACTION:
                logger.error(
                    "Action '%s' exceeds max resources (%d > %d)",
                    action_name,
                    len(resources),
                    _MAX_RESOURCES_PER_ACTION,
                )
                return

            for r in resources:
                if not isinstance(r, str) or len(r) > _MAX_RESOURCE_CATEGORY_LENGTH:
                    logger.error(
                        "Invalid resource category '%s' for action '%s'", r, action_name
                    )
                    return

            strategies_raw = action_data.get("strategies", {})
            strategies: dict[str, ConflictResolutionStrategy] = {}
            for resource_cat, strategy_str in strategies_raw.items():
                try:
                    strategies[resource_cat] = ConflictResolutionStrategy(strategy_str)
                except ValueError:
                    logger.error(
                        "Invalid strategy '%s' for resource '%s' in action '%s'",
                        strategy_str,
                        resource_cat,
                        action_name,
                    )
                    return

            new_actions[action_name] = ActionResourceConfig(
                resources=resources, strategies=strategies
            )

        # Validation passed — apply new config
        self._actions = new_actions
        self._last_loaded_mtime = os.path.getmtime(path) if os.path.exists(path) else 0.0
        logger.info(
            "Loaded resource conflict config with %d actions from %s",
            len(new_actions),
            path,
        )

    def _check_reload(self) -> None:
        """Check if the config file has been modified and reload if needed."""
        if not self._config_path:
            return

        now = time.time()
        if now - self._last_check_time < _RELOAD_CHECK_INTERVAL:
            return
        self._last_check_time = now

        try:
            current_mtime = os.path.getmtime(self._config_path)
            if current_mtime > self._last_loaded_mtime:
                logger.info("Resource conflict config changed, reloading")
                self.load_from_yaml(self._config_path)
        except OSError:
            pass

    def get_resource_categories(self, action_name: str) -> list[str]:
        """Get the resource categories for an action.

        Returns empty list if the action is not registered.
        """
        self._check_reload()
        config = self._actions.get(action_name)
        if config is None:
            return []
        return config.resources

    def get_resolution_strategy(
        self, action_name: str, resource_category: str
    ) -> ConflictResolutionStrategy:
        """Get the conflict resolution strategy for a resource category.

        Defaults to QUEUE if no specific strategy is configured.
        """
        self._check_reload()
        config = self._actions.get(action_name)
        if config is None:
            return ConflictResolutionStrategy.QUEUE
        return config.strategies.get(resource_category, ConflictResolutionStrategy.QUEUE)

    def detect_conflicts(
        self,
        action_name: str,
        host: str,
        active_executions: dict[str, list[str]],
    ) -> list[ResourceConflict]:
        """Detect resource conflicts between a submitted action and active executions.

        Args:
            action_name: The submitted action name.
            host: The target host.
            active_executions: Map of incident_id → list of resource categories
                for currently executing actions on the same host.

        Returns:
            List of detected ResourceConflict objects.
        """
        self._check_reload()

        my_resources = set(self.get_resource_categories(action_name))
        if not my_resources:
            # Action has no declared resources — no conflicts
            if action_name not in self._actions:
                logger.warning(
                    "Action '%s' not registered in Resource Conflict Registry", action_name
                )
            return []

        conflicts: list[ResourceConflict] = []

        for blocking_id, blocking_resources in active_executions.items():
            overlap = my_resources & set(blocking_resources)
            if overlap:
                # Determine resolution strategy (use the most restrictive)
                strategies = [
                    self.get_resolution_strategy(action_name, cat) for cat in overlap
                ]
                # PREEMPT > REJECT > QUEUE (most restrictive wins)
                priority_order = {
                    ConflictResolutionStrategy.PREEMPT: 3,
                    ConflictResolutionStrategy.REJECT: 2,
                    ConflictResolutionStrategy.QUEUE: 1,
                }
                strategy = max(strategies, key=lambda s: priority_order[s])

                conflicts.append(
                    ResourceConflict(
                        conflicting_categories=sorted(overlap),
                        blocking_incident_id=blocking_id,
                        blocking_action_name="",  # Caller fills this in
                        resolution_strategy=strategy,
                    )
                )

        return conflicts

    def is_registered(self, action_name: str) -> bool:
        """Check if an action is registered in the registry."""
        self._check_reload()
        return action_name in self._actions
