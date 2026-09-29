"""Unit tests for the AssetInventory and Enricher classes."""

import os
import tempfile
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import yaml

from src.enricher import AssetInventory, Enricher, LOOKUP_LABEL_PRIORITY
from src.models import NormalizedAlert, Severity, AlertStatus


# --- Fixtures ---


@pytest.fixture
def sample_normalized_alert():
    """Create a sample normalized alert for testing."""
    return NormalizedAlert(
        incident_id="test-incident-001",
        alert_name="HighCPUUsage",
        severity=Severity.P1,
        status=AlertStatus.FIRING,
        labels={
            "instance": "web-server-01:9090",
            "hostname": "web-server-01",
            "job": "node-exporter",
            "alertname": "HighCPUUsage",
            "severity": "critical",
        },
        annotations={"summary": "CPU usage is above 90%"},
        starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        ends_at=None,
        raw_fingerprint="abc123",
    )


@pytest.fixture
def sample_inventory_data():
    """Sample asset inventory data."""
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
def inventory_with_data(sample_inventory_data):
    """Create an AssetInventory pre-loaded with sample data."""
    inventory = AssetInventory()
    inventory.set_assets(sample_inventory_data)
    return inventory


@pytest.fixture
def enricher(inventory_with_data):
    """Create an Enricher with a pre-loaded inventory."""
    return Enricher(inventory_with_data)


@pytest.fixture
def temp_inventory_file(sample_inventory_data):
    """Create a temporary YAML inventory file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    ) as f:
        yaml.dump({"assets": sample_inventory_data}, f)
        path = f.name
    yield path
    os.unlink(path)


# --- AssetInventory Tests ---


class TestAssetInventory:
    """Tests for the AssetInventory class."""

    def test_load_from_yaml_file(self, temp_inventory_file):
        """Test loading inventory from a valid YAML file."""
        inventory = AssetInventory(temp_inventory_file)
        assert inventory.is_loaded
        assert inventory.asset_count == 2

    def test_lookup_existing_asset(self, inventory_with_data):
        """Test looking up an existing asset."""
        result = inventory_with_data.lookup("web-server-01:9090")
        assert result is not None
        assert result["hostname"] == "web-server-01"
        assert result["ip_address"] == "10.0.1.10"

    def test_lookup_missing_asset(self, inventory_with_data):
        """Test looking up a non-existent asset."""
        result = inventory_with_data.lookup("nonexistent-host")
        assert result is None

    def test_empty_inventory_path(self):
        """Test creating inventory with no path."""
        inventory = AssetInventory()
        assert not inventory.is_loaded
        assert inventory.asset_count == 0

    def test_nonexistent_file_path(self):
        """Test loading from a non-existent file."""
        inventory = AssetInventory("/nonexistent/path/inventory.yml")
        assert not inventory.is_loaded
        assert inventory.asset_count == 0

    def test_malformed_yaml_file(self):
        """Test loading from a malformed YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False, encoding="utf-8"
        ) as f:
            f.write("invalid: yaml: [unclosed")
            path = f.name
        try:
            inventory = AssetInventory(path)
            # Should not crash, just not load
            assert inventory.asset_count == 0
        finally:
            os.unlink(path)

    def test_empty_yaml_file(self):
        """Test loading from an empty YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            path = f.name
        try:
            inventory = AssetInventory(path)
            assert not inventory.is_loaded
        finally:
            os.unlink(path)

    def test_hot_reload_detects_changes(self, temp_inventory_file):
        """Test that reload detects file modifications."""
        inventory = AssetInventory(temp_inventory_file)
        assert inventory.asset_count == 2

        # Modify the file with new data
        time.sleep(0.1)  # Ensure mtime changes
        new_data = {
            "assets": {
                "new-server:9090": {
                    "hostname": "new-server",
                    "ip_address": "10.0.3.30",
                    "location": "us-west-2a",
                    "service_name": "api-gateway",
                    "service_owner": "api-team",
                }
            }
        }
        with open(temp_inventory_file, "w", encoding="utf-8") as f:
            yaml.dump(new_data, f)

        # Force mtime to be newer
        os.utime(temp_inventory_file, (time.time() + 1, time.time() + 1))

        reloaded = inventory.reload()
        assert reloaded
        assert inventory.asset_count == 1
        assert inventory.lookup("new-server:9090") is not None

    def test_reload_no_changes(self, temp_inventory_file):
        """Test that reload returns False when file hasn't changed."""
        inventory = AssetInventory(temp_inventory_file)
        reloaded = inventory.reload()
        assert not reloaded

    def test_flat_format_inventory(self):
        """Test loading inventory in flat format (without 'assets' key)."""
        data = {
            "server-01:9090": {
                "hostname": "server-01",
                "ip_address": "10.0.1.1",
                "location": "us-east-1",
                "service_name": "web",
                "service_owner": "team-a",
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False, encoding="utf-8"
        ) as f:
            yaml.dump(data, f)
            path = f.name
        try:
            inventory = AssetInventory(path)
            assert inventory.is_loaded
            assert inventory.asset_count == 1
            assert inventory.lookup("server-01:9090") is not None
        finally:
            os.unlink(path)

    def test_set_assets_directly(self):
        """Test setting assets directly for testing purposes."""
        inventory = AssetInventory()
        inventory.set_assets({"key1": {"hostname": "host1"}})
        assert inventory.is_loaded
        assert inventory.asset_count == 1
        assert inventory.lookup("key1") == {"hostname": "host1"}


# --- Enricher Tests ---


class TestEnricher:
    """Tests for the Enricher class."""

    def test_enrich_with_instance_label(self, enricher, sample_normalized_alert):
        """Test enrichment using the 'instance' label (highest priority)."""
        result = enricher.enrich(sample_normalized_alert)
        assert result.is_enriched
        assert result.asset is not None
        assert result.asset.hostname == "web-server-01"
        assert result.asset.ip_address == "10.0.1.10"
        assert result.asset.location == "us-east-1a"
        assert result.asset.service_name == "web-frontend"
        assert result.asset.service_owner == "platform-team"

    def test_enrich_with_hostname_label(self, enricher):
        """Test enrichment falls back to 'hostname' label."""
        alert = NormalizedAlert(
            incident_id="test-002",
            alert_name="HighMemory",
            severity=Severity.P2,
            status=AlertStatus.FIRING,
            labels={"hostname": "web-server-01:9090", "job": "node-exporter"},
            annotations={},
            starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            ends_at=None,
        )
        result = enricher.enrich(alert)
        assert result.is_enriched
        assert result.asset.hostname == "web-server-01"

    def test_enrich_with_job_label(self, inventory_with_data):
        """Test enrichment falls back to 'job' label."""
        # Add an asset keyed by job name
        inventory_with_data.set_assets(
            {"node-exporter": {"hostname": "job-host", "ip_address": "10.0.0.1",
                               "location": "us-west-1", "service_name": "monitoring",
                               "service_owner": "ops-team"}}
        )
        enricher = Enricher(inventory_with_data)
        alert = NormalizedAlert(
            incident_id="test-003",
            alert_name="HighMemory",
            severity=Severity.P2,
            status=AlertStatus.FIRING,
            labels={"job": "node-exporter"},
            annotations={},
            starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            ends_at=None,
        )
        result = enricher.enrich(alert)
        assert result.is_enriched
        assert result.asset.hostname == "job-host"

    def test_enrich_no_lookup_labels(self, enricher):
        """Test enrichment when no lookup labels are present."""
        alert = NormalizedAlert(
            incident_id="test-004",
            alert_name="SomeAlert",
            severity=Severity.P3,
            status=AlertStatus.FIRING,
            labels={"alertname": "SomeAlert", "severity": "info"},
            annotations={},
            starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            ends_at=None,
        )
        result = enricher.enrich(alert)
        assert not result.is_enriched
        assert result.asset is None

    def test_enrich_empty_lookup_labels(self, enricher):
        """Test enrichment when lookup labels are empty strings."""
        alert = NormalizedAlert(
            incident_id="test-005",
            alert_name="SomeAlert",
            severity=Severity.P3,
            status=AlertStatus.FIRING,
            labels={"instance": "", "hostname": "", "job": ""},
            annotations={},
            starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            ends_at=None,
        )
        result = enricher.enrich(alert)
        assert not result.is_enriched
        assert result.asset is None

    def test_enrich_asset_not_found(self, enricher):
        """Test enrichment when asset is not in inventory."""
        alert = NormalizedAlert(
            incident_id="test-006",
            alert_name="SomeAlert",
            severity=Severity.P2,
            status=AlertStatus.FIRING,
            labels={"instance": "unknown-host:9090"},
            annotations={},
            starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            ends_at=None,
        )
        result = enricher.enrich(alert)
        assert not result.is_enriched
        assert result.asset is None

    def test_enrich_preserves_alert_fields(self, enricher, sample_normalized_alert):
        """Test that enrichment preserves all original alert fields."""
        result = enricher.enrich(sample_normalized_alert)
        assert result.incident_id == sample_normalized_alert.incident_id
        assert result.alert_name == sample_normalized_alert.alert_name
        assert result.severity == sample_normalized_alert.severity
        assert result.status == sample_normalized_alert.status
        assert result.labels == sample_normalized_alert.labels
        assert result.annotations == sample_normalized_alert.annotations
        assert result.starts_at == sample_normalized_alert.starts_at
        assert result.ends_at == sample_normalized_alert.ends_at

    def test_enrich_with_missing_asset_fields(self):
        """Test enrichment when asset has missing fields (set to empty string)."""
        inventory = AssetInventory()
        inventory.set_assets({
            "partial-host:9090": {
                "hostname": "partial-host",
                "ip_address": "10.0.1.1",
                # location, service_name, service_owner are missing
            }
        })
        enricher = Enricher(inventory)
        alert = NormalizedAlert(
            incident_id="test-007",
            alert_name="Alert",
            severity=Severity.P2,
            status=AlertStatus.FIRING,
            labels={"instance": "partial-host:9090"},
            annotations={},
            starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            ends_at=None,
        )
        result = enricher.enrich(alert)
        assert result.is_enriched
        assert result.asset.hostname == "partial-host"
        assert result.asset.ip_address == "10.0.1.1"
        assert result.asset.location == ""
        assert result.asset.service_name == ""
        assert result.asset.service_owner == ""

    def test_enrich_instance_takes_priority_over_hostname(self, enricher):
        """Test that 'instance' label takes priority over 'hostname'."""
        # inventory has "web-server-01:9090" but not "web-server-01"
        alert = NormalizedAlert(
            incident_id="test-008",
            alert_name="Alert",
            severity=Severity.P1,
            status=AlertStatus.FIRING,
            labels={
                "instance": "web-server-01:9090",
                "hostname": "some-other-host",
            },
            annotations={},
            starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            ends_at=None,
        )
        result = enricher.enrich(alert)
        # Should use instance label, which matches
        assert result.is_enriched
        assert result.asset.hostname == "web-server-01"

    def test_enrich_corrupted_asset_data(self):
        """Test enrichment handles corrupted asset data gracefully."""
        inventory = AssetInventory()
        # Simulate corrupted data that would cause TypeError in AssetInfo construction
        inventory.set_assets({"bad-host:9090": None})  # type: ignore
        enricher = Enricher(inventory)
        alert = NormalizedAlert(
            incident_id="test-009",
            alert_name="Alert",
            severity=Severity.P2,
            status=AlertStatus.FIRING,
            labels={"instance": "bad-host:9090"},
            annotations={},
            starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            ends_at=None,
        )
        # The lookup returns None for corrupted data since set_assets stores it
        # but _build_asset_info will fail
        result = enricher.enrich(alert)
        # When lookup returns a non-dict value, _build_asset_info raises ValueError
        assert not result.is_enriched
        assert result.asset is None

    def test_enrich_inventory_lookup_exception(self):
        """Test enrichment handles inventory lookup exceptions."""
        inventory = AssetInventory()
        inventory.set_assets({"host:9090": {"hostname": "host"}})

        # Patch lookup to raise an exception
        enricher = Enricher(inventory)
        with patch.object(inventory, "lookup", side_effect=RuntimeError("Connection failed")):
            alert = NormalizedAlert(
                incident_id="test-010",
                alert_name="Alert",
                severity=Severity.P2,
                status=AlertStatus.FIRING,
                labels={"instance": "host:9090"},
                annotations={},
                starts_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
                ends_at=None,
            )
            result = enricher.enrich(alert)
            assert not result.is_enriched
            assert result.asset is None

    def test_label_priority_order(self):
        """Test that LOOKUP_LABEL_PRIORITY is instance, hostname, job."""
        assert LOOKUP_LABEL_PRIORITY == ["instance", "hostname", "job"]
