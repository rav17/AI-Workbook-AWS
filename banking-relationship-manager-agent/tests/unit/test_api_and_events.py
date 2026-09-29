import json

from aria.api.lambda_entry import invoke_agent
from aria.events.handler import handle_event, normalize_event


def test_api_handler_parses_json_and_returns_json_response():
    response = invoke_agent(
        {"body": json.dumps({"message": "hello"})},
        lambda payload, state: {"message": payload["message"], "state": state},
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["message"] == "hello"


def test_api_handler_rejects_non_object_body():
    response = invoke_agent({"body": "[]"}, lambda payload, state: {})

    assert response["statusCode"] == 400


def test_event_normalization_requires_id_and_client():
    normalized = normalize_event(
        {
            "id": "event-1",
            "detail-type": "MaturityDue",
            "detail": {"client_id": "client-1", "days": 30},
        }
    )

    assert normalized["event_id"] == "event-1"
    assert normalized["client_id"] == "client-1"


def test_event_handler_passes_normalized_event_to_processor():
    result = handle_event(
        {"id": "event-2", "detail": {"client_id": "client-2"}},
        lambda event: {"event_type": event["event_type"]},
    )

    assert result == {
        "status": "processed",
        "event_id": "event-2",
        "result": {"event_type": "unknown"},
    }
