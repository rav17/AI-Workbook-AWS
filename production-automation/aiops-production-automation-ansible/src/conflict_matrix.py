"""Conflict Matrix for mutual exclusion between playbooks.

Manages conflict groups that define which playbooks are mutually exclusive
and cannot run concurrently on the same host. Configuration is loaded from
a YAML file following the same pattern as config/conflict_matrix.yml.
"""

import logging
from pathlib import Path

import yaml

from src.concurrency_models import ConflictGroup

logger = logging.getLogger(__name__)


class ConflictMatrix:
    """Enforces mutual exclusion between conflicting playbooks on the same host.

    A ConflictMatrix holds named groups of playbooks that are mutually exclusive.
    When one playbook in a group is executing, no other playbook in the same group
    should execute concurrently on the same host.
    """

    def __init__(self, groups: list[ConflictGroup]) -> None:
        """Initialize the ConflictMatrix with a list of conflict groups.

        Args:
            groups: List of ConflictGroup instances defining mutual exclusion sets.
        """
        self._groups = groups
        # Build a lookup: playbook_path -> set of conflicting playbook paths
        self._conflict_map: dict[str, set[str]] = {}
        for group in groups:
            for playbook in group.playbooks:
                # All other playbooks in the same group are conflicts
                conflicts = {p for p in group.playbooks if p != playbook}
                if playbook in self._conflict_map:
                    # A playbook can appear in multiple groups
                    self._conflict_map[playbook].update(conflicts)
                else:
                    self._conflict_map[playbook] = conflicts

    @classmethod
    def from_yaml(cls, path: str) -> "ConflictMatrix":
        """Load a ConflictMatrix from a YAML configuration file.

        Handles missing or invalid YAML gracefully by logging a warning
        and returning an empty ConflictMatrix.

        Args:
            path: Path to the conflict matrix YAML configuration file.

        Returns:
            A ConflictMatrix instance populated from the file, or an empty
            matrix if the file is missing or invalid.
        """
        try:
            config_path = Path(path)
            if not config_path.exists():
                logger.warning(
                    "Conflict matrix config file not found at %s, "
                    "using empty matrix (host-level locking only)",
                    path,
                )
                return cls(groups=[])

            with open(config_path, "r") as f:
                raw = yaml.safe_load(f)

            if not raw or not isinstance(raw, dict):
                logger.warning(
                    "Conflict matrix config file %s is empty or invalid, "
                    "using empty matrix",
                    path,
                )
                return cls(groups=[])

            raw_groups = raw.get("conflict_groups", [])
            if not isinstance(raw_groups, list):
                logger.warning(
                    "Conflict matrix config file %s has invalid 'conflict_groups' "
                    "field, using empty matrix",
                    path,
                )
                return cls(groups=[])

            groups: list[ConflictGroup] = []
            for entry in raw_groups:
                if not isinstance(entry, dict):
                    logger.warning(
                        "Skipping invalid conflict group entry: %s", entry
                    )
                    continue
                name = entry.get("name", "")
                playbooks = entry.get("playbooks", [])
                if not isinstance(name, str) or not name:
                    logger.warning(
                        "Skipping conflict group with missing/invalid name: %s",
                        entry,
                    )
                    continue
                if not isinstance(playbooks, list):
                    logger.warning(
                        "Skipping conflict group '%s' with invalid playbooks list",
                        name,
                    )
                    continue
                # Filter out non-string entries in playbooks list
                valid_playbooks = [p for p in playbooks if isinstance(p, str) and p]
                groups.append(ConflictGroup(name=name, playbooks=valid_playbooks))

            return cls(groups=groups)

        except (yaml.YAMLError, OSError, TypeError) as e:
            logger.warning(
                "Error loading conflict matrix from %s: %s. Using empty matrix.",
                path,
                e,
            )
            return cls(groups=[])

    def get_conflicts(self, playbook_path: str) -> set[str]:
        """Return all playbook paths that conflict with the given playbook.

        Returns the set of all OTHER playbooks that are in the same conflict
        group(s) as the given playbook. Does not include the input playbook itself.

        Args:
            playbook_path: The playbook path to check for conflicts.

        Returns:
            A set of playbook paths that conflict with the given playbook.
            Returns an empty set if the playbook is not in any conflict group.
        """
        return self._conflict_map.get(playbook_path, set()).copy()

    def is_conflicting(self, playbook_path: str, active_playbooks: set[str]) -> bool:
        """Check if playbook_path conflicts with any currently active playbook.

        Determines whether any playbook in the same conflict group as
        playbook_path is present in the active_playbooks set.

        Args:
            playbook_path: The playbook path to check.
            active_playbooks: Set of currently executing playbook paths.

        Returns:
            True if there is a conflict (an active playbook is in the same
            conflict group), False otherwise.
        """
        conflicts = self._conflict_map.get(playbook_path, set())
        return bool(conflicts & active_playbooks)

    def to_yaml(self) -> str:
        """Serialize the conflict matrix back to YAML.

        Produces YAML in the same format as config/conflict_matrix.yml:

            conflict_groups:
              - name: group-name
                playbooks:
                  - playbook/path.yml

        Returns:
            A YAML string representation of the conflict matrix.
        """
        data = {
            "conflict_groups": [
                {"name": group.name, "playbooks": group.playbooks}
                for group in self._groups
            ]
        }
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @property
    def groups(self) -> list[ConflictGroup]:
        """Return the list of conflict groups."""
        return self._groups
