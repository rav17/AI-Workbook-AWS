from hypothesis import given
from hypothesis import strategies as st

from aria.agent import AriaAgent
from aria.tools.maturity_tool import evaluate_maturity_event, evaluate_outflow_event


@given(balance=st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False))
def test_balance_qualification_is_monotonic(balance: float):
    result = AriaAgent(kyc_status_provider=lambda client_id: "current").recommend_products(
        {"client_id": "property-client", "risk_appetite": "moderate", "balance": balance}
    )
    recommendations = " ".join(result["recommendations"]).lower()

    if balance >= 100000:
        assert "fixed deposit" in recommendations
    else:
        assert "fixed deposit" not in recommendations


@given(
    amount=st.floats(min_value=0, max_value=2_000_000, allow_nan=False, allow_infinity=False),
    threshold=st.floats(min_value=1, max_value=1_000_000, allow_nan=False, allow_infinity=False),
)
def test_outflow_alert_matches_threshold(amount: float, threshold: float):
    result = evaluate_outflow_event({"amount": amount, "threshold_amount": threshold})

    assert (result["status"] == "alert") is (amount >= threshold)
    assert (result["recommended_action"] == "rebalance_portfolio") is (amount >= threshold)


@given(days=st.integers(min_value=-365, max_value=365))
def test_maturity_notification_boundary_is_exact(days: int):
    result = evaluate_maturity_event({"days_to_maturity": days, "amount": 1000})

    assert (result["status"] == "notify") is (days <= 30)
    if days <= 30:
        assert result["recommended_action"] == "review_reinvestment"
    else:
        assert result["recommended_action"] == "continue_tracking"


@given(
    name=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        min_size=1,
        max_size=20,
    )
)
def test_response_style_preserves_name_and_bulleted_next_steps(name: str):
    response = AriaAgent().handle_client_message(
        {"client_id": "property-client", "name": name, "message": "Hello"},
        crm_store={},
    )

    assert name in response["greeting"]
    assert response["next_steps"]
    assert all(step.startswith("- ") for step in response["next_steps"])
