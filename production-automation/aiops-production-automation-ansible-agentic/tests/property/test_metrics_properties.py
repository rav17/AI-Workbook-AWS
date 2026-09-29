# Feature: self-healing-infrastructure, Property 29: Monotonically increasing counters
# Feature: self-healing-infrastructure, Property 30: Prometheus exposition format
"""Property-based tests for the MetricsCollector component.

Property 29: Monotonically increasing counters
*For any* sequence of alert processing events, each metric counter SHALL only increase
(never decrease) and SHALL increment by exactly 1 for each corresponding event.

**Validates: Requirements 11.1**

Property 30: Prometheus exposition format
*For any* state of the metrics collector, the rendered output SHALL conform to the
Prometheus exposition format with correct metric names, labels (alert name, severity),
and counter values.

**Validates: Requirements 11.2**
"""

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from src.metrics import MetricsCollector


# --- Hypothesis Strategies ---


def alert_name_strategy():
    """Generate alert names that may contain special characters.
    
    Excludes characters that would break Prometheus label value parsing
    when not properly escaped: { and } (brace delimiters).
    The MetricsCollector escapes \\, ", and \\n but not braces.
    """
    return st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            whitelist_characters="_-./",
            blacklist_characters="{}",
        ),
        min_size=0,
        max_size=50,
    )


def severity_strategy():
    """Generate severity values including known and unknown values.
    
    Excludes characters that would break Prometheus label value parsing
    when not properly escaped: { and } (brace delimiters).
    """
    return st.one_of(
        st.sampled_from(["P1", "P2", "P3", "critical", "warning", "info"]),
        st.text(
            min_size=0,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                whitelist_characters="_-",
            ),
        ),
    )


def increment_action_strategy():
    """Generate a sequence of increment actions to apply to the collector.

    Each action is a tuple of (method_name, alert_name, severity).
    """
    method_names = st.sampled_from([
        "increment_alerts_received",
        "increment_remediation_success",
        "increment_remediation_failure",
        "increment_remediation_timeout",
        "increment_no_playbook_match",
        "increment_notification_failure",
    ])
    return st.tuples(method_names, alert_name_strategy(), severity_strategy())


def increment_actions_strategy(min_size: int = 0, max_size: int = 30):
    """Generate a list of increment actions."""
    return st.lists(
        increment_action_strategy(),
        min_size=min_size,
        max_size=max_size,
    )


# --- Helper Functions ---


def apply_actions(collector: MetricsCollector, actions: list[tuple[str, str, str]]) -> None:
    """Apply a list of increment actions to a MetricsCollector."""
    for method_name, alert_name, severity in actions:
        method = getattr(collector, method_name)
        method(alert_name=alert_name, severity=severity)


# Prometheus exposition format patterns
# A HELP comment line
HELP_LINE_PATTERN = re.compile(r'^# HELP ([a-zA-Z_:][a-zA-Z0-9_:]*) (.+)$')
# A TYPE comment line
TYPE_LINE_PATTERN = re.compile(r'^# TYPE ([a-zA-Z_:][a-zA-Z0-9_:]*) (counter|gauge|histogram|summary|untyped)$')
# A metric line pattern: metric_name{labels} value
# This handles escaped characters in label values (e.g., \", \\, \n)
METRIC_LINE_PATTERN = re.compile(
    r'^([a-zA-Z_:][a-zA-Z0-9_:]*)\{((?:[^}\\]|\\.)*)\}\s+(\d+(?:\.\d+)?)$'
)
# Label pair pattern: key="value" (value may contain escaped chars like \", \\, \n)
LABEL_PAIR_PATTERN = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"$')


def parse_metric_line(line: str) -> tuple[str, str, str] | None:
    """Parse a Prometheus metric line into (metric_name, labels_str, value).

    Handles quoted label values that may contain special characters like }, {, and ,.
    Returns None if the line doesn't match the expected format.
    """
    # Find the metric name (everything before the first '{')
    brace_start = line.find("{")
    if brace_start == -1:
        return None

    metric_name = line[:brace_start]
    if not re.match(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$', metric_name):
        return None

    # Parse labels section by tracking quotes properly
    # Start after the opening brace
    i = brace_start + 1
    in_quotes = False
    escape_next = False
    labels_end = -1

    for idx in range(i, len(line)):
        ch = line[idx]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_quotes:
            escape_next = True
            continue
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if ch == '}' and not in_quotes:
            labels_end = idx
            break

    if labels_end == -1:
        return None

    labels_str = line[brace_start + 1:labels_end]

    # After the closing brace, expect a space and then the value
    remainder = line[labels_end + 1:]
    value_match = re.match(r'^\s+(\d+(?:\.\d+)?)$', remainder)
    if not value_match:
        return None

    value = value_match.group(1)
    return (metric_name, labels_str, value)


def parse_label_pairs(labels_str: str) -> list[tuple[str, str]] | None:
    """Parse a labels string into a list of (key, value) tuples.

    Handles escaped characters within quoted values.
    Returns None if parsing fails.
    """
    if not labels_str:
        return []

    pairs = []
    i = 0
    while i < len(labels_str):
        # Skip whitespace
        while i < len(labels_str) and labels_str[i] in (' ', '\t'):
            i += 1
        if i >= len(labels_str):
            break

        # Parse key
        key_start = i
        while i < len(labels_str) and labels_str[i] not in ('=', ',', '}'):
            i += 1
        if i >= len(labels_str) or labels_str[i] != '=':
            return None
        key = labels_str[key_start:i]
        i += 1  # skip '='

        # Expect opening quote
        if i >= len(labels_str) or labels_str[i] != '"':
            return None
        i += 1  # skip opening quote

        # Parse value (handle escapes)
        value_chars = []
        while i < len(labels_str):
            ch = labels_str[i]
            if ch == '\\' and i + 1 < len(labels_str):
                value_chars.append(ch)
                value_chars.append(labels_str[i + 1])
                i += 2
            elif ch == '"':
                break
            else:
                value_chars.append(ch)
                i += 1

        if i >= len(labels_str) or labels_str[i] != '"':
            return None
        i += 1  # skip closing quote

        pairs.append((key, ''.join(value_chars)))

        # Skip comma separator
        if i < len(labels_str) and labels_str[i] == ',':
            i += 1

    return pairs


class TestPrometheusExpositionFormat:
    """Property tests for Prometheus exposition format (Property 30).

    *For any* state of the metrics collector, the rendered output SHALL conform to the
    Prometheus exposition format with correct metric names, labels (alert name, severity),
    and counter values.

    **Validates: Requirements 11.2**
    """

    @given(actions=increment_actions_strategy(min_size=0, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_output_follows_prometheus_format(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any state of the metrics collector, the output SHALL follow Prometheus
        exposition format (metric_name{labels} value).

        Each non-comment line must match the pattern: metric_name{key="value",...} integer_value

        **Validates: Requirements 11.2**
        """
        collector = MetricsCollector()
        apply_actions(collector, actions)

        output = collector.render_metrics()

        for line in output.strip().split("\n"):
            if line.startswith("# HELP"):
                assert HELP_LINE_PATTERN.match(line), (
                    f"HELP line does not match Prometheus format: '{line}'"
                )
            elif line.startswith("# TYPE"):
                assert TYPE_LINE_PATTERN.match(line), (
                    f"TYPE line does not match Prometheus format: '{line}'"
                )
            else:
                parsed = parse_metric_line(line)
                assert parsed is not None, (
                    f"Metric line does not match Prometheus format "
                    f"(metric_name{{labels}} value): '{line}'"
                )

    @given(actions=increment_actions_strategy(min_size=0, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_labels_properly_formatted(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any state of the metrics collector, labels SHALL be properly formatted
        with key="value" pairs.

        **Validates: Requirements 11.2**
        """
        collector = MetricsCollector()
        apply_actions(collector, actions)

        output = collector.render_metrics()

        for line in output.strip().split("\n"):
            if line.startswith("#"):
                continue

            parsed = parse_metric_line(line)
            assert parsed is not None, f"Line does not match metric format: '{line}'"

            _, labels_str, _ = parsed
            # Parse label pairs using the proper parser that handles escaped values
            if labels_str:
                pairs = parse_label_pairs(labels_str)
                assert pairs is not None, (
                    f"Failed to parse label pairs from: '{labels_str}' "
                    f"in line: '{line}'"
                )
                # Each pair should have a valid key
                for key, value in pairs:
                    assert re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key), (
                        f"Label key '{key}' does not match valid format "
                        f"in line: '{line}'"
                    )

    @given(actions=increment_actions_strategy(min_size=0, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_counter_values_are_non_negative_integers(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any state of the metrics collector, counter values SHALL be
        non-negative integers.

        **Validates: Requirements 11.2**
        """
        collector = MetricsCollector()
        apply_actions(collector, actions)

        output = collector.render_metrics()

        for line in output.strip().split("\n"):
            if line.startswith("#"):
                continue

            parsed = parse_metric_line(line)
            assert parsed is not None, f"Line does not match metric format: '{line}'"

            value_str = parsed[2]
            value = int(value_str)
            assert value >= 0, (
                f"Counter value is negative ({value}) in line: '{line}'"
            )

    @given(actions=increment_actions_strategy(min_size=0, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_each_metric_line_ends_with_newline(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any state of the metrics collector, each metric line SHALL end with
        a newline character.

        **Validates: Requirements 11.2**
        """
        collector = MetricsCollector()
        apply_actions(collector, actions)

        output = collector.render_metrics()

        # The entire output should end with a newline
        assert output.endswith("\n"), (
            "Rendered metrics output does not end with a newline"
        )

        # Every line (when split by newline) should be non-empty except the last
        # (which is empty due to trailing newline)
        lines = output.split("\n")
        assert lines[-1] == "", (
            "Output does not have a trailing newline (last split element should be empty)"
        )
        for line in lines[:-1]:
            assert len(line) > 0, "Found an empty line in the metrics output"

    @given(actions=increment_actions_strategy(min_size=0, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_help_and_type_comments_included_for_each_metric_family(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any state of the metrics collector, HELP and TYPE comments SHALL be
        included for each metric family.

        **Validates: Requirements 11.2**
        """
        collector = MetricsCollector()
        apply_actions(collector, actions)

        output = collector.render_metrics()
        lines = output.strip().split("\n")

        # Expected metric families
        expected_metrics = set(MetricsCollector.METRIC_DEFINITIONS.keys())

        # Collect HELP and TYPE declarations found
        help_metrics = set()
        type_metrics = set()

        for line in lines:
            help_match = HELP_LINE_PATTERN.match(line)
            if help_match:
                help_metrics.add(help_match.group(1))

            type_match = TYPE_LINE_PATTERN.match(line)
            if type_match:
                type_metrics.add(type_match.group(1))

        # Every expected metric must have both HELP and TYPE
        for metric_name in expected_metrics:
            assert metric_name in help_metrics, (
                f"Missing # HELP comment for metric '{metric_name}'"
            )
            assert metric_name in type_metrics, (
                f"Missing # TYPE comment for metric '{metric_name}'"
            )

    @given(actions=increment_actions_strategy(min_size=1, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_metric_labels_contain_alert_name_and_severity(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any state of the metrics collector with recorded events, metric lines
        SHALL include alert_name and severity labels.

        **Validates: Requirements 11.2**
        """
        collector = MetricsCollector()
        apply_actions(collector, actions)

        output = collector.render_metrics()

        for line in output.strip().split("\n"):
            if line.startswith("#"):
                continue

            parsed = parse_metric_line(line)
            assert parsed is not None, f"Line does not match metric format: '{line}'"

            labels_str = parsed[1]
            # Check that both alert_name and severity labels are present
            assert 'alert_name=' in labels_str, (
                f"Missing 'alert_name' label in line: '{line}'"
            )
            assert 'severity=' in labels_str, (
                f"Missing 'severity' label in line: '{line}'"
            )

    @given(actions=increment_actions_strategy(min_size=0, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_type_is_counter_for_all_metrics(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any state of the metrics collector, all TYPE declarations SHALL
        specify 'counter' as the metric type.

        **Validates: Requirements 11.2**
        """
        collector = MetricsCollector()
        apply_actions(collector, actions)

        output = collector.render_metrics()

        for line in output.strip().split("\n"):
            type_match = TYPE_LINE_PATTERN.match(line)
            if type_match:
                metric_type = type_match.group(2)
                assert metric_type == "counter", (
                    f"Metric type should be 'counter' but got '{metric_type}' "
                    f"in line: '{line}'"
                )


# --- Property 29: Monotonically increasing counters ---


class TestMonotonicallyIncreasingCounters:
    """Property tests for monotonically increasing counters (Property 29).

    *For any* sequence of alert processing events, each metric counter SHALL only
    increase (never decrease) and SHALL increment by exactly 1 for each
    corresponding event.

    **Validates: Requirements 11.1**
    """

    @given(actions=increment_actions_strategy(min_size=1, max_size=50))
    @settings(max_examples=100, deadline=2000)
    def test_counters_never_decrease(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any sequence of increment operations, counter values SHALL never
        decrease.

        **Validates: Requirements 11.1**

        Strategy: Apply actions one at a time and verify that after each action,
        no counter value is less than its previous value.
        """
        collector = MetricsCollector()

        previous_output = collector.render_metrics()
        previous_values = self._extract_counter_values(previous_output)

        for method_name, alert_name, severity in actions:
            method = getattr(collector, method_name)
            method(alert_name=alert_name, severity=severity)

            current_output = collector.render_metrics()
            current_values = self._extract_counter_values(current_output)

            # Every counter that existed before must not have decreased
            for key, prev_val in previous_values.items():
                if key in current_values:
                    assert current_values[key] >= prev_val, (
                        f"Counter '{key}' decreased from {prev_val} to "
                        f"{current_values[key]} after {method_name}"
                    )

            previous_values = current_values

    @given(actions=increment_actions_strategy(min_size=1, max_size=50))
    @settings(max_examples=100, deadline=2000)
    def test_each_increment_adds_exactly_one(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """For any increment operation, the corresponding counter SHALL increase
        by exactly 1.

        **Validates: Requirements 11.1**

        Strategy: For each action, record the counter value before and after,
        and verify the difference is exactly 1 for the targeted counter.
        """
        collector = MetricsCollector()

        # Map method names to metric names
        method_to_metric = {
            "increment_alerts_received": "alerts_received_total",
            "increment_remediation_success": "remediation_success_total",
            "increment_remediation_failure": "remediation_failure_total",
            "increment_remediation_timeout": "remediation_timeout_total",
            "increment_no_playbook_match": "no_playbook_match_total",
            "increment_notification_failure": "notification_failure_total",
        }

        for method_name, alert_name, severity in actions:
            metric_name = method_to_metric[method_name]
            key = (metric_name, alert_name, severity)

            before_output = collector.render_metrics()
            before_values = self._extract_counter_values(before_output)
            before_val = before_values.get(key, 0)

            method = getattr(collector, method_name)
            method(alert_name=alert_name, severity=severity)

            after_output = collector.render_metrics()
            after_values = self._extract_counter_values(after_output)
            after_val = after_values.get(key, 0)

            assert after_val == before_val + 1, (
                f"Counter {key} should have incremented by 1 "
                f"(from {before_val} to {before_val + 1}), but got {after_val}"
            )

    @given(actions=increment_actions_strategy(min_size=0, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_counters_start_at_zero(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """All counters SHALL start at zero before any events are processed.

        **Validates: Requirements 11.1**

        Strategy: Create a fresh collector and verify all initial counter values
        are zero.
        """
        collector = MetricsCollector()
        output = collector.render_metrics()
        values = self._extract_counter_values(output)

        for key, value in values.items():
            assert value == 0, (
                f"Counter {key} should start at 0, but got {value}"
            )

    @given(actions=increment_actions_strategy(min_size=1, max_size=30))
    @settings(max_examples=100, deadline=2000)
    def test_total_count_equals_number_of_increments(
        self, actions: list[tuple[str, str, str]]
    ) -> None:
        """The sum of all counter values for a given metric SHALL equal the
        number of times that metric was incremented.

        **Validates: Requirements 11.1**

        Strategy: Count the number of times each (metric, alert_name, severity)
        combination is incremented, then verify the final counter matches.
        """
        collector = MetricsCollector()

        # Map method names to metric names
        method_to_metric = {
            "increment_alerts_received": "alerts_received_total",
            "increment_remediation_success": "remediation_success_total",
            "increment_remediation_failure": "remediation_failure_total",
            "increment_remediation_timeout": "remediation_timeout_total",
            "increment_no_playbook_match": "no_playbook_match_total",
            "increment_notification_failure": "notification_failure_total",
        }

        # Count expected increments
        expected_counts: dict[tuple[str, str, str], int] = {}
        for method_name, alert_name, severity in actions:
            metric_name = method_to_metric[method_name]
            key = (metric_name, alert_name, severity)
            expected_counts[key] = expected_counts.get(key, 0) + 1

        # Apply all actions
        apply_actions(collector, actions)

        # Verify final counts
        output = collector.render_metrics()
        actual_values = self._extract_counter_values(output)

        for key, expected in expected_counts.items():
            actual = actual_values.get(key, 0)
            assert actual == expected, (
                f"Counter {key} should be {expected} after all increments, "
                f"but got {actual}"
            )

    def _extract_counter_values(
        self, output: str
    ) -> dict[tuple[str, str, str], int]:
        """Extract counter values from Prometheus output.

        Returns a dict mapping (metric_name, alert_name, severity) to value.
        """
        values: dict[tuple[str, str, str], int] = {}

        for line in output.strip().split("\n"):
            if line.startswith("#"):
                continue

            match = METRIC_LINE_PATTERN.match(line)
            if match:
                metric_name = match.group(1)
                labels_str = match.group(2)
                value = int(match.group(3))

                # Extract alert_name and severity from labels
                alert_name = ""
                severity = ""
                pairs = parse_label_pairs(labels_str)
                if pairs is not None:
                    for k, v in pairs:
                        # Unescape the value
                        unescaped = v.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
                        if k == "alert_name":
                            alert_name = unescaped
                        elif k == "severity":
                            severity = unescaped

                values[(metric_name, alert_name, severity)] = value

        return values
