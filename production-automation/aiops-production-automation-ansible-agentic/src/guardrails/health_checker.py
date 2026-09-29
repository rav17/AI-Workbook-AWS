"""Health Checker — verifies peer instance health before remediation.

Queries health of peer instances to ensure sufficient capacity
remains before allowing a remediation action.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import asyncio
import logging

from src.guardrails.interfaces import ServiceRegistry
from src.guardrails.models import (
    CheckResult,
    CheckResultType,
    RemediationAction,
    RiskLevel,
)

logger = logging.getLogger(__name__)

PER_PEER_TIMEOUT = 5.0  # seconds
OVERALL_TIMEOUT = 10.0  # seconds
MIN_HEALTHY_PEERS = 2


class HealthChecker:
    """Verifies peer instance health before allowing remediation.

    Decision logic:
    - Single instance → DENY for critical/high risk
    - All peers unhealthy → DENY + escalation
    - < 2 healthy peers → DENY for critical, ALLOW with warning for others
    - Timeout → DENY for high/critical, ALLOW with warning for low/medium
    """

    def __init__(self, service_registry: ServiceRegistry) -> None:
        self._service_registry = service_registry

    @property
    def name(self) -> str:
        return "health_checker"

    async def check(self, action: RemediationAction) -> CheckResult:
        """Check peer health before allowing remediation."""
        if not action.service_name:
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason="No service name — skipping health check",
            )

        risk = action.risk_level or RiskLevel.HIGH

        try:
            healthy_peers = await asyncio.wait_for(
                self._service_registry.get_healthy_instances(action.service_name),
                timeout=OVERALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                return CheckResult(
                    result_type=CheckResultType.DENY,
                    check_name=self.name,
                    reason="Health check timed out for high/critical risk action",
                )
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason="Health check timed out — allowing low/medium risk",
                metadata={"warning": "health_check_timeout"},
            )
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                return CheckResult(
                    result_type=CheckResultType.DENY,
                    check_name=self.name,
                    reason=f"Health check error: {e}",
                )
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason="Health check error — allowing low/medium risk",
            )

        # Exclude target host from healthy peers count
        target = action.target_host.lower()
        remaining_healthy = [
            p for p in healthy_peers if p.lower() != target
        ]
        total_peers = len(healthy_peers)

        # Single instance — DENY for critical/high
        if total_peers <= 1:
            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                return CheckResult(
                    result_type=CheckResultType.DENY,
                    check_name=self.name,
                    reason="Single instance service — denying high/critical action",
                    metadata={"total_peers": "1"},
                )
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason="Single instance — allowing low/medium risk",
            )

        # All peers unhealthy — DENY + escalation
        if len(remaining_healthy) == 0:
            return CheckResult(
                result_type=CheckResultType.DENY,
                check_name=self.name,
                reason="All peer instances unhealthy — escalation required",
                metadata={"escalation": "true"},
            )

        # < 2 healthy peers
        if len(remaining_healthy) < MIN_HEALTHY_PEERS:
            if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                return CheckResult(
                    result_type=CheckResultType.DENY,
                    check_name=self.name,
                    reason=(
                        f"Only {len(remaining_healthy)} healthy peer(s) "
                        f"remaining — denying critical/high"
                    ),
                )
            return CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=self.name,
                reason=(
                    f"Only {len(remaining_healthy)} healthy peer(s) "
                    f"— allowing with warning"
                ),
                metadata={"warning": "low_peer_count"},
            )

        return CheckResult(
            result_type=CheckResultType.ALLOW,
            check_name=self.name,
            reason=f"{len(remaining_healthy)} healthy peers available",
        )
