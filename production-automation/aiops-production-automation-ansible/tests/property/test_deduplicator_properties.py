# Feature: execution-concurrency-safety, Property 4: Deduplication Metamorphic Bound
"""Property-based tests for the Alert Deduplicator component.

Property 4: Deduplication Metamorphic Bound
*For any* sequence of alerts within a Suppression_Window targeting the same
(hostname, alert_name) pair, the number of executions triggered SHALL be less
than or equal to the number of distinct severity escalations plus one.

**Validates: Requirements 2.1, 2.3, 2.6, 2.7**
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from src.alert_deduplicator import AlertDeduplicator
from src.models import Severity


# --- Hypothesis Strategies ---

# Strategy for generating a list of Severity values representing an alert sequence
severity_sequence_strategy = st.lists(
    st.sampled_from([Severity.P1, Severity.P2, Severity.P3]),
    min_size=1,
    max_size=50,
)

# Severity rank: P1=1 (highest), P2=2, P3=3 (lowest)
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.P1: 1,
    Severity.P2: 2,
    Severity.P3: 3,
}


def _is_escalation(incoming: Severity, previous: Severity) -> bool:
    """Check if incoming severity is strictly higher than previous.

    P1 > P2 > P3 (lower rank = higher severity).
    """
    return _SEVERITY_RANK[incoming] < _SEVERITY_RANK[previous]


# --- Property 4: Deduplication Metamorphic Bound ---


class TestDeduplicationMetamorphicBound:
    """Property tests for deduplication metamorphic bound (Property 4).

    **Validates: Requirements 2.1, 2.3, 2.6, 2.7**

    For any sequence of alerts within a Suppression_Window targeting the same
    (hostname, alert_name) pair, the number of executions triggered SHALL be
    less than or equal to the number of distinct severity escalations plus one.
    """

    @given(severity_sequence=severity_sequence_strategy)
    @settings(max_examples=100, deadline=5000)
    def test_executions_bounded_by_escalations_plus_one(
        self,
        severity_sequence: list[Severity],
    ) -> None:
        """The number of executions SHALL be ≤ severity escalations + 1.

        **Validates: Requirements 2.1, 2.3, 2.6, 2.7**

        Strategy:
        1. Generate a list of Severity values (P1, P2, P3) representing an alert sequence
        2. Create an AlertDeduplicator with a large suppression window (so nothing expires)
        3. Process each alert: if should_suppress() returns False, count as execution
           and call record_execution()
        4. Count severity escalations (where severity is strictly higher than the
           previous executed severity)
        5. Assert: executions <= severity_escalations + 1
        """
        # Use a very large suppression window so nothing expires during the test
        deduplicator = AlertDeduplicator(suppression_window=999999.0)

        hostname = "test-host"
        alert_name = "TestAlert"

        executions = 0
        severity_escalations = 0
        last_executed_severity: Severity | None = None

        for severity in severity_sequence:
            suppressed = deduplicator.should_suppress(hostname, alert_name, severity)

            if not suppressed:
                # Count this as an execution
                executions += 1

                # Count severity escalation (strictly higher than previous executed)
                if last_executed_severity is not None:
                    if _is_escalation(severity, last_executed_severity):
                        severity_escalations += 1

                # Record the execution to start/reset suppression window
                deduplicator.record_execution(hostname, alert_name, severity)
                last_executed_severity = severity

        # Property assertion: executions <= severity_escalations + 1
        assert executions <= severity_escalations + 1, (
            f"Executions ({executions}) exceeded severity_escalations + 1 "
            f"({severity_escalations + 1}). "
            f"Severity sequence: {[s.value for s in severity_sequence]}"
        )
