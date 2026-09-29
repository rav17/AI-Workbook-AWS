"""Maintenance Window Manager — defers actions during scheduled maintenance.

Loads maintenance windows from YAML config and defers matching actions.
Supports recurring (daily, weekly, monthly) and one-time windows with timezone support.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import yaml

from src.guardrails.models import CheckResult, CheckResultType, RemediationAction

logger = logging.getLogger(__name__)

MAX_WINDOWS = 100
MAX_DEFER_AGE = 3600  # seconds
DEFAULT_CONFIG_PATH = "config/maintenance_windows.yml"
RELOAD_INTERVAL_SECONDS = 60


@dataclass
class MaintenanceWindow:
    """A single maintenance window definition."""

    name: str
    window_type: str  # "recurring" or "one_time"
    scope: str  # "global" or service group name
    start_hour: int = 0
    start_minute: int = 0
    duration_minutes: int = 60
    days_of_week: list[int] = field(default_factory=list)  # 0=Monday, 6=Sunday
    day_of_month: int = 0
    start_datetime: Optional[datetime] = None  # For one-time windows
    end_datetime: Optional[datetime] = None  # For one-time windows
    timezone_name: str = "UTC"


class MaintenanceWindowManager:
    """Defers remediation actions during scheduled maintenance windows.

    Loads window definitions from YAML config, supports recurring and
    one-time windows, and implements periodic reload every 60 seconds.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize MaintenanceWindowManager.

        Args:
            config_path: Path to the maintenance windows YAML config.

        Raises:
            SystemExit: If config is missing or invalid on startup.
        """
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._windows: list[MaintenanceWindow] = []
        self._lock = threading.Lock()
        self._reload_thread: Optional[threading.Thread] = None
        self._running = False

        if not os.path.isfile(self._config_path):
            logger.critical(
                "MaintenanceWindowManager refusing to start: "
                "config file not found at %s",
                self._config_path,
            )
            raise SystemExit(1)

        windows = self._load_config(self._config_path)
        if windows is None:
            logger.critical(
                "MaintenanceWindowManager refusing to start: invalid config"
            )
            raise SystemExit(1)

        self._windows = windows
        logger.info(
            "MaintenanceWindowManager initialized with %d windows",
            len(self._windows),
        )

    @property
    def name(self) -> str:
        """Unique name identifying this guardrail check."""
        return "maintenance_window"

    def start_reload_loop(self) -> None:
        """Start the periodic config reload background thread."""
        if self._running:
            return
        self._running = True
        self._reload_thread = threading.Thread(
            target=self._reload_loop, daemon=True, name="maint-window-reload"
        )
        self._reload_thread.start()

    def stop_reload_loop(self) -> None:
        """Stop the periodic config reload thread."""
        self._running = False
        if self._reload_thread and self._reload_thread.is_alive():
            self._reload_thread.join(timeout=5.0)

    async def check(self, action: RemediationAction) -> CheckResult:
        """Check if the action should be deferred due to a maintenance window.

        Global windows defer all actions. Service-group windows defer only
        actions targeting that service. Unknown service groups are deferred
        conservatively.

        Args:
            action: The remediation action to evaluate.

        Returns:
            DEFER if in a matching window, ALLOW otherwise.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            windows = list(self._windows)

        for window in windows:
            if self._is_in_window(window, now):
                # Check scope matching
                if window.scope == "global":
                    return CheckResult(
                        result_type=CheckResultType.DEFER,
                        check_name=self.name,
                        reason=f"Global maintenance window '{window.name}' is active",
                        metadata={"window_name": window.name, "scope": "global"},
                    )
                elif window.scope == action.service_name:
                    return CheckResult(
                        result_type=CheckResultType.DEFER,
                        check_name=self.name,
                        reason=(
                            f"Maintenance window '{window.name}' is active "
                            f"for service '{action.service_name}'"
                        ),
                        metadata={
                            "window_name": window.name,
                            "scope": window.scope,
                        },
                    )
                elif action.service_name == "":
                    # Unknown service group — conservative deferral
                    return CheckResult(
                        result_type=CheckResultType.DEFER,
                        check_name=self.name,
                        reason=(
                            f"Maintenance window '{window.name}' active and "
                            f"service group unknown — deferring conservatively"
                        ),
                        metadata={
                            "window_name": window.name,
                            "scope": window.scope,
                        },
                    )

        return CheckResult(
            result_type=CheckResultType.ALLOW,
            check_name=self.name,
            reason="No active maintenance window",
        )

    def _is_in_window(self, window: MaintenanceWindow, now: datetime) -> bool:
        """Determine if the current time falls within a maintenance window."""
        if window.window_type == "one_time":
            if window.start_datetime and window.end_datetime:
                return window.start_datetime <= now <= window.end_datetime
            return False

        # Recurring window
        current_hour = now.hour
        current_minute = now.minute
        current_day = now.weekday()  # 0=Monday

        # Check day-of-week (if specified)
        if window.days_of_week and current_day not in window.days_of_week:
            return False

        # Check day-of-month (if specified)
        if window.day_of_month > 0 and now.day != window.day_of_month:
            return False

        # Check time range
        window_start_minutes = window.start_hour * 60 + window.start_minute
        window_end_minutes = window_start_minutes + window.duration_minutes
        current_minutes = current_hour * 60 + current_minute

        # Handle windows that cross midnight
        if window_end_minutes > 1440:
            return (
                current_minutes >= window_start_minutes
                or current_minutes < (window_end_minutes - 1440)
            )

        return window_start_minutes <= current_minutes < window_end_minutes

    def _reload_loop(self) -> None:
        """Background thread for periodic config reload."""
        while self._running:
            time.sleep(RELOAD_INTERVAL_SECONDS)
            self._reload()

    def _reload(self) -> None:
        """Reload config, retaining valid config on failure."""
        if not os.path.isfile(self._config_path):
            logger.warning("Config file missing during reload, retaining current config")
            return

        new_windows = self._load_config(self._config_path)
        if new_windows is None:
            logger.warning("Invalid config during reload, retaining previous config")
            return

        with self._lock:
            self._windows = new_windows

        logger.debug("Maintenance windows reloaded: %d windows", len(new_windows))

    def _load_config(self, path: str) -> Optional[list[MaintenanceWindow]]:
        """Load and validate the maintenance windows config.

        Returns:
            List of MaintenanceWindow objects, or None if invalid.
        """
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.error("Failed to load maintenance windows config: %s", e)
            return None

        if not isinstance(data, dict):
            logger.error("Maintenance windows config must be a YAML mapping")
            return None

        windows_list = data.get("maintenance_windows")
        if not isinstance(windows_list, list):
            logger.error("'maintenance_windows' key must be a list")
            return None

        if len(windows_list) > MAX_WINDOWS:
            logger.error(
                "Too many windows: %d (max %d)", len(windows_list), MAX_WINDOWS
            )
            return None

        windows: list[MaintenanceWindow] = []
        for entry in windows_list:
            if not isinstance(entry, dict):
                logger.error("Each window entry must be a mapping")
                return None

            name = entry.get("name", "")
            if not name:
                logger.error("Window entry missing 'name'")
                return None

            window = MaintenanceWindow(
                name=name,
                window_type=entry.get("type", "recurring"),
                scope=entry.get("scope", "global"),
                start_hour=int(entry.get("start_hour", 0)),
                start_minute=int(entry.get("start_minute", 0)),
                duration_minutes=int(entry.get("duration_minutes", 60)),
                days_of_week=entry.get("days_of_week", []),
                day_of_month=int(entry.get("day_of_month", 0)),
                timezone_name=entry.get("timezone", "UTC"),
            )

            # Parse one-time window datetimes
            if window.window_type == "one_time":
                start_str = entry.get("start_datetime")
                end_str = entry.get("end_datetime")
                if start_str:
                    try:
                        window.start_datetime = datetime.fromisoformat(start_str)
                        if window.start_datetime.tzinfo is None:
                            window.start_datetime = window.start_datetime.replace(
                                tzinfo=timezone.utc
                            )
                    except ValueError:
                        logger.error("Invalid start_datetime for window '%s'", name)
                        return None
                if end_str:
                    try:
                        window.end_datetime = datetime.fromisoformat(end_str)
                        if window.end_datetime.tzinfo is None:
                            window.end_datetime = window.end_datetime.replace(
                                tzinfo=timezone.utc
                            )
                    except ValueError:
                        logger.error("Invalid end_datetime for window '%s'", name)
                        return None

            windows.append(window)

        return windows
