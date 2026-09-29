# Feature: self-healing-infrastructure, Property 21, 22, 23: Orchestrator pipeline properties
"""Property-based tests for the Orchestrator component.

Property 21: Pipeline UUID uniqueness and sequential execution
*For any* AlertmanagerPayload processed by the Orchestrator, each individual alert
SHALL be assigned a unique UUID-format incident identifier, and pipeline stages
SHALL execute in the defined sequence (normalize → enrich → match → execute → notify).
**Validates: Requirements 7.1**

Property 22: Stage failure triggers logging and notification
*For any* pipeline stage that fails with an unhandled exception, the Orchestrator
SHALL log the failure with incident ID and stage name, skip remaining stages, and
dispatch a failure notification.
**Validates: Requirements 7.3**

Property 23: Unmatched alert skips execution
*For any* alert with no matching playbook, the Orchestrator SHALL skip the
remediation execution stage and dispatch a manual triage notification.
**Validates: Requirements 7.5**
"""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import (
    AlertmanagerAlert,
    AlertmanagerPayload,
    AlertStatus,
    AssetInfo,
    EnrichedAlert,
    ExecutionResult,
    NormalizedAlert,
    PlaybookMatch,
    RemediationStatus,
    Severity,
)
from src.normalizer import Normalizer
from src.enricher import Enricher
from src.executor import RemediationExecutor
from src.notification import NotificationDispatcher
from src.playbook_mapper import PlaybookMapper
from src.audit_logger import AuditLogger
from src.metrics import MetricsCollector
from src.orchestrator import Orchestrator


# --- Hypothesis Strategies ---

# Strategy for generating severity values
severity_strategy = st.sampled_from([Severity.P1, Severity.P2, Severity.P3])

# Strategy for generating alert status values
alert_status_strategy = st.sampled_from([AlertStatus.FIRING, AlertStatus.RESOLVED])

# Strategy for generating alert names
alert_name_strategy = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
)

# Strategy for generating labels dictionaries
labels_strategy = st.fixed_dictionaries(
    {
        "alertname": alert_name_strategy,
        "severity": st.sampled_from(["critical", "warning", "info"]),
    },
    optional={
        "instance": st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), whitelist_characters="_-.:"
            ),
        ),
    },
)

# Strategy for generating annotations dictionaries
annotations_strategy = st.dictionaries(
    keys=st.text(
        min_size=1,
        max_size=15,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    ),
    values=st.text(
        min_size=0,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    ),
    min_size=0,
    max_size=3,
)

# Strategy for generating a single AlertmanagerAlert
alertmanager_alert_strategy = st.builds(
    AlertmanagerAlert,
    status=st.sampled_from(["firing", "resolved"]),
    labels=labels_strategy,
    annotations=annotations_strategy,
    starts_at=st.just("2024-01-01T00:00:00Z"),
    ends_at=st.just("0001-01-01T00:00:00Z"),
    generator_url=st.just("http://prometheus:9090/graph"),
    fingerprint=st.uuids().map(lambda u: str(u)[:16]),
)

# Strategy for generating AlertmanagerPayload with 1-10 alerts
alertmanager_payload_strategy = st.builds(
    AlertmanagerPayload,
    version=st.just("4"),
    group_key=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    status=st.just("firing"),
    receiver=st.just("test-receiver"),
    alerts=st.lists(alertmanager_alert_strategy, min_size=1, max_size=10),
    group_labels=st.just({}),
    common_labels=st.just({}),
    common_annotations=st.just({}),
    external_url=st.just("http://alertmanager:9093"),
)


# --- Helper functions ---


def _make_normalized_alert(
    incident_id: str = None,
    alert_name: str = "TestAlert",
    severity: Severity = Severity.P1,
) -> NormalizedAlert:
    """Create a NormalizedAlert for testing."""
    return NormalizedAlert(
        incident_id=incident_id or str(uuid.uuid4()),
        alert_name=alert_name,
        severity=severity,
        status=AlertStatus.FIRING,
        labels={"alertname": alert_name, "severity": "critical", "instance": "host1:9090"},
        annotations={"summary": "Test alert"},
        starts_at=datetime.now(timezone.utc),
        ends_at=None,
        raw_fingerprint="abc123",
    )


def _make_enriched_alert(normalized: NormalizedAlert) -> EnrichedAlert:
    """Create an EnrichedAlert from a NormalizedAlert."""
    return EnrichedAlert(
        incident_id=normalized.incident_id,
        alert_name=normalized.alert_name,
        severity=normalized.severity,
        status=normalized.status,
        labels=normalized.labels,
        annotations=normalized.annotations,
        starts_at=normalized.starts_at,
        ends_at=normalized.ends_at,
        asset=AssetInfo(
            hostname="host1.example.com",
            ip_address="10.0.0.1",
            location="us-east-1",
            service_name="web-api",
            service_owner="team-alpha",
        ),
        is_enriched=True,
    )


def _make_playbook_match() -> PlaybookMatch:
    """Create a PlaybookMatch for testing."""
    return PlaybookMatch(
        rule_name="test-rule",
        playbook_path="/playbooks/restart_service.yml",
        matched_attributes=3,
    )


def _make_execution_result(playbook_path: str = "/playbooks/restart_service.yml") -> ExecutionResult:
    """Create a successful ExecutionResult for testing."""
    return ExecutionResult(
        status=RemediationStatus.SUCCESS,
        return_code=0,
        stdout="ok",
        stderr="",
        duration_seconds=2.5,
        playbook_path=playbook_path,
        target_host="host1.example.com",
    )


def _build_orchestrator(
    normalizer=None,
    enricher=None,
    mapper=None,
    executor=None,
    dispatcher=None,
    audit_logger=None,
    metrics_collector=None,
):
    """Build an Orchestrator with mocked components."""
    return Orchestrator(
        normalizer=normalizer or MagicMock(spec=Normalizer),
        enricher=enricher or MagicMock(spec=Enricher),
        mapper=mapper or MagicMock(spec=PlaybookMapper),
        executor=executor or AsyncMock(spec=RemediationExecutor),
        dispatcher=dispatcher or AsyncMock(spec=NotificationDispatcher),
        audit_logger=audit_logger or MagicMock(spec=AuditLogger),
        metrics_collector=metrics_collector or MagicMock(spec=MetricsCollector),
    )


# --- Property 21: Pipeline UUID uniqueness and sequential execution ---


class TestPipelineUUIDUniquenessAndSequentialExecution:
    """Property tests for pipeline UUID uniqueness and sequential execution (Property 21).

    **Validates: Requirements 7.1**

    For any AlertmanagerPayload processed by the Orchestrator, each individual alert
    SHALL be assigned a unique UUID-format incident identifier, and pipeline stages
    SHALL execute in the defined sequence (normalize → enrich → match → execute → notify).
    """

    @given(payload=alertmanager_payload_strategy)
    @settings(max_examples=100, deadline=10000)
    def test_each_alert_gets_unique_uuid_incident_id(
        self,
        payload: AlertmanagerPayload,
    ) -> None:
        """Each alert in the payload SHALL be assigned a unique UUID-format incident ID.

        **Validates: Requirements 7.1**
        """
        # Use the real normalizer to generate incident IDs
        normalizer = Normalizer()

        # Create mocks for remaining components
        enricher = MagicMock(spec=Enricher)
        mapper = MagicMock(spec=PlaybookMapper)
        executor = AsyncMock(spec=RemediationExecutor)
        dispatcher = AsyncMock(spec=NotificationDispatcher)
        audit_logger = MagicMock(spec=AuditLogger)
        metrics = MagicMock(spec=MetricsCollector)

        # Configure enricher to return enriched alerts
        def enrich_side_effect(alert):
            return _make_enriched_alert(alert)

        enricher.enrich.side_effect = enrich_side_effect

        # Configure mapper to return a match
        mapper.match.return_value = _make_playbook_match()

        # Configure executor to return success
        executor.execute = AsyncMock(return_value=_make_execution_result())

        # Configure dispatcher
        dispatcher.notify_remediation = AsyncMock()
        dispatcher.notify_incident = AsyncMock()
        dispatcher.notify_manual_triage = AsyncMock()

        orchestrator = Orchestrator(
            normalizer=normalizer,
            enricher=enricher,
            mapper=mapper,
            executor=executor,
            dispatcher=dispatcher,
            audit_logger=audit_logger,
            metrics_collector=metrics,
        )

        incident_ids = asyncio.run(orchestrator.process_alert_payload(payload))

        # Verify we got one incident_id per alert
        assert len(incident_ids) == len(payload.alerts), (
            f"Expected {len(payload.alerts)} incident IDs, got {len(incident_ids)}"
        )

        # Verify all incident IDs are unique
        assert len(set(incident_ids)) == len(incident_ids), (
            f"Incident IDs are not unique: {incident_ids}"
        )

        # Verify each incident ID is a valid UUID format
        for iid in incident_ids:
            try:
                parsed = uuid.UUID(iid)
                assert str(parsed) == iid, (
                    f"Incident ID '{iid}' is not in standard UUID format"
                )
            except ValueError:
                raise AssertionError(
                    f"Incident ID '{iid}' is not a valid UUID"
                )

    @given(payload=alertmanager_payload_strategy)
    @settings(max_examples=100, deadline=10000)
    def test_pipeline_stages_execute_in_defined_sequence(
        self,
        payload: AlertmanagerPayload,
    ) -> None:
        """Pipeline stages SHALL execute in the defined sequence:
        normalize → enrich → match → execute → notify.

        **Validates: Requirements 7.1**
        """
        # Track call order
        call_order = []

        normalizer = MagicMock(spec=Normalizer)
        enricher = MagicMock(spec=Enricher)
        mapper = MagicMock(spec=PlaybookMapper)
        executor = AsyncMock(spec=RemediationExecutor)
        dispatcher = AsyncMock(spec=NotificationDispatcher)
        audit_logger = MagicMock(spec=AuditLogger)
        metrics = MagicMock(spec=MetricsCollector)

        # Create normalized alerts for the payload
        normalized_alerts = [
            _make_normalized_alert(alert_name=f"Alert{i}")
            for i in range(len(payload.alerts))
        ]

        def normalize_side_effect(p):
            call_order.append("normalize")
            return normalized_alerts

        normalizer.normalize.side_effect = normalize_side_effect

        def enrich_side_effect(alert):
            call_order.append("enrich")
            return _make_enriched_alert(alert)

        enricher.enrich.side_effect = enrich_side_effect

        def match_side_effect(enriched):
            call_order.append("match")
            return _make_playbook_match()

        mapper.match.side_effect = match_side_effect

        async def execute_side_effect(*args, **kwargs):
            call_order.append("execute")
            return _make_execution_result()

        executor.execute = AsyncMock(side_effect=execute_side_effect)

        async def notify_side_effect(*args, **kwargs):
            call_order.append("notify")

        dispatcher.notify_remediation = AsyncMock(side_effect=notify_side_effect)
        dispatcher.notify_incident = AsyncMock()
        dispatcher.notify_manual_triage = AsyncMock()

        orchestrator = Orchestrator(
            normalizer=normalizer,
            enricher=enricher,
            mapper=mapper,
            executor=executor,
            dispatcher=dispatcher,
            audit_logger=audit_logger,
            metrics_collector=metrics,
        )

        asyncio.run(orchestrator.process_alert_payload(payload))

        # Verify normalize is called first
        assert call_order[0] == "normalize", (
            f"First stage should be 'normalize', got '{call_order[0]}'"
        )

        # For each alert, verify the sequence: enrich → match → execute → notify
        expected_per_alert = ["enrich", "match", "execute", "notify"]
        remaining = call_order[1:]  # Skip the initial normalize

        num_alerts = len(payload.alerts)
        for i in range(num_alerts):
            offset = i * len(expected_per_alert)
            alert_stages = remaining[offset:offset + len(expected_per_alert)]
            assert alert_stages == expected_per_alert, (
                f"Alert {i} stages should be {expected_per_alert}, got {alert_stages}. "
                f"Full call order: {call_order}"
            )


# --- Property 22: Stage failure triggers logging and notification ---


class TestStageFailureTriggersLoggingAndNotification:
    """Property tests for stage failure handling (Property 22).

    **Validates: Requirements 7.3**

    For any pipeline stage that fails with an unhandled exception, the Orchestrator
    SHALL log the failure with incident ID and stage name, skip remaining stages,
    and dispatch a failure notification.
    """

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_enrich_stage_failure_dispatches_notification(
        self,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """When the enrich stage fails, a failure notification SHALL be dispatched
        and the executor SHALL NOT be called.

        **Validates: Requirements 7.3**
        """
        normalizer = MagicMock(spec=Normalizer)
        enricher = MagicMock(spec=Enricher)
        mapper = MagicMock(spec=PlaybookMapper)
        executor = AsyncMock(spec=RemediationExecutor)
        dispatcher = AsyncMock(spec=NotificationDispatcher)
        audit_logger = MagicMock(spec=AuditLogger)
        metrics = MagicMock(spec=MetricsCollector)

        normalized_alert = _make_normalized_alert(
            alert_name=alert_name, severity=severity
        )
        normalizer.normalize.return_value = [normalized_alert]

        # Make enrich stage raise an exception
        enricher.enrich.side_effect = RuntimeError("Enrichment service unavailable")

        # Configure dispatcher
        dispatcher.notify_incident = AsyncMock()
        dispatcher.notify_remediation = AsyncMock()
        dispatcher.notify_manual_triage = AsyncMock()

        # Configure executor
        executor.execute = AsyncMock()

        orchestrator = Orchestrator(
            normalizer=normalizer,
            enricher=enricher,
            mapper=mapper,
            executor=executor,
            dispatcher=dispatcher,
            audit_logger=audit_logger,
            metrics_collector=metrics,
        )

        payload = AlertmanagerPayload(
            version="4",
            group_key="test",
            status="firing",
            receiver="test",
            alerts=[
                AlertmanagerAlert(
                    status="firing",
                    labels={"alertname": alert_name, "severity": "critical"},
                    annotations={},
                    starts_at="2024-01-01T00:00:00Z",
                    ends_at="0001-01-01T00:00:00Z",
                )
            ],
        )

        asyncio.run(orchestrator.process_alert_payload(payload))

        # Verify failure notification was dispatched
        dispatcher.notify_incident.assert_called_once()

        # Verify executor was NOT called (remaining stages skipped)
        executor.execute.assert_not_called()

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_match_stage_failure_dispatches_notification(
        self,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """When the match stage fails, a failure notification SHALL be dispatched
        and the executor SHALL NOT be called.

        **Validates: Requirements 7.3**
        """
        normalizer = MagicMock(spec=Normalizer)
        enricher = MagicMock(spec=Enricher)
        mapper = MagicMock(spec=PlaybookMapper)
        executor = AsyncMock(spec=RemediationExecutor)
        dispatcher = AsyncMock(spec=NotificationDispatcher)
        audit_logger = MagicMock(spec=AuditLogger)
        metrics = MagicMock(spec=MetricsCollector)

        normalized_alert = _make_normalized_alert(
            alert_name=alert_name, severity=severity
        )
        normalizer.normalize.return_value = [normalized_alert]

        # Enricher works fine
        enricher.enrich.side_effect = lambda a: _make_enriched_alert(a)

        # Make match stage raise an exception
        mapper.match.side_effect = RuntimeError("Mapping config corrupted")

        # Configure dispatcher
        dispatcher.notify_incident = AsyncMock()
        dispatcher.notify_remediation = AsyncMock()
        dispatcher.notify_manual_triage = AsyncMock()

        # Configure executor
        executor.execute = AsyncMock()

        orchestrator = Orchestrator(
            normalizer=normalizer,
            enricher=enricher,
            mapper=mapper,
            executor=executor,
            dispatcher=dispatcher,
            audit_logger=audit_logger,
            metrics_collector=metrics,
        )

        payload = AlertmanagerPayload(
            version="4",
            group_key="test",
            status="firing",
            receiver="test",
            alerts=[
                AlertmanagerAlert(
                    status="firing",
                    labels={"alertname": alert_name, "severity": "critical"},
                    annotations={},
                    starts_at="2024-01-01T00:00:00Z",
                    ends_at="0001-01-01T00:00:00Z",
                )
            ],
        )

        asyncio.run(orchestrator.process_alert_payload(payload))

        # Verify failure notification was dispatched
        dispatcher.notify_incident.assert_called_once()

        # Verify executor was NOT called (remaining stages skipped)
        executor.execute.assert_not_called()

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_execute_stage_failure_dispatches_notification(
        self,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """When the execute stage fails, a failure notification SHALL be dispatched.

        **Validates: Requirements 7.3**
        """
        normalizer = MagicMock(spec=Normalizer)
        enricher = MagicMock(spec=Enricher)
        mapper = MagicMock(spec=PlaybookMapper)
        executor = AsyncMock(spec=RemediationExecutor)
        dispatcher = AsyncMock(spec=NotificationDispatcher)
        audit_logger = MagicMock(spec=AuditLogger)
        metrics = MagicMock(spec=MetricsCollector)

        normalized_alert = _make_normalized_alert(
            alert_name=alert_name, severity=severity
        )
        normalizer.normalize.return_value = [normalized_alert]

        # Enricher and mapper work fine
        enricher.enrich.side_effect = lambda a: _make_enriched_alert(a)
        mapper.match.return_value = _make_playbook_match()

        # Make execute stage raise an exception
        executor.execute = AsyncMock(
            side_effect=RuntimeError("Ansible subprocess crashed")
        )

        # Configure dispatcher
        dispatcher.notify_incident = AsyncMock()
        dispatcher.notify_remediation = AsyncMock()
        dispatcher.notify_manual_triage = AsyncMock()

        orchestrator = Orchestrator(
            normalizer=normalizer,
            enricher=enricher,
            mapper=mapper,
            executor=executor,
            dispatcher=dispatcher,
            audit_logger=audit_logger,
            metrics_collector=metrics,
        )

        payload = AlertmanagerPayload(
            version="4",
            group_key="test",
            status="firing",
            receiver="test",
            alerts=[
                AlertmanagerAlert(
                    status="firing",
                    labels={"alertname": alert_name, "severity": "critical"},
                    annotations={},
                    starts_at="2024-01-01T00:00:00Z",
                    ends_at="0001-01-01T00:00:00Z",
                )
            ],
        )

        asyncio.run(orchestrator.process_alert_payload(payload))

        # Verify failure notification was dispatched
        dispatcher.notify_incident.assert_called_once()

        # Verify notify_remediation was NOT called (pipeline stopped at execute)
        dispatcher.notify_remediation.assert_not_called()


# --- Property 23: Unmatched alert skips execution ---


class TestUnmatchedAlertSkipsExecution:
    """Property tests for unmatched alert handling (Property 23).

    **Validates: Requirements 7.5**

    For any alert with no matching playbook, the Orchestrator SHALL skip the
    remediation execution stage and dispatch a manual triage notification.
    """

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_unmatched_alert_skips_executor(
        self,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """When mapper returns None (no match), the executor SHALL NOT be called.

        **Validates: Requirements 7.5**
        """
        normalizer = MagicMock(spec=Normalizer)
        enricher = MagicMock(spec=Enricher)
        mapper = MagicMock(spec=PlaybookMapper)
        executor = AsyncMock(spec=RemediationExecutor)
        dispatcher = AsyncMock(spec=NotificationDispatcher)
        audit_logger = MagicMock(spec=AuditLogger)
        metrics = MagicMock(spec=MetricsCollector)

        normalized_alert = _make_normalized_alert(
            alert_name=alert_name, severity=severity
        )
        normalizer.normalize.return_value = [normalized_alert]

        # Enricher works fine
        enricher.enrich.side_effect = lambda a: _make_enriched_alert(a)

        # Mapper returns None (no match)
        mapper.match.return_value = None

        # Configure executor
        executor.execute = AsyncMock()

        # Configure dispatcher
        dispatcher.notify_incident = AsyncMock()
        dispatcher.notify_remediation = AsyncMock()
        dispatcher.notify_manual_triage = AsyncMock()

        orchestrator = Orchestrator(
            normalizer=normalizer,
            enricher=enricher,
            mapper=mapper,
            executor=executor,
            dispatcher=dispatcher,
            audit_logger=audit_logger,
            metrics_collector=metrics,
        )

        payload = AlertmanagerPayload(
            version="4",
            group_key="test",
            status="firing",
            receiver="test",
            alerts=[
                AlertmanagerAlert(
                    status="firing",
                    labels={"alertname": alert_name, "severity": "critical"},
                    annotations={},
                    starts_at="2024-01-01T00:00:00Z",
                    ends_at="0001-01-01T00:00:00Z",
                )
            ],
        )

        asyncio.run(orchestrator.process_alert_payload(payload))

        # Verify executor was NOT called
        executor.execute.assert_not_called()

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_unmatched_alert_dispatches_manual_triage(
        self,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """When mapper returns None, notify_manual_triage SHALL be called.

        **Validates: Requirements 7.5**
        """
        normalizer = MagicMock(spec=Normalizer)
        enricher = MagicMock(spec=Enricher)
        mapper = MagicMock(spec=PlaybookMapper)
        executor = AsyncMock(spec=RemediationExecutor)
        dispatcher = AsyncMock(spec=NotificationDispatcher)
        audit_logger = MagicMock(spec=AuditLogger)
        metrics = MagicMock(spec=MetricsCollector)

        normalized_alert = _make_normalized_alert(
            alert_name=alert_name, severity=severity
        )
        normalizer.normalize.return_value = [normalized_alert]

        # Enricher works fine
        enricher.enrich.side_effect = lambda a: _make_enriched_alert(a)

        # Mapper returns None (no match)
        mapper.match.return_value = None

        # Configure executor
        executor.execute = AsyncMock()

        # Configure dispatcher
        dispatcher.notify_incident = AsyncMock()
        dispatcher.notify_remediation = AsyncMock()
        dispatcher.notify_manual_triage = AsyncMock()

        orchestrator = Orchestrator(
            normalizer=normalizer,
            enricher=enricher,
            mapper=mapper,
            executor=executor,
            dispatcher=dispatcher,
            audit_logger=audit_logger,
            metrics_collector=metrics,
        )

        payload = AlertmanagerPayload(
            version="4",
            group_key="test",
            status="firing",
            receiver="test",
            alerts=[
                AlertmanagerAlert(
                    status="firing",
                    labels={"alertname": alert_name, "severity": "critical"},
                    annotations={},
                    starts_at="2024-01-01T00:00:00Z",
                    ends_at="0001-01-01T00:00:00Z",
                )
            ],
        )

        asyncio.run(orchestrator.process_alert_payload(payload))

        # Verify manual triage notification was dispatched
        dispatcher.notify_manual_triage.assert_called_once()

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=10000)
    def test_unmatched_alert_does_not_notify_remediation(
        self,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """When mapper returns None, notify_remediation SHALL NOT be called.

        **Validates: Requirements 7.5**
        """
        normalizer = MagicMock(spec=Normalizer)
        enricher = MagicMock(spec=Enricher)
        mapper = MagicMock(spec=PlaybookMapper)
        executor = AsyncMock(spec=RemediationExecutor)
        dispatcher = AsyncMock(spec=NotificationDispatcher)
        audit_logger = MagicMock(spec=AuditLogger)
        metrics = MagicMock(spec=MetricsCollector)

        normalized_alert = _make_normalized_alert(
            alert_name=alert_name, severity=severity
        )
        normalizer.normalize.return_value = [normalized_alert]

        # Enricher works fine
        enricher.enrich.side_effect = lambda a: _make_enriched_alert(a)

        # Mapper returns None (no match)
        mapper.match.return_value = None

        # Configure executor
        executor.execute = AsyncMock()

        # Configure dispatcher
        dispatcher.notify_incident = AsyncMock()
        dispatcher.notify_remediation = AsyncMock()
        dispatcher.notify_manual_triage = AsyncMock()

        orchestrator = Orchestrator(
            normalizer=normalizer,
            enricher=enricher,
            mapper=mapper,
            executor=executor,
            dispatcher=dispatcher,
            audit_logger=audit_logger,
            metrics_collector=metrics,
        )

        payload = AlertmanagerPayload(
            version="4",
            group_key="test",
            status="firing",
            receiver="test",
            alerts=[
                AlertmanagerAlert(
                    status="firing",
                    labels={"alertname": alert_name, "severity": "critical"},
                    annotations={},
                    starts_at="2024-01-01T00:00:00Z",
                    ends_at="0001-01-01T00:00:00Z",
                )
            ],
        )

        asyncio.run(orchestrator.process_alert_payload(payload))

        # Verify remediation notification was NOT dispatched
        dispatcher.notify_remediation.assert_not_called()
