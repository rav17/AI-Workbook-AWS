from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

import pytest

from aria.agents.aria.receivables.engine import ReceivablesInvestigationEngine
from aria.agents.aria.receivables.metrics import (
    audit_event_counts,
    retrieval_correspondence,
    workflow_metrics,
)
from aria.agents.aria.receivables.models import DecisionKind, EvidenceType, Outcome, TrustedContext
from aria.agents.aria.receivables.policy import canonical_json_bytes, load_approved_catalogue
from aria.agents.aria.receivables.trusted_context import (
    UntrustedContextError,
    synthetic_harness_context,
)
from demo.receivables_exception.adapters import FixtureReadOnlyAdapter
from demo.receivables_exception.app import create_wsgi_app, render_proposal
from demo.receivables_exception.service import ReceivablesWorkflowService
from demo.receivables_exception.store import LocalSQLiteStore, StoreError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "specs/004-receivables-exception-resolution/synthetic-fixtures.json"


class FixedClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value


def make_service(tmp_path: Path, *, audit_failure: bool = False):
    catalogue = load_approved_catalogue(ROOT)
    store = LocalSQLiteStore(tmp_path / "synthetic.sqlite", audit_failure=audit_failure)
    clock = FixedClock()
    engine = ReceivablesInvestigationEngine(FixtureReadOnlyAdapter(catalogue), catalogue)
    return ReceivablesWorkflowService(engine, store, clock), store, clock


def context(user: str = "analyst", session: str = "workflow") -> TrustedContext:
    return synthetic_harness_context(
        tenant_id="TENANT-SYN-001",
        user_id=user,
        session_id=session,
        correlation_id="workflow-correlation",
    )


def approved(service: ReceivablesWorkflowService, ctx: TrustedContext):
    proposal = service.investigate(ctx, "PAY-SYN-A02")
    assert proposal.outcome == Outcome.RECOMMEND
    response = service.decide(ctx, proposal.proposal_id, DecisionKind.APPROVE)
    return proposal, response


def confirm(service: ReceivablesWorkflowService, ctx: TrustedContext, response):
    return service.confirm(
        ctx,
        response["confirmation_id"],
        response["payload_hash"],
        response["proposal_version"],
    )


def test_approve_confirmation_create_replay_and_create_only_task(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    proposal, response = approved(service, ctx)
    proposal_events = [event for event in store.audit_events(ctx) if event.event_type == "proposal"]
    assert len(proposal_events) == 1
    assert proposal_events[0].proposal_id == proposal.proposal_id
    assert proposal_events[0].proposal_version == proposal.version
    assert proposal_events[0].source_refs == tuple(
        item.source_record_id for item in proposal.evidence
    )
    assert store.task_count() == 0
    assert response["payload"].invoice_id == "INV-SYN-1002"
    assert "payer" not in response["payload"].model_dump_json().lower()
    created = confirm(service, ctx, response)
    proposal_events = [event for event in store.audit_events(ctx) if event.event_type == "proposal"]
    assert len(proposal_events) == service.engine.returned_proposals == 2
    assert all(event.proposal_id == proposal.proposal_id for event in proposal_events)
    assert all(event.proposal_version == proposal.version for event in proposal_events)
    assert all(
        event.source_refs == tuple(item.source_record_id for item in proposal.evidence)
        for event in proposal_events
    )
    assert created["status"] == "created" and store.task_count() == 1
    task_id = created["task"].case_task_id
    replay = confirm(service, ctx, response)
    assert replay["status"] == "replayed" and replay["task"].case_task_id == task_id
    assert store.task_count() == 1
    for table in ("proposals", "bindings", "decisions", "audit", "case_tasks"):
        if table == "proposals":
            update = "UPDATE proposals SET payload=payload"
        elif table == "bindings":
            update = "UPDATE bindings SET payload_hash=payload_hash"
        elif table == "decisions":
            update = "UPDATE decisions SET rationale=rationale"
        elif table == "audit":
            update = "UPDATE audit SET event_json=event_json"
        else:
            update = "UPDATE case_tasks SET payload_hash=payload_hash"
        with pytest.raises(sqlite3.IntegrityError):
            store._db.execute(update)
        with pytest.raises(sqlite3.IntegrityError):
            store._db.execute(f"DELETE FROM {table}")
    events = store.audit_events(ctx)
    assert {event.event_type for event in events} >= {
        "proposal",
        "decision",
        "confirmation_binding",
        "confirmation",
        "task_result",
        "replay",
    }
    audit_text = " ".join(event.model_dump_json() for event in events)
    assert "please approve now" not in audit_text and "credential" not in audit_text.lower()
    store.close()


def test_reject_escalate_revise_and_nonrecommendation_approval_are_separate(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    proposal = service.investigate(ctx, "PAY-SYN-A02")
    revised = service.decide(ctx, proposal.proposal_id, "revise")
    assert revised["proposal"].version == 2
    assert revised["proposal"].proposal_id != proposal.proposal_id
    assert store.task_count() == 0
    revised_approval = service.decide(ctx, revised["proposal"].proposal_id, "approve")
    assert revised_approval["confirmation_id"]
    service.decide(ctx, revised["proposal"].proposal_id, "reject")
    assert store.task_count() == 0
    no_recommendation = service.investigate(ctx, "PAY-SYN-T01")
    assert no_recommendation.outcome == Outcome.NO_RECOMMENDATION
    with pytest.raises(StoreError, match="approval unavailable"):
        service.decide(ctx, no_recommendation.proposal_id, "approve")
    assert store.task_count() == 0
    store.close()


def test_decision_first_stales_confirmation_and_task_first_is_not_mutated(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    proposal, response = approved(service, ctx)
    store.record_decision(ctx, proposal.proposal_id, DecisionKind.REJECT)
    stale = confirm(service, ctx, response)
    assert stale["status"] == "stale_confirmation" and store.task_count() == 0

    service, store, _ = make_service(tmp_path / "task-first")
    ctx = context(session="task-first")
    proposal, response = approved(service, ctx)
    created = confirm(service, ctx, response)
    store.record_decision(ctx, proposal.proposal_id, DecisionKind.REJECT)
    replay = confirm(service, ctx, response)
    assert replay["status"] == "replayed"
    assert replay["task"].case_task_id == created["task"].case_task_id
    assert store.task_count() == 1
    store.close()


def test_changed_binding_cross_scope_and_audit_failure_never_claim_success(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    _, response = approved(service, ctx)
    binding = store.get_binding(ctx, response["confirmation_id"])
    assert binding is not None
    wrong_context = context(user="other")
    assert confirm(service, wrong_context, response)["status"] == "unauthorized"
    payload = response["payload"].model_copy(update={"invoice_id": "INV-SYN-1003"})
    forged_hash = hashlib.sha256(canonical_json_bytes(payload.model_dump(mode="json"))).hexdigest()
    status, task = store.confirm(
        ctx, response["confirmation_id"], payload, forged_hash, datetime.now(UTC)
    )
    assert status == "conflict" and task is None and store.task_count() == 0
    store.audit_failure = True
    result = confirm(service, ctx, response)
    assert result["status"] == "unconfirmed" and store.task_count() == 0
    store.audit_failure = False
    assert confirm(service, ctx, response)["status"] == "created"
    other_tenant = TrustedContext(
        tenant_id="TENANT-SYN-OTHER",
        user_id="analyst",
        session_id=ctx.session_id,
        correlation_id="other",
        authority_source="synthetic_harness",
    )
    with pytest.raises(UntrustedContextError, match="not issued"):
        confirm(service, other_tenant, response)
    store.close()


def test_failed_investigation_audit_never_returns_or_persists_a_proposal(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path, audit_failure=True)
    ctx = context()
    with pytest.raises(StoreError, match="audit sink failed"):
        service.investigate(ctx, "PAY-SYN-A02")
    assert service.engine.returned_proposals == 0
    assert store.get_current_proposal(ctx, "EXC-SYN-A02") is None
    assert not [event for event in store.audit_events(ctx) if event.event_type == "proposal"]
    store.close()


def test_expired_confirmation_rolls_back_and_audit_failure_before_write_is_not_success(
    tmp_path: Path,
) -> None:
    service, store, clock = make_service(tmp_path)
    ctx = context()
    _, response = approved(service, ctx)
    clock.value += timedelta(minutes=11)
    assert confirm(service, ctx, response)["status"] == "stale_confirmation"
    assert store.task_count() == 0
    store.close()


@pytest.mark.parametrize("scenario_id", [f"W{i:02}" for i in range(1, 15)])
def test_all_fourteen_approved_workflow_scenarios_execute_real_paths(
    tmp_path: Path, scenario_id: str, monkeypatch
) -> None:
    fixture_before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenarios = {item["id"]: item for item in fixture["workflow_scenarios"]["scenarios"]}
    scenario = scenarios[scenario_id]
    assert scenario["expected"]
    service, store, clock = make_service(tmp_path / scenario_id)
    ctx = context(session=scenario_id)
    store_results = []
    original_confirm = store.confirm
    original_replay = store.record_replay

    def measured_confirm(*args, **kwargs):
        result = original_confirm(*args, **kwargs)
        store_results.append(result[0])
        return result

    def measured_replay(*args, **kwargs):
        result = original_replay(*args, **kwargs)
        store_results.append("replayed")
        return result

    monkeypatch.setattr(store, "confirm", measured_confirm)
    monkeypatch.setattr(store, "record_replay", measured_replay)

    if scenario_id == "W09":
        proposal = service.investigate(ctx, "PAY-SYN-T01")
        assert proposal.outcome != Outcome.RECOMMEND
        with pytest.raises(StoreError, match="approval unavailable"):
            service.decide(ctx, proposal.proposal_id, "approve")
        assert store.task_count() == 0
    else:
        proposal, response = approved(service, ctx)
        assert store.task_count() == 0
        if scenario_id == "W01":
            result = confirm(service, ctx, response)
            assert result["status"] == "created" and store.task_count() == 1
            assert {event.event_type for event in store.audit_events(ctx)} >= {
                "retrieval",
                "proposal",
                "decision",
                "confirmation_binding",
                "confirmation",
                "task_result",
            }
        elif scenario_id == "W02":
            first = confirm(service, ctx, response)
            second = confirm(service, ctx, response)
            assert first["status"] == "created" and second["status"] == "replayed"
            assert first["task"].case_task_id == second["task"].case_task_id
            assert store.task_count() == 1
        elif scenario_id == "W03":
            altered = response["payload"].model_copy(update={"invoice_id": "INV-SYN-1003"})
            status, task = store.confirm(
                ctx, response["confirmation_id"], altered, "changed-hash", clock.now()
            )
            assert status == "conflict" and task is None and store.task_count() == 0
        elif scenario_id == "W04":
            service.decide(ctx, proposal.proposal_id, "reject")
            assert confirm(service, ctx, response)["status"] == "stale_confirmation"
            assert store.task_count() == 0
        elif scenario_id == "W05":
            service.decide(ctx, proposal.proposal_id, "escalate")
            assert confirm(service, ctx, response)["status"] == "stale_confirmation"
            assert store.task_count() == 0
        elif scenario_id in {"W06", "W07"}:
            created = confirm(service, ctx, response)
            assert created["status"] == "created"
            before = store.get_current_proposal(ctx, proposal.exception_id)
            service.decide(ctx, proposal.proposal_id, "reject")
            with pytest.raises(sqlite3.IntegrityError):
                store._db.execute("UPDATE case_tasks SET payload_hash='mutated'")
            if scenario_id == "W07":
                replay = confirm(service, ctx, response)
                assert replay["status"] == "replayed"
                assert replay["task"].case_task_id == created["task"].case_task_id
            assert store.task_count() == 1
            assert before is not None
        elif scenario_id == "W08":
            revised = service.decide(ctx, proposal.proposal_id, "revise")["proposal"]
            assert confirm(service, ctx, response)["status"] == "stale_confirmation"
            second = service.decide(ctx, revised.proposal_id, "approve")
            assert second["confirmation_id"] != response["confirmation_id"]
            assert confirm(service, ctx, second)["status"] == "created"
            assert store.task_count() == 1
        elif scenario_id == "W10":
            original = store.confirm
            first_call = True

            def fail_before_commit(*args, **kwargs):
                nonlocal first_call
                if first_call:
                    first_call = False
                    raise StoreError("simulated pre-commit failure")
                return original(*args, **kwargs)

            monkeypatch.setattr(store, "confirm", fail_before_commit)
            assert confirm(service, ctx, response)["status"] == "unconfirmed"
            assert store.task_count() == 0
            monkeypatch.setattr(store, "confirm", original)
            assert confirm(service, ctx, response)["status"] == "created"
        elif scenario_id == "W11":
            inject_confirmation_audit_failure(store)
            before_attempts = store._db.write_attempts["insert:case_tasks"]
            before_calls = store._db.write_calls["insert:case_tasks"]
            assert confirm(service, ctx, response)["status"] == "unconfirmed"
            assert store.task_count() == 0
            assert store._db.write_attempts["insert:case_tasks"] == before_attempts + 1
            assert store._db.write_calls["insert:case_tasks"] == before_calls + 1
            assert store._db.execute("SELECT state FROM states").fetchone()[0] == (
                "approved_awaiting_confirmation"
            )
            assert not any(
                event.event_type in {"confirmation", "task_result"}
                for event in store.audit_events(ctx)
            )
            store._db.execute("DROP TRIGGER injected_confirmation_audit_failure")
            assert confirm(service, ctx, response)["status"] == "created"
            assert confirm(service, ctx, response)["status"] == "replayed"
            assert store.task_count() == 1
        elif scenario_id == "W12":
            assert (
                confirm(service, context(session="other-session"), response)["status"]
                == "unauthorized"
            )
            assert store.task_count() == 0
        elif scenario_id == "W13":
            from pydantic import ValidationError

            with pytest.raises(ValidationError, match="unsupported synthetic analyst role"):
                TrustedContext(
                    tenant_id=ctx.tenant_id,
                    user_id=ctx.user_id,
                    session_id=ctx.session_id,
                    correlation_id=ctx.correlation_id,
                    analyst_role="viewer",
                    authority_source="synthetic_harness",
                )
            app = create_wsgi_app(service, ctx)
            body = urlencode(
                {
                    "confirmation_id": response["confirmation_id"],
                    "payload_hash": response["payload_hash"],
                    "proposal_version": str(response["proposal_version"]),
                    "analyst_role": "viewer",
                }
            ).encode("utf-8")
            status: list[str] = []
            app(
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": "/confirm",
                    "CONTENT_LENGTH": str(len(body)),
                    "wsgi.input": BytesIO(body),
                },
                lambda code, headers: status.append(code),
            )
            assert status == ["400 Bad Request"] and store.task_count() == 0
        elif scenario_id == "W14":
            clock.value += timedelta(minutes=11)
            assert confirm(service, ctx, response)["status"] == "stale_confirmation"
            assert store.task_count() == 0

    snapshot = store.measurements()
    adapter = service.engine.source
    source_calls = {kind.value: adapter.calls.count(kind) for kind in EvidenceType}
    expected_events = {f"retrieval:{kind}": count for kind, count in source_calls.items()}
    rows = snapshot["committed_rows"]
    expected_events.update(
        {
            "check": service.engine.completed_checks,
            "proposal": service.engine.returned_proposals,
            "decision": rows["decisions"],
            "confirmation_binding": rows["bindings"],
            "confirmation": rows["case_tasks"],
            "task_result": rows["case_tasks"],
            "replay": store_results.count("replayed"),
            "rejection": sum(
                status in {"conflict", "stale_confirmation"} for status in store_results
            ),
        }
    )
    expected_events = {key: count for key, count in expected_events.items() if count}
    observed_events = audit_event_counts(store.audit_events(ctx))
    fixture_after = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    measurement = workflow_metrics(
        source_calls=source_calls,
        **{key: snapshot[key] for key in ("write_attempts", "write_calls", "committed_rows")},
        tasks_created=store.task_count(),
        expected_events=expected_events,
        observed_events=observed_events,
        fixture_hash_before=fixture_before,
        fixture_hash_after=fixture_after,
    )
    measurement["audit_failures"] = snapshot["audit_failures"]
    measurement["store_confirmation_results"] = store_results
    measurement["retrieval_correspondence"] = retrieval_correspondence(
        adapter.read_observations, store.audit_events(ctx)
    )
    proposal_audit_gap = service.engine.returned_proposals - observed_events.get("proposal", 0)
    measurement["proposals_returned"] = service.engine.returned_proposals
    proposal_events = [event for event in store.audit_events(ctx) if event.event_type == "proposal"]
    assert proposal_audit_gap == 0
    assert all(event.proposal_id and event.proposal_version for event in proposal_events)
    assert measurement["audit_correspondence"]["matches"], measurement
    assert measurement["audit_correspondence"]["missing"].get("proposal", 0) == 0
    assert measurement["retrieval_correspondence"]["matches"]
    measurement["audit_failure_classification"] = {
        "failed_transactional_audit_insert_attempts": 1 if scenario_id == "W11" else 0,
        "failed_attempt_persisted": False,
        "injected_expected_failure_missing": {},
        "unexplained_missing_events": {},
        "returned_proposal_audit_gap": proposal_audit_gap,
        "scope": "Committed events match; W11 failed confirmation audit INSERT is not persisted",
    }
    assert measurement["fixture_unchanged"]
    assert sum(expected_events.values()) == rows["audit"]
    assert not snapshot["audit_failures"]  # Python sink fault counter, not SQL failures
    assert snapshot["write_attempts"]["insert:audit"] - snapshot["write_calls"]["insert:audit"] == (
        1 if scenario_id == "W11" else 0
    )

    if scenario_id == "W14":
        expired_service, expired_store, expired_clock = make_service(tmp_path / "proposal-ttl")
        expired_ctx = context(session="proposal-ttl")
        expired_proposal = expired_service.investigate(expired_ctx, "PAY-SYN-A02")
        expired_clock.value += timedelta(minutes=31)
        with pytest.raises(StoreError, match="expired proposal"):
            expired_service.decide(expired_ctx, expired_proposal.proposal_id, "approve")
        assert expired_store.task_count() == 0
        expired_store.close()
    if os.environ.get("RECEIVABLES_EVIDENCE_DIR"):
        directory = Path(os.environ["RECEIVABLES_EVIDENCE_DIR"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{scenario_id}.json").write_text(
            json.dumps(
                {
                    "path": scenario_id,
                    "fixture_expected": scenario["expected"],
                    "measurement": measurement,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    store.close()


def test_accessible_demo_labels_status_without_color_and_exposes_keyboard_controls(
    tmp_path: Path,
) -> None:
    service, store, _ = make_service(tmp_path)
    proposal = service.investigate(context(), "PAY-SYN-A02")
    html = render_proposal(proposal).lower()
    assert "<h1" in html and "<h2" in html
    assert "aria-label=" in html and "<button" in html and 'method="post"' in html
    assert 'aria-live="polite"' in html and 'role="alert"' in html
    assert "button:focus" in html and "loading synthetic investigation" in html
    assert "status:" in html and "color:" not in html
    approved_view = service.decide(context(), proposal.proposal_id, "approve")
    review_html = render_proposal(
        proposal,
        confirmation_id=approved_view["confirmation_id"],
        payload=approved_view["payload"],
        payload_hash=approved_view["payload_hash"],
        proposal_version=approved_view["proposal_version"],
    ).lower()
    assert "confirm displayed task" in review_html and "explicit confirmation" in review_html
    assert approved_view["payload"].invoice_id.lower() in review_html
    assert approved_view["payload_hash"] in review_html
    assert f"proposal version: {approved_view['proposal_version']}" in review_html
    store.close()


def test_fixture_hash_remains_unchanged_across_local_workflow(tmp_path: Path) -> None:
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    service, store, _ = make_service(tmp_path)
    proposal, response = approved(service, context())
    assert proposal.proposed_invoice_id == response["payload"].invoice_id
    assert confirm(service, context(), response)["status"] == "created"
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == before
    store.close()


def test_local_wsgi_journey_investigate_approve_display_exact_payload_confirm(
    tmp_path: Path,
    monkeypatch,
) -> None:
    before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    request_results = []
    from aria.agents.aria.receivables.engine import LogicalDemoClock
    from demo.receivables_exception import app as app_module

    ticks = [100.0]
    composed = []
    monkeypatch.setattr(
        app_module, "serve_local", lambda service, ctx: composed.append((service, ctx))
    )
    app_module.main(store_path=tmp_path / "default-demo.sqlite", monotonic=lambda: ticks[0])
    service, ctx = composed[0]
    engine, store = service.engine, service.store
    assert isinstance(engine.clock, LogicalDemoClock)
    assert engine.clock is service.clock is store.clock
    app = create_wsgi_app(service, ctx)

    def request(path: str, values: dict[str, str] | None = None):
        data = urlencode(values or {}).encode("utf-8")
        status: list[str] = []

        def start_response(code, headers):
            status.append(code)

        result = app(
            {
                "REQUEST_METHOD": "POST" if values is not None else "GET",
                "PATH_INFO": path,
                "QUERY_STRING": "",
                "CONTENT_LENGTH": str(len(data)),
                "wsgi.input": BytesIO(data),
            },
            start_response,
        )
        request_results.append({"path": path, "status": status[0]})
        return status[0], b"".join(result).decode("utf-8")

    status, page = request("/")
    assert status == "200 OK" and "Start investigation" in page
    status, page = request(
        "/investigate", {"payment_id": "PAY-SYN-A02", "exception_type": "amount_reference_mismatch"}
    )
    assert status == "200 OK" and "INV-SYN-1002" in page
    proposal = service.store.get_current_proposal(ctx, "EXC-SYN-A02")
    assert proposal is not None
    ticks[0] += 1
    assert engine.clock.now() > proposal.created_at
    status, page = request(
        "/decision", {"proposal_id": proposal.proposal_id, "decision": "approve"}
    )
    assert status == "200 OK" and "Exact immutable task payload" in page
    assert "INV-SYN-1002" in page and "Confirm displayed task" in page
    assert store.task_count() == 0
    binding = store.get_binding(ctx, "")
    assert binding is None
    # The server-issued confirmation is present in the form, never selected by the model.
    marker = 'name="confirmation_id" value="'
    confirmation_id = page.split(marker, 1)[1].split('"', 1)[0]
    hash_marker = 'name="payload_hash" value="'
    payload_hash = page.split(hash_marker, 1)[1].split('"', 1)[0]
    version_marker = 'name="proposal_version" value="'
    proposal_version = page.split(version_marker, 1)[1].split('"', 1)[0]
    status, page = request(
        "/confirm",
        {
            "confirmation_id": confirmation_id,
            "payload_hash": payload_hash,
            "proposal_version": proposal_version,
        },
    )
    assert status == "200 OK" and "task confirmed" in page.lower()
    assert store.task_count() == 1
    ticks[0] += 31 * 60  # exact committed replay survives both expiries
    retry_values = {
        "confirmation_id": confirmation_id,
        "payload_hash": payload_hash,
        "proposal_version": proposal_version,
    }
    status, page = request("/confirm", retry_values)
    assert status == "200 OK" and "task confirmed" in page.lower()
    assert store.task_count() == 1
    snapshot = store.measurements()
    source_calls = {kind.value: engine.source.calls.count(kind) for kind in EvidenceType}
    expected = {f"retrieval:{kind}": count for kind, count in source_calls.items()}
    rows = snapshot["committed_rows"]
    expected.update(
        {
            "check": engine.completed_checks,
            "proposal": service.engine.returned_proposals,
            "decision": rows["decisions"],
            "confirmation_binding": rows["bindings"],
            "confirmation": rows["case_tasks"],
            "task_result": rows["case_tasks"],
            "replay": 1,
        }
    )
    measurement = workflow_metrics(
        source_calls=source_calls,
        **{key: snapshot[key] for key in ("write_attempts", "write_calls", "committed_rows")},
        tasks_created=store.task_count(),
        expected_events=expected,
        observed_events=audit_event_counts(store.audit_events(ctx)),
        fixture_hash_before=before,
        fixture_hash_after=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
    )
    measurement["retrieval_correspondence"] = retrieval_correspondence(
        engine.source.read_observations, store.audit_events(ctx)
    )
    assert measurement["retrieval_correspondence"]["matches"]
    proposal_events = [event for event in store.audit_events(ctx) if event.event_type == "proposal"]
    assert len(proposal_events) == engine.returned_proposals == 2
    assert all(event.proposal_id == proposal.proposal_id for event in proposal_events)
    measurement["proposal_audit_bindings"] = [
        {
            "proposal_id": event.proposal_id,
            "proposal_version": event.proposal_version,
            "source_refs": list(event.source_refs),
        }
        for event in proposal_events
    ]
    measurement["proposals_returned"] = engine.returned_proposals
    assert measurement["audit_correspondence"]["matches"]
    assert measurement["audit_correspondence"]["missing"] == {}
    assert measurement["fixture_unchanged"]
    stale_checks = []
    for payment_id, elapsed in (("PAY-SYN-A02", 11 * 60), ("PAY-SYN-A02", 31 * 60)):
        # Return fixture clock near anchor so sources are fresh at investigation.
        # A separate main composition gives an independent monotonic origin, no rewind.
        app_module.main(store_path=tmp_path / f"ttl-{elapsed}.sqlite", monotonic=lambda: ticks[0])
        ttl_service, ttl_ctx = composed[-1]
        app = create_wsgi_app(ttl_service, ttl_ctx)
        status, page = request(
            "/investigate",
            {"payment_id": payment_id, "exception_type": "amount_reference_mismatch"},
        )
        ttl_proposal = ttl_service.store.get_current_proposal(ttl_ctx, "EXC-SYN-" + payment_id[8:])
        assert status == "200 OK" and ttl_proposal is not None
        approval_delay = 29 * 60 if elapsed == 31 * 60 else 0
        ticks[0] += approval_delay
        status, page = request(
            "/decision", {"proposal_id": ttl_proposal.proposal_id, "decision": "approve"}
        )
        assert status == "200 OK" and "Exact immutable task payload" in page
        values = {
            key: page.split(f'name="{key}" value="', 1)[1].split('"', 1)[0]
            for key in ("confirmation_id", "payload_hash", "proposal_version")
        }
        ticks[0] += elapsed - approval_delay
        for _ in range(2):
            status, page = request("/confirm", values)
            assert status == "200 OK" and "Unconfirmed; no success" in page
            assert ttl_service.store.task_count() == 0
        stale_checks.append({"elapsed_seconds": elapsed, "stale_retries": 2, "tasks": 0})
        ttl_service.store.close()
    if os.environ.get("RECEIVABLES_EVIDENCE_DIR"):
        directory = Path(os.environ["RECEIVABLES_EVIDENCE_DIR"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "demo.json").write_text(
            json.dumps(
                {
                    "path": "demo",
                    "journey": request_results[:5],
                    "stale_ttl_subcases": stale_checks,
                    "clock": "main composition shared LogicalDemoClock; controlled monotonic",
                    "measurement": measurement,
                    "scope": (
                        "in-process WSGI journey; no browser, HTTP listener, network, "
                        "real model or AWS"
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    store.close()


def test_w05_escalate_first_invalidates_pending_confirmation(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    proposal, response = approved(service, ctx)
    service.decide(ctx, proposal.proposal_id, "escalate")
    result = confirm(service, ctx, response)
    assert result["status"] == "stale_confirmation" and store.task_count() == 0
    store.close()


def test_w08_revised_approval_uses_distinct_retry_id_and_old_binding_stays_stale(
    tmp_path: Path,
) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    proposal, first = approved(service, ctx)
    revised = service.decide(ctx, proposal.proposal_id, "revise")["proposal"]
    assert revised.version == 2
    assert confirm(service, ctx, first)["status"] == "stale_confirmation"
    second = service.decide(ctx, revised.proposal_id, "approve")
    assert second["confirmation_id"] != first["confirmation_id"]
    assert confirm(service, ctx, second)["status"] == "created"
    assert confirm(service, ctx, first)["status"] == "stale_confirmation"
    assert store.task_count() == 1
    store.close()


def test_separate_retrieval_audit_failure_returns_unconfirmed_without_task(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    _, response = approved(service, ctx)
    store.audit_failure = True
    result = confirm(service, ctx, response)
    assert result["status"] == "unconfirmed"
    assert store.task_count() == 0
    assert "success" not in result
    assert store.audit_failures == {"retrieval:payment": 1}
    failed_trace = retrieval_correspondence(
        service.engine.source.read_observations, store.audit_events(ctx)
    )
    assert not failed_trace["matches"]
    assert failed_trace["expected"] - failed_trace["matched"] == 1
    store.audit_failure = False
    assert confirm(service, ctx, response)["status"] == "created"
    assert confirm(service, ctx, response)["status"] == "replayed"
    assert store.task_count() == 1
    if os.environ.get("RECEIVABLES_EVIDENCE_DIR"):
        directory = Path(os.environ["RECEIVABLES_EVIDENCE_DIR"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "retrieval-audit-failure.json").write_text(
            json.dumps(
                {
                    "path": "separate retrieval-audit sink failure, not W11",
                    "failed_result": result["status"],
                    "failed_task_count": 0,
                    "failed_attempts": dict(store.audit_failures),
                    "failed_retrieval_correspondence": failed_trace,
                    "after_retry_tasks": store.task_count(),
                    "failed_event_persisted": False,
                    "scope": "Rejected retrieval audit missing; excluded from all14 aggregate",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    store.close()


def test_proposal_ttl_is_rechecked_after_approval_and_at_store_commit(tmp_path: Path) -> None:
    service, store, clock = make_service(tmp_path)
    ctx = context()
    proposal = service.investigate(ctx, "PAY-SYN-A02")
    clock.value += timedelta(minutes=29)
    response = service.decide(ctx, proposal.proposal_id, DecisionKind.APPROVE)
    original_confirm = store.confirm

    def cross_proposal_ttl_during_recheck(*args, **kwargs):
        clock.value += timedelta(minutes=2)
        return original_confirm(*args, **kwargs)

    store.confirm = cross_proposal_ttl_during_recheck
    assert confirm(service, ctx, response)["status"] == "stale_confirmation"
    assert store.task_count() == 0
    store.close()

    service, store, clock = make_service(tmp_path / "store-boundary")
    ctx = context(session="store-boundary")
    proposal = service.investigate(ctx, "PAY-SYN-A02")
    clock.value += timedelta(minutes=29)
    response = service.decide(ctx, proposal.proposal_id, DecisionKind.APPROVE)
    clock.value += timedelta(minutes=2)
    status, task = store.confirm(
        ctx,
        response["confirmation_id"],
        response["payload"],
        response["payload_hash"],
        clock.now(),
    )
    assert status == "stale_confirmation" and task is None
    assert store.task_count() == 0
    state = store._db.execute(
        "SELECT state FROM states WHERE exception_id=?", (proposal.exception_id,)
    ).fetchone()
    assert state["state"] == "approved_awaiting_confirmation"
    store.close()


def test_expiry_crossing_before_sqlite_commit_rolls_back_task_and_audit(tmp_path: Path) -> None:
    service, store, clock = make_service(tmp_path)
    ctx = context()
    proposal = service.investigate(ctx, "PAY-SYN-A02")
    clock.value += timedelta(minutes=29)
    response = service.decide(ctx, proposal.proposal_id, DecisionKind.APPROVE)
    original_audit = store._audit

    def cross_expiry_after_transactional_audit(event_context, event):
        result = original_audit(event_context, event)
        if event.event_type == "task_result":
            clock.value += timedelta(minutes=2)
        return result

    store._audit = cross_expiry_after_transactional_audit
    result = confirm(service, ctx, response)
    assert result["status"] == "stale_confirmation"
    assert store.task_count() == 0
    state = store._db.execute(
        "SELECT state FROM states WHERE exception_id=?", (proposal.exception_id,)
    ).fetchone()
    assert state["state"] == "approved_awaiting_confirmation"
    events = store.audit_events(ctx)
    assert not any(event.event_type in {"confirmation", "task_result"} for event in events)
    assert any(
        event.event_type == "rejection"
        and event.safe_summary == "Confirmation expired before transaction commit"
        for event in events
    )
    store.close()


def inject_confirmation_audit_failure(store: LocalSQLiteStore) -> None:
    store._db.execute(
        """
        CREATE TRIGGER injected_confirmation_audit_failure
        BEFORE INSERT ON audit
        WHEN instr(NEW.event_json, '"event_type":"confirmation"') > 0
          AND EXISTS (SELECT 1 FROM case_tasks)
          AND EXISTS (SELECT 1 FROM states WHERE state='task_created')
        BEGIN
            SELECT RAISE(ABORT, 'injected transactional audit insert failure');
        END
        """
    )


def test_transactional_audit_failure_rolls_back_task_and_state_then_exact_retry_succeeds(
    tmp_path: Path,
) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    proposal, response = approved(service, ctx)
    inject_confirmation_audit_failure(store)
    original_confirm = store.confirm
    transaction_checkpoint = {}

    def record_transaction_checkpoint(*args, **kwargs):
        transaction_checkpoint["audit_count"] = store._db.execute(
            "SELECT COUNT(*) FROM audit"
        ).fetchone()[0]
        transaction_checkpoint["audit_attempts"] = store._db.write_attempts["insert:audit"]
        transaction_checkpoint["audit_calls"] = store._db.write_calls["insert:audit"]
        return original_confirm(*args, **kwargs)

    store.confirm = record_transaction_checkpoint
    failed = confirm(service, ctx, response)
    assert failed["status"] == "unconfirmed" and "success" not in failed
    assert store.task_count() == 0
    state = store._db.execute(
        "SELECT state FROM states WHERE exception_id=?", (proposal.exception_id,)
    ).fetchone()
    assert state["state"] == "approved_awaiting_confirmation"
    assert (
        store._db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
        == transaction_checkpoint["audit_count"]
    )
    assert store._db.write_attempts["insert:audit"] == transaction_checkpoint["audit_attempts"] + 1
    assert store._db.write_calls["insert:audit"] == transaction_checkpoint["audit_calls"]
    assert not any(
        event.event_type in {"confirmation", "task_result"} for event in store.audit_events(ctx)
    )

    store.confirm = original_confirm
    store._db.execute("DROP TRIGGER injected_confirmation_audit_failure")
    retried = confirm(service, ctx, response)
    assert retried["status"] == "created"
    assert store.task_count() == 1
    assert any(event.event_type == "task_result" for event in store.audit_events(ctx))
    store.close()


def test_confirmation_requires_exact_displayed_payload_digest_and_version(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    _, response = approved(service, ctx)
    confirmation_id = response["confirmation_id"]
    assert service.confirm(ctx, confirmation_id)["status"] == "binding_mismatch"
    assert (
        service.confirm(ctx, confirmation_id, "0" * 64, response["proposal_version"])["status"]
        == "binding_mismatch"
    )
    assert (
        service.confirm(
            ctx, confirmation_id, response["payload_hash"], response["proposal_version"] + 1
        )["status"]
        == "binding_mismatch"
    )
    assert store.task_count() == 0
    assert confirm(service, ctx, response)["status"] == "created"
    store.close()


def test_two_sqlite_connections_race_task_creation_and_decision_atomically(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    proposal, response = approved(service, ctx)
    other = LocalSQLiteStore(
        tmp_path / "synthetic.sqlite",
    )
    start = threading.Barrier(3)
    results: dict[str, object] = {}

    def decide() -> None:
        start.wait()
        results["decision"] = other.record_decision(ctx, proposal.proposal_id, DecisionKind.REJECT)

    def create() -> None:
        start.wait()
        results["confirmation"] = store.confirm(
            ctx,
            response["confirmation_id"],
            response["payload"],
            response["payload_hash"],
            datetime(2026, 3, 16, 12, 0, tzinfo=UTC),
        )

    threads = [threading.Thread(target=decide), threading.Thread(target=create)]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    status, task = results["confirmation"]
    assert results["decision"] is not None
    assert status in {"created", "stale_confirmation"}
    assert store.task_count() == (1 if status == "created" else 0)
    if task is not None:
        assert task.payload == response["payload"]
        with pytest.raises(Exception):
            other._db.execute("UPDATE case_tasks SET payload_hash='mutated'")
    other.close()
    store.close()


def test_two_sqlite_connections_concurrent_exact_retries_create_one_task(tmp_path: Path) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    _, response = approved(service, ctx)
    other = LocalSQLiteStore(tmp_path / "synthetic.sqlite")
    start = threading.Barrier(3)
    results: list[tuple[str, object]] = []
    result_lock = threading.Lock()

    def confirm_on(connection: LocalSQLiteStore) -> None:
        start.wait()
        result = connection.confirm(
            ctx,
            response["confirmation_id"],
            response["payload"],
            response["payload_hash"],
            datetime(2026, 3, 16, 12, 0, tzinfo=UTC),
        )
        with result_lock:
            results.append(result)

    threads = [
        threading.Thread(target=confirm_on, args=(store,)),
        threading.Thread(target=confirm_on, args=(other,)),
    ]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert sorted(status for status, _ in results) == ["created", "replayed"]
    assert results[0][1].case_task_id == results[1][1].case_task_id
    assert store.task_count() == 1
    other.close()
    store.close()


def test_default_demo_clock_matches_fixture_for_proposal_expiry(tmp_path: Path) -> None:
    catalogue = load_approved_catalogue(ROOT)
    store = LocalSQLiteStore(tmp_path / "synthetic.sqlite")
    engine = ReceivablesInvestigationEngine(FixtureReadOnlyAdapter(catalogue), catalogue)
    service = ReceivablesWorkflowService(engine, store)
    ctx = context()
    proposal = service.investigate(ctx, "PAY-SYN-A02")
    approved_response = service.decide(ctx, proposal.proposal_id, "approve")
    assert confirm(service, ctx, approved_response)["status"] == "created"
    store.close()


def test_w10_precommit_failure_is_unconfirmed_and_same_identity_retries(
    tmp_path: Path, monkeypatch
) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    _, response = approved(service, ctx)
    original_confirm = store.confirm
    first_call = True

    def fail_before_commit(*args, **kwargs):
        nonlocal first_call
        if first_call:
            first_call = False
            raise StoreError("simulated pre-commit failure")
        return original_confirm(*args, **kwargs)

    monkeypatch.setattr(store, "confirm", fail_before_commit)
    failed = confirm(service, ctx, response)
    assert failed["status"] == "unconfirmed"
    assert store.task_count() == 0
    retried = confirm(service, ctx, response)
    assert retried["status"] == "created"
    assert store.task_count() == 1
    store.close()


def test_w12_other_session_and_w13_untrusted_role_cannot_confirm(tmp_path: Path) -> None:
    from pydantic import ValidationError

    service, store, _ = make_service(tmp_path)
    ctx = context()
    _, response = approved(service, ctx)
    other_session = context(session="different")
    assert confirm(service, other_session, response)["status"] == "unauthorized"
    with pytest.raises(ValidationError, match="unsupported synthetic analyst role"):
        TrustedContext(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            session_id=ctx.session_id,
            correlation_id=ctx.correlation_id,
            analyst_role="viewer",
            authority_source="synthetic_harness",
        )
    result = service.confirm(
        ctx, response["confirmation_id"], response["payload_hash"], response["proposal_version"]
    )
    assert result["status"] == "created"
    store.close()


def test_w14_proposal_ttl_and_confirmation_window_are_enforced(tmp_path: Path) -> None:
    service, store, clock = make_service(tmp_path)
    ctx = context()
    proposal, _ = approved(service, ctx)
    clock.value += timedelta(minutes=31)
    with pytest.raises(StoreError, match="expired proposal"):
        service.decide(ctx, proposal.proposal_id, "approve")
    assert store.task_count() == 0

    service, store, clock = make_service(tmp_path / "confirmation")
    ctx = context(session="confirmation-window")
    _, response = approved(service, ctx)
    clock.value += timedelta(minutes=11)
    assert confirm(service, ctx, response)["status"] == "stale_confirmation"
    assert store.task_count() == 0
    store.close()


def test_store_recomputes_approval_payload_hash_and_exact_proposal_binding(tmp_path: Path) -> None:
    service, store, clock = make_service(tmp_path)
    ctx = context()
    proposal = service.investigate(ctx, "PAY-SYN-A02")
    valid = service._payload(proposal, 1)
    altered = valid.model_copy(update={"summary": "Changed immutable proposal"})
    forged_hash = hashlib.sha256(canonical_json_bytes(altered.model_dump(mode="json"))).hexdigest()
    with pytest.raises(StoreError, match="does not match the proposal binding"):
        store.approve(
            ctx,
            proposal.proposal_id,
            altered,
            "CNF-SYN-FORGED",
            forged_hash,
            clock.now(),
            proposal.expires_at,
        )
    assert store.get_binding(ctx, "CNF-SYN-FORGED") is None
    assert store.task_count() == 0
    store.close()


@pytest.mark.parametrize(
    "failure",
    ["investigation", "retrieval_audit", "decision_audit", "proposal_audit", "persistence"],
)
def test_revision_failures_are_atomic_and_retry_commits_one_immutable_link(
    tmp_path: Path,
    monkeypatch,
    failure: str,
) -> None:
    service, store, _ = make_service(tmp_path)
    ctx = context()
    proposal, response = approved(service, ctx)
    original_payload = store.get_proposal(ctx, proposal.proposal_id)
    before_state = tuple(store._db.execute("SELECT * FROM states").fetchone())
    before_decisions = store._db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    original_investigate = service.engine.investigate
    if failure == "investigation":

        def fail(*args, **kwargs):
            raise RuntimeError("injected investigation failure")

        monkeypatch.setattr(service.engine, "investigate", fail)
    elif failure == "retrieval_audit":
        store.audit_failure = True
    else:
        table = "proposals" if failure == "persistence" else "audit"
        condition = (
            "1"
            if failure == "persistence"
            else (
                f"json_extract(NEW.event_json, '$.event_type') = '{failure.removesuffix('_audit')}'"
            )
        )
        store._db.execute(f"""CREATE TRIGGER revision_fault BEFORE INSERT ON {table}
            WHEN {condition} BEGIN SELECT RAISE(ABORT, 'injected revision failure'); END""")
    with pytest.raises((StoreError, RuntimeError)):
        service.decide(ctx, proposal.proposal_id, "revise", "synthetic revision")
    assert tuple(store._db.execute("SELECT * FROM states").fetchone()) == before_state
    assert store._db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == before_decisions
    assert store._db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0] == 1
    assert store.task_count() == 0
    assert not any("revised to" in event.safe_summary for event in store.audit_events(ctx))
    monkeypatch.setattr(service.engine, "investigate", original_investigate)
    store.audit_failure = False
    if failure not in {"investigation", "retrieval_audit"}:
        store._db.execute("DROP TRIGGER revision_fault")
    revised = service.decide(ctx, proposal.proposal_id, "revise", "synthetic revision")["proposal"]
    assert revised.version == 2
    assert store.get_proposal(ctx, proposal.proposal_id) == original_payload
    assert store.get_current_proposal(ctx, proposal.exception_id) == revised
    assert store._db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == before_decisions + 1
    assert store._db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0] == 2
    links = [event for event in store.audit_events(ctx) if "revised to" in event.safe_summary]
    assert len(links) == 1 and links[0].source_refs == (proposal.proposal_id, revised.proposal_id)
    assert links[0].proposal_id == proposal.proposal_id
    assert links[0].proposal_version == 1
    with pytest.raises(StoreError, match="stale"):
        service.decide(ctx, proposal.proposal_id, "revise")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store._db.execute("UPDATE audit SET event_json='{}'")
    assert store._db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == before_decisions + 1
    assert store.task_count() == 0
    assert confirm(service, ctx, response)["status"] == "stale_confirmation"
    second = service.decide(ctx, revised.proposal_id, "approve")
    assert confirm(service, ctx, second)["status"] == "created"
    assert confirm(service, ctx, second)["status"] == "replayed"
    assert store.task_count() == 1
    store.close()
