from aria.agent import AriaAgent
from aria.tools.crm_tool import create_followup_reminder, log_interaction, update_client_profile
from aria.tools.knowledge_tool import answer_service_query


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
            "session_id": "SESSION-1",
            "topics": ["mutual funds", "risk tolerance"],
            "preferences": ["concise answers"],
            "follow_up": "Send product brief",
            "segment_flags": ["premier", "eligible_for_advisory"],
        }
    )

    assert summary["summary"]["topics"] == ["mutual funds", "risk tolerance"]
    assert summary["summary"]["session_id"] == "SESSION-1"
    assert summary["summary"]["segment_flags"] == ["premier", "eligible_for_advisory"]
    assert summary["summary"]["interaction_date"]
    assert summary["summary"]["follow_up_actions"][0]["action"] == "Send product brief"
    reminder = create_followup_reminder("CUST-1", "Send product brief")
    assert reminder["client_id"] == "CUST-1"
    assert "Send product brief" in reminder["message"]


def test_log_interaction_redacts_credentials_before_serializing_summary():
    summary = log_interaction(
        {
            "client_id": "CUST-14",
            "session_id": "SESSION-14",
            "topics": ["Client shared OTP 123456"],
            "preferences": ["password is account-secret"],
            "follow_up": "Confirm OTP 123456",
        }
    )

    rendered = str(summary)
    assert "123456" not in rendered
    assert "account-secret" not in rendered
    assert "[REDACTED]" in rendered


def test_client_profile_does_not_accept_caller_kyc_status():
    result = update_client_profile(
        "CUST-2",
        {
            "name": "Aisha Khan",
            "segment": "premier",
            "risk_appetite": "moderate",
            "family_members": ["Husband", "Child"],
            "kyc_status": "current",
        },
    )

    assert result["family_members"] == ["Husband", "Child"]
    assert "kyc_status" not in result


def test_agent_suggests_family_ctg_for_eligible_accounts():
    agent = AriaAgent()
    response = agent.handle_client_message(
        {
            "client_id": "CUST-2",
            "name": "Aisha",
            "needs": ["wealth growth"],
            "family_members": ["Spouse", "Child"],
            "message": "I want to review my family finances.",
        },
        crm_store={},
    )

    text = " ".join(str(value) for value in response.values()).lower()
    assert "family" in text
    assert "ctg" in text or "suggest" in text


def test_agent_response_is_personalized_empathetic_and_actionable():
    agent = AriaAgent()
    response = agent.handle_client_message(
        {
            "client_id": "CUST-3",
            "name": "Aisha",
            "needs": ["wealth growth"],
            "message": "I want to review my finances.",
        },
        crm_store={},
    )

    assert response["greeting"].startswith("Hello Aisha")
    assert "happy to help" in response["tone"]
    assert response["next_steps"]
    assert all(step.startswith("- ") for step in response["next_steps"])


def test_agent_registers_and_dispatches_core_tools(caplog):
    agent = AriaAgent(kyc_status_provider=lambda client_id: "current")

    assert {"handle_client_message", "handle_wallet_profile", "recommend_products"}.issubset(
        agent.registered_tools()
    )
    with caplog.at_level("INFO", logger="aria.observability"):
        result = agent.execute_tool(
            "recommend_products",
            {"client_id": "CUST-5", "risk_appetite": "moderate", "balance": 100000},
        )

    assert result["recommendations"]
    assert '"event": "tool.recommend_products"' in caplog.text


def test_answer_service_query_escalates_low_confidence_or_missing_rate_source():
    result = answer_service_query(
        "What is the savings account rate?",
        {
            "savings account": {
                "answer": "Rate is 2.5%.",
                "confidence": 0.42,
            }
        },
    )

    assert result["status"] == "escalate"
