# Feature: self-healing-infrastructure, Property 7: Enrichment lookup key priority
"""Property-based tests for the Enricher component.

Property 7: Enrichment lookup key priority
*For any* normalized alert, the Enricher SHALL derive the lookup key by checking
labels in priority order (instance → hostname → job), using the first non-empty
value found. If none are present or non-empty, the alert SHALL be marked as unenriched.

**Validates: Requirements 3.1, 3.5**

Property 9: Unresolved lookup produces unenriched alert
*For any* normalized alert where the lookup key does not match any asset in the
inventory, the resulting EnrichedAlert SHALL have is_enriched set to False and
asset set to None.

**Validates: Requirements 3.3**
"""

from datetime import datetime, timezone
from typing import Optional

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.enricher import AssetInventory, Enricher, LOOKUP_LABEL_PRIORITY
from src.models import AlertStatus, EnrichedAlert, NormalizedAlert, Severity


# --- Hypothesis Strategies ---

# Strategy for generating non-empty label values (valid lookup keys)
non_empty_label_value = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".-_:/"),
).filter(lambda s: s.strip() != "")

# Strategy for generating empty or whitespace-only label values
empty_label_value = st.one_of(
    st.just(""),
    st.text(
        alphabet=st.just(" "),
        min_size=1,
        max_size=5,
    ),
)

# Strategy for extra labels that do NOT include the priority keys
extra_labels_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        min_size=1,
        max_size=20,
    ).filter(lambda k: k not in LOOKUP_LABEL_PRIORITY),
    values=st.text(min_size=0, max_size=50),
    min_size=0,
    max_size=5,
)


# Strategy for generating a NormalizedAlert with specific labels
def normalized_alert_with_labels(labels: dict[str, str]) -> st.SearchStrategy[NormalizedAlert]:
    """Build a NormalizedAlert strategy with the given labels."""
    return st.builds(
        NormalizedAlert,
        incident_id=st.uuids().map(str),
        alert_name=st.text(min_size=1, max_size=50),
        severity=st.sampled_from(list(Severity)),
        status=st.sampled_from(list(AlertStatus)),
        labels=st.just(labels),
        annotations=st.just({}),
        starts_at=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        ends_at=st.none(),
        raw_fingerprint=st.just(""),
    )


def make_inventory_with_key(key: str) -> AssetInventory:
    """Create an AssetInventory that contains the given key."""
    inventory = AssetInventory()
    inventory.set_assets({
        key: {
            "hostname": f"host-{key}",
            "ip_address": "10.0.0.1",
            "location": "us-east-1a",
            "service_name": "test-service",
            "service_owner": "test-team",
        }
    })
    return inventory


class TestEnrichmentLookupKeyPriority:
    """Property tests for Enricher lookup key priority (Property 7).

    **Validates: Requirements 3.1, 3.5**
    """

    @given(
        instance_val=non_empty_label_value,
        hostname_val=st.one_of(non_empty_label_value, empty_label_value, st.just(None)),
        job_val=st.one_of(non_empty_label_value, empty_label_value, st.just(None)),
        extra_labels=extra_labels_strategy,
    )
    @settings(max_examples=100)
    def test_instance_label_has_highest_priority(
        self,
        instance_val: str,
        hostname_val: Optional[str],
        job_val: Optional[str],
        extra_labels: dict[str, str],
    ) -> None:
        """When 'instance' label is non-empty, it SHALL be used as the lookup key
        regardless of whether 'hostname' or 'job' are also present.

        **Validates: Requirements 3.1, 3.5**
        """
        labels = {**extra_labels, "instance": instance_val}
        if hostname_val is not None:
            labels["hostname"] = hostname_val
        if job_val is not None:
            labels["job"] = job_val

        inventory = make_inventory_with_key(instance_val.strip())
        enricher = Enricher(inventory)

        alert = NormalizedAlert(
            incident_id="test-id",
            alert_name="TestAlert",
            severity=Severity.P1,
            status=AlertStatus.FIRING,
            labels=labels,
            annotations={},
            starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ends_at=None,
        )

        result = enricher.enrich(alert)

        assert result.is_enriched is True
        assert result.asset is not None
        assert result.asset.hostname == f"host-{instance_val.strip()}"

    @given(
        hostname_val=non_empty_label_value,
        job_val=st.one_of(non_empty_label_value, empty_label_value, st.just(None)),
        extra_labels=extra_labels_strategy,
    )
    @settings(max_examples=100)
    def test_hostname_label_used_when_instance_absent_or_empty(
        self,
        hostname_val: str,
        job_val: Optional[str],
        extra_labels: dict[str, str],
    ) -> None:
        """When 'instance' is absent or empty but 'hostname' is non-empty,
        'hostname' SHALL be used as the lookup key.

        **Validates: Requirements 3.1, 3.5**
        """
        labels = {**extra_labels, "hostname": hostname_val}
        if job_val is not None:
            labels["job"] = job_val
        labels.pop("instance", None)

        inventory = make_inventory_with_key(hostname_val.strip())
        enricher = Enricher(inventory)

        alert = NormalizedAlert(
            incident_id="test-id",
            alert_name="TestAlert",
            severity=Severity.P2,
            status=AlertStatus.FIRING,
            labels=labels,
            annotations={},
            starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ends_at=None,
        )

        result = enricher.enrich(alert)

        assert result.is_enriched is True
        assert result.asset is not None
        assert result.asset.hostname == f"host-{hostname_val.strip()}"

    @given(
        hostname_val=non_empty_label_value,
        job_val=st.one_of(non_empty_label_value, empty_label_value, st.just(None)),
        instance_empty=empty_label_value,
        extra_labels=extra_labels_strategy,
    )
    @settings(max_examples=100)
    def test_hostname_used_when_instance_is_empty_string(
        self,
        hostname_val: str,
        job_val: Optional[str],
        instance_empty: str,
        extra_labels: dict[str, str],
    ) -> None:
        """When 'instance' is present but empty/whitespace, 'hostname' SHALL be used.

        **Validates: Requirements 3.1, 3.5**
        """
        labels = {**extra_labels, "instance": instance_empty, "hostname": hostname_val}
        if job_val is not None:
            labels["job"] = job_val

        inventory = make_inventory_with_key(hostname_val.strip())
        enricher = Enricher(inventory)

        alert = NormalizedAlert(
            incident_id="test-id",
            alert_name="TestAlert",
            severity=Severity.P3,
            status=AlertStatus.FIRING,
            labels=labels,
            annotations={},
            starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ends_at=None,
        )

        result = enricher.enrich(alert)

        assert result.is_enriched is True
        assert result.asset is not None
        assert result.asset.hostname == f"host-{hostname_val.strip()}"

    @given(
        job_val=non_empty_label_value,
        extra_labels=extra_labels_strategy,
    )
    @settings(max_examples=100)
    def test_job_label_used_when_instance_and_hostname_absent_or_empty(
        self,
        job_val: str,
        extra_labels: dict[str, str],
    ) -> None:
        """When 'instance' and 'hostname' are absent or empty but 'job' is non-empty,
        'job' SHALL be used as the lookup key.

        **Validates: Requirements 3.1, 3.5**
        """
        labels = {**extra_labels, "job": job_val}
        labels.pop("instance", None)
        labels.pop("hostname", None)

        inventory = make_inventory_with_key(job_val.strip())
        enricher = Enricher(inventory)

        alert = NormalizedAlert(
            incident_id="test-id",
            alert_name="TestAlert",
            severity=Severity.P1,
            status=AlertStatus.FIRING,
            labels=labels,
            annotations={},
            starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ends_at=None,
        )

        result = enricher.enrich(alert)

        assert result.is_enriched is True
        assert result.asset is not None
        assert result.asset.hostname == f"host-{job_val.strip()}"

    @given(
        instance_empty=st.one_of(empty_label_value, st.just(None)),
        hostname_empty=st.one_of(empty_label_value, st.just(None)),
        job_empty=st.one_of(empty_label_value, st.just(None)),
        extra_labels=extra_labels_strategy,
    )
    @settings(max_examples=100)
    def test_no_valid_lookup_key_marks_alert_unenriched(
        self,
        instance_empty: Optional[str],
        hostname_empty: Optional[str],
        job_empty: Optional[str],
        extra_labels: dict[str, str],
    ) -> None:
        """When none of the priority labels (instance, hostname, job) are present
        or non-empty, the alert SHALL be marked as unenriched.

        **Validates: Requirements 3.1, 3.5**
        """
        labels = dict(extra_labels)
        if instance_empty is not None:
            labels["instance"] = instance_empty
        else:
            labels.pop("instance", None)
        if hostname_empty is not None:
            labels["hostname"] = hostname_empty
        else:
            labels.pop("hostname", None)
        if job_empty is not None:
            labels["job"] = job_empty
        else:
            labels.pop("job", None)

        inventory = AssetInventory()
        inventory.set_assets({
            "some-host": {
                "hostname": "some-host",
                "ip_address": "10.0.0.1",
                "location": "us-east-1a",
                "service_name": "test-service",
                "service_owner": "test-team",
            }
        })
        enricher = Enricher(inventory)

        alert = NormalizedAlert(
            incident_id="test-id",
            alert_name="TestAlert",
            severity=Severity.P2,
            status=AlertStatus.FIRING,
            labels=labels,
            annotations={},
            starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ends_at=None,
        )

        result = enricher.enrich(alert)

        assert result.is_enriched is False
        assert result.asset is None

    @given(
        instance_val=non_empty_label_value,
        hostname_val=non_empty_label_value,
        job_val=non_empty_label_value,
        extra_labels=extra_labels_strategy,
    )
    @settings(max_examples=100)
    def test_priority_order_instance_over_hostname_over_job(
        self,
        instance_val: str,
        hostname_val: str,
        job_val: str,
        extra_labels: dict[str, str],
    ) -> None:
        """When all three priority labels are present and non-empty,
        'instance' SHALL be used (highest priority).

        **Validates: Requirements 3.1, 3.5**
        """
        assume(instance_val.strip() != hostname_val.strip())
        assume(instance_val.strip() != job_val.strip())
        assume(hostname_val.strip() != job_val.strip())

        labels = {
            **extra_labels,
            "instance": instance_val,
            "hostname": hostname_val,
            "job": job_val,
        }

        inventory = AssetInventory()
        inventory.set_assets({
            instance_val.strip(): {
                "hostname": "from-instance",
                "ip_address": "10.0.0.1",
                "location": "us-east-1a",
                "service_name": "svc-instance",
                "service_owner": "team-instance",
            },
            hostname_val.strip(): {
                "hostname": "from-hostname",
                "ip_address": "10.0.0.2",
                "location": "us-east-1b",
                "service_name": "svc-hostname",
                "service_owner": "team-hostname",
            },
            job_val.strip(): {
                "hostname": "from-job",
                "ip_address": "10.0.0.3",
                "location": "us-east-1c",
                "service_name": "svc-job",
                "service_owner": "team-job",
            },
        })
        enricher = Enricher(inventory)

        alert = NormalizedAlert(
            incident_id="test-id",
            alert_name="TestAlert",
            severity=Severity.P1,
            status=AlertStatus.FIRING,
            labels=labels,
            annotations={},
            starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ends_at=None,
        )

        result = enricher.enrich(alert)

        assert result.is_enriched is True
        assert result.asset is not None
        assert result.asset.hostname == "from-instance"


# --- Property 9: Unresolved lookup produces unenriched alert ---

# Strategy for generating non-empty lookup key values that won't match inventory
_non_matching_key_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_.:"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")

# Fixed inventory for Property 9 tests
FIXED_INVENTORY_ASSETS = {
    "web-server-01:9090": {
        "hostname": "web-server-01",
        "ip_address": "10.0.1.10",
        "location": "us-east-1a",
        "service_name": "web-frontend",
        "service_owner": "platform-team",
    },
    "db-server-01:5432": {
        "hostname": "db-server-01",
        "ip_address": "10.0.2.20",
        "location": "us-east-1b",
        "service_name": "postgres-primary",
        "service_owner": "database-team",
    },
    "cache-server-01:6379": {
        "hostname": "cache-server-01",
        "ip_address": "10.0.3.30",
        "location": "us-west-2a",
        "service_name": "redis-cache",
        "service_owner": "infra-team",
    },
}

FIXED_INVENTORY_KEYS = set(FIXED_INVENTORY_ASSETS.keys())


def _labels_with_unresolved_key_strategy(inventory_keys: set):
    """Generate labels with a lookup key that does not match any inventory asset."""
    unmatched_value = _non_matching_key_strategy.filter(
        lambda v: v not in inventory_keys
    )
    lookup_label = st.sampled_from(LOOKUP_LABEL_PRIORITY)
    extra = st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
            min_size=1,
            max_size=20,
        ).filter(lambda k: k not in LOOKUP_LABEL_PRIORITY),
        values=st.text(min_size=0, max_size=50),
        min_size=0,
        max_size=5,
    )
    return st.tuples(lookup_label, unmatched_value, extra).map(
        lambda t: {**t[2], t[0]: t[1]}
    )


def _normalized_alert_unresolved_strategy(inventory_keys: set):
    """Generate NormalizedAlert whose lookup key won't match any inventory asset."""
    return st.builds(
        NormalizedAlert,
        incident_id=st.uuids().map(str),
        alert_name=st.text(min_size=1, max_size=50),
        severity=st.sampled_from(list(Severity)),
        status=st.sampled_from(list(AlertStatus)),
        labels=_labels_with_unresolved_key_strategy(inventory_keys),
        annotations=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
            values=st.text(min_size=0, max_size=100),
            min_size=0,
            max_size=3,
        ),
        starts_at=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        ends_at=st.one_of(
            st.none(),
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2030, 12, 31),
                timezones=st.just(timezone.utc),
            ),
        ),
        raw_fingerprint=st.text(min_size=0, max_size=16, alphabet=st.characters(whitelist_categories=("L", "N"))),
    )


class TestUnresolvedLookupProducesUnenrichedAlert:
    """Property tests for unresolved lookup behavior (Property 9).

    **Validates: Requirements 3.3**

    For any normalized alert where the lookup key does not match any asset
    in the inventory, the resulting EnrichedAlert SHALL have is_enriched
    set to False and asset set to None.
    """

    @given(alert=_normalized_alert_unresolved_strategy(FIXED_INVENTORY_KEYS))
    @settings(max_examples=100)
    def test_unresolved_lookup_sets_is_enriched_false(self, alert: NormalizedAlert) -> None:
        """For any alert with a non-matching lookup key, is_enriched SHALL be False.

        **Validates: Requirements 3.3**
        """
        inventory = AssetInventory()
        inventory.set_assets(FIXED_INVENTORY_ASSETS)
        enricher = Enricher(inventory)

        result = enricher.enrich(alert)

        assert isinstance(result, EnrichedAlert)
        assert result.is_enriched is False

    @given(alert=_normalized_alert_unresolved_strategy(FIXED_INVENTORY_KEYS))
    @settings(max_examples=100)
    def test_unresolved_lookup_sets_asset_none(self, alert: NormalizedAlert) -> None:
        """For any alert with a non-matching lookup key, asset SHALL be None.

        **Validates: Requirements 3.3**
        """
        inventory = AssetInventory()
        inventory.set_assets(FIXED_INVENTORY_ASSETS)
        enricher = Enricher(inventory)

        result = enricher.enrich(alert)

        assert isinstance(result, EnrichedAlert)
        assert result.asset is None

    @given(alert=_normalized_alert_unresolved_strategy(FIXED_INVENTORY_KEYS))
    @settings(max_examples=100)
    def test_unresolved_lookup_preserves_alert_fields(self, alert: NormalizedAlert) -> None:
        """For any alert with a non-matching lookup key, all original alert fields
        SHALL be preserved in the EnrichedAlert.

        **Validates: Requirements 3.3**
        """
        inventory = AssetInventory()
        inventory.set_assets(FIXED_INVENTORY_ASSETS)
        enricher = Enricher(inventory)

        result = enricher.enrich(alert)

        assert result.incident_id == alert.incident_id
        assert result.alert_name == alert.alert_name
        assert result.severity == alert.severity
        assert result.status == alert.status
        assert result.labels == alert.labels
        assert result.annotations == alert.annotations
        assert result.starts_at == alert.starts_at
        assert result.ends_at == alert.ends_at


# --- Property 8: Asset metadata attachment completeness ---

# All expected fields in an AssetInfo record
ASSET_INFO_FIELDS = ["hostname", "ip_address", "location", "service_name", "service_owner"]

# Strategy for generating asset data dictionaries with some fields potentially missing
# This simulates real-world asset records where some fields may be absent
_asset_data_with_optional_fields = st.fixed_dictionaries(
    {},
    optional={
        "hostname": st.text(min_size=0, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".-_")),
        "ip_address": st.text(min_size=0, max_size=45, alphabet=st.characters(whitelist_categories=("N",), whitelist_characters=".:")),
        "location": st.text(min_size=0, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_")),
        "service_name": st.text(min_size=0, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_")),
        "service_owner": st.text(min_size=0, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_@")),
    },
)

# Strategy for choosing which lookup label to use
_lookup_label_for_p8 = st.sampled_from(LOOKUP_LABEL_PRIORITY)

# Strategy for generating a non-empty lookup key
_lookup_key_for_p8 = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".-_:"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")


class TestAssetMetadataAttachmentCompleteness:
    """Property tests for asset metadata attachment completeness (Property 8).

    For any normalized alert where the lookup key resolves to an asset in the
    inventory, the EnrichedAlert SHALL contain all available fields from the asset
    record, with any missing fields set to a null marker, and is_enriched SHALL be True.

    **Validates: Requirements 3.2**
    """

    @given(data=st.data())
    @settings(max_examples=100)
    def test_enriched_alert_contains_all_available_fields_with_missing_as_null_marker(
        self, data
    ) -> None:
        """For any normalized alert where the lookup key resolves to an asset,
        the EnrichedAlert SHALL contain all available fields from the asset record,
        with any missing fields set to a null marker (empty string), and
        is_enriched SHALL be True.

        **Validates: Requirements 3.2**
        """
        # Generate a lookup label and key
        lookup_label = data.draw(_lookup_label_for_p8)
        lookup_key = data.draw(_lookup_key_for_p8)

        # Generate asset data (with some fields potentially missing)
        asset_data = data.draw(_asset_data_with_optional_fields)

        # Create a NormalizedAlert with the lookup label set
        alert = NormalizedAlert(
            incident_id="test-incident-p8",
            alert_name="TestAlert",
            severity=Severity.P1,
            status=AlertStatus.FIRING,
            labels={lookup_label: lookup_key},
            annotations={},
            starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ends_at=None,
        )

        # Set up the asset inventory with the generated asset data
        inventory = AssetInventory()
        inventory.set_assets({lookup_key: asset_data})

        # Enrich the alert
        enricher = Enricher(inventory)
        enriched = enricher.enrich(alert)

        # Assert is_enriched is True
        assert enriched.is_enriched is True, (
            f"Expected is_enriched=True when asset is found for key '{lookup_key}', "
            f"but got is_enriched={enriched.is_enriched}"
        )

        # Assert asset is not None
        assert enriched.asset is not None, (
            f"Expected asset to be attached when key '{lookup_key}' resolves in inventory"
        )

        # Verify all fields: available fields match, missing fields are null marker
        for field_name in ASSET_INFO_FIELDS:
            actual_value = getattr(enriched.asset, field_name)
            if field_name in asset_data:
                # Field was present in asset record - should match
                expected_value = str(asset_data[field_name]) if asset_data[field_name] is not None else ""
                assert actual_value == expected_value, (
                    f"Field '{field_name}' mismatch: expected '{expected_value}', "
                    f"got '{actual_value}'"
                )
            else:
                # Field was missing from asset record - should be null marker (empty string)
                assert actual_value == "", (
                    f"Missing field '{field_name}' should be set to null marker (empty string), "
                    f"but got '{actual_value}'"
                )

    @given(data=st.data())
    @settings(max_examples=100)
    def test_complete_asset_record_all_fields_attached(self, data) -> None:
        """For any normalized alert where the asset record has ALL fields populated,
        the EnrichedAlert SHALL contain all fields with their exact values and
        is_enriched SHALL be True.

        **Validates: Requirements 3.2**
        """
        # Generate a lookup label and key
        lookup_label = data.draw(_lookup_label_for_p8)
        lookup_key = data.draw(_lookup_key_for_p8)

        # Generate a complete asset record (all fields present and non-empty)
        hostname = data.draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".-_")))
        ip_address = data.draw(st.text(min_size=1, max_size=45, alphabet=st.characters(whitelist_categories=("N",), whitelist_characters=".:")))
        location = data.draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_")))
        service_name = data.draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_")))
        service_owner = data.draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_@")))

        asset_data = {
            "hostname": hostname,
            "ip_address": ip_address,
            "location": location,
            "service_name": service_name,
            "service_owner": service_owner,
        }

        # Create a NormalizedAlert with the lookup label set
        alert = NormalizedAlert(
            incident_id="test-incident-p8-complete",
            alert_name="TestAlert",
            severity=data.draw(st.sampled_from(list(Severity))),
            status=data.draw(st.sampled_from(list(AlertStatus))),
            labels={lookup_label: lookup_key},
            annotations={},
            starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ends_at=None,
        )

        # Set up the asset inventory
        inventory = AssetInventory()
        inventory.set_assets({lookup_key: asset_data})

        # Enrich the alert
        enricher = Enricher(inventory)
        enriched = enricher.enrich(alert)

        # Assert is_enriched is True
        assert enriched.is_enriched is True

        # Assert asset is not None
        assert enriched.asset is not None

        # Verify all fields match exactly
        assert enriched.asset.hostname == hostname
        assert enriched.asset.ip_address == ip_address
        assert enriched.asset.location == location
        assert enriched.asset.service_name == service_name
        assert enriched.asset.service_owner == service_owner
