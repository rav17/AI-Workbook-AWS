from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from aria.agents.aria.receivables.models import CandidateAllocation, PolicyRecord

REFERENCE_PATTERN = re.compile(r"(?i)\bINV[-\s]?(\d{4})\b")
SUPPORTED_CATEGORIES = {"invalid_mapping", "amount_reference_mismatch", "suspected_duplicate"}


def reference_tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(f"INV{match}" for match in REFERENCE_PATTERN.findall(value or "")))


def calculate_variance(payment_amount: str | Decimal, expected_amount: str | Decimal) -> Decimal:
    return Decimal(str(payment_amount)) - Decimal(str(expected_amount))


def within_tolerance(variance: Decimal, outstanding: Decimal, policy: PolicyRecord) -> bool:
    return (
        abs(variance) <= policy.tolerance_abs
        and abs(variance) <= outstanding * policy.tolerance_pct
    )


def mapping_status(
    payment: dict[str, Any],
    virtual_accounts: list[dict[str, Any]],
    customer_id: str,
    value_date: str,
) -> tuple[bool, str]:
    va_id = payment.get("va_id")
    if not va_id:
        return False, "MAPPING_MISSING_ID"
    matches = [row for row in virtual_accounts if row.get("va_id") == va_id]
    if not matches:
        return False, "MAPPING_ABSENT"
    if len(matches) != 1:
        return False, "EVIDENCE_CONFLICT"
    account = matches[0]
    if account.get("status") != "active":
        return False, "MAPPING_EXPIRED" if account.get(
            "status"
        ) == "expired" else "MAPPING_INACTIVE"
    if account.get("customer_id") != customer_id:
        return False, "MAPPING_CUSTOMER_MISMATCH"
    if not (account["effective_from"] <= value_date <= account["effective_to"]):
        return False, "MAPPING_OUTSIDE_EFFECTIVE_DATES"
    return True, "NONE"


def classify_exception(
    mapping_valid: bool,
    mapping_reason: str,
    duplicate_status: str,
    prior_status: str,
    determinable: bool = True,
) -> str | None:
    if not determinable:
        return None
    if not mapping_valid:
        return "invalid_mapping"
    if duplicate_status in {"suspected", "confirmed"} or prior_status in {"present", "confirmed"}:
        return "suspected_duplicate"
    return "amount_reference_mismatch"


def rank_candidates(
    payment: dict[str, Any],
    invoices: list[dict[str, Any]],
    customer_id: str,
    currency: str,
    policy: PolicyRecord,
) -> tuple[CandidateAllocation, ...]:
    amount = Decimal(str(payment["amount"]))
    tokens = set(reference_tokens(str(payment.get("remittance_reference", ""))))
    result: list[CandidateAllocation] = []
    for invoice in invoices[:20]:
        status = invoice.get("status")
        invoice_customer = invoice.get("customer_id", customer_id)
        invoice_currency = invoice.get("currency", currency)
        eligible = (
            status in {"open", "partially_open"}
            and Decimal(str(invoice.get("outstanding_amount", "0"))) > 0
        )
        eligible = eligible and invoice_customer == customer_id and invoice_currency == currency
        reason = None
        if status in {"closed", "disputed"}:
            reason = f"INVOICE_INELIGIBLE_{status.upper()}"
        elif not eligible:
            reason = "INVOICE_INELIGIBLE_SCOPE"
        outstanding = Decimal(str(invoice.get("outstanding_amount", "0")))
        variance = calculate_variance(amount, outstanding)
        tolerance = within_tolerance(variance, outstanding, policy) if eligible else False
        reference_match = bool(
            tokens.intersection(reference_tokens(str(invoice.get("reference", ""))))
        )
        score = 0
        if eligible and reference_match:
            score += policy.weights["reference_exact"]
        if eligible and tolerance:
            score += policy.weights["amount_within_tolerance"]
        if eligible and variance == 0:
            score += policy.weights["amount_exact_bonus"]
        if score > 0 or not eligible:
            band = (
                "high"
                if score >= policy.bands["high_min"]
                else "medium"
                if score >= policy.bands["medium_min"]
                else "low"
            )
            result.append(
                CandidateAllocation(
                    invoice_id=invoice["invoice_id"],
                    eligible=eligible,
                    exclusion_reason=reason,
                    score=score,
                    band=band,
                    expected_amount=outstanding,
                    variance=variance,
                    within_tolerance=tolerance,
                )
            )
    return tuple(sorted(result, key=lambda item: (-item.score, item.invoice_id))[:20])


def competing_candidates(candidates: tuple[CandidateAllocation, ...], margin: int) -> bool:
    ranked = [candidate for candidate in candidates if candidate.eligible and candidate.score > 0]
    return len(ranked) > 1 and ranked[1].score >= ranked[0].score - margin


def duplicate_status(
    payment: dict[str, Any], history: list[dict[str, Any]], policy: PolicyRecord
) -> str:
    current_tokens = set(reference_tokens(str(payment.get("remittance_reference", ""))))
    matches: list[dict[str, Any]] = []
    for other in history:
        if other.get("payment_id") == payment.get("payment_id"):
            continue
        if other.get("va_id") != payment.get("va_id") or Decimal(
            str(other.get("amount", "-1"))
        ) != Decimal(str(payment.get("amount", "0"))):
            continue
        if not current_tokens or current_tokens != set(
            reference_tokens(str(other.get("remittance_reference", "")))
        ):
            continue
        delta = abs(
            (
                date.fromisoformat(other["value_date"]) - date.fromisoformat(payment["value_date"])
            ).days
        )
        if delta <= policy.duplicate_window_days:
            matches.append(other)
    if not matches:
        return "clear"
    if any(item.get("bank_reference") == payment.get("bank_reference") for item in matches):
        return "confirmed"
    return "suspected"


def prior_allocation_status(
    payment_id: str, candidates: tuple[CandidateAllocation, ...], allocations: list[dict[str, Any]]
) -> tuple[str, str | None]:
    candidate_ids = {row.invoice_id for row in candidates if row.eligible}
    # Any pending or posted allocation by another payment blocks the candidate invoice.
    relevant = [
        row
        for row in allocations
        if row.get("payment_id") == payment_id or row.get("invoice_id") in candidate_ids
    ]
    if any(
        row.get("payment_id") == payment_id and row.get("status") == "posted" for row in relevant
    ):
        return "confirmed", "PRIOR_ALLOC_PAYMENT"
    if any(
        row.get("payment_id") == payment_id and row.get("status") == "pending" for row in relevant
    ):
        return "present", "PRIOR_ALLOC_PAYMENT"
    if any(
        row.get("invoice_id") in candidate_ids
        and row.get("payment_id") != payment_id
        and row.get("status") in {"pending", "posted"}
        for row in relevant
    ):
        return "conflict", "PRIOR_ALLOC_INVOICE_PENDING"
    if any(row.get("status") not in {"pending", "posted"} for row in relevant):
        return "unknown", "PRIOR_ALLOC_UNKNOWN"
    return "clear", None
