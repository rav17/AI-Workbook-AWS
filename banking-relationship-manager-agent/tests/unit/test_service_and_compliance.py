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


def test_aml_activity_flags_threshold_crossing():
    flagged = flag_aml_activity({"monthly_transactions": 750000, "threshold": 500000})
    assert flagged["status"] == "flagged"
    assert flagged["severity"] == "high"
