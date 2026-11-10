"""Unit tests for the human approval gate in the Orchestrator pipeline.

Regression test for the approval bypass found in the dev end-to-end test:
the pipeline executed the matched playbook immediately and only afterwards
sent the "approval" email, so the human approval had no effect.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.audit_logger import AuditLogger
from src.enricher import Enricher
from src.executor import RemediationExecutor
from src.metrics import MetricsCollector
from src.models import (
    AlertStatus,
    EnrichedAlert,
    ExecutionResult,
    NormalizedAlert,
    PlaybookMatch,
    RemediationStatus,
    Severity,
)
from src.normalizer import Normalizer
from src.notification import NotificationDispatcher
from src.orchestrator import Orchestrator
from src.playbook_mapper import PlaybookMapper

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


def _alert() -> NormalizedAlert:
    return NormalizedAlert(
        incident_id="inc-approval-1",
        alert_name="HighCPUUsage",
        severity=Severity.P1,
        status=AlertStatus.FIRING,
        labels={"alertname": "HighCPUUsage", "instance": "i-0123456789abcdef0"},
        annotations={},
        starts_at=_NOW,
        ends_at=None,
    )


def _build(require_human_approval: bool) -> tuple[Orchestrator, AsyncMock, MagicMock]:
    """Build an orchestrator whose mapper always matches a playbook."""
    alert = _alert()
    enricher = MagicMock(spec=Enricher)
    enricher.enrich.return_value = EnrichedAlert(
        incident_id=alert.incident_id,
        alert_name=alert.alert_name,
        severity=alert.severity,
        status=alert.status,
        labels=alert.labels,
        annotations=alert.annotations,
        starts_at=alert.starts_at,
        ends_at=None,
    )
    mapper = MagicMock(spec=PlaybookMapper)
    mapper.match.return_value = PlaybookMatch(
        rule_name="high-cpu-any",
        playbook_path="playbooks/fix_high_cpu.yml",
        matched_attributes=1,
    )
    executor = AsyncMock(spec=RemediationExecutor)
    executor.execute.return_value = ExecutionResult(
        status=RemediationStatus.SUCCESS,
        return_code=0,
        stdout="ok",
        stderr="",
        duration_seconds=1.0,
        playbook_path="playbooks/fix_high_cpu.yml",
        target_host="i-0123456789abcdef0",
    )
    audit_logger = MagicMock(spec=AuditLogger)
    orchestrator = Orchestrator(
        normalizer=MagicMock(spec=Normalizer),
        enricher=enricher,
        mapper=mapper,
        executor=executor,
        dispatcher=AsyncMock(spec=NotificationDispatcher),
        audit_logger=audit_logger,
        metrics_collector=MagicMock(spec=MetricsCollector),
        require_human_approval=require_human_approval,
    )
    return orchestrator, executor, audit_logger


def _audit_statuses(audit_logger: MagicMock) -> list[str]:
    return [c.args[0].notification_status for c in audit_logger.log_incident.call_args_list]


class TestHumanApprovalGate:
    """The pipeline must not execute a matched playbook until a human approves."""

    def test_approval_required_does_not_execute(self) -> None:
        orchestrator, executor, audit_logger = _build(require_human_approval=True)

        incident_id = asyncio.run(orchestrator._run_pipeline(_alert()))

        assert incident_id == "inc-approval-1"
        executor.execute.assert_not_called()
        assert _audit_statuses(audit_logger) == ["awaiting_approval"]

    def test_approval_not_required_executes(self) -> None:
        orchestrator, executor, audit_logger = _build(require_human_approval=False)

        asyncio.run(orchestrator._run_pipeline(_alert()))

        executor.execute.assert_awaited_once()
        assert "awaiting_approval" not in _audit_statuses(audit_logger)

    def test_guardrail_deny_still_wins_over_approval(self) -> None:
        """A guardrail DENY must stop the pipeline before the approval stage."""
        from src.guardrails.models import GuardrailDecisionType

        orchestrator, executor, audit_logger = _build(require_human_approval=True)
        engine = MagicMock()
        engine.evaluate = AsyncMock(
            return_value=MagicMock(
                decision_type=GuardrailDecisionType.DENY,
                reason="protected host",
                denying_check="self_protection",
            )
        )
        orchestrator._guardrail_engine = engine

        asyncio.run(orchestrator._run_pipeline(_alert()))

        executor.execute.assert_not_called()
        assert _audit_statuses(audit_logger) == ["guardrail_deny:self_protection"]


class TestRequireHumanApprovalEnv:
    """REQUIRE_HUMAN_APPROVAL parsing is fail-safe (approval stays ON by default)."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, True),
            ("true", True),
            ("TRUE", True),
            ("yes", True),
            ("tru", True),  # typo keeps the gate on
            ("", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ],
    )
    def test_parsing(self, monkeypatch, value, expected) -> None:
        from src.app import _require_human_approval

        if value is None:
            monkeypatch.delenv("REQUIRE_HUMAN_APPROVAL", raising=False)
        else:
            monkeypatch.setenv("REQUIRE_HUMAN_APPROVAL", value)
        assert _require_human_approval() is expected
