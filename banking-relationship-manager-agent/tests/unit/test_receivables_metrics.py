from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

from aria.agents.aria.receivables.agent import should_route_receivables_request
from aria.agents.aria.receivables.engine import ReceivablesInvestigationEngine
from aria.agents.aria.receivables.metrics import (
    audit_event_counts,
    catalogue_metrics,
    retrieval_correspondence,
    workflow_metrics,
)
from aria.agents.aria.receivables.models import EvidenceType, Freshness
from aria.agents.aria.receivables.policy import (
    build_snapshot_manifest,
    load_approved_catalogue,
    verify_citation,
)
from aria.agents.aria.receivables.trusted_context import synthetic_harness_context
from demo.receivables_exception.adapters import FixtureReadOnlyAdapter
from demo.receivables_exception.service import ReceivablesWorkflowService
from demo.receivables_exception.store import LocalSQLiteStore

ROOT = Path(__file__).resolve().parents[2]
FEATURE = ROOT / "specs/004-receivables-exception-resolution"


def test_catalogue_e_path_uses_fixed_denominators_and_preserves_unscored_counts() -> None:
    catalogue = load_approved_catalogue(ROOT)
    fixture = catalogue.fixture
    ctx = synthetic_harness_context(
        tenant_id="TENANT-SYN-001",
        user_id="analyst",
        session_id="metrics",
        correlation_id="metrics-run",
    )
    adapter = FixtureReadOnlyAdapter(catalogue)
    before = hashlib.sha256((FEATURE / "synthetic-fixtures.json").read_bytes()).hexdigest()
    events = []
    engine = ReceivablesInvestigationEngine(
        adapter, catalogue, audit_sink=lambda ctx, event: events.append(event)
    )
    proposals = [
        engine.investigate(
            ctx, case["payment"]["payment_id"], case.get("intake_hint", "amount_reference_mismatch")
        )
        for case in fixture["cases"]
    ]
    returned_proposals = list(proposals)
    result = catalogue_metrics(
        fixture["cases"],
        proposals,
        coverage={kind.value: adapter.calls.count(kind) for kind in EvidenceType},
        fixture=fixture,
    )
    assert result["classification"]["denominator"] == 50
    assert result["classification"]["unscored_by_label"] == 2
    assert result["top_candidate"]["denominator"] == 13
    assert result["escalation"]["denominator"] == 36
    assert sum(fixture["expected_catalogue_counts"]["by_stratum"].values()) == 52
    assert result["coverage"] == {
        kind.value: {"calls": 52, "status": "measured"} for kind in EvidenceType
    }
    assert result["claims"].startswith("no success-target claim")
    assert result["citation_trace"]["valid"] > 0
    assert result["citation_completeness"]["recommendations"] >= 0
    assert result["strata"]["S1_allocatable"]["total"] == 13
    assert result["escalation"]["required_denominator"] == 36
    assert result["escalation"]["not_required_denominator"] == 16
    assert result["classification"]["correct"] == 50
    assert result["top_candidate"]["correct"] == 13
    assert result["recommendation"]["precision_numerator"] == 13
    assert result["recommendation"]["precision_denominator"] == 13
    assert result["escalation"]["correct_required"] == 36
    assert result["escalation"]["false_escalations"] == 0
    assert result["dispositions"] == {
        "recommend": 13,
        "escalate": 36,
        "no_recommendation": 3,
    }
    assert result["abstentions"] == 39 and result["errors"] == 0
    assert result["unlabelled_cases"] == 0
    assert result["citation_trace"] == {"valid": 939, "cited": 939, "failures": 0}
    assert adapter.read_count == 52 * 7
    for recommendation in (item for item in proposals if item.outcome.value == "recommend"):
        resolved = FixtureReadOnlyAdapter(catalogue)
        records = [
            record
            for source_type in EvidenceType
            for record in resolved.read(ctx, source_type, recommendation.payment_id).records
        ]
        manifest = build_snapshot_manifest(records)
        assert recommendation.snapshot is not None
        assert manifest.aggregate_digest == recommendation.snapshot.aggregate_digest
        assert {item.source_type for item in recommendation.evidence} == set(EvidenceType)
        assert all(verify_citation(item, records, manifest) for item in recommendation.evidence)
    expected_cases = {case["payment"]["payment_id"]: case for case in fixture["cases"]}
    proposal_by_id = {proposal.payment_id: proposal for proposal in proposals}
    assert set(expected_cases) == set(proposal_by_id)
    assert result["classification"]["correct"] == sum(
        bool(case["expected"].get("classification_scored"))
        and bool(proposal_by_id[payment_id].evidence)
        and proposal_by_id[payment_id].classification == case["expected"].get("classification")
        for payment_id, case in expected_cases.items()
    )
    assert result["top_candidate"]["correct"] == sum(
        bool(case["expected"].get("allocatable"))
        and bool(proposal_by_id[payment_id].evidence)
        and bool(
            [
                item
                for item in proposal_by_id[payment_id].candidates
                if item.eligible and item.score > 0
            ]
        )
        and [
            item.invoice_id
            for item in proposal_by_id[payment_id].candidates
            if item.eligible and item.score > 0
        ][0]
        in case["expected"].get("acceptable_invoice_ids", [])
        for payment_id, case in expected_cases.items()
    )
    for stratum, expected_count in fixture["expected_catalogue_counts"]["by_stratum"].items():
        assert result["strata"][stratum]["total"] == expected_count
    assert result["strata"]["S7_degraded_evidence"]["classification_correct"] == 7

    guards = fixture["guard_cases"]
    assert len(guards) == 5
    for guard in guards:
        request = guard["request"]
        before_reads = adapter.read_count
        if "input" in request:
            assert not should_route_receivables_request(request["input"])
        else:
            proposal = engine.investigate(
                ctx,
                request["payment_id"],
                request.get("exception_type", "amount_reference_mismatch"),
                customer_id=request.get("customer_scope", "CORP-SYN-001"),
                currency=request.get("currency", "USD"),
            )
            assert proposal.outcome.value == guard["expected"]["disposition"]
            assert adapter.read_count - before_reads == guard["expected"]["source_reads"] == 0
            returned_proposals.append(proposal)

    expected_events = {
        f"retrieval:{kind.value}": adapter.calls.count(kind) for kind in EvidenceType
    }
    expected_events["check"] = engine.completed_checks
    expected_events["proposal"] = engine.returned_proposals
    observed_events = audit_event_counts(events)
    retrievals = retrieval_correspondence(adapter.read_observations, events)
    assert retrievals["matches"] and retrievals["matched"] == adapter.read_count
    assert expected_events == observed_events
    proposal_events = [event for event in events if event.event_type == "proposal"]
    proposal_audit_matches = sorted(
        (event.proposal_id, event.proposal_version, event.source_refs)
        for event in proposal_events
    ) == sorted(
        (
            proposal.proposal_id,
            proposal.version,
            tuple(item.source_record_id for item in proposal.evidence),
        )
        for proposal in returned_proposals
    )
    assert proposal_audit_matches
    assert engine.returned_proposals == len(returned_proposals) == 56
    assert len([guard for guard in guards if "input" not in guard["request"]]) == 4
    assert len([guard for guard in guards if "input" in guard["request"]]) == 1
    assert len(guards) + len(proposals) == 57
    assert result["citation_completeness"] == {
        "complete_recommendations": 13,
        "recommendations": 13,
        "rate": 1.0,
    }
    assert result["variance_recomputation"] == {"correct": 13, "denominator": 13}
    # Independent fixture labels remain fixed; all 102 supplied labels now match.
    assert result["fixture_label_checks"] == {
        "primary_reason": {"denominator": 52, "correct": 52},
        "variance": {"denominator": 16, "correct": 16},
        "duplicate_status": {"denominator": 18, "correct": 18},
        "prior_allocation_status": {"denominator": 16, "correct": 16},
    }
    assert result["fixture_label_mismatches"] == []
    assert result["citation_trace"] == {"valid": 939, "cited": 939, "failures": 0}
    assert result["dispositions"] == {"recommend": 13, "escalate": 36, "no_recommendation": 3}
    assert result["errors"] == 0
    after = hashlib.sha256((FEATURE / "synthetic-fixtures.json").read_bytes()).hexdigest()
    assert before == after
    if os.environ.get("RECEIVABLES_EVIDENCE_DIR"):
        directory = Path(os.environ["RECEIVABLES_EVIDENCE_DIR"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "E.json").write_text(
            json.dumps(
                {
                    "path": "E",
                    "cases_exercised": 57,
                    "guard_cases": 5,
                    "proposals_returned": engine.returned_proposals,
                    "guard_attempts": {
                        "cases": len(guards),
                        "engine_invocations": 4,
                        "returned_proposals": 4,
                        "router_only_rejections": 1,
                        "source_reads": 0,
                    },
                    "metrics": result,
                    "retrieval_correspondence": retrievals,
                    "audit_correspondence": {
                        "expected": expected_events,
                        "observed": observed_events,
                        "matches": expected_events == observed_events,
                        "missing": {},
                        "proposal_bindings": {
                            "returned": len(returned_proposals),
                            "audited": len(proposal_events),
                            "matches": proposal_audit_matches,
                        },
                    },
                    "fixture_hash_before": before,
                    "fixture_hash_after": after,
                    "writers": (
                        "No workflow store in E; proposal/decision/binding/state/task/SQLite "
                        "audit writers unexercised; in-memory audit sink measured"
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def test_metrics_use_na_for_zero_denominators_and_keep_abstentions_visible() -> None:
    result = catalogue_metrics([], [], coverage={"unused_writer": 0})
    assert result["classification"]["rate"] == "N/A"
    assert result["top_candidate"]["rate"] == "N/A"
    assert result["escalation"]["rate"] == "N/A"
    assert result["citation_completeness"]["rate"] == "N/A"
    assert result["coverage"]["unused_writer"] == {"calls": 0, "status": "unexercised"}


def test_workflow_instrumentation_compares_immutable_fixture_bytes(tmp_path: Path) -> None:
    before = hashlib.sha256((FEATURE / "synthetic-fixtures.json").read_bytes()).hexdigest()
    catalogue = load_approved_catalogue(ROOT)
    adapter = FixtureReadOnlyAdapter(catalogue)
    store = LocalSQLiteStore(tmp_path / "metrics.sqlite")
    ctx = synthetic_harness_context(
        tenant_id="TENANT-SYN-001",
        user_id="analyst",
        session_id="metrics-workflow",
        correlation_id="metrics-workflow",
    )
    service = ReceivablesWorkflowService(ReceivablesInvestigationEngine(adapter, catalogue), store)
    proposal = service.investigate(ctx, "PAY-SYN-A02")
    assert store.task_count() == 0
    response = service.decide(ctx, proposal.proposal_id, "approve")
    assert store.task_count() == 0
    created = service.confirm(
        ctx,
        response["confirmation_id"],
        response["payload_hash"],
        response["proposal_version"],
    )
    assert created["status"] == "created"
    after = hashlib.sha256((FEATURE / "synthetic-fixtures.json").read_bytes()).hexdigest()
    snapshot = store.measurements()
    source_calls = {kind.value: adapter.calls.count(kind) for kind in EvidenceType}
    expected = {f"retrieval:{key}": count for key, count in source_calls.items()}
    expected.update(
        {
            "check": service.engine.completed_checks,
            "proposal": service.engine.returned_proposals,
            "decision": snapshot["committed_rows"]["decisions"],
            "confirmation_binding": snapshot["committed_rows"]["bindings"],
            "confirmation": store.task_count(),
            "task_result": store.task_count(),
        }
    )
    result = workflow_metrics(
        source_calls=source_calls,
        **{key: snapshot[key] for key in ("write_attempts", "write_calls", "committed_rows")},
        tasks_created=store.task_count(),
        expected_events=expected,
        observed_events=audit_event_counts(store.audit_events(ctx)),
        fixture_hash_before=before,
        fixture_hash_after=after,
    )
    assert result["source_reads"] == 14
    assert result["tasks_created"] == 1
    assert result["audit_events"] == 22
    assert result["fixture_unchanged"] is True
    assert result["audit_correspondence"]["matches"] is True
    assert result["audit_correspondence"]["missing"] == {}
    assert all(
        result["writer_surfaces"]["insert:" + table]["calls"] > 0
        for table in ("proposals", "states", "decisions", "bindings", "case_tasks", "audit")
    )
    assert result["writer_surfaces"]["delete:case_tasks"] == {
        "attempts": 0,
        "calls": 0,
        "status": "unexercised",
    }
    store.close()


def test_invalid_citation_is_counted_as_error_and_abstention() -> None:
    catalogue = load_approved_catalogue(ROOT)
    ctx = synthetic_harness_context(
        tenant_id="TENANT-SYN-001",
        user_id="analyst",
        session_id="invalid-trace",
        correlation_id="invalid-trace",
    )
    proposal = ReceivablesInvestigationEngine(
        FixtureReadOnlyAdapter(catalogue), catalogue
    ).investigate(ctx, "PAY-SYN-A02")
    invalid_citation = proposal.evidence[0].model_copy(
        update={"record_digest": "sha256:" + "0" * 64}
    )
    invalid = proposal.model_copy(update={"evidence": (invalid_citation, *proposal.evidence[1:])})
    case = next(
        case
        for case in catalogue.fixture["cases"]
        if case["payment"]["payment_id"] == "PAY-SYN-A02"
    )
    result = catalogue_metrics([case], [invalid])
    assert result["errors"] == 1 and result["abstentions"] == 1
    assert result["citation_trace"]["failures"] == 1
    assert result["top_candidate"]["correct"] == 0
    assert result["recommendation"]["precision_denominator"] == 1
    assert result["recommendation"]["precision_numerator"] == 0
    assert result["citation_completeness"]["complete_recommendations"] == 0


@pytest.mark.parametrize("missing", [True, False])
def test_required_escalation_is_not_credited_for_missing_proposal_or_invalid_trace(missing) -> None:
    catalogue = load_approved_catalogue(ROOT)
    case = next(row for row in catalogue.fixture["cases"] if row["id"] == "M01")
    assert case["expected"]["escalation_required"] is True
    ctx = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="s", correlation_id="c"
    )
    proposal = ReceivablesInvestigationEngine(
        FixtureReadOnlyAdapter(catalogue), catalogue
    ).investigate(ctx, case["payment"]["payment_id"])
    invalid = proposal.model_copy(
        update={
            "evidence": (
                proposal.evidence[0].model_copy(update={"record_digest": "sha256:" + "0" * 64}),
                *proposal.evidence[1:],
            )
        }
    )
    result = catalogue_metrics([case], [] if missing else [invalid], fixture=catalogue.fixture)
    assert result["escalation"]["correct_required"] == 0
    assert result["strata"][case["stratum"]]["escalation_correct"] == 0
    assert result["classification"]["correct"] == 0
    assert result["top_candidate"]["correct"] == 0
    assert result["recommendation"]["precision_numerator"] == 0
    assert result["citation_completeness"]["complete_recommendations"] == 0
    assert result["dispositions"] == {"error": 1}
    assert result["errors"] == result["abstentions"] == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "variance",
        "expected_amount",
        "candidate_variance",
        "status",
        "stale_status",
        "stale_citation",
        *[kind.value for kind in EvidenceType],
    ],
)
def test_sc005_requires_seven_distinct_citation_types_and_independent_exact_amounts(
    mutation,
) -> None:
    from aria.agents.aria.receivables.models import (
        EvidenceCitation,
        EvidenceClassification,
        SourceRecord,
    )
    from aria.agents.aria.receivables.policy import build_snapshot_manifest

    catalogue = load_approved_catalogue(ROOT)
    case = next(row for row in catalogue.fixture["cases"] if row["id"] == "A02")
    ctx = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="sc005", correlation_id="sc005"
    )
    proposal = ReceivablesInvestigationEngine(
        FixtureReadOnlyAdapter(catalogue), catalogue
    ).investigate(ctx, case["payment"]["payment_id"])
    # Metric-only construction to test a complete manifest, including explicit ledger evidence.
    # Not added to fixtures or presented as an actual engine result.
    manifest = build_snapshot_manifest(
        [
            SourceRecord(
                source_type=kind,
                source_record_id=kind.value,
                source_version="test-v1",
                values=dict(catalogue.fixture["policy"]) if kind == EvidenceType.POLICY else {},
            )
            for kind in EvidenceType
        ]
    )
    citations = tuple(
        EvidenceCitation(
            source_type=entry.source_type,
            source_record_id=entry.source_record_id,
            snapshot_id=manifest.snapshot_id,
            snapshot_version=manifest.snapshot_version,
            record_digest=entry.record_digest,
            classification=EvidenceClassification.AUTHORITATIVE,
            as_of=proposal.created_at,
            age_seconds=0,
        )
        for entry in manifest.entries
    )
    updates = {"snapshot": manifest, "evidence": citations}
    if mutation in {kind.value for kind in EvidenceType}:
        kept = tuple(item for item in citations if item.source_type.value != mutation)
        updates["evidence"] = (*kept, kept[0])  # Seven citations, only six distinct types.
    elif mutation == "variance":
        updates["variance"] = proposal.variance + Decimal("0.01")
    elif mutation == "expected_amount":
        updates["expected_amount"] = proposal.expected_amount + Decimal("0.01")
    elif mutation == "candidate_variance":
        first = proposal.candidates[0].model_copy(update={"variance": Decimal("123.45")})
        updates["candidates"] = (first, *proposal.candidates[1:])
    elif mutation == "status":
        updates["evidence_statuses"] = proposal.evidence_statuses[1:]
    elif mutation == "stale_status":
        updates["evidence_statuses"] = (
            proposal.evidence_statuses[0].model_copy(update={"freshness": Freshness.STALE}),
            *proposal.evidence_statuses[1:],
        )
    elif mutation == "stale_citation":
        updates["evidence"] = (
            citations[0].model_copy(update={"freshness": Freshness.STALE}),
            *citations[1:],
        )
    result = catalogue_metrics(
        [case], [proposal.model_copy(update=updates)], fixture=catalogue.fixture
    )
    assert (
        result["errors"] == 0
    )  # A valid trace is not the same thing as complete required evidence.
    assert result["citation_completeness"]["complete_recommendations"] == int(mutation == "none")
    assert result["variance_recomputation"]["correct"] == int(
        mutation not in {"variance", "expected_amount", "candidate_variance"}
    )


def test_audit_correspondence_rejects_missing_and_wrong_source_references() -> None:
    from datetime import UTC, datetime

    from aria.agents.aria.receivables.models import AuditEvent

    reads = [
        {"source_type": "payment", "source_refs": ("PAY-SYN-A02",), "availability": "available"}
    ]
    event = AuditEvent(
        event_id="sensor",
        correlation_id="sensor",
        sequence=1,
        event_type="retrieval",
        actor="analyst",
        source_refs=("PAY-SYN-A02",),
        safe_summary="Retrieved payment evidence (available)",
        created_at=datetime(2026, 3, 16, tzinfo=UTC),
    )
    assert retrieval_correspondence(reads, [event])["matches"]
    assert retrieval_correspondence(reads, [])["matched"] == 0
    wrong = event.model_copy(update={"source_refs": ("PAY-SYN-OTHER",)})
    result = retrieval_correspondence(reads, [wrong])
    assert not result["matches"] and result["matched"] == 0
    assert result["missing"][0]["source_refs"] == ["PAY-SYN-A02"]
    assert result["unexpected"][0]["source_refs"] == ["PAY-SYN-OTHER"]
