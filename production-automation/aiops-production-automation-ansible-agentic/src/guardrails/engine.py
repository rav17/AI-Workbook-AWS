"""Guardrail Engine — orchestrates all seven checks in fixed order.

Evaluates remediation actions through ordered checks with
short-circuit semantics and 15-second overall timeout.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Coroutine, Optional

from src.guardrails.interfaces import GuardrailCheck
from src.guardrails.models import (
    CheckResult,
    CheckResultType,
    GuardrailDecision,
    GuardrailDecisionType,
    RemediationAction,
)

logger = logging.getLogger(__name__)

EVALUATION_TIMEOUT_SECONDS = 15
NOTIFICATION_TIMEOUT_SECONDS = 30


class GuardrailEngine:
    """Orchestrates all guardrail checks in a fixed evaluation order.

    Evaluation order:
    1. Self-Protection
    2. Maintenance Window
    3. Circuit Breaker
    4. Concurrency Guard
    5. Blast Radius Classifier
    6. Health Checker
    7. Approval Gate

    Short-circuits on the first non-ALLOW result.
    15-second overall timeout results in DENY.
    Exceptions from individual checks result in DENY.
    """

    def __init__(
        self,
        checks: list[GuardrailCheck],
        notify_func: Optional[Callable[..., Coroutine]] = None,
    ) -> None:
        """Initialize GuardrailEngine.

        Args:
            checks: Ordered list of guardrail checks.
            notify_func: Async callable for dispatching notifications
                on DENY/DEFER decisions.
        """
        self._checks = checks
        self._notify_func = notify_func

    async def evaluate(
        self, action: RemediationAction, skip_approval: bool = False
    ) -> GuardrailDecision:
        """Evaluate a remediation action through all guardrail checks.

        Executes checks in order with short-circuit semantics.
        15-second overall timeout results in DENY with "guardrail_timeout".

        Args:
            action: The remediation action to evaluate.
            skip_approval: If True, skip the Approval Gate check (used when
                action was already approved by a human via email link).
                All other 6 safety checks still evaluate.

        Returns:
            GuardrailDecision with the final outcome.
        """
        start_time = time.time()
        checks_passed: list[str] = []

        try:
            result = await asyncio.wait_for(
                self._run_checks(action, checks_passed, skip_approval),
                timeout=EVALUATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            decision = GuardrailDecision(
                decision_type=GuardrailDecisionType.DENY,
                action=action,
                checks_passed=checks_passed,
                denying_check="guardrail_timeout",
                reason="Guardrail evaluation timed out after 15 seconds",
                evaluation_duration_seconds=duration,
                timestamp=datetime.now(timezone.utc),
            )
            self._log_decision(decision)
            await self._dispatch_notification(decision)
            return decision

        duration = time.time() - start_time
        decision = self._build_decision(action, result, checks_passed, duration)
        self._log_decision(decision)

        if decision.decision_type != GuardrailDecisionType.ALLOW:
            await self._dispatch_notification(decision)

        return decision

    async def _run_checks(
        self,
        action: RemediationAction,
        checks_passed: list[str],
        skip_approval: bool = False,
    ) -> CheckResult:
        """Run all checks sequentially with short-circuit on non-ALLOW.

        Args:
            action: The remediation action to evaluate.
            checks_passed: Accumulator for passed check names.
            skip_approval: If True, skip any check named 'approval_gate'.
        """
        for check in self._checks:
            # Skip approval gate if the action was pre-approved by human
            if skip_approval and check.name == "approval_gate":
                checks_passed.append(f"{check.name}(skipped:pre_approved)")
                continue

            result = await self._run_check(check, action)
            if result.result_type != CheckResultType.ALLOW:
                return result
            checks_passed.append(check.name)

        # All checks passed
        return CheckResult(
            result_type=CheckResultType.ALLOW,
            check_name="all",
            reason="All guardrail checks passed",
        )

    async def _run_check(
        self, check: GuardrailCheck, action: RemediationAction
    ) -> CheckResult:
        """Run a single check with error isolation.

        Any exception from a check results in DENY.
        """
        try:
            return await check.check(action)
        except Exception as e:
            logger.error(
                "Guardrail check '%s' raised exception: %s",
                check.name,
                str(e),
            )
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=check.name,
                reason=f"Internal error in check '{check.name}': {e}",
            )

    def _build_decision(
        self,
        action: RemediationAction,
        result: CheckResult,
        checks_passed: list[str],
        duration: float,
    ) -> GuardrailDecision:
        """Build a GuardrailDecision from the check result."""
        if result.result_type == CheckResultType.ALLOW:
            return GuardrailDecision(
                decision_type=GuardrailDecisionType.ALLOW,
                action=action,
                checks_passed=checks_passed,
                reason=result.reason,
                evaluation_duration_seconds=duration,
                timestamp=datetime.now(timezone.utc),
            )
        elif result.result_type == CheckResultType.DEFER:
            return GuardrailDecision(
                decision_type=GuardrailDecisionType.DEFER,
                action=action,
                checks_passed=checks_passed,
                denying_check=result.check_name,
                reason=result.reason,
                evaluation_duration_seconds=duration,
                timestamp=datetime.now(timezone.utc),
            )
        else:
            return GuardrailDecision(
                decision_type=GuardrailDecisionType.DENY,
                action=action,
                checks_passed=checks_passed,
                denying_check=result.check_name,
                reason=result.reason,
                evaluation_duration_seconds=duration,
                timestamp=datetime.now(timezone.utc),
            )

    def _log_decision(self, decision: GuardrailDecision) -> None:
        """Log structured JSON audit entry for the evaluation."""
        log_entry = {
            "event": "guardrail_evaluation",
            "incident_id": decision.action.incident_id,
            "decision": decision.decision_type.value,
            "checks_passed": decision.checks_passed,
            "denying_check": decision.denying_check,
            "reason": decision.reason,
            "duration_seconds": round(decision.evaluation_duration_seconds, 3),
            "target_host": decision.action.target_host,
            "action_name": decision.action.action_name,
            "risk_level": (
                decision.action.risk_level.value
                if decision.action.risk_level
                else None
            ),
            "timestamp": decision.timestamp.isoformat(),
        }

        if decision.decision_type == GuardrailDecisionType.ALLOW:
            logger.info(json.dumps(log_entry))
        else:
            logger.warning(json.dumps(log_entry))

    async def _dispatch_notification(self, decision: GuardrailDecision) -> None:
        """Dispatch notification on DENY/DEFER within 30 seconds."""
        if self._notify_func is None:
            return

        try:
            await asyncio.wait_for(
                self._notify_func(decision),
                timeout=NOTIFICATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Notification dispatch timed out for incident %s",
                decision.action.incident_id,
            )
        except Exception as e:
            logger.error(
                "Failed to dispatch notification for incident %s: %s",
                decision.action.incident_id,
                e,
            )

    async def record_outcome(self, action: RemediationAction, success: bool) -> None:
        """Record outcome for circuit breaker and concurrency tracking.

        Should be called after execution completes.
        """
        # Find circuit breaker and concurrency guard in checks
        for check in self._checks:
            if hasattr(check, "record_success") and hasattr(check, "record_failure"):
                if success:
                    check.record_success()
                else:
                    check.record_failure()
                break

    async def release_action(self, action: RemediationAction) -> None:
        """Release concurrency slot for the action.

        Should be called after execution completes.
        """
        for check in self._checks:
            if hasattr(check, "release"):
                await check.release(action)
                break
