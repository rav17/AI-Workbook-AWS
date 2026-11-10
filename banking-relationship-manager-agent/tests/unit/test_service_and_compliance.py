import pytest

from aria.agent import AriaAgent
from aria.tools.compliance_tool import check_kyc_status, flag_aml_activity
from aria.tools.knowledge_tool import answer_service_query


def test_service_query_returns_answer_and_source_date():
    response = answer_service_query(
        "How do I change my address?",
        knowledge={
            "address update": {
                "answer": "Log in to the app, select profile, and submit the new address.",
                "source_date": "2026-09-01",
                "confidence": 0.92,
            }
        },
    )

    assert response["status"] == "answered"
    assert "profile" in response["answer"].lower()
    assert response["source_date"] == "2026-09-01"


def test_agent_routes_resolvable_service_query_to_knowledge_answer():
    agent = AriaAgent(
        kyc_status_provider=lambda client_id: "current",
        knowledge_provider=lambda question: {
            "address update": {
                "answer": "Use Profile, then select Update address.",
                "source_date": "2026-09-15",
                "confidence": 0.95,
            }
        },
    )
    response = agent.handle_client_message(
        {
            "client_id": "CUST-12",
            "name": "Aisha",
            "message": "How do I update my address?",
        },
        crm_store={},
    )

    assert response["service_query"]["status"] == "answered"
    assert "Update address" in response["service_query"]["answer"]
    assert response["service_query"]["source_date"] == "2026-09-15"


def test_agent_escalates_unresolved_service_query_with_client_context():
    agent = AriaAgent(kyc_status_provider=lambda client_id: "current")
    response = agent.handle_client_message(
        {
            "client_id": "CUST-13",
            "name": "Aisha",
            "segment_flags": ["premier"],
            "session_id": "SESSION-13",
            "message": "What is the international wire fee for this account?",
            "knowledge_base": {},
        },
        crm_store={},
    )

    assert response["escalation"]["status"] == "escalated"
    assert response["escalation"]["category"] == "unresolved query"
    assert response["escalation"]["context"]["session_id"] == "SESSION-13"
    assert "international wire fee" in response["escalation"]["context"]["question"].lower()


def test_service_query_guardrail_blocks_credentials_before_knowledge_lookup():
    provider_queries = []
    agent = AriaAgent(
        kyc_status_provider=lambda client_id: "current",
        knowledge_provider=lambda question: provider_queries.append(question) or {},
    )

    response = agent.handle_client_message(
        {
            "client_id": "CUST-14",
            "name": "Aisha",
            "message": "What is the wire fee? My OTP is 123456",
        },
        crm_store={},
    )

    assert response["service_query"]["status"] == "blocked"
    assert provider_queries == []
    assert "123456" not in str(response)


def test_service_query_escalates_when_unresolved():
    response = answer_service_query(
        "What is the exact fee for a private placement?",
        knowledge={},
    )

    assert response["status"] == "escalate"
    assert "human" in response["message"].lower()


def test_kyc_status_blocks_missing_or_expired_records():
    assert check_kyc_status("expired")["status"] == "blocked"
    assert check_kyc_status("current")["status"] == "approved"
    assert check_kyc_status(None)["status"] == "blocked"


def test_aml_activity_flags_threshold_crossing():
    flagged = flag_aml_activity({"monthly_transactions": 750000, "threshold": 500000})
    assert flagged["status"] == "flagged"
    assert flagged["severity"] == "high"


@pytest.mark.parametrize(
    "metrics",
    [
        {},
        {"monthly_transactions": 10},
        {"threshold": 500},
        {"monthly_transactions": "invalid", "threshold": 500},
        {"monthly_transactions": -1, "threshold": 500},
        {"monthly_transactions": 1, "threshold": 0},
        {"monthly_transactions": 1, "threshold": -1},
        {"monthly_transactions": "NaN", "threshold": 500},
    ],
)
def test_aml_activity_requires_complete_valid_metrics(metrics):
    result = flag_aml_activity(metrics)

    assert result["status"] == "insufficient_data"
    assert result["severity"] == "unknown"


def test_aml_activity_does_not_flag_zero_activity_with_positive_threshold():
    result = flag_aml_activity({"monthly_transactions": 0, "threshold": 1})

    assert result["status"] == "clear"


def test_kyc_gate_blocks_unapproved_requests_before_product_recommendation():
    agent = AriaAgent()
    result = agent.handle_client_message(
        {
            "client_id": "CUST-10",
            "name": "Aisha",
            "needs": ["wealth growth"],
            "kyc_status": "expired",
            "message": "I want to open a new investment product.",
        },
        crm_store={},
    )

    assert result["requires_kyc"] is True
    assert "kyc" in str(result["next_step"]).lower()


@pytest.mark.parametrize(
    "provider",
    [
        lambda client_id: "verified",
        lambda client_id: 123,
        lambda client_id: None,
    ],
)
def test_invalid_compliance_provider_response_fails_closed(provider):
    agent = AriaAgent(kyc_status_provider=provider)

    result = agent.recommend_products(
        {"client_id": "CUST-15", "risk_appetite": "moderate", "balance": 100000}
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "kyc_required"
    assert result["recommendations"] == []


def test_compliance_provider_timeout_fails_closed():
    def unavailable_provider(client_id: str) -> str:
        raise TimeoutError("provider unavailable")

    agent = AriaAgent(kyc_status_provider=unavailable_provider)
    result = agent.recommend_products(
        {"client_id": "CUST-16", "risk_appetite": "moderate", "balance": 100000}
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "kyc_required"
    assert result["recommendations"] == []


def test_client_supplied_current_kyc_does_not_authorize_product_recommendations():
    agent = AriaAgent()

    result = agent.recommend_products(
        {
            "client_id": "CUST-11",
            "kyc_status": "current",
            "risk_appetite": "moderate",
        }
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "kyc_required"
    assert result["recommendations"] == []


def test_escalation_tool_maps_reason_to_team_and_timeline():
    from aria.tools.escalation_tool import escalate_request

    escalation = escalate_request("fraud alert", {"client_id": "CUST-7", "name": "Aisha"})

    assert escalation["priority"] == "high"
    assert escalation["team"] == "legal-and-risk"
    assert escalation["response_timeline"]
