from __future__ import annotations


def check_kyc_status(status: str) -> dict:
    if status in {"missing", "expired"}:
        return {
            "status": "blocked",
            "message": "Current KYC is required before new product requests.",
        }
    return {"status": "approved", "message": "KYC is current."}


def flag_aml_activity(metrics: dict) -> dict:
    monthly_transactions = float(metrics.get("monthly_transactions", 0))
    threshold = float(metrics.get("threshold", 0))

    if monthly_transactions >= threshold:
        return {
            "status": "flagged",
            "severity": "high",
            "message": "AML threshold crossed; compliance review required.",
        }
    return {"status": "clear", "severity": "low", "message": "No AML concern detected."}
