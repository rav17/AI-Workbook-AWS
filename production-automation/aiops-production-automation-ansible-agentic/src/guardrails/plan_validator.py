"""AI Remediation Plan Validator.

Validates AI-generated remediation plans against safety rules before
allowing execution. Blocks dangerous commands, enforces parameter
bounds, and rate-limits AI-generated actions.

Inspired by Amazon Bedrock Guardrails 'denied topics' pattern.
"""

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import yaml

from src.guardrails.models import CheckResult, CheckResultType, RemediationAction
from src.guardrails.interfaces import GuardrailCheck

logger = logging.getLogger(__name__)

DENIED_COMMANDS_CONFIG_PATH = os.environ.get(
    "DENIED_COMMANDS_CONFIG_PATH", "config/denied_commands.yml"
)


@dataclass
class DeniedPattern:
    """A pattern that should never appear in a remediation plan."""

    pattern: str
    reason: str
    compiled: Optional[re.Pattern] = field(default=None, repr=False)

    def __post_init__(self):
        try:
            self.compiled = re.compile(self.pattern, re.IGNORECASE)
        except re.error as e:
            logger.warning("Invalid denied pattern '%s': %s", self.pattern, e)
            self.compiled = None


@dataclass
class ParameterBounds:
    """Safety bounds for remediation plan parameters."""

    max_timeout_seconds: int = 600
    max_target_hosts: int = 5
    max_plan_steps: int = 10
    max_ai_executions_per_host_per_hour: int = 3


class PlanValidator(GuardrailCheck):
    """Validates AI-generated remediation plans against safety rules.

    This check runs ONLY for actions flagged as ai_generated=True.
    Rule-based playbook matches are NOT subject to plan validation
    (they are pre-vetted by the ops team).
    """

    def __init__(self, config_path: str = DENIED_COMMANDS_CONFIG_PATH) -> None:
        self._config_path = config_path
        self._denied_patterns: list[DeniedPattern] = []
        self._parameter_bounds = ParameterBounds()
        self._action_allowlist: list[str] = []
        self._allowlist_enabled: bool = False
        self._ai_execution_tracker: dict[str, list[float]] = {}  # host -> [timestamps]
        self._load_config()

    @property
    def name(self) -> str:
        return "plan_validator"

    def _load_config(self) -> None:
        """Load denied patterns and parameter bounds from YAML config."""
        if not os.path.isfile(self._config_path):
            logger.info("No plan validator config at %s — using defaults", self._config_path)
            self._load_default_patterns()
            return

        try:
            with open(self._config_path, "r") as f:
                data = yaml.safe_load(f) or {}

            # Load denied patterns
            for entry in data.get("denied_patterns", []):
                self._denied_patterns.append(
                    DeniedPattern(
                        pattern=entry.get("pattern", ""),
                        reason=entry.get("reason", "Denied by safety policy"),
                    )
                )

            # Load parameter bounds
            bounds = data.get("parameter_bounds", {})
            self._parameter_bounds = ParameterBounds(
                max_timeout_seconds=bounds.get("max_timeout_seconds", 600),
                max_target_hosts=bounds.get("max_target_hosts", 5),
                max_plan_steps=bounds.get("max_plan_steps", 10),
                max_ai_executions_per_host_per_hour=bounds.get(
                    "max_ai_executions_per_host_per_hour", 3
                ),
            )

            # Load action allowlist
            self._allowlist_enabled = data.get("action_allowlist_enabled", False)
            self._action_allowlist = data.get("action_allowlist", [])

            logger.info(
                "Loaded plan validator: %d denied patterns, allowlist=%s",
                len(self._denied_patterns),
                "enabled" if self._allowlist_enabled else "disabled",
            )
        except Exception as e:
            logger.warning("Failed to load plan validator config: %s — using defaults", e)
            self._load_default_patterns()

    def _load_default_patterns(self) -> None:
        """Load built-in safety patterns when no config is available."""
        defaults = [
            DeniedPattern(pattern=r"rm\s+(-rf?\s+)?/", reason="Recursive delete of root"),
            DeniedPattern(pattern=r"shutdown|halt|poweroff|init\s+0", reason="Host shutdown"),
            DeniedPattern(pattern=r"dd\s+if=", reason="Raw disk write"),
            DeniedPattern(pattern=r"mkfs|format", reason="Filesystem creation"),
            DeniedPattern(pattern=r"iptables\s+-F|iptables.*DROP", reason="Firewall flush"),
            DeniedPattern(pattern=r"systemctl\s+(disable|mask)", reason="Permanent service disable"),
        ]
        self._denied_patterns = defaults

    async def check(self, action: RemediationAction) -> CheckResult:
        """Validate the remediation action against safety rules.

        Only applies to AI-generated plans. Rule-based matches pass through.
        """
        # Skip validation for non-AI-generated actions (rule-based playbooks)
        if not action.ai_generated:
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason="Rule-based action — plan validation skipped",
            )

        # Check 1: Denied command patterns
        violation = self._check_denied_patterns(action)
        if violation:
            return violation

        # Check 2: Action allowlist (if enabled)
        if self._allowlist_enabled:
            if action.action_name not in self._action_allowlist:
                return CheckResult(
                    result_type=CheckResultType.DENY,
                    check_name=self.name,
                    reason=f"Action '{action.action_name}' not in allowlist",
                )

        # Check 3: Rate limiting per host
        rate_violation = self._check_rate_limit(action)
        if rate_violation:
            return rate_violation

        # All validations passed
        self._record_execution(action)
        return CheckResult(
            result_type=CheckResultType.ALLOW,
            check_name=self.name,
            reason="AI plan validation passed",
        )

    def _check_denied_patterns(self, action: RemediationAction) -> Optional[CheckResult]:
        """Check action against denied command patterns."""
        # Build text to scan: action name + playbook path + extra vars values
        text_to_scan = " ".join([
            action.action_name,
            action.playbook_path,
            " ".join(str(v) for v in action.extra_vars.values()),
        ])

        for pattern in self._denied_patterns:
            if pattern.compiled and pattern.compiled.search(text_to_scan):
                logger.warning(
                    "AI plan DENIED by safety rule: %s (incident=%s, pattern=%s)",
                    pattern.reason,
                    action.incident_id,
                    pattern.pattern,
                )
                return CheckResult(
                    result_type=CheckResultType.DENY,
                    check_name=self.name,
                    reason=f"Blocked by safety rule: {pattern.reason}",
                    metadata={"denied_pattern": pattern.pattern},
                )

        return None

    def _check_rate_limit(self, action: RemediationAction) -> Optional[CheckResult]:
        """Check AI execution rate limit per host."""
        host = action.target_host
        now = time.time()
        one_hour_ago = now - 3600

        # Clean old entries
        if host in self._ai_execution_tracker:
            self._ai_execution_tracker[host] = [
                ts for ts in self._ai_execution_tracker[host] if ts > one_hour_ago
            ]
        else:
            self._ai_execution_tracker[host] = []

        # Check limit
        recent_count = len(self._ai_execution_tracker.get(host, []))
        max_allowed = self._parameter_bounds.max_ai_executions_per_host_per_hour

        if recent_count >= max_allowed:
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason=(
                    f"AI execution rate limit exceeded for host '{host}': "
                    f"{recent_count}/{max_allowed} per hour"
                ),
            )

        return None

    def _record_execution(self, action: RemediationAction) -> None:
        """Record an AI execution for rate limiting."""
        host = action.target_host
        if host not in self._ai_execution_tracker:
            self._ai_execution_tracker[host] = []
        self._ai_execution_tracker[host].append(time.time())
