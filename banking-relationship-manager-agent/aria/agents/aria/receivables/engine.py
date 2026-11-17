from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aria.agents.aria.receivables.freshness import freshness, policy_is_effective
from aria.agents.aria.receivables.models import (
    AllocationCheckStatus,
    AuditEvent,
    Availability,
    CandidateAllocation,
    CheckStatus,
    EvidenceCitation,
    EvidenceClassification,
    EvidenceDisclosure,
    EvidenceType,
    Freshness,
    InvestigationProposal,
    Outcome,
    PolicyRecord,
    SnapshotManifest,
    SourceRecord,
    SourceResult,
    TrustedContext,
)
from aria.agents.aria.receivables.policy import (
    ApprovedCatalogue,
    build_snapshot_manifest,
    canonical_json_bytes,
    canonical_record_digest,
    load_approved_catalogue,
)
from aria.agents.aria.receivables.ports import Clock, ReadOnlySource
from aria.agents.aria.receivables.rules import (
    classify_exception,
    competing_candidates,
    duplicate_status,
    mapping_status,
    prior_allocation_status,
    rank_candidates,
    reference_tokens,
)
from aria.agents.aria.receivables.trusted_context import require_context

SOURCE_ORDER = tuple(EvidenceType)
PAYMENT_RE = re.compile(r"^PAY-SYN-[A-Z0-9]{3,8}$")
EXCEPTION_RE = re.compile(r"^EXC-SYN-[A-Z0-9]{3,8}$")


class InvestigationStopped(RuntimeError):
    """Cooperative investigation boundary was cancelled or expired."""


@dataclass
class InvocationBudget:
    started: float
    deadline: float
    cancelled: Callable[[], bool]
    iterations: int = 0

    @classmethod
    def start(
        cls,
        monotonic: Callable[[], float],
        cancelled: Callable[[], bool],
        caller_deadline: float | None = None,
    ) -> InvocationBudget:
        started = monotonic()
        deadline = (
            min(started + 30.0, caller_deadline) if caller_deadline is not None else started + 30.0
        )
        return cls(started=started, deadline=deadline, cancelled=cancelled)

    def check(self, monotonic: Callable[[], float], *, model_iteration: bool = False) -> None:
        if self.cancelled():
            raise InvestigationStopped("investigation cancelled")
        if monotonic() >= self.deadline:
            raise InvestigationStopped("caller deadline expired")
        if model_iteration:
            if self.iterations >= 4:
                raise InvestigationStopped("four-iteration budget exhausted")
            self.iterations += 1


class _SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class _FixtureClock(_SystemClock):
    def __init__(self, value: str) -> None:
        self._now = datetime.fromisoformat(value.replace("Z", "+00:00"))

    def now(self) -> datetime:
        return self._now


class LogicalDemoClock(_SystemClock):
    """Synthetic time anchored to the fixture clock and advanced by monotonic elapsed time."""

    def __init__(self, value: str, monotonic: Callable[[], float] = time.monotonic) -> None:
        self._anchor = datetime.fromisoformat(value.replace("Z", "+00:00"))
        self._monotonic = monotonic
        self._started = monotonic()

    def now(self) -> datetime:
        elapsed = max(0.0, self.monotonic() - self._started)
        return self._anchor + timedelta(seconds=elapsed)

    def monotonic(self) -> float:
        return self._monotonic()


class ReceivablesInvestigationEngine:
    def __init__(
        self,
        source: ReadOnlySource,
        catalogue: ApprovedCatalogue | None = None,
        clock: Clock | None = None,
        audit_sink: Callable[[TrustedContext, AuditEvent], None] | None = None,
    ) -> None:
        self.source = source
        self.catalogue = catalogue or load_approved_catalogue()
        self.clock = clock or _FixtureClock(self.catalogue.fixture["fixed_clock"])
        self.audit_sink = audit_sink
        self.audit_proposals = True
        self.completed_checks = 0
        self.returned_proposals = 0

    def investigate(
        self,
        context: TrustedContext,
        payment_id: str,
        exception_type: str = "amount_reference_mismatch",
        *,
        customer_id: str = "CORP-SYN-001",
        currency: str = "USD",
        cancelled: Callable[[], bool] = lambda: False,
        caller_deadline: float | None = None,
    ) -> InvestigationProposal:
        require_context(context, tenant_id=self.catalogue.fixture["tenant_id"])
        if (
            not PAYMENT_RE.fullmatch(payment_id)
            or exception_type not in self.catalogue.policy.exception_types
            or customer_id != "CORP-SYN-001"
            or currency != "USD"
        ):
            return self._proposal(
                context,
                payment_id or "UNKNOWN",
                exception_type,
                Outcome.OUT_OF_SCOPE,
                "OUT_OF_SCOPE",
                None,
                None,
                None,
                None,
                None,
                None,
                (),
                None,
                "No source reads were made because this request is outside the synthetic scope.",
            )
        budget = InvocationBudget.start(self.clock.monotonic, cancelled, caller_deadline)
        results: list[tuple[EvidenceType, SourceResult]] = []
        for source_type in SOURCE_ORDER:
            budget.check(self.clock.monotonic)
            result = self.source.read(context, source_type, payment_id)
            budget.check(self.clock.monotonic)
            if self.audit_sink is not None:
                budget.check(self.clock.monotonic)
                event = AuditEvent(
                    event_id=hashlib.sha256(
                        f"{context.correlation_id}:{source_type.value}:{len(results)}".encode()
                    ).hexdigest(),
                    correlation_id=context.correlation_id,
                    sequence=0,
                    event_type="retrieval",
                    actor=context.user_id,
                    source_refs=tuple(record.source_record_id for record in result.records),
                    policy_version=self.catalogue.policy.version,
                    safe_summary=f"Retrieved {source_type.value} evidence ({result.status.value})",
                    created_at=self.clock.now(),
                )
                self.audit_sink(context, event)
            budget.check(self.clock.monotonic)
            if len(result.records) > 20:
                return self._proposal(
                    context,
                    payment_id,
                    exception_type,
                    Outcome.ESCALATE,
                    "EVIDENCE_MALFORMED",
                    "amount_reference_mismatch",
                    None,
                    None,
                    None,
                    None,
                    self.catalogue.policy,
                    (),
                    None,
                    "Source result exceeded the bounded row limit.",
                )
            results.append((source_type, result))
        statuses = {kind: result.status for kind, result in results}
        records = {kind: list(result.records) for kind, result in results}
        now = self.clock.now()
        reasons: list[str] = []
        availability_reason = {
            Availability.PARTIAL: "EVIDENCE_PARTIAL",
            Availability.UNAVAILABLE: "EVIDENCE_UNAVAILABLE",
            Availability.MALFORMED: "EVIDENCE_MALFORMED",
            Availability.CONFLICTING: "EVIDENCE_CONFLICT",
        }
        for kind, status in statuses.items():
            if status != Availability.AVAILABLE:
                reasons.append(availability_reason.get(status, "EVIDENCE_UNAVAILABLE"))
            max_age = self.catalogue.policy.freshness_max_age_seconds.get(kind.value)
            if max_age is not None:
                result = dict(results)[kind]
                state, _ = freshness(result.as_of, now, max_age)
                if state == Freshness.STALE:
                    reasons.append("EVIDENCE_STALE")
                elif state == Freshness.UNKNOWN:
                    reasons.append("EVIDENCE_MALFORMED")
        policy = self.catalogue.policy
        policy_rows = records[EvidenceType.POLICY]
        if not policy_rows:
            reasons.append(
                "POLICY_MISSING"
                if statuses[EvidenceType.POLICY] == Availability.UNAVAILABLE
                else "POLICY_UNAPPROVED"
            )
        elif len(policy_rows) != 1:
            reasons.append("POLICY_SOURCE_MISMATCH")
        else:
            source_policy = policy_rows[0]
            source_values = dict(source_policy.values)
            try:
                declared_digest = source_values.get("declared_policy_digest")
                if declared_digest != canonical_record_digest(source_policy):
                    reasons.append("POLICY_SOURCE_MISMATCH")
                if source_values.get("approval_status_current") != "approved_synthetic_test_only":
                    reasons.append("POLICY_UNAPPROVED")
                policy = PolicyRecord(
                    **{
                        key: source_values[key]
                        for key in (
                            "policy_id",
                            "version",
                            "tenant_id",
                            "currency",
                            "exception_types",
                            "effective_from",
                            "effective_to",
                            "tolerance_abs",
                            "tolerance_pct",
                            "weights",
                            "bands",
                            "competing_margin",
                            "duplicate_window_days",
                            "proposal_ttl_minutes",
                            "confirmation_window_minutes",
                        )
                    },
                    approval_status=str(source_values.get("approval_status_current", "")),
                    approval_record_ref=str(source_values.get("approval_record_ref") or ""),
                    freshness_max_age_seconds=self.catalogue.policy.freshness_max_age_seconds,
                )
            except (KeyError, TypeError, ValueError):
                reasons.append("EVIDENCE_MALFORMED")
                policy = self.catalogue.policy
            if policy.tenant_id != context.tenant_id:
                reasons.append("POLICY_SOURCE_MISMATCH")
            if not policy_is_effective(policy.effective_from, policy.effective_to, now.date()):
                reasons.append("POLICY_EXPIRED")
            if policy.currency != currency or exception_type not in policy.exception_types:
                reasons.append("POLICY_INAPPLICABLE")
        payment_record = records[EvidenceType.PAYMENT][0] if records[EvidenceType.PAYMENT] else None
        payment = dict(payment_record.values) if payment_record else {}
        customer_records = records[EvidenceType.CUSTOMER]
        customer = dict(customer_records[0].values) if customer_records else {}
        invoices = [dict(record.values) for record in records[EvidenceType.INVOICE]]
        va_rows = [dict(record.values) for record in records[EvidenceType.VIRTUAL_ACCOUNT]]
        history = [dict(record.values) for record in records[EvidenceType.PAYMENT_HISTORY]]
        allocations = [dict(record.values) for record in records[EvidenceType.ALLOCATION_LEDGER]]
        if not payment_record or not customer_records:
            reasons.append("EVIDENCE_UNAVAILABLE")
        if (
            payment.get("va_id")
            and len(va_rows) != 1
            and statuses[EvidenceType.VIRTUAL_ACCOUNT] == Availability.AVAILABLE
        ):
            reasons.append("MAPPING_ABSENT" if not va_rows else "EVIDENCE_CONFLICT")
        mapping_valid, mapping_reason = (
            mapping_status(
                payment,
                va_rows,
                customer.get("customer_id", customer_id),
                payment.get("value_date", "0000-00-00"),
            )
            if payment
            else (False, "MAPPING_MISSING_ID")
        )
        if not mapping_valid:
            reasons.append(mapping_reason)
        try:
            amount = payment.get("amount")
            if not isinstance(amount, str) or not amount:
                raise ValueError("payment amount is absent or not a schema string")
            candidates = (
                rank_candidates(
                    payment, invoices, customer.get("customer_id", customer_id), currency, policy
                )
                if invoices
                else ()
            )
        except (ValueError, KeyError, ArithmeticError):
            reasons.append("EVIDENCE_MALFORMED")
            candidates = ()
        for candidate in candidates:
            if candidate.exclusion_reason:
                reasons.append(candidate.exclusion_reason)
        try:
            duplicate = (
                duplicate_status(payment, history, policy)
                if payment and payment.get("amount")
                else "unknown"
            )
        except (ValueError, KeyError, ArithmeticError):
            duplicate = "unknown"
            reasons.append("EVIDENCE_MALFORMED")
        prior, prior_reason = prior_allocation_status(payment_id, candidates, allocations)
        mapping_determinable = (
            statuses[EvidenceType.VIRTUAL_ACCOUNT]
            in {Availability.AVAILABLE, Availability.CONFLICTING}
            and statuses[EvidenceType.PAYMENT] == Availability.AVAILABLE
        )
        classification = classify_exception(
            mapping_valid, mapping_reason, duplicate, prior, determinable=mapping_determinable
        )
        if duplicate in {"suspected", "confirmed"}:
            reasons.append("DUP_" + duplicate.upper())
        if (
            duplicate == "clear"
            and statuses[EvidenceType.PAYMENT_HISTORY] != Availability.AVAILABLE
        ):
            duplicate = "unknown"
            reasons.append("DUP_UNKNOWN")
        if prior_reason:
            reasons.append(prior_reason)
        if statuses[EvidenceType.ALLOCATION_LEDGER] != Availability.AVAILABLE:
            prior = "unknown"
            reasons.append("PRIOR_ALLOC_UNKNOWN")
        valid_candidates = [item for item in candidates if item.eligible and item.score > 0]
        competing = competing_candidates(candidates, policy.competing_margin)
        if not valid_candidates:
            reasons.append("NO_CANDIDATE")
        if competing:
            reasons.append("COMPETING_CANDIDATES")
        if valid_candidates and valid_candidates[0].band == "low":
            reasons.append("LOW_CONFIDENCE")
        partial = any(status == Availability.PARTIAL for status in statuses.values())
        if partial:
            primary = "EVIDENCE_PARTIAL"
            outcome = Outcome.ESCALATE
        elif any(reason.startswith("POLICY_") for reason in reasons):
            primary = next(reason for reason in reasons if reason.startswith("POLICY_"))
            outcome = Outcome.ESCALATE
        elif (
            any(status != Availability.AVAILABLE for status in statuses.values())
            or "EVIDENCE_STALE" in reasons
            or "EVIDENCE_MALFORMED" in reasons
            or "EVIDENCE_CONFLICT" in reasons
        ):
            primary = next(
                (reason for reason in reasons if reason.startswith("EVIDENCE_")),
                "EVIDENCE_UNAVAILABLE",
            )
            outcome = Outcome.ESCALATE
        elif (
            not mapping_valid
            or duplicate in {"suspected", "confirmed", "unknown"}
            or prior != "clear"
        ):
            if not mapping_valid:
                primary = mapping_reason
            elif prior_reason:
                primary = prior_reason
            elif duplicate in {"suspected", "confirmed", "unknown"}:
                primary = f"DUP_{duplicate.upper()}"
            else:
                primary = "DUP_UNKNOWN"
            outcome = Outcome.ESCALATE
        elif competing:
            primary = "COMPETING_CANDIDATES"
            outcome = Outcome.ESCALATE
        elif not valid_candidates:
            tokens = set(reference_tokens(str(payment.get("remittance_reference", ""))))
            matched_exclusion = None
            for candidate in candidates:
                record = next(
                    (
                        item
                        for item in records[EvidenceType.INVOICE]
                        if item.source_record_id == candidate.invoice_id
                    ),
                    None,
                )
                reference = str(record.values.get("reference", "")) if record else ""
                if candidate.exclusion_reason and tokens.intersection(reference_tokens(reference)):
                    matched_exclusion = candidate.exclusion_reason
                    break
            primary = matched_exclusion or next(
                (reason for reason in reasons if reason in {"NO_CANDIDATE", "LOW_CONFIDENCE"}),
                "NO_CANDIDATE",
            )
            outcome = Outcome.ESCALATE
        elif valid_candidates[0].band == "low":
            primary = "LOW_CONFIDENCE"
            outcome = Outcome.ESCALATE
        elif valid_candidates[0].band == "medium":
            primary = "MEDIUM_CONFIDENCE_VARIANCE_OUT_OF_TOLERANCE"
            outcome = Outcome.NO_RECOMMENDATION
        else:
            primary = "NONE"
            outcome = Outcome.RECOMMEND
        records_for_manifest = [record for _, result in results for record in result.records]
        try:
            manifest = build_snapshot_manifest(records_for_manifest)
            citations = self._citations(results, manifest, now)
            citations = self._inference_citations(
                citations, payment, records[EvidenceType.INVOICE], customer
            )
        except (ValueError, KeyError) as exc:
            manifest = None
            citations = ()
            outcome = Outcome.ESCALATE
            primary = "EVIDENCE_CONFLICT"
            reasons.append(f"TRACE_VALIDATION: {exc}")
        proposed = (
            valid_candidates[0] if outcome == Outcome.RECOMMEND and valid_candidates else None
        )
        reported_candidate = proposed or (
            valid_candidates[0]
            if outcome == Outcome.NO_RECOMMENDATION and valid_candidates
            else None
        )
        next_step = None
        if partial:
            partial_names = ", ".join(
                kind.value for kind, status in statuses.items() if status == Availability.PARTIAL
            )
            next_step = (
                f"Refresh or complete {partial_names}, rerun the investigation, "
                "and route for human review if still incomplete."
            )
        elif outcome != Outcome.RECOMMEND:
            next_step = (
                "Refresh or reconcile the cited synthetic evidence and "
                "route to an analyst for review."
            )
        self.completed_checks += 1
        if self.audit_sink is not None:
            budget.check(self.clock.monotonic)
            self.audit_sink(
                context,
                AuditEvent(
                    event_id=hashlib.sha256(
                        f"{context.correlation_id}:check:{payment_id}".encode()
                    ).hexdigest(),
                    correlation_id=context.correlation_id,
                    sequence=0,
                    event_type="check",
                    actor=context.user_id,
                    source_refs=tuple(
                        record.source_record_id for rows in records.values() for record in rows
                    ),
                    policy_version=policy.version,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    safe_summary=f"Deterministic checks completed with {outcome.value}",
                    created_at=now,
                ),
            )
        disclosures = self._disclosures(results, now)
        return self._proposal(
            context,
            payment_id,
            exception_type,
            outcome,
            primary,
            classification,
            proposed.invoice_id if proposed else None,
            Decimal(str(payment["amount"]))
            if reported_candidate and payment.get("amount")
            else None,
            reported_candidate.expected_amount if reported_candidate else None,
            reported_candidate.variance if reported_candidate else None,
            policy,
            citations,
            manifest,
            next_step,
            tuple(candidates),
            tuple(dict.fromkeys(reasons)),
            disclosures,
            duplicate=duplicate,
            prior=prior,
        )

    def _citations(
        self,
        results: list[tuple[EvidenceType, SourceResult]],
        manifest: SnapshotManifest,
        now: datetime,
    ) -> tuple[EvidenceCitation, ...]:
        citations = []
        for source_type, raw_result in results:
            for record in raw_result.records:
                entry = next(
                    (
                        item
                        for item in manifest.entries
                        if item.source_type == record.source_type
                        and item.source_record_id == record.source_record_id
                        and item.source_version == record.source_version
                    ),
                    None,
                )
                if entry is None:
                    raise ValueError("citation cannot resolve to a unique snapshot entry")
                digest = canonical_record_digest(record)
                if digest != entry.record_digest:
                    raise ValueError("citation record digest mismatch")
                state, age = freshness(
                    raw_result.as_of,
                    now,
                    self.catalogue.policy.freshness_max_age_seconds.get(source_type.value, 86400),
                )
                if age is None or age < 0:
                    age = 0
                kind = "source_fact"
                classification = EvidenceClassification.AUTHORITATIVE
                citations.append(
                    EvidenceCitation(
                        source_type=source_type,
                        source_record_id=record.source_record_id,
                        snapshot_id=manifest.snapshot_id,
                        snapshot_version=manifest.snapshot_version,
                        record_digest=entry.record_digest,
                        classification=classification,
                        evidence_kind=kind,
                        as_of=raw_result.as_of,
                        age_seconds=age,
                        availability=raw_result.status,
                        freshness=state if state != Freshness.UNKNOWN else Freshness.STALE,
                    )
                )
        return tuple(citations)

    def _disclosures(
        self, results: list[tuple[EvidenceType, SourceResult]], now: datetime
    ) -> tuple[EvidenceDisclosure, ...]:
        disclosures = []
        for source_type, raw_result in results:
            maximum = self.catalogue.policy.freshness_max_age_seconds.get(source_type.value, 86400)
            state, age = freshness(raw_result.as_of, now, maximum)
            details = {
                Availability.PARTIAL: "Required source result is incomplete.",
                Availability.UNAVAILABLE: "Required source result is unavailable.",
                Availability.MALFORMED: "Required source result is malformed.",
                Availability.CONFLICTING: "Required source result contains conflicting records.",
            }
            disclosures.append(
                EvidenceDisclosure(
                    source_type=source_type,
                    availability=raw_result.status,
                    freshness=state,
                    as_of=raw_result.as_of,
                    age_seconds=age,
                    safe_detail=details.get(raw_result.status),
                )
            )
        return tuple(disclosures)

    def _inference_citations(
        self,
        citations: tuple[EvidenceCitation, ...],
        payment: dict[str, object],
        invoices: list[SourceRecord],
        customer: dict[str, object],
    ) -> tuple[EvidenceCitation, ...]:
        inferred: list[EvidenceCitation] = []
        tokens = set(reference_tokens(str(payment.get("remittance_reference", ""))))
        for citation in citations:
            if citation.source_type == EvidenceType.INVOICE:
                record = next(
                    (
                        item
                        for item in invoices
                        if item.source_record_id == citation.source_record_id
                    ),
                    None,
                )
                reference = str(record.values.get("reference", "")) if record else ""
                if tokens.intersection(reference_tokens(reference)):
                    inferred.append(
                        citation.model_copy(
                            update={
                                "classification": EvidenceClassification.INFERENCE,
                                "evidence_kind": "reference_match",
                            }
                        )
                    )
            if citation.source_type == EvidenceType.CUSTOMER:
                names = customer.get("known_payer_names", [])
                payer = payment.get("payer_name")
                if isinstance(names, (list, tuple)) and payer and payer in names:
                    inferred.append(
                        citation.model_copy(
                            update={
                                "classification": EvidenceClassification.INFERENCE,
                                "evidence_kind": "payer_name_match",
                            }
                        )
                    )
        return citations + tuple(inferred)

    def _proposal(
        self,
        context: TrustedContext,
        payment_id: str,
        exception_type: str,
        outcome: Outcome,
        primary: str,
        classification: str | None,
        invoice_id: str | None,
        payment_amount: Decimal | None,
        expected_amount: Decimal | None,
        variance: Decimal | None,
        policy: PolicyRecord | None,
        evidence: tuple[EvidenceCitation, ...],
        snapshot: SnapshotManifest | None,
        next_step: str | None,
        candidates: tuple[CandidateAllocation, ...] = (),
        secondary: tuple[str, ...] = (),
        disclosures: tuple[EvidenceDisclosure, ...] = (),
        duplicate: str = "unknown",
        prior: str = "unknown",
    ) -> InvestigationProposal:
        now = self.clock.now()
        proposal_id = f"PROP-SYN-{payment_id.removeprefix('PAY-SYN-')}-1"
        payload = {
            "proposal_id": proposal_id,
            "outcome": outcome.value,
            "reason": primary,
            "invoice": invoice_id,
            "payment": payment_id,
            "exception_type": exception_type,
        }
        content_hash = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        proposal = InvestigationProposal(
            proposal_id=proposal_id,
            exception_id=f"EXC-SYN-{payment_id.removeprefix('PAY-SYN-')}",
            payment_id=payment_id,
            version=1,
            outcome=outcome,
            classification=classification,
            primary_reason=primary,
            duplicate_status=CheckStatus(duplicate),
            prior_allocation_status=AllocationCheckStatus(prior),
            secondary_reasons=secondary,
            proposed_invoice_id=invoice_id,
            payment_amount=payment_amount,
            expected_amount=expected_amount,
            variance=variance,
            currency="USD",
            policy_id=getattr(policy, "policy_id", None),
            policy_version=getattr(policy, "version", None),
            evidence=evidence,
            evidence_statuses=disclosures,
            snapshot=snapshot,
            created_at=now,
            expires_at=now + timedelta(minutes=getattr(policy, "proposal_ttl_minutes", 30)),
            draft_operations_note=f"Synthetic investigation {outcome.value}: {primary}.",
            safe_next_step=next_step,
            content_hash=content_hash,
            candidates=candidates,
        )
        if self.audit_sink is not None and self.audit_proposals:
            self.audit_sink(
                context,
                AuditEvent(
                    event_id=hashlib.sha256(
                        f"{context.correlation_id}:proposal:{proposal.proposal_id}:"
                        f"{proposal.version}:{self.returned_proposals + 1}".encode()
                    ).hexdigest(),
                    correlation_id=context.correlation_id,
                    sequence=0,
                    event_type="proposal",
                    actor=context.user_id,
                    source_refs=tuple(item.source_record_id for item in proposal.evidence),
                    policy_version=proposal.policy_version,
                    reason_codes=(proposal.primary_reason, *proposal.secondary_reasons),
                    proposal_version=proposal.version,
                    proposal_id=proposal.proposal_id,
                    safe_summary=f"Returned proposal {proposal.version}: {proposal.outcome.value}",
                    created_at=now,
                ),
            )
        self.returned_proposals += 1
        return proposal
