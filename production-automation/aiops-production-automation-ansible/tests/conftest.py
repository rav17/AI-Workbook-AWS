"""Shared fixtures and generators for the self-healing infrastructure test suite."""

import pytest
from datetime import datetime, timezone
from hypothesis import strategies as st


# --- Hypothesis Strategies (Generators) ---

def alertmanager_severity_strategy():
    """Generate valid Alertmanager severity values."""
    return st.sampled_from(["critical", "warning", "info"])


def extended_severity_strategy():
    """Generate severity values including unknown/invalid ones."""
    return st.one_of(
        alertmanager_severity_strategy(),
        st.text(min_size=1, max_size=20),
    )


def alert_status_strategy():
    """Generate valid alert status values."""
    return st.sampled_from(["firing", "resolved"])


def labels_strategy():
    """Generate alert labels dictionaries."""
    return st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=30,
        ),
        values=st.text(min_size=0, max_size=100),
        min_size=0,
        max_size=10,
    )


def annotations_strategy():
    """Generate alert annotations dictionaries."""
    return st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=30,
        ),
        values=st.text(min_size=0, max_size=200),
        min_size=0,
        max_size=5,
    )


def iso_timestamp_strategy():
    """Generate ISO 8601 timestamp strings."""
    return st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
        timezones=st.just(timezone.utc),
    ).map(lambda dt: dt.isoformat())


def alertmanager_alert_strategy():
    """Generate a single Alertmanager alert dictionary."""
    return st.fixed_dictionaries({
        "status": alert_status_strategy(),
        "labels": st.fixed_dictionaries({
            "alertname": st.text(min_size=1, max_size=50),
            "severity": extended_severity_strategy(),
        }).flatmap(lambda base: labels_strategy().map(lambda extra: {**extra, **base})),
        "annotations": annotations_strategy(),
        "startsAt": iso_timestamp_strategy(),
        "endsAt": iso_timestamp_strategy(),
        "generatorURL": st.just("http://prometheus:9090/graph"),
        "fingerprint": st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=8,
            max_size=16,
        ),
    })


def valid_alertmanager_payload_strategy():
    """Generate a valid Alertmanager webhook payload."""
    return st.fixed_dictionaries({
        "version": st.just("4"),
        "groupKey": st.text(min_size=1, max_size=100),
        "status": alert_status_strategy(),
        "receiver": st.text(min_size=1, max_size=50),
        "alerts": st.lists(alertmanager_alert_strategy(), min_size=1, max_size=20),
        "groupLabels": labels_strategy(),
        "commonLabels": labels_strategy(),
        "commonAnnotations": annotations_strategy(),
        "externalURL": st.just("http://alertmanager:9093"),
    })


# --- Pytest Fixtures ---

@pytest.fixture
def sample_alertmanager_payload():
    """A minimal valid Alertmanager webhook payload for unit tests."""
    return {
        "version": "4",
        "groupKey": "test-group",
        "status": "firing",
        "receiver": "self-healing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "HighCPUUsage",
                    "severity": "critical",
                    "instance": "web-server-01:9090",
                    "job": "node-exporter",
                },
                "annotations": {
                    "summary": "CPU usage is above 90%",
                    "description": "Instance web-server-01 has CPU usage above 90% for 5 minutes.",
                },
                "startsAt": "2024-01-15T10:30:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph",
                "fingerprint": "abc123def456",
            }
        ],
        "groupLabels": {"alertname": "HighCPUUsage"},
        "commonLabels": {"severity": "critical"},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093",
    }


@pytest.fixture
def sample_asset_inventory():
    """Sample asset inventory data for unit tests."""
    return {
        "web-server-01:9090": {
            "hostname": "web-server-01",
            "ip_address": "10.0.1.10",
            "location": "us-east-1a",
            "service_name": "web-frontend",
            "service_owner": "platform-team",
        },
        "db-server-01:9090": {
            "hostname": "db-server-01",
            "ip_address": "10.0.2.20",
            "location": "us-east-1b",
            "service_name": "postgres-primary",
            "service_owner": "database-team",
        },
    }


@pytest.fixture
def sample_mapping_rules():
    """Sample playbook mapping rules for unit tests."""
    return [
        {
            "name": "high-cpu-restart",
            "conditions": {
                "alert_name": "HighCPUUsage",
                "severity": "P1",
            },
            "playbook_path": "playbooks/restart_service.yml",
        },
        {
            "name": "disk-cleanup",
            "conditions": {
                "alert_name": "DiskSpaceLow",
            },
            "playbook_path": "playbooks/clear_disk.yml",
        },
    ]


@pytest.fixture
def sample_execution_result():
    """Sample execution result for unit tests."""
    return {
        "status": "success",
        "return_code": 0,
        "stdout": "PLAY [Restart service] ***\nok: [web-server-01]\n",
        "stderr": "",
        "duration_seconds": 12.5,
        "playbook_path": "playbooks/restart_service.yml",
        "target_host": "web-server-01",
    }
