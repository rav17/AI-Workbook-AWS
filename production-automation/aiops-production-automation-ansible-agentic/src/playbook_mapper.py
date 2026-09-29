"""Playbook Mapper component for matching enriched alerts to Ansible remediation playbooks.

Maps alerts to playbooks using configurable YAML rules with best-fit selection
(most matching attributes) and tie-breaking by earliest rule position.
"""

import logging
import os
from typing import Optional

import yaml

from src.models import EnrichedAlert, MappingRule, PlaybookMatch

logger = logging.getLogger(__name__)

MAX_RULES = 500


class PlaybookMapper:
    """Maps enriched alerts to remediation playbooks based on configurable rules.

    Loads mapping rules from a YAML configuration file and evaluates them
    against alert attributes to find the best matching playbook.

    The matching algorithm:
    1. For each rule, check if ALL conditions match the alert attributes.
    2. Among all fully-matching rules, select the one with the most matching attributes (best-fit).
    3. If multiple rules tie on matched attribute count, the earliest rule in config wins.
    4. Before returning a match, validate that the playbook file exists on disk.
    """

    def __init__(self, mapping_config_path: str) -> None:
        """Initialize the PlaybookMapper with a path to the YAML mapping configuration.

        Args:
            mapping_config_path: Path to the YAML file containing mapping rules.
        """
        self._config_path = mapping_config_path
        self._rules: list[MappingRule] = []
        self._load_rules(mapping_config_path)

    def _load_rules(self, config_path: str) -> list[MappingRule]:
        """Load and parse mapping rules from a YAML configuration file.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            List of parsed MappingRule objects.

        Raises:
            No exceptions are raised; on failure, an empty list is returned
            and an error is logged.
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                logger.warning("Mapping configuration file is empty: %s", config_path)
                self._rules = []
                return self._rules

            rules_data = data if isinstance(data, list) else data.get("rules", [])

            if not isinstance(rules_data, list):
                logger.error(
                    "Mapping configuration must contain a list of rules or a 'rules' key with a list: %s",
                    config_path,
                )
                self._rules = []
                return self._rules

            # Enforce max 500 rules limit
            if len(rules_data) > MAX_RULES:
                logger.warning(
                    "Mapping configuration contains %d rules, exceeding maximum of %d. "
                    "Only the first %d rules will be loaded.",
                    len(rules_data),
                    MAX_RULES,
                    MAX_RULES,
                )
                rules_data = rules_data[:MAX_RULES]

            parsed_rules: list[MappingRule] = []
            for idx, rule_dict in enumerate(rules_data):
                try:
                    rule = self._parse_rule(rule_dict, idx)
                    if rule is not None:
                        parsed_rules.append(rule)
                except (TypeError, KeyError, ValueError) as e:
                    logger.warning(
                        "Skipping malformed rule at index %d: %s", idx, str(e)
                    )
                    continue

            self._rules = parsed_rules
            logger.info(
                "Loaded %d mapping rules from %s", len(self._rules), config_path
            )
            return self._rules

        except FileNotFoundError:
            logger.error("Mapping configuration file not found: %s", config_path)
            self._rules = []
            return self._rules
        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML mapping configuration: %s", str(e))
            # If we already have rules loaded, keep them (handled in reload)
            # For initial load, start with empty rules
            self._rules = []
            return self._rules
        except OSError as e:
            logger.error("Error reading mapping configuration file: %s", str(e))
            self._rules = []
            return self._rules

    def _parse_rule(self, rule_dict: dict, index: int) -> Optional[MappingRule]:
        """Parse a single rule dictionary into a MappingRule object.

        Args:
            rule_dict: Dictionary containing rule definition.
            index: Position of the rule in the configuration file.

        Returns:
            A MappingRule object, or None if the rule is invalid.
        """
        if not isinstance(rule_dict, dict):
            raise TypeError(f"Rule must be a dictionary, got {type(rule_dict).__name__}")

        name = rule_dict.get("name")
        if not name:
            raise ValueError("Rule must have a non-empty 'name' field")

        conditions = rule_dict.get("conditions")
        if not isinstance(conditions, dict) or not conditions:
            raise ValueError("Rule must have a non-empty 'conditions' dictionary")

        playbook_path = rule_dict.get("playbook_path")
        if not playbook_path:
            raise ValueError("Rule must have a non-empty 'playbook_path' field")

        # Ensure all condition values are strings
        str_conditions = {str(k): str(v) for k, v in conditions.items()}

        return MappingRule(
            name=str(name),
            conditions=str_conditions,
            playbook_path=str(playbook_path),
            priority=index,
        )

    def match(self, alert: EnrichedAlert) -> Optional[PlaybookMatch]:
        """Evaluate mapping rules against an enriched alert and return the best match.

        The matching algorithm:
        1. For each rule, check if ALL conditions are satisfied by the alert.
        2. Among fully-matching rules, select the one with the most conditions (best-fit).
        3. Ties are broken by rule position (earliest in config wins).
        4. The matched playbook path must exist on the filesystem.

        Args:
            alert: The enriched alert to match against rules.

        Returns:
            A PlaybookMatch if a matching rule is found and its playbook exists,
            or None if no rule matches or the playbook file doesn't exist.
        """
        alert_attrs = self._extract_alert_attributes(alert)

        best_match: Optional[tuple[MappingRule, int]] = None

        for rule in self._rules:
            matched_count = self._evaluate_rule(rule, alert_attrs)
            if matched_count is None:
                # Not all conditions satisfied
                continue

            if best_match is None:
                best_match = (rule, matched_count)
            else:
                _, best_count = best_match
                if matched_count > best_count:
                    best_match = (rule, matched_count)
                elif matched_count == best_count:
                    # Tie-breaking: earliest rule in config wins (lower priority index)
                    if rule.priority < best_match[0].priority:
                        best_match = (rule, matched_count)

        if best_match is None:
            return None

        matched_rule, matched_count = best_match

        # Validate playbook path existence before returning
        if not os.path.isfile(matched_rule.playbook_path):
            logger.warning(
                "Matched playbook path does not exist: %s (rule: %s)",
                matched_rule.playbook_path,
                matched_rule.name,
            )
            return None

        return PlaybookMatch(
            rule_name=matched_rule.name,
            playbook_path=matched_rule.playbook_path,
            matched_attributes=matched_count,
        )

    def _extract_alert_attributes(self, alert: EnrichedAlert) -> dict[str, str]:
        """Extract a flat dictionary of alert attributes for rule matching.

        Attributes available for matching:
        - alert_name: The alert name
        - severity: The severity level (P1, P2, P3)
        - status: The alert status (firing, resolved)
        - service_name: The service name from enrichment (if available)
        - Any label key from the alert's labels dict

        Args:
            alert: The enriched alert to extract attributes from.

        Returns:
            A dictionary of attribute name to value for matching.
        """
        attrs: dict[str, str] = {}

        # Core alert attributes
        attrs["alert_name"] = alert.alert_name
        attrs["severity"] = alert.severity.value
        attrs["status"] = alert.status.value

        # Labels (flattened into the attribute space)
        for key, value in alert.labels.items():
            attrs[key] = value

        # Enrichment attributes (if available)
        if alert.asset is not None:
            attrs["service_name"] = alert.asset.service_name
            attrs["service_owner"] = alert.asset.service_owner
            attrs["hostname"] = alert.asset.hostname
            attrs["location"] = alert.asset.location

        return attrs

    def _evaluate_rule(
        self, rule: MappingRule, alert_attrs: dict[str, str]
    ) -> Optional[int]:
        """Evaluate whether a rule's conditions are all satisfied by alert attributes.

        Args:
            rule: The mapping rule to evaluate.
            alert_attrs: The flattened alert attributes dictionary.

        Returns:
            The number of matched conditions if ALL conditions are satisfied,
            or None if any condition is not satisfied.
        """
        try:
            for attr_name, expected_value in rule.conditions.items():
                actual_value = alert_attrs.get(attr_name)
                if actual_value is None or actual_value != expected_value:
                    return None
            return len(rule.conditions)
        except (TypeError, AttributeError) as e:
            logger.warning(
                "Error evaluating rule '%s': %s", rule.name, str(e)
            )
            return None

    def reload(self) -> None:
        """Reload mapping configuration from disk.

        On successful parse, replaces the current rules with the new ones.
        On parse failure (malformed YAML, file not found, etc.), retains
        the previously loaded valid configuration and logs an error.
        """
        previous_rules = self._rules[:]

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                logger.warning(
                    "Mapping configuration file is empty on reload: %s",
                    self._config_path,
                )
                # Retain previous rules - empty config is treated as malformed
                self._rules = previous_rules
                return

            if isinstance(data, list):
                rules_data = data
            elif isinstance(data, dict):
                rules_data = data.get("rules", [])
            else:
                logger.error(
                    "Mapping configuration has unexpected format on reload: %s",
                    self._config_path,
                )
                # Retain previous rules on failure
                self._rules = previous_rules
                return

            if not isinstance(rules_data, list):
                logger.error(
                    "Mapping configuration must contain a list of rules on reload: %s",
                    self._config_path,
                )
                # Retain previous rules on failure
                self._rules = previous_rules
                return

            # Enforce max 500 rules limit
            if len(rules_data) > MAX_RULES:
                logger.warning(
                    "Mapping configuration contains %d rules on reload, "
                    "exceeding maximum of %d. Only the first %d rules will be loaded.",
                    len(rules_data),
                    MAX_RULES,
                    MAX_RULES,
                )
                rules_data = rules_data[:MAX_RULES]

            parsed_rules: list[MappingRule] = []
            for idx, rule_dict in enumerate(rules_data):
                try:
                    rule = self._parse_rule(rule_dict, idx)
                    if rule is not None:
                        parsed_rules.append(rule)
                except (TypeError, KeyError, ValueError) as e:
                    logger.warning(
                        "Skipping malformed rule at index %d during reload: %s",
                        idx,
                        str(e),
                    )
                    continue

            # If no valid rules were parsed but we had rules before,
            # treat this as a malformed configuration and retain previous rules
            if not parsed_rules and previous_rules and rules_data:
                logger.error(
                    "All rules in configuration are malformed on reload, "
                    "retaining previous configuration: %s",
                    self._config_path,
                )
                self._rules = previous_rules
                return

            self._rules = parsed_rules
            logger.info(
                "Reloaded %d mapping rules from %s",
                len(self._rules),
                self._config_path,
            )

        except FileNotFoundError:
            logger.error(
                "Mapping configuration file not found during reload: %s",
                self._config_path,
            )
            self._rules = previous_rules
        except yaml.YAMLError as e:
            logger.error(
                "Failed to parse YAML during reload, retaining previous configuration: %s",
                str(e),
            )
            self._rules = previous_rules
        except OSError as e:
            logger.error(
                "Error reading mapping configuration during reload: %s", str(e)
            )
            self._rules = previous_rules

    @property
    def rules(self) -> list[MappingRule]:
        """Return the currently loaded mapping rules (read-only)."""
        return self._rules[:]

    @property
    def config_path(self) -> str:
        """Return the path to the mapping configuration file."""
        return self._config_path
