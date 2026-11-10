from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Protocol


class KYCStatusProvider(Protocol):
    """Callable contract for an authoritative KYC status source."""

    def __call__(self, client_id: str) -> str | None: ...


def check_kyc_status(status: str | None) -> dict[str, Any]:
    normalized = status.strip().lower() if isinstance(status, str) else ""
    if normalized in {"missing", "expired"}:
        return {
            "status": "blocked",
            "message": "Current KYC is required before new product requests.",
            "requires_kyc": True,
        }
    if normalized == "pending":
        return {
            "status": "pending",
            "message": "KYC review is in progress.",
            "requires_kyc": True,
        }
    if normalized == "current":
        return {
            "status": "approved",
            "message": "KYC is current.",
            "requires_kyc": False,
        }
    return {
        "status": "blocked",
        "message": "KYC status could not be verified. Product requests are unavailable.",
        "requires_kyc": True,
    }


def flag_aml_activity(metrics: dict[str, Any]) -> dict[str, Any]:
    required = ("monthly_transactions", "threshold")
    missing = [key for key in required if key not in metrics or metrics[key] is None]
    if missing:
        return {
            "status": "insufficient_data",
            "severity": "unknown",
            "message": "AML review requires both activity metrics and an approved threshold.",
            "missing_fields": missing,
        }

    try:
        monthly_transactions = Decimal(str(metrics["monthly_transactions"]))
        threshold = Decimal(str(metrics["threshold"]))
    except (InvalidOperation, ValueError, TypeError):
        monthly_transactions = Decimal("NaN")
        threshold = Decimal("NaN")

    invalid = []
    if not monthly_transactions.is_finite() or monthly_transactions < 0:
        invalid.append("monthly_transactions")
    if not threshold.is_finite() or threshold <= 0:
        invalid.append("threshold")
    if invalid:
        return {
            "status": "insufficient_data",
            "severity": "unknown",
            "message": "AML review requires finite non-negative activity and a positive threshold.",
            "invalid_fields": invalid,
        }

    if monthly_transactions >= threshold:
        return {
            "status": "flagged",
            "severity": "high",
            "message": "AML threshold crossed; compliance review required.",
        }
    return {"status": "clear", "severity": "low", "message": "No AML concern detected."}
