# Feature: self-healing-infrastructure, Property 4: Normalization field extraction
# Feature: self-healing-infrastructure, Property 5: Default value assignment for missing or unknown fields
# Feature: self-healing-infrastructure, Property 6: Alert count preservation
"""Property-based tests for the Normalizer component.

Property 4: Normalization field extraction
*For any* valid AlertmanagerPayload, the Normalizer SHALL produce NormalizedAlert objects
where each extracted field (alert name, status, labels, annotations, starts_at, ends_at)
matches the corresponding field in the source alert.

**Validates: Requirements 2.1**

Property 5: Default value assignment for missing or unknown fields
*For any* alert with missing required fields or unrecognized severity values,
the Normalizer SHALL assign correct defaults (empty string for alert name, P3 for
unknown/missing severity, "firing" for missing status, current time for missing
starts_at) and the output SHALL always have all required fields populated.

**Validates: Requirements 2.3, 2.5**

Property 6: Alert count preservation
*For any* AlertmanagerPayload containing N alerts, the Normalizer SHALL produce
exactly N NormalizedAlert objects — no alerts are dropped or duplicated during
normalization.

**Validates: Requirements 2.4**
"""

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import (
    AlertmanagerAlert,
    AlertmanagerPayload,
    AlertStatus,
    NormalizedAlert,
    Severity,
)
from src.normalizer import Normalizer


# --- Hypothesis Strategies for Property 4 ---


def valid_severity_strategy():
    """Generate valid Alertmanager severity values that map to known internal levels."""
    return st.sampled_from(["critical", "warning", "info"])


def valid_status_strategy():
    """Generate valid alert status values."""
    return st.sampled_from(["firing", "resolved"])


def prop4_labels_strategy(alertname: st.SearchStrategy, severity: st.SearchStrategy):
    """Generate labels dict with required alertname and severity, plus optional extras."""
    extra_labels = st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=20,
        ).filter(lambda k: k not in ("alertname", "severity")),
        values=st.text(min_size=1, max_size=50),
        min_size=0,
        max_size=5,
    )
    return st.tuples(alertname, severity, extra_labels).map(
        lambda t: {"alertname": t[0], "severity": t[1], **t[2]}
    )


def prop4_annotations_strategy():
    """Generate annotations dictionaries."""
    return st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=20,
        ),
        values=st.text(min_size=0, max_size=100),
        min_size=0,
        max_size=5,
    )


def valid_iso_timestamp_strategy():
    """Generate valid ISO 8601 timestamp strings that can be parsed."""
    return st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
        timezones=st.just(timezone.utc),
    ).map(lambda dt: dt.isoformat())


def valid_alertmanager_alert_strategy():
    """Generate a valid AlertmanagerAlert dataclass with known-good fields."""
    return st.builds(
        AlertmanagerAlert,
        status=valid_status_strategy(),
        labels=prop4_labels_strategy(
            alertname=st.text(min_size=1, max_size=50),
            severity=valid_severity_strategy(),
        ),
        annotations=prop4_annotations_strategy(),
        starts_at=valid_iso_timestamp_strategy(),
        ends_at=valid_iso_timestamp_strategy(),
        generator_url=st.just("http://prometheus:9090/graph"),
        fingerprint=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=8,
            max_size=16,
        ),
    )


def valid_alertmanager_payload_strategy():
    """Generate a valid AlertmanagerPayload with 1-10 alerts."""
    return st.builds(
        AlertmanagerPayload,
        version=st.just("4"),
        group_key=st.text(min_size=1, max_size=50),
        status=valid_status_strategy(),
        receiver=st.text(min_size=1, max_size=30),
        alerts=st.lists(valid_alertmanager_alert_strategy(), min_size=1, max_size=10),
        group_labels=st.just({}),
        common_labels=st.just({}),
        common_annotations=st.just({}),
        external_url=st.just("http://alertmanager:9093"),
    )


# --- Expected Mapping Helpers ---

SEVERITY_MAP = {
    "critical": Severity.P1,
    "warning": Severity.P2,
    "info": Severity.P3,
}

STATUS_MAP = {
    "firing": AlertStatus.FIRING,
    "resolved": AlertStatus.RESOLVED,
}


class TestNormalizerFieldExtraction:
    """Property tests for Normalizer field extraction (Property 4).

    Verifies that for any valid AlertmanagerPayload, the Normalizer produces
    NormalizedAlert objects where each extracted field matches the corresponding
    field in the source alert.

    **Validates: Requirements 2.1**
    """

    def setup_method(self):
        """Create a fresh Normalizer instance for each test."""
        self.normalizer = Normalizer()

    @given(payload=valid_alertmanager_payload_strategy())
    @settings(max_examples=100)
    def test_alert_name_matches_source(self, payload: AlertmanagerPayload) -> None:
        """For any valid payload, the alert_name in each NormalizedAlert SHALL match
        the 'alertname' label from the corresponding source alert.

        **Validates: Requirements 2.1**
        """
        results = self.normalizer.normalize(payload)

        for i, (source_alert, normalized) in enumerate(zip(payload.alerts, results)):
            expected_name = source_alert.labels.get("alertname", "")
            assert normalized.alert_name == expected_name, (
                f"Alert {i}: expected alert_name '{expected_name}', "
                f"got '{normalized.alert_name}'"
            )

    @given(payload=valid_alertmanager_payload_strategy())
    @settings(max_examples=100)
    def test_status_matches_source(self, payload: AlertmanagerPayload) -> None:
        """For any valid payload, the status in each NormalizedAlert SHALL match
        the status from the corresponding source alert.

        **Validates: Requirements 2.1**
        """
        results = self.normalizer.normalize(payload)

        for i, (source_alert, normalized) in enumerate(zip(payload.alerts, results)):
            expected_status = STATUS_MAP[source_alert.status.lower()]
            assert normalized.status == expected_status, (
                f"Alert {i}: expected status '{expected_status}', "
                f"got '{normalized.status}'"
            )

    @given(payload=valid_alertmanager_payload_strategy())
    @settings(max_examples=100)
    def test_labels_match_source(self, payload: AlertmanagerPayload) -> None:
        """For any valid payload, the labels in each NormalizedAlert SHALL be
        identical to the labels from the corresponding source alert.

        **Validates: Requirements 2.1**
        """
        results = self.normalizer.normalize(payload)

        for i, (source_alert, normalized) in enumerate(zip(payload.alerts, results)):
            assert normalized.labels == source_alert.labels, (
                f"Alert {i}: labels mismatch. "
                f"Expected {source_alert.labels}, got {normalized.labels}"
            )

    @given(payload=valid_alertmanager_payload_strategy())
    @settings(max_examples=100)
    def test_annotations_match_source(self, payload: AlertmanagerPayload) -> None:
        """For any valid payload, the annotations in each NormalizedAlert SHALL be
        identical to the annotations from the corresponding source alert.

        **Validates: Requirements 2.1**
        """
        results = self.normalizer.normalize(payload)

        for i, (source_alert, normalized) in enumerate(zip(payload.alerts, results)):
            assert normalized.annotations == source_alert.annotations, (
                f"Alert {i}: annotations mismatch. "
                f"Expected {source_alert.annotations}, got {normalized.annotations}"
            )

    @given(payload=valid_alertmanager_payload_strategy())
    @settings(max_examples=100)
    def test_starts_at_matches_source(self, payload: AlertmanagerPayload) -> None:
        """For any valid payload with parseable timestamps, the starts_at in each
        NormalizedAlert SHALL match the parsed starts_at from the source alert.

        **Validates: Requirements 2.1**
        """
        results = self.normalizer.normalize(payload)

        for i, (source_alert, normalized) in enumerate(zip(payload.alerts, results)):
            expected_dt = datetime.fromisoformat(
                source_alert.starts_at.replace("Z", "+00:00")
            )
            assert normalized.starts_at == expected_dt, (
                f"Alert {i}: expected starts_at '{expected_dt}', "
                f"got '{normalized.starts_at}'"
            )

    @given(payload=valid_alertmanager_payload_strategy())
    @settings(max_examples=100)
    def test_ends_at_matches_source(self, payload: AlertmanagerPayload) -> None:
        """For any valid payload with parseable ends_at timestamps, the ends_at in each
        NormalizedAlert SHALL match the parsed ends_at from the source alert.

        **Validates: Requirements 2.1**
        """
        results = self.normalizer.normalize(payload)

        for i, (source_alert, normalized) in enumerate(zip(payload.alerts, results)):
            # The normalizer returns None for zero-value timestamps
            if source_alert.ends_at.startswith("0001-01-01"):
                assert normalized.ends_at is None, (
                    f"Alert {i}: expected ends_at None for zero-value timestamp, "
                    f"got '{normalized.ends_at}'"
                )
            else:
                expected_dt = datetime.fromisoformat(
                    source_alert.ends_at.replace("Z", "+00:00")
                )
                assert normalized.ends_at == expected_dt, (
                    f"Alert {i}: expected ends_at '{expected_dt}', "
                    f"got '{normalized.ends_at}'"
                )


# --- Hypothesis Strategies ---

# Strategy for generating severity values that are NOT in the known set
unknown_severity_strategy = st.text(min_size=0, max_size=30).filter(
    lambda s: s.lower() not in ("critical", "warning", "info")
)

# Strategy for generating labels WITHOUT alertname
labels_without_alertname_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        min_size=1,
        max_size=30,
    ).filter(lambda k: k != "alertname"),
    values=st.text(min_size=0, max_size=50),
    min_size=0,
    max_size=5,
)

# Strategy for generating labels WITHOUT severity
labels_without_severity_strategy = st.fixed_dictionaries({
    "alertname": st.text(min_size=1, max_size=50),
}).flatmap(
    lambda base: st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=30,
        ).filter(lambda k: k not in ("alertname", "severity")),
        values=st.text(min_size=0, max_size=50),
        min_size=0,
        max_size=5,
    ).map(lambda extra: {**extra, **base})
)

# Strategy for generating labels with unknown severity
labels_with_unknown_severity_strategy = st.fixed_dictionaries({
    "alertname": st.text(min_size=1, max_size=50),
    "severity": unknown_severity_strategy.filter(lambda s: len(s) > 0),
}).flatmap(
    lambda base: st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=30,
        ).filter(lambda k: k not in ("alertname", "severity")),
        values=st.text(min_size=0, max_size=50),
        min_size=0,
        max_size=5,
    ).map(lambda extra: {**extra, **base})
)

# Strategy for generating invalid/empty status values
invalid_status_strategy = st.one_of(
    st.just(""),
    st.just("   "),
    st.text(min_size=1, max_size=20).filter(
        lambda s: s.strip().lower() not in ("firing", "resolved")
    ),
)

# Strategy for generating invalid/empty starts_at values
invalid_starts_at_strategy = st.one_of(
    st.just(""),
    st.just("   "),
    st.just("not-a-timestamp"),
    st.text(min_size=1, max_size=30).filter(
        lambda s: not _is_valid_iso_timestamp(s)
    ),
)


def _is_valid_iso_timestamp(s: str) -> bool:
    """Check if a string is a valid ISO timestamp."""
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


def _make_payload(alerts: list[AlertmanagerAlert]) -> AlertmanagerPayload:
    """Helper to wrap alerts in a minimal valid payload."""
    return AlertmanagerPayload(
        version="4",
        group_key="test-group",
        status="firing",
        receiver="test-receiver",
        alerts=alerts,
    )


class TestDefaultValueAssignment:
    """Property tests for default value assignment (Property 5).

    **Validates: Requirements 2.3, 2.5**
    """

    @given(labels=labels_without_alertname_strategy)
    @settings(max_examples=100)
    def test_missing_alertname_defaults_to_empty_string(self, labels: dict) -> None:
        """For any alert with missing alertname, the Normalizer SHALL assign empty string.

        **Validates: Requirements 2.3, 2.5**
        """
        # Ensure alertname is not in labels
        labels.pop("alertname", None)
        # Add a severity so we isolate the alertname default behavior
        labels["severity"] = "critical"

        alert = AlertmanagerAlert(
            status="firing",
            labels=labels,
            annotations={},
            starts_at="2024-01-15T10:30:00Z",
            ends_at="",
            fingerprint="test123",
        )
        payload = _make_payload([alert])
        normalizer = Normalizer()

        results = normalizer.normalize(payload)

        assert len(results) == 1
        assert results[0].alert_name == ""

    @given(severity_value=unknown_severity_strategy)
    @settings(max_examples=100)
    def test_unknown_severity_defaults_to_p3(self, severity_value: str) -> None:
        """For any alert with unrecognized severity, the Normalizer SHALL assign P3.

        **Validates: Requirements 2.3, 2.5**
        """
        labels = {
            "alertname": "TestAlert",
            "severity": severity_value,
        }

        alert = AlertmanagerAlert(
            status="firing",
            labels=labels,
            annotations={},
            starts_at="2024-01-15T10:30:00Z",
            ends_at="",
            fingerprint="test123",
        )
        payload = _make_payload([alert])
        normalizer = Normalizer()

        results = normalizer.normalize(payload)

        assert len(results) == 1
        assert results[0].severity == Severity.P3

    @given(labels=labels_without_severity_strategy)
    @settings(max_examples=100)
    def test_missing_severity_defaults_to_p3(self, labels: dict) -> None:
        """For any alert with missing severity label, the Normalizer SHALL assign P3.

        **Validates: Requirements 2.3, 2.5**
        """
        # Ensure severity is not in labels
        labels.pop("severity", None)

        alert = AlertmanagerAlert(
            status="firing",
            labels=labels,
            annotations={},
            starts_at="2024-01-15T10:30:00Z",
            ends_at="",
            fingerprint="test123",
        )
        payload = _make_payload([alert])
        normalizer = Normalizer()

        results = normalizer.normalize(payload)

        assert len(results) == 1
        assert results[0].severity == Severity.P3

    @given(status_value=invalid_status_strategy)
    @settings(max_examples=100)
    def test_missing_or_invalid_status_defaults_to_firing(self, status_value: str) -> None:
        """For any alert with missing or unrecognized status, the Normalizer SHALL assign 'firing'.

        **Validates: Requirements 2.3, 2.5**
        """
        alert = AlertmanagerAlert(
            status=status_value,
            labels={"alertname": "TestAlert", "severity": "warning"},
            annotations={},
            starts_at="2024-01-15T10:30:00Z",
            ends_at="",
            fingerprint="test123",
        )
        payload = _make_payload([alert])
        normalizer = Normalizer()

        results = normalizer.normalize(payload)

        assert len(results) == 1
        assert results[0].status == AlertStatus.FIRING

    @given(starts_at_value=invalid_starts_at_strategy)
    @settings(max_examples=100)
    def test_missing_or_invalid_starts_at_defaults_to_current_time(
        self, starts_at_value: str
    ) -> None:
        """For any alert with missing or invalid starts_at, the Normalizer SHALL assign current time.

        **Validates: Requirements 2.3, 2.5**
        """
        before = datetime.now(timezone.utc)

        alert = AlertmanagerAlert(
            status="firing",
            labels={"alertname": "TestAlert", "severity": "info"},
            annotations={},
            starts_at=starts_at_value,
            ends_at="",
            fingerprint="test123",
        )
        payload = _make_payload([alert])
        normalizer = Normalizer()

        results = normalizer.normalize(payload)

        after = datetime.now(timezone.utc)

        assert len(results) == 1
        # The default starts_at should be approximately the current time
        assert results[0].starts_at >= before
        assert results[0].starts_at <= after

    @given(
        labels=st.fixed_dictionaries({}).flatmap(
            lambda _: st.dictionaries(
                keys=st.text(
                    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
                    min_size=1,
                    max_size=30,
                ).filter(lambda k: k not in ("alertname", "severity")),
                values=st.text(min_size=0, max_size=50),
                min_size=0,
                max_size=5,
            )
        ),
        status_value=st.one_of(st.just(""), st.just("   ")),
        starts_at_value=st.one_of(st.just(""), st.just("not-a-date")),
    )
    @settings(max_examples=100)
    def test_all_fields_missing_assigns_all_defaults(
        self, labels: dict, status_value: str, starts_at_value: str
    ) -> None:
        """For any alert with ALL required fields missing, the Normalizer SHALL assign all defaults.

        The output SHALL always have all required fields populated:
        - alert_name: empty string
        - severity: P3
        - status: FIRING
        - starts_at: current time (datetime)
        - incident_id: non-empty string
        - labels: dict
        - annotations: dict

        **Validates: Requirements 2.3, 2.5**
        """
        # No alertname, no severity in labels
        labels.pop("alertname", None)
        labels.pop("severity", None)

        before = datetime.now(timezone.utc)

        alert = AlertmanagerAlert(
            status=status_value,
            labels=labels,
            annotations={},
            starts_at=starts_at_value,
            ends_at="",
            fingerprint="test123",
        )
        payload = _make_payload([alert])
        normalizer = Normalizer()

        results = normalizer.normalize(payload)

        after = datetime.now(timezone.utc)

        assert len(results) == 1
        result = results[0]

        # All required fields must be populated with correct defaults
        assert result.alert_name == ""
        assert result.severity == Severity.P3
        assert result.status == AlertStatus.FIRING
        assert result.starts_at >= before
        assert result.starts_at <= after

        # Output SHALL always have all required fields populated
        assert isinstance(result.incident_id, str) and len(result.incident_id) > 0
        assert isinstance(result.labels, dict)
        assert isinstance(result.annotations, dict)
        assert isinstance(result.starts_at, datetime)


# --- Property 6: Alert count preservation ---
# Feature: self-healing-infrastructure, Property 6: Alert count preservation


def _prop6_alert_labels_strategy():
    """Generate alert labels with optional alertname and severity fields for Property 6."""
    base_labels = st.fixed_dictionaries({
        "alertname": st.text(min_size=0, max_size=50),
        "severity": st.one_of(
            st.sampled_from(["critical", "warning", "info"]),
            st.text(min_size=0, max_size=20),
        ),
    })
    extra_labels = st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=20,
        ).filter(lambda k: k not in ("alertname", "severity")),
        values=st.text(min_size=0, max_size=50),
        min_size=0,
        max_size=5,
    )
    return base_labels.flatmap(
        lambda base: extra_labels.map(lambda extra: {**extra, **base})
    )


def _prop6_alertmanager_alert_strategy():
    """Generate a single AlertmanagerAlert for Property 6 testing."""
    return st.builds(
        AlertmanagerAlert,
        status=st.one_of(
            st.sampled_from(["firing", "resolved"]),
            st.text(min_size=0, max_size=20),
        ),
        labels=_prop6_alert_labels_strategy(),
        annotations=st.dictionaries(
            keys=st.text(
                alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
                min_size=1,
                max_size=20,
            ),
            values=st.text(min_size=0, max_size=100),
            min_size=0,
            max_size=3,
        ),
        starts_at=st.one_of(
            st.just(""),
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2030, 12, 31),
                timezones=st.just(timezone.utc),
            ).map(lambda dt: dt.isoformat()),
        ),
        ends_at=st.one_of(
            st.just(""),
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2030, 12, 31),
                timezones=st.just(timezone.utc),
            ).map(lambda dt: dt.isoformat()),
        ),
        generator_url=st.just("http://prometheus:9090/graph"),
        fingerprint=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=0,
            max_size=16,
        ),
    )


def _prop6_alertmanager_payload_strategy(min_alerts: int = 1, max_alerts: int = 20):
    """Generate an AlertmanagerPayload with a configurable number of alerts for Property 6."""
    return st.builds(
        AlertmanagerPayload,
        version=st.just("4"),
        group_key=st.text(min_size=1, max_size=50),
        status=st.sampled_from(["firing", "resolved"]),
        receiver=st.text(min_size=1, max_size=30),
        alerts=st.lists(
            _prop6_alertmanager_alert_strategy(),
            min_size=min_alerts,
            max_size=max_alerts,
        ),
        group_labels=st.just({}),
        common_labels=st.just({}),
        common_annotations=st.just({}),
        external_url=st.just("http://alertmanager:9093"),
    )


class TestAlertCountPreservation:
    """Property tests for alert count preservation (Property 6).

    *For any* AlertmanagerPayload containing N alerts, the Normalizer SHALL produce
    exactly N NormalizedAlert objects — no alerts are dropped or duplicated during
    normalization.

    **Validates: Requirements 2.4**
    """

    @given(payload=_prop6_alertmanager_payload_strategy(min_alerts=1, max_alerts=20))
    @settings(max_examples=100, deadline=1000)
    def test_normalizer_produces_exactly_n_alerts(self, payload: AlertmanagerPayload) -> None:
        """For any AlertmanagerPayload containing N alerts, the Normalizer SHALL produce
        exactly N NormalizedAlert objects — no alerts are dropped or duplicated.

        **Validates: Requirements 2.4**
        """
        normalizer = Normalizer()
        input_count = len(payload.alerts)

        result = normalizer.normalize(payload)

        assert len(result) == input_count, (
            f"Expected {input_count} normalized alerts but got {len(result)}. "
            f"Alerts were {'dropped' if len(result) < input_count else 'duplicated'} "
            f"during normalization."
        )

    @given(payload=_prop6_alertmanager_payload_strategy(min_alerts=1, max_alerts=20))
    @settings(max_examples=100, deadline=1000)
    def test_all_results_are_normalized_alert_instances(self, payload: AlertmanagerPayload) -> None:
        """For any AlertmanagerPayload, all output objects SHALL be NormalizedAlert instances.

        **Validates: Requirements 2.4**
        """
        normalizer = Normalizer()

        result = normalizer.normalize(payload)

        for i, alert in enumerate(result):
            assert isinstance(alert, NormalizedAlert), (
                f"Result at index {i} is {type(alert).__name__}, expected NormalizedAlert"
            )

    @given(payload=_prop6_alertmanager_payload_strategy(min_alerts=1, max_alerts=20))
    @settings(max_examples=100, deadline=1000)
    def test_each_alert_gets_unique_incident_id(self, payload: AlertmanagerPayload) -> None:
        """For any AlertmanagerPayload, each normalized alert SHALL have a unique incident ID,
        confirming no duplication occurred.

        **Validates: Requirements 2.4**
        """
        normalizer = Normalizer()

        result = normalizer.normalize(payload)

        incident_ids = [alert.incident_id for alert in result]
        assert len(incident_ids) == len(set(incident_ids)), (
            f"Duplicate incident IDs found: {incident_ids}. "
            f"This indicates alerts were duplicated during normalization."
        )
