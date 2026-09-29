from aria.agent import AriaAgent
from aria.tools.maturity_tool import evaluate_maturity_event


def test_wallet_profile_detects_external_assets():
    agent = AriaAgent()
    result = agent.handle_wallet_profile(
        {
            "client_id": "CUST-22",
            "name": "Aisha",
            "external_assets": ["FD 250000", "Demat account"],
        }
    )

    assert result["wallet_profile"]["external_assets"] == ["FD 250000", "Demat account"]
    assert "benefit" in result["suggestion"].lower()


def test_recommend_products_by_risk_profile():
    agent = AriaAgent()
    result = agent.recommend_products(
        {
            "risk_appetite": "moderate",
            "goal": "wealth growth",
            "balance": 250000,
        }
    )

    assert any("mutual fund" in item.lower() for item in result["recommendations"])
    assert any("fixed deposit" in item.lower() for item in result["recommendations"])


def test_maturity_tool_flags_30_day_maturity():
    result = evaluate_maturity_event({"days_to_maturity": 30, "amount": 150000})

    assert result["status"] == "notify"
    assert result["recommended_action"] == "review_reinvestment"
