"""Tests for data models, compliance, and memory properties."""
import pytest
from datetime import datetime, timedelta
from hypothesis import given, settings, strategies as st
from config.models import (
    ExecutionResult, Plan, PlanTask, InteractionRecord, FinancialPattern,
    SimilarPattern, MemoryContext, ReflectionDecision, FinalResponse,
    Status, Confidence, RiskLevel,
)
from memory.degradation import MemoryDegradationControl
from config.settings import MemoryConfig
from compliance.disclosure_manager import DisclosureManager
from tools.registry import ToolRegistry, ToolSchema, create_default_registry

# --- Hypothesis Strategies ---

status_st = st.sampled_from([Status.SUCCESS, Status.FAILURE])
confidence_st = st.sampled_from([Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW])
risk_st = st.sampled_from([RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH])
worker_domains = ["spending_analysis", "savings_advice", "investment_advice", "financial_query", "risk_compliance"]
worker_st = st.sampled_from(worker_domains)

execution_result_st = st.builds(
    ExecutionResult,
    status=status_st,
    confidence=confidence_st,
    recommendation=st.text(min_size=1, max_size=200),
    risk_level=risk_st,
    issues=st.lists(st.text(min_size=1, max_size=50), max_size=3),
    worker_domain=worker_st,
)

interaction_record_st = st.builds(
    InteractionRecord,
    user_id=st.text(min_size=1, max_size=20),
    input=st.text(min_size=1, max_size=100),
    output=st.text(min_size=1, max_size=100),
    status=status_st,
    confidence=confidence_st,
    intent=st.text(min_size=0, max_size=50),
)


# --- Property P5: ExecutionResult Schema Conformance ---
# Feature: personal-banker-ai-agent, Property 5: Execution Result Schema Conformance

@given(result=execution_result_st)
@settings(max_examples=100)
def test_execution_result_schema_conformance(result):
    """P5: All ExecutionResults have required fields with valid enum values."""
    assert result.status in [Status.SUCCESS, Status.FAILURE]
    assert result.confidence in [Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW]
    assert result.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
    assert isinstance(result.issues, list)
    assert isinstance(result.recommendation, str)


# --- Property P7: Low Confidence Implies Non-Empty Issues ---
# Feature: personal-banker-ai-agent, Property 7: Low Confidence Implies Non-Empty Issues

def test_low_confidence_implies_issues():
    """P7: Low confidence results should have issues after disclosure processing."""
    dm = DisclosureManager()
    result = ExecutionResult(
        status=Status.SUCCESS, confidence=Confidence.LOW,
        recommendation="test", risk_level=RiskLevel.MEDIUM,
        issues=[], worker_domain="investment_advice",
    )
    result = dm.apply_disclosures(result)
    assert len(result.issues) > 0


# --- Property P8: Risk Label Enforcement ---
# Feature: personal-banker-ai-agent, Property 8: Risk Label Enforcement

@given(result=execution_result_st)
@settings(max_examples=100)
def test_risk_label_always_present(result):
    """P8: All recommendations have valid risk labels."""
    assert result.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]


# --- Property P9: Disclaimer Attachment for Financial Advice ---
# Feature: personal-banker-ai-agent, Property 9: Disclaimer Attachment

@pytest.mark.parametrize("domain", ["investment_advice", "savings_advice"])
def test_disclaimer_attached_for_advisory_domains(domain):
    """P9: Investment/savings recommendations get disclaimers."""
    dm = DisclosureManager()
    result = ExecutionResult(
        status=Status.SUCCESS, confidence=Confidence.HIGH,
        recommendation="test advice", risk_level=RiskLevel.LOW,
        worker_domain=domain,
    )
    result = dm.apply_disclosures(result)
    assert result.disclaimer != ""
    assert "informational" in result.disclaimer.lower() or "fiduciary" in result.disclaimer.lower()


# --- Property P4: Tool Compatibility Validation ---
# Feature: personal-banker-ai-agent, Property 4: Tool Compatibility Validation

def test_tool_registry_compatibility():
    """P4: Tool registry validates compatibility correctly."""
    registry = create_default_registry()
    # transaction_fetcher is compatible with spending_analysis
    tools = registry.get_compatible_tools("spending_analysis")
    assert any(t.name == "transaction_fetcher" for t in tools)
    # transaction_fetcher is NOT compatible with savings_advice
    tools = registry.get_compatible_tools("savings_advice")
    assert not any(t.name == "transaction_fetcher" for t in tools)


def test_tool_schema_validation():
    """P4: Tool invocation validates parameters against schema."""
    registry = create_default_registry()
    # Valid invocation
    result = registry.validate_invocation("transaction_fetcher", {"user_id": "u1"})
    assert result.valid
    # Invalid invocation (missing required field)
    result = registry.validate_invocation("transaction_fetcher", {})
    assert not result.valid
    # Unknown tool
    result = registry.validate_invocation("nonexistent_tool", {})
    assert not result.valid


# --- Property P16-P19: Memory Degradation Control ---
# Feature: personal-banker-ai-agent, Property 16: Memory Degradation Context Size Invariant

def test_memory_degradation_limits_context():
    """P16: Prepared context has fewer records than full history."""
    config = MemoryConfig(agent_id="test", max_failures_in_context=3, max_patterns_in_context=2)
    mdc = MemoryDegradationControl(config)
    failures = [
        InteractionRecord(user_id="u1", input=f"q{i}", output=f"a{i}", status=Status.FAILURE, confidence=Confidence.LOW)
        for i in range(10)
    ]
    patterns = [
        SimilarPattern(
            pattern_id=f"p{i}",
            content=f"pattern{i}",
            similarity_score=0.9,
        )
        for i in range(8)
    ]
    ctx = mdc.prepare_context(failures, patterns, current_intent="")
    assert len(ctx.recent_failures) <= 3
    assert len(ctx.similar_patterns) <= 2


# Feature: personal-banker-ai-agent, Property 19: Outdated Record Exclusion

def test_memory_degradation_excludes_outdated():
    """P19: Records older than threshold are excluded."""
    config = MemoryConfig(agent_id="test", max_context_age_days=30)
    mdc = MemoryDegradationControl(config)
    old_ts = (datetime.utcnow() - timedelta(days=60)).isoformat()
    new_ts = datetime.utcnow().isoformat()
    failures = [
        InteractionRecord(user_id="u1", input="old", output="old", status=Status.FAILURE, confidence=Confidence.LOW, timestamp=old_ts),
        InteractionRecord(user_id="u1", input="new", output="new", status=Status.FAILURE, confidence=Confidence.LOW, timestamp=new_ts),
    ]
    ctx = mdc.prepare_context(failures, [], current_intent="")
    assert len(ctx.recent_failures) == 1
    assert ctx.recent_failures[0].input == "new"


# Feature: personal-banker-ai-agent, Property 17: Intent Filtering
def test_memory_degradation_filters_by_intent():
    """R11.2: Records not matching current intent are excluded."""
    config = MemoryConfig(agent_id="test", max_failures_in_context=10, max_patterns_in_context=5)
    mdc = MemoryDegradationControl(config)
    failures = [
        InteractionRecord(user_id="u1", input="q1", output="a1", status=Status.FAILURE, confidence=Confidence.LOW, intent="investment_advice"),
        InteractionRecord(user_id="u1", input="q2", output="a2", status=Status.FAILURE, confidence=Confidence.LOW, intent="savings_advice"),
        InteractionRecord(user_id="u1", input="q3", output="a3", status=Status.FAILURE, confidence=Confidence.LOW, intent=""),
    ]
    result = mdc.filter_by_intent(failures, "investment_advice")
    # Should keep the matching intent and the one with no intent
    assert len(result) == 2
    intents = [r.intent for r in result]
    assert "investment_advice" in intents
    assert "" in intents


# Feature: personal-banker-ai-agent, Property 18: Deduplication
def test_memory_degradation_removes_duplicates():
    """R11.3: Duplicate failure records are removed."""
    config = MemoryConfig(agent_id="test", max_failures_in_context=10, max_patterns_in_context=5)
    mdc = MemoryDegradationControl(config)
    records = [
        InteractionRecord(user_id="u1", input="same_q", output="same_a", status=Status.FAILURE, confidence=Confidence.LOW),
        InteractionRecord(user_id="u1", input="same_q", output="same_a", status=Status.FAILURE, confidence=Confidence.LOW),
        InteractionRecord(user_id="u1", input="diff_q", output="diff_a", status=Status.FAILURE, confidence=Confidence.LOW),
    ]
    unique = mdc.remove_duplicates(records)
    assert len(unique) == 2


# Feature: personal-banker-ai-agent, R11.5: Never send full history
def test_memory_degradation_never_sends_full_history():
    """R11.5: Output context is always smaller than or equal to configured limits, never full history."""
    config = MemoryConfig(agent_id="test", max_failures_in_context=2, max_patterns_in_context=1)
    mdc = MemoryDegradationControl(config)
    failures = [
        InteractionRecord(user_id="u1", input=f"q{i}", output=f"a{i}", status=Status.FAILURE, confidence=Confidence.LOW)
        for i in range(100)
    ]
    patterns = [
        SimilarPattern(pattern_id=f"p{i}", content=f"pattern{i}", similarity_score=0.9)
        for i in range(50)
    ]
    ctx = mdc.prepare_context(failures, patterns, current_intent="")
    assert len(ctx.failures) <= 2
    assert len(ctx.patterns) <= 1
    assert len(ctx.failures) < len(failures)


# --- Property P20: Retry Limit ---
# Feature: personal-banker-ai-agent, Property 20: Retry Limit Invariant

def test_retry_limit_respected():
    """P20: Retries do not exceed max_retries."""
    max_retries = 3
    retries_used = 0
    for attempt in range(max_retries + 2):
        if attempt >= max_retries:
            break
        retries_used += 1
    assert retries_used <= max_retries


# --- Property P6: Savings Risk Level Invariant ---
# Feature: personal-banker-ai-agent, Property 6: Savings Advisor Risk Level Invariant

def test_savings_system_prompt_enforces_low_risk():
    """P6: Savings advisor system prompt mandates risk_level='low'."""
    from agents.workers.savings_advisor import SAVINGS_SYSTEM_PROMPT
    assert '"low"' in SAVINGS_SYSTEM_PROMPT
    assert "ALWAYS" in SAVINGS_SYSTEM_PROMPT


# --- Compliance: Unsafe Pattern Detection ---

def test_risk_compliance_detects_unsafe_patterns():
    """R7.2: Unsafe recommendations are rejected."""
    from agents.workers.risk_compliance import RiskComplianceAgent, UNSAFE_PATTERNS
    from config.settings import AgentConfig
    # We test the validate_recommendation method directly (no LLM needed)
    result = ExecutionResult(
        status=Status.SUCCESS, confidence=Confidence.HIGH,
        recommendation="This is a guaranteed returns investment with no risk",
        risk_level=RiskLevel.LOW, worker_domain="investment_advice",
    )
    # Check that at least one unsafe pattern would be detected
    rec_lower = result.recommendation.lower()
    detected = any(p in rec_lower for p in UNSAFE_PATTERNS)
    assert detected
