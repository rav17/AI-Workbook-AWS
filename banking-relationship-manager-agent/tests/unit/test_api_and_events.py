import json
import sys

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


def test_deployed_lambda_entrypoint_rejects_missing_authorizer_claims():
    from aria.api.lambda_entry import handler

    response = handler(
        {
            "headers": {"Authorization": "Bearer arbitrary"},
            "body": json.dumps({"message": "hello"}),
        }
    )

    assert response["statusCode"] == 401


def test_deployed_lambda_handler_routes_authenticated_request_to_runtime(monkeypatch):
    from types import SimpleNamespace

    import aria.api.rest_handler as rest_handler
    from aria.api.lambda_entry import handler

    invocations = []

    class FakeCoordinator:
        def run(self, event, payload, callback, *, idempotency_key=None):
            runtime_session = SimpleNamespace(
                runtime_session_id="r" * 64,
                tenant_id="tenant-1",
                user_id="user-1",
            )
            return {
                **callback(runtime_session, {}),
                "session_id": "tenant-1:user-1:conversation-1",
                "runtime_session_id": runtime_session.runtime_session_id,
                "runtime_revision": 0,
            }

    class FakeRuntimeClient:
        def invoke(self, payload, **kwargs):
            invocations.append((payload, kwargs))
            return {"status": "processed", "response": "runtime response"}

    monkeypatch.setattr(
        rest_handler,
        "_build_runtime_coordinator",
        lambda: (FakeCoordinator(), FakeRuntimeClient()),
    )

    response = handler(
        {
            "requestContext": {
                "authorizer": {"claims": {"sub": "user-1", "custom:tenant_id": "tenant-1"}}
            },
            "body": json.dumps({"prompt": "hello", "conversation_id": "conversation-1"}),
        }
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {
        "status": "processed",
        "response": "runtime response",
        "session_id": "tenant-1:user-1:conversation-1",
        "runtime_session_id": "r" * 64,
        "runtime_revision": 0,
    }
    assert invocations == [
        (
            {"prompt": "hello", "conversation_id": "conversation-1"},
            {
                "runtime_session_id": "r" * 64,
                "tenant_id": "tenant-1",
                "user_id": "user-1",
            },
        )
    ]


def test_api_request_emits_structured_request_operation(caplog):
    with caplog.at_level("INFO", logger="aria.observability"):
        response = invoke_agent(
            {"body": json.dumps({"message": "hello"})},
            lambda payload, state: {"message": payload["message"], "state": state},
        )

    assert response["statusCode"] == 200
    assert '"event": "request.invoke"' in caplog.text


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


def test_rest_handler_requires_authorization_header():
    from aria.api.rest_handler import handler

    result = handler({"body": json.dumps({"message": "hello"})})

    assert result["statusCode"] == 401


def test_rest_handler_rejects_unverified_authorization_header():
    from aria.api.rest_handler import handler

    result = handler(
        {
            "headers": {"Authorization": "Bearer not-a-verified-token"},
            "body": json.dumps({"message": "hello"}),
        }
    )

    assert result["statusCode"] == 401


def test_rest_handler_accepts_verified_tenant_and_subject_claims(monkeypatch):
    from types import SimpleNamespace

    import aria.api.rest_handler as rest_handler
    from aria.api.rest_handler import handler

    class FakeCoordinator:
        def __init__(self):
            self.idempotency_key = None

        def run(self, event, payload, callback, *, idempotency_key=None):
            self.idempotency_key = idempotency_key
            runtime_session = SimpleNamespace(
                runtime_session_id="a" * 64,
                tenant_id="tenant-1",
                user_id="user-1",
            )
            return callback(runtime_session, {})

    class FakeRuntimeClient:
        def invoke(self, payload, **kwargs):
            return {"status": "processed", "response": payload["message"], **kwargs}

    coordinator = FakeCoordinator()
    monkeypatch.setattr(
        rest_handler,
        "_build_runtime_coordinator",
        lambda: (coordinator, FakeRuntimeClient()),
    )

    result = handler(
        {
            "requestContext": {
                "authorizer": {"claims": {"sub": "user-1", "custom:tenant_id": "tenant-1"}}
            },
            "headers": {"Idempotency-Key": "message-request-1"},
            "body": json.dumps({"message": "hello"}),
        }
    )

    assert result["statusCode"] == 200
    assert coordinator.idempotency_key == "message-request-1"


def test_runtime_coordinator_loads_arn_from_ssm(monkeypatch):
    import aria.api.rest_handler as rest_handler

    class FakeSsmClient:
        def get_parameter(self, *, Name):
            assert Name == "/aria/test/agentcore/runtime-arn"
            return {"Parameter": {"Value": "arn:aws:bedrock-agentcore:region:account:runtime/id"}}

    class FakeBoto3:
        def client(self, service_name):
            if service_name == "ssm":
                return FakeSsmClient()
            return object()

        def resource(self, service_name):
            assert service_name == "dynamodb"
            return SimpleNamespace(Table=lambda name: ("table", name))

    from types import SimpleNamespace

    monkeypatch.setenv("SESSION_TABLE_NAME", "sessions")
    monkeypatch.setenv("IDEMPOTENCY_TABLE_NAME", "idempotency")
    monkeypatch.setenv("AGENTCORE_RUNTIME_ARN_PARAMETER", "/aria/test/agentcore/runtime-arn")
    monkeypatch.setitem(sys.modules, "boto3", FakeBoto3())

    coordinator, runtime_client = rest_handler._build_runtime_coordinator()

    assert runtime_client.runtime_arn == "arn:aws:bedrock-agentcore:region:account:runtime/id"
    assert coordinator.runtime_adapter.client is runtime_client


def test_duplicate_idempotency_key_returns_conflict():
    from aria.api.lambda_entry import invoke_agent
    from aria.api.runtime_session import IdempotencyConflict

    def duplicate_handler(payload, state):
        raise IdempotencyConflict("duplicate_request")

    result = invoke_agent(
        {"body": json.dumps({"message": "hello"})},
        duplicate_handler,
    )

    assert result["statusCode"] == 409
    assert json.loads(result["body"]) == {"error": "duplicate_request"}


def test_event_handler_routes_maturity_and_outflow_events():
    from aria.events.handler import process_event

    maturity = process_event(
        {
            "id": "maturity-1",
            "detail-type": "MaturityDue",
            "detail": {"client_id": "client-1", "days_to_maturity": 30},
        }
    )
    outflow = process_event(
        {
            "id": "outflow-1",
            "detail-type": "LargeOutflowDetected",
            "detail": {"client_id": "client-1", "amount": 250000},
        }
    )

    assert maturity["event_type"] == "maturity"
    assert maturity["recommended_action"] == "review_reinvestment"
    assert outflow["event_type"] == "outflow"
    assert outflow["recommended_action"] == "rebalance_portfolio"
