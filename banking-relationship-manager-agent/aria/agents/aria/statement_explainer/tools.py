from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from aria.agents.aria.statement_explainer.models import StatementTransaction

MAX_TRANSACTION_ROWS = 500
MAX_RESULT_ROWS = 100


def _validated_rows(
    transactions: Iterable[StatementTransaction | Mapping[str, Any]],
) -> list[StatementTransaction]:
    rows = [
        item if isinstance(item, StatementTransaction) else StatementTransaction.model_validate(item)
        for item in transactions
    ]
    if len(rows) > MAX_TRANSACTION_ROWS:
        raise ValueError("statement analysis row limit exceeded")
    ids = [row.trans_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("statement analysis rows contain duplicate transaction IDs")
    return sorted(rows, key=lambda item: (item.value_date, item.trans_id))


def _date_range(start_date: str | None, end_date: str | None) -> tuple[str | None, str | None]:
    try:
        start = date.fromisoformat(start_date).isoformat() if start_date else None
        end = date.fromisoformat(end_date).isoformat() if end_date else None
    except (TypeError, ValueError) as exc:
        raise ValueError("date filters must be ISO dates") from exc
    if start and end and start > end:
        raise ValueError("start_date must not be after end_date")
    return start, end


def _amount(value: Decimal | str | int | float | None) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("amount filter must be a finite decimal") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("amount filter must be a finite non-negative decimal")
    return result


def _row_dict(transaction: StatementTransaction) -> dict[str, Any]:
    return transaction.model_dump(mode="json")


def get_transactions(
    transactions: Iterable[StatementTransaction | Mapping[str, Any]],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    dr_cr_ind: str | None = None,
    min_amount: Decimal | str | int | float | None = None,
    narrative_keyword: str | None = None,
    category: str | None = None,
    max_results: int = MAX_RESULT_ROWS,
) -> list[dict[str, Any]]:
    if isinstance(max_results, bool) or not 1 <= max_results <= MAX_RESULT_ROWS:
        raise ValueError(f"max_results must be between 1 and {MAX_RESULT_ROWS}")
    start, end = _date_range(start_date, end_date)
    minimum = _amount(min_amount)
    direction = str(dr_cr_ind).upper() if dr_cr_ind is not None else None
    if direction is not None and direction not in {"D", "C"}:
        raise ValueError("dr_cr_ind must be 'D' or 'C'")
    category_name = str(category).strip().lower() if category else None
    needle = str(narrative_keyword).strip().lower() if narrative_keyword else None

    rows = _validated_rows(transactions)
    matches = [
        row
        for row in rows
        if (start is None or row.value_date >= start)
        and (end is None or row.value_date <= end)
        and (direction is None or row.dr_cr_ind == direction)
        and (minimum is None or row.amount >= minimum)
        and (category_name is None or row.category == category_name)
        and (needle is None or needle in row.narrative.lower())
    ]
    return [_row_dict(row) for row in matches[:max_results]]


def summarise_period(
    transactions: Iterable[StatementTransaction | Mapping[str, Any]],
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    rows = get_transactions(transactions, start_date=start_date, end_date=end_date)
    debit_total = sum(
        (Decimal(row["amount"]) for row in rows if row["dr_cr_ind"] == "D"), Decimal("0")
    )
    credit_total = sum(
        (Decimal(row["amount"]) for row in rows if row["dr_cr_ind"] == "C"), Decimal("0")
    )
    category_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        if row["dr_cr_ind"] == "D":
            category_totals[str(row["category"])] += Decimal(row["amount"])
    return {
        "start_date": start_date,
        "end_date": end_date,
        "transaction_count": len(rows),
        "debit_total": debit_total,
        "credit_total": credit_total,
        "net_movement": credit_total - debit_total,
        "average_transaction_size": (debit_total + credit_total) / Decimal(len(rows))
        if rows
        else Decimal("0"),
        "category_totals": dict(sorted(category_totals.items())),
        "transaction_ids": [row["trans_id"] for row in rows],
    }


def categorise_spend(
    transactions: Iterable[StatementTransaction | Mapping[str, Any]],
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    rows = get_transactions(
        transactions,
        start_date=start_date,
        end_date=end_date,
        dr_cr_ind="D",
    )
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    ids_by_category: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        category = str(row["category"])
        totals[category] += Decimal(row["amount"])
        ids_by_category[category].append(str(row["trans_id"]))
    return {
        "start_date": start_date,
        "end_date": end_date,
        "category_totals": dict(sorted(totals.items())),
        "transaction_ids": [item for ids in ids_by_category.values() for item in ids],
        "categories": dict(sorted(ids_by_category.items())),
    }


def compare_category_spend(
    transactions: Iterable[StatementTransaction | Mapping[str, Any]],
    category: str,
    *,
    current_start: str,
    current_end: str,
    prior_start: str,
    prior_end: str,
) -> dict[str, Any]:
    current_rows = get_transactions(
        transactions,
        start_date=current_start,
        end_date=current_end,
        dr_cr_ind="D",
        category=category,
    )
    prior_rows = get_transactions(
        transactions,
        start_date=prior_start,
        end_date=prior_end,
        dr_cr_ind="D",
        category=category,
    )
    current_total = sum((Decimal(row["amount"]) for row in current_rows), Decimal("0"))
    prior_total = sum((Decimal(row["amount"]) for row in prior_rows), Decimal("0"))
    difference = current_total - prior_total
    return {
        "category": category,
        "current_period": {"start_date": current_start, "end_date": current_end},
        "prior_period": {"start_date": prior_start, "end_date": prior_end},
        "current_total": current_total,
        "prior_total": prior_total,
        "change": difference,
        "absolute_change": abs(difference),
        "current_transaction_ids": [row["trans_id"] for row in current_rows],
        "prior_transaction_ids": [row["trans_id"] for row in prior_rows],
    }


def detect_anomalies(
    transactions: Iterable[StatementTransaction | Mapping[str, Any]],
    category: str,
    current_start: str,
    current_end: str,
    *,
    threshold_multiplier: Decimal | str | float = Decimal("1.5"),
) -> dict[str, Any]:
    start, end = _date_range(current_start, current_end)
    if start is None or end is None:
        raise ValueError("current period dates are required")
    start_date_value = date.fromisoformat(start)
    month_index = start_date_value.year * 12 + start_date_value.month - 1
    baseline_months: list[str] = []
    for offset in (3, 2, 1):
        prior_index = month_index - offset
        year, month_zero = divmod(prior_index, 12)
        baseline_months.append(f"{year:04d}-{month_zero + 1:02d}")

    rows = _validated_rows(transactions)
    category_name = category.strip().lower()
    current_rows = [
        row
        for row in rows
        if row.category == category_name
        and row.dr_cr_ind == "D"
        and start <= row.value_date <= end
    ]
    baseline_rows = [
        row
        for row in rows
        if row.category == category_name
        and row.dr_cr_ind == "D"
        and row.value_date[:7] in baseline_months
    ]
    current_total = sum((row.amount for row in current_rows), Decimal("0"))
    baseline_total = sum((row.amount for row in baseline_rows), Decimal("0"))
    if baseline_total == 0:
        return {
            "status": "insufficient_data",
            "category": category_name,
            "baseline_months": baseline_months,
            "baseline_monthly_average": Decimal("0"),
            "deviation_percent": Decimal("0"),
            "current_period_total": current_total,
            "baseline_transaction_ids": [],
            "transaction_ids": [row.trans_id for row in current_rows],
        }

    baseline_average = baseline_total / Decimal(3)
    threshold = _amount(threshold_multiplier)
    if threshold is None:
        raise ValueError("threshold_multiplier is required")
    deviation = ((current_total - baseline_average) / baseline_average) * Decimal("100")
    return {
        "status": "ok" if current_total >= baseline_average * threshold else "normal",
        "category": category_name,
        "baseline_months": baseline_months,
        "baseline_monthly_average": baseline_average,
        "deviation_percent": deviation,
        "current_period_total": current_total,
        "threshold_multiplier": threshold,
        "baseline_transaction_ids": [row.trans_id for row in baseline_rows],
        "transaction_ids": [row.trans_id for row in current_rows],
    }


def explain_transaction(
    transactions: Iterable[StatementTransaction | Mapping[str, Any]],
    trans_id: str,
) -> dict[str, Any]:
    matches = [row for row in _validated_rows(transactions) if row.trans_id == trans_id]
    if not matches:
        return {"trans_id": trans_id, "status": "not_found"}
    if len(matches) != 1:
        return {"trans_id": trans_id, "status": "ambiguous"}
    return {**_row_dict(matches[0]), "status": "ok"}


__all__ = [
    "categorise_spend",
    "compare_category_spend",
    "detect_anomalies",
    "explain_transaction",
    "get_transactions",
    "summarise_period",
]
