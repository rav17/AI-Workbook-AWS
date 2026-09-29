from aria.agent import AriaAgent
from aria.tools.crm_tool import create_followup_reminder, log_interaction, update_client_profile


def test_agent_greets_and_requests_risk_for_market_inquiry():
    agent = AriaAgent()

    response = agent.handle_client_message(
        {
            "client_id": "CUST-1",
            "name": "Aisha",
            "needs": ["wealth growth"],
            "risk_appetite": None,
            "message": "I want to invest in a market-linked product.",
        },
        crm_store={},
    )

    assert "Aisha" in response["greeting"]
    assert "risk questionnaire" in response["next_step"].lower()


def test_update_client_profile_persists_fields():
    result = update_client_profile(
        "CUST-1",
        {
            "name": "Aisha Khan",
            "segment": "premier",
            "risk_appetite": "moderate",
            "needs": ["wealth growth", "tax planning"],
        },
    )

    assert result["client_id"] == "CUST-1"
    assert result["risk_appetite"] == "moderate"
    assert "wealth growth" in result["needs"]


def test_log_interaction_creates_summary_and_reminder():
    summary = log_interaction(
        {
            "client_id": "CUST-1",
            "topics": ["mutual funds", "risk tolerance"],
            "preferences": ["concise answers"],
            "follow_up": "Send product brief",
        }
    )

    assert summary["summary"]["topics"] == ["mutual funds", "risk tolerance"]
    reminder = create_followup_reminder("CUST-1", "Send product brief")
    assert reminder["client_id"] == "CUST-1"
    assert "Send product brief" in reminder["message"]
