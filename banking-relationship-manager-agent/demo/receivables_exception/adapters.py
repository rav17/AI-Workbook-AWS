from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from pydantic import BaseModel, ValidationError

from aria.agents.aria.receivables.models import (
    AllocationRecord,
    Availability,
    CustomerData,
    EvidenceType,
    InvoiceData,
    PaymentData,
    SourceRecord,
    SourceResult,
    TrustedContext,
    VirtualAccountData,
)
from aria.agents.aria.receivables.policy import (
    POLICY_PROJECTION,
    ApprovedCatalogue,
    canonical_record_digest,
    load_approved_catalogue,
)
from aria.agents.aria.receivables.rules import reference_tokens
from aria.agents.aria.receivables.trusted_context import require_context


class FixtureReadOnlyAdapter:
    """Bounded, local-only adapter over the approved immutable synthetic catalogue."""

    def __init__(self, catalogue: ApprovedCatalogue | None = None) -> None:
        self.catalogue = catalogue or load_approved_catalogue()
        self.calls: list[EvidenceType] = []
        self.read_observations: list[dict[str, Any]] = []

    @property
    def read_count(self) -> int:
        return len(self.calls)

    def _case(self, payment_id: str) -> dict[str, Any] | None:
        for case in self.catalogue.fixture["cases"]:
            if case["payment"]["payment_id"] == payment_id:
                return cast(dict[str, Any], case)
        return None

    def _payment(self, payment: dict[str, Any]) -> dict[str, Any]:
        values = dict(self.catalogue.fixture["payment_defaults"])
        values.update(payment)
        if values.get("bank_reference") == "BREF-<payment_id>":
            values["bank_reference"] = f"BREF-{values['payment_id']}"
        values.setdefault("bank_reference", f"BREF-{values['payment_id']}")
        return values

    def _records(
        self, source_type: EvidenceType, payment_id: str, case: dict[str, Any]
    ) -> list[SourceRecord]:
        fixture = self.catalogue.fixture
        version = f"fixture-v1@sha256:{self.catalogue.fixture_sha256}"
        if source_type == EvidenceType.PAYMENT:
            rows = [self._payment(case["payment"])]
            for extra in case.get("extra_payments", []):
                rows.append(self._payment(extra))
            return [self._record(source_type, row["payment_id"], version, row) for row in rows[:20]]
        if source_type == EvidenceType.VIRTUAL_ACCOUNT:
            payment = self._payment(case["payment"])
            rows = [
                row for row in fixture["virtual_accounts"] if row["va_id"] == payment.get("va_id")
            ]
            for fault in case.get("faults", []):
                if (
                    fault.get("source") == "virtual_account"
                    and fault.get("kind") == "conflicting_records"
                ):
                    rows.append(fault["extra_record"])
            return [self._record(source_type, row["va_id"], version, row) for row in rows[:20]]
        if source_type == EvidenceType.CUSTOMER:
            row = fixture["customer"]
            return [self._record(source_type, row["customer_id"], version, row)]
        if source_type == EvidenceType.INVOICE:
            rows = []
            for invoice in fixture["invoices"]:
                normalized = {
                    "customer_id": fixture["customer_id"],
                    "currency": fixture["currency"],
                    **invoice,
                }
                rows.append(normalized)
            for fault in case.get("faults", []):
                if fault.get("source") == "invoice" and fault.get("kind") == "conflicting_records":
                    rows.append(
                        {
                            "customer_id": fixture["customer_id"],
                            "currency": fixture["currency"],
                            **fault["extra_record"],
                        }
                    )
            return [self._record(source_type, row["invoice_id"], version, row) for row in rows[:20]]
        if source_type == EvidenceType.PAYMENT_HISTORY:
            current = self._payment(case["payment"])
            # Include only fixture-backed candidates that could meet the duplicate criteria.
            current_record = self._payment(case["payment"])
            candidates = [current_record]
            for item in (self._payment(row) for row in case.get("extra_payments", [])):
                if item["payment_id"] == payment_id or item.get("va_id") != current.get("va_id"):
                    continue
                if item.get("amount") != current.get("amount"):
                    continue
                ref_tokens = set(reference_tokens(str(item.get("remittance_reference", ""))))
                current_tokens = set(reference_tokens(str(current.get("remittance_reference", ""))))
                if ref_tokens and ref_tokens == current_tokens:
                    candidates.append(item)
            return [
                self._record(source_type, row["payment_id"], version, row)
                for row in candidates[:20]
            ]
        if source_type == EvidenceType.ALLOCATION_LEDGER:
            # Each approved case is an isolated source snapshot; do not leak another case's rows.
            rows = case.get("allocations", [])
            if not rows:
                # This is a digest-bound envelope for the scoped empty query, not a ledger row.
                return [
                    self._record(
                        source_type,
                        f"empty-scope:{payment_id}",
                        version,
                        {
                            "envelope_type": "empty_scope_v1",
                            "scope_payment_id": payment_id,
                            "record_count": 0,
                            "records": [],
                        },
                    )
                ]
            return [
                self._record(source_type, row["allocation_id"], version, row) for row in rows[:20]
            ]
        if source_type == EvidenceType.POLICY:
            return [self._policy_record(case)]
        return []

    def _policy_record(self, case: dict[str, Any]) -> SourceRecord:
        fixture = self.catalogue.fixture
        raw = fixture["policy"]
        variant_name = case.get("policy_variant")
        variant = fixture.get("policy_variants", {}).get(variant_name, {})
        values = {key: raw[key] for key in POLICY_PROJECTION}
        values.update({key: value for key, value in variant.items() if key in POLICY_PROJECTION})
        approval_status = variant.get(
            "approval_status_current", raw["approval_status_after_human_approval"]
        )
        values["approval_status_current"] = approval_status
        values["approval_record_ref"] = (
            self.catalogue.approval_ref
            if approval_status == "approved_synthetic_test_only"
            else None
        )
        provisional = self._record(
            EvidenceType.POLICY, str(values["policy_id"]), str(values["version"]), values
        )
        computed_digest = canonical_record_digest(provisional)
        values["declared_policy_digest"] = (
            canonical_record_digest(self.catalogue.policy_source)
            if variant.get("digest_mismatch")
            else computed_digest
        )
        return self._record(
            EvidenceType.POLICY, str(values["policy_id"]), str(values["version"]), values
        )

    @staticmethod
    def _record(
        source_type: EvidenceType, record_id: str, version: str, values: dict[str, Any]
    ) -> SourceRecord:
        return SourceRecord(
            source_type=source_type,
            source_record_id=record_id,
            source_version=version,
            values=values,
        )

    @staticmethod
    def _schema_valid(record: SourceRecord) -> bool:
        schemas: dict[EvidenceType, type[BaseModel]] = {
            EvidenceType.PAYMENT: PaymentData,
            EvidenceType.PAYMENT_HISTORY: PaymentData,
            EvidenceType.VIRTUAL_ACCOUNT: VirtualAccountData,
            EvidenceType.CUSTOMER: CustomerData,
            EvidenceType.INVOICE: InvoiceData,
            EvidenceType.ALLOCATION_LEDGER: AllocationRecord,
        }
        if (
            record.source_type == EvidenceType.ALLOCATION_LEDGER
            and record.values.get("envelope_type") == "empty_scope_v1"
        ):
            values = record.values
            return (
                values.get("scope_payment_id")
                == record.source_record_id.removeprefix("empty-scope:")
                and values.get("record_count") == 0
                and values.get("records") == ()
            )
        schema = schemas.get(record.source_type)
        if record.source_type == EvidenceType.POLICY:
            try:
                canonical_record_digest(record)
                return bool(record.values.get("declared_policy_digest"))
            except (ValueError, TypeError, KeyError):
                return False
        if schema is None:
            return True
        try:
            schema.model_validate(dict(record.values))
        except (ValidationError, ValueError, TypeError):
            return False
        return True

    def read(self, context: TrustedContext, source_type: EvidenceType, key: str) -> SourceResult:
        result = self._read(context, source_type, key)
        self.read_observations.append(
            {
                "source_type": source_type.value,
                "source_refs": tuple(record.source_record_id for record in result.records),
                "availability": result.status.value,
            }
        )
        return result

    def _read(self, context: TrustedContext, source_type: EvidenceType, key: str) -> SourceResult:
        require_context(context, tenant_id=self.catalogue.fixture["tenant_id"])
        self.calls.append(source_type)
        case = self._case(key)
        if case is None:
            return SourceResult(
                status=Availability.UNAVAILABLE,
                records=(),
                as_of=datetime.fromisoformat(
                    self.catalogue.fixture["fixed_clock"].replace("Z", "+00:00")
                ),
                detail="payment is not present in the approved synthetic catalogue",
            )
        if case.get("policy_variant") == "P01" and source_type == EvidenceType.POLICY:
            status = Availability.UNAVAILABLE
            records: list[SourceRecord] = []
        else:
            records = self._records(source_type, key, case)
            status = Availability.AVAILABLE
            if records and not all(self._schema_valid(record) for record in records):
                status = Availability.MALFORMED
            identities = [
                (record.source_type, record.source_record_id, record.source_version)
                for record in records
            ]
            collisions = {identity for identity in identities if identities.count(identity) > 1}
            if collisions:
                # Suppress every ambiguous record; only availability, not either contested
                # value, may influence the fail-closed investigation.
                records = [
                    record
                    for record in records
                    if (record.source_type, record.source_record_id, record.source_version)
                    not in collisions
                ]
                status = Availability.CONFLICTING
        fault_time: str | None = None
        for fault in case.get("faults", []):
            if fault.get("source") == source_type.value:
                kind = fault.get("kind")
                fault_time = fault.get("as_of") or fault_time
                if kind == "unavailable":
                    status = Availability.UNAVAILABLE
                    records = []
                elif kind == "partial":
                    status = Availability.PARTIAL
                elif kind == "malformed":
                    status = Availability.MALFORMED
                elif kind == "conflicting_records":
                    status = Availability.CONFLICTING
        as_of = datetime.fromisoformat(
            (fault_time or self.catalogue.fixture["default_as_of"]).replace("Z", "+00:00")
        )
        return SourceResult(status=status, records=tuple(records[:20]), as_of=as_of)
