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
