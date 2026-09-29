"""DAG-based execution dependency management."""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_MAX_NODES = 200
_MAX_EDGES = 500


@dataclass
class ValidationResult:
    """Result of graph validation."""

    valid: bool
    error: Optional[str] = None
    cycle_path: Optional[list[str]] = None


class DependencyGraph:
    """DAG-based execution dependency management.

    Defines ordering constraints between remediation actions.
    An edge from A to B means A must complete before B can begin.
    """

    def __init__(self) -> None:
        # action -> list of successors
        self._successors: dict[str, list[str]] = defaultdict(list)
        # action -> list of predecessors
        self._predecessors: dict[str, list[str]] = defaultdict(list)
        self._nodes: set[str] = set()
        self._edge_count: int = 0

    def load_from_yaml(self, path: str) -> bool:
        """Load dependency configuration from a YAML file.

        Returns True if loaded successfully, False if validation fails.
        Retains previous graph on failure.
        """
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            logger.error("Failed to load dependency graph from %s: %s", path, e)
            return False

        if not isinstance(data, dict) or "dependencies" not in data:
            logger.error("Invalid dependency config: missing 'dependencies' key in %s", path)
            return False

        dependencies = data["dependencies"]
        if not isinstance(dependencies, list):
            logger.error("Invalid 'dependencies': expected list in %s", path)
            return False

        # Build a temporary graph for validation
        temp_successors: dict[str, list[str]] = defaultdict(list)
        temp_predecessors: dict[str, list[str]] = defaultdict(list)
        temp_nodes: set[str] = set()

        for dep in dependencies:
            if not isinstance(dep, dict):
                logger.error("Invalid dependency entry: expected dict")
                return False

            predecessor = dep.get("predecessor")
            successor = dep.get("successor")

            if not predecessor or not successor:
                logger.error("Dependency missing 'predecessor' or 'successor'")
                return False

            temp_nodes.add(predecessor)
            temp_nodes.add(successor)
            temp_successors[predecessor].append(successor)
            temp_predecessors[successor].append(predecessor)

        edge_count = len(dependencies)

        # Check limits
        if len(temp_nodes) > _MAX_NODES:
            logger.error(
                "Dependency graph exceeds max nodes: %d > %d",
                len(temp_nodes),
                _MAX_NODES,
            )
            return False

        if edge_count > _MAX_EDGES:
            logger.error(
                "Dependency graph exceeds max edges: %d > %d",
                edge_count,
                _MAX_EDGES,
            )
            return False

        # Validate acyclic
        validation = self._detect_cycle(temp_successors, temp_nodes)
        if not validation.valid:
            logger.error(
                "Dependency graph contains a cycle: %s",
                " -> ".join(validation.cycle_path or []),
            )
            return False

        # Validation passed — apply new graph
        self._successors = temp_successors
        self._predecessors = temp_predecessors
        self._nodes = temp_nodes
        self._edge_count = edge_count

        logger.info(
            "Loaded dependency graph: %d nodes, %d edges from %s",
            len(temp_nodes),
            edge_count,
            path,
        )
        return True

    def validate_acyclic(self) -> ValidationResult:
        """Validate that the current graph is acyclic."""
        return self._detect_cycle(self._successors, self._nodes)

    def get_predecessors(self, action_name: str) -> list[str]:
        """Get the direct predecessors of an action."""
        return list(self._predecessors.get(action_name, []))

    def get_transitive_successors(self, action_name: str) -> list[str]:
        """Get all transitive successors of an action (BFS)."""
        visited: set[str] = set()
        queue = deque(self._successors.get(action_name, []))

        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(self._successors.get(node, []))

        return sorted(visited)

    def are_independent(self, action_a: str, action_b: str) -> bool:
        """Check if two actions have no dependency relationship.

        They are independent if neither is a transitive predecessor/successor
        of the other.
        """
        if action_a not in self._nodes or action_b not in self._nodes:
            return True

        # Check if b is reachable from a
        successors_a = set(self.get_transitive_successors(action_a))
        if action_b in successors_a:
            return False

        # Check if a is reachable from b
        successors_b = set(self.get_transitive_successors(action_b))
        if action_a in successors_b:
            return False

        return True

    def has_action(self, action_name: str) -> bool:
        """Check if an action exists in the graph."""
        return action_name in self._nodes

    def _detect_cycle(
        self, successors: dict[str, list[str]], nodes: set[str]
    ) -> ValidationResult:
        """Detect cycles using topological sort (Kahn's algorithm).

        Returns ValidationResult with cycle_path if a cycle is found.
        """
        # Compute in-degrees
        in_degree: dict[str, int] = {node: 0 for node in nodes}
        for node in nodes:
            for successor in successors.get(node, []):
                in_degree[successor] = in_degree.get(successor, 0) + 1

        # Start with nodes that have no incoming edges
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        sorted_count = 0

        while queue:
            node = queue.popleft()
            sorted_count += 1
            for successor in successors.get(node, []):
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        if sorted_count != len(nodes):
            # Cycle detected — find a cycle path using DFS
            cycle_path = self._find_cycle_path(successors, nodes)
            return ValidationResult(valid=False, cycle_path=cycle_path)

        return ValidationResult(valid=True)

    def _find_cycle_path(
        self, successors: dict[str, list[str]], nodes: set[str]
    ) -> list[str]:
        """Find a cycle path using DFS for error reporting."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {node: WHITE for node in nodes}
        path: list[str] = []

        def dfs(node: str) -> bool:
            color[node] = GRAY
            path.append(node)
            for successor in successors.get(node, []):
                if color.get(successor, WHITE) == GRAY:
                    # Found cycle
                    path.append(successor)
                    return True
                if color.get(successor, WHITE) == WHITE:
                    if dfs(successor):
                        return True
            path.pop()
            color[node] = BLACK
            return False

        for node in nodes:
            if color[node] == WHITE:
                if dfs(node):
                    return path
        return []
