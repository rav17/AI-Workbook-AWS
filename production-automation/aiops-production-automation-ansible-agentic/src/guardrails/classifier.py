"""Blast Radius Classifier — classifies risk level of remediation actions.

Applies classification rules in priority order:
single-instance override → database override → rule match →
environment elevation → default to HIGH.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
"""

import logging
import os
import threading
import time
from typing import Optional

import yaml

from src.guardrails.models import (
    CheckResult,
    CheckResultType,
    RemediationAction,
    RiskLevel,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config/risk_classification.yml"
CLASSIFICATION_TIMEOUT_SECONDS = 2.0


class BlastRadiusClassifier:
    """Classifies remediation actions by blast radius risk level.

    Classification logic priority:
    1. Single-instance services → CRITICAL
    2. Database restart/stop → CRITICAL
    3. Rule match from config
    4. Production environment elevation (one level up)
    5. Default to HIGH for unknown
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._rules: list[dict] = []
        self._single_instance_services: list[str] = []
        self._database_services: list[str] = []
        self._lock = threading.Lock()

        if os.path.isfile(self._config_path):
            config = self._load_config(self._config_path)
            if config is not None:
                self._apply_config(config)
            else:
                logger.warning(
                    "Invalid risk classification config, defaulting all to HIGH"
                )
        else:
            logger.warning(
                "Risk classification config not found at %s, "
                "defaulting all to HIGH",
                self._config_path,
            )

    @property
    def name(self) -> str:
        return "blast_radius_classifier"

    async def check(self, action: RemediationAction) -> CheckResult:
        """Classify the action and set its risk_level.

        Always returns ALLOW (classification is informational).
        The risk_level is set on the action object for downstream checks.
        """
        start = time.time()
        risk = self._classify(action)
        action.risk_level = risk
        duration = time.time() - start

        if duration > CLASSIFICATION_TIMEOUT_SECONDS:
            logger.warning(
                "Classification took %.2fs (exceeds 2s limit)", duration
            )

        return CheckResult(
            result_type=CheckResultType.ALLOW,
            check_name=self.name,
            reason=f"Classified as {risk.value}",
            metadata={"risk_level": risk.value},
        )

    def _classify(self, action: RemediationAction) -> RiskLevel:
        """Internal classification logic."""
        with self._lock:
            single_instance = list(self._single_instance_services)
            database_services = list(self._database_services)
            rules = list(self._rules)

        # Priority 1: Single-instance services → CRITICAL
        if action.service_name.lower() in [s.lower() for s in single_instance]:
            return RiskLevel.CRITICAL

        # Priority 2: Database restart/stop → CRITICAL
        action_lower = action.action_name.lower()
        is_db = action.service_name.lower() in [s.lower() for s in database_services]
        if is_db and any(kw in action_lower for kw in ("restart", "stop")):
            return RiskLevel.CRITICAL

        # Priority 3: Rule match from config
        matched_risk = self._match_rules(action, rules)
        if matched_risk is not None:
            risk = matched_risk
        else:
            # Priority 5: Default to HIGH for unknown
            risk = RiskLevel.HIGH

        # Priority 4: Production environment elevation
        if action.environment.lower() == "prod":
            risk = risk.elevate()

        return risk

    def _match_rules(
        self, action: RemediationAction, rules: list[dict]
    ) -> Optional[RiskLevel]:
        """Match action against configured rules."""
        for rule in rules:
            service_pattern = rule.get("service", "").lower()
            action_pattern = rule.get("action", "").lower()
            risk_str = rule.get("risk_level", "high").lower()

            service_match = (
                not service_pattern
                or service_pattern == "*"
                or service_pattern == action.service_name.lower()
            )
            action_match = (
                not action_pattern
                or action_pattern == "*"
                or action_pattern == action.action_name.lower()
            )

            if service_match and action_match:
                try:
                    return RiskLevel(risk_str)
                except ValueError:
                    return RiskLevel.HIGH

        return None

    def reload(self) -> bool:
        """Hot-reload configuration. Retains valid config on failure."""
        if not os.path.isfile(self._config_path):
            logger.warning("Config file missing during reload")
            return False

        config = self._load_config(self._config_path)
        if config is None:
            logger.warning("Invalid config during reload, retaining previous")
            return False

        self._apply_config(config)
        return True

    def _apply_config(self, config: dict) -> None:
        """Apply parsed config to internal state."""
        with self._lock:
            self._rules = config.get("rules", [])
            self._single_instance_services = config.get(
                "single_instance_services", []
            )
            self._database_services = config.get("database_services", [])

    def _load_config(self, path: str) -> Optional[dict]:
        """Load and validate the risk classification config."""
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.error("Failed to load risk classification config: %s", e)
            return None

        if not isinstance(data, dict):
            logger.error("Risk classification config must be a YAML mapping")
            return None

        return data
