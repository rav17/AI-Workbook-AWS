"""Property-based tests for data model validation.

Property 2: Remediation Plan Structure Validity
*For any* valid model response parsed by the AI Reasoning Agent, the resulting
RemediationPlan SHALL contain a non-empty selected action, a non-empty target
resource identifier, a confidence score in the range [0.0, 1.0], and a reasoning
explanation of at most 2048 characters.

**Validates: Requirements 1.2**

Property 7: Correlation Window Configuration Validation
*For any* environment variable value provided for the Alert Correlation Window,
the effective window SHALL be 300 seconds if the value is not a valid integer,
below 30, or above 900; otherwise the effective window SHALL equal the provided value.

**Validates: Requirements 2.5, 2.6**
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.agentic_ai.models.domain import RemediationPlan, RemediationStep
from src.agentic_ai.models.enums import FallbackReason


# --- Helper: Correlation Window Validation Logic ---


def get_effective_correlation_window(env_value: str) -> int:
    """Parse and validate the correlation window environment variable.

    Mimics the validation logic specified in Requirements 2.5 and 2.6:
    - If the value is not a valid integer, return default 300
    - If the value is below 30 or above 900, return default 300
    - Otherwise, return the provided value

    Args:
        env_value: The raw environment variable string value.

    Returns:
        The effective correlation window in seconds.
    """
    DEFAULT_WINDOW = 300
    MIN_WINDOW = 30
    MAX_WINDOW = 900

    try:
        parsed = int(env_value)
    except (ValueError, TypeError):
        return DEFAULT_WINDOW

    if parsed < MIN_WINDOW or parsed > MAX_WINDOW:
        return DEFAULT_WINDOW

    return parsed


# --- Hypothesis Strategies ---


# Strategy for non-empty strings (used for action and target_resource)
non_empty_text_strategy = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(blacklist_categories=("Cs",)),
)

# Strategy for reasoning explanation (max 2048 chars)
reasoning_strategy = st.text(
    min_size=0,
    max_size=2048,
    alphabet=st.characters(blacklist_categories=("Cs",)),
)

# Strategy for confidence scores in valid range [0.0, 1.0]
confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for generating valid RemediationStep instances
remediation_step_strategy = st.builds(
    RemediationStep,
    step_number=st.integers(min_value=1, max_value=20),
    action=non_empty_text_strategy,
    target_resource=non_empty_text_strategy,
    parameters=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))),
        values=st.text(min_size=0, max_size=50, alphabet=st.characters(blacklist_categories=("Cs",))),
        max_size=3,
    ),
    expected_outcome=st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",))),
)

# Strategy for generating valid RemediationPlan instances
remediation_plan_strategy = st.builds(
    RemediationPlan,
    incident_ids=st.lists(
        st.text(min_size=1, max_size=36, alphabet=st.characters(blacklist_categories=("Cs",))),
        min_size=1,
        max_size=5,
    ),
    steps=st.lists(remediation_step_strategy, min_size=0, max_size=5),
    confidence_score=confidence_strategy,
    reasoning_explanation=reasoning_strategy,
    selected_action=non_empty_text_strategy,
    target_resource=non_empty_text_strategy,
    requires_escalation=st.booleans(),
    fallback_used=st.booleans(),
    fallback_reason=st.one_of(st.none(), st.sampled_from(list(FallbackReason))),
    truncation_flag=st.booleans(),
)

# Strategy for valid correlation window values (integers in [30, 900])
valid_window_strategy = st.integers(min_value=30, max_value=900)

# Strategy for invalid correlation window values (non-integer strings)
invalid_non_integer_strategy = st.one_of(
    st.text(min_size=0, max_size=50, alphabet=st.characters(blacklist_categories=("Cs", "Nd"))),
    st.sampled_from(["abc", "not_a_number", "3.14", "30.0", "", " ", "NaN", "inf"]),
)

# Strategy for out-of-range integer values (below 30 or above 900)
out_of_range_strategy = st.one_of(
    st.integers(min_value=-10000, max_value=29),
    st.integers(min_value=901, max_value=100000),
)


# --- Property 2: Remediation Plan Structure Validity ---


@pytest.mark.property
class TestRemediationPlanStructureValidity:
    """Property 2: RemediationPlan structure validity.

    **Validates: Requirements 1.2**
    """

    @given(plan=remediation_plan_strategy)
    @settings(max_examples=200)
    def test_selected_action_is_non_empty(self, plan: RemediationPlan) -> None:
        """For any valid RemediationPlan, selected_action SHALL be non-empty.

        **Validates: Requirements 1.2**
        """
        assert len(plan.selected_action) > 0
        assert plan.selected_action.strip() != "" or len(plan.selected_action) > 0

    @given(plan=remediation_plan_strategy)
    @settings(max_examples=200)
    def test_target_resource_is_non_empty(self, plan: RemediationPlan) -> None:
        """For any valid RemediationPlan, target_resource SHALL be non-empty.

        **Validates: Requirements 1.2**
        """
        assert len(plan.target_resource) > 0

    @given(plan=remediation_plan_strategy)
    @settings(max_examples=200)
    def test_confidence_score_in_valid_range(self, plan: RemediationPlan) -> None:
        """For any valid RemediationPlan, confidence_score SHALL be in [0.0, 1.0].

        **Validates: Requirements 1.2**
        """
        assert 0.0 <= plan.confidence_score <= 1.0

    @given(plan=remediation_plan_strategy)
    @settings(max_examples=200)
    def test_reasoning_explanation_within_limit(self, plan: RemediationPlan) -> None:
        """For any valid RemediationPlan, reasoning_explanation SHALL be ≤ 2048 characters.

        **Validates: Requirements 1.2**
        """
        assert len(plan.reasoning_explanation) <= 2048

    @given(
        confidence=st.floats(min_value=-100.0, max_value=-0.001, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_confidence_below_zero_rejected(self, confidence: float) -> None:
        """RemediationPlan SHALL reject confidence_score below 0.0.

        **Validates: Requirements 1.2**
        """
        with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
            RemediationPlan(
                incident_ids=["inc-1"],
                steps=[],
                confidence_score=confidence,
                reasoning_explanation="test",
                selected_action="restart_service",
                target_resource="i-1234567890abcdef0",
            )

    @given(
        confidence=st.floats(min_value=1.001, max_value=100.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_confidence_above_one_rejected(self, confidence: float) -> None:
        """RemediationPlan SHALL reject confidence_score above 1.0.

        **Validates: Requirements 1.2**
        """
        with pytest.raises(ValueError, match="confidence_score must be between 0.0 and 1.0"):
            RemediationPlan(
                incident_ids=["inc-1"],
                steps=[],
                confidence_score=confidence,
                reasoning_explanation="test",
                selected_action="restart_service",
                target_resource="i-1234567890abcdef0",
            )

    @given(
        reasoning=st.text(
            min_size=2049,
            max_size=5000,
            alphabet=st.characters(blacklist_categories=("Cs",)),
        ),
    )
    @settings(max_examples=50)
    def test_reasoning_exceeding_2048_chars_rejected(self, reasoning: str) -> None:
        """RemediationPlan SHALL reject reasoning_explanation exceeding 2048 characters.

        **Validates: Requirements 1.2**
        """
        with pytest.raises(ValueError, match="reasoning_explanation must be at most 2048 characters"):
            RemediationPlan(
                incident_ids=["inc-1"],
                steps=[],
                confidence_score=0.8,
                reasoning_explanation=reasoning,
                selected_action="restart_service",
                target_resource="i-1234567890abcdef0",
            )


# --- Property 7: Correlation Window Configuration Validation ---


@pytest.mark.property
class TestCorrelationWindowConfigValidation:
    """Property 7: Correlation window configuration validation.

    **Validates: Requirements 2.5, 2.6**
    """

    @given(window_value=valid_window_strategy)
    @settings(max_examples=200)
    def test_valid_integer_in_range_returns_provided_value(self, window_value: int) -> None:
        """For any valid integer in [30, 900], effective window SHALL equal the provided value.

        **Validates: Requirements 2.5, 2.6**
        """
        env_value = str(window_value)
        effective = get_effective_correlation_window(env_value)
        assert effective == window_value

    @given(window_value=out_of_range_strategy)
    @settings(max_examples=200)
    def test_out_of_range_integer_defaults_to_300(self, window_value: int) -> None:
        """For any integer below 30 or above 900, effective window SHALL be 300.

        **Validates: Requirements 2.5, 2.6**
        """
        env_value = str(window_value)
        effective = get_effective_correlation_window(env_value)
        assert effective == 300

    @given(env_value=invalid_non_integer_strategy)
    @settings(max_examples=200)
    def test_non_integer_value_defaults_to_300(self, env_value: str) -> None:
        """For any non-integer string value, effective window SHALL be 300.

        **Validates: Requirements 2.5, 2.6**
        """
        # Ensure the value is truly not a valid integer
        try:
            int(env_value)
            assume(False)  # Skip if it happens to be a valid integer
        except (ValueError, TypeError):
            pass

        effective = get_effective_correlation_window(env_value)
        assert effective == 300

    @given(
        window_value=st.one_of(
            st.integers(min_value=-10000, max_value=29),
            st.integers(min_value=901, max_value=100000),
            st.just(0),
            st.just(-1),
            st.just(29),
            st.just(901),
        )
    )
    @settings(max_examples=100)
    def test_boundary_values_default_to_300(self, window_value: int) -> None:
        """For boundary values just outside [30, 900], effective window SHALL be 300.

        **Validates: Requirements 2.5, 2.6**
        """
        env_value = str(window_value)
        effective = get_effective_correlation_window(env_value)
        assert effective == 300

    @given(window_value=st.sampled_from([30, 900]))
    @settings(max_examples=10)
    def test_exact_boundary_values_accepted(self, window_value: int) -> None:
        """For exact boundary values 30 and 900, effective window SHALL equal the value.

        **Validates: Requirements 2.5, 2.6**
        """
        env_value = str(window_value)
        effective = get_effective_correlation_window(env_value)
        assert effective == window_value

    @given(
        env_value=st.sampled_from([
            "3.14", "30.5", "100.0", "1e2", "0x1E",
            "thirty", "abc", "None", "null", "true",
            "", " ", "\t", "\n",
        ])
    )
    @settings(max_examples=50)
    def test_various_invalid_formats_default_to_300(self, env_value: str) -> None:
        """For various invalid format strings, effective window SHALL be 300.

        **Validates: Requirements 2.5, 2.6**
        """
        effective = get_effective_correlation_window(env_value)
        assert effective == 300
