"""End-to-end unit tests for AI advisory history, outcomes and feedback.

Covers the path for alerts with no playbook:
  advisory email -> pending incident in DynamoDB -> feedback link -> outcome
  -> model routing for the next occurrence,
plus the "resolved" signal from Alertmanager or a CloudWatch alarm returning to OK.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

import src.app as app_module
from src.agentic_ai.agents.model_router import MODEL_TIERS, AlertComplexity
from src.agentic_ai.agents.reasoning_agent import AgentConfig, AIReasoningAgent
from src.agentic_ai.models.domain import (
    IncidentRecord,
    RemediationPlan,
    RemediationStep,
)
from src.agentic_ai.models.incident_store import OUTCOME_PENDING, IncidentMemoryStore
from src.feedback_tokens import VERDICT_SUCCESS, create_feedback_token
from src.models import AlertmanagerAlert, AlertmanagerPayload
from tests.unit.fake_dynamodb import FakeDynamoDBClient

pytestmark = pytest.mark.unit

TABLE = "AiopsIncidentMemory-test"
SECRET = "unit-test-secret"  # noqa: S105 - test-only value
ALERT = "NetworkFloodDetected"
HOST = "i-0abc123"
PLAN_JSON = json.dumps(
    {
        "confidence": 0.9,
        "reasoning": "Traffic spike",
        "action": "rate_limit",
        "steps": [],
    }
)


@pytest.fixture
def store() -> IncidentMemoryStore:
    return IncidentMemoryStore(
        table_name=TABLE, dynamodb_client=FakeDynamoDBClient(TABLE)
    )


def _seed(store: IncidentMemoryStore, incident_id: str, outcome: str) -> None:
    store.record_incident(
        IncidentRecord(
            incident_id=incident_id,
            alert_name=ALERT,
            severity="P3",
            affected_service="web-frontend",
            affected_resource=HOST,
            remediation_action="rate_limit",
            outcome=outcome,
            execution_duration_seconds=0.0,
            timestamp_completed=datetime.now(timezone.utc),
            expiry_timestamp=0,
        )
    )


def _agent(store: IncidentMemoryStore) -> AIReasoningAgent:
    agent = AIReasoningAgent(
        config=AgentConfig(), incident_store=store, bedrock_client=MagicMock()
    )
    agent._invoke_with_retry = AsyncMock(return_value=PLAN_JSON)
    return agent


async def _reason(agent: AIReasoningAgent) -> None:
    await agent.reason(
        alert_name=ALERT,
        severity="P3",
        service_name="web-frontend",
        target_resource=HOST,
        labels={},
        incident_id="inc-new",
    )


# ---------------------------------------------------------------------------
# Model routing from DynamoDB history
# ---------------------------------------------------------------------------


async def test_well_known_successful_alert_routes_to_simple_tier(store) -> None:
    for n in range(5):
        _seed(store, f"ok-{n}", "success")
    agent = _agent(store)
    await _reason(agent)
    assert agent.last_model_id == MODEL_TIERS[AlertComplexity.SIMPLE]
    assert (
        agent._invoke_with_retry.await_args.kwargs["primary_model_id"]
        == (MODEL_TIERS[AlertComplexity.SIMPLE])
    )


async def test_pending_incidents_do_not_count_as_failures(store) -> None:
    """Advisories without feedback must not push routing to 'all past failed'."""
    for n in range(5):
        _seed(store, f"ok-{n}", "success")
    for n in range(5):
        _seed(store, f"pending-{n}", OUTCOME_PENDING)
    agent = _agent(store)
    await _reason(agent)
    assert agent.last_model_id == MODEL_TIERS[AlertComplexity.SIMPLE]


async def test_mixed_history_routes_to_moderate_tier(store) -> None:
    for n in range(3):
        _seed(store, f"ok-{n}", "success")
    _seed(store, "bad-1", "failure")
    agent = _agent(store)
    await _reason(agent)
    assert agent.last_model_id == MODEL_TIERS[AlertComplexity.MODERATE]


async def test_all_failed_history_routes_to_complex_tier(store) -> None:
    _seed(store, "bad-1", "failure")
    _seed(store, "bad-2", "timeout")
    agent = _agent(store)
    await _reason(agent)
    assert agent.last_model_id == MODEL_TIERS[AlertComplexity.COMPLEX]


async def test_last_model_id_is_the_model_that_answered(store) -> None:
    """Regression: a denied primary model was recorded although a fallback answered."""
    from botocore.exceptions import ClientError

    denied = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "marketplace"}},
        "InvokeModel",
    )
    answered: list[str] = []

    async def invoke(prompt: str, model_id: str) -> str:
        if model_id == MODEL_TIERS[AlertComplexity.COMPLEX]:
            raise denied
        answered.append(model_id)
        return PLAN_JSON

    agent = AIReasoningAgent(
        config=AgentConfig(), incident_store=store, bedrock_client=MagicMock()
    )
    agent._invoke_model = invoke
    await _reason(agent)  # no history -> routed to the complex tier, which is denied
    assert answered, "a fallback model should have answered"
    assert agent.last_model_id == answered[0]
    assert agent.last_model_id != MODEL_TIERS[AlertComplexity.COMPLEX]


async def test_no_history_routes_to_complex_tier(store) -> None:
    agent = _agent(store)
    await _reason(agent)
    assert agent.last_model_id == MODEL_TIERS[AlertComplexity.COMPLEX]


# ---------------------------------------------------------------------------
# Feedback endpoints
# ---------------------------------------------------------------------------


@pytest.fixture
def app_env(store):
    """Point the app at the fake store and a fixed signing secret."""
    with (
        patch.object(app_module, "incident_store", store),
        patch.object(app_module, "get_signing_secret", return_value=SECRET),
    ):
        yield store


async def _client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app_module.app), base_url="http://test"
    )


async def test_feedback_get_has_no_side_effects_and_post_records(app_env) -> None:
    _seed(app_env, "inc-fb", OUTCOME_PENDING)
    token = create_feedback_token("inc-fb", VERDICT_SUCCESS, SECRET)
    async with await _client() as client:
        page = await client.get(f"/feedback/{token}")
        assert page.status_code == 200
        assert f'action="/feedback/{token}/confirm"' in page.text
        assert app_env.get_incident("inc-fb").outcome == OUTCOME_PENDING

        done = await client.post(f"/feedback/{token}/confirm")
        assert done.status_code == 200
        assert "recorded" in done.text
        assert app_env.get_incident("inc-fb").outcome == "success"

        again = await client.post(f"/feedback/{token}/confirm")
        assert again.status_code == 200
        assert "already" in again.text


async def test_feedback_rejects_invalid_token(app_env) -> None:
    async with await _client() as client:
        assert (await client.get("/feedback/not-a-token")).status_code == 410
        assert (await client.post("/feedback/not-a-token/confirm")).status_code == 410


async def test_feedback_unknown_incident_returns_404(app_env) -> None:
    token = create_feedback_token("ghost", VERDICT_SUCCESS, SECRET)
    async with await _client() as client:
        assert (await client.get(f"/feedback/{token}")).status_code == 404


async def test_feedback_without_store_returns_503() -> None:
    token = create_feedback_token("inc-1", VERDICT_SUCCESS, SECRET)
    with (
        patch.object(app_module, "incident_store", None),
        patch.object(app_module, "get_signing_secret", return_value=SECRET),
    ):
        async with await _client() as client:
            assert (await client.post(f"/feedback/{token}/confirm")).status_code == 503


# ---------------------------------------------------------------------------
# Resolved alerts
# ---------------------------------------------------------------------------


def _payload(status: str) -> AlertmanagerPayload:
    return AlertmanagerPayload(
        version="4",
        group_key="g",
        status=status,
        receiver="aiops",
        alerts=[
            AlertmanagerAlert(
                status=status,
                labels={"alertname": ALERT, "instance": HOST, "severity": "critical"},
                annotations={},
                starts_at="2026-01-01T00:00:00Z",
                ends_at="2026-01-01T00:05:00Z",
                generator_url="",
                fingerprint="fp",
            )
        ],
    )


async def test_resolved_only_payload_skips_pipeline_and_marks_incident(app_env) -> None:
    _seed(app_env, "inc-res", OUTCOME_PENDING)
    pipeline = AsyncMock(return_value=[])
    with (
        patch.object(app_module.orchestrator, "process_alert_payload", pipeline),
        patch.object(
            app_module.devops_forwarder,
            "forward_resolved_async",
            AsyncMock(return_value=None),
        ),
    ):
        await app_module._process_and_notify(_payload("resolved"))
    pipeline.assert_not_awaited()
    item = next(iter(app_env._client.items.values()))
    assert item["resolution_status"] == {"S": "resolved"}
    assert item["outcome"] == {"S": OUTCOME_PENDING}


# ---------------------------------------------------------------------------
# Advisory email records the incident and carries feedback links
# ---------------------------------------------------------------------------


async def test_advisory_email_records_pending_incident_with_feedback_links(
    app_env,
) -> None:
    plan = RemediationPlan(
        incident_ids=["inc-mail"],
        steps=[
            RemediationStep(step_number=1, action="rate_limit", target_resource=HOST)
        ],
        confidence_score=0.8,
        reasoning_explanation="Traffic spike",
        selected_action="rate_limit",
        target_resource=HOST,
    )
    ses = MagicMock()
    with (
        patch.object(AIReasoningAgent, "reason", AsyncMock(return_value=plan)),
        patch.object(app_module, "_get_ses_client", return_value=ses),
    ):
        await app_module._send_ai_advisory_email(
            incident_id="inc-mail",
            alert_name=ALERT,
            severity="critical",
            instance=HOST,
            service_name="web-frontend",
            root_cause="spike",
            labels={},
            annotations={},
        )
    record = app_env.get_incident("inc-mail")
    assert record is not None and record.outcome == OUTCOME_PENDING
    body = ses.send_email.call_args.kwargs["Message"]["Body"]
    assert "/feedback/" in body["Html"]["Data"]
    assert "/feedback/" in body["Text"]["Data"]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("critical", "P1"),
        ("warning", "P2"),
        ("info", "P3"),
        ("P4", "P4"),
        ("bogus", "P3"),
    ],
)
async def test_advisory_passes_p_severity_to_router(
    app_env, label: str, expected: str
) -> None:
    """Regression: the raw label ("critical") never matched the router's P1-P5 rules."""
    plan = RemediationPlan(
        incident_ids=["inc-sev"],
        steps=[],
        confidence_score=0.8,
        reasoning_explanation="r",
        selected_action="a",
        target_resource=HOST,
    )
    reason = AsyncMock(return_value=plan)
    with (
        patch.object(AIReasoningAgent, "reason", reason),
        patch.object(app_module, "_get_ses_client", return_value=MagicMock()),
    ):
        await app_module._send_ai_advisory_email(
            incident_id="inc-sev",
            alert_name=ALERT,
            severity=label,
            instance=HOST,
            service_name="web-frontend",
            root_cause="spike",
            labels={},
            annotations={},
        )
    assert reason.await_args.kwargs["severity"] == expected
    assert app_env.get_incident("inc-sev").severity == expected


async def test_critical_alert_with_good_history_still_uses_complex_tier(store) -> None:
    """End to end through the real agent: P1 is always routed to the strongest model."""
    for n in range(5):
        _seed(store, f"ok-{n}", "success")
    agent = _agent(store)
    await agent.reason(
        alert_name=ALERT,
        severity=app_module._routing_severity("critical"),
        service_name="web-frontend",
        target_resource=HOST,
        labels={},
    )
    assert agent.last_model_id == MODEL_TIERS[AlertComplexity.COMPLEX]


async def test_advisory_email_still_sent_when_store_missing() -> None:
    ses = MagicMock()
    with (
        patch.object(app_module, "incident_store", None),
        patch.object(
            AIReasoningAgent, "reason", AsyncMock(side_effect=RuntimeError("down"))
        ),
        patch.object(app_module, "_get_ses_client", return_value=ses),
    ):
        await app_module._send_ai_advisory_email(
            incident_id="inc-x",
            alert_name=ALERT,
            severity="critical",
            instance=HOST,
            service_name="web-frontend",
            root_cause="spike",
            labels={},
            annotations={},
        )
    ses.send_email.assert_called_once()
    assert (
        "/feedback/"
        not in ses.send_email.call_args.kwargs["Message"]["Body"]["Html"]["Data"]
    )


# ---------------------------------------------------------------------------
# CloudWatch alarm Lambda: OK -> "resolved"
# ---------------------------------------------------------------------------


def _run_alarm_lambda(event: dict) -> tuple[dict, dict | None]:
    from src.agentic_ai.infra.stacks import simulation_stack

    namespace: dict = {}
    exec(simulation_stack._ALERT_LAMBDA_CODE, namespace)  # noqa: S102 - our own inline code
    ssm = MagicMock()
    ssm.get_parameter.return_value = {"Parameter": {"Value": "https://api.example.com"}}
    namespace["boto3"] = MagicMock(client=MagicMock(return_value=ssm))
    sent: dict = {}

    def fake_urlopen(req, timeout):
        sent["payload"] = json.loads(req.data)
        return MagicMock(status=200)

    env = {"ENVIRONMENT": "dev", "INSTANCE_ID": HOST, "ALERT_NAME": "HighCPUUsage"}
    with patch.dict("os.environ", env), patch("urllib.request.urlopen", fake_urlopen):
        result = namespace["handler"](event, None)
    return result, sent.get("payload")


def _sns(state: str) -> dict:
    message = {"NewStateValue": state, "NewStateReason": f"went {state}"}
    return {"Records": [{"Sns": {"Message": json.dumps(message)}}]}


def test_alarm_lambda_sends_firing_on_alarm() -> None:
    _, payload = _run_alarm_lambda(_sns("ALARM"))
    assert payload["status"] == "firing"
    assert payload["alerts"][0]["status"] == "firing"


def test_alarm_lambda_sends_resolved_on_ok() -> None:
    _, payload = _run_alarm_lambda(_sns("OK"))
    assert payload["status"] == "resolved"
    alert = payload["alerts"][0]
    assert alert["status"] == "resolved"
    assert alert["labels"]["alertname"] == "HighCPUUsage"
    assert alert["endsAt"] != "0001-01-01T00:00:00Z"


def test_alarm_lambda_reports_the_instance_the_alarm_watches() -> None:
    """The network alarm watches the secondary host; the alert must name it."""
    message = {
        "NewStateValue": "ALARM",
        "NewStateReason": "packets",
        "Trigger": {"Dimensions": [{"name": "InstanceId", "value": "i-0secondary"}]},
    }
    _, payload = _run_alarm_lambda(
        {"Records": [{"Sns": {"Message": json.dumps(message)}}]}
    )
    labels = payload["alerts"][0]["labels"]
    assert labels["instance"] == "i-0secondary"
    assert payload["alerts"][0]["fingerprint"].endswith("i-0secondary")


async def test_approved_remediation_updates_resolved_tracker() -> None:
    """Regression: a resolved alert after an approved fix was logged as 'before execution'."""
    from src.models import ExecutionResult, RemediationStatus

    tracker = app_module.ResolvedAlertTracker()
    tracker.register_pending("inc-appr", "HighMemoryUsage", HOST)
    approval = MagicMock(
        incident_id="inc-appr",
        playbook_path="playbooks/fix_high_memory.yml",
        affected_host=HOST,
        extra_vars={},
        alert_name="HighMemoryUsage",
        severity="critical",
        service_name="web-frontend",
        proposed_action="Execute playbooks/fix_high_memory.yml",
        root_cause="memory",
    )
    result = MagicMock(spec=ExecutionResult)
    result.status = RemediationStatus.SUCCESS
    result.duration_seconds = 1.0
    with (
        patch.object(app_module, "resolved_tracker", tracker),
        patch.object(app_module.executor, "execute", AsyncMock(return_value=result)),
        patch.object(app_module.orchestrator, "_guardrail_engine", None),
    ):
        await app_module._execute_approved_remediation(approval)
    decision = tracker.handle_resolved("HighMemoryUsage", HOST)
    assert not decision.should_cancel


def test_alarm_lambda_ignores_insufficient_data() -> None:
    result, payload = _run_alarm_lambda(_sns("INSUFFICIENT_DATA"))
    assert payload is None
    assert "skipped" in result
