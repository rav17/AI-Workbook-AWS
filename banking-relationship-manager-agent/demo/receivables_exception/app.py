from __future__ import annotations

import time
from collections.abc import Callable
from html import escape
from pathlib import Path
from tempfile import gettempdir
from typing import Any
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from aria.agents.aria.receivables.engine import LogicalDemoClock, ReceivablesInvestigationEngine
from aria.agents.aria.receivables.models import (
    DecisionKind,
    InvestigationProposal,
    MockCaseTaskPayload,
    TrustedContext,
)
from aria.agents.aria.receivables.trusted_context import synthetic_harness_context
from demo.receivables_exception.adapters import FixtureReadOnlyAdapter
from demo.receivables_exception.service import ReceivablesWorkflowService
from demo.receivables_exception.store import LocalSQLiteStore, StoreError

MAX_FORM_BYTES = 4_000


def render_proposal(
    proposal: InvestigationProposal | None,
    *,
    confirmation_id: str | None = None,
    payload: MockCaseTaskPayload | None = None,
    payload_hash: str | None = None,
    proposal_version: int | None = None,
    message: str = "",
) -> str:
    if proposal is None:
        body = """<h1>Receivables exception review</h1>
<p role="status" aria-live="polite">Ready</p>
<form method="post" action="/investigate">
<h2>Start investigation</h2>
<label for="payment-id">Synthetic payment identifier</label>
<input id="payment-id" name="payment_id" required
 pattern="PAY-SYN-[A-Z0-9]{3,8}" maxlength="20">
<label for="exception-type">Exception category</label>
<select id="exception-type" name="exception_type">
<option value="invalid_mapping">Invalid mapping</option>
<option value="amount_reference_mismatch">Amount/reference mismatch</option>
<option value="suspected_duplicate">Suspected duplicate</option>
</select><button type="submit">Investigate</button></form>"""
    else:
        status = escape(proposal.outcome.value.replace("_", " ").title())
        statuses = "".join(
            f"<li><strong>{escape(item.source_type.value)}</strong>: "
            f"{escape(item.availability.value)}, {escape(item.freshness.value)} "
            f"{escape(item.safe_detail or '')}</li>"
            for item in proposal.evidence_statuses
        )
        facts = "".join(
            f"<li><strong>{escape(item.source_type.value)} record</strong>: "
            f"{escape(item.source_record_id)} ? {escape(item.classification.value)}; "
            f"{escape(item.availability.value)}, {escape(item.freshness.value)}</li>"
            for item in proposal.evidence
        )
        candidates = "".join(
            f"<li>{escape(item.invoice_id)}: score {item.score}; {escape(item.band)}; "
            f"variance {item.variance}; eligible {str(item.eligible).lower()}</li>"
            for item in proposal.candidates
        )
        choices = (
            '<button aria-label="Approve current proposal" name="decision" '
            'value="approve">Approve proposal</button>'
            if proposal.outcome.value == "recommend"
            else ""
        )
        controls = f"""
<section aria-labelledby="decision-heading">
<h2 id="decision-heading">Analyst decision</h2>
<form method="post" action="/decision">
<input type="hidden" name="proposal_id" value="{escape(proposal.proposal_id)}">
<label for="rationale">Rationale (optional)</label>
<textarea id="rationale" name="rationale" maxlength="500"></textarea>
{choices}
<button aria-label="Revise current proposal" name="decision"
 value="revise">Revise proposal</button>
<button aria-label="Reject current proposal" name="decision"
 value="reject">Reject proposal</button>
<button aria-label="Escalate current proposal" name="decision"
 value="escalate">Escalate proposal</button>
</form></section>"""
        task = ""
        if (
            payload is not None
            and confirmation_id
            and payload_hash
            and proposal_version is not None
        ):
            task_fields = "".join(
                f"<li><strong>{escape(key)}</strong>: {escape(str(value))}</li>"
                for key, value in payload.model_dump(mode="json").items()
            )
            task = f"""
<section aria-labelledby="payload-heading">
<h2 id="payload-heading">Exact immutable task payload</h2>
<ul>{task_fields}</ul>
<p>No task exists before this explicit confirmation.</p>
<p>Proposal version: {proposal_version}. Confirmation payload SHA-256:
<code>{escape(payload_hash)}</code></p>
<form method="post" action="/confirm">
<input type="hidden" name="confirmation_id" value="{escape(confirmation_id)}">
<input type="hidden" name="payload_hash" value="{escape(payload_hash)}">
<input type="hidden" name="proposal_version" value="{proposal_version}">
<button type="submit" aria-label="Confirm displayed synthetic task">
Confirm displayed task</button></form></section>"""
        body = f"""<h1>Receivables exception review</h1>
<p id="status" role="status" aria-live="polite" aria-busy="false">
Status: {status}. {escape(message)}</p>
<section aria-labelledby="facts-heading">
<h2 id="facts-heading">Evidence and facts</h2><ul>{facts}{statuses}</ul></section>
<section aria-labelledby="candidate-heading">
<h2 id="candidate-heading">Candidates and inference</h2>
<ul>{candidates}</ul><p>{escape(proposal.draft_operations_note)}</p>
<p>{escape(proposal.safe_next_step or "")}</p></section>{controls}{task}
<form method="post" action="/investigate">
<label for="new-payment-id">Another synthetic payment identifier</label>
<input id="new-payment-id" name="payment_id" required
 pattern="PAY-SYN-[A-Z0-9]{{3,8}}" maxlength="20">
<input type="hidden" name="exception_type" value="amount_reference_mismatch">
<button type="submit">Investigate another payment</button></form>"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Receivables exception review</title>
<style>button:focus,input:focus,select:focus,textarea:focus {{
outline: 3px solid #111; outline-offset: 2px; }}</style></head>
<body><main>{body}
<p role="alert" aria-live="assertive">
{escape(message) if message.startswith("Error:") else ""}</p>
<p>Failed or uncertain writes are unconfirmed, never successful; safely retry the same
confirmation.</p>
<script>document.querySelectorAll('form').forEach(form => form.addEventListener('submit', () => {{
const status = document.querySelector('[role="status"]');
if (status) {{ status.textContent = 'Loading synthetic investigation or workflow result';
status.setAttribute('aria-busy', 'true'); }}
}}));</script></main></body></html>"""


def local_demo_status(result: dict[str, Any]) -> str:
    if result.get("status") in {"created", "replayed"}:
        return "Synthetic mock task confirmed."
    return "No success is claimed. Check local status and retry the same confirmation if needed."


def create_wsgi_app(
    service: ReceivablesWorkflowService, context: TrustedContext
) -> Callable[[dict[str, Any], Callable[..., Any]], list[bytes]]:
    def app(environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        proposal: InvestigationProposal | None = None
        message = ""
        payload = None
        payload_hash = None
        proposal_version = None
        confirmation_id = None
        try:
            if method == "POST":
                try:
                    length = int(environ.get("CONTENT_LENGTH") or "0")
                except ValueError:
                    length = MAX_FORM_BYTES + 1
                if length > MAX_FORM_BYTES:
                    raise ValueError("form exceeds bounded limit")
                raw = environ["wsgi.input"].read(length) if length else b""
                form = parse_qs(raw.decode("utf-8", errors="strict"), keep_blank_values=True)
                if any(
                    key in form
                    for key in (
                        "tenant_id",
                        "user_id",
                        "session_id",
                        "analyst_id",
                        "analyst_role",
                        "_verified_principal",
                    )
                ):
                    raise ValueError("identity must come from the trusted local harness")
                if path == "/investigate":
                    proposal = service.investigate(
                        context,
                        form.get("payment_id", [""])[0],
                        form.get("exception_type", [""])[0],
                    )
                elif path == "/decision":
                    proposal_id = form.get("proposal_id", [""])[0]
                    decision = DecisionKind(form.get("decision", [""])[0])
                    result = service.decide(
                        context, proposal_id, decision, form.get("rationale", [""])[0]
                    )
                    proposal = result.get("proposal") or service.store.get_proposal(
                        context, proposal_id
                    )
                    if decision == DecisionKind.APPROVE:
                        confirmation_id = result["confirmation_id"]
                        payload = result["payload"]
                        payload_hash = result["payload_hash"]
                        proposal_version = result["proposal_version"]
                        message = "Approval recorded. Review this exact payload before confirming."
                    else:
                        message = f"Decision recorded: {decision.value}. No mock task was created."
                        if result.get("proposal"):
                            proposal = result["proposal"]
                elif path == "/confirm":
                    confirmation_id = form.get("confirmation_id", [""])[0]
                    try:
                        displayed_version = int(form.get("proposal_version", [""])[0])
                    except ValueError:
                        displayed_version = None
                    result = service.confirm(
                        context,
                        confirmation_id,
                        form.get("payload_hash", [""])[0],
                        displayed_version,
                    )
                    message = local_demo_status(result)
                    binding = service.store.get_binding(context, confirmation_id)
                    proposal = (
                        service.store.get_proposal(context, binding["proposal_id"])
                        if binding
                        else None
                    )
                    if result.get("status") not in {"created", "replayed"}:
                        message = "Unconfirmed; no success is claimed. " + str(
                            result.get("safe_next_step", "Check local task status.")
                        )
                else:
                    raise ValueError("unsupported local demo action")
            elif method != "GET":
                raise ValueError("unsupported method")
            else:
                values = parse_qs(environ.get("QUERY_STRING", ""))
                payment_id = values.get("payment_id", [""])[0]
                if payment_id:
                    proposal = service.store.get_current_proposal(
                        context, f"EXC-SYN-{payment_id.removeprefix('PAY-SYN-')}"
                    )
            body = render_proposal(
                proposal,
                confirmation_id=confirmation_id,
                payload=payload,
                payload_hash=payload_hash,
                proposal_version=proposal_version,
                message=message,
            )
            status = "200 OK"
        except (ValueError, StoreError, UnicodeDecodeError):
            body = render_proposal(
                proposal,
                message="Error: request not accepted; review the synthetic scope and try again.",
            )
            status = "400 Bad Request"
        encoded = body.encode("utf-8")
        start_response(
            status,
            [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(encoded)))],
        )
        return [encoded]

    return app


def serve_local(
    service: ReceivablesWorkflowService, context: TrustedContext, port: int = 8765
) -> None:
    with make_server("127.0.0.1", port, create_wsgi_app(service, context)) as server:
        server.serve_forever()


def main(
    *, store_path: Path | None = None, monotonic: Callable[[], float] = time.monotonic
) -> None:
    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001",
        user_id="local-analyst",
        session_id="local-demo",
        correlation_id="local-demo",
    )
    adapter = FixtureReadOnlyAdapter()
    logical_clock = LogicalDemoClock(adapter.catalogue.fixture["fixed_clock"], monotonic=monotonic)
    engine = ReceivablesInvestigationEngine(adapter, adapter.catalogue, logical_clock)
    store = LocalSQLiteStore(
        store_path or Path(gettempdir()) / "aria-receivables-synthetic-demo.sqlite3"
    )
    serve_local(ReceivablesWorkflowService(engine, store), context)


if __name__ == "__main__":
    main()
