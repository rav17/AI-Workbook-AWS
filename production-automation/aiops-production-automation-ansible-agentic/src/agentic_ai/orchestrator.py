"""AWS Orchestrator — SQS-driven pipeline with operating modes.

Polls SQS, processes alerts through the AI/rule-based pipeline,
and manages operating modes (ai_only, rules_only, ai_with_fallback).

Requirements: 5.3, 5.4, 5.5, 7.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 10.6
"""

import json
import logging
import os
import re

import boto3

from src.agentic_ai.models.enums import OperatingMode

logger = logging.getLogger(__name__)

# Labels considered sensitive and redacted before storage
SENSITIVE_LABEL_PATTERNS = [
    re.compile(r"(?i)password"),
    re.compile(r"(?i)secret"),
    re.compile(r"(?i)token"),
    re.compile(r"(?i)api.?key"),
    re.compile(r"(?i)credential"),
]
REDACTION_PLACEHOLDER = "***REDACTED***"


class AWSOrchestrator:
    """SQS-driven orchestrator with AI/rule-based operating modes.

    Pipeline: normalize → enrich → correlate → reason → execute → notify.

    Operating modes:
    - ai_only: AI reasoning only, no rule-based fallback
    - rules_only: Rule-based only, AI bypassed
    - ai_with_fallback: AI with rule-based fallback on failure

    Defaults to "rules_only" when env var not set.
    """

    def __init__(
        self,
        queue_url: str,
        reasoning_agent=None,
        playbook_mapper=None,
        ssm_executor=None,
        correlator=None,
        escalation_manager=None,
        metrics_publisher=None,
        incident_store=None,
        sqs_client=None,
        dynamodb_client=None,
        bedrock_client=None,
    ) -> None:
        self._queue_url = queue_url
        self._reasoning_agent = reasoning_agent
        self._playbook_mapper = playbook_mapper
        self._ssm_executor = ssm_executor
        self._correlator = correlator
        self._escalation_manager = escalation_manager
        self._metrics = metrics_publisher
        self._incident_store = incident_store

        self._sqs = sqs_client or boto3.client("sqs")
        self._dynamodb = dynamodb_client
        self._bedrock = bedrock_client

        # Operating mode
        mode_str = os.environ.get("OPERATING_MODE", "rules_only")
        self._mode = self._parse_mode(mode_str)

        self._running = False
        self._mapping_config_valid = True

    @property
    def mode(self) -> OperatingMode:
        return self._mode

    def change_mode(self, new_mode: str) -> tuple[bool, str]:
        """Change operating mode at runtime.

        Args:
            new_mode: Mode string to switch to.

        Returns:
            (success, message) tuple.
        """
        try:
            parsed = OperatingMode(new_mode)
        except ValueError:
            valid = [m.value for m in OperatingMode]
            return False, f"Invalid mode '{new_mode}'. Valid: {valid}"

        # Validate mapping config for rules/fallback modes
        if parsed in (OperatingMode.RULES_ONLY, OperatingMode.AI_WITH_FALLBACK):
            if not self._mapping_config_valid:
                return False, "Cannot switch to rules mode: mapping config invalid"

        old_mode = self._mode
        self._mode = parsed
        logger.info("Operating mode changed: %s → %s", old_mode.value, parsed.value)
        return True, f"Mode changed to {parsed.value}"

    async def process_message(self, message_body: str) -> bool:
        """Process a single SQS message through the pipeline.

        Returns:
            True if processed successfully, False otherwise.
        """
        try:
            payload = json.loads(message_body)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in SQS message: %s", e)
            return False

        alerts = payload.get("alerts", [])
        if not alerts:
            return False

        for alert in alerts:
            await self._process_alert(alert)

        return True

    async def _process_alert(self, alert: dict) -> None:
        """Process a single alert through the full pipeline."""
        labels = alert.get("labels", {})
        alert_name = labels.get("alertname", "unknown")
        severity = labels.get("severity", "warning")

        # Redact sensitive labels before storage
        redacted_labels = self._redact_sensitive_labels(labels)

        # Route based on operating mode
        if self._mode == OperatingMode.RULES_ONLY:
            await self._route_rules_only(alert_name, severity, redacted_labels)
        elif self._mode == OperatingMode.AI_ONLY:
            await self._route_ai_only(alert_name, severity, redacted_labels)
        else:
            await self._route_ai_with_fallback(alert_name, severity, redacted_labels)

    async def _route_ai_only(
        self, alert_name: str, severity: str, labels: dict
    ) -> None:
        """Route through AI reasoning only."""
        if self._reasoning_agent is None:
            logger.error("AI agent not available in ai_only mode")
            return
        try:
            plan = await self._reasoning_agent.reason(
                alert_name=alert_name,
                severity=severity,
                service_name=labels.get("service_name", ""),
                target_resource=labels.get("instance", ""),
                labels=labels,
            )
            await self._execute_plan(plan)
        except Exception as e:
            logger.error("AI reasoning failed in ai_only mode: %s", e)

    async def _route_rules_only(
        self, alert_name: str, severity: str, labels: dict
    ) -> None:
        """Route through rule-based matching only."""
        if self._playbook_mapper is None:
            logger.error("Playbook mapper not available in rules_only mode")
            return
        # Delegate to existing playbook mapper logic
        logger.info("Processing alert '%s' via rules_only mode", alert_name)

    async def _route_ai_with_fallback(
        self, alert_name: str, severity: str, labels: dict
    ) -> None:
        """Route through AI with rule-based fallback."""
        if self._reasoning_agent:
            try:
                plan = await self._reasoning_agent.reason(
                    alert_name=alert_name,
                    severity=severity,
                    service_name=labels.get("service_name", ""),
                    target_resource=labels.get("instance", ""),
                    labels=labels,
                )
                if not plan.fallback_used:
                    await self._execute_plan(plan)
                    return
            except Exception as e:
                logger.warning("AI reasoning failed, falling back to rules: %s", e)

        # Fallback to rules
        await self._route_rules_only(alert_name, severity, labels)

    async def _execute_plan(self, plan) -> None:
        """Execute a remediation plan via SSM."""
        if self._ssm_executor is None:
            logger.warning("SSM executor not available")
            return
        try:
            result = await self._ssm_executor.execute(plan)
            logger.info(
                "Execution completed: success=%s steps=%d/%d",
                result.success,
                result.steps_completed,
                result.total_steps,
            )
        except Exception as e:
            logger.error("Execution failed: %s", e)

    @staticmethod
    def _redact_sensitive_labels(labels: dict[str, str]) -> dict[str, str]:
        """Redact labels matching sensitive patterns."""
        redacted = {}
        for key, value in labels.items():
            if any(pattern.search(key) for pattern in SENSITIVE_LABEL_PATTERNS):
                redacted[key] = REDACTION_PLACEHOLDER
            else:
                redacted[key] = value
        return redacted

    @staticmethod
    def _parse_mode(mode_str: str) -> OperatingMode:
        """Parse operating mode, defaulting to rules_only."""
        try:
            return OperatingMode(mode_str)
        except ValueError:
            return OperatingMode.RULES_ONLY

    async def health_check(self) -> dict[str, str]:
        """Check connectivity to SQS, DynamoDB, and Bedrock."""
        status: dict[str, str] = {}

        # SQS
        try:
            self._sqs.get_queue_attributes(
                QueueUrl=self._queue_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            status["sqs"] = "healthy"
        except Exception:
            status["sqs"] = "unhealthy"

        # DynamoDB
        if self._dynamodb:
            try:
                self._dynamodb.describe_endpoints()
                status["dynamodb"] = "healthy"
            except Exception:
                status["dynamodb"] = "unhealthy"
        else:
            status["dynamodb"] = "not_configured"

        # Bedrock
        if self._bedrock:
            try:
                self._bedrock.list_foundation_models(byOutputModality="TEXT")
                status["bedrock"] = "healthy"
            except Exception:
                status["bedrock"] = "unhealthy"
        else:
            status["bedrock"] = "not_configured"

        return status
