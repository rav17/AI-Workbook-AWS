"""Metrics Collector component for the self-healing infrastructure system.

Collects and exposes operational metrics in Prometheus exposition format.
Implements monotonically increasing counters with labels for alert_name and severity.
"""

from collections import defaultdict
from threading import Lock


class MetricsCollector:
    """Collects and exposes Prometheus metrics.

    Maintains monotonically increasing counters for various alert processing events.
    Counters are labeled by alert_name and severity and are exposed in Prometheus
    exposition format via render_metrics().
    """

    # Metric names and their descriptions
    METRIC_DEFINITIONS = {
        "alerts_received_total": "Total number of alerts received",
        "remediation_success_total": "Total number of successful remediations",
        "remediation_failure_total": "Total number of failed remediations",
        "remediation_timeout_total": "Total number of timed-out remediations",
        "no_playbook_match_total": "Total number of alerts with no matching playbook",
        "notification_failure_total": "Total number of notification failures",
        "alerts_storm_suppressed_total": "Total alerts suppressed by storm detection",
        "fleet_breaker_trips_total": "Total fleet circuit breaker activations",
    }

    def __init__(self) -> None:
        """Initialize all counters to zero."""
        self._lock = Lock()
        # Counters stored as {metric_name: {(alert_name, severity): count}}
        self._counters: dict[str, dict[tuple[str, str], int]] = {
            name: defaultdict(int) for name in self.METRIC_DEFINITIONS
        }

    def increment_alerts_received(
        self, alert_name: str = "", severity: str = ""
    ) -> None:
        """Increment the alerts_received counter."""
        with self._lock:
            self._counters["alerts_received_total"][(alert_name, severity)] += 1

    def increment_remediation_success(
        self, alert_name: str = "", severity: str = ""
    ) -> None:
        """Increment the remediation_success counter."""
        with self._lock:
            self._counters["remediation_success_total"][(alert_name, severity)] += 1

    def increment_remediation_failure(
        self, alert_name: str = "", severity: str = ""
    ) -> None:
        """Increment the remediation_failure counter."""
        with self._lock:
            self._counters["remediation_failure_total"][(alert_name, severity)] += 1

    def increment_remediation_timeout(
        self, alert_name: str = "", severity: str = ""
    ) -> None:
        """Increment the remediation_timeout counter."""
        with self._lock:
            self._counters["remediation_timeout_total"][(alert_name, severity)] += 1

    def increment_no_playbook_match(
        self, alert_name: str = "", severity: str = ""
    ) -> None:
        """Increment the no_playbook_match counter."""
        with self._lock:
            self._counters["no_playbook_match_total"][(alert_name, severity)] += 1

    def increment_notification_failure(
        self, alert_name: str = "", severity: str = ""
    ) -> None:
        """Increment the notification_failure counter."""
        with self._lock:
            self._counters["notification_failure_total"][(alert_name, severity)] += 1

    def increment_storm_suppressed(
        self, alert_name: str = "", severity: str = ""
    ) -> None:
        """Increment the storm suppression counter."""
        with self._lock:
            self._counters["alerts_storm_suppressed_total"][(alert_name, severity)] += 1

    def increment_fleet_breaker_trips(
        self, alert_name: str = "", severity: str = ""
    ) -> None:
        """Increment the fleet breaker trip counter."""
        with self._lock:
            self._counters["fleet_breaker_trips_total"][(alert_name, severity)] += 1

    def render_metrics(self) -> str:
        """Render all metrics in Prometheus exposition format.

        Returns a string with HELP and TYPE comments for each metric family,
        followed by metric lines in the format:
            metric_name{label1="value1",label2="value2"} value

        Each metric line ends with a newline. Counter values are non-negative integers.
        """
        with self._lock:
            lines: list[str] = []

            for metric_name, description in self.METRIC_DEFINITIONS.items():
                # HELP comment
                lines.append(f"# HELP {metric_name} {description}")
                # TYPE comment
                lines.append(f"# TYPE {metric_name} counter")

                label_values = self._counters[metric_name]
                if label_values:
                    for (alert_name, severity), value in sorted(
                        label_values.items()
                    ):
                        # Escape label values for Prometheus format
                        escaped_alert_name = self._escape_label_value(alert_name)
                        escaped_severity = self._escape_label_value(severity)
                        lines.append(
                            f'{metric_name}{{alert_name="{escaped_alert_name}",'
                            f'severity="{escaped_severity}"}} {value}'
                        )
                else:
                    # Emit a zero-value line with empty labels if no data yet
                    lines.append(
                        f'{metric_name}{{alert_name="",severity=""}} 0'
                    )

            # Each line ends with a newline; final output ends with newline
            return "\n".join(lines) + "\n"

    @staticmethod
    def _escape_label_value(value: str) -> str:
        """Escape special characters in Prometheus label values.

        Per Prometheus exposition format, label values must escape:
        - backslash as \\\\
        - double quote as \\"
        - newline as \\n
        """
        value = value.replace("\\", "\\\\")
        value = value.replace('"', '\\"')
        value = value.replace("\n", "\\n")
        return value
