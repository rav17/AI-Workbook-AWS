from __future__ import annotations

from aria.workflow.dependencies import WorkflowDependencyGraph


def next_step_after_change(
    steps: list[str], changed_fields: set[str], graph: WorkflowDependencyGraph | None = None
) -> str | None:
    graph = graph or WorkflowDependencyGraph()
    affected = set()
    for field in changed_fields:
        affected |= graph.invalidates_for(field)

    for step in steps:
        if step in affected:
            return step
    return None
