# Feature: self-healing-infrastructure, Property 10: Playbook rule matching correctness
# Feature: self-healing-infrastructure, Property 11: Tie-breaking selects earliest rule
# Feature: self-healing-infrastructure, Property 12: Unmatched alerts produce no playbook match
# Feature: self-healing-infrastructure, Property 13: Malformed configuration preserves previous state
# Feature: self-healing-infrastructure, Property 14: Non-existent playbook path treated as unmatched
"""Property-based tests for the Playbook Mapper component.

Property 10: Playbook rule matching correctness
*For any* enriched alert and set of mapping rules, the Playbook Mapper SHALL
return the rule whose conditions are all satisfied by the alert's attributes,
selecting the rule with the most matching attributes (best-fit).

Property 11: Tie-breaking selects earliest rule
*For any* enriched alert that matches multiple rules with an equal number of
matching attributes, the Playbook Mapper SHALL select the rule that appears
earliest in the configuration file.

Property 12: Unmatched alerts produce no playbook match
*For any* enriched alert whose attributes do not satisfy all conditions of any
mapping rule, the Playbook Mapper SHALL return None (no match).

Property 13: Malformed configuration preserves previous state
*For any* malformed YAML configuration input, the Playbook Mapper SHALL retain
the previously loaded valid rule set and continue operating with those rules.

Property 14: Non-existent playbook path treated as unmatched
*For any* matched rule whose playbook_path does not exist on the filesystem,
the Playbook Mapper SHALL treat the alert as unmatched.

**Validates: Requirements 4.2, 4.3, 4.4, 4.6, 4.7**
"""

import os
import tempfile
from datetime import datetime, timezone

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from src.models import AssetInfo, EnrichedAlert, Severity, AlertStatus
from src.playbook_mapper import PlaybookMapper


# --- Hypothesis Strategies ---

# Strategy for generating valid alert names
alert_name_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
)

# Strategy for generating severity values
severity_strategy = st.sampled_from([Severity.P1, Severity.P2, Severity.P3])

# Strategy for generating alert status values
status_strategy = st.sampled_from([AlertStatus.FIRING, AlertStatus.RESOLVED])

# Strategy for generating labels dictionaries
labels_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        min_size=1,
        max_size=20,
    ),
    values=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-.:/"),
    ),
    min_size=0,
    max_size=5,
)

# Strategy for generating non-existent playbook paths
# These paths are guaranteed to not exist on the filesystem
nonexistent_path_strategy = st.text(
    min_size=5,
    max_size=80,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-/"),
).map(lambda p: f"/nonexistent_dir_xyz/{p}/playbook.yml")

# Strategy for generating service names
service_name_strategy = st.text(
    min_size=1,
    max_size=30,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
)


def enriched_alert_strategy(alert_name=None, severity=None, status=None, labels=None):
    """Generate EnrichedAlert instances with optional fixed attributes for matching."""
    return st.builds(
        EnrichedAlert,
        incident_id=st.uuids().map(str),
        alert_name=alert_name if alert_name is not None else alert_name_strategy,
        severity=severity if severity is not None else severity_strategy,
        status=status if status is not None else status_strategy,
        labels=labels if labels is not None else labels_strategy,
        annotations=st.just({}),
        starts_at=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        ends_at=st.none(),
        asset=st.one_of(
            st.none(),
            st.builds(
                AssetInfo,
                hostname=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-")),
                ip_address=st.just("10.0.0.1"),
                location=st.just("us-east-1a"),
                service_name=service_name_strategy,
                service_owner=st.just("team-a"),
            ),
        ),
        is_enriched=st.booleans(),
    )


# --- Property 10: Playbook rule matching correctness ---


class TestPlaybookRuleMatchingCorrectness:
    """Property tests for playbook rule matching correctness (Property 10).

    **Validates: Requirements 4.2**

    For any enriched alert and set of mapping rules, the Playbook Mapper SHALL
    return the rule whose conditions are all satisfied by the alert's attributes,
    selecting the rule with the most matching attributes (best-fit).
    """

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        status=status_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_best_fit_rule_selected_over_less_specific(
        self,
        alert_name: str,
        severity: Severity,
        status: AlertStatus,
    ) -> None:
        """The rule with the most matching attributes (best-fit) SHALL be selected
        over rules with fewer matching attributes.

        **Validates: Requirements 4.2**

        Strategy: Create rules with varying specificity (1, 2, and 3 conditions).
        The alert satisfies all conditions of all rules. The rule with 3 conditions
        (most specific) should be selected as the best-fit.
        """
        playbook_files = []
        try:
            for i in range(3):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write(f"---\n- hosts: all\n  tasks: []\n  # rule {i}\n")
                pf.close()
                playbook_files.append(pf.name)

            # Rule with 1 condition (least specific)
            # Rule with 2 conditions (medium specificity)
            # Rule with 3 conditions (most specific - best fit)
            rules_config = [
                {
                    "name": "rule-1-condition",
                    "conditions": {
                        "alert_name": alert_name,
                    },
                    "playbook_path": playbook_files[0],
                },
                {
                    "name": "rule-2-conditions",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                    },
                    "playbook_path": playbook_files[1],
                },
                {
                    "name": "rule-3-conditions",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                        "status": status.value,
                    },
                    "playbook_path": playbook_files[2],
                },
            ]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                alert = EnrichedAlert(
                    incident_id="test-best-fit-001",
                    alert_name=alert_name,
                    severity=severity,
                    status=status,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match since all rules match the alert"
                )
                # The most specific rule (3 conditions) should win
                assert result.rule_name == "rule-3-conditions", (
                    f"Expected best-fit rule 'rule-3-conditions' (3 conditions), "
                    f"but got '{result.rule_name}'"
                )
                assert result.matched_attributes == 3, (
                    f"Expected 3 matched attributes, got {result.matched_attributes}"
                )
                assert result.playbook_path == playbook_files[2]
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        status=status_strategy,
        service_name=service_name_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_best_fit_with_enrichment_attributes(
        self,
        alert_name: str,
        severity: Severity,
        status: AlertStatus,
        service_name: str,
    ) -> None:
        """Best-fit selection works correctly when rules match on enrichment
        attributes (service_name from asset info).

        **Validates: Requirements 4.2**

        Strategy: Create rules where the most specific rule includes a
        service_name condition from the enriched asset. The alert has asset
        info attached, so the most specific rule should win.
        """
        playbook_files = []
        try:
            for i in range(3):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write("---\n- hosts: all\n  tasks: []\n")
                pf.close()
                playbook_files.append(pf.name)

            rules_config = [
                {
                    "name": "rule-alert-only",
                    "conditions": {
                        "alert_name": alert_name,
                    },
                    "playbook_path": playbook_files[0],
                },
                {
                    "name": "rule-alert-severity",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                    },
                    "playbook_path": playbook_files[1],
                },
                {
                    "name": "rule-alert-severity-service",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                        "service_name": service_name,
                    },
                    "playbook_path": playbook_files[2],
                },
            ]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                # Create an enriched alert with asset info
                alert = EnrichedAlert(
                    incident_id="test-best-fit-enriched-001",
                    alert_name=alert_name,
                    severity=severity,
                    status=status,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=AssetInfo(
                        hostname="web-server-01",
                        ip_address="10.0.0.1",
                        location="us-east-1a",
                        service_name=service_name,
                        service_owner="team-a",
                    ),
                    is_enriched=True,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match since all rules match the enriched alert"
                )
                # The most specific rule (3 conditions including service_name) should win
                assert result.rule_name == "rule-alert-severity-service", (
                    f"Expected best-fit rule 'rule-alert-severity-service' (3 conditions), "
                    f"but got '{result.rule_name}'"
                )
                assert result.matched_attributes == 3, (
                    f"Expected 3 matched attributes, got {result.matched_attributes}"
                )
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        label_key=st.text(
            min_size=3,
            max_size=15,
            alphabet=st.characters(whitelist_categories=("L",), whitelist_characters="_"),
        ),
        label_value=st.text(
            min_size=1,
            max_size=15,
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        ),
    )
    @settings(max_examples=100, deadline=5000)
    def test_best_fit_with_label_conditions(
        self,
        alert_name: str,
        severity: Severity,
        label_key: str,
        label_value: str,
    ) -> None:
        """Best-fit selection works correctly when rules match on alert labels.

        **Validates: Requirements 4.2**

        Strategy: Create rules where the most specific rule includes a label
        condition. The alert has that label, so the most specific rule should win.
        """
        from hypothesis import assume

        # Ensure the label key doesn't collide with core attribute names
        assume(label_key not in ("alert_name", "severity", "status",
                                  "service_name", "service_owner",
                                  "hostname", "location"))

        playbook_files = []
        try:
            for i in range(2):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write("---\n- hosts: all\n  tasks: []\n")
                pf.close()
                playbook_files.append(pf.name)

            rules_config = [
                {
                    "name": "rule-basic",
                    "conditions": {
                        "alert_name": alert_name,
                    },
                    "playbook_path": playbook_files[0],
                },
                {
                    "name": "rule-with-label",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                        label_key: label_value,
                    },
                    "playbook_path": playbook_files[1],
                },
            ]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                alert = EnrichedAlert(
                    incident_id="test-best-fit-labels-001",
                    alert_name=alert_name,
                    severity=severity,
                    status=AlertStatus.FIRING,
                    labels={label_key: label_value},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match since both rules match the alert"
                )
                # The rule with 3 conditions (including label) should win
                assert result.rule_name == "rule-with-label", (
                    f"Expected best-fit rule 'rule-with-label' (3 conditions), "
                    f"but got '{result.rule_name}'"
                )
                assert result.matched_attributes == 3, (
                    f"Expected 3 matched attributes, got {result.matched_attributes}"
                )
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        status=status_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_only_fully_matching_rules_considered(
        self,
        alert_name: str,
        severity: Severity,
        status: AlertStatus,
    ) -> None:
        """Only rules whose ALL conditions are satisfied are considered for
        best-fit selection. A rule with more conditions but partial match
        SHALL NOT be selected over a fully matching rule with fewer conditions.

        **Validates: Requirements 4.2**

        Strategy: Create a rule with 4 conditions (one impossible) and a rule
        with 2 conditions (all matching). The 2-condition rule should win because
        the 4-condition rule doesn't fully match.
        """
        playbook_files = []
        try:
            for i in range(2):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write("---\n- hosts: all\n  tasks: []\n")
                pf.close()
                playbook_files.append(pf.name)

            rules_config = [
                {
                    "name": "rule-partial-match-more-conditions",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                        "status": status.value,
                        "service_name": "IMPOSSIBLE_SERVICE_ZZZZZ",
                    },
                    "playbook_path": playbook_files[0],
                },
                {
                    "name": "rule-full-match-fewer-conditions",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                    },
                    "playbook_path": playbook_files[1],
                },
            ]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                alert = EnrichedAlert(
                    incident_id="test-partial-match-001",
                    alert_name=alert_name,
                    severity=severity,
                    status=status,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match from the fully matching rule"
                )
                # The fully matching rule with 2 conditions should win
                # (the 4-condition rule doesn't fully match)
                assert result.rule_name == "rule-full-match-fewer-conditions", (
                    f"Expected 'rule-full-match-fewer-conditions' (fully matching), "
                    f"but got '{result.rule_name}'"
                )
                assert result.matched_attributes == 2, (
                    f"Expected 2 matched attributes, got {result.matched_attributes}"
                )
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        status=status_strategy,
        num_rules=st.integers(min_value=2, max_value=8),
    )
    @settings(max_examples=100, deadline=5000)
    def test_best_fit_among_multiple_fully_matching_rules(
        self,
        alert_name: str,
        severity: Severity,
        status: AlertStatus,
        num_rules: int,
    ) -> None:
        """Among multiple fully matching rules with different specificity levels,
        the one with the most conditions SHALL be selected.

        **Validates: Requirements 4.2**

        Strategy: Generate N rules with increasing specificity (1 to N conditions).
        All conditions are satisfied by the alert. The rule with N conditions
        (most specific) should be selected.
        """
        # Build conditions incrementally
        all_conditions = [
            ("alert_name", alert_name),
            ("severity", severity.value),
            ("status", status.value),
        ]
        # Limit num_rules to available conditions
        actual_num_rules = min(num_rules, len(all_conditions))

        playbook_files = []
        try:
            for i in range(actual_num_rules):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write("---\n- hosts: all\n  tasks: []\n")
                pf.close()
                playbook_files.append(pf.name)

            rules_config = []
            for i in range(actual_num_rules):
                # Rule i has (i+1) conditions
                conditions = dict(all_conditions[: i + 1])
                rules_config.append({
                    "name": f"rule-{i + 1}-conditions",
                    "conditions": conditions,
                    "playbook_path": playbook_files[i],
                })

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                alert = EnrichedAlert(
                    incident_id="test-multi-fit-001",
                    alert_name=alert_name,
                    severity=severity,
                    status=status,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match since all rules match the alert"
                )
                # The most specific rule should win
                expected_name = f"rule-{actual_num_rules}-conditions"
                assert result.rule_name == expected_name, (
                    f"Expected most specific rule '{expected_name}', "
                    f"but got '{result.rule_name}'"
                )
                assert result.matched_attributes == actual_num_rules, (
                    f"Expected {actual_num_rules} matched attributes, "
                    f"got {result.matched_attributes}"
                )
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        status=status_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_best_fit_independent_of_rule_order_in_config(
        self,
        alert_name: str,
        severity: Severity,
        status: AlertStatus,
    ) -> None:
        """Best-fit selection is based on number of matching attributes, not
        position in config. A more specific rule later in config SHALL be
        selected over a less specific rule earlier in config.

        **Validates: Requirements 4.2**

        Strategy: Place the most specific rule LAST in the config. It should
        still be selected because it has more matching attributes.
        """
        playbook_files = []
        try:
            for i in range(3):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write("---\n- hosts: all\n  tasks: []\n")
                pf.close()
                playbook_files.append(pf.name)

            # Place rules in REVERSE specificity order (least specific first)
            rules_config = [
                {
                    "name": "rule-least-specific",
                    "conditions": {
                        "alert_name": alert_name,
                    },
                    "playbook_path": playbook_files[0],
                },
                {
                    "name": "rule-medium-specific",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                    },
                    "playbook_path": playbook_files[1],
                },
                {
                    "name": "rule-most-specific",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                        "status": status.value,
                    },
                    "playbook_path": playbook_files[2],
                },
            ]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                alert = EnrichedAlert(
                    incident_id="test-order-independent-001",
                    alert_name=alert_name,
                    severity=severity,
                    status=status,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match since all rules match the alert"
                )
                # The most specific rule (last in config) should still win
                assert result.rule_name == "rule-most-specific", (
                    f"Expected 'rule-most-specific' (3 conditions, last in config), "
                    f"but got '{result.rule_name}'"
                )
                assert result.matched_attributes == 3
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_single_matching_rule_is_selected(
        self,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """When exactly one rule fully matches the alert, that rule SHALL be
        selected regardless of how many conditions it has.

        **Validates: Requirements 4.2**

        Strategy: Create one matching rule and one non-matching rule. The
        matching rule should be selected.
        """
        playbook_files = []
        try:
            for i in range(2):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write("---\n- hosts: all\n  tasks: []\n")
                pf.close()
                playbook_files.append(pf.name)

            rules_config = [
                {
                    "name": "non-matching-rule",
                    "conditions": {
                        "alert_name": "IMPOSSIBLE_ALERT_NAME_ZZZZZ",
                        "severity": severity.value,
                        "status": "firing",
                    },
                    "playbook_path": playbook_files[0],
                },
                {
                    "name": "matching-rule",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                    },
                    "playbook_path": playbook_files[1],
                },
            ]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                alert = EnrichedAlert(
                    incident_id="test-single-match-001",
                    alert_name=alert_name,
                    severity=severity,
                    status=AlertStatus.FIRING,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match from the matching rule"
                )
                assert result.rule_name == "matching-rule", (
                    f"Expected 'matching-rule', but got '{result.rule_name}'"
                )
                assert result.matched_attributes == 2
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)


# --- Property 11: Tie-breaking selects earliest rule ---


class TestTieBreakingSelectsEarliestRule:
    """Property tests for tie-breaking behavior (Property 11).

    **Validates: Requirements 4.3**

    For any enriched alert that matches multiple rules with an equal number of
    matching attributes, the Playbook Mapper SHALL select the rule that appears
    earliest in the configuration file.
    """

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        num_tied_rules=st.integers(min_value=2, max_value=6),
    )
    @settings(max_examples=100, deadline=5000)
    def test_tie_breaking_selects_earliest_rule(
        self,
        alert_name: str,
        severity: Severity,
        num_tied_rules: int,
    ) -> None:
        """For any enriched alert matching multiple rules with equal matching
        attributes, the Playbook Mapper SHALL select the earliest rule in config.

        **Validates: Requirements 4.3**

        Strategy: Generate N rules that all match the same alert with the same
        number of conditions (tied on matched_attributes). Each rule has a
        distinct playbook path pointing to a real file. Verify the mapper
        always selects the first rule (index 0).
        """
        # Create temporary playbook files for each rule
        playbook_files = []
        try:
            for i in range(num_tied_rules):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write(f"---\n- hosts: all\n  tasks: []\n  # rule {i}\n")
                pf.close()
                playbook_files.append(pf.name)

            # All rules have the same number of conditions (2: alert_name + severity)
            # but different names and playbook paths
            rules_config = []
            for i in range(num_tied_rules):
                rules_config.append({
                    "name": f"tied-rule-{i}",
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                    },
                    "playbook_path": playbook_files[i],
                })

            # Write the config to a temporary YAML file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                # Create an alert that matches all rules equally
                alert = EnrichedAlert(
                    incident_id="test-tie-break-001",
                    alert_name=alert_name,
                    severity=severity,
                    status=AlertStatus.FIRING,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match since all rules match the alert"
                )
                # The earliest rule (index 0) should win the tie-break
                assert result.rule_name == "tied-rule-0", (
                    f"Expected earliest rule 'tied-rule-0' to win tie-break, "
                    f"but got '{result.rule_name}'"
                )
                assert result.playbook_path == playbook_files[0], (
                    f"Expected playbook path of earliest rule, "
                    f"but got '{result.playbook_path}'"
                )
                assert result.matched_attributes == 2, (
                    f"Expected 2 matched attributes, got {result.matched_attributes}"
                )
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        status=status_strategy,
        permutation_seed=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=100, deadline=5000)
    def test_tie_breaking_independent_of_rule_name(
        self,
        alert_name: str,
        severity: Severity,
        status: AlertStatus,
        permutation_seed: int,
    ) -> None:
        """Tie-breaking is determined by position in config, not by rule name.

        **Validates: Requirements 4.3**

        Strategy: Create rules with names that would sort differently
        alphabetically vs. their position in the config. Verify position wins.
        """
        # Create rule names that sort in reverse alphabetical order
        # but the first one in config should still win
        rule_names = [f"z_rule_{i}" if i == 0 else f"a_rule_{i}" for i in range(3)]

        playbook_files = []
        try:
            for i in range(3):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write(f"---\n- hosts: all\n  tasks: []\n  # rule {i}\n")
                pf.close()
                playbook_files.append(pf.name)

            # All rules match on the same 3 conditions
            rules_config = []
            for i in range(3):
                rules_config.append({
                    "name": rule_names[i],
                    "conditions": {
                        "alert_name": alert_name,
                        "severity": severity.value,
                        "status": status.value,
                    },
                    "playbook_path": playbook_files[i],
                })

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                alert = EnrichedAlert(
                    incident_id="test-tie-break-002",
                    alert_name=alert_name,
                    severity=severity,
                    status=status,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match since all rules match the alert"
                )
                # First rule in config wins regardless of alphabetical name order
                assert result.rule_name == rule_names[0], (
                    f"Expected first rule '{rule_names[0]}' to win tie-break, "
                    f"but got '{result.rule_name}'"
                )
                assert result.playbook_path == playbook_files[0]
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        extra_label_key=st.text(
            min_size=3,
            max_size=15,
            alphabet=st.characters(whitelist_categories=("L",), whitelist_characters="_"),
        ),
        extra_label_value=st.text(
            min_size=1,
            max_size=15,
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        ),
    )
    @settings(max_examples=100, deadline=5000)
    def test_tie_breaking_with_label_conditions(
        self,
        alert_name: str,
        severity: Severity,
        extra_label_key: str,
        extra_label_value: str,
    ) -> None:
        """Tie-breaking works correctly when rules match on label conditions.

        **Validates: Requirements 4.3**

        Strategy: Create multiple rules that all match on the same set of
        conditions including a label key. Verify earliest rule wins.
        """
        from hypothesis import assume

        # Ensure the label key doesn't collide with core attribute names
        assume(extra_label_key not in ("alert_name", "severity", "status",
                                        "service_name", "service_owner",
                                        "hostname", "location"))

        playbook_files = []
        try:
            for i in range(3):
                pf = tempfile.NamedTemporaryFile(
                    mode="w", suffix=f"_rule{i}.yml", delete=False
                )
                pf.write("---\n- hosts: all\n  tasks: []\n")
                pf.close()
                playbook_files.append(pf.name)

            # All rules match on alert_name + the extra label (2 conditions each)
            rules_config = []
            for i in range(3):
                rules_config.append({
                    "name": f"label-tie-rule-{i}",
                    "conditions": {
                        "alert_name": alert_name,
                        extra_label_key: extra_label_value,
                    },
                    "playbook_path": playbook_files[i],
                })

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False
            ) as config_file:
                yaml.dump({"rules": rules_config}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                alert = EnrichedAlert(
                    incident_id="test-tie-break-003",
                    alert_name=alert_name,
                    severity=severity,
                    status=AlertStatus.FIRING,
                    labels={extra_label_key: extra_label_value},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result = mapper.match(alert)
                assert result is not None, (
                    "Expected a match since all rules match the alert"
                )
                # Earliest rule in config wins
                assert result.rule_name == "label-tie-rule-0", (
                    f"Expected 'label-tie-rule-0' to win tie-break, "
                    f"but got '{result.rule_name}'"
                )
                assert result.playbook_path == playbook_files[0]
                assert result.matched_attributes == 2
            finally:
                os.unlink(config_path)
        finally:
            for pf in playbook_files:
                if os.path.exists(pf):
                    os.unlink(pf)


# --- Property 14: Non-existent playbook path treated as unmatched ---


class TestNonExistentPlaybookPath:
    """Property tests for non-existent playbook path handling (Property 14).

    **Validates: Requirements 4.7**

    For any matched rule whose playbook_path does not exist on the filesystem,
    the Playbook Mapper SHALL treat the alert as unmatched (return None).
    """

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        nonexistent_path=nonexistent_path_strategy,
    )
    @settings(max_examples=100)
    def test_nonexistent_playbook_path_returns_none(
        self,
        alert_name: str,
        severity: Severity,
        nonexistent_path: str,
    ) -> None:
        """For any matched rule with a non-existent playbook_path, match() SHALL return None.

        **Validates: Requirements 4.7**

        This test creates a mapping rule that matches the alert (by alert_name and severity),
        but whose playbook_path points to a file that does not exist on the filesystem.
        The Playbook Mapper must treat this as unmatched and return None.
        """
        # Ensure the path truly does not exist
        assert not os.path.isfile(nonexistent_path), (
            f"Path unexpectedly exists: {nonexistent_path}"
        )

        # Create a mapping config with a rule that will match the alert
        rules_config = [
            {
                "name": "test-rule-nonexistent-path",
                "conditions": {
                    "alert_name": alert_name,
                    "severity": severity.value,
                },
                "playbook_path": nonexistent_path,
            }
        ]

        # Write the config to a temporary YAML file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as config_file:
            yaml.dump({"rules": rules_config}, config_file)
            config_path = config_file.name

        try:
            mapper = PlaybookMapper(config_path)

            # Create an enriched alert that matches the rule conditions
            alert = EnrichedAlert(
                incident_id="test-incident-001",
                alert_name=alert_name,
                severity=severity,
                status=AlertStatus.FIRING,
                labels={},
                annotations={},
                starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                ends_at=None,
                asset=None,
                is_enriched=False,
            )

            # The rule conditions match, but playbook_path doesn't exist
            # So the mapper should return None (treat as unmatched)
            result = mapper.match(alert)
            assert result is None, (
                f"Expected None for non-existent playbook path '{nonexistent_path}', "
                f"but got: {result}"
            )
        finally:
            os.unlink(config_path)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        nonexistent_path=nonexistent_path_strategy,
    )
    @settings(max_examples=100)
    def test_nonexistent_path_among_multiple_rules_still_unmatched(
        self,
        alert_name: str,
        severity: Severity,
        nonexistent_path: str,
    ) -> None:
        """When the best-fit rule has a non-existent playbook, the alert is unmatched.

        **Validates: Requirements 4.7**

        Even when there are multiple rules and the best-fit (most matching attributes)
        rule has a non-existent playbook path, the mapper SHALL return None.
        """
        assert not os.path.isfile(nonexistent_path)

        # Create multiple rules - the best-fit one has a non-existent path
        rules_config = [
            {
                "name": "less-specific-rule",
                "conditions": {
                    "alert_name": alert_name,
                },
                "playbook_path": nonexistent_path,
            },
            {
                "name": "best-fit-rule-nonexistent",
                "conditions": {
                    "alert_name": alert_name,
                    "severity": severity.value,
                },
                "playbook_path": nonexistent_path,
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as config_file:
            yaml.dump({"rules": rules_config}, config_file)
            config_path = config_file.name

        try:
            mapper = PlaybookMapper(config_path)

            alert = EnrichedAlert(
                incident_id="test-incident-002",
                alert_name=alert_name,
                severity=severity,
                status=AlertStatus.FIRING,
                labels={},
                annotations={},
                starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                ends_at=None,
                asset=None,
                is_enriched=False,
            )

            # Both rules match but both have non-existent paths
            result = mapper.match(alert)
            assert result is None, (
                f"Expected None when best-fit rule has non-existent playbook path, "
                f"but got: {result}"
            )
        finally:
            os.unlink(config_path)

    @given(
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100)
    def test_existing_playbook_path_returns_match(
        self,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """Contrast: when playbook_path exists, the mapper SHALL return a valid match.

        **Validates: Requirements 4.7**

        This is the positive counterpart: if the playbook file exists on disk,
        the mapper should return a PlaybookMatch (not None).
        """
        # Create a temporary file to act as an existing playbook
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as playbook_file:
            playbook_file.write("---\n- hosts: all\n  tasks: []\n")
            existing_playbook_path = playbook_file.name

        # Create a mapping config with a rule pointing to the existing playbook
        rules_config = [
            {
                "name": "test-rule-existing-path",
                "conditions": {
                    "alert_name": alert_name,
                    "severity": severity.value,
                },
                "playbook_path": existing_playbook_path,
            }
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as config_file:
            yaml.dump({"rules": rules_config}, config_file)
            config_path = config_file.name

        try:
            mapper = PlaybookMapper(config_path)

            alert = EnrichedAlert(
                incident_id="test-incident-003",
                alert_name=alert_name,
                severity=severity,
                status=AlertStatus.FIRING,
                labels={},
                annotations={},
                starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                ends_at=None,
                asset=None,
                is_enriched=False,
            )

            # The rule matches and the playbook exists, so we should get a match
            result = mapper.match(alert)
            assert result is not None, (
                "Expected a PlaybookMatch for existing playbook path, but got None"
            )
            assert result.playbook_path == existing_playbook_path
            assert result.rule_name == "test-rule-existing-path"
            assert result.matched_attributes == 2  # alert_name + severity
        finally:
            os.unlink(config_path)
            os.unlink(existing_playbook_path)



# --- Property 12: Unmatched alerts produce no playbook match ---


def _extract_alert_attributes(alert: EnrichedAlert) -> dict[str, str]:
    """Extract the flat attribute dictionary from an alert (mirrors PlaybookMapper logic)."""
    attrs: dict[str, str] = {}
    attrs["alert_name"] = alert.alert_name
    attrs["severity"] = alert.severity.value
    attrs["status"] = alert.status.value

    for key, value in alert.labels.items():
        attrs[key] = value

    if alert.asset is not None:
        attrs["service_name"] = alert.asset.service_name
        attrs["service_owner"] = alert.asset.service_owner
        attrs["hostname"] = alert.asset.hostname
        attrs["location"] = alert.asset.location

    return attrs


def _rule_matches_alert(rule_conditions: dict[str, str], alert_attrs: dict[str, str]) -> bool:
    """Check if ALL conditions of a rule are satisfied by alert attributes."""
    for attr_name, expected_value in rule_conditions.items():
        actual_value = alert_attrs.get(attr_name)
        if actual_value is None or actual_value != expected_value:
            return False
    return True


# Strategy for generating mapping rule condition keys
_condition_key_strategy = st.sampled_from([
    "alert_name", "severity", "status", "service_name", "service_owner",
    "hostname", "location",
])

# Strategy for generating a single mapping rule for Property 12
_mapping_rule_p12_strategy = st.fixed_dictionaries({
    "name": st.text(
        min_size=3,
        max_size=30,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    ),
    "conditions": st.dictionaries(
        keys=_condition_key_strategy,
        values=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        ),
        min_size=1,
        max_size=3,
    ),
    "playbook_path": st.just("__placeholder__"),
})

# Strategy for generating a list of mapping rules for Property 12
_mapping_rules_list_p12_strategy = st.lists(_mapping_rule_p12_strategy, min_size=1, max_size=5)

# Strategy for generating enriched alerts for Property 12
_enriched_alert_p12_strategy = st.builds(
    EnrichedAlert,
    incident_id=st.uuids().map(str),
    alert_name=alert_name_strategy,
    severity=severity_strategy,
    status=status_strategy,
    labels=labels_strategy,
    annotations=st.just({}),
    starts_at=st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
        timezones=st.just(timezone.utc),
    ),
    ends_at=st.none(),
    asset=st.one_of(
        st.none(),
        st.builds(
            AssetInfo,
            hostname=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-")),
            ip_address=st.just("10.0.0.1"),
            location=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-")),
            service_name=service_name_strategy,
            service_owner=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-")),
        ),
    ),
    is_enriched=st.booleans(),
)


class TestUnmatchedAlertsProduceNoMatch:
    """Property tests for unmatched alerts returning None (Property 12).

    **Validates: Requirements 4.4**

    For any enriched alert whose attributes do not satisfy all conditions of any
    mapping rule, the Playbook Mapper SHALL return None (no match).
    """

    @given(
        rules_data=_mapping_rules_list_p12_strategy,
        alert=_enriched_alert_p12_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_unmatched_alert_returns_none(
        self,
        rules_data: list[dict],
        alert: EnrichedAlert,
    ) -> None:
        """For any enriched alert whose attributes do not satisfy all conditions
        of any mapping rule, the Playbook Mapper SHALL return None (no match).

        **Validates: Requirements 4.4**

        Strategy: Generate random rules and a random alert, then use assume()
        to filter to cases where the alert does NOT match any rule. Verify
        that match() returns None.
        """
        from hypothesis import assume

        # Extract alert attributes to check if any rule matches
        alert_attrs = _extract_alert_attributes(alert)

        # Filter: only proceed if the alert does NOT match any rule
        for rule in rules_data:
            conditions = rule["conditions"]
            if _rule_matches_alert(conditions, alert_attrs):
                assume(False)  # Skip this example - alert matches a rule

        # Create a temporary playbook file (so path validation doesn't interfere)
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False, mode="w") as playbook_file:
            playbook_file.write("---\n- hosts: all\n  tasks: []\n")
            playbook_path = playbook_file.name

        try:
            # Update rules to point to the real playbook path
            for rule in rules_data:
                rule["playbook_path"] = playbook_path

            # Write rules to a temporary YAML config
            with tempfile.NamedTemporaryFile(
                suffix=".yml", delete=False, mode="w", encoding="utf-8"
            ) as config_file:
                yaml.dump({"rules": rules_data}, config_file)
                config_path = config_file.name

            try:
                # Create the PlaybookMapper with the generated rules
                mapper = PlaybookMapper(config_path)

                # The alert should NOT match any rule, so match() must return None
                result = mapper.match(alert)
                assert result is None, (
                    f"Expected None for unmatched alert, but got {result}. "
                    f"Alert attrs: {alert_attrs}, Rules: {rules_data}"
                )
            finally:
                os.unlink(config_path)
        finally:
            os.unlink(playbook_path)

    @given(alert=_enriched_alert_p12_strategy)
    @settings(max_examples=100, deadline=5000)
    def test_empty_rules_always_returns_none(
        self,
        alert: EnrichedAlert,
    ) -> None:
        """For any enriched alert with an empty rule set, the Playbook Mapper
        SHALL return None since no rules can possibly match.

        **Validates: Requirements 4.4**
        """
        # Write an empty rules config
        with tempfile.NamedTemporaryFile(
            suffix=".yml", delete=False, mode="w", encoding="utf-8"
        ) as config_file:
            yaml.dump({"rules": []}, config_file)
            config_path = config_file.name

        try:
            mapper = PlaybookMapper(config_path)
            result = mapper.match(alert)
            assert result is None, (
                f"Expected None for alert with empty rules, but got {result}"
            )
        finally:
            os.unlink(config_path)

    @given(
        rules_data=_mapping_rules_list_p12_strategy,
        alert=_enriched_alert_p12_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_deliberately_mismatched_alert_returns_none(
        self,
        rules_data: list[dict],
        alert: EnrichedAlert,
    ) -> None:
        """For any set of rules, when all rule conditions use impossible values
        that cannot appear in the alert attributes, match() SHALL return None.

        **Validates: Requirements 4.4**

        Strategy: Modify each rule's condition values to guaranteed-impossible
        values, ensuring no rule can match any alert.
        """
        # Create a temporary playbook file
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False, mode="w") as playbook_file:
            playbook_file.write("---\n- hosts: all\n  tasks: []\n")
            playbook_path = playbook_file.name

        try:
            # Modify rules so that each rule has conditions with impossible values
            impossible_prefix = "IMPOSSIBLE_VALUE_ZZZZZ_"
            modified_rules = []
            for i, rule in enumerate(rules_data):
                modified_rule = {
                    "name": rule["name"],
                    "conditions": {},
                    "playbook_path": playbook_path,
                }
                conditions = dict(rule["conditions"])
                # Set ALL condition values to impossible values
                for key in conditions:
                    conditions[key] = f"{impossible_prefix}{i}_{key}"
                modified_rule["conditions"] = conditions
                modified_rules.append(modified_rule)

            # Write rules to a temporary YAML config
            with tempfile.NamedTemporaryFile(
                suffix=".yml", delete=False, mode="w", encoding="utf-8"
            ) as config_file:
                yaml.dump({"rules": modified_rules}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)
                result = mapper.match(alert)
                assert result is None, (
                    f"Expected None for deliberately mismatched alert, but got {result}. "
                    f"Alert: {alert}, Modified rules: {modified_rules}"
                )
            finally:
                os.unlink(config_path)
        finally:
            os.unlink(playbook_path)


# --- Property 13: Malformed configuration preserves previous state ---


# Strategy for generating malformed YAML content that will fail parsing
_malformed_yaml_strategy = st.one_of(
    # Unbalanced braces/brackets
    st.text(min_size=1, max_size=100).map(lambda t: "{" + t),
    st.text(min_size=1, max_size=100).map(lambda t: "[" + t + ": {"),
    # Invalid YAML with tabs in wrong places and broken indentation
    st.text(min_size=1, max_size=50).map(lambda t: f"rules:\n\t- name: {t}\n  \t  bad:\n\t\t- {{broken"),
    # Completely invalid YAML with unmatched quotes and special chars
    st.text(min_size=1, max_size=80).map(lambda t: f'"{t}\n  : [{t}'),
    # Binary-like garbage that cannot be valid YAML
    st.binary(min_size=5, max_size=100).map(lambda b: b.decode("latin-1")),
    # YAML with duplicate keys and broken structure
    st.text(min_size=1, max_size=30).map(lambda t: f"---\n- {t}: *invalid_anchor\n  <<: *missing"),
)

# Strategy for generating valid rule sets to pre-load
_valid_rule_strategy = st.fixed_dictionaries({
    "name": st.text(
        min_size=3,
        max_size=30,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    ),
    "conditions": st.dictionaries(
        keys=st.sampled_from(["alert_name", "severity", "status", "service_name"]),
        values=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        ),
        min_size=1,
        max_size=3,
    ),
    "playbook_path": st.just("__placeholder__"),
})

_valid_rules_list_strategy = st.lists(_valid_rule_strategy, min_size=1, max_size=5)


class TestMalformedConfigPreservesPreviousState:
    """Property tests for malformed configuration handling (Property 13).

    **Validates: Requirements 4.6**

    For any malformed YAML configuration input, the Playbook Mapper SHALL retain
    the previously loaded valid rule set and continue operating with those rules.
    """

    @given(
        valid_rules=_valid_rules_list_strategy,
        malformed_content=_malformed_yaml_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_malformed_yaml_reload_preserves_previous_rules(
        self,
        valid_rules: list[dict],
        malformed_content: str,
    ) -> None:
        """For any malformed YAML configuration input, the Playbook Mapper SHALL
        retain the previously loaded valid rule set and continue operating with
        those rules.

        **Validates: Requirements 4.6**

        Strategy:
        1. Create a valid YAML config and load it into the PlaybookMapper.
        2. Overwrite the config file with malformed YAML content.
        3. Call reload() on the mapper.
        4. Verify that the mapper still has the original valid rules.
        """
        # Create a temporary playbook file for valid rules
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as playbook_file:
            playbook_file.write("---\n- hosts: all\n  tasks: []\n")
            playbook_path = playbook_file.name

        try:
            # Set playbook_path on all valid rules
            for rule in valid_rules:
                rule["playbook_path"] = playbook_path

            # Write valid config to a temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False, encoding="utf-8"
            ) as config_file:
                yaml.dump({"rules": valid_rules}, config_file)
                config_path = config_file.name

            try:
                # Load the mapper with valid configuration
                mapper = PlaybookMapper(config_path)

                # Capture the initial valid rules
                initial_rules = mapper.rules
                initial_rule_count = len(initial_rules)

                # Verify we loaded at least some rules
                assert initial_rule_count > 0, (
                    "Expected at least one valid rule to be loaded initially"
                )

                # Overwrite the config file with malformed YAML
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(malformed_content)

                # Reload the mapper - this should fail to parse and retain previous rules
                mapper.reload()

                # Verify the mapper still has the same rules as before
                after_reload_rules = mapper.rules
                assert len(after_reload_rules) == initial_rule_count, (
                    f"Expected {initial_rule_count} rules after malformed reload, "
                    f"but got {len(after_reload_rules)}. "
                    f"Malformed content: {repr(malformed_content[:100])}"
                )

                # Verify rule names are preserved
                initial_names = [r.name for r in initial_rules]
                after_names = [r.name for r in after_reload_rules]
                assert initial_names == after_names, (
                    f"Rule names changed after malformed reload. "
                    f"Before: {initial_names}, After: {after_names}"
                )

                # Verify rule conditions are preserved
                for orig, reloaded in zip(initial_rules, after_reload_rules):
                    assert orig.conditions == reloaded.conditions, (
                        f"Rule conditions changed for '{orig.name}'. "
                        f"Before: {orig.conditions}, After: {reloaded.conditions}"
                    )
                    assert orig.playbook_path == reloaded.playbook_path, (
                        f"Playbook path changed for '{orig.name}'. "
                        f"Before: {orig.playbook_path}, After: {reloaded.playbook_path}"
                    )

            finally:
                os.unlink(config_path)
        finally:
            os.unlink(playbook_path)

    @given(
        valid_rules=_valid_rules_list_strategy,
        malformed_content=_malformed_yaml_strategy,
        alert_name=alert_name_strategy,
        severity=severity_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_malformed_reload_mapper_continues_operating(
        self,
        valid_rules: list[dict],
        malformed_content: str,
        alert_name: str,
        severity: Severity,
    ) -> None:
        """After a malformed reload, the Playbook Mapper SHALL continue operating
        with the previously loaded rules and still match alerts correctly.

        **Validates: Requirements 4.6**

        Strategy:
        1. Create a valid config with a rule matching a specific alert.
        2. Overwrite with malformed YAML and reload.
        3. Verify the mapper can still match alerts using the original rules.
        """
        # Create a temporary playbook file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as playbook_file:
            playbook_file.write("---\n- hosts: all\n  tasks: []\n")
            playbook_path = playbook_file.name

        try:
            # Create a rule that will match our test alert
            matching_rule = {
                "name": "matching-rule",
                "conditions": {
                    "alert_name": alert_name,
                    "severity": severity.value,
                },
                "playbook_path": playbook_path,
            }

            # Include the matching rule along with any generated valid rules
            all_rules = [matching_rule] + [
                {**r, "playbook_path": playbook_path} for r in valid_rules
            ]

            # Write valid config
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False, encoding="utf-8"
            ) as config_file:
                yaml.dump({"rules": all_rules}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)

                # Verify the mapper can match before the malformed reload
                alert = EnrichedAlert(
                    incident_id="test-incident-p13",
                    alert_name=alert_name,
                    severity=severity,
                    status=AlertStatus.FIRING,
                    labels={},
                    annotations={},
                    starts_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    ends_at=None,
                    asset=None,
                    is_enriched=False,
                )

                result_before = mapper.match(alert)
                assert result_before is not None, (
                    "Expected a match before malformed reload"
                )

                # Overwrite config with malformed YAML
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(malformed_content)

                # Reload with malformed content
                mapper.reload()

                # The mapper should still be able to match the same alert
                result_after = mapper.match(alert)
                assert result_after is not None, (
                    f"Expected mapper to still match after malformed reload, "
                    f"but got None. Malformed content: {repr(malformed_content[:100])}"
                )
                assert result_after.rule_name == result_before.rule_name, (
                    f"Matched rule changed after malformed reload. "
                    f"Before: {result_before.rule_name}, After: {result_after.rule_name}"
                )
                assert result_after.playbook_path == result_before.playbook_path, (
                    f"Playbook path changed after malformed reload. "
                    f"Before: {result_before.playbook_path}, After: {result_after.playbook_path}"
                )

            finally:
                os.unlink(config_path)
        finally:
            os.unlink(playbook_path)

    @given(
        valid_rules=_valid_rules_list_strategy,
        malformed_content=_malformed_yaml_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_multiple_malformed_reloads_preserve_original_state(
        self,
        valid_rules: list[dict],
        malformed_content: str,
    ) -> None:
        """Multiple consecutive malformed reloads SHALL all preserve the original
        valid rule set without degradation.

        **Validates: Requirements 4.6**

        Strategy: Load valid config, then perform multiple malformed reloads
        and verify the rules remain unchanged after each one.
        """
        # Create a temporary playbook file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as playbook_file:
            playbook_file.write("---\n- hosts: all\n  tasks: []\n")
            playbook_path = playbook_file.name

        try:
            for rule in valid_rules:
                rule["playbook_path"] = playbook_path

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False, encoding="utf-8"
            ) as config_file:
                yaml.dump({"rules": valid_rules}, config_file)
                config_path = config_file.name

            try:
                mapper = PlaybookMapper(config_path)
                initial_rules = mapper.rules
                initial_rule_count = len(initial_rules)

                assert initial_rule_count > 0

                # Perform 3 consecutive malformed reloads
                for attempt in range(3):
                    with open(config_path, "w", encoding="utf-8") as f:
                        f.write(malformed_content + f"\n# attempt {attempt}")

                    mapper.reload()

                    current_rules = mapper.rules
                    assert len(current_rules) == initial_rule_count, (
                        f"Rule count changed after malformed reload attempt {attempt + 1}. "
                        f"Expected {initial_rule_count}, got {len(current_rules)}"
                    )

                    # Verify rule integrity
                    for orig, current in zip(initial_rules, current_rules):
                        assert orig.name == current.name
                        assert orig.conditions == current.conditions
                        assert orig.playbook_path == current.playbook_path

            finally:
                os.unlink(config_path)
        finally:
            os.unlink(playbook_path)
