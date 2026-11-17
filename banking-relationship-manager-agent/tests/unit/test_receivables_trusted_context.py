from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError


def test_package_imports_and_trusted_context_is_frozen() -> None:
    import aria.agents.aria.receivables as receivables
    import demo.receivables_exception as demo
    from aria.agents.aria.receivables.models import AuthoritySource, TrustedContext
    from aria.agents.aria.receivables.trusted_context import synthetic_harness_context

    assert receivables is not None and demo is not None
    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001",
        user_id="analyst-1",
        session_id="session-1",
        correlation_id="corr-1",
    )
    assert context.authority_source is AuthoritySource.SYNTHETIC_HARNESS
    with pytest.raises(ValidationError):
        context.tenant_id = "TENANT-SYN-OTHER"
    with pytest.raises(ValidationError):
        TrustedContext(
            tenant_id="TENANT-SYN-001",
            user_id="u",
            session_id="s",
            correlation_id="c",
            authority_source="model",
        )


def test_boundary_enum_values_and_invalid_models_are_rejected() -> None:
    from aria.agents.aria.receivables.models import (
        Availability,
        DecisionKind,
        EvidenceClassification,
        EvidenceType,
        Freshness,
        Outcome,
        TrustedContext,
    )

    assert {item.value for item in Availability} == {
        "available",
        "partial",
        "unavailable",
        "malformed",
        "conflicting",
    }
    assert {item.value for item in Freshness} == {"fresh", "stale", "unknown"}
    assert {item.value for item in Outcome} == {
        "recommend",
        "no_recommendation",
        "escalate",
        "out_of_scope",
    }
    assert {item.value for item in DecisionKind} == {"approve", "revise", "reject", "escalate"}
    assert {item.value for item in EvidenceType} == {
        "payment",
        "virtual_account",
        "customer",
        "invoice",
        "payment_history",
        "allocation_ledger",
        "policy",
    }
    assert {item.value for item in EvidenceClassification} == {"authoritative", "inference"}
    with pytest.raises(ValidationError):
        TrustedContext(tenant_id="t", user_id="u", session_id="s", correlation_id="c")


def test_payload_identity_is_not_a_context_and_scope_is_rechecked() -> None:
    from aria.agents.aria.receivables.trusted_context import (
        UntrustedContextError,
        reject_payload_identity,
        require_context,
        synthetic_harness_context,
    )

    with pytest.raises(UntrustedContextError):
        reject_payload_identity({"_verified_principal": {"tenant_id": "TENANT-SYN-001"}})
    with pytest.raises(UntrustedContextError):
        reject_payload_identity({"tenant_id": "TENANT-SYN-001"})
    context = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="s", correlation_id="c"
    )
    assert require_context(context, tenant_id="TENANT-SYN-001") is context
    with pytest.raises(UntrustedContextError):
        require_context(context, tenant_id="TENANT-SYN-OTHER")
    with pytest.raises(UntrustedContextError):
        require_context(object())  # type: ignore[arg-type]


def test_declared_immutable_models_and_read_source_protocol_have_no_mutation() -> None:
    import inspect

    from aria.agents.aria.receivables.models import (
        EvidenceCitation,
        EvidenceType,
        SnapshotEntry,
        SnapshotManifest,
        SourceRecord,
    )
    from aria.agents.aria.receivables.ports import ReadOnlySource

    assert not any(
        name.startswith(("write", "update", "delete", "create", "upsert"))
        for name in dir(ReadOnlySource)
    )
    citation = EvidenceCitation(
        source_type=EvidenceType.PAYMENT,
        source_record_id="PAY-SYN-A02",
        snapshot_id="snap-x",
        snapshot_version="v1-x",
        record_digest="sha256:" + "0" * 64,
        classification="authoritative",
        as_of=datetime(2026, 3, 16, 10, 30, tzinfo=UTC),
        age_seconds=5400,
    )
    with pytest.raises(Exception):
        citation.age_seconds = 1
    entry = SnapshotEntry(
        source_type=EvidenceType.PAYMENT,
        source_record_id="PAY-SYN-A02",
        source_version="fixture-v1",
        record_digest="sha256:" + "0" * 64,
    )
    manifest = SnapshotManifest(
        entries=(entry,),
        snapshot_id="snap-x",
        snapshot_version="v1-x",
        aggregate_digest="sha256:" + "0" * 64,
    )
    with pytest.raises(Exception):
        manifest.entries += (entry,)
    source = SourceRecord(
        source_type=EvidenceType.PAYMENT,
        source_record_id="PAY-SYN-A02",
        source_version="fixture-v1",
        values={"nested": {"rows": ["x"]}},
    )
    with pytest.raises(TypeError):
        source.values["new"] = "value"
    with pytest.raises(TypeError):
        source.values["nested"]["new"] = "value"
    assert inspect.signature(ReadOnlySource.read).parameters.keys() == {
        "self",
        "context",
        "source_type",
        "key",
    }
    with pytest.raises(ValueError):
        EvidenceCitation(
            source_type="payment",
            source_record_id="x",
            snapshot_id="x",
            snapshot_version="x",
            record_digest="0",
            classification="model",
            as_of=datetime.now(UTC),
            age_seconds=-1,
        )


def test_all_declared_boundary_enums_and_frozen_payload_models() -> None:
    from aria.agents.aria.receivables.models import (
        AnalystDecision,
        AuthoritySource,
        CheckStatus,
        ConfirmationBinding,
        DecisionKind,
        DecisionState,
        EvidenceClassification,
        EvidenceType,
        ExceptionState,
        PaymentData,
        ReceivablesException,
        TrustedContext,
    )

    assert {item.value for item in AuthoritySource} == {
        "trusted_server_provider",
        "synthetic_harness",
    }
    assert {item.value for item in ExceptionState} == {
        "received",
        "investigating",
        "awaiting_analyst",
        "approved_awaiting_confirmation",
        "revised",
        "rejected",
        "escalated",
        "task_created",
    }
    assert {item.value for item in CheckStatus} == {
        "clear",
        "suspected",
        "confirmed",
        "unknown",
        "conflict",
    }
    assert set(DecisionKind) and set(EvidenceType) and set(EvidenceClassification)
    with pytest.raises(ValidationError):
        PaymentData.model_validate({"payment_id": "PAY-SYN-A02", "currency": "USD"})
    with pytest.raises(ValidationError):
        PaymentData.model_validate(
            {
                "payment_id": "PAY-SYN-A02",
                "amount": "NaN",
                "currency": "USD",
                "value_date": "2026-03-16",
                "va_id": None,
            }
        )
    with pytest.raises(ValidationError):
        ReceivablesException(exception_id="wrong", payment_id="PAY-SYN-A02", intake_hint="test")
    context = TrustedContext(
        tenant_id="t",
        user_id="u",
        session_id="s",
        correlation_id="c",
        authority_source=AuthoritySource.SYNTHETIC_HARNESS,
    )
    state = DecisionState(
        tenant_id="t",
        session_id="s",
        exception_id="EXC-SYN-A02",
        current_proposal_version=1,
        decision_revision=0,
        state="received",
    )
    decision = AnalystDecision(
        decision_id="d",
        proposal_id="p",
        proposal_version=1,
        decision=DecisionKind.REJECT,
        analyst_id="u",
        decision_revision=1,
        created_at=datetime.now(UTC),
    )
    binding = ConfirmationBinding(
        confirmation_id="c",
        tenant_id="t",
        session_id="s",
        exception_id="EXC-SYN-A02",
        proposal_id="p",
        proposal_version=1,
        decision_revision=1,
        payload_hash="sha256:" + "0" * 64,
        context_binding="sha256:" + "1" * 64,
    )
    for model, field in (
        (context, "tenant_id"),
        (state, "state"),
        (decision, "decision"),
        (binding, "confirmation_id"),
    ):
        with pytest.raises(ValidationError):
            setattr(model, field, "changed")


@pytest.mark.parametrize("authority", ["synthetic_harness", "trusted_server_provider"])
def test_forged_typed_contexts_are_rejected_at_all_state_boundaries(tmp_path, authority) -> None:
    from pathlib import Path

    from aria.agents.aria.receivables.engine import ReceivablesInvestigationEngine
    from aria.agents.aria.receivables.models import TrustedContext
    from aria.agents.aria.receivables.policy import load_approved_catalogue
    from aria.agents.aria.receivables.trusted_context import (
        UntrustedContextError,
        context_from_provider,
        require_context,
        synthetic_harness_context,
    )
    from demo.receivables_exception.adapters import FixtureReadOnlyAdapter
    from demo.receivables_exception.service import ReceivablesWorkflowService
    from demo.receivables_exception.store import LocalSQLiteStore

    issued = synthetic_harness_context(
        tenant_id="TENANT-SYN-001", user_id="u", session_id="s", correlation_id="c"
    )
    forged = TrustedContext.model_validate({**issued.model_dump(), "authority_source": authority})
    catalogue = load_approved_catalogue(Path(__file__).resolve().parents[2])
    adapter = FixtureReadOnlyAdapter(catalogue)
    engine = ReceivablesInvestigationEngine(adapter, catalogue)
    store = LocalSQLiteStore(tmp_path / "forgery.sqlite")
    service = ReceivablesWorkflowService(engine, store)
    try:
        for context in (
            forged,
            issued.model_copy(),
            issued.model_copy(update={"user_id": "forged"}),
        ):
            with pytest.raises(UntrustedContextError, match="not issued"):
                engine.investigate(context, "PAY-SYN-A02")
            with pytest.raises(UntrustedContextError, match="not issued"):
                service.investigate(context, "PAY-SYN-A02")
            with pytest.raises(UntrustedContextError, match="not issued"):
                service.decide(context, "PROP-SYN-A02-1", "approve")
            with pytest.raises(UntrustedContextError, match="not issued"):
                service.confirm(context, "CNF-SYN-forged", "hash", 1)
            with pytest.raises(UntrustedContextError, match="not issued"):
                store.get_current_proposal(context, "EXC-SYN-A02")
        assert adapter.read_count == 0
        assert not any(store.measurements()["write_attempts"].values())

        class Provider:
            def trusted_context(self):
                return {**issued.model_dump(), "authority_source": "trusted_server_provider"}

        trusted = context_from_provider(Provider())
        assert require_context(trusted) is trusted
        with pytest.raises(UntrustedContextError, match="not issued"):
            require_context(TrustedContext.model_validate(trusted.model_dump()))
    finally:
        store.close()
