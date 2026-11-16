"""Deliver AWS DevOps Agent investigation findings to the operator.

Triggered by EventBridge (source ``aws.aidevops``) when an investigation reaches
a terminal state. The event carries identifiers only, so this function:

1. reads the task (``GetBacklogTask``) to recover our incident reference
   ``aiops-<incident_id>-<trigger>`` that the webhook forwarder sent,
2. reads the investigation summary (``ListJournalRecords``),
3. records the delivery in DynamoDB (idempotency + metadata audit, no summary text),
4. emails the operator through SES.

It never executes anything and never changes any AWS resource other than its own
audit record. The summary is untrusted text (it is derived from alert content), so
it is HTML-escaped, truncated and never rendered as links or run.

This module is packaged on its own: it may import only the standard library and
boto3, not other modules from this repository.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Detail types we act on. The EventBridge rule filters on the same list; this is a
# second check so a misconfigured rule can never email on unrelated events.
HANDLED_DETAIL_TYPES = frozenset(
    {
        "Investigation Completed",
        "Investigation Failed",
        "Investigation Timed Out",
        "Investigation Linked",
    }
)

# Incident reference sent by src/devops_agent.py: aiops-<incident_id>-<trigger>
REFERENCE_RE = re.compile(
    r"^aiops-(?P<incident>.+)-(?P<trigger>unmatched|failed|critical|resolved)$"
)
_SPACE_ID_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

INVESTIGATION_SUMMARY = "investigation_summary_md"
# Written instead of a summary when the agent could not run a real investigation
# (for example the host in the alert does not exist). Plain explanatory text.
INVESTIGATION_RESULT = "investigation_result"
MAX_SUMMARY_CHARS = 6000
MAX_TITLE_CHARS = 150
SUMMARY_LOOKUP_ATTEMPTS = 3
SUMMARY_LOOKUP_DELAY_SECONDS = 2.0
RECORD_TTL_DAYS = 90

# Dedicated PK namespace: never collides with incident, approval or lock items that
# live in the same table and are queried by incident_id.
RECORD_PK_PREFIX = "devops-finding#"
RECORD_SK = "finding"

_CLIENT_CONFIG = Config(
    connect_timeout=5,
    read_timeout=15,
    retries={"max_attempts": 3, "mode": "standard"},
)

# Errors that mean "this task is not ours / not readable": skip quietly, do not retry.
_IGNORABLE_CODES = frozenset({"AccessDeniedException", "ResourceNotFoundException"})

_sleep = time.sleep  # patched in tests
_clients: dict[str, Any] = {}


def _log(level: int, message: str, **fields: Any) -> None:
    """Emit one structured JSON log line. Never include summary text or secrets."""
    logger.log(level, json.dumps({"message": message, **fields}, default=str))


def _client(name: str, region: Optional[str] = None) -> Any:
    """Return a cached boto3 client with explicit timeouts and retries."""
    key = f"{name}:{region or ''}"
    if key not in _clients:
        _clients[key] = boto3.client(
            name, region_name=region or None, config=_CLIENT_CONFIG
        )
    return _clients[key]


def _table() -> Any:
    if "table" not in _clients:
        _clients["table"] = boto3.resource("dynamodb", config=_CLIENT_CONFIG).Table(
            os.environ["TABLE_NAME"]
        )
    return _clients["table"]


def _one_line(value: object, limit: int) -> str:
    """Single-line, control-character-free text (safe for subjects and headers)."""
    text = " ".join(_CONTROL_CHARS.sub(" ", str(value)).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return (
        text[:limit].rstrip()
        + "\n\n[truncated; open the DevOps Agent web app for the full text]"
    )


def _error_code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code", ""))


def _get_task(space_id: str, task_id: str, region: Optional[str]) -> Optional[dict]:
    """Read a task; None if it is not readable (other project's space, or gone)."""
    try:
        response = _client("devops-agent", region).get_backlog_task(
            agentSpaceId=space_id, taskId=task_id
        )
    except ClientError as e:
        if _error_code(e) in _IGNORABLE_CODES:
            _log(
                logging.INFO,
                "task not readable; ignoring event",
                agent_space_id=space_id,
                task_id=task_id,
                error_code=_error_code(e),
            )
            return None
        raise
    return response.get("task") or {}


def _fetch_summary(
    space_id: str,
    execution_id: str,
    summary_record_id: Optional[str],
    region: Optional[str],
) -> Optional[str]:
    """Return the investigation summary text, or None if there is none.

    An execution can hold several summary records, so select the one named by
    the event. The record can lag the event briefly, so retry a few times.
    """
    if not (summary_record_id and execution_id):
        return None
    client = _client("devops-agent", region)
    for attempt in range(SUMMARY_LOOKUP_ATTEMPTS):
        paginator = client.get_paginator("list_journal_records")
        pages = paginator.paginate(
            agentSpaceId=space_id,
            executionId=execution_id,
            recordType=INVESTIGATION_SUMMARY,
        )
        for page in pages:
            for record in page.get("records", []):
                if record.get("recordId") == summary_record_id:
                    content = record.get("content")
                    return (
                        content
                        if isinstance(content, str)
                        else json.dumps(content, indent=1)
                    )
        if attempt < SUMMARY_LOOKUP_ATTEMPTS - 1:
            _sleep(SUMMARY_LOOKUP_DELAY_SECONDS)
    return None


def _result_text(content: Any) -> str:
    """Extract the explanation from an ``investigation_result`` record's content."""
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except ValueError:
            return content
        content = parsed if isinstance(parsed, (dict, str)) else content
        if isinstance(content, str):
            return content
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return content["text"]
    return json.dumps(content, indent=1)


def _fetch_result(
    space_id: str, execution_id: str, region: Optional[str]
) -> Optional[str]:
    """Return the agent's explanation when it wrote no summary, or None.

    The newest ``investigation_result`` record is used. Retried briefly because the
    record can lag the event.
    """
    if not execution_id:
        return None
    client = _client("devops-agent", region)
    for attempt in range(SUMMARY_LOOKUP_ATTEMPTS):
        records: list[dict] = []
        pages = client.get_paginator("list_journal_records").paginate(
            agentSpaceId=space_id,
            executionId=execution_id,
            recordType=INVESTIGATION_RESULT,
        )
        for page in pages:
            records.extend(page.get("records", []))
        if records:
            latest = max(records, key=lambda r: r.get("createdAt") or 0)
            return _result_text(latest.get("content"))
        if attempt < SUMMARY_LOOKUP_ATTEMPTS - 1:
            _sleep(SUMMARY_LOOKUP_DELAY_SECONDS)
    return None


def _claim(event_id: str, fields: dict[str, Any]) -> bool:
    """Record that we are handling this event. False if it was already delivered.

    EventBridge is at-least-once, so the same event can arrive twice. A previous
    attempt that failed before sending leaves status "processing", which is retried.
    """
    table = _table()
    now = int(time.time())
    item = {
        "incident_id": f"{RECORD_PK_PREFIX}{event_id}",
        "timestamp": RECORD_SK,
        "status": "processing",
        "created_at": now,
        "expiry_timestamp": now + RECORD_TTL_DAYS * 86400,
        **{k: v for k, v in fields.items() if v},
    }
    try:
        table.put_item(
            Item=item, ConditionExpression="attribute_not_exists(incident_id)"
        )
        return True
    except ClientError as e:
        if _error_code(e) != "ConditionalCheckFailedException":
            raise
    existing = table.get_item(
        Key={"incident_id": item["incident_id"], "timestamp": RECORD_SK},
        ConsistentRead=True,
    ).get("Item", {})
    return existing.get("status") != "sent"


def _mark_sent(event_id: str) -> None:
    _table().update_item(
        Key={"incident_id": f"{RECORD_PK_PREFIX}{event_id}", "timestamp": RECORD_SK},
        UpdateExpression="SET #s = :sent, sent_at = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":sent": "sent", ":now": int(time.time())},
    )


def _web_app_url(space_id: str) -> str:
    """Operator web app URL (same pattern aiops_env.py uses); '' if the id looks wrong."""
    if not _SPACE_ID_RE.match(space_id or ""):
        return ""
    return f"https://{space_id}.aidevops.global.app.aws"


def build_message(
    *,
    detail_type: str,
    title: str,
    incident_id: str,
    trigger: str,
    priority: str,
    summary: Optional[str],
    primary_reference: str,
    web_app_url: str,
    result_text: Optional[str] = None,
) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body) for one finding. All values are escaped.

    ``result_text`` is the agent's explanation when it wrote no summary (for example
    the host in the alert does not exist). It is shown only if there is no summary.
    """
    status_line = {
        "Investigation Completed": "DevOps Agent finished investigating this incident.",
        "Investigation Failed": "The DevOps Agent investigation FAILED. No findings are available.",
        "Investigation Timed Out": "The DevOps Agent investigation TIMED OUT. No findings are available.",
        "Investigation Linked": (
            "DevOps Agent grouped this incident with another investigation"
            + (f" ({primary_reference})" if primary_reference else "")
            + ". Findings will be sent when that investigation completes."
        ),
    }[detail_type]

    section_title = "Findings"
    if detail_type == "Investigation Completed" and not summary:
        if result_text:
            section_title = "Explanation"
            status_line = (
                "DevOps Agent could not complete a full investigation of this incident. "
                "Its explanation is below."
            )
        else:
            status_line += (
                " It produced no summary text; open the web app to review the run."
            )
    subject = _one_line(f"[AIOps] DevOps Agent: {title or incident_id}", 200)
    shown = summary or result_text or ""
    body_text = _truncate(shown, MAX_SUMMARY_CHARS) if shown else ""

    text_lines = [
        status_line,
        "",
        f"Incident: {incident_id} (forwarded as: {trigger})",
        f"Priority: {priority or 'unknown'}",
    ]
    if web_app_url:
        text_lines.append(f"DevOps Agent web app: {web_app_url}")
    if body_text:
        text_lines += [
            "",
            f"--- {section_title} (generated by DevOps Agent; verify before acting) ---",
            body_text,
        ]
    text_lines += [
        "",
        "This message is informational. No action was taken automatically.",
    ]

    esc = html.escape
    link = (
        f'<p><a href="{esc(web_app_url, quote=True)}">Open the DevOps Agent web app</a></p>'
        if web_app_url
        else ""
    )
    findings = (
        f"<h3>{esc(section_title)}</h3>"
        '<p style="color:#6c757d;font-size:12px;">Generated by DevOps Agent from alert data. '
        "Verify before acting.</p>"
        '<pre style="white-space:pre-wrap;font-family:monospace;font-size:13px;'
        f'background:#f8f9fa;border:1px solid #dee2e6;border-radius:4px;padding:12px;">{esc(body_text)}</pre>'
        if body_text
        else ""
    )
    html_body = (
        '<html><body style="font-family:-apple-system,sans-serif;max-width:700px;margin:0 auto;'
        'padding:20px;">'
        f'<div style="border-left:4px solid #0d6efd;padding:12px 16px;background:#f8f9fa;">'
        f"<h2 style=\"margin:0 0 8px 0;\">{esc(title or incident_id)}</h2>"
        f'<p style="margin:0;">{esc(status_line)}</p></div>'
        f"<p>Incident: <code>{esc(incident_id)}</code> (forwarded as {esc(trigger)})<br>"
        f"Priority: <strong>{esc(priority or 'unknown')}</strong></p>"
        f"{link}{findings}"
        '<hr><p style="color:#6c757d;font-size:12px;">This message is informational. '
        "No action was taken automatically.</p></body></html>"
    )
    return subject, "\n".join(text_lines), html_body


def _send_email(subject: str, text_body: str, html_body: str) -> None:
    _client("ses").send_email(
        Source=os.environ["SES_FROM_ADDRESS"],
        Destination={"ToAddresses": [os.environ["OPERATOR_EMAIL"]]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text_body, "Charset": "UTF-8"},
                "Html": {"Data": html_body, "Charset": "UTF-8"},
            },
        },
    )


def _primary_reference(task: dict, space_id: str, region: Optional[str]) -> str:
    """Reference of the investigation this task was linked to ('' if unknown)."""
    primary_id = task.get("primaryTaskId")
    if not primary_id or primary_id == task.get("taskId"):
        return ""
    try:
        primary = _get_task(space_id, primary_id, region) or {}
    except ClientError as e:  # a missing hint must not block the notice
        _log(logging.WARNING, "could not read primary task", error_code=_error_code(e))
        return ""
    return _one_line((primary.get("reference") or {}).get("referenceId", ""), 120)


def lambda_handler(event: dict, context: Any) -> dict:
    """EventBridge entry point. Raises on transient failures so Lambda retries."""
    detail_type = event.get("detail-type")
    if detail_type not in HANDLED_DETAIL_TYPES:
        _log(logging.INFO, "ignored event type", detail_type=detail_type)
        return {"status": "ignored", "reason": "detail-type"}

    detail = event.get("detail") or {}
    metadata = detail.get("metadata") or {}
    data = detail.get("data") or {}
    space_id = metadata.get("agent_space_id")
    task_id = metadata.get("task_id")
    if not space_id or not task_id:
        _log(
            logging.WARNING,
            "event without agent space or task id",
            detail_type=detail_type,
        )
        return {"status": "ignored", "reason": "missing ids"}
    region = event.get("region")
    event_id = (
        event.get("id") or f"{task_id}:{detail_type}:{data.get('updated_at', '')}"
    )

    task = _get_task(space_id, task_id, region)
    if task is None:
        return {"status": "ignored", "reason": "task not readable"}

    reference = (task.get("reference") or {}).get("referenceId", "")
    match = REFERENCE_RE.match(reference)
    if not match:
        _log(logging.INFO, "not an AIOps incident; ignoring", task_id=task_id)
        return {"status": "ignored", "reason": "not an AIOps incident"}
    incident_id, trigger = match.group("incident"), match.group("trigger")

    audit = {
        "aiops_incident_id": incident_id,
        "trigger": trigger,
        "detail_type": detail_type,
        "agent_space_id": space_id,
        "task_id": task_id,
        "execution_id": metadata.get("execution_id"),
        "summary_record_id": data.get("summary_record_id"),
        "task_status": data.get("status"),
    }
    if not _claim(event_id, audit):
        _log(
            logging.INFO, "duplicate event; already delivered", incident_id=incident_id
        )
        return {"status": "duplicate", "incident_id": incident_id}

    summary = None
    result_text = None
    if detail_type == "Investigation Completed":
        execution_id = metadata.get("execution_id", "")
        summary = _fetch_summary(
            space_id, execution_id, data.get("summary_record_id"), region
        )
        if not summary:
            # No summary: the agent may have explained why it could not investigate.
            result_text = _fetch_result(space_id, execution_id, region)
    primary_reference = (
        _primary_reference(task, space_id, region)
        if detail_type == "Investigation Linked"
        else ""
    )

    subject, text_body, html_body = build_message(
        detail_type=detail_type,
        title=_one_line(task.get("title", ""), MAX_TITLE_CHARS),
        incident_id=_one_line(incident_id, 100),
        trigger=trigger,
        priority=_one_line(data.get("priority") or task.get("priority") or "", 20),
        summary=summary,
        primary_reference=primary_reference,
        web_app_url=_web_app_url(space_id),
        result_text=result_text,
    )
    _send_email(subject, text_body, html_body)
    _mark_sent(event_id)
    _log(
        logging.INFO,
        "finding delivered",
        incident_id=incident_id,
        detail_type=detail_type,
        has_summary=bool(summary),
        has_result=bool(result_text),
        summary_chars=len(summary or ""),
    )
    return {
        "status": "sent",
        "incident_id": incident_id,
        "has_summary": bool(summary),
        "has_result": bool(result_text),
    }
