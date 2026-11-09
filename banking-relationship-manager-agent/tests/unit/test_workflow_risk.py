from aria.tools.knowledge_tool import ProductAnswer, query_product_info
from aria.tools.risk_tool import assess_risk_appetite, get_risk_questionnaire
from aria.workflow.patch import StatePatch
from aria.workflow.state import WorkflowState


def test_risk_questionnaire_includes_market_risk_checks():
    questions = get_risk_questionnaire()

    assert len(questions) >= 3
    assert any("market" in q.lower() for q in questions)


def test_assess_risk_appetite_classifies_consistently():
    assert assess_risk_appetite({"risk_tolerance": 8}) == "high"
    assert assess_risk_appetite({"risk_tolerance": 4}) == "moderate"
    assert assess_risk_appetite({"risk_tolerance": 1}) == "conservative"


def test_workflow_state_patch_applies_revision():
    state = WorkflowState(client_id="CUST-1", workflow_version=1)
    patch = StatePatch(field="risk_appetite", value="moderate")

    updated = state.apply_patch(patch)

    assert updated.risk_appetite == "moderate"
    assert updated.workflow_version == 2


def test_workflow_state_applies_multiple_operations_atomically():
    state = WorkflowState(client_id="CUST-1")
    patch = StatePatch.multi(
        [("risk_appetite", "moderate"), ("segment", "premier")],
        reason="profile_update",
    )

    updated = state.apply_patch(patch, expected_revision=1)

    assert updated.risk_appetite == "moderate"
    assert updated.segment == "premier"
    assert updated.revision == 2


def test_workflow_state_rejects_stale_or_locked_atomic_patches():
    state = WorkflowState(client_id="CUST-1")

    try:
        state.apply_patch(
            StatePatch.multi([("risk_appetite", "high"), ("unknown", "value")]),
            expected_revision=1,
        )
    except ValueError as exc:
        assert str(exc) == "unknown_field"
    else:
        raise AssertionError("unknown fields must reject the complete patch")

    try:
        state.apply_patch(
            StatePatch(field="segment", value="retail"),
            expected_revision=0,
        )
    except RuntimeError as exc:
        assert str(exc) == "stale_revision"
    else:
        raise AssertionError("stale revisions must be retryable conflicts")

    try:
        state.apply_patch(
            StatePatch(field="segment", value="retail"),
            locked_fields={"segment"},
        )
    except ValueError as exc:
        assert str(exc) == "locked_field"
    else:
        raise AssertionError("locked fields must reject the complete patch")

    assert state.risk_appetite is None
    assert state.segment is None
    assert state.revision == 1


def test_query_product_info_returns_sourced_answer():
    answer = query_product_info(
        "What is the rate on a savings account?",
        knowledge={
            "savings account": {
                "answer": "The standard savings interest rate is 4.25% per annum.",
                "source_date": "2026-09-01",
                "confidence": 0.91,
            }
        },
    )

    assert isinstance(answer, ProductAnswer)
    assert answer.answer.lower().startswith("the standard")
    assert answer.source_date == "2026-09-01"
    assert answer.confidence >= 0.8
