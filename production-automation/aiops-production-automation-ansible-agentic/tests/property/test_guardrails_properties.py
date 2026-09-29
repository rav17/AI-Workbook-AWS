"""Property-based tests for the Safe Execution Guardrails module.

Validates universal correctness properties using Hypothesis.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.guardrails.models import (
    CheckResult,
    CheckResultType,
    GuardrailDecisionType,
    RemediationAction,
    RiskLevel,
)
from src.guardrails.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from src.guardrails.classifier import BlastRadiusClassifier
from src.guardrails.engine import GuardrailEngine

pytestmark = pytest.mark.property


# --- Property 1: Classification always produces exactly one valid RiskLevel ---


@given(
    service_name=st.text(min_size=1, max_size=50),
    action_name=st.text(min_size=1, max_size=50),
    environment=st.sampled_from(["dev", "staging", "prod"]),
)
@settings(max_examples=100)
def test_classification_totality(service_name, action_name, environment):
    """Property 1: Classification always produces exactly one valid RiskLevel."""
    classifier = BlastRadiusClassifier(config_path="/nonexistent")
    action = RemediationAction(
        incident_id="test-001",
        action_name=action_name,
        target_host="host-1",
        service_name=service_name,
        environment=environment,
    )
    result = asyncio.run(classifier.check(action))
    assert result.result_type == CheckResultType.ALLOW
    assert action.risk_level is not None
    assert action.risk_level in list(RiskLevel)


# --- Property 4: Production environment elevates risk by exactly one level ---


@given(
    service_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
    action_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
)
@settings(max_examples=100)
def test_production_elevation(service_name, action_name):
    """Property 4: Production environment elevates risk by exactly one level."""
    classifier = BlastRadiusClassifier(config_path="/nonexistent")

    # Classify in non-prod
    action_dev = RemediationAction(
        incident_id="test-dev",
        action_name=action_name,
        target_host="host-1",
        service_name=service_name,
        environment="dev",
    )
    asyncio.run(classifier.check(action_dev))
    dev_risk = action_dev.risk_level

    # Classify in prod
    action_prod = RemediationAction(
        incident_id="test-prod",
        action_name=action_name,
        target_host="host-1",
        service_name=service_name,
        environment="prod",
    )
    asyncio.run(classifier.check(action_prod))
    prod_risk = action_prod.risk_level

    # Prod should be elevated by one level (capped at CRITICAL)
    assert prod_risk == dev_risk.elevate()


# --- Property 5: Unknown service/playbook defaults to high ---


@given(
    service_name=st.text(min_size=10, max_size=30, alphabet=st.characters(whitelist_categories=("L",))),
    action_name=st.text(min_size=10, max_size=30, alphabet=st.characters(whitelist_categories=("L",))),
)
@settings(max_examples=100)
def test_unknown_defaults_to_high(service_name, action_name):
    """Property 5: Unknown service or playbook defaults to high."""
    # Use a config with no rules
    classifier = BlastRadiusClassifier(config_path="/nonexistent")
    action = RemediationAction(
        incident_id="test-001",
        action_name=action_name,
        target_host="host-1",
        service_name=service_name,
        environment="dev",
    )
    asyncio.run(classifier.check(action))
    # Without config and non-prod, should be HIGH
    assert action.risk_level == RiskLevel.HIGH


# --- Property 13: Circuit breaker opens on threshold breach ---


@given(
    failure_count=st.integers(min_value=1, max_value=50),
    threshold=st.integers(min_value=1, max_value=50),
)
@settings(max_examples=100)
def test_circuit_breaker_threshold_breach(failure_count, threshold):
    """Property 13: Circuit breaker opens on threshold breach."""
    config = CircuitBreakerConfig(failure_threshold=threshold, window_seconds=300)
    cb = CircuitBreaker(config=config)

    for _ in range(failure_count):
        cb.record_failure()

    if failure_count >= threshold:
        assert cb.state == CircuitState.OPEN
    else:
        assert cb.state == CircuitState.CLOSED


# --- Property 14: Open circuit breaker denies all actions ---


@given(threshold=st.integers(min_value=1, max_value=10))
@settings(max_examples=100)
def test_open_circuit_breaker_denies(threshold):
    """Property 14: Open circuit breaker denies all actions."""
    config = CircuitBreakerConfig(
        failure_threshold=threshold, cooldown_seconds=1800
    )
    cb = CircuitBreaker(config=config)

    # Force open
    for _ in range(threshold):
        cb.record_failure()

    assert cb.state == CircuitState.OPEN

    action = RemediationAction(
        incident_id="test", action_name="restart", target_host="host-1"
    )
    result = asyncio.run(cb.check(action))
    assert result.result_type == CheckResultType.DENY


# --- Property 15: Circuit breaker config validation clamps to defaults ---


@given(
    failure_threshold=st.integers(min_value=-100, max_value=200),
    window_seconds=st.integers(min_value=-100, max_value=10000),
    cooldown_seconds=st.integers(min_value=-100, max_value=5000),
)
@settings(max_examples=100)
def test_circuit_breaker_config_clamping(failure_threshold, window_seconds, cooldown_seconds):
    """Property 15: Circuit breaker config validation clamps to defaults."""
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        window_seconds=window_seconds,
        cooldown_seconds=cooldown_seconds,
    )
    # All values should be within valid ranges
    assert 1 <= config.failure_threshold <= 50
    assert 30 <= config.window_seconds <= 3600
    assert 10 <= config.cooldown_seconds <= 1800


# --- Property 19: Evaluation short-circuits on non-ALLOW result ---


@given(deny_at_index=st.integers(min_value=0, max_value=4))
@settings(max_examples=100)
def test_evaluation_short_circuits(deny_at_index):
    """Property 19: Evaluation short-circuits on non-ALLOW result."""
    checks = []

    for i in range(5):
        mock_check = AsyncMock()
        mock_check.name = f"check_{i}"

        if i == deny_at_index:
            mock_check.check = AsyncMock(return_value=CheckResult(
                result_type=CheckResultType.DENY,
                check_name=f"check_{i}",
                reason="test deny",
            ))
        else:
            mock_check.check = AsyncMock(return_value=CheckResult(
                result_type=CheckResultType.ALLOW,
                check_name=f"check_{i}",
            ))
        checks.append(mock_check)

    engine = GuardrailEngine(checks=checks)
    action = RemediationAction(
        incident_id="test", action_name="test", target_host="host-1"
    )
    decision = asyncio.run(engine.evaluate(action))

    assert decision.decision_type == GuardrailDecisionType.DENY
    # Checks after the denying one should NOT have been called
    for i in range(deny_at_index + 1, 5):
        checks[i].check.assert_not_called()


# --- Property 22: Internal check errors result in DENY ---


@given(error_msg=st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_internal_errors_result_in_deny(error_msg):
    """Property 22: Internal check errors result in DENY."""
    mock_check = AsyncMock()
    mock_check.name = "failing_check"
    mock_check.check = AsyncMock(side_effect=RuntimeError(error_msg))

    engine = GuardrailEngine(checks=[mock_check])
    action = RemediationAction(
        incident_id="test", action_name="test", target_host="host-1"
    )
    decision = asyncio.run(engine.evaluate(action))

    assert decision.decision_type == GuardrailDecisionType.DENY
    assert decision.denying_check == "failing_check"
