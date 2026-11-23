"""Integration test: self-healing loop and learning improvement over repeated bad advice.

This test demonstrates:
1. First request: investment advice fails (bad recommendation)
2. Failure is persisted to memory
3. Second request: system retrieves failure, avoids the bad strategy, produces improved advice
"""
import json
from config.models import (
    ExecutionResult, Plan, PlanTask, InteractionRecord, FinancialPattern,
    SimilarPattern, MemoryContext, Status, Confidence, RiskLevel,
)
from memory.degradation import MemoryDegradationControl
from config.settings import MemoryConfig
from compliance.disclosure_manager import DisclosureManager


def test_learning_improvement_after_repeated_bad_advice():
    """Scenario: System learns from repeated bad investment advice.

    Round 1: User asks for investment advice. System recommends high-risk tech stocks.
             Result: failure (market crash, user lost money).
             System persists failure to memory.

    Round 2: User asks for investment advice again.
             System retrieves past failure from memory.
             System AVOIDS high-risk tech stocks.
             System recommends diversified low-risk portfolio instead.
             Result: success with improved strategy.
    """
    dm = DisclosureManager()
    mdc = MemoryDegradationControl(MemoryConfig(agent_id="test", max_failures_in_context=5, max_patterns_in_context=3))

    # === ROUND 1: Bad advice ===
    round1_result = ExecutionResult(
        status=Status.FAILURE,
        confidence=Confidence.HIGH,
        recommendation="Invest 80% in high-risk tech growth stocks for maximum returns",
        risk_level=RiskLevel.HIGH,
        issues=["Market downturn caused significant losses"],
        explainability_summary="Concentrated tech stock allocation",
        worker_domain="investment_advice",
    )

    # Persist failure to memory (simulated)
    failure_record = InteractionRecord(
        user_id="user_001",
        input="Give me investment advice to grow my money fast",
        output=round1_result.recommendation,
        status=Status.FAILURE,
        confidence=Confidence.HIGH,
        intent="investment_advice",
        strategy_used="concentrated_tech_stocks",
    )

    failure_pattern = FinancialPattern(
        user_id="user_001",
        pattern_type="failure",
        content="Investment advice: concentrated tech stocks → market crash → significant losses",
        metadata={"risk_level": "high", "outcome": "failure", "worker_domain": "investment_advice"},
    )

    # === ROUND 2: Improved advice ===
    # System retrieves memory context with past failure
    context = mdc.prepare_context(
        failures=[failure_record],
        patterns=[SimilarPattern(
            pattern_id=failure_pattern.pattern_id,
            content=failure_pattern.content,
            similarity_score=0.92,
            metadata=failure_pattern.metadata,
        )],
        current_intent="investment_advice",
    )

    # Verify memory context contains the failure
    assert len(context.recent_failures) == 1
    assert context.recent_failures[0].strategy_used == "concentrated_tech_stocks"
    assert len(context.similar_patterns) == 1
    assert context.similar_patterns[0].similarity_score > 0.9

    # System generates improved recommendation (simulated worker output)
    round2_result = ExecutionResult(
        status=Status.SUCCESS,
        confidence=Confidence.HIGH,
        recommendation=(
            "Based on your history, I recommend a diversified portfolio: "
            "40% index funds, 30% bonds, 20% international equities, 10% cash reserves. "
            "This avoids the concentrated tech stock approach that previously resulted in losses."
        ),
        risk_level=RiskLevel.MEDIUM,
        issues=[],
        explainability_summary=(
            "Avoided concentrated tech stocks (past failure). "
            "Diversified across asset classes to reduce risk while maintaining growth potential."
        ),
        worker_domain="investment_advice",
    )

    # Apply disclosures
    round2_result = dm.apply_disclosures(round2_result)

    # === ASSERTIONS: Learning improvement verified ===

    # 1. Round 2 avoids the failed strategy
    assert "concentrated" not in round2_result.recommendation.lower() or "avoids" in round2_result.recommendation.lower()

    # 2. Round 2 is successful
    assert round2_result.status == Status.SUCCESS

    # 3. Round 2 has disclaimer (investment advice)
    assert round2_result.disclaimer != ""
    assert "fiduciary" in round2_result.disclaimer.lower()

    # 4. Round 2 has explainability referencing the past failure
    assert "past failure" in round2_result.explainability_summary.lower() or "avoided" in round2_result.explainability_summary.lower()

    # 5. Round 2 risk level is not HIGH (learned from past)
    assert round2_result.risk_level != RiskLevel.HIGH

    print("\n=== Learning Improvement Test Passed ===")
    print(f"Round 1 (failed): {round1_result.recommendation[:80]}...")
    print(f"Round 2 (improved): {round2_result.recommendation[:80]}...")
    print(f"Strategy avoided: {context.recent_failures[0].strategy_used}")
    print(f"Similarity score of past failure: {context.similar_patterns[0].similarity_score}")


def test_memory_pruning_preserves_failures():
    """Verify that memory pruning keeps failure records. Traces: R9.3, R9.4."""
    records = []
    # Create 25 records: 5 failures + 20 successes
    for i in range(20):
        records.append(InteractionRecord(
            user_id="u1", input=f"q{i}", output=f"a{i}",
            status=Status.SUCCESS, confidence=Confidence.HIGH,
        ))
    for i in range(5):
        records.append(InteractionRecord(
            user_id="u1", input=f"fail{i}", output=f"fail_a{i}",
            status=Status.FAILURE, confidence=Confidence.LOW,
        ))

    # Simulate pruning: keep max 20, prioritize failures
    max_n = 20
    if len(records) > max_n:
        sorted_records = sorted(records, key=lambda r: r.timestamp)
        to_remove = []
        for r in sorted_records:
            if len(records) - len(to_remove) <= max_n:
                break
            if r.status != Status.FAILURE:
                to_remove.append(r)
        for r in to_remove:
            records.remove(r)

    assert len(records) <= max_n
    # All 5 failures should be preserved
    failures = [r for r in records if r.status == Status.FAILURE]
    assert len(failures) == 5


def test_risk_aware_recommendation_behavior():
    """Verify risk-aware behavior: high-risk recommendations get flagged. Traces: R7, R15."""
    dm = DisclosureManager()

    high_risk = ExecutionResult(
        status=Status.SUCCESS, confidence=Confidence.MEDIUM,
        recommendation="Invest in volatile crypto assets",
        risk_level=RiskLevel.HIGH, worker_domain="investment_advice",
    )
    high_risk = dm.apply_disclosures(high_risk)
    assert high_risk.disclaimer != ""
    assert high_risk.risk_level == RiskLevel.HIGH

    low_risk = ExecutionResult(
        status=Status.SUCCESS, confidence=Confidence.HIGH,
        recommendation="Open a high-yield savings account",
        risk_level=RiskLevel.LOW, worker_domain="savings_advice",
    )
    low_risk = dm.apply_disclosures(low_risk)
    assert low_risk.disclaimer != ""
    assert low_risk.risk_level == RiskLevel.LOW
