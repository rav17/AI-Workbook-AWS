"""Unit tests for the DevOps Agent findings Lambda (no AWS calls)."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from src.agentic_ai.lambdas.devops_agent_findings import handler

pytestmark = pytest.mark.unit

SPACE = "15dd52dd-0f2e-4fa9-bcf1-e40444b7fb8c"
INCIDENT = "4acb31c9-1111-2222-3333-444455556666"
REFERENCE = f"aiops-{INCIDENT}-unmatched"
SUMMARY = "# Investigation Summary\n## Findings\nDisk /var is 97% full on billing-api."


def _error(code: str, operation: str = "GetBacklogTask") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


def _task(task_id: str = "task-1", reference: str = REFERENCE, **extra) -> dict:
    return {
        "taskId": task_id,
        "title": "[AIOps/dev] DiskSpaceCritical on i-0123",
        "priority": "HIGH",
        "executionId": "exec-1",
        "reference": {"referenceId": reference},
        **extra,
    }


def _event(
    detail_type: str = "Investigation Completed",
    task_id: str = "task-1",
    record_id: str | None = "rec-1",
    event_id: str = "evt-1",
    status: str = "COMPLETED",
) -> dict:
    data = {"task_type": "INVESTIGATION", "priority": "HIGH", "status": status}
    if record_id:
        data["summary_record_id"] = record_id
    return {
        "version": "0",
        "id": event_id,
        "detail-type": detail_type,
        "source": "aws.aidevops",
        "region": "us-east-1",
        "detail": {
            "version": "1.0.0",
            "metadata": {
                "agent_space_id": SPACE,
                "task_id": task_id,
                "execution_id": "exec-1",
            },
            "data": data,
        },
    }


class FakeDevOps:
    """Stands in for the boto3 devops-agent client."""

    def __init__(
        self,
        tasks=None,
        errors=None,
        pages_per_attempt=None,
        result_pages_per_attempt=None,
    ) -> None:
        self.tasks = tasks if tasks is not None else {"task-1": _task()}
        self.errors = errors or {}
        self.pages_per_attempt = pages_per_attempt or [
            [{"records": [{"recordId": "rec-1", "content": SUMMARY}]}]
        ]
        self.result_pages_per_attempt = result_pages_per_attempt or [[{"records": []}]]
        self.paginate_calls: list[dict] = []
        self.summary_calls: list[dict] = []
        self.result_calls: list[dict] = []
        self.task_calls: list[str] = []

    def get_backlog_task(self, agentSpaceId, taskId):  # noqa: N803 - boto3 naming
        self.task_calls.append(taskId)
        if taskId in self.errors:
            raise self.errors[taskId]
        return {"task": self.tasks[taskId]}

    def get_paginator(self, name):
        assert name == "list_journal_records"
        return self

    def paginate(self, **kwargs):
        self.paginate_calls.append(kwargs)
        if kwargs["recordType"] == "investigation_result":
            self.result_calls.append(kwargs)
            pages, calls = self.result_pages_per_attempt, self.result_calls
        else:
            self.summary_calls.append(kwargs)
            pages, calls = self.pages_per_attempt, self.summary_calls
        return iter(pages[min(len(calls) - 1, len(pages) - 1)])


@pytest.fixture
def aws(monkeypatch):
    """Install fake clients and environment; returns a namespace of the fakes."""
    monkeypatch.setenv("TABLE_NAME", "AiopsIncidentMemory-dev")
    monkeypatch.setenv("SES_FROM_ADDRESS", "ops@example.com")
    monkeypatch.setenv("OPERATOR_EMAIL", "oncall@example.com")
    monkeypatch.setattr(handler, "_sleep", MagicMock())

    class Fakes:
        devops = FakeDevOps()
        ses = MagicMock()
        table = MagicMock()

    Fakes.table.get_item.return_value = {}

    def install(devops: FakeDevOps | None = None) -> type:
        Fakes.devops = devops or FakeDevOps()
        monkeypatch.setattr(
            handler,
            "_clients",
            {
                "devops-agent:us-east-1": Fakes.devops,
                "ses:": Fakes.ses,
                "table": Fakes.table,
            },
        )
        return Fakes

    Fakes.install = staticmethod(install)  # type: ignore[attr-defined]
    install()
    return Fakes


def _sent_email(fakes) -> dict:
    fakes.ses.send_email.assert_called_once()
    return fakes.ses.send_email.call_args.kwargs


class TestCompleted:
    def test_emails_the_summary_and_records_delivery(self, aws) -> None:
        result = handler.lambda_handler(_event(), None)

        assert result == {
            "status": "sent",
            "incident_id": INCIDENT,
            "has_summary": True,
            "has_result": False,
        }
        mail = _sent_email(aws)
        assert mail["Source"] == "ops@example.com"
        assert mail["Destination"] == {"ToAddresses": ["oncall@example.com"]}
        assert "DiskSpaceCritical" in mail["Message"]["Subject"]["Data"]
        assert "97% full" in mail["Message"]["Body"]["Text"]["Data"]
        assert "97% full" in mail["Message"]["Body"]["Html"]["Data"]
        assert aws.devops.paginate_calls == [
            {
                "agentSpaceId": SPACE,
                "executionId": "exec-1",
                "recordType": "investigation_summary_md",
            }
        ]
        put = aws.table.put_item.call_args.kwargs
        assert put["Item"]["incident_id"] == "devops-finding#evt-1"
        assert put["Item"]["aiops_incident_id"] == INCIDENT
        assert put["Item"]["trigger"] == "unmatched"
        assert put["ConditionExpression"] == "attribute_not_exists(incident_id)"
        aws.table.update_item.assert_called_once()

    def test_audit_record_holds_metadata_only_and_expires(self, aws) -> None:
        handler.lambda_handler(_event(), None)
        item = aws.table.put_item.call_args.kwargs["Item"]
        assert "97% full" not in json.dumps(item, default=str)
        assert item["expiry_timestamp"] > item["created_at"]
        assert item["status"] == "processing"

    def test_selects_the_record_named_by_the_event_across_pages(self, aws) -> None:
        pages = [
            {"records": [{"recordId": "other-1", "content": "WRONG ONE"}]},
            {
                "records": [
                    {"recordId": "other-2", "content": "ALSO WRONG"},
                    {"recordId": "rec-1", "content": SUMMARY},
                ]
            },
        ]
        aws.install(FakeDevOps(pages_per_attempt=[pages]))
        handler.lambda_handler(_event(), None)
        text = _sent_email(aws)["Message"]["Body"]["Text"]["Data"]
        assert "97% full" in text and "WRONG" not in text

    def test_retries_when_the_record_lags_the_event(self, aws) -> None:
        late = [
            [{"records": []}],
            [{"records": [{"recordId": "rec-1", "content": SUMMARY}]}],
        ]
        aws.install(FakeDevOps(pages_per_attempt=late))
        result = handler.lambda_handler(_event(), None)
        assert result["has_summary"] is True
        assert len(aws.devops.paginate_calls) == 2
        handler._sleep.assert_called_once()

    def test_gives_up_after_a_few_attempts_and_still_notifies(self, aws) -> None:
        aws.install(FakeDevOps(pages_per_attempt=[[{"records": []}]]))
        result = handler.lambda_handler(_event(), None)
        assert result["has_summary"] is False
        assert len(aws.devops.summary_calls) == handler.SUMMARY_LOOKUP_ATTEMPTS
        assert len(aws.devops.result_calls) == handler.SUMMARY_LOOKUP_ATTEMPTS
        assert "no summary text" in _sent_email(aws)["Message"]["Body"]["Text"]["Data"]

    def test_event_without_summary_id_skips_the_journal_and_still_notifies(
        self, aws
    ) -> None:
        result = handler.lambda_handler(_event(record_id=None), None)
        assert result["has_summary"] is False
        assert aws.devops.summary_calls == []
        aws.ses.send_email.assert_called_once()

    def test_non_string_content_is_serialised(self, aws) -> None:
        pages = [
            {"records": [{"recordId": "rec-1", "content": {"finding": "disk full"}}]}
        ]
        aws.install(FakeDevOps(pages_per_attempt=[pages]))
        handler.lambda_handler(_event(), None)
        assert "disk full" in _sent_email(aws)["Message"]["Body"]["Text"]["Data"]


class TestInvestigationResultFallback:
    """When the agent writes no summary it may write an explanation instead (seen live)."""

    EXPLANATION = "I couldn't investigate: the instance in the alert does not exist."

    def _result_pages(self, content, created_at: int = 1):
        return [
            [
                {
                    "records": [
                        {
                            "recordId": "res-1",
                            "createdAt": created_at,
                            "content": content,
                        }
                    ]
                }
            ]
        ]

    def test_explanation_is_emailed_when_there_is_no_summary(self, aws) -> None:
        content = json.dumps({"type": "investigation_result", "text": self.EXPLANATION})
        aws.install(FakeDevOps(result_pages_per_attempt=self._result_pages(content)))

        result = handler.lambda_handler(_event(record_id=None), None)

        assert result["has_summary"] is False and result["has_result"] is True
        body = _sent_email(aws)["Message"]["Body"]
        assert self.EXPLANATION in body["Text"]["Data"]
        assert "could not complete a full investigation" in body["Text"]["Data"]
        assert "<h3>Explanation</h3>" in body["Html"]["Data"]
        assert aws.devops.result_calls[0]["recordType"] == "investigation_result"

    @pytest.mark.parametrize(
        "content",
        [
            json.dumps({"type": "investigation_result", "text": EXPLANATION}),
            {"type": "investigation_result", "text": EXPLANATION},
            EXPLANATION,
        ],
    )
    def test_content_shapes(self, aws, content) -> None:
        aws.install(FakeDevOps(result_pages_per_attempt=self._result_pages(content)))
        handler.lambda_handler(_event(record_id=None), None)
        assert self.EXPLANATION in _sent_email(aws)["Message"]["Body"]["Text"]["Data"]

    def test_uses_the_newest_result(self, aws) -> None:
        pages = [
            [
                {
                    "recordId": "old",
                    "createdAt": 1,
                    "content": json.dumps({"text": "OLD"}),
                },
                {
                    "recordId": "new",
                    "createdAt": 9,
                    "content": json.dumps({"text": "NEWEST"}),
                },
                {
                    "recordId": "mid",
                    "createdAt": 5,
                    "content": json.dumps({"text": "MIDDLE"}),
                },
            ]
        ]
        aws.install(FakeDevOps(result_pages_per_attempt=[[{"records": pages[0]}]]))
        handler.lambda_handler(_event(record_id=None), None)
        text = _sent_email(aws)["Message"]["Body"]["Text"]["Data"]
        assert "NEWEST" in text and "OLD" not in text and "MIDDLE" not in text

    def test_retries_when_the_result_lags_the_event(self, aws) -> None:
        content = json.dumps({"text": self.EXPLANATION})
        late = [[{"records": []}], self._result_pages(content)[0]]
        aws.install(FakeDevOps(result_pages_per_attempt=late))
        assert (
            handler.lambda_handler(_event(record_id=None), None)["has_result"] is True
        )
        assert len(aws.devops.result_calls) == 2

    def test_a_missing_summary_record_also_falls_back_to_the_explanation(
        self, aws
    ) -> None:
        content = json.dumps({"text": self.EXPLANATION})
        aws.install(
            FakeDevOps(
                pages_per_attempt=[[{"records": []}]],
                result_pages_per_attempt=self._result_pages(content),
            )
        )
        result = handler.lambda_handler(_event(record_id="rec-missing"), None)
        assert result["has_summary"] is False and result["has_result"] is True

    def test_not_fetched_when_a_summary_exists_or_for_failed_events(self, aws) -> None:
        handler.lambda_handler(_event(), None)
        assert aws.devops.result_calls == []
        aws.ses.reset_mock()
        handler.lambda_handler(
            _event("Investigation Failed", record_id=None, event_id="evt-2"), None
        )
        assert aws.devops.result_calls == []

    def test_explanation_is_escaped_and_not_logged(self, aws, caplog) -> None:
        evil = json.dumps({"text": "<img src=x onerror=alert(1)> SECRET-EXPLANATION"})
        aws.install(FakeDevOps(result_pages_per_attempt=self._result_pages(evil)))
        with caplog.at_level(logging.INFO):
            handler.lambda_handler(_event(record_id=None), None)
        page = _sent_email(aws)["Message"]["Body"]["Html"]["Data"]
        assert "<img" not in page and "&lt;img" in page
        assert "SECRET-EXPLANATION" not in caplog.text


class TestUntrustedText:
    def test_summary_is_html_escaped(self, aws) -> None:
        evil = (
            '<script>alert(1)</script> <a href="https://evil.example">click</a> & more'
        )
        aws.install(
            FakeDevOps(
                pages_per_attempt=[
                    [{"records": [{"recordId": "rec-1", "content": evil}]}]
                ]
            )
        )
        handler.lambda_handler(_event(), None)
        page = _sent_email(aws)["Message"]["Body"]["Html"]["Data"]
        assert "<script>" not in page and '<a href="https://evil.example">' not in page
        assert "&lt;script&gt;" in page and "&amp; more" in page

    def test_title_cannot_inject_headers_or_markup(self, aws) -> None:
        task = _task(title="Disk\r\nBcc: attacker@example.com <b>x</b>")
        aws.install(FakeDevOps(tasks={"task-1": task}))
        handler.lambda_handler(_event(), None)
        mail = _sent_email(aws)
        assert "\n" not in mail["Message"]["Subject"]["Data"]
        assert "\r" not in mail["Message"]["Subject"]["Data"]
        assert "<b>" not in mail["Message"]["Body"]["Html"]["Data"]

    def test_long_summary_is_truncated(self, aws) -> None:
        long = "x" * 50000
        aws.install(
            FakeDevOps(
                pages_per_attempt=[
                    [{"records": [{"recordId": "rec-1", "content": long}]}]
                ]
            )
        )
        handler.lambda_handler(_event(), None)
        text = _sent_email(aws)["Message"]["Body"]["Text"]["Data"]
        assert len(text) < handler.MAX_SUMMARY_CHARS + 1000
        assert "truncated" in text

    def test_logs_never_contain_the_summary_text(self, aws, caplog) -> None:
        with caplog.at_level(logging.INFO):
            handler.lambda_handler(_event(), None)
        assert "97% full" not in caplog.text
        assert INCIDENT in caplog.text

    def test_web_link_is_only_built_for_a_well_formed_space_id(self, aws) -> None:
        assert handler._web_app_url(SPACE) == f"https://{SPACE}.aidevops.global.app.aws"
        assert handler._web_app_url('x"><script>') == ""
        assert handler._web_app_url("") == ""


class TestOtherDetailTypes:
    @pytest.mark.parametrize(
        ("detail_type", "phrase"),
        [("Investigation Failed", "FAILED"), ("Investigation Timed Out", "TIMED OUT")],
    )
    def test_failed_and_timed_out_send_a_short_notice(
        self, aws, detail_type, phrase
    ) -> None:
        result = handler.lambda_handler(
            _event(detail_type, record_id=None, status="FAILED"), None
        )
        assert result["status"] == "sent"
        assert phrase in _sent_email(aws)["Message"]["Body"]["Text"]["Data"]
        assert aws.devops.paginate_calls == []

    def test_linked_names_the_primary_investigation(self, aws) -> None:
        primary_ref = "aiops-9999-critical"
        tasks = {
            "task-1": _task(primaryTaskId="task-0"),
            "task-0": _task("task-0", reference=primary_ref),
        }
        aws.install(FakeDevOps(tasks=tasks))
        handler.lambda_handler(
            _event("Investigation Linked", record_id=None, status="LINKED"), None
        )
        text = _sent_email(aws)["Message"]["Body"]["Text"]["Data"]
        assert "grouped" in text and primary_ref in text

    def test_linked_still_notifies_if_the_primary_cannot_be_read(self, aws) -> None:
        tasks = {"task-1": _task(primaryTaskId="task-0")}
        errors = {"task-0": _error("ThrottlingException")}
        aws.install(FakeDevOps(tasks=tasks, errors=errors))
        result = handler.lambda_handler(
            _event("Investigation Linked", record_id=None), None
        )
        assert result["status"] == "sent"

    def test_unrelated_detail_types_are_ignored(self, aws) -> None:
        for detail_type in (
            "Investigation Created",
            "Mitigation Completed",
            "Something Else",
        ):
            assert (
                handler.lambda_handler(_event(detail_type), None)["status"] == "ignored"
            )
        aws.ses.send_email.assert_not_called()
        aws.table.put_item.assert_not_called()


class TestOwnership:
    def test_non_aiops_investigations_are_ignored(self, aws) -> None:
        aws.install(FakeDevOps(tasks={"task-1": _task(reference="INC0012345")}))
        result = handler.lambda_handler(_event(), None)
        assert result == {"status": "ignored", "reason": "not an AIOps incident"}
        aws.ses.send_email.assert_not_called()
        aws.table.put_item.assert_not_called()

    def test_task_without_a_reference_is_ignored(self, aws) -> None:
        aws.install(
            FakeDevOps(tasks={"task-1": {"taskId": "task-1", "title": "manual"}})
        )
        assert handler.lambda_handler(_event(), None)["status"] == "ignored"

    @pytest.mark.parametrize(
        "code", ["AccessDeniedException", "ResourceNotFoundException"]
    )
    def test_other_projects_spaces_or_missing_tasks_are_ignored(
        self, aws, code
    ) -> None:
        aws.install(FakeDevOps(errors={"task-1": _error(code)}))
        assert handler.lambda_handler(_event(), None) == {
            "status": "ignored",
            "reason": "task not readable",
        }
        aws.ses.send_email.assert_not_called()

    def test_transient_errors_are_raised_so_lambda_retries(self, aws) -> None:
        aws.install(FakeDevOps(errors={"task-1": _error("ThrottlingException")}))
        with pytest.raises(ClientError):
            handler.lambda_handler(_event(), None)

    def test_events_without_ids_are_ignored(self, aws) -> None:
        event = _event()
        del event["detail"]["metadata"]["task_id"]
        assert handler.lambda_handler(event, None)["status"] == "ignored"

    @pytest.mark.parametrize(
        ("reference", "incident", "trigger"),
        [
            (f"aiops-{INCIDENT}-critical", INCIDENT, "critical"),
            ("aiops-inc-with-dashes-1-failed", "inc-with-dashes-1", "failed"),
            ("aiops-x-resolved", "x", "resolved"),
        ],
    )
    def test_reference_parsing(self, reference, incident, trigger) -> None:
        match = handler.REFERENCE_RE.match(reference)
        assert match and match["incident"] == incident and match["trigger"] == trigger

    @pytest.mark.parametrize(
        "reference",
        ["INC001", "aiops--unmatched", "aiops-abc-other", "xaiops-a-failed"],
    )
    def test_reference_rejects_foreign_formats(self, reference) -> None:
        assert handler.REFERENCE_RE.match(reference) is None


class TestIdempotency:
    @staticmethod
    def _already_recorded(aws, status: str) -> None:
        aws.table.put_item.side_effect = _error(
            "ConditionalCheckFailedException", "PutItem"
        )
        aws.table.get_item.return_value = {"Item": {"status": status}}

    def test_duplicate_delivery_sends_nothing(self, aws) -> None:
        self._already_recorded(aws, "sent")
        result = handler.lambda_handler(_event(), None)
        assert result["status"] == "duplicate"
        aws.ses.send_email.assert_not_called()
        aws.table.update_item.assert_not_called()

    def test_a_previous_failed_attempt_is_retried(self, aws) -> None:
        self._already_recorded(aws, "processing")
        assert handler.lambda_handler(_event(), None)["status"] == "sent"
        aws.ses.send_email.assert_called_once()

    def test_email_failure_raises_and_is_not_marked_sent(self, aws) -> None:
        aws.ses.send_email.side_effect = _error("MessageRejected", "SendEmail")
        with pytest.raises(ClientError):
            handler.lambda_handler(_event(), None)
        aws.table.update_item.assert_not_called()

    def test_unexpected_dynamodb_errors_are_raised(self, aws) -> None:
        aws.table.put_item.side_effect = _error(
            "ProvisionedThroughputExceededException", "PutItem"
        )
        with pytest.raises(ClientError):
            handler.lambda_handler(_event(), None)
        aws.ses.send_email.assert_not_called()


def test_handled_types_match_the_cdk_rule() -> None:
    """The EventBridge rule and the handler must list the same detail types."""
    from src.agentic_ai.infra.constructs.devops_agent_findings import (
        FINDINGS_DETAIL_TYPES,
    )

    assert set(FINDINGS_DETAIL_TYPES) == set(handler.HANDLED_DETAIL_TYPES)
