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


def test_observability_records_structured_operation_metadata():
    entry = Observability().log_operation(
        "tool.query_product_info",
        {"client_id": "CUST-9", "password": "secret"},
        correlation_id="corr-9",
        session_id="runtime-9",
        latency_ms=12.5,
        status="success",
    )

    assert entry["category"] == "tool"
    assert entry["tool"] == "query_product_info"
    assert entry["session_id"] == "runtime-9"
    assert entry["latency_ms"] == 12.5
    assert entry["status"] == "success"
    assert "secret" not in str(entry)


def test_observability_emits_json_for_cloudwatch(caplog):
    with caplog.at_level("INFO", logger="aria.observability"):
        entry = Observability().emit_operation(
            "request.invoke",
            {"client_id": "CUST-9", "token": "secret"},
            correlation_id="corr-10",
        )

    assert entry["correlation_id"] == "corr-10"
    assert "token" not in caplog.text
    assert '"event": "request.invoke"' in caplog.text
