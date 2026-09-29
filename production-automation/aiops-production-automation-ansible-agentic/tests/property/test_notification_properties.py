# Feature: self-healing-infrastructure, Property 19: Incident notification content completeness
# Feature: self-healing-infrastructure, Property 20: Remediation notification content completeness
"""Property-based tests for the NotificationDispatcher component.

Property 19: Incident notification content completeness
*For any* detected incident, the notification SHALL contain the alert name,
severity, affected host, and timestamp.

**Validates: Requirements 6.1, 6.6**

Property 20: Remediation notification content completeness
*For any* completed remediation action, the notification SHALL contain the action
taken, outcome (success/failure/timeout), and execution duration.

**Validates: Requirements 6.2**
"""

import asyncio
from datetime import datetime, timezone
from typing import List

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import (
    AssetInfo,
    EnrichedAlert,
    ExecutionResult,
    RemediationStatus,
    Severity,
    AlertStatus,
)
from src.notification import (
    NotificationChannel,
    NotificationDispatcher,
    NotificationMessage,
)


# --- Test Channel Implementation ---


class RecordingChannel(NotificationChannel):
    """A test notification channel that records all sent messages."""

    def __init__(self, channel_name: str = "test-channel"):
        self._name = channel_name
        self.sent_messages: List[NotificationMessage] = []

    @property
    def name(self) -> str:
        return self._name

    async def send(self, message: NotificationMessage) -> None:
        self.sent_messages.append(message)


# --- Hypothesis Strategies ---

# Strategy for generating severity values
severity_strategy = st.sampled_from(list(Severity))

# Strategy for generating alert status
alert_status_strategy = st.sampled_from(list(AlertStatus))

# Strategy for generating alert names
alert_name_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
).filter(lambda s: s.strip() != "")

# Strategy for generating hostnames
hostname_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".-_"),
).filter(lambda s: s.strip() != "")

# Strategy for generating IP addresses
ip_strategy = st.tuples(
    st.integers(min_value=1, max_value=254),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=1, max_value=254),
).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}")

# Strategy for generating AssetInfo
asset_info_strategy = st.builds(
    AssetInfo,
    hostname=hostname_strategy,
    ip_address=ip_strategy,
    location=st.text(min_size=1, max_size=30),
    service_name=st.text(min_size=1, max_size=30),
    service_owner=st.text(min_size=1, max_size=30),
)

# Strategy for generating labels with instance key
labels_with_instance_strategy = st.fixed_dictionaries(
    {"instance": hostname_strategy},
    optional={
        "job": st.text(min_size=1, max_size=20),
    },
)

# Strategy for generating datetimes
datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

# Strategy for generating EnrichedAlert with asset info
enriched_alert_with_asset_strategy = st.builds(
    EnrichedAlert,
    incident_id=st.uuids().map(str),
    alert_name=alert_name_strategy,
    severity=severity_strategy,
    status=alert_status_strategy,
    labels=labels_with_instance_strategy,
    annotations=st.just({}),
    starts_at=datetime_strategy,
    ends_at=st.one_of(st.none(), datetime_strategy),
    asset=asset_info_strategy,
    is_enriched=st.just(True),
)

# Strategy for generating EnrichedAlert without asset info (uses labels for host)
enriched_alert_without_asset_strategy = st.builds(
    EnrichedAlert,
    incident_id=st.uuids().map(str),
    alert_name=alert_name_strategy,
    severity=severity_strategy,
    status=alert_status_strategy,
    labels=labels_with_instance_strategy,
    annotations=st.just({}),
    starts_at=datetime_strategy,
    ends_at=st.one_of(st.none(), datetime_strategy),
    asset=st.none(),
    is_enriched=st.just(False),
)

# Combined enriched alert strategy
enriched_alert_strategy = st.one_of(
    enriched_alert_with_asset_strategy,
    enriched_alert_without_asset_strategy,
)

# Strategy for generating playbook paths
playbook_path_strategy = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_./"),
).filter(lambda s: s.strip() != "")

# Strategy for generating remediation outcomes
outcome_strategy = st.sampled_from(list(RemediationStatus))

# Strategy for generating positive duration values in seconds
duration_strategy = st.floats(
    min_value=0.0,
    max_value=86400.0,
    allow_nan=False,
    allow_infinity=False,
)

# Strategy for generating target hosts
target_host_strategy = hostname_strategy

# Strategy for generating ExecutionResult
execution_result_strategy = st.builds(
    ExecutionResult,
    status=outcome_strategy,
    return_code=st.integers(min_value=-1, max_value=255),
    stdout=st.text(min_size=0, max_size=100),
    stderr=st.text(min_size=0, max_size=100),
    duration_seconds=duration_strategy,
    playbook_path=playbook_path_strategy,
    target_host=target_host_strategy,
)

# Strategy for generating a list of channel names (1-5 channels)
channel_names_strategy = st.lists(
    st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    ).filter(lambda s: s.strip() != ""),
    min_size=1,
    max_size=5,
    unique=True,
)


# --- Property 19: Incident notification content completeness ---


class TestIncidentNotificationContentCompleteness:
    """Property tests for incident notification content completeness (Property 19).

    *For any* detected incident, the notification SHALL contain the alert name,
    severity, affected host, and timestamp.

    **Validates: Requirements 6.1, 6.6**
    """

    @given(alert=enriched_alert_with_asset_strategy)
    @settings(max_examples=100)
    def test_incident_notification_contains_alert_name(
        self, alert: EnrichedAlert
    ) -> None:
        """For any detected incident, the notification SHALL contain the alert name.

        **Validates: Requirements 6.1**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_incident(alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        assert message.alert_name == alert.alert_name, (
            f"Expected alert_name='{alert.alert_name}', got '{message.alert_name}'"
        )

    @given(alert=enriched_alert_with_asset_strategy)
    @settings(max_examples=100)
    def test_incident_notification_contains_severity(
        self, alert: EnrichedAlert
    ) -> None:
        """For any detected incident, the notification SHALL contain the severity.

        **Validates: Requirements 6.1**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_incident(alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        assert message.severity == alert.severity.value, (
            f"Expected severity='{alert.severity.value}', got '{message.severity}'"
        )

    @given(alert=enriched_alert_with_asset_strategy)
    @settings(max_examples=100)
    def test_incident_notification_contains_affected_host(
        self, alert: EnrichedAlert
    ) -> None:
        """For any detected incident with asset info, the notification SHALL
        contain the affected host from asset metadata.

        **Validates: Requirements 6.1**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_incident(alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        # When asset info is available, affected_host should come from asset.hostname
        assert message.affected_host == alert.asset.hostname, (
            f"Expected affected_host='{alert.asset.hostname}', "
            f"got '{message.affected_host}'"
        )

    @given(alert=enriched_alert_with_asset_strategy)
    @settings(max_examples=100)
    def test_incident_notification_contains_timestamp(
        self, alert: EnrichedAlert
    ) -> None:
        """For any detected incident, the notification SHALL contain the timestamp.

        **Validates: Requirements 6.1**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_incident(alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        assert message.timestamp == alert.starts_at.isoformat(), (
            f"Expected timestamp='{alert.starts_at.isoformat()}', "
            f"got '{message.timestamp}'"
        )

    @given(alert=enriched_alert_strategy, channel_names=channel_names_strategy)
    @settings(max_examples=100)
    def test_incident_notification_dispatched_to_all_channels(
        self, alert: EnrichedAlert, channel_names: List[str]
    ) -> None:
        """For any detected incident, the notification SHALL be dispatched
        to all configured channels.

        **Validates: Requirements 6.6**
        """
        channels = [RecordingChannel(name) for name in channel_names]
        dispatcher = NotificationDispatcher(channels=channels)

        asyncio.run(
            dispatcher.notify_incident(alert)
        )

        for channel in channels:
            assert len(channel.sent_messages) == 1, (
                f"Channel '{channel.name}' should have received exactly 1 message, "
                f"got {len(channel.sent_messages)}"
            )

    @given(alert=enriched_alert_with_asset_strategy)
    @settings(max_examples=100)
    def test_incident_notification_message_type_is_incident(
        self, alert: EnrichedAlert
    ) -> None:
        """For any detected incident, the notification message_type SHALL be 'incident'.

        **Validates: Requirements 6.1**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_incident(alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        assert message.message_type == "incident", (
            f"Expected message_type='incident', got '{message.message_type}'"
        )


# --- Property 20: Remediation notification content completeness ---


class TestRemediationNotificationContentCompleteness:
    """Property tests for remediation notification content completeness (Property 20).

    *For any* completed remediation action, the notification SHALL contain the
    action taken, outcome (success/failure/timeout), and execution duration.

    **Validates: Requirements 6.2**
    """

    @given(result=execution_result_strategy, alert=enriched_alert_strategy)
    @settings(max_examples=100)
    def test_remediation_notification_contains_action_taken(
        self, result: ExecutionResult, alert: EnrichedAlert
    ) -> None:
        """For any completed remediation, the notification SHALL contain the action taken.

        **Validates: Requirements 6.2**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_remediation(result, alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        assert message.action_taken == result.playbook_path, (
            f"Expected action_taken='{result.playbook_path}', "
            f"got '{message.action_taken}'"
        )

    @given(result=execution_result_strategy, alert=enriched_alert_strategy)
    @settings(max_examples=100)
    def test_remediation_notification_contains_outcome(
        self, result: ExecutionResult, alert: EnrichedAlert
    ) -> None:
        """For any completed remediation, the notification SHALL contain the outcome
        (success/failure/timeout).

        **Validates: Requirements 6.2**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_remediation(result, alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        assert message.outcome == result.status.value, (
            f"Expected outcome='{result.status.value}', got '{message.outcome}'"
        )

    @given(result=execution_result_strategy, alert=enriched_alert_strategy)
    @settings(max_examples=100)
    def test_remediation_notification_contains_duration(
        self, result: ExecutionResult, alert: EnrichedAlert
    ) -> None:
        """For any completed remediation, the notification SHALL contain the
        execution duration.

        **Validates: Requirements 6.2**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_remediation(result, alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        assert message.duration_seconds == result.duration_seconds, (
            f"Expected duration={result.duration_seconds}, "
            f"got {message.duration_seconds}"
        )

    @given(
        result=execution_result_strategy,
        alert=enriched_alert_strategy,
        channel_names=channel_names_strategy,
    )
    @settings(max_examples=100)
    def test_remediation_notification_dispatched_to_all_channels(
        self,
        result: ExecutionResult,
        alert: EnrichedAlert,
        channel_names: List[str],
    ) -> None:
        """For any completed remediation, the notification SHALL be dispatched
        to all configured channels.

        **Validates: Requirements 6.2**
        """
        channels = [RecordingChannel(name) for name in channel_names]
        dispatcher = NotificationDispatcher(channels=channels)

        asyncio.run(
            dispatcher.notify_remediation(result, alert)
        )

        for channel in channels:
            assert len(channel.sent_messages) == 1, (
                f"Channel '{channel.name}' should have received exactly 1 message, "
                f"got {len(channel.sent_messages)}"
            )

    @given(result=execution_result_strategy, alert=enriched_alert_strategy)
    @settings(max_examples=100)
    def test_remediation_notification_contains_all_required_fields(
        self, result: ExecutionResult, alert: EnrichedAlert
    ) -> None:
        """For any completed remediation, the notification SHALL contain all
        required fields: action_taken, outcome, and duration.

        **Validates: Requirements 6.2**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_remediation(result, alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]

        # Verify all required fields are present and accurate
        assert message.action_taken == result.playbook_path
        assert message.outcome == result.status.value
        assert message.duration_seconds == result.duration_seconds

    @given(result=execution_result_strategy, alert=enriched_alert_strategy)
    @settings(max_examples=100)
    def test_remediation_notification_message_type_is_remediation(
        self, result: ExecutionResult, alert: EnrichedAlert
    ) -> None:
        """For any completed remediation, the notification message_type SHALL
        be 'remediation'.

        **Validates: Requirements 6.2**
        """
        channel = RecordingChannel()
        dispatcher = NotificationDispatcher(channels=[channel])

        asyncio.run(
            dispatcher.notify_remediation(result, alert)
        )

        assert len(channel.sent_messages) == 1
        message = channel.sent_messages[0]
        assert message.message_type == "remediation", (
            f"Expected message_type='remediation', got '{message.message_type}'"
        )
