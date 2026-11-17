from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from aria.agents.aria.receivables.models import (
    AuditEvent,
    EvidenceType,
    InvestigationProposal,
    Outcome,
)
from aria.agents.aria.receivables.policy import verify_snapshot_manifest


def _trace_valid(proposal: InvestigationProposal) -> bool:
    if proposal.snapshot is None or not proposal.evidence:
        return False
    try:
        verify_snapshot_manifest(proposal.snapshot)
    except ValueError:
        return False
    for citation in proposal.evidence:
        entries = [
            item
            for item in proposal.snapshot.entries
            if item.source_type == citation.source_type
            and item.source_record_id == citation.source_record_id
            and item.record_digest == citation.record_digest
        ]
        if (
            len(entries) != 1
            or citation.snapshot_id != proposal.snapshot.snapshot_id
            or citation.snapshot_version != proposal.snapshot.snapshot_version
        ):
            return False
    return True


def _variance_valid(
    proposal: InvestigationProposal, case: dict[str, Any], fixture: dict[str, Any] | None
) -> bool:
    """Independent Decimal recomputation from immutable input, not engine formulas/labels."""
    if fixture is None:
        return False
    try:
        payment = {**fixture["payment_defaults"], **case["payment"]}
        amount = Decimal(payment["amount"])
        invoices = {
            row["invoice_id"]: Decimal(row["outstanding_amount"]) for row in fixture["invoices"]
        }
        expected = invoices[proposal.proposed_invoice_id]
        return (
            amount.is_finite()
            and expected.is_finite()
            and proposal.payment_amount == amount
            and proposal.expected_amount == expected
            and proposal.variance == amount - expected
            and all(
                candidate.expected_amount == invoices[candidate.invoice_id]
                and candidate.variance == amount - invoices[candidate.invoice_id]
                for candidate in proposal.candidates
            )
        )
    except (KeyError, TypeError, InvalidOperation):
        return False


def catalogue_metrics(
    cases: list[dict[str, Any]],
    proposals: list[InvestigationProposal],
    *,
    coverage: dict[str, int] | None = None,
    fixture: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score fixed E-path denominators; trace errors are not business escalations."""
    observed = {proposal.payment_id: proposal for proposal in proposals}
    classification_scored = [
        case for case in cases if case["expected"].get("classification_scored")
    ]
    unscored = sum(not bool(case["expected"].get("classification_scored")) for case in cases)
    by_class: Counter[str] = Counter()
    strata: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "classification_correct": 0,
            "top_candidate_correct": 0,
            "escalation_required": 0,
            "escalation_correct": 0,
        }
    )
    dispositions: Counter[str] = Counter()
    class_correct = top_correct = escalation_correct = false_escalations = (
        confident_nonallocatable
    ) = 0
    recommendation_count = correct_recommendations = allocatable_recommendations = (
        incorrect_recommendations
    ) = 0
    citation_count = citation_valid = trace_failures = errors = abstentions = 0
    required_total = required_correct = not_required_total = 0
    evidence_complete_recommendations = 0
    variance_correct = 0
    label_checks: dict[str, Counter[str]] = defaultdict(Counter)
    label_mismatches: list[dict[str, Any]] = []
    recommendation_evidence_checks: list[dict[str, Any]] = []
    error_cases: list[str] = []
    for case in cases:
        expected = case["expected"]
        stratum = str(case.get("stratum", "unlabelled"))
        row = strata[stratum]
        row["total"] += 1
        if "classification" in expected and expected.get("classification") is not None:
            by_class[str(expected["classification"])] += 1
        proposal = observed.get(case.get("payment", {}).get("payment_id", ""))
        if proposal is None:
            errors += 1
            abstentions += 1
            dispositions["error"] += 1
            trace_failures += 1
            effective_outcome = None
            prediction = None
            ranked: list[str] = []
        else:
            trace_ok = _trace_valid(proposal)
            citation_count += len(proposal.evidence)
            if trace_ok:
                citation_valid += len(proposal.evidence)
            else:
                trace_failures += 1
            if not trace_ok:
                errors += 1
                effective_outcome = None
                prediction = None
                ranked = []
            else:
                effective_outcome = proposal.outcome
                prediction = proposal.classification
                ranked = [
                    candidate.invoice_id
                    for candidate in proposal.candidates
                    if candidate.eligible and candidate.score > 0
                ]
            dispositions[effective_outcome.value if effective_outcome is not None else "error"] += 1
            if effective_outcome != Outcome.RECOMMEND:
                abstentions += 1
        if effective_outcome is None:
            error_cases.append(case["id"])
        if proposal is not None:
            actual_labels = {
                "primary_reason": proposal.primary_reason,
                "variance": str(proposal.variance) if proposal.variance is not None else None,
                "duplicate_status": proposal.duplicate_status.value,
                "prior_allocation_status": proposal.prior_allocation_status.value,
            }
        else:
            actual_labels = {}
        for name in ("primary_reason", "variance", "duplicate_status", "prior_allocation_status"):
            if name in expected:
                match = actual_labels.get(name) == expected[name]
                if name == "variance" and actual_labels.get(name) is not None:
                    match = Decimal(str(actual_labels[name])) == Decimal(expected[name])
                match = match and effective_outcome is not None
                label_checks[name]["denominator"] += 1
                label_checks[name]["correct"] += int(match)
                if not match:
                    label_mismatches.append(
                        {
                            "case_id": case["id"],
                            "field": name,
                            "expected": expected[name],
                            "actual": actual_labels.get(name),
                            "trace_valid": effective_outcome is not None,
                        }
                    )
        if expected.get("classification_scored"):
            correct = prediction == expected.get("classification")
            class_correct += int(correct)
            row["classification_correct"] += int(correct)
        acceptable = set(expected.get("acceptable_invoice_ids", []))
        allocatable = bool(expected.get("allocatable"))
        correct_top = allocatable and bool(ranked) and ranked[0] in acceptable
        if allocatable:
            top_correct += int(correct_top)
            row["top_candidate_correct"] += int(correct_top)
        if proposal is not None and proposal.outcome == Outcome.RECOMMEND:
            recommendation_count += 1
            allocatable_recommendations += 1
            if correct_top:
                correct_recommendations += 1
            else:
                incorrect_recommendations += 1
            statuses = (
                {
                    item.source_type.value: item.availability.value
                    for item in proposal.evidence_statuses
                }
                if proposal is not None
                else {}
            )
            recomputed = effective_outcome == Outcome.RECOMMEND and _variance_valid(
                proposal, case, fixture
            )
            variance_correct += int(recomputed)
            cited_types = (
                {item.source_type for item in proposal.evidence} if proposal is not None else set()
            )
            recommendation_evidence_checks.append(
                {
                    "case_id": case["id"],
                    "distinct_citation_types": sorted(item.value for item in cited_types),
                    "missing_citation_types": sorted(
                        item.value for item in set(EvidenceType) - cited_types
                    ),
                    "variance_recomputed_exactly": recomputed,
                    "availability": statuses,
                }
            )
            fresh = all(item.freshness.value == "fresh" for item in proposal.evidence_statuses)
            fresh = fresh and all(
                item.freshness.value == "fresh" and item.availability.value == "available"
                for item in proposal.evidence
            )
            if (
                recomputed
                and fresh
                and cited_types == set(EvidenceType)
                and statuses
                == {
                    "payment": "available",
                    "virtual_account": "available",
                    "customer": "available",
                    "invoice": "available",
                    "payment_history": "available",
                    "allocation_ledger": "available",
                    "policy": "available",
                }
            ):
                evidence_complete_recommendations += 1
            if not allocatable:
                confident_nonallocatable += 1
        escalation_required = expected.get("escalation_required")
        if escalation_required is True:
            required_total += 1
            row["escalation_required"] += 1
            correct = effective_outcome == Outcome.ESCALATE
            required_correct += int(correct)
            escalation_correct += int(correct)
            row["escalation_correct"] += int(correct)
        elif escalation_required is False:
            not_required_total += 1
            false_escalations += int(effective_outcome == Outcome.ESCALATE)
    top_denominator = sum(bool(case["expected"].get("allocatable")) for case in cases)
    class_denominator = len(classification_scored)
    escalation_denominator = required_total
    coverage_result = {
        key: {"calls": value, "status": "measured" if value > 0 else "unexercised"}
        for key, value in (coverage or {}).items()
    }
    return {
        "error_cases": error_cases,
        "recommendation_evidence_checks": recommendation_evidence_checks,
        "fixture_label_checks": {key: dict(value) for key, value in label_checks.items()},
        "fixture_label_mismatches": label_mismatches,
        "variance_recomputation": {
            "correct": variance_correct,
            "denominator": recommendation_count,
        },
        "classification": {
            "correct": class_correct,
            "denominator": class_denominator,
            "unscored_by_label": unscored,
            "by_expected_class": dict(by_class),
            "rate": class_correct / class_denominator if class_denominator else "N/A",
        },
        "top_candidate": {
            "correct": top_correct,
            "denominator": top_denominator,
            "rate": top_correct / top_denominator if top_denominator else "N/A",
        },
        "recommendation": {
            "precision_numerator": correct_recommendations,
            "precision_denominator": recommendation_count,
            "precision": correct_recommendations / recommendation_count
            if recommendation_count
            else "N/A",
            "incorrect_allocations": incorrect_recommendations,
            "incorrect_allocation_denominator": allocatable_recommendations,
            "confident_nonallocatable": confident_nonallocatable,
        },
        "citation_completeness": {
            "complete_recommendations": evidence_complete_recommendations,
            "recommendations": recommendation_count,
            "rate": evidence_complete_recommendations / recommendation_count
            if recommendation_count
            else "N/A",
        },
        "escalation": {
            "labelled_cases": required_total + not_required_total,
            "correct_required": required_correct,
            "required_denominator": required_total,
            "false_escalations": false_escalations,
            "not_required_denominator": not_required_total,
            "correct": escalation_correct,
            "denominator": escalation_denominator,
            "rate": escalation_correct / escalation_denominator
            if escalation_denominator
            else "N/A",
        },
        "strata": {key: dict(value) for key, value in sorted(strata.items())},
        "dispositions": dict(dispositions),
        "abstentions": abstentions,
        "errors": errors,
        "unlabelled_cases": sum("classification" not in case["expected"] for case in cases),
        "citation_trace": {
            "valid": citation_valid,
            "cited": citation_count,
            "failures": trace_failures,
        },
        "coverage": coverage_result,
        "claims": "no success-target claim; synthetic conformance only",
    }


def workflow_metrics(
    *,
    source_calls: dict[str, int],
    write_attempts: dict[str, int],
    write_calls: dict[str, int],
    committed_rows: dict[str, int],
    expected_events: dict[str, int],
    observed_events: dict[str, int],
    tasks_created: int,
    fixture_hash_before: str,
    fixture_hash_after: str,
) -> dict[str, Any]:
    return {
        "source_reads": sum(source_calls.values()),
        "source_surfaces": {
            key: {"calls": count, "status": "measured" if count else "unexercised"}
            for key, count in source_calls.items()
        },
        "writer_surfaces": {
            key: {
                "attempts": write_attempts.get(key, 0),
                "calls": count,
                "status": "measured" if write_attempts.get(key, 0) or count else "unexercised",
            }
            for key, count in write_calls.items()
        },
        "committed_rows": committed_rows,
        "tasks_created": tasks_created,
        "audit_events": sum(observed_events.values()),
        "audit_correspondence": {
            "missing": {
                key: count - observed_events.get(key, 0)
                for key, count in expected_events.items()
                if count > observed_events.get(key, 0)
            },
            "unexpected": {
                key: count - expected_events.get(key, 0)
                for key, count in observed_events.items()
                if count > expected_events.get(key, 0)
            },
            "expected": expected_events,
            "observed": observed_events,
            "matches": expected_events == observed_events,
        },
        "fixture_hash_before": fixture_hash_before,
        "fixture_hash_after": fixture_hash_after,
        "fixture_unchanged": fixture_hash_before == fixture_hash_after,
        "unmeasured": ["network", "AWS", "production_writers"],
        "claim_scope": (
            "instrumented local synthetic surfaces only; successful SQL calls may roll back"
        ),
    }


def audit_event_counts(events: list[AuditEvent]) -> dict[str, int]:
    """Retain source identity in retrieval counts, rather than a single surface flag."""
    counts: Counter[str] = Counter()
    for event in events:
        key = event.event_type
        if key == "retrieval":
            key += ":" + event.safe_summary.split()[1]
        counts[key] += 1
    return dict(counts)


def retrieval_correspondence(
    reads: list[dict[str, Any]], events: list[AuditEvent]
) -> dict[str, Any]:
    """Compare actual source returns to audited type, references AND availability.

    This is stricter than event totals. A failed audit is a measured gap, not
    removed from the denominator or silently credited as a correspondence.
    """
    expected = Counter(
        (str(row["source_type"]), tuple(row["source_refs"]), str(row["availability"]))
        for row in reads
    )
    observed = Counter(
        (
            event.safe_summary.split()[1],
            tuple(event.source_refs),
            event.safe_summary.split()[-1].strip("()"),
        )
        for event in events
        if event.event_type == "retrieval"
    )
    return {
        "expected": sum(expected.values()),
        "observed": sum(observed.values()),
        "matched": sum((expected & observed).values()),
        "matches": expected == observed,
        "missing": [
            {
                "source_type": key[0],
                "source_refs": list(key[1]),
                "availability": key[2],
                "calls": count,
            }
            for key, count in (expected - observed).items()
        ],
        "unexpected": [
            {
                "source_type": key[0],
                "source_refs": list(key[1]),
                "availability": key[2],
                "calls": count,
            }
            for key, count in (observed - expected).items()
        ],
    }
