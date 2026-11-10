"""Regression tests: the guardrail engine must actually be wired in at startup.

Previously ConcurrencyGuard()/HealthChecker() raised TypeError, the error was
logged as "non-fatal", and the service ran with NO guardrail checks at all.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.guardrails.engine import GuardrailEngine
from src.guardrails.models import GuardrailDecisionType, RemediationAction

pytestmark = pytest.mark.unit

EXPECTED_CHECKS = [
    "self_protection",
    "maintenance_window",
    "circuit_breaker",
    "blast_radius_classifier",
    "approval_gate",
    "plan_validator",
]


def _engine() -> GuardrailEngine:
    import src.app as app

    engine = app.orchestrator._guardrail_engine
    assert engine is not None, "guardrail engine was not wired into the orchestrator"
    return engine


def test_engine_is_wired_with_expected_checks_in_order() -> None:
    names = [c.name for c in _engine()._checks]
    assert names == EXPECTED_CHECKS


def test_classifier_runs_before_approval_gate() -> None:
    names = [c.name for c in _engine()._checks]
    assert names.index("blast_radius_classifier") < names.index("approval_gate")


def _action(**overrides) -> RemediationAction:
    values = dict(
        incident_id="inc-1",
        action_name="fix_high_cpu.yml",
        target_host="i-0123456789abcdef0",
        service_name="web-frontend",
        playbook_path="playbooks/fix_high_cpu.yml",
        severity="critical",
        pre_approved=True,
    )
    values.update(overrides)
    return RemediationAction(**values)


def test_protected_host_is_denied_by_the_live_engine() -> None:
    decision = asyncio.run(
        _engine().evaluate(_action(target_host="vault-primary.internal"), skip_approval=True)
    )
    assert decision.decision_type == GuardrailDecisionType.DENY
    assert decision.denying_check == "self_protection"


def test_without_human_approval_high_risk_is_denied_by_approval_gate() -> None:
    """Unattended mode stays fail-safe: HIGH risk needs an approval channel."""
    from src.guardrails.maintenance_window import MaintenanceWindowManager

    engine = _engine()
    # Make the result independent of the wall clock (maintenance windows).
    window = next(c for c in engine._checks if isinstance(c, MaintenanceWindowManager))
    original = window.check
    window.check = AsyncMock(return_value=MagicMock(
        result_type=__import__("src.guardrails.models", fromlist=["CheckResultType"])
        .CheckResultType.ALLOW, check_name="maintenance_window", reason="", metadata={},
    ))
    try:
        decision = asyncio.run(engine.evaluate(_action(pre_approved=False), skip_approval=False))
    finally:
        window.check = original
    assert decision.decision_type == GuardrailDecisionType.DENY
    assert decision.denying_check == "approval_gate"


def test_orchestrator_skips_inprocess_approval_gate_when_email_approval_is_on() -> None:
    from tests.unit.test_human_approval_gate import _alert, _build

    orchestrator, executor, _ = _build(require_human_approval=True)
    engine = MagicMock()
    engine.evaluate = AsyncMock(return_value=MagicMock(
        decision_type=GuardrailDecisionType.ALLOW, reason="", denying_check=""
    ))
    orchestrator._guardrail_engine = engine

    asyncio.run(orchestrator._run_pipeline(_alert()))

    assert engine.evaluate.await_args.kwargs["skip_approval"] is True
    executor.execute.assert_not_called()
