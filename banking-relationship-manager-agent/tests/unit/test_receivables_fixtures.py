from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aria.agents.aria.receivables.engine import (
    InvestigationStopped,
    LogicalDemoClock,
    ReceivablesInvestigationEngine,
)
from aria.agents.aria.receivables.freshness import proposal_is_current
from aria.agents.aria.receivables.models import Availability, EvidenceType
from aria.agents.aria.receivables.policy import (
    build_snapshot_manifest,
    canonical_record_digest,
    load_approved_catalogue,
    verify_citation,
)
from aria.agents.aria.receivables.trusted_context import synthetic_harness_context
from demo.receivables_exception.adapters import FixtureReadOnlyAdapter

ROOT = Path(__file__).resolve().parents[2]
FEATURE = ROOT / "specs/004-receivables-exception-resolution"


class FixedClock:
    def __init__(self) -> None:
        self.tick = 100.0

    def now(self) -> datetime:
        return datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.tick


def context():
    return synthetic_harness_context(
        tenant_id="TENANT-SYN-001",
        user_id="analyst",
        session_id="session",
        correlation_id="correlation",
    )


def test_policy_variants_are_materialized_and_source_attributes_drive_rules() -> None:
    catalogue = load_approved_catalogue(ROOT)
    expected_reasons = {
        "P01": "POLICY_MISSING",
        "P02": "POLICY_UNAPPROVED",
        "P03": "POLICY_EXPIRED",
        "P04": "POLICY_SOURCE_MISMATCH",
        "P05": "POLICY_INAPPLICABLE",
    }
    for variant, expected_reason in expected_reasons.items():
        case = next(
            item
            for item in catalogue.fixture["cases"]
            if item.get("policy_variant") == variant
        )
        payment_id = case["payment"]["payment_id"]
        adapter = FixtureReadOnlyAdapter(catalogue)
        policy_result = adapter.read(context(), EvidenceType.POLICY, payment_id)
        if variant == "P01":
            assert policy_result.status == Availability.UNAVAILABLE
            assert not policy_result.records
        else:
            assert len(policy_result.records) == 1
            values = policy_result.records[0].values
            assert "policy_variant" not in values
            assert "expected" not in values
            digest = canonical_record_digest(policy_result.records[0])
            if variant == "P04":
                assert values["declared_policy_digest"] != digest
            else:
                assert values["declared_policy_digest"] == digest
        proposal = ReceivablesInvestigationEngine(adapter, catalogue, FixedClock()).investigate(
            context(), payment_id
        )
        assert proposal.primary_reason == expected_reason

    base = FixtureReadOnlyAdapter(catalogue)

    class ChangedPolicySource:
        def read(self, trusted_context, source_type, key):
            result = base.read(trusted_context, source_type, key)
            if source_type != EvidenceType.POLICY or not result.records:
                return result
            record = result.records[0]
            changed = record.model_copy(
                update={
                    "values": {
                        **record.values,
                        "approval_status_current": "proposed_not_approved",
                    }
                }
            )
            return result.model_copy(update={"records": (changed,)})

    changed_proposal = ReceivablesInvestigationEngine(
        ChangedPolicySource(), catalogue, FixedClock()
    ).investigate(context(), "PAY-SYN-A02")
    assert changed_proposal.primary_reason == "POLICY_UNAPPROVED"


def test_fixture_clock_stays_fixed_but_demo_clock_advances_logical_expiry() -> None:
    catalogue = load_approved_catalogue(ROOT)
    fixture_engine = ReceivablesInvestigationEngine(FixtureReadOnlyAdapter(catalogue), catalogue)
    fixed_now = fixture_engine.clock.now()
    assert fixture_engine.clock.now() == fixed_now

    tick = [250.0]
    demo_clock = LogicalDemoClock(catalogue.fixture["fixed_clock"], lambda: tick[0])
    created = demo_clock.now()
    tick[0] += 30 * 60 + 1
    assert demo_clock.now() == created.replace(minute=30, second=1)
    assert not proposal_is_current(created, created.replace(minute=30), demo_clock.now())


def test_catalogue_counts_scopes_and_labels_are_unchanged() -> None:
    catalogue = load_approved_catalogue(ROOT)
    fixture = catalogue.fixture
    assert len(fixture["cases"]) == 52
    assert len(fixture["guard_cases"]) == 5
    assert fixture["expected_catalogue_counts"]["total_cases"] == 57
    assert fixture["expected_catalogue_counts"]["by_stratum"] == {
        "S1_allocatable": 13,
        "S2_invalid_mapping": 7,
        "S3_duplicate_prior": 5,
        "S4_ineligible_conflict_competing": 4,
        "S5_low_confidence_no_candidate": 6,
        "S6_out_of_tolerance": 3,
        "S7_degraded_evidence": 9,
        "S8_policy_fail_closed": 5,
    }
    assert fixture["tenant_id"] == "TENANT-SYN-001" and fixture["customer_id"] == "CORP-SYN-001"
    assert fixture["currency"] == "USD"
    assert set(catalogue.policy.exception_types) == {
        "invalid_mapping",
        "amount_reference_mismatch",
        "suspected_duplicate",
    }


def test_adapters_are_read_only_bounded_and_guard_requests_do_not_read() -> None:
    catalogue = load_approved_catalogue(ROOT)
    adapter = FixtureReadOnlyAdapter(catalogue)
    assert not any(
        name.startswith(("write", "update", "delete", "create", "upsert"))
        for name in dir(adapter)
        if not name.startswith("__")
    )
    engine = ReceivablesInvestigationEngine(adapter, catalogue, FixedClock())
    out_of_scope = engine.investigate(context(), "PAY-SYN-X01", "chargeback")
    assert out_of_scope.outcome.value == "out_of_scope"
    assert adapter.read_count == 0
    invalid_currency = engine.investigate(context(), "PAY-SYN-A02", currency="EUR")
    assert invalid_currency.outcome.value == "out_of_scope"
    assert adapter.read_count == 0
    proposal = engine.investigate(context(), "PAY-SYN-A02")
    assert adapter.read_count == 7
    assert len(adapter.calls) == 7
    assert len(proposal.candidates) <= 20
    assert proposal.proposed_invoice_id == "INV-SYN-1002", (
        proposal.primary_reason,
        proposal.secondary_reasons,
    )
    assert {item.source_type for item in proposal.evidence_statuses} == set(EvidenceType)
    assert all(item.availability.value == "available" for item in proposal.evidence_statuses)


def test_each_citation_resolves_to_exact_fixture_record_and_snapshot_manifest() -> None:
    catalogue = load_approved_catalogue(ROOT)
    adapter = FixtureReadOnlyAdapter(catalogue)
    engine = ReceivablesInvestigationEngine(adapter, catalogue, FixedClock())
    proposal = engine.investigate(context(), "PAY-SYN-A02")
    assert proposal.snapshot is not None, proposal.secondary_reasons
    cited_types = {item.source_type for item in proposal.evidence}
    status_types = {item.source_type for item in proposal.evidence_statuses}
    assert status_types == set(EvidenceType)
    assert cited_types <= set(EvidenceType)
    assert len(proposal.evidence) >= 6
    reread = FixtureReadOnlyAdapter(catalogue)
    records = [
        record
        for source_type in EvidenceType
        for record in reread.read(context(), source_type, "PAY-SYN-A02").records
    ]
    # Independently derive the manifest from the exact records returned by the read-only catalogue.
    manifest = build_snapshot_manifest(records)
    assert manifest.aggregate_digest == proposal.snapshot.aggregate_digest
    assert manifest.snapshot_id == proposal.snapshot.snapshot_id
    for citation in proposal.evidence:
        assert citation.snapshot_id == manifest.snapshot_id
        assert citation.snapshot_version == manifest.snapshot_version
        assert citation.record_digest.startswith("sha256:") and len(citation.record_digest) == 71
        assert verify_citation(citation, records, manifest)
    inferred = [item for item in proposal.evidence if item.classification.value == "inference"]
    assert all(item.evidence_kind in {"reference_match", "payer_name_match"} for item in inferred)
    assert any(item.evidence_kind == "reference_match" for item in inferred)
    with pytest.raises(ValueError):
        build_snapshot_manifest(records + records[:1])


def test_bad_or_unresolvable_citations_fail_closed() -> None:
    catalogue = load_approved_catalogue(ROOT)
    adapter = FixtureReadOnlyAdapter(catalogue)
    proposal = ReceivablesInvestigationEngine(adapter, catalogue, FixedClock()).investigate(
        context(), "PAY-SYN-A02"
    )
    assert proposal.snapshot is not None
    records = [
        record
        for source_type in EvidenceType
        for record in FixtureReadOnlyAdapter(catalogue)
        .read(context(), source_type, "PAY-SYN-A02")
        .records
    ]
    manifest = build_snapshot_manifest(records)
    citation = proposal.evidence[0]
    changed = citation.model_copy(update={"record_digest": "sha256:" + "0" * 64})
    with pytest.raises(ValueError):
        verify_citation(changed, records, manifest)
    with pytest.raises(ValueError):
        verify_citation(citation, [], manifest)
    bad_manifest = manifest.model_copy(update={"aggregate_digest": "sha256:" + "f" * 64})
    with pytest.raises(ValueError):
        verify_citation(citation, records, bad_manifest)
    with pytest.raises(ValueError):
        verify_citation(
            citation.model_copy(update={"source_type": EvidenceType.INVOICE}), records, manifest
        )
    with pytest.raises(ValueError):
        verify_citation(
            citation.model_copy(update={"snapshot_version": "v1-wrong"}), records, manifest
        )
    with pytest.raises(ValueError):
        verify_citation(
            citation.model_copy(update={"record_digest": "malformed"}), records, manifest
        )
    incomplete = manifest.model_copy(update={"entries": manifest.entries[1:]})
    with pytest.raises(ValueError):
        verify_citation(citation, records, incomplete)
    changed_record = records[0].model_copy(
        update={"values": {**records[0].values, "changed": "synthetic"}}
    )
    changed_records = [changed_record, *records[1:]]
    with pytest.raises(ValueError):
        verify_citation(citation, changed_records, manifest)


def test_fixture_faults_fail_closed_and_partial_sources_disclose_safe_next_step() -> None:
    catalogue = load_approved_catalogue(ROOT)
    for case_id, expected_reason in (
        ("S03", "EVIDENCE_UNAVAILABLE"),
        ("S04", "EVIDENCE_PARTIAL"),
        ("S08", "EVIDENCE_CONFLICT"),
        ("P02", "POLICY_UNAPPROVED"),
    ):
        adapter = FixtureReadOnlyAdapter(catalogue)
        proposal = ReceivablesInvestigationEngine(adapter, catalogue, FixedClock()).investigate(
            context(), f"PAY-SYN-{case_id}"
        )
        assert proposal.outcome.value == "escalate"
        assert expected_reason in {proposal.primary_reason, *proposal.secondary_reasons}
        if case_id == "S04":
            assert (
                proposal.safe_next_step and "refresh or complete" in proposal.safe_next_step.lower()
            )
            assert any(
                item.source_type.value == "invoice" and item.availability.value == "partial"
                for item in proposal.evidence_statuses
            )


def test_engine_cancellation_and_deadline_stop_subsequent_reads() -> None:
    catalogue = load_approved_catalogue(ROOT)
    adapter = FixtureReadOnlyAdapter(catalogue)
    engine = ReceivablesInvestigationEngine(adapter, catalogue, FixedClock())
    audit_events = []
    engine = ReceivablesInvestigationEngine(
        adapter,
        catalogue,
        FixedClock(),
        audit_sink=lambda context, event: audit_events.append(event),
    )
    with pytest.raises(InvestigationStopped, match="cancelled"):
        engine.investigate(context(), "PAY-SYN-A02", cancelled=lambda: adapter.read_count >= 1)
    assert adapter.read_count == 1
    assert audit_events == []
    adapter = FixtureReadOnlyAdapter(catalogue)
    clock = FixedClock()

    def monotonic() -> float:
        clock.tick += 0.6
        return clock.tick

    clock.monotonic = monotonic  # type: ignore[method-assign]
    engine = ReceivablesInvestigationEngine(adapter, catalogue, clock)
    with pytest.raises(InvestigationStopped, match="deadline"):
        engine.investigate(context(), "PAY-SYN-A02", caller_deadline=clock.tick + 1.0)
    assert adapter.read_count <= 1

    slow_clock = FixedClock()

    class SlowSource:
        calls = 0

        def read(self, trusted_context, source_type, key):
            self.calls += 1
            slow_clock.tick = 131.0
            return FixtureReadOnlyAdapter(catalogue).read(trusted_context, source_type, key)

    slow_source = SlowSource()
    slow_engine = ReceivablesInvestigationEngine(slow_source, catalogue, slow_clock)
    with pytest.raises(InvestigationStopped, match="deadline"):
        slow_engine.investigate(context(), "PAY-SYN-A02")
    assert slow_source.calls == 1


def test_approved_fixture_artifact_bytes_are_not_modified_by_reads() -> None:
    before = hashlib.sha256((FEATURE / "synthetic-fixtures.json").read_bytes()).hexdigest()
    catalogue = load_approved_catalogue(ROOT)
    adapter = FixtureReadOnlyAdapter(catalogue)
    adapter.read(context(), EvidenceType.PAYMENT, "PAY-SYN-A02")
    after = hashlib.sha256((FEATURE / "synthetic-fixtures.json").read_bytes()).hexdigest()
    assert before == after == catalogue.fixture_sha256


def test_fixture_adapter_validates_typed_source_schemas() -> None:
    catalogue = load_approved_catalogue(ROOT)
    malformed_fixture = json.loads(json.dumps(catalogue.fixture))
    malformed_fixture["cases"][0]["payment"]["amount"] = "NaN"
    malformed_catalogue = replace(catalogue, fixture=malformed_fixture)
    result = FixtureReadOnlyAdapter(malformed_catalogue).read(
        context(), EvidenceType.PAYMENT, malformed_fixture["cases"][0]["payment"]["payment_id"]
    )
    assert result.status == Availability.MALFORMED
    assert malformed_fixture["cases"][0]["payment"]["amount"] == "NaN"
    assert catalogue.fixture["cases"][0]["payment"]["amount"] != "NaN"


def test_history_adapter_uses_the_same_normalized_reference_tokens_as_rules() -> None:
    catalogue = load_approved_catalogue(ROOT)
    fixture = json.loads(json.dumps(catalogue.fixture))
    case = next(row for row in fixture["cases"] if row["id"] == "A11")
    case["payment"]["remittance_reference"] = "payment for INV 1002"
    case["extra_payments"][0]["remittance_reference"] = "INV-1002/MARCH"
    adapted = replace(catalogue, fixture=fixture)
    records = FixtureReadOnlyAdapter(adapted)._records(
        EvidenceType.PAYMENT_HISTORY, case["payment"]["payment_id"], case
    )
    record_ids = {row.source_record_id for row in records}
    assert {"PAY-SYN-A11", "PAY-SYN-A11T"}.issubset(record_ids)


def test_empty_ledger_uses_independently_verifiable_scoped_envelope() -> None:
    catalogue = load_approved_catalogue(ROOT)
    adapter = FixtureReadOnlyAdapter(catalogue)
    ctx = context()
    result = adapter.read(ctx, EvidenceType.ALLOCATION_LEDGER, "PAY-SYN-A01")
    assert result.status == Availability.AVAILABLE
    assert len(result.records) == 1
    envelope = result.records[0]
    assert envelope.source_record_id == "empty-scope:PAY-SYN-A01"
    assert dict(envelope.values) == {
        "envelope_type": "empty_scope_v1",
        "scope_payment_id": "PAY-SYN-A01",
        "record_count": 0,
        "records": (),
    }
    assert adapter._schema_valid(envelope)

    proposal = ReceivablesInvestigationEngine(
        FixtureReadOnlyAdapter(catalogue), catalogue
    ).investigate(ctx, "PAY-SYN-A01")
    assert proposal.snapshot is not None
    ledger_citation = next(
        citation
        for citation in proposal.evidence
        if citation.source_type == EvidenceType.ALLOCATION_LEDGER
    )
    all_records = [
        record
        for source_type in EvidenceType
        for record in FixtureReadOnlyAdapter(catalogue)
        .read(ctx, source_type, "PAY-SYN-A01")
        .records
    ]
    assert verify_citation(ledger_citation, all_records, proposal.snapshot)
    assert ledger_citation.source_record_id == envelope.source_record_id


def test_conflicting_record_identities_are_suppressed_and_fail_closed() -> None:
    catalogue = load_approved_catalogue(ROOT)
    ctx = context()
    for case_id, source_type in (
        ("S08", EvidenceType.VIRTUAL_ACCOUNT),
        ("S09", EvidenceType.INVOICE),
    ):
        adapter = FixtureReadOnlyAdapter(catalogue)
        result = adapter.read(ctx, source_type, f"PAY-SYN-{case_id}")
        assert result.status == Availability.CONFLICTING
        conflicted_id = (
            "VA-SYN-001" if source_type == EvidenceType.VIRTUAL_ACCOUNT else "INV-SYN-1002"
        )
        assert all(record.source_record_id != conflicted_id for record in result.records)
        proposal = ReceivablesInvestigationEngine(adapter, catalogue).investigate(
            ctx, f"PAY-SYN-{case_id}"
        )
        assert proposal.outcome.value == "escalate"
        assert proposal.primary_reason == "EVIDENCE_CONFLICT"
        assert proposal.snapshot is not None
        assert all(citation.source_record_id != conflicted_id for citation in proposal.evidence)
        assert (
            next(
                disclosure
                for disclosure in proposal.evidence_statuses
                if disclosure.source_type == source_type
            ).availability
            == Availability.CONFLICTING
        )
