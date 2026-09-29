from aria.workflow.dependencies import WorkflowDependencyGraph
from aria.workflow.next_step import next_step_after_change


def test_dependency_graph_tracks_transitive_invalidations():
    graph = WorkflowDependencyGraph()

    assert "risk_questionnaire" in graph.invalidates_for("risk_appetite")
    assert "product_recommendation" in graph.invalidates_for("risk_appetite")
    assert "product_recommendation" in graph.invalidates_for("kyc_status")


def test_next_step_selects_earliest_affected_step():
    steps = [
        "client_profile",
        "risk_questionnaire",
        "kyc_check",
        "product_recommendation",
    ]

    next_step = next_step_after_change(
        steps, changed_fields={"risk_appetite"}, graph=WorkflowDependencyGraph()
    )
    assert next_step == "risk_questionnaire"
