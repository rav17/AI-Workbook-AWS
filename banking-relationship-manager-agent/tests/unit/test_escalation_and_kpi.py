from aria.observability import Observability
from aria.tools.escalation_tool import escalate_request


def test_escalation_route_handles_high_value_credit():
    response = escalate_request(
        "high-value credit request", {"client_id": "CUST-9", "name": "Aisha"}
    )

    assert response["team"] == "credit-underwriting"
    assert response["priority"] == "high"


def test_observability_records_metrics_without_sensitive_data():
    metrics = Observability()
    entry = metrics.log_event("request", {"message": "Hello", "secret": "should-not-log"})

    assert entry["event"] == "request"
    assert "secret" not in str(entry)
    assert entry["message"] == "Hello"
